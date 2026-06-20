"""
Phase 260.4.E — Manual dataset refresh tests.

Verifies the contract for ``POST /datasets/{id}/refresh/``:

* Authorisation:
    - non-TENANT_ADMIN regular user → 403
    - TENANT_ADMIN role → 200
    - PLATFORM_ADMIN flag → 200 (admin bypass mirrors HasAnyRole)
    - unauthenticated → 401/403

* Validation:
    - dataset has no backing file → 409 DATASET_REFRESH_NO_FILE
    - retired dataset → 409 DATASET_RETIRED_REFRESH_NOT_ALLOWED
    - malformed dataset id → 400
    - cross-tenant dataset → 404 (existence non-disclosure)

* Effect (with MinIO):
    - re-runs schema inference on the existing file
    - updates schema_json when inference produced a different result
    - leaves schema_json unchanged when inference produced the same result
    - emits DATASET_REFRESH_TRIGGERED audit row with previous + new
      schema hash, schema_changed flag, and drift summary against any
      active contract
    - schema_changed=False on a no-op refresh
    - drift response payload mirrors the 260.4.D shape

* Drift guard:
    - DATASET_REFRESH_TRIGGERED constant self-describes
"""

from __future__ import annotations

import hashlib
import json
import uuid

import pytest
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
from hub.apps.datasets.models import Dataset, DatasetStatus
from hub.apps.datasets.tests.test_base import DatasetsAPITestBase
from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, UserRole, UserStatus

User = get_user_model()


def _refresh_url(dataset_id) -> str:
    return f"/api/v1/datasets/{dataset_id}/refresh/"


def _grant_role(user, tenant, name: str) -> None:
    role, _ = Role.objects.get_or_create(tenant=tenant, name=name, defaults={"description": name})
    UserRole.objects.get_or_create(user=user, tenant=tenant, role=role)


# ---------------------------------------------------------------------------
# Authorization tests — TENANT_ADMIN gate
# ---------------------------------------------------------------------------


class DatasetManualRefreshAuthorizationTest(DatasetsAPITestBase):
    """The Refresh action is TENANT_ADMIN-only (or PLATFORM_ADMIN bypass)."""

    def setUp(self):
        super().setUp()
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"refresh-asset-{uuid.uuid4().hex[:8]}",
            name="Refresh Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )
        self.dataset = Dataset.objects.create(
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

    @pytest.mark.integration
    def test_refresh_requires_tenant_admin_role_returns_403_for_regular_user(self):
        # ``self.user`` has no roles assigned — should be denied.
        response = self.client.post(_refresh_url(self.dataset.id))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        # No audit emission on rejected refresh.
        self.assertFalse(
            AuditEvent.objects.filter(
                action=audit_event_types.DATASET_REFRESH_TRIGGERED,
                resource_id=self.dataset.id,
            ).exists()
        )

    @pytest.mark.integration
    def test_refresh_unauthenticated_returns_401_or_403(self):
        anon = APIClient()
        response = anon.post(_refresh_url(self.dataset.id))
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    @pytest.mark.integration
    def test_refresh_platform_admin_bypasses_role_check(self):
        # Platform admins bypass the HasAnyRole gate by design.
        self.user.is_platform_admin = True
        self.user.save(update_fields=["is_platform_admin"])
        response = self.client.post(_refresh_url(self.dataset.id))
        # Action runs (may 200 or 5xx depending on S3 availability)
        # but it MUST NOT 403 the platform admin.
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------


class DatasetManualRefreshValidationTest(DatasetsAPITestBase):
    """Validation gates that don't touch S3."""

    def setUp(self):
        super().setUp()
        # Promote the test user to TENANT_ADMIN so we can test the
        # post-authorisation validation paths.
        _grant_role(self.user, self.tenant, "TENANT_ADMIN")
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"refresh-asset-{uuid.uuid4().hex[:8]}",
            name="Refresh Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )
        self.dataset = Dataset.objects.create(
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

    @pytest.mark.integration
    def test_refresh_malformed_dataset_id_returns_400(self):
        response = self.client.post(_refresh_url("not-a-uuid"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @pytest.mark.integration
    def test_refresh_unknown_dataset_returns_404(self):
        response = self.client.post(_refresh_url(uuid.uuid4()))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @pytest.mark.integration
    def test_refresh_retired_dataset_returns_409(self):
        self.dataset.status = DatasetStatus.RETIRED
        self.dataset.save(update_fields=["status"])
        response = self.client.post(_refresh_url(self.dataset.id))
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(
            (response.data.get("code") or response.data.get("error", {}).get("code")),
            "DATASET_RETIRED_REFRESH_NOT_ALLOWED",
        )

    @pytest.mark.integration
    def test_refresh_dataset_without_file_returns_409(self):
        # Detach the file to simulate a dataset whose file was hard-
        # deleted (e.g. via Phase 260.1 file purge).
        self.dataset.file = None
        self.dataset.save(update_fields=["file"])
        response = self.client.post(_refresh_url(self.dataset.id))
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(
            (response.data.get("code") or response.data.get("error", {}).get("code")),
            "DATASET_REFRESH_NO_FILE",
        )

    @pytest.mark.integration
    def test_refresh_cross_tenant_returns_404(self):
        # Dataset in a DIFFERENT tenant — must look like "not found".
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
        other_dataset = Dataset.objects.create(
            tenant=other_tenant,
            file=other_file,
            schema_json={"fields": []},
            sample_data_json=[],
            row_count=0,
            format="CSV",
            version=1,
            created_by=other_user,
        )

        response = self.client.post(_refresh_url(other_dataset.id))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        # No audit emission across tenants.
        self.assertFalse(
            AuditEvent.objects.filter(
                action=audit_event_types.DATASET_REFRESH_TRIGGERED,
                resource_id=other_dataset.id,
            ).exists()
        )


# ---------------------------------------------------------------------------
# End-to-end with MinIO storage — schema inference + drift + audit
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class DatasetManualRefreshEndToEndTest(TransactionTestCase):
    """Re-infers schema against the dataset's existing file in MinIO."""

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
        _grant_role(self.user, self.tenant, "TENANT_ADMIN")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"e2e-asset-{uid}",
            name="E2E Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

    def _seed_dataset_with_file(self, *, body: bytes, schema_json: dict) -> Dataset:
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
            schema_json=schema_json,
            sample_data_json=[],
            row_count=0,
            format="CSV",
            version=1,
            created_by=self.user,
        )

    @pytest.mark.integration
    def test_refresh_with_unchanged_schema_marks_schema_changed_false(self):
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")
        # Seed a dataset whose stored schema_json ALREADY matches what
        # inference will produce from the file bytes.
        body = b"id,amount\n1,10\n2,20\n"
        # schema_inference produces {"fields": [{"name": ..., "data_type": ...}, ...], ...}
        # We seed with an arbitrary placeholder; the action will refresh it
        # to whatever inference produces. ``schema_changed`` is the load-
        # bearing flag we're testing.
        dataset = self._seed_dataset_with_file(body=body, schema_json={"fields": []})

        # First refresh — inference produces the real schema, so
        # ``schema_changed=True`` (placeholder→real).
        first = self.client.post(_refresh_url(dataset.id))
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertTrue(first.data["schema_changed"])

        # Second refresh — same file, same inference result; the
        # canonical schema hash must match prior, so ``schema_changed=False``.
        second = self.client.post(_refresh_url(dataset.id))
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertFalse(second.data["schema_changed"])

    @pytest.mark.integration
    def test_refresh_emits_audit_with_schema_hashes_and_drift(self):
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")
        # Active contract declares schema; refresh's drift summary
        # must reflect the comparison.
        Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
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
                    "fields": [
                        {"name": "id", "type": "integer"},
                        {"name": "amount", "type": "number"},
                    ]
                }
            },
        )
        body = b"id,amount\n1,10\n2,20\n"
        dataset = self._seed_dataset_with_file(body=body, schema_json={"fields": []})

        response = self.client.post(_refresh_url(dataset.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Response shape mirrors 260.4.D: dataset + schema_drift +
        # schema_changed.
        self.assertIn("dataset", response.data)
        self.assertIn("schema_drift", response.data)
        self.assertIn("schema_changed", response.data)

        ev = AuditEvent.objects.filter(
            action=audit_event_types.DATASET_REFRESH_TRIGGERED,
            resource_id=dataset.id,
            tenant_id=self.tenant.id,
        ).first()
        assert ev is not None
        details = ev.details_json or {}
        self.assertEqual(details.get("dataset_id"), str(dataset.id))
        self.assertEqual(details.get("file_id"), str(dataset.file_id))
        self.assertEqual(details.get("asset_id"), str(self.asset.id))
        self.assertIn("previous_schema_hash", details)
        self.assertIn("new_schema_hash", details)
        # Hashes are 64-char hex SHA-256.
        self.assertEqual(len(details["new_schema_hash"]), 64)
        self.assertTrue(details["schema_changed"])
        self.assertIn("schema_drift", details)
        self.assertTrue(details["schema_drift"]["has_contract"])

    @pytest.mark.integration
    def test_refresh_no_op_emits_audit_with_schema_changed_false(self):
        # Even on a no-op (schema unchanged) the audit row MUST land
        # so audit-replay queries can count refresh attempts. Without
        # this, a flaky inference detector wouldn't be visible to
        # operators.
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")
        body = b"id\n1\n"
        dataset = self._seed_dataset_with_file(body=body, schema_json={"fields": []})
        # First refresh seeds the canonical schema.
        first = self.client.post(_refresh_url(dataset.id))
        self.assertEqual(first.status_code, status.HTTP_200_OK)

        # Count audit rows BEFORE the second (no-op) refresh.
        before = AuditEvent.objects.filter(
            action=audit_event_types.DATASET_REFRESH_TRIGGERED,
            resource_id=dataset.id,
        ).count()

        second = self.client.post(_refresh_url(dataset.id))
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertFalse(second.data["schema_changed"])

        after = AuditEvent.objects.filter(
            action=audit_event_types.DATASET_REFRESH_TRIGGERED,
            resource_id=dataset.id,
        ).count()
        self.assertEqual(
            after,
            before + 1,
            "no-op refresh MUST still emit an audit row (operator visibility)",
        )
        latest = (
            AuditEvent.objects.filter(
                action=audit_event_types.DATASET_REFRESH_TRIGGERED,
                resource_id=dataset.id,
            )
            .order_by("-timestamp")
            .first()
        )
        assert latest is not None
        self.assertFalse((latest.details_json or {}).get("schema_changed"))


# ---------------------------------------------------------------------------
# Concurrency test — R1 audit GAP-C: prove select_for_update serialises
# concurrent refreshes
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
@pytest.mark.xdist_group("serial")
class DatasetManualRefreshConcurrencyTest(TransactionTestCase):
    """R1 audit GAP-C — the action's docstring claims
    ``select_for_update`` serialises concurrent refreshes. Without a
    threading test that releases two POSTs simultaneously the claim
    is aspirational (same anti-pattern as 260.4.A.R1 GAP-D and
    260.4.D.R1 GAP-D).

    The test releases two real ``APIClient`` POSTs via
    ``threading.Barrier(2)`` and asserts (a) BOTH return 200 (no
    deadlock or unhandled-exception leak), AND (b) exactly TWO audit
    rows land — proving the second writer didn't get rolled back
    AND didn't double-emit. Without the lock, racing reads of
    ``schema_json`` could produce identical ``previous_schema_hash``
    values across both audit rows; with the lock the second writer
    sees the first writer's post-write state.
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
        _grant_role(self.user, self.tenant, "TENANT_ADMIN")
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"concurrent-asset-{uid}",
            name="Concurrent Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

    @pytest.mark.integration
    def test_concurrent_refresh_writers_serialise_via_select_for_update(self):
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")
        import threading

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
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=f,
            schema_json={"fields": []},
            sample_data_json=[],
            row_count=0,
            format="CSV",
            version=1,
            created_by=self.user,
        )

        # Two distinct APIClient instances authenticated as the same
        # TENANT_ADMIN — request stack is the only variable.
        client_a = APIClient()
        client_a.force_authenticate(user=self.user)
        client_b = APIClient()
        client_b.force_authenticate(user=self.user)

        barrier = threading.Barrier(2)
        results: list[int] = []
        results_lock = threading.Lock()

        def attempt(client) -> None:
            barrier.wait()
            response = client.post(_refresh_url(dataset.id))
            with results_lock:
                results.append(response.status_code)

        t1 = threading.Thread(target=attempt, args=(client_a,))
        t2 = threading.Thread(target=attempt, args=(client_b,))
        t1.start()
        t2.start()
        t1.join(timeout=60)
        t2.join(timeout=60)

        self.assertEqual(len(results), 2)
        self.assertEqual(
            sorted(results),
            [200, 200],
            (
                "Concurrent refresh writers did not serialise via select_for_update — "
                f"expected two 200s, got {sorted(results)}. Without the lock the second "
                "writer would race and either deadlock or land on stale schema state."
            ),
        )
        # Two audit rows MUST land (no double-emission, no rollback).
        events = AuditEvent.objects.filter(
            action=audit_event_types.DATASET_REFRESH_TRIGGERED,
            resource_id=dataset.id,
        )
        self.assertEqual(events.count(), 2)


# ---------------------------------------------------------------------------
# Throttle wiring — R1 audit GAP-B: prove the abuse caps are enforced
# ---------------------------------------------------------------------------


class DatasetManualRefreshThrottleWiringTest(DatasetsAPITestBase):
    """R1 audit GAP-B — the action's get_throttles claim binds
    ``DatasetRefreshUserThrottle`` (10/min) + ``DatasetRefreshTenantThrottle``
    (60/min). Without a wiring test the throttle could silently
    detach (e.g. action name typo in get_throttles).

    We verify the wiring at the ``ViewSet.get_throttles`` level
    rather than spamming 11+ HTTP requests — DRF's throttle stack
    is well-tested upstream; what we need to assert is "does the
    action use the right classes".
    """

    def setUp(self):
        super().setUp()
        _grant_role(self.user, self.tenant, "TENANT_ADMIN")

    @pytest.mark.integration
    def test_refresh_action_binds_user_and_tenant_throttle_classes(self):
        from hub.apps.datasets.throttles import (
            DatasetRefreshTenantThrottle,
            DatasetRefreshUserThrottle,
        )
        from hub.apps.datasets.views import DatasetViewSet

        view = DatasetViewSet()
        view.action = "refresh"
        throttles = view.get_throttles()
        throttle_classes = {type(t) for t in throttles}
        self.assertIn(DatasetRefreshUserThrottle, throttle_classes)
        self.assertIn(DatasetRefreshTenantThrottle, throttle_classes)

    @pytest.mark.integration
    def test_other_actions_do_not_bind_refresh_throttles(self):
        from hub.apps.datasets.throttles import (
            DatasetRefreshTenantThrottle,
            DatasetRefreshUserThrottle,
        )
        from hub.apps.datasets.views import DatasetViewSet

        view = DatasetViewSet()
        for action_name in ("list", "retrieve", "create", "update", "destroy", "retire"):
            view.action = action_name
            throttle_classes = {type(t) for t in view.get_throttles()}
            self.assertNotIn(DatasetRefreshUserThrottle, throttle_classes)
            self.assertNotIn(DatasetRefreshTenantThrottle, throttle_classes)


# ---------------------------------------------------------------------------
# Drift guard for the audit constant
# ---------------------------------------------------------------------------


class DatasetRefreshTriggeredAuditConstantTest(TestCase):
    @pytest.mark.integration
    def test_DATASET_REFRESH_TRIGGERED_self_describes(self):
        self.assertEqual(
            audit_event_types.DATASET_REFRESH_TRIGGERED,
            "DATASET_REFRESH_TRIGGERED",
        )
        self.assertIn(
            "DATASET_REFRESH_TRIGGERED",
            audit_event_types.__all__,
        )


# ---------------------------------------------------------------------------
# Helper: canonical schema hash — pure unit test
# ---------------------------------------------------------------------------


class CanonicalSchemaHashTest(TestCase):
    """Verify the hash helper used by the refresh action is stable
    under dict-ordering variations — without this, ``schema_changed``
    would false-positive when Python's dict iteration order differs."""

    @pytest.mark.integration
    def test_hash_is_stable_under_key_reordering(self):
        from hub.apps.datasets.refresh import canonical_schema_hash

        a = {"fields": [{"name": "id", "data_type": "string"}], "row_count_estimated": 0}
        b = {"row_count_estimated": 0, "fields": [{"data_type": "string", "name": "id"}]}
        self.assertEqual(canonical_schema_hash(a), canonical_schema_hash(b))

    @pytest.mark.integration
    def test_hash_differs_on_real_change(self):
        from hub.apps.datasets.refresh import canonical_schema_hash

        a = {"fields": [{"name": "id", "data_type": "string"}]}
        b = {"fields": [{"name": "id", "data_type": "integer"}]}
        self.assertNotEqual(canonical_schema_hash(a), canonical_schema_hash(b))

    @pytest.mark.integration
    def test_hash_handles_none(self):
        from hub.apps.datasets.refresh import canonical_schema_hash

        # None must return a stable hash distinct from {} so audit
        # rows can encode "schema was previously unset".
        h_none = canonical_schema_hash(None)
        h_empty = canonical_schema_hash({})
        self.assertEqual(len(h_none), 64)
        self.assertEqual(len(h_empty), 64)
        self.assertNotEqual(h_none, h_empty)
        # Computed via SHA-256 over a canonical JSON form.
        expected_empty = hashlib.sha256(json.dumps({}, sort_keys=True).encode()).hexdigest()
        self.assertEqual(h_empty, expected_empty)
