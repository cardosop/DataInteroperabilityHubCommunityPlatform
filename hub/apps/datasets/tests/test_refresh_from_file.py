"""
Phase 260.4.D — Refresh-from-new-file workflow tests.

Verifies the contract for ``POST /datasets/{id}/refresh-from-file/``:

* Validation gates (no S3 needed):
    - source dataset must have an asset (400 DATASET_REFRESH_REQUIRES_ASSET)
    - retired source returns 409 DATASET_RETIRED_REFRESH_NOT_ALLOWED
    - unknown / cross-tenant file → 404 FILE_NOT_FOUND
    - file scan not CLEAN → 400 FILE_SCAN_NOT_CLEAN
    - file status not ACTIVE/COMPLETED → 400 FILE_NOT_READY
    - same file_id as source's current file → 400 DATASET_REFRESH_SAME_FILE
    - missing file_id → 400 (serializer)
    - malformed dataset id → 400

* Drift helper (pure, no S3):
    - no asset → has_contract=False, severity=NONE
    - no active contract → has_contract=False, severity=NONE
    - matching schema → has_contract=True, severity=NONE, detected=False
    - missing field → severity=FAIL, structural_incompatibility=True
    - extra field only → severity=WARN

* End-to-end with MinIO storage (skipped when S3 unavailable):
    - happy path 200 with new dataset version + drift
    - audit row ``DATASET_REFRESHED_FROM_FILE`` lands with parent + new IDs + drift
    - new dataset has parent_version FK pointing at the source
    - new version counter == source.version + 1
    - same asset FK preserved; new file FK is the uploaded one

* Drift guard:
    - audit constant self-describes
"""
from __future__ import annotations
import pytest

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.audit import event_types as audit_event_types
from hub.apps.audit.models import AuditEvent
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
)
from hub.apps.datasets.contract_drift import compute_dataset_contract_drift
from hub.apps.datasets.models import Dataset, DatasetStatus
from hub.apps.datasets.tests.test_base import DatasetsAPITestBase
from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

User = get_user_model()


def _refresh_url(dataset_id) -> str:
    return f"/api/v1/datasets/{dataset_id}/refresh-from-file/"


def _make_active_contract(tenant, asset, *, fields):
    """Helper — seed a Contract row with the given schema fields under
    ``hub_contract_json``."""
    return Contract.objects.create(
        tenant=tenant,
        asset=asset,
        version=1,
        status=ContractStatus.ACTIVE,
        original_spec_type=OriginalSpecType.ODCS,
        original_spec_version="3.0.2",
        original_format=OriginalFormat.JSON,
        original_raw="{}",
        hub_contract_version="1.0.0",
        normalization_status=NormalizationStatus.NORMALIZED_OK,
        hub_contract_json={
            "schema": {
                "fields": fields,
            }
        },
    )


# ---------------------------------------------------------------------------
# Validation tests — no S3 needed
# ---------------------------------------------------------------------------


class DatasetRefreshFromFileValidationTest(DatasetsAPITestBase):
    """Validation gates that don't touch S3."""

    def setUp(self):
        super().setUp()
        # Create an asset + a "source" dataset with an existing file.
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"refresh-asset-{uuid.uuid4().hex[:8]}",
            name="Refresh Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )
        self.source_dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "id", "data_type": "string"}]},
            sample_data_json=[],
            row_count=0,
            format="CSV",
            version=1,
            created_by=self.user,
        )
        # A fresh, valid "new" file in the same tenant.
        new_file_id = uuid.uuid4()
        self.new_file = File.objects.create(
            id=new_file_id,
            tenant=self.tenant,
            name="refresh.csv",
            content_type="text/csv",
            size=42,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=f"{self.tenant.id}/{new_file_id}/refresh.csv",
            created_by=self.user,
        )

    @pytest.mark.integration
    def test_refresh_missing_file_id_returns_400(self):
        response = self.client.post(
            _refresh_url(self.source_dataset.id),
            data={},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @pytest.mark.integration
    def test_refresh_malformed_dataset_id_returns_400(self):
        response = self.client.post(
            _refresh_url("not-a-uuid"),
            data={"file_id": str(self.new_file.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @pytest.mark.integration
    def test_refresh_unknown_dataset_returns_404(self):
        response = self.client.post(
            _refresh_url(uuid.uuid4()),
            data={"file_id": str(self.new_file.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @pytest.mark.integration
    def test_refresh_source_without_asset_returns_400(self):
        # Create a dataset without an asset link.
        no_asset_dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=None,
            file=self.file,
            schema_json={"fields": [{"name": "x", "data_type": "string"}]},
            sample_data_json=[],
            row_count=0,
            format="CSV",
            version=1,
            created_by=self.user,
        )
        response = self.client.post(
            _refresh_url(no_asset_dataset.id),
            data={"file_id": str(self.new_file.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        body = response.data
        # ``api_error_response`` emits the flat envelope; the legacy
        # nested ``{"error": {"code": ...}}`` shape only survives on
        # middleware short-circuits. Accept either.
        nested_error = body.get("error") if isinstance(body, dict) else None
        code = (
            nested_error.get("code") if isinstance(nested_error, dict)
            else body.get("code") if isinstance(body, dict) else None
        )
        self.assertEqual(code, "DATASET_REFRESH_REQUIRES_ASSET")
        # No audit row from a rejected refresh.
        self.assertFalse(
            AuditEvent.objects.filter(
                action=audit_event_types.DATASET_REFRESHED_FROM_FILE,
                resource_id=no_asset_dataset.id,
            ).exists()
        )

    @pytest.mark.integration
    def test_refresh_retired_source_returns_409(self):
        self.source_dataset.status = DatasetStatus.RETIRED
        self.source_dataset.save(update_fields=["status"])
        response = self.client.post(
            _refresh_url(self.source_dataset.id),
            data={"file_id": str(self.new_file.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(
            response.data.get("code"),
            "DATASET_RETIRED_REFRESH_NOT_ALLOWED",
        )

    @pytest.mark.integration
    def test_refresh_unknown_file_id_returns_404(self):
        response = self.client.post(
            _refresh_url(self.source_dataset.id),
            data={"file_id": str(uuid.uuid4())},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data.get("code"), "FILE_NOT_FOUND")

    @pytest.mark.integration
    def test_refresh_cross_tenant_file_returns_404(self):
        # File owned by a DIFFERENT tenant — must look like "not found"
        # to the requesting user (existence non-disclosure).
        other_tenant = Tenant.objects.create(
            name=f"Other {uuid.uuid4().hex[:8]}",
            slug=f"other-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(other_tenant)
        other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE,
        )
        other_file_id = uuid.uuid4()
        other_file = File.objects.create(
            id=other_file_id,
            tenant=other_tenant,
            name="other.csv",
            content_type="text/csv",
            size=10,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=f"{other_tenant.id}/{other_file_id}/other.csv",
            created_by=other_user,
        )
        response = self.client.post(
            _refresh_url(self.source_dataset.id),
            data={"file_id": str(other_file.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data.get("code"), "FILE_NOT_FOUND")

    @pytest.mark.integration
    def test_refresh_file_with_pending_scan_returns_400(self):
        self.new_file.scan_status = FileScanStatus.PENDING_SCAN
        self.new_file.save(update_fields=["scan_status"])
        response = self.client.post(
            _refresh_url(self.source_dataset.id),
            data={"file_id": str(self.new_file.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data.get("code"), "FILE_SCAN_NOT_CLEAN")

    @pytest.mark.integration
    def test_refresh_file_with_infected_scan_returns_400(self):
        self.new_file.scan_status = FileScanStatus.INFECTED
        self.new_file.save(update_fields=["scan_status"])
        response = self.client.post(
            _refresh_url(self.source_dataset.id),
            data={"file_id": str(self.new_file.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data.get("code"), "FILE_SCAN_NOT_CLEAN")

    @pytest.mark.integration
    def test_refresh_file_status_pending_returns_400(self):
        self.new_file.status = FileStatus.PENDING
        self.new_file.save(update_fields=["status"])
        response = self.client.post(
            _refresh_url(self.source_dataset.id),
            data={"file_id": str(self.new_file.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data.get("code"), "FILE_NOT_READY")

    @pytest.mark.integration
    def test_refresh_with_same_file_id_returns_400(self):
        # Refusing to refresh with the same file is a guard against
        # accidental no-op version creation.
        response = self.client.post(
            _refresh_url(self.source_dataset.id),
            data={"file_id": str(self.source_dataset.file.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data.get("code"), "DATASET_REFRESH_SAME_FILE")


# ---------------------------------------------------------------------------
# Drift helper — pure function, no S3
# ---------------------------------------------------------------------------


class ComputeDatasetContractDriftTest(TestCase):
    """Pure unit tests for :func:`compute_dataset_contract_drift`.

    Exercises the four meaningful drift outcomes against real DB
    rows: no asset, no contract, matching schema, missing field,
    extra field. No mocks — Contract / Asset / Dataset rows are
    real ORM objects.
    """

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Drift T {uid}",
            slug=f"drift-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"drift-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"drift-asset-{uid}",
            name="Drift Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

    def _make_dataset(self, *, asset, fields):
        return Dataset.objects.create(
            tenant=self.tenant,
            asset=asset,
            file=None,
            schema_json={"fields": fields},
            sample_data_json=[],
            row_count=0,
            format="CSV",
            version=1,
            created_by=self.user,
        )

    @pytest.mark.integration
    def test_drift_no_asset_returns_no_contract(self):
        dataset = self._make_dataset(asset=None, fields=[{"name": "x", "data_type": "string"}])
        drift = compute_dataset_contract_drift(dataset)
        self.assertFalse(drift["has_contract"])
        self.assertEqual(drift["severity"], "NONE")
        self.assertFalse(drift["detected"])

    @pytest.mark.integration
    def test_drift_no_active_contract_returns_no_contract(self):
        dataset = self._make_dataset(
            asset=self.asset, fields=[{"name": "x", "data_type": "string"}]
        )
        drift = compute_dataset_contract_drift(dataset)
        self.assertFalse(drift["has_contract"])
        self.assertEqual(drift["severity"], "NONE")

    @pytest.mark.integration
    def test_drift_matching_schema_returns_NONE(self):
        _make_active_contract(
            self.tenant,
            self.asset,
            fields=[{"name": "id", "type": "string"}, {"name": "amount", "type": "number"}],
        )
        dataset = self._make_dataset(
            asset=self.asset,
            fields=[
                {"name": "id", "data_type": "string"},
                {"name": "amount", "data_type": "number"},
            ],
        )
        drift = compute_dataset_contract_drift(dataset)
        self.assertTrue(drift["has_contract"])
        self.assertFalse(drift["detected"])
        self.assertEqual(drift["severity"], "NONE")

    @pytest.mark.integration
    def test_drift_missing_field_returns_FAIL(self):
        _make_active_contract(
            self.tenant,
            self.asset,
            fields=[
                {"name": "id", "type": "string"},
                {"name": "required_field", "type": "string"},
            ],
        )
        dataset = self._make_dataset(
            asset=self.asset,
            fields=[{"name": "id", "data_type": "string"}],
        )
        drift = compute_dataset_contract_drift(dataset)
        self.assertTrue(drift["has_contract"])
        self.assertTrue(drift["detected"])
        self.assertEqual(drift["severity"], "FAIL")
        self.assertIn("required_field", drift["missing_fields"])
        self.assertTrue(drift["structural_incompatibility"])

    @pytest.mark.integration
    def test_drift_extra_field_only_returns_WARN(self):
        _make_active_contract(
            self.tenant,
            self.asset,
            fields=[{"name": "id", "type": "string"}],
        )
        dataset = self._make_dataset(
            asset=self.asset,
            fields=[
                {"name": "id", "data_type": "string"},
                {"name": "bonus", "data_type": "string"},
            ],
        )
        drift = compute_dataset_contract_drift(dataset)
        self.assertTrue(drift["has_contract"])
        self.assertTrue(drift["detected"])
        self.assertEqual(drift["severity"], "WARN")
        self.assertIn("bonus", drift["extra_fields"])
        self.assertFalse(drift["structural_incompatibility"])

    @pytest.mark.integration
    def test_drift_only_active_contract_used(self):
        # A DRAFT contract must NOT be picked up (drift against
        # drafts is noise, not an audit-worthy signal).
        Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            version=2,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw="{}",
            hub_contract_version="1.0.0",
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_json={
                "schema": {"fields": [{"name": "draft_only", "type": "string"}]}
            },
        )
        dataset = self._make_dataset(
            asset=self.asset,
            fields=[{"name": "id", "data_type": "string"}],
        )
        drift = compute_dataset_contract_drift(dataset)
        self.assertFalse(drift["has_contract"])


# ---------------------------------------------------------------------------
# End-to-end with MinIO storage (skipped when S3 unavailable)
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class DatasetRefreshFromFileEndToEndTest(TransactionTestCase):
    """E2E: uploads real bytes to MinIO, calls the refresh endpoint,
    asserts the new dataset row + audit + drift surface.

    Skips when MinIO is not reachable (consistent with the established
    pattern in :mod:`test_chunked_upload`).
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
            name=f"E2E T {uid}",
            slug=f"e2e-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"e2e-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"e2e-asset-{uid}",
            name="E2E Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        # Source file + dataset (file content is irrelevant for the
        # source — only its tenant/active/clean status matters since
        # the action does NOT re-infer the source's schema).
        source_file_id = uuid.uuid4()
        self.source_file = File.objects.create(
            id=source_file_id,
            tenant=self.tenant,
            name="source.csv",
            content_type="text/csv",
            size=12,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=f"{self.tenant.id}/{source_file_id}/source.csv",
            created_by=self.user,
        )
        self.source_dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.source_file,
            schema_json={"fields": [{"name": "id", "data_type": "string"}]},
            sample_data_json=[],
            row_count=0,
            format="CSV",
            version=1,
            created_by=self.user,
        )

    def _create_new_file_with_bytes(self, *, name: str, body: bytes, content_type: str):
        """Upload real bytes to MinIO + register a File row."""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")
        new_file_id = uuid.uuid4()
        storage_path = f"{self.tenant.id}/{new_file_id}/{name}"
        self.storage_client.upload_file(storage_path, body, content_type)
        return File.objects.create(
            id=new_file_id,
            tenant=self.tenant,
            name=name,
            content_type=content_type,
            size=len(body),
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=storage_path,
            created_by=self.user,
        )

    @pytest.mark.integration
    def test_refresh_creates_new_version_with_parent_link_and_emits_audit(self):
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")
        # New CSV with the SAME field set → no drift.
        new_file = self._create_new_file_with_bytes(
            name="refresh.csv",
            body=b"id\n1\n2\n3\n",
            content_type="text/csv",
        )

        response = self.client.post(
            _refresh_url(self.source_dataset.id),
            data={"file_id": str(new_file.id)},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.data
        self.assertIn("dataset", body)
        self.assertIn("schema_drift", body)

        new_dataset_id = body["dataset"]["id"]
        new_dataset = Dataset.objects.get(id=new_dataset_id)
        # Same asset FK, new file FK, parent_version → source.
        self.assertEqual(new_dataset.asset_id, self.source_dataset.asset_id)
        self.assertEqual(new_dataset.file_id, new_file.id)
        self.assertEqual(new_dataset.parent_version_id, self.source_dataset.id)
        self.assertEqual(new_dataset.version, self.source_dataset.version + 1)

        # Audit row landed.
        events = AuditEvent.objects.filter(
            tenant_id=self.tenant.id,
            resource_type="DATASET",
            resource_id=new_dataset.id,
            action=audit_event_types.DATASET_REFRESHED_FROM_FILE,
        )
        self.assertEqual(events.count(), 1)
        ev = events.first()
        assert ev is not None
        details = ev.details_json or {}
        self.assertEqual(details.get("parent_dataset_id"), str(self.source_dataset.id))
        self.assertEqual(details.get("new_dataset_id"), str(new_dataset.id))
        self.assertEqual(details.get("new_file_id"), str(new_file.id))
        self.assertEqual(details.get("parent_file_id"), str(self.source_file.id))
        self.assertEqual(details.get("new_version"), self.source_dataset.version + 1)
        self.assertEqual(details.get("asset_id"), str(self.source_dataset.asset_id))
        self.assertIn("schema_drift", details)
        # No active contract on the asset → has_contract=False.
        self.assertFalse(details["schema_drift"]["has_contract"])

    @pytest.mark.integration
    def test_refresh_with_drift_surfaces_severity_in_response_and_audit(self):
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")
        # Active contract declares both ``id`` and ``amount`` fields.
        _make_active_contract(
            self.tenant,
            self.asset,
            fields=[
                {"name": "id", "type": "string"},
                {"name": "amount", "type": "number"},
            ],
        )
        # New CSV is missing ``amount`` AND has an extra ``unexpected``
        # field — produces FAIL severity (missing required field).
        new_file = self._create_new_file_with_bytes(
            name="drifted.csv",
            body=b"id,unexpected\n1,foo\n2,bar\n",
            content_type="text/csv",
        )
        response = self.client.post(
            _refresh_url(self.source_dataset.id),
            data={"file_id": str(new_file.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        drift = response.data["schema_drift"]
        self.assertTrue(drift["has_contract"])
        self.assertTrue(drift["detected"])
        self.assertEqual(drift["severity"], "FAIL")
        self.assertIn("amount", drift["missing_fields"])
        self.assertIn("unexpected", drift["extra_fields"])
        self.assertTrue(drift["structural_incompatibility"])

        # Audit row's schema_drift summary mirrors the response.
        ev = AuditEvent.objects.filter(
            action=audit_event_types.DATASET_REFRESHED_FROM_FILE,
            resource_id=response.data["dataset"]["id"],
        ).first()
        assert ev is not None
        audit_drift = (ev.details_json or {}).get("schema_drift") or {}
        self.assertEqual(audit_drift.get("severity"), "FAIL")
        self.assertIn("amount", audit_drift.get("missing_fields", []))


# ---------------------------------------------------------------------------
# Concurrent-refresh lock test — R1 audit GAP-C
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class DatasetRefreshFromFileConcurrencyTest(TransactionTestCase):
    """R1 audit GAP-C — two concurrent refresh-from-file requests on
    the same source dataset MUST serialise via ``select_for_update``,
    not race to a unique-constraint violation.

    Without the lock added in R1: both threads read ``latest_dataset``
    inside ``DatasetService.create_dataset`` and compute the same
    ``version+1``. The second ``Dataset.objects.create()`` violates
    ``unique_dataset_version_per_asset`` → IntegrityError → unhandled
    500. With the lock: the second writer waits for the first to
    commit, re-reads the now-incremented latest version, and produces
    ``version+2``. Both refreshes succeed; chain stays clean.
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
            name=f"Concurrent T {uid}",
            slug=f"concurrent-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"concurrent-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"concurrent-asset-{uid}",
            name="Concurrent Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )
        source_file_id = uuid.uuid4()
        self.source_file = File.objects.create(
            id=source_file_id,
            tenant=self.tenant,
            name="source.csv",
            content_type="text/csv",
            size=12,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=f"{self.tenant.id}/{source_file_id}/source.csv",
            created_by=self.user,
        )
        self.source_dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.source_file,
            schema_json={"fields": [{"name": "id", "data_type": "string"}]},
            sample_data_json=[],
            row_count=0,
            format="CSV",
            version=1,
            created_by=self.user,
        )

    def _create_new_file_with_bytes(self, *, name: str, body: bytes):
        new_file_id = uuid.uuid4()
        storage_path = f"{self.tenant.id}/{new_file_id}/{name}"
        self.storage_client.upload_file(storage_path, body, "text/csv")
        return File.objects.create(
            id=new_file_id,
            tenant=self.tenant,
            name=name,
            content_type="text/csv",
            size=len(body),
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=storage_path,
            created_by=self.user,
        )

    @pytest.mark.integration
    def test_concurrent_refresh_writers_serialize_via_select_for_update(self):
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        import threading

        # Two distinct uploaded files so the action's same-file guard
        # doesn't 400 either thread.
        file_b = self._create_new_file_with_bytes(name="b.csv", body=b"id\n1\n")
        file_c = self._create_new_file_with_bytes(name="c.csv", body=b"id\n2\n")

        client_a = APIClient()
        client_a.force_authenticate(user=self.user)
        client_b = APIClient()
        client_b.force_authenticate(user=self.user)

        barrier = threading.Barrier(2)
        results: list[int] = []
        results_lock = threading.Lock()

        def attempt(client, file_id) -> None:
            barrier.wait()
            response = client.post(
                _refresh_url(self.source_dataset.id),
                data={"file_id": str(file_id)},
                format="json",
            )
            with results_lock:
                results.append(response.status_code)

        t1 = threading.Thread(target=attempt, args=(client_a, file_b.id))
        t2 = threading.Thread(target=attempt, args=(client_b, file_c.id))
        t1.start()
        t2.start()
        t1.join(timeout=60)
        t2.join(timeout=60)

        self.assertEqual(len(results), 2)
        # Both threads MUST land 200; the lock guarantees the second
        # writer re-reads the incremented version and avoids the
        # unique-constraint collision.
        self.assertEqual(
            sorted(results),
            [200, 200],
            (
                "Concurrent refresh-from-file did not serialise via select_for_update — "
                "expected two 200s, got %s. Without the lock the second writer's "
                "Dataset.objects.create() violates unique_dataset_version_per_asset "
                "and the action returns 500."
                % sorted(results)
            ),
        )

        # Three rows total: source (v1), refresh-A (v2), refresh-B (v3).
        # The audit log shows two FILE_REFRESH events with distinct
        # ``new_version`` values forming a clean chain.
        events = list(
            AuditEvent.objects.filter(
                action=audit_event_types.DATASET_REFRESHED_FROM_FILE,
                tenant_id=self.tenant.id,
            ).order_by("timestamp")
        )
        self.assertEqual(len(events), 2)
        new_versions = sorted(
            (ev.details_json or {}).get("new_version") for ev in events
        )
        self.assertEqual(
            new_versions,
            [2, 3],
            (
                "Concurrent refreshes produced overlapping ``new_version`` values "
                "in audit rows; lock is missing or ineffective."
            ),
        )


# ---------------------------------------------------------------------------
# Drift guard for the audit constant
# ---------------------------------------------------------------------------


class DatasetRefreshedFromFileAuditConstantTest(TestCase):
    """The constant must self-describe AND be exported via __all__ so
    audit consumers can import it via ``from hub.apps.audit.event_types
    import DATASET_REFRESHED_FROM_FILE``."""

    @pytest.mark.integration
    def test_DATASET_REFRESHED_FROM_FILE_self_describes(self):
        self.assertEqual(
            audit_event_types.DATASET_REFRESHED_FROM_FILE,
            "DATASET_REFRESHED_FROM_FILE",
        )
        self.assertIn(
            "DATASET_REFRESHED_FROM_FILE",
            audit_event_types.__all__,
        )
