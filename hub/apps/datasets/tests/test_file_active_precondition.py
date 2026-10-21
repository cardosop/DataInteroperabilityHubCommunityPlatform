"""
Phase 260.5.B — File.status precondition for dataset creation.

Verifies the ``ValidateFileActive`` rule rejects dataset creation
against files that are not in an admit-state (anything outside
``ACTIVE``) AND surfaces the rejection as HTTP 400 with code
``FILE_NOT_READY_FOR_DATASET``.

Phase 260.6.A retired the legacy ``COMPLETED`` value from
``FileStatus``; ``ACTIVE`` is the sole post-260.6.A terminal
upload state.

Three layers:

1. **Rule-layer unit tests** — pure ``DatasetsBusinessRules.validate(
   ..., validation_type="file_active")`` calls against in-memory File
   instances. No DB plumbing, no S3, no HTTP. Verifies the
   admit-set + reject-set + the file-is-None special case.

2. **Service-layer integration test** — calls
   ``DatasetService.create_dataset`` directly with a File row in each
   non-admit status. Asserts the correct ``ValidationError`` is
   raised with the documented code. Skips the schema-inference path
   because the rejection happens BEFORE the S3 fetch.

3. **API-layer pytest acceptance** — ``POST /api/v1/datasets/``
   with files in each non-admit status returns 400 with the
   documented error envelope. Active file with real bytes returns
   201 (skips when MinIO is unavailable).
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.core.services.base import ValidationError as ServiceValidationError
from hub.apps.datasets.business_rules import DatasetsBusinessRules
from hub.apps.datasets.models import Dataset
from hub.apps.datasets.services import DatasetService
from hub.apps.datasets.tests.test_base import DatasetsAPITestBase
from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

User = get_user_model()


# ---------------------------------------------------------------------------
# Layer 1 — Rule-layer unit tests
# ---------------------------------------------------------------------------


class ValidateFileActiveRuleTest(TestCase):
    """Pure rule unit tests — no DB rows needed.

    Exercises ``DatasetsBusinessRules._validate_file_active`` via a
    minimal File-shaped duck type (a class with a ``status`` attr +
    an ``id`` attr is sufficient — the rule reads only those two).
    Avoids the DB cost of seeding 7 different File rows for each
    status enum value.
    """

    def setUp(self):
        self.rules = DatasetsBusinessRules(tenant_id=str(uuid.uuid4()), user_id=str(uuid.uuid4()))

    class _FakeFile:
        """Duck-typed File: rule only reads ``id`` + ``status``."""

        def __init__(self, status_value: str) -> None:
            self.id = uuid.uuid4()
            self.status = status_value

    @pytest.mark.integration
    def test_admits_active_file(self):
        # Phase 260.6.A — ACTIVE is the only terminal upload
        # state (legacy ``COMPLETED`` retired via migration
        # ``0009_drop_completed_file_status``). The rule's
        # admit-set is pinned to {ACTIVE} only; a future status
        # addition would require an explicit code change AND a
        # corresponding test update at the pinned-set assertion
        # below.
        result = self.rules._validate_file_active(self._FakeFile(FileStatus.ACTIVE))
        self.assertTrue(result.is_valid)
        self.assertEqual(result.errors, [])
        self.assertTrue(result.details["admitted"])

    @pytest.mark.integration
    def test_rejects_pending_file(self):
        result = self.rules._validate_file_active(self._FakeFile(FileStatus.PENDING))
        self.assertFalse(result.is_valid)
        self.assertEqual(result.details["error_code"], "FILE_NOT_READY_FOR_DATASET")
        # Error message names the actionable next step.
        self.assertIn("wait for the upload to complete", result.errors[0].lower())

    @pytest.mark.integration
    def test_rejects_uploading_file(self):
        result = self.rules._validate_file_active(self._FakeFile(FileStatus.UPLOADING))
        self.assertFalse(result.is_valid)
        self.assertEqual(result.details["error_code"], "FILE_NOT_READY_FOR_DATASET")

    @pytest.mark.integration
    def test_rejects_deleting_file(self):
        result = self.rules._validate_file_active(self._FakeFile(FileStatus.DELETING))
        self.assertFalse(result.is_valid)
        self.assertEqual(result.details["error_code"], "FILE_NOT_READY_FOR_DATASET")

    @pytest.mark.integration
    def test_rejects_deleted_file(self):
        result = self.rules._validate_file_active(self._FakeFile(FileStatus.DELETED))
        self.assertFalse(result.is_valid)
        self.assertEqual(result.details["error_code"], "FILE_NOT_READY_FOR_DATASET")

    @pytest.mark.integration
    def test_rejects_failed_file(self):
        result = self.rules._validate_file_active(self._FakeFile(FileStatus.FAILED))
        self.assertFalse(result.is_valid)
        self.assertEqual(result.details["error_code"], "FILE_NOT_READY_FOR_DATASET")

    @pytest.mark.integration
    def test_admits_none_file(self):
        # File-less validation is admitted — the file_relationship
        # validator handles dataset-without-file separately.
        result = self.rules._validate_file_active(None)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.details["reason"], "file_not_provided")

    @pytest.mark.integration
    def test_admit_set_pinned_to_active_only(self):
        # Phase 260.6.A — admit set narrowed to {ACTIVE} only
        # (legacy ``COMPLETED`` retired via migration
        # ``0009_drop_completed_file_status``). A future status
        # addition would need a code change at this exact site
        # (the pinned frozenset on the rules class) — the test
        # makes the set's contents explicit so a future drift is
        # loud.
        self.assertEqual(
            DatasetsBusinessRules._FILE_STATUSES_ALLOWING_DATASET_CREATION,
            frozenset({FileStatus.ACTIVE}),
        )


# ---------------------------------------------------------------------------
# Layer 2 — Service-layer integration test
# ---------------------------------------------------------------------------


class DatasetServiceFileActivePreconditionTest(TestCase):
    """``DatasetService.create_dataset`` raises ServiceValidationError
    with code ``FILE_NOT_READY_FOR_DATASET`` for non-admit-status
    files. No S3 fetch happens because the rejection fires BEFORE
    the schema-inference branch."""

    def setUp(self):
        super().setUp()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"FA T {uid}",
            slug=f"fa-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"fa-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.service = DatasetService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

    def _make_file(self, status_value: str) -> File:
        file_id = uuid.uuid4()
        return File.objects.create(
            id=file_id,
            tenant=self.tenant,
            name="data.csv",
            content_type="text/csv",
            size=1024,
            status=status_value,
            scan_status=FileScanStatus.CLEAN,
            storage_path=f"{self.tenant.id}/{file_id}/data.csv",
            created_by=self.user,
        )

    def _assert_service_rejects(self, status_value: str) -> None:
        f = self._make_file(status_value)
        with self.assertRaises(ServiceValidationError) as ctx:
            self.service.create_dataset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                file_id=str(f.id),
            )
        # The error code is the contract anchor — SDK/FE consumers
        # branch on this string.
        self.assertEqual(getattr(ctx.exception, "code", None), "FILE_NOT_READY_FOR_DATASET")
        # No row landed (rejection fires before the INSERT branch).
        self.assertEqual(
            Dataset.objects.filter(tenant=self.tenant, file=f).count(),
            0,
        )

    @pytest.mark.integration
    def test_service_rejects_pending_file(self):
        self._assert_service_rejects(FileStatus.PENDING)

    @pytest.mark.integration
    def test_service_rejects_uploading_file(self):
        self._assert_service_rejects(FileStatus.UPLOADING)

    @pytest.mark.integration
    def test_service_rejects_deleting_file(self):
        self._assert_service_rejects(FileStatus.DELETING)

    @pytest.mark.integration
    def test_service_rejects_deleted_file(self):
        self._assert_service_rejects(FileStatus.DELETED)

    @pytest.mark.integration
    def test_service_rejects_failed_file(self):
        self._assert_service_rejects(FileStatus.FAILED)

    @pytest.mark.integration
    def test_service_rejects_pending_file_with_asset_link(self):
        # R1 audit GAP-A — the rule MUST fire regardless of whether
        # the create call carries an asset_id. Without this guard a
        # future refactor that gates the rule on "no asset" or
        # similar would silently regress the asset-linked path.
        from hub.apps.assets.models import Asset, AssetStatus

        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"asset-{uuid.uuid4().hex[:8]}",
            name="Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )
        f = self._make_file(FileStatus.PENDING)
        with self.assertRaises(ServiceValidationError) as ctx:
            self.service.create_dataset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                file_id=str(f.id),
                asset_id=str(asset.id),
            )
        self.assertEqual(
            getattr(ctx.exception, "code", None),
            "FILE_NOT_READY_FOR_DATASET",
        )
        self.assertEqual(
            Dataset.objects.filter(tenant=self.tenant, file=f).count(),
            0,
        )


# ---------------------------------------------------------------------------
# Layer 2b — Composition with the existing scan-status gate (Phase 260.2.D)
# ---------------------------------------------------------------------------


class FileActiveAndScanGateCompositionTest(TestCase):
    """R1 audit GAP-B — the new lifecycle rule (260.5.B) and the
    existing scan-status gate (260.2.D) MUST compose cleanly:

      * Lifecycle reject (e.g. PENDING + scan=CLEAN) → 260.5.B fires
        first with ``FILE_NOT_READY_FOR_DATASET`` (the cheaper
        check; saves the platform from running scan logic on a file
        that's not ready anyway).
      * Lifecycle admit + scan reject (e.g. ACTIVE + scan=PENDING_SCAN)
        → 260.5.B passes, 260.2.D rejects with ``FILE_SCAN_PENDING``.
      * Both reject (e.g. PENDING + scan=PENDING_SCAN) → 260.5.B
        wins (lifecycle is the cheaper / earlier failure).

    Without this composition test, a refactor that reorders the
    two gates would silently change which error code surfaces for
    a given input — SDK consumers would see a subtle behaviour
    drift without any test catching it.
    """

    def setUp(self):
        super().setUp()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Comp T {uid}",
            slug=f"comp-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"comp-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.service = DatasetService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

    def _make_file(
        self,
        *,
        status_value: str,
        scan_status_value: str,
    ) -> File:
        file_id = uuid.uuid4()
        return File.objects.create(
            id=file_id,
            tenant=self.tenant,
            name="data.csv",
            content_type="text/csv",
            size=1024,
            status=status_value,
            scan_status=scan_status_value,
            storage_path=f"{self.tenant.id}/{file_id}/data.csv",
            created_by=self.user,
        )

    @pytest.mark.integration
    def test_lifecycle_gate_fires_before_scan_gate(self):
        # PENDING (lifecycle reject) + CLEAN (scan admit) → 260.5.B wins.
        f = self._make_file(
            status_value=FileStatus.PENDING,
            scan_status_value=FileScanStatus.CLEAN,
        )
        with self.assertRaises(ServiceValidationError) as ctx:
            self.service.create_dataset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                file_id=str(f.id),
            )
        self.assertEqual(
            getattr(ctx.exception, "code", None),
            "FILE_NOT_READY_FOR_DATASET",
            (
                "Lifecycle gate (260.5.B) MUST fire BEFORE the scan gate "
                "(260.2.D) — file is in PENDING state which the lifecycle "
                "gate alone catches."
            ),
        )

    @override_settings(CLAMAV_ENABLED=True)
    @pytest.mark.integration
    def test_scan_gate_fires_when_lifecycle_admits(self):
        # ACTIVE (lifecycle admit) + PENDING_SCAN (scan reject) → 260.2.D wins.
        f = self._make_file(
            status_value=FileStatus.ACTIVE,
            scan_status_value=FileScanStatus.PENDING_SCAN,
        )
        with self.assertRaises(ServiceValidationError) as ctx:
            self.service.create_dataset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                file_id=str(f.id),
            )
        self.assertEqual(
            getattr(ctx.exception, "code", None),
            "FILE_SCAN_PENDING",
            (
                "Scan gate (260.2.D) MUST fire when the lifecycle gate "
                "admits — file is ACTIVE but scan is PENDING_SCAN, so "
                "the scan-status check is the load-bearing rejection."
            ),
        )

    @pytest.mark.integration
    def test_scan_gate_fires_for_infected_file(self):
        # ACTIVE + INFECTED → 260.2.D wins with FILE_INFECTED.
        f = self._make_file(
            status_value=FileStatus.ACTIVE,
            scan_status_value=FileScanStatus.INFECTED,
        )
        with self.assertRaises(ServiceValidationError) as ctx:
            self.service.create_dataset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                file_id=str(f.id),
            )
        self.assertEqual(
            getattr(ctx.exception, "code", None),
            "FILE_INFECTED",
        )


# ---------------------------------------------------------------------------
# Layer 3 — API-layer 400 + 201 acceptance
# ---------------------------------------------------------------------------


class DatasetCreateFileActivePreconditionAPITest(DatasetsAPITestBase):
    """``POST /api/v1/datasets/`` returns 400 with the documented
    error envelope for files in non-admit status."""

    def _make_file_in_status(self, status_value: str) -> File:
        file_id = uuid.uuid4()
        return File.objects.create(
            id=file_id,
            tenant=self.tenant,
            name=f"data-{status_value}.csv",
            content_type="text/csv",
            size=1024,
            status=status_value,
            scan_status=FileScanStatus.CLEAN,
            storage_path=f"{self.tenant.id}/{file_id}/data.csv",
            created_by=self.user,
        )

    def _assert_api_400(self, status_value: str) -> None:
        f = self._make_file_in_status(status_value)
        response = self.client.post(
            "/api/v1/datasets/",
            data={"file_id": str(f.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        body = response.data
        # Error envelope carries the documented code so SDK/FE
        # consumers can match without parsing the message.  The
        # ``api_error_response`` helper renders code at the top
        # level (``hub/apps/core/responses.py:73-80``); a nested
        # ``error.code`` shape was the legacy envelope.
        if isinstance(body, dict):
            code = body.get("code") or (body.get("error", {}) or {}).get("code")
        else:
            code = None
        self.assertEqual(
            code,
            "FILE_NOT_READY_FOR_DATASET",
            f"Expected error.code=FILE_NOT_READY_FOR_DATASET on {status_value} file; "
            f"got body={body!r}",
        )

    @pytest.mark.integration
    def test_api_400_pending(self):
        self._assert_api_400(FileStatus.PENDING)

    @pytest.mark.integration
    def test_api_400_uploading(self):
        self._assert_api_400(FileStatus.UPLOADING)

    @pytest.mark.integration
    def test_api_400_deleting(self):
        self._assert_api_400(FileStatus.DELETING)

    @pytest.mark.integration
    def test_api_400_deleted(self):
        self._assert_api_400(FileStatus.DELETED)

    @pytest.mark.integration
    def test_api_400_failed(self):
        self._assert_api_400(FileStatus.FAILED)


# ---------------------------------------------------------------------------
# Layer 3b — ACTIVE file → 201 (E2E with MinIO)
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class DatasetCreateActiveFileSucceedsTest(TransactionTestCase):
    """End-to-end: ``POST /api/v1/datasets/`` with an ACTIVE file
    that has real bytes in MinIO returns 201.

    Uses ``TransactionTestCase`` to avoid the outer-transaction
    issue with S3 cleanup; matches the established 260.4.A /
    260.4.D / 260.4.E / 260.5.A pattern. Skips when MinIO is
    unavailable (consistent with the existing skip pattern).
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
            name=f"E2E-FA T {uid}",
            slug=f"e2e-fa-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"e2e-fa-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @pytest.mark.integration
    def test_api_201_active_file(self):
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        body = b"id,amount\n1,10\n2,20\n"
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

        response = self.client.post(
            "/api/v1/datasets/",
            data={"file_id": str(f.id)},
            format="json",
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            f"ACTIVE file failed dataset creation: body={response.data!r}",
        )
        # Row landed.
        self.assertEqual(
            Dataset.objects.filter(tenant=self.tenant, file=f).count(),
            1,
        )
