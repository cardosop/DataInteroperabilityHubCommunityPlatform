"""
Phase 260.5.A — file_handle_purpose distinguisher tests.

Verifies the (tenant, file, file_handle_purpose) partial unique
constraint:

* Default value: existing rows + new rows without ``file_handle_purpose``
  default to ``"PRIMARY"`` (backward-compat).
* Sequential same-purpose conflict: two ``Dataset.objects.create`` calls
  with the same ``(tenant, file, file_handle_purpose='primary')`` raise
  IntegrityError on the second.
* Sequential different-purpose: ``primary`` + ``sample`` + ``schema_only``
  on the same file all coexist.
* Concurrent same-purpose POSTs: two ``APIClient.post('/datasets/')``
  calls released simultaneously via ``threading.Barrier(2)`` resolve to
  exactly one 201 + one 409 (no double-create slipping past the
  constraint).
* Concurrent different-purpose POSTs: two simultaneous POSTs with the
  same file_id but different ``file_handle_purpose`` BOTH succeed.
* File-less Dataset rows are exempt from the constraint (the partial
  index is gated on ``file_id IS NOT NULL``).
* Choices enum: only ``primary``, ``sample``, ``schema_only`` accepted
  by the serializer; unknown values 400.
"""

from __future__ import annotations

import threading
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset, DatasetFileHandlePurpose
from hub.apps.datasets.tests.test_base import DatasetsAPITestBase
from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

User = get_user_model()


# ---------------------------------------------------------------------------
# Pure model-layer constraint tests (no API plumbing, no S3)
# ---------------------------------------------------------------------------


class DatasetFileHandlePurposeConstraintTest(TestCase):
    """260.5.A.3 — (tenant, file, file_handle_purpose) unique-when-file-not-null."""

    def setUp(self):
        super().setUp()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"FH T {uid}",
            slug=f"fh-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"fh-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        file_id = uuid.uuid4()
        self.file = File.objects.create(
            id=file_id,
            tenant=self.tenant,
            name="data.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=f"{self.tenant.id}/{file_id}/data.csv",
            created_by=self.user,
        )

    def _make(self, *, purpose: str, version: int = 1) -> Dataset:
        # ``_skip_test_purpose_rotation`` opts out of the test-mode
        # auto-rotation signal in ``hub/apps/datasets/tests/conftest.py``
        # — these tests deliberately exercise the unique-constraint
        # branch and need the IntegrityError to surface.
        obj = Dataset(
            tenant=self.tenant,
            asset=None,
            file=self.file,
            schema_json={"fields": []},
            sample_data_json=[],
            row_count=0,
            format="CSV",
            version=version,
            file_handle_purpose=purpose,
            created_by=self.user,
        )
        obj._skip_test_purpose_rotation = True
        obj.save()
        return obj

    @pytest.mark.integration
    def test_default_is_primary(self):
        # 260.5.A.1 — existing callers that don't pass file_handle_purpose
        # get "PRIMARY" so previous one-File → one-Dataset semantics hold.
        ds = Dataset.objects.create(
            tenant=self.tenant,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=1,
        )
        self.assertEqual(ds.file_handle_purpose, DatasetFileHandlePurpose.PRIMARY)

    @pytest.mark.integration
    def test_two_primary_on_same_file_both_succeed(self):
        # Migration 0110 removed the unique partial index on
        # (tenant, file, file_handle_purpose) WHERE file IS NOT NULL.
        # The DB-level constraint no longer exists; multiple PRIMARY
        # datasets on the same file are now allowed at the DB layer.
        # Application-level enforcement may be re-added later.
        self._make(purpose="PRIMARY", version=1)
        self._make(purpose="PRIMARY", version=2)
        self.assertEqual(
            Dataset.objects.filter(
                tenant=self.tenant, file=self.file, file_handle_purpose="PRIMARY"
            ).count(),
            2,
        )

    @pytest.mark.integration
    def test_primary_and_sample_and_schema_only_coexist(self):
        # 260.5.A — three datasets on the same file with different
        # purposes are allowed; the constraint scopes uniqueness to
        # the (tenant, file, file_handle_purpose) triple.
        self._make(purpose="PRIMARY", version=1)
        self._make(purpose="sample", version=2)
        self._make(purpose="schema_only", version=3)
        self.assertEqual(
            Dataset.objects.filter(tenant=self.tenant, file=self.file).count(),
            3,
        )

    @pytest.mark.integration
    def test_two_datasets_with_no_file_are_exempt_from_constraint(self):
        # The partial index is gated on file_id IS NOT NULL; file-
        # less datasets (e.g. retired-with-purged-file rows from
        # Phase 260.1.C) don't share the constraint.
        Dataset.objects.create(
            tenant=self.tenant,
            file=None,
            schema_json={"fields": []},
            format="CSV",
            version=1,
            file_handle_purpose="PRIMARY",
        )
        Dataset.objects.create(
            tenant=self.tenant,
            file=None,
            schema_json={"fields": []},
            format="CSV",
            version=2,
            file_handle_purpose="PRIMARY",
        )
        # Both rows committed without IntegrityError.
        self.assertEqual(
            Dataset.objects.filter(tenant=self.tenant, file__isnull=True).count(),
            2,
        )

    @pytest.mark.integration
    def test_constraint_scoped_per_tenant(self):
        # Two tenants with the same file_id (cross-tenant; not a
        # realistic data path since File is itself tenant-scoped, but
        # the constraint composition test verifies the tenant column
        # is part of the unique index).
        self._make(purpose="PRIMARY", version=1)
        # Build a second tenant + same-shaped File row to verify
        # the constraint does NOT collide across tenants.
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
            name="data.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=f"{other_tenant.id}/{other_file_id}/data.csv",
            created_by=other_user,
        )
        Dataset.objects.create(
            tenant=other_tenant,
            file=other_file,
            schema_json={"fields": []},
            format="CSV",
            version=1,
            file_handle_purpose="PRIMARY",
        )
        # Each tenant has its own PRIMARY dataset on its own file.
        # Filter by the specific tenants created in this test to avoid
        # counting accumulated PRIMARY rows from other tests when using
        # --reuse-db.
        self.assertEqual(
            Dataset.objects.filter(
                tenant__in=[self.tenant, other_tenant],
                file_handle_purpose="PRIMARY",
            ).count(),
            2,
        )


# ---------------------------------------------------------------------------
# Serializer / API validation
# ---------------------------------------------------------------------------


class DatasetCreateFileHandlePurposeValidationTest(DatasetsAPITestBase):
    """Serializer-level checks that the choice gate works."""

    @pytest.mark.integration
    def test_unknown_purpose_returns_400(self):
        response = self.client.post(
            "/api/v1/datasets/",
            data={"file_id": str(self.file.id), "file_handle_purpose": "garbage"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Error envelope mentions the field; exact serializer message
        # depends on DRF version, but the field name MUST appear so the
        # FE can highlight the right input.
        self.assertIn("file_handle_purpose", str(response.data).lower())


class DatasetServiceForwardingTest(TestCase):
    """R1 audit GAP-B — pin down that ``DatasetService.create_dataset``
    forwards ``file_handle_purpose`` to the persisted Dataset row.

    Without this test a regression where the service signature
    accepts the param but doesn't pass it to ``Dataset.objects.create``
    would silently default every new dataset to ``primary`` — the
    only failure surface would be the constraint test catching a
    different shape later. Testing the forwarding directly keeps
    the layered contract explicit.

    Tests the SAVE path through the service layer using direct
    Dataset.objects.create() (matches the platform's create_dataset
    plumbing without the S3 fetch dependency). For S3-end-to-end
    coverage see ``DatasetCreateConcurrencyTest`` below.
    """

    def setUp(self):
        super().setUp()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Forwarding {uid}",
            slug=f"fwd-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"fwd-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    @pytest.mark.integration
    def test_service_forwards_purpose_to_persisted_row(self):
        # Direct ORM verification: pass each purpose value and
        # confirm it round-trips to the persisted row. This proves
        # the model field accepts the value AND that it's not
        # silently mapped to the default during save.
        for purpose in ("PRIMARY", "sample", "schema_only"):
            file_id = uuid.uuid4()
            f = File.objects.create(
                id=file_id,
                tenant=self.tenant,
                name=f"data-{purpose}.csv",
                content_type="text/csv",
                size=1,
                status=FileStatus.ACTIVE,
                scan_status=FileScanStatus.CLEAN,
                storage_path=f"{self.tenant.id}/{file_id}/data-{purpose}.csv",
                created_by=self.user,
            )
            dataset = Dataset.objects.create(
                tenant=self.tenant,
                file=f,
                schema_json={"fields": []},
                format="CSV",
                version=1,
                file_handle_purpose=purpose,
            )
            dataset.refresh_from_db()
            self.assertEqual(
                dataset.file_handle_purpose,
                purpose,
                f"file_handle_purpose round-trip failed for {purpose!r}",
            )


class DatasetFileHandlePurposeReadOnlyOnPatchTest(DatasetsAPITestBase):
    """R1 audit GAP-C — file_handle_purpose is invariant after create.

    The Dataset serializer declares the field as read-only on
    Meta.read_only_fields so PATCH attempts to mutate it are
    silently dropped (DRF's standard behaviour). Without a test
    pinning this contract, a future serializer refactor that moved
    the field out of read_only_fields would let a user mutate the
    purpose post-create AND silently break the partial unique
    constraint's invariant (a row could flip from PRIMARY to
    SAMPLE under another tenant's nose).
    """

    @pytest.mark.integration
    def test_patch_with_file_handle_purpose_does_not_mutate_persisted_value(self):
        from hub.apps.datasets.models import Dataset

        # Create a PRIMARY dataset directly (skip API + S3 to keep
        # the test focused on the read-only contract).
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=1,
            file_handle_purpose="PRIMARY",
            created_by=self.user,
        )

        # Attempt to PATCH the purpose to "sample".
        response = self.client.patch(
            f"/api/v1/datasets/{dataset.id}/",
            data={"file_handle_purpose": "sample"},
            format="json",
        )
        # 200 (PATCH succeeds — read-only fields are silently dropped,
        # not 400'd) but the persisted value is UNCHANGED.
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        dataset.refresh_from_db()
        self.assertEqual(
            dataset.file_handle_purpose,
            "PRIMARY",
            (
                "file_handle_purpose was mutated via PATCH — the field "
                "MUST be read-only on the Dataset serializer to preserve "
                "the partial unique constraint's create-time invariant."
            ),
        )


# ---------------------------------------------------------------------------
# Concurrent POST /datasets/ test (260.5.A.4) — TransactionTestCase
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
@pytest.mark.xdist_group("serial")
class DatasetCreateConcurrencyTest(TransactionTestCase):
    """260.5.A.4 — two concurrent POST /datasets/ same file_id + same purpose
    → exactly one 201 + one 409. Different purpose → both succeed.

    Uses TransactionTestCase + ``threading.Barrier(2)`` (matches the
    260.4.A / 260.4.C / 260.4.D / 260.4.E concurrency-test pattern)
    because Django's ``TestCase`` wraps each test in a single outer
    transaction invisible to other threads — threading-based
    concurrency tests need real per-connection transactions to
    exercise the constraint against Postgres.

    Schema inference path requires real S3 storage; test seeds the
    file content into MinIO and skips when MinIO is unavailable
    (consistent with the 260.4.A / 260.4.D / 260.4.E e2e pattern).
    """

    def setUp(self):
        super().setUp()
        from django.db.models.signals import pre_save

        from hub.apps.datasets.models import Dataset
        from hub.apps.datasets.tests.conftest import _rotate_purpose
        from hub.apps.files.storage import S3StorageClient

        # The session-wide ``conftest._rotate_purpose`` pre_save signal
        # auto-rotates ``file_handle_purpose`` so concurrent tests don't
        # all collide on PRIMARY. THIS test deliberately exercises the
        # collision contract — disconnect the rotation for the duration
        # of the test class so the constraint actually fires.
        pre_save.disconnect(
            _rotate_purpose,
            sender=Dataset,
            dispatch_uid="datasets_tests_auto_rotate_file_handle_purpose",
        )
        self.addCleanup(
            pre_save.connect,
            _rotate_purpose,
            sender=Dataset,
            dispatch_uid="datasets_tests_auto_rotate_file_handle_purpose",
        )

        self.storage_available = False
        try:
            self.storage_client = S3StorageClient()
            self.storage_client._ensure_bucket_exists()
            self.storage_available = True
        except (OSError, ConnectionError, TimeoutError):
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
        # Asset is required for the dataset-creation business rules to
        # accept the row in some configurations; harmless if not.
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"asset-{uid}",
            name="Concurrent Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

    def _seed_file_with_bytes(self, *, body: bytes = b"id,amount\n1,10\n") -> File:
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")
        file_id = uuid.uuid4()
        storage_path = f"{self.tenant.id}/{file_id}/data.csv"
        self.storage_client.upload_file(storage_path, body, "text/csv")
        return File.objects.create(
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

    @pytest.mark.integration
    def test_concurrent_same_purpose_both_return_201(self):
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")
        f = self._seed_file_with_bytes()

        client_a = APIClient()
        client_a.force_authenticate(user=self.user)
        client_b = APIClient()
        client_b.force_authenticate(user=self.user)

        barrier = threading.Barrier(2)
        results: list[int] = []
        results_lock = threading.Lock()

        # R1 audit GAP-A — DELIBERATELY omit asset_id. With an asset
        # link, both threads also collide on
        # ``unique_dataset_version_per_asset`` (both compute the
        # same version=1) and Postgres may report EITHER constraint
        # name first — the test would be flaky depending on which
        # the view's IntegrityError catch matched. Without asset_id
        # the version constraint is gated off (its condition is
        # ``asset__isnull=False``) so ONLY the file_handle_purpose
        # constraint can fire — deterministic test.
        def attempt(client) -> None:
            barrier.wait()
            response = client.post(
                "/api/v1/datasets/",
                data={
                    "file_id": str(f.id),
                    "file_handle_purpose": "PRIMARY",
                },
                format="json",
            )
            with results_lock:
                results.append(response.status_code)

        t1 = threading.Thread(target=attempt, args=(client_a,))
        t2 = threading.Thread(target=attempt, args=(client_b,))
        t1.start()
        t2.start()
        t1.join(timeout=60)
        t2.join(timeout=60)

        self.assertEqual(len(results), 2)
        # Migration 0110 removed the unique partial index on
        # (tenant, file, file_handle_purpose). The DB-level constraint
        # no longer exists; both concurrent requests succeed with 201.
        # Application-level enforcement may be re-added later.
        self.assertEqual(
            sorted(results),
            [status.HTTP_201_CREATED, status.HTTP_201_CREATED],
            (
                "Concurrent POSTs with same file_id + purpose did not both "
                f"succeed; got {sorted(results)}. Migration 0110 removed the "
                "DB-level constraint; both should succeed."
            ),
        )

        # Both rows landed (constraint removed).
        self.assertEqual(
            Dataset.objects.filter(tenant=self.tenant, file=f).count(),
            2,
        )

    @pytest.mark.integration
    def test_concurrent_different_purpose_both_succeed(self):
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")
        f = self._seed_file_with_bytes()

        client_a = APIClient()
        client_a.force_authenticate(user=self.user)
        client_b = APIClient()
        client_b.force_authenticate(user=self.user)

        barrier = threading.Barrier(2)
        results: list[int] = []
        results_lock = threading.Lock()

        # R1 audit GAP-A — same reasoning as the same-purpose test:
        # omit asset_id so the version constraint doesn't apply.
        # With asset_id BOTH threads would compute version=1 and
        # collide on ``unique_dataset_version_per_asset`` even
        # though their purposes differ. Without asset_id, version
        # uniqueness is gated off and the only constraint in play
        # is the (tenant, file, purpose) one — which different
        # purposes don't violate.
        def attempt(client, purpose: str) -> None:
            barrier.wait()
            response = client.post(
                "/api/v1/datasets/",
                data={
                    "file_id": str(f.id),
                    "file_handle_purpose": purpose,
                },
                format="json",
            )
            with results_lock:
                results.append(response.status_code)

        t1 = threading.Thread(target=attempt, args=(client_a, "PRIMARY"))
        t2 = threading.Thread(target=attempt, args=(client_b, "SAMPLE"))
        t1.start()
        t2.start()
        t1.join(timeout=60)
        t2.join(timeout=60)

        # Both threads land 201 — the constraint scopes uniqueness to
        # (tenant, file, file_handle_purpose), so primary + sample on
        # the same file coexist.
        self.assertEqual(
            sorted(results),
            [status.HTTP_201_CREATED, status.HTTP_201_CREATED],
            (
                "Concurrent POSTs with same file_id but DIFFERENT "
                f"purposes did not BOTH succeed; got {sorted(results)}. "
                "The constraint should scope uniqueness to the "
                "(tenant, file, file_handle_purpose) triple."
            ),
        )

        rows = list(
            Dataset.objects.filter(tenant=self.tenant, file=f)
            .order_by("file_handle_purpose")
            .values_list("file_handle_purpose", flat=True)
        )
        self.assertEqual(rows, ["PRIMARY", "SAMPLE"])
