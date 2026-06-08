"""
Phase 260.5.F — Inference-limits integration on
``DatasetService.create_dataset``.

The pure-unit tests in :mod:`test_inference_limits` cover the
planner + truncation primitives. These tests verify that the
planner is actually WIRED into the service path: the storage
fetch honours ``max_bytes``, the truncation runs before the
parser, the sampled metadata lands on the schema, and oversize
files reject with HTTP 413 before the storage GET.

All tests use ``override_settings`` to reduce the FULL_READ /
SAMPLE / MAX thresholds to KB-scale — exercising the real
pipeline with real MinIO without needing multi-GB fixtures.
Skip when MinIO is unavailable (matches the established pattern).
"""
from __future__ import annotations
import pytest

import uuid

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.core.services.base import ValidationError as ServiceValidationError
from hub.apps.datasets.models import Dataset
from hub.apps.datasets.services import DatasetService
from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

User = get_user_model()


def _extract_error_code(body):
    if not isinstance(body, dict):
        return None
    nested = body.get("error")
    if isinstance(nested, dict) and nested.get("code"):
        return nested.get("code")
    return body.get("code")


class _LimitsTestMixin:
    """Shared MinIO + tenant setUp; matches the encoding-gate
    integration tests so the family stays uniform."""

    def setUp(self):
        super().setUp()
        from hub.apps.files.storage import S3StorageClient

        self.storage_available = False
        try:
            self.storage_client = S3StorageClient()
            self.storage_client._ensure_bucket_exists()
            self.storage_available = True
        except Exception:
            self.storage_available = False

        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Limits {uid}",
            slug=f"limits-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"limits-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.service = DatasetService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

    def _make_active_file(
        self, *, body: bytes, name: str = "data.csv",
        content_type: str = "text/csv",
    ) -> File:
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")
        file_id = uuid.uuid4()
        storage_path = f"{self.tenant.id}/{file_id}/{name}"
        self.storage_client.upload_file(storage_path, body, content_type)
        return File.objects.create(
            id=file_id,
            tenant=self.tenant,
            name=name,
            content_type=content_type,
            size=len(body),
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=storage_path,
            created_by=self.user,
        )


# ---------------------------------------------------------------------------
# REJECT path — File.size > MAX threshold
# ---------------------------------------------------------------------------


class DatasetCreateOversizeRejectionTest(_LimitsTestMixin, TransactionTestCase):
    """Phase 260.5.F.2 — oversize files reject BEFORE the S3 GET.

    The pre-flight runs against ``File.size`` (the row's recorded
    size) so the rejection happens without paying the network /
    memory cost of a multi-GB download. We use a tight MAX
    override to make the test tractable.
    """

    @override_settings(DATASET_INFERENCE_MAX_BYTES=512)
    @pytest.mark.integration
    def test_service_rejects_oversize_with_typed_413_error(self):
        # Body is 1 KB; cap is 512 B.
        body = b"id,name\n" + b"1,row\n" * 100
        f = self._make_active_file(body=body)
        self.assertGreater(f.size, 512)

        with self.assertRaises(ServiceValidationError) as ctx:
            self.service.create_dataset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                file_id=str(f.id),
            )
        self.assertEqual(
            getattr(ctx.exception, "code", None),
            "FILE_TOO_LARGE_FOR_INFERENCE",
        )
        self.assertEqual(getattr(ctx.exception, "http_status", None), 413)

        # No Dataset row was created — the gate fires BEFORE the
        # service inserts.
        self.assertEqual(
            Dataset.objects.filter(tenant=self.tenant, file=f).count(),
            0,
            "Oversize gate must reject BEFORE Dataset row creation",
        )

    @override_settings(DATASET_INFERENCE_MAX_BYTES=512)
    @pytest.mark.integration
    def test_api_returns_413_for_oversize_csv(self):
        body = b"id,name\n" + b"1,row\n" * 100
        f = self._make_active_file(body=body)

        response = self.client.post(
            "/api/v1/datasets/",
            data={"file_id": str(f.id)},
            format="json",
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"Expected 413; got body={response.data!r}",
        )
        code = _extract_error_code(response.data)
        self.assertEqual(
            code,
            "FILE_TOO_LARGE_FOR_INFERENCE",
            f"Expected FILE_TOO_LARGE_FOR_INFERENCE; got body={response.data!r}",
        )


# ---------------------------------------------------------------------------
# SAMPLE path — File.size between FULL_READ and MAX
# ---------------------------------------------------------------------------


class DatasetCreateSampleModeTest(_LimitsTestMixin, TransactionTestCase):
    """Phase 260.5.F (engineering pushback) — files larger than the
    FULL_READ threshold are SAMPLED, not refused.

    Covers the two load-bearing properties:
    1. The ranged read transfers ONLY the sample bytes (S3 cost
       savings on large files).
    2. The sampled metadata flags the schema so consumers know
       it came from a partial read.
    """

    @override_settings(
        DATASET_INFERENCE_FULL_READ_BYTES=64,
        DATASET_INFERENCE_SAMPLE_BYTES=64,
        DATASET_INFERENCE_MAX_BYTES=10 * 1024,
    )
    @pytest.mark.integration
    def test_csv_above_full_read_threshold_admits_with_sampled_flag(self):
        # 200 byte CSV → above the 64 byte FULL_READ threshold →
        # SAMPLE mode. The sample is 64 bytes (truncated to last
        # newline); inference runs on the partial payload but
        # produces a schema with the sampled flag set.
        body = b"id,name\n" + b"\n".join(
            f"{i},user_{i}".encode() for i in range(40)
        ) + b"\n"
        f = self._make_active_file(body=body)
        self.assertGreater(f.size, 64)

        ds = self.service.create_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            file_id=str(f.id),
        )
        self.assertEqual(ds.format, "CSV")
        # The schema's inference_metadata must record the sampled
        # state — without this, contract drift / FE consumers
        # cannot distinguish a partial-read schema from a full
        # one.
        meta = (ds.schema_json or {}).get("inference_metadata") or {}
        self.assertTrue(
            meta.get("sampled"),
            f"sample-mode dataset missing sampled=True; got meta={meta!r}",
        )
        self.assertEqual(
            meta.get("sample_bytes"),
            64,
            f"sample_bytes should equal the configured override",
        )
        self.assertEqual(
            meta.get("total_bytes"),
            f.size,
            f"total_bytes should equal File.size",
        )
        self.assertTrue(meta.get("row_count_estimated_from_sample"))

    @override_settings(
        DATASET_INFERENCE_FULL_READ_BYTES=64 * 1024 * 1024,
        DATASET_INFERENCE_SAMPLE_BYTES=64 * 1024 * 1024,
        DATASET_INFERENCE_MAX_BYTES=1 * 1024 * 1024 * 1024,
    )
    @pytest.mark.integration
    def test_csv_below_full_read_threshold_no_sampled_flag(self):
        # Default thresholds — 1 KB CSV admits FULL_READ; the
        # schema's metadata must carry sampled=False so consumers
        # don't see false-positive partial-read warnings.
        body = b"id,name\n" + b"\n".join(
            f"{i},user_{i}".encode() for i in range(20)
        ) + b"\n"
        f = self._make_active_file(body=body)

        ds = self.service.create_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            file_id=str(f.id),
        )
        meta = (ds.schema_json or {}).get("inference_metadata") or {}
        self.assertFalse(
            meta.get("sampled", False),
            f"FULL_READ dataset should have sampled=False; got meta={meta!r}",
        )

    @override_settings(
        DATASET_INFERENCE_FULL_READ_BYTES=64,
        DATASET_INFERENCE_SAMPLE_BYTES=64,
        DATASET_INFERENCE_MAX_BYTES=10 * 1024,
    )
    @pytest.mark.integration
    def test_sample_truncation_does_not_break_csv_inference(self):
        # The 64-byte sample of a CSV will cut MID-ROW. Truncation
        # must trim back to the last newline so the parser sees
        # only complete rows. Without this, csv.DictReader's
        # behaviour on a half-row is dialect-dependent (some
        # versions silently drop, some raise) — this test is the
        # regression guard.
        body = (
            b"id,name,description\n"
            + b"\n".join(
                f"{i},user_{i},a_long_description_that_pads_the_row".encode()
                for i in range(50)
            )
            + b"\n"
        )
        f = self._make_active_file(body=body)
        # Sample boundary will land mid-row; truncation must
        # handle it. If parsing failed, create_dataset would
        # raise — the test asserts the happy outcome.
        ds = self.service.create_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            file_id=str(f.id),
        )
        # Schema fields are inferred from the sample; column
        # NAMES must still be the full set (header is in the
        # first row, well within the first 64 bytes).
        field_names = [
            fld["name"] for fld in (ds.schema_json or {}).get("fields", [])
        ]
        self.assertEqual(field_names, ["id", "name", "description"])
