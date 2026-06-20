"""
Phase 260.5.D — Encoding-gate integration tests on
``DatasetService.create_dataset_from_file``.

The pure-unit tests in :mod:`test_encoding_detection` cover the
detector primitive. These tests verify that the gate is actually
WIRED into the service path: a file whose bytes can't be decoded
with high confidence MUST be rejected before pandas sees them, and
the rejection MUST surface as HTTP 400 with code
``FILE_ENCODING_UNSUPPORTED``.

Three layers:

1. **Service layer** — direct ``service.create_dataset(...)``
   calls; uploads bytes to MinIO, asserts the typed
   ``ValidationError(code='FILE_ENCODING_UNSUPPORTED')`` propagates.
2. **API layer** — ``POST /api/v1/datasets/`` returns 400 with the
   correct envelope.
3. **Carve-out** — Parquet content is NOT gated (binary format
   has its own validation; gating it would produce false 400s on
   legitimate uploads).

All tests skip gracefully when MinIO is unavailable, matching the
260.4 / 260.5 family pattern.
"""

from __future__ import annotations

import os
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.core.services.base import ValidationError as ServiceValidationError
from hub.apps.datasets.models import Dataset
from hub.apps.datasets.services import DatasetService
from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

from hub.apps.datasets.tests.conftest import extract_error_code

User = get_user_model()


class _DatasetEncodingTestMixin:
    """Shared setUp for tenant + user + MinIO availability check.

    Uses ``TransactionTestCase`` because S3/MinIO interactions need
    real per-connection transactions (matches the pattern in
    ``test_file_active_precondition.DatasetCreateActiveFileSucceedsTest``).
    """

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
            name=f"Enc T {uid}",
            slug=f"enc-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"enc-{uid}@example.com",
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
        self,
        *,
        body: bytes,
        name: str,
        content_type: str,
    ) -> File:
        """Upload bytes to MinIO + create matching ACTIVE File row."""
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


class DatasetCreateEncodingServiceLayerTest(_DatasetEncodingTestMixin, TransactionTestCase):
    """Phase 260.5.D — service-layer assertions on the encoding gate."""

    @pytest.mark.integration
    def test_well_formed_utf8_csv_admits(self):
        # Sanity / regression: the gate MUST NOT block legitimate
        # UTF-8 CSV. If this test fails after a charset_normalizer
        # version bump the threshold may need to be re-tuned; but
        # the gate itself should never reject pure ASCII / well-
        # formed UTF-8.
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        body = "id,name,note\n1,Alice,café\n2,Bob,müller\n".encode()
        f = self._make_active_file(body=body, name="utf8.csv", content_type="text/csv")

        ds = self.service.create_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            file_id=str(f.id),
        )
        self.assertEqual(ds.format, "CSV")
        self.assertIsNotNone(ds.schema_json)

    @pytest.mark.integration
    def test_random_bytes_csv_rejects_with_typed_error(self):
        # The gate MUST raise the typed FILE_ENCODING_UNSUPPORTED
        # code, NOT the generic BUSINESS_RULES_VALIDATION umbrella
        # AND NOT the generic "Schema inference failed" wrapper.
        # The re-raise in services.py preserves the typed code.
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        body = os.urandom(2000)
        f = self._make_active_file(body=body, name="garbage.csv", content_type="text/csv")

        with self.assertRaises(ServiceValidationError) as ctx:
            self.service.create_dataset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                file_id=str(f.id),
            )
        self.assertEqual(
            getattr(ctx.exception, "code", None),
            "FILE_ENCODING_UNSUPPORTED",
            f"Expected typed code; got {ctx.exception!r}",
        )
        self.assertEqual(
            getattr(ctx.exception, "http_status", None),
            400,
            "FILE_ENCODING_UNSUPPORTED must surface as HTTP 400",
        )
        # Confidence MUST appear in details so operators can
        # decide whether to ask the tenant to re-encode or to
        # raise the platform's threshold for legacy data.
        details = getattr(ctx.exception, "details", {}) or {}
        self.assertIn("confidence", details)
        self.assertIn("min_confidence", details)
        self.assertEqual(details["file_format"], "CSV")
        # NO Dataset row should have been created.
        self.assertEqual(
            Dataset.objects.filter(tenant=self.tenant, file=f).count(),
            0,
            "Encoding gate must reject BEFORE Dataset row creation",
        )

    @pytest.mark.integration
    def test_parquet_with_random_bytes_passes_encoding_gate(self):
        # Carve-out: Parquet is binary; the gate skips it. The
        # downstream parquet parser will raise its own error if
        # the bytes are not a valid Parquet file — but that is
        # NOT FILE_ENCODING_UNSUPPORTED.
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        body = os.urandom(2000)
        f = self._make_active_file(
            body=body,
            name="garbage.parquet",
            content_type="application/parquet",
        )

        with self.assertRaises(ServiceValidationError) as ctx:
            self.service.create_dataset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                file_id=str(f.id),
            )
        # The error from the parquet parser is wrapped in the
        # generic schema-inference umbrella; what matters here is
        # that the encoding gate did NOT fire.
        self.assertNotEqual(
            getattr(ctx.exception, "code", None),
            "FILE_ENCODING_UNSUPPORTED",
            "Parquet must NOT be gated by the text-encoding rule",
        )


class DatasetCreateEncodingAPILayerTest(_DatasetEncodingTestMixin, TransactionTestCase):
    """Phase 260.5.D.2 acceptance: 400 with FILE_ENCODING_UNSUPPORTED
    over the wire."""

    @pytest.mark.integration
    def test_api_400_when_csv_bytes_undetectable(self):
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        body = os.urandom(2000)
        f = self._make_active_file(body=body, name="bad.csv", content_type="text/csv")

        response = self.client.post(
            "/api/v1/datasets/",
            data={"file_id": str(f.id)},
            format="json",
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            f"Expected 400; got body={response.data!r}",
        )
        code = extract_error_code(response.data)
        self.assertEqual(
            code,
            "FILE_ENCODING_UNSUPPORTED",
            f"Expected FILE_ENCODING_UNSUPPORTED; got body={response.data!r}",
        )

    @pytest.mark.integration
    def test_api_201_when_csv_is_valid_utf8(self):
        # Happy path — the gate must not regress legitimate uploads.
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        body = b"id,amount\n1,10\n2,20\n"
        f = self._make_active_file(body=body, name="ok.csv", content_type="text/csv")

        response = self.client.post(
            "/api/v1/datasets/",
            data={"file_id": str(f.id)},
            format="json",
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            f"Valid UTF-8 was rejected: body={response.data!r}",
        )


# ---------------------------------------------------------------------------
# Phase 260.5.D.R1 GAP-A — refresh-path encoding gate
# ---------------------------------------------------------------------------
#
# The initial 260.5.D wiring placed the gate in
# ``DatasetService.create_dataset`` only — ``refresh.py`` had its own
# format-dispatch block that bypassed the gate. A user could create
# a dataset against a clean UTF-8 file (admitted), then refresh
# against a re-uploaded mojibake file and silently end up with
# scrambled schema. R1 fix routes the refresh path through the
# canonical ``infer_schema_with_encoding_gate`` helper; these tests
# pin the API contract end-to-end.


def _grant_tenant_admin(user, tenant):
    """Grant TENANT_ADMIN to ``user`` for ``tenant``.

    The ``Role`` model carries a ``NOT NULL`` ``tenant`` FK
    (hub/apps/users/models.py:267-272), so the get_or_create must
    include ``tenant=tenant`` — otherwise the implicit insert hits
    ``IntegrityError: null value in column "tenant_id"``.
    """
    from hub.apps.users.models import Role, UserRole

    role, _ = Role.objects.get_or_create(
        tenant=tenant,
        name="TENANT_ADMIN",
        defaults={"description": "Tenant Administrator"},
    )
    UserRole.objects.get_or_create(user=user, tenant=tenant, role=role)


class DatasetRefreshEncodingGateAPITest(TransactionTestCase):
    """Phase 260.5.D.R1 GAP-A — manual refresh action must gate."""

    def setUp(self):
        super().setUp()
        from hub.apps.assets.models import Asset, AssetStatus
        from hub.apps.datasets.models import DatasetStatus
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
            name=f"Refresh-Enc {uid}",
            slug=f"refresh-enc-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"refresh-enc-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        # Manual refresh requires TENANT_ADMIN role.
        _grant_tenant_admin(self.user, self.tenant)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"refresh-enc-asset-{uid}",
            name="Refresh-Enc Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )
        self._dataset_status_active = DatasetStatus.ACTIVE

    def _seed_dataset_with_file(self, *, body: bytes) -> Dataset:
        """Seed a dataset bound to a file. Storage upload uses the
        same shape as DatasetCreateActiveFileSucceedsTest.
        """
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")
        file_id = uuid.uuid4()
        storage_path = f"{self.tenant.id}/{file_id}/data.csv"
        self.storage_client.upload_file(storage_path, body, "text/csv")
        f = File.objects.create(
            id=file_id,
            tenant=self.tenant,
            name="data.csv",
            content_type="text/csv",
            size=len(body),
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=storage_path,
            created_by=self.user,
        )
        return Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=f,
            schema_json={"columns": []},
            sample_data_json=[],
            row_count=0,
            format="CSV",
            version=1,
            status=self._dataset_status_active,
            created_by=self.user,
        )

    @pytest.mark.integration
    def test_refresh_returns_400_when_re_fetched_file_is_undetectable(self):
        # Seed a dataset against a CLEAN UTF-8 file (admit). Then
        # OVERWRITE the storage object with random bytes so the next
        # refresh reads garbage. The gate must reject with 400 +
        # FILE_ENCODING_UNSUPPORTED. Without the R1 fix this would
        # have silently produced an empty schema.
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")
        ds = self._seed_dataset_with_file(body=b"id,name\n1,alice\n2,bob\n")
        # Overwrite the underlying object with garbage AT THE SAME
        # storage_path.
        self.storage_client.upload_file(ds.file.storage_path, os.urandom(2000), "text/csv")

        response = self.client.post(
            f"/api/v1/datasets/{ds.id}/refresh/",
            data={},
            format="json",
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            f"Refresh did not 400 on bad encoding; body={response.data!r}",
        )
        code = extract_error_code(response.data)
        self.assertEqual(
            code,
            "FILE_ENCODING_UNSUPPORTED",
            f"Expected FILE_ENCODING_UNSUPPORTED; got body={response.data!r}",
        )

    @pytest.mark.integration
    def test_refresh_returns_200_when_file_is_clean_utf8(self):
        # Regression guard: the gate must NOT block a clean refresh,
        # and the schema must be re-inferred from the file content.
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")
        ds = self._seed_dataset_with_file(body=b"id,name\n1,alice\n")

        response = self.client.post(
            f"/api/v1/datasets/{ds.id}/refresh/",
            data={},
            format="json",
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            f"Clean UTF-8 refresh was rejected: body={response.data!r}",
        )
        # The refresh endpoint wraps the updated dataset under the
        # "dataset" key alongside "schema_drift" and "schema_changed".
        self.assertIn("dataset", response.data,
                      "Refresh response must include dataset key")
        self.assertIn("schema_json", response.data["dataset"],
                      "Refreshed dataset must include re-inferred schema_json")
