"""W2.7 (oss-release-remediation B2-B7) — plan-limit hardening.

Evidence pins for:

* **B3 PENDING-aware counters (quota-stacking)** — the ``max_storage_gb``
  counter counted ACTIVE files only, so a PENDING/UPLOADING upload did
  NOT reserve quota: two concurrent 1GB uploads both passed a 1GB plan
  (quota stacking).  Post-fix the counter (and the quota meter) count
  PENDING + UPLOADING + ACTIVE; FAILED releases the reservation.
* **B2 check_limit in background ingestion** — the live background paths
  (the orchestration workflow's ``_create_dataset_version_task`` and the
  worker's ``process_file_for_run``) created File + Dataset rows with NO
  plan-limit check (the request path checked; the sibling didn't — the
  P1 pattern).  Post-fix both check ``max_storage_gb`` (delta = content
  size) and ``max_datasets`` BEFORE any File row exists.
* **B4 orphan-S3 cleanup** — when ``complete_upload`` REJECTS an upload
  (size mismatch / hash mismatch / quota reject) the S3 object was left
  orphaned forever.  Post-fix the rejection deletes the S3 object and
  marks the row FAILED (releasing the reserved quota).
* **B5 upload completion fail-closed** — ``complete_upload`` failed OPEN
  on S3 errors (storage check failure → "allow completion (test/dev
  mode)" → row ACTIVE without any object).  Post-fix: S3 errors → 502
  (no ACTIVE transition); a cleanly-missing object → 409 (no completion).
* **B6 counter-error alerting + LIMIT_CHECK_STRICT** —
  ``get_resource_count`` swallowed counter errors into a silent 0
  (fail-open quota).  Post-fix: every counter error emits a
  ``LIMIT_COUNTER_ERROR`` audit; ``LIMIT_CHECK_STRICT`` makes the error
  RAISE (fail closed) instead of reading as free quota.
* **B7 single seeder source** — ``seed_default_plans`` carried an
  inline plan list that DIVERGED from the canonical
  ``tenants/plan_defaults.py`` (seeded FREE: max_assets=10 vs canonical
  3, max_storage_gb=1GB vs canonical unlimited, …) and
  ``billing/test_support`` hardcoded a third plan shape.  Post-fix every
  seeder derives from ``plan_defaults`` / the KNOWN_LIMIT_KEYS catalog.

NO MOCKS at contract boundaries: real Postgres, real ORM, real services,
real S3 (MinIO on the test stack), real workflow tasks — the one
existing S3-stub convention of the sibling parity suite is NOT used
here.  The seeder pins use TransactionTestCase (global plan rows are
wiped and re-seeded for a clean comparison).
"""

from __future__ import annotations

import hashlib
import tempfile
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.audit.models import AuditEvent
from hub.apps.core.limit_registry import RESOURCE_COUNTERS, ResourceCounter, get_resource_count
from hub.apps.core.services.base import ValidationError as ServiceValidationError
from hub.apps.files.models import File, FileStatus
from hub.apps.files.quota import get_tenant_file_storage_quota
from hub.apps.files.services import FileService
from hub.apps.files.storage import S3StorageClient
from hub.apps.files.tests.test_base import FilesTestBase
from hub.apps.scheduled_ingestion.models import (
    ScheduledIngestion,
    ScheduledIngestionRun,
    ScheduledIngestionRunStatus,
)
from hub.apps.scheduled_ingestion.worker_services import process_file_for_run
from hub.apps.tenants.models import KYCStatus, PlanCategory, PlanTier, Tenant, TenantPlan
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()

GB = 1024**3


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _make_plan(*, max_storage_gb=None, max_datasets=None, slug=None) -> TenantPlan:
    """Create a real TenantPlan with explicit limits (None = unlimited key)."""
    limits = {}
    if max_storage_gb is not None:
        limits["max_storage_gb"] = max_storage_gb
    if max_datasets is not None:
        limits["max_datasets"] = max_datasets
    limits.setdefault("max_assets", 1000)
    plan = TenantPlan.objects.create(
        name=f"W27 {slug or _uid()}",
        slug=slug or f"w27-{_uid()}",
        tier=PlanTier.FREE,
        category=PlanCategory.BASE,
        limits_json=limits,
        is_active=True,
    )
    return plan


class W27StoragePins(FilesTestBase):
    """B3 — PENDING-aware storage counters (quota-stacking contract)."""

    def setUp(self):
        super().setUp()
        # The base fixture's 1024-byte ACTIVE file would sit on the 1GB
        # boundary (1GB + 1024B > 1GB) and mask the quota-hole RED.
        self.file.delete()
        # Replace the base subscription's plan with a 1GB-cap plan.
        self.plan = _make_plan(max_storage_gb=1, max_datasets=1000)
        self.tenant.plan = self.plan
        self.tenant.save(update_fields=["plan"])
        self.service = FileService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def _create_pending_file(self, size_bytes: int) -> File:
        return self.service.create_file(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name=f"w27-{_uid()}.csv",
            content_type="text/csv",
            size=size_bytes,
            upload_method="browser",
        )

    def test_second_pending_upload_blocked_by_reserved_quota(self):
        """2x1GB on a 1GB plan: the second PENDING upload is blocked."""
        first = self._create_pending_file(GB)
        self.assertEqual(first.status, FileStatus.PENDING)

        with self.assertRaises(ServiceValidationError) as ctx:
            self._create_pending_file(GB)
        self.assertEqual(ctx.exception.code, "plan_limit_exceeded")

    def test_uploading_file_reserves_quota(self):
        """A UPLOADING (in-flight multipart) file reserves quota too."""
        first = self._create_pending_file(GB)
        File.objects.filter(pk=first.pk).update(status=FileStatus.UPLOADING)

        with self.assertRaises(ServiceValidationError) as ctx:
            self._create_pending_file(GB)
        self.assertEqual(ctx.exception.code, "plan_limit_exceeded")

    def test_failed_file_releases_reserved_quota(self):
        """A FAILED upload releases its reservation — quota is free again."""
        first = self._create_pending_file(GB)
        File.objects.filter(pk=first.pk).update(status=FileStatus.FAILED)

        second = self._create_pending_file(GB)
        self.assertEqual(second.status, FileStatus.PENDING)

    def test_quota_meter_counts_pending_uploads(self):
        """The storage meter mirrors the counter: PENDING bytes count."""
        self._create_pending_file(GB)
        quota = get_tenant_file_storage_quota(str(self.tenant.id))
        self.assertEqual(quota["used_bytes"], GB)


class W27BackgroundIngestionPins(TestCase):
    """B2 — check_limit on the live background ingestion paths."""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name=f"W27 {_uid()}",
            slug=f"w27-{_uid()}",
            status="ACTIVE",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"w27-{_uid()}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.scheduled_ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="W27 Ingestion",
            source_type="S3",
            source_config={"bucket": "w27-bucket"},
            schedule_type="DAILY",
            schedule_config={"time": "00:00"},
            file_pattern=r".*\.csv",
            created_by=self.user,
        )
        self.run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.scheduled_ingestion,
            status=ScheduledIngestionRunStatus.RUNNING,
        )

    def _assign_plan(self, *, max_storage_gb=None, max_datasets=None):
        plan = _make_plan(max_storage_gb=max_storage_gb, max_datasets=max_datasets)
        self.tenant.plan = plan
        self.tenant.save(update_fields=["plan"])

    def _write_temp_csv(self, size_bytes: int) -> tuple[str, bytes]:
        content = b"a" * size_bytes
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            f.write(content)
            return f.name, content

    def test_workflow_file_creation_checks_storage_limit(self):
        """The workflow's dataset-version task checks max_storage_gb first."""
        self._assign_plan(max_storage_gb=0.001, max_datasets=1000)  # ~1MB cap
        temp_path, content = self._write_temp_csv(2 * 1024 * 1024)  # 2MB

        from hub.apps.orchestration.workflows.scheduled_ingestion import (
            ScheduledIngestionWorkflow,
        )

        input_data = {
            "scheduled_ingestion_id": str(self.scheduled_ingestion.id),
            "file_path": "s3://w27-bucket/data/sample.csv",
            "temp_path": temp_path,
            "file_format": "CSV",
            "content_type": "text/csv",
            "file_hash": hashlib.sha256(content).hexdigest(),
        }
        with self.assertRaises(Exception) as ctx:
            ScheduledIngestionWorkflow._create_dataset_version_task(input_data, None, None)
        self.assertEqual(getattr(ctx.exception, "code", None), "plan_limit_exceeded")

        self.assertEqual(
            File.objects.filter(tenant=self.tenant).count(),
            0,
            "The limit check must block BEFORE any File row exists",
        )

    def test_workflow_dataset_creation_checks_max_datasets(self):
        """max_datasets=0 blocks the task before any side effect."""
        self._assign_plan(max_storage_gb=None, max_datasets=0)
        temp_path, content = self._write_temp_csv(1024)

        from hub.apps.orchestration.workflows.scheduled_ingestion import (
            ScheduledIngestionWorkflow,
        )

        input_data = {
            "scheduled_ingestion_id": str(self.scheduled_ingestion.id),
            "file_path": "s3://w27-bucket/data/sample.csv",
            "temp_path": temp_path,
            "file_format": "CSV",
            "content_type": "text/csv",
            "file_hash": hashlib.sha256(content).hexdigest(),
        }
        with self.assertRaises(Exception) as ctx:
            ScheduledIngestionWorkflow._create_dataset_version_task(input_data, None, None)
        self.assertEqual(getattr(ctx.exception, "code", None), "plan_limit_exceeded")
        self.assertEqual(File.objects.filter(tenant=self.tenant).count(), 0)

    def test_worker_process_file_checks_limits(self):
        """The worker's internal path raises plan_limit_exceeded (not silent)."""
        self._assign_plan(max_storage_gb=0.001, max_datasets=1000)
        csv_content = b"id,name\n1,alpha\n" + b"x" * (2 * 1024 * 1024)

        with self.assertRaises(Exception) as ctx:
            process_file_for_run(
                run_id=str(self.run.id),
                file_path="data/sample.csv",
                file_content=csv_content,
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
            )
        self.assertEqual(getattr(ctx.exception, "code", None), "plan_limit_exceeded")
        self.assertEqual(File.objects.filter(tenant=self.tenant).count(), 0)


class W27UploadCompletionPins(FilesTestBase):
    """B4 + B5 — rejections clean S3; storage errors fail closed."""

    def setUp(self):
        super().setUp()
        self.plan = _make_plan(max_storage_gb=10, max_datasets=1000)
        self.tenant.plan = self.plan
        self.tenant.save(update_fields=["plan"])
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.storage_available = False
        try:
            self.storage_client = S3StorageClient()
            self.storage_client._ensure_bucket_exists()
            self.storage_available = True
        except (ConnectionError, TimeoutError, OSError):  # pragma: no cover — S3 probe
            self.storage_available = False

    def _pending_file_with_object(self, content: bytes, *, declared_size=None) -> File:
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")
        file_id = uuid.uuid4()
        file_obj = File.objects.create(
            id=file_id,
            tenant=self.tenant,
            name=f"w27-{_uid()}.csv",
            content_type="text/csv",
            size=declared_size if declared_size is not None else len(content),
            storage_path=f"{self.tenant.id}/{file_id}/data.csv",
            status=FileStatus.PENDING,
            created_by=self.user,
        )
        self.storage_client.save_file(
            tenant_id=str(self.tenant.id),
            file_id=str(file_obj.id),
            file_content=ContentFile(content),
            file_name="data.csv",  # must match storage_path's final segment
        )
        return file_obj

    def test_complete_upload_hash_mismatch_deletes_s3_object(self):
        """Rejected upload (hash mismatch) leaves no orphan S3 object."""
        content = b"w27 hash mismatch content"
        file_obj = self._pending_file_with_object(content)
        wrong_hash = hashlib.sha256(b"different content").hexdigest()

        response = self.client.post(
            f"/api/v1/files/{file_obj.id}/complete/",
            {"content_sha256": wrong_hash},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            self.storage_client.file_exists(file_obj.storage_path),
            "The rejected upload's S3 object must be deleted (no orphan)",
        )
        file_obj.refresh_from_db()
        self.assertEqual(file_obj.status, FileStatus.FAILED)

    def test_complete_upload_size_mismatch_deletes_s3_object(self):
        """Rejected upload (size mismatch) leaves no orphan S3 object."""
        content = b"w27 size mismatch content"
        file_obj = self._pending_file_with_object(content, declared_size=len(content) + 10)

        response = self.client.post(
            f"/api/v1/files/{file_obj.id}/complete/",
            {"content_sha256": hashlib.sha256(content).hexdigest()},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(self.storage_client.file_exists(file_obj.storage_path))
        file_obj.refresh_from_db()
        self.assertEqual(file_obj.status, FileStatus.FAILED)

    def test_complete_upload_storage_error_fails_closed(self):
        """An S3 ERROR during verification → 502, no ACTIVE transition."""
        from unittest.mock import patch

        file_id = uuid.uuid4()
        file_obj = File.objects.create(
            id=file_id,
            tenant=self.tenant,
            name=f"w27-{_uid()}.csv",
            content_type="text/csv",
            size=1024,
            storage_path=f"{self.tenant.id}/{file_id}/data.csv",
            status=FileStatus.PENDING,
            created_by=self.user,
        )

        # Point the view's fresh S3StorageClient at a DEAD endpoint (env
        # config, not behavior stubbing — S3StorageClient reads
        # AWS_S3_ENDPOINT_URL from the environment first) so every call
        # raises a REAL connection error — the pre-fix code swallowed it
        # and completed the upload anyway.
        with patch.dict("os.environ", {"AWS_S3_ENDPOINT_URL": "http://127.0.0.1:9"}, clear=False):
            response = self.client.post(
                f"/api/v1/files/{file_obj.id}/complete/",
                {"content_sha256": "a" * 64},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertIn("STORAGE_VERIFICATION_FAILED", str(response.data))
        file_obj.refresh_from_db()
        self.assertNotEqual(
            file_obj.status,
            FileStatus.ACTIVE,
            "A storage error must never complete the upload (fail closed)",
        )

    def test_complete_upload_missing_object_fails_closed(self):
        """A cleanly-missing object → 409; the upload must not complete."""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")
        file_obj = File.objects.create(
            tenant=self.tenant,
            name=f"w27-{_uid()}.csv",
            content_type="text/csv",
            size=1024,
            storage_path=f"{self.tenant.id}/missing-object/data.csv",
            status=FileStatus.PENDING,
            created_by=self.user,
        )

        response = self.client.post(
            f"/api/v1/files/{file_obj.id}/complete/",
            {"content_sha256": "a" * 64},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("FILE_NOT_IN_STORAGE", str(response.data))
        file_obj.refresh_from_db()
        self.assertNotEqual(file_obj.status, FileStatus.ACTIVE)


class W27CounterErrorPins(TestCase):
    """B6 — counter errors are audited; LIMIT_CHECK_STRICT fails closed."""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name=f"W27 {_uid()}",
            slug=f"w27-{_uid()}",
            status="ACTIVE",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.plan = _make_plan(max_storage_gb=1)
        self.tenant.plan = self.plan
        self.tenant.save(update_fields=["plan"])

    def test_counter_error_emits_audit_event(self):
        """A broken counter logs + audits (never a silent 0)."""
        broken_key = f"max_broken_{_uid()}"
        # exclude_statuses is what actually references status_field — a
        # bogus column makes get_count raise FieldError for real.
        RESOURCE_COUNTERS[broken_key] = ResourceCounter(
            "files.File",
            status_field="no_such_field",
            exclude_statuses=["BOGUS"],
        )
        try:
            result = get_resource_count(str(self.tenant.id), broken_key)
        finally:
            RESOURCE_COUNTERS.pop(broken_key, None)

        self.assertEqual(result, 0)
        self.assertGreaterEqual(
            AuditEvent.objects.filter(
                action="LIMIT_COUNTER_ERROR",
                details_json__limit_key=broken_key,
            ).count(),
            1,
            "Every counter error must emit a LIMIT_COUNTER_ERROR audit",
        )

    @override_settings(LIMIT_CHECK_STRICT=True)
    def test_strict_mode_raises_on_counter_error(self):
        """LIMIT_CHECK_STRICT makes a broken counter fail the check closed."""
        broken_key = f"max_broken_{_uid()}"
        # exclude_statuses is what actually references status_field — a
        # bogus column makes get_count raise FieldError for real.
        RESOURCE_COUNTERS[broken_key] = ResourceCounter(
            "files.File",
            status_field="no_such_field",
            exclude_statuses=["BOGUS"],
        )
        # check_limit short-circuits to unlimited when the plan has no
        # entry for the key — the broken key must BE in the plan for the
        # counter to be reached at all.
        self.plan.limits_json = {**self.plan.limits_json, broken_key: 5}
        self.plan.save(update_fields=["limits_json"])
        try:
            from hub.apps.tenants.services import PlanLimitService

            with self.assertRaises(Exception) as ctx:
                PlanLimitService().check_limit(
                    tenant_id=str(self.tenant.id),
                    limit_key=broken_key,
                    delta=1,
                )
        finally:
            RESOURCE_COUNTERS.pop(broken_key, None)
        self.assertIn("counter", str(ctx.exception).lower())


class W27SeederSourcePins(TransactionTestCase):
    """B7 — every seeder derives from the canonical plan_defaults source.

    TransactionTestCase: plan rows are global; the pin wipes them,
    re-seeds, and compares — committed visibility required.
    """

    def _wipe_plans(self):
        # billing is the paid layer — guarded for both core-only absence
        # forms (W7.1); without it there is nothing to wipe.
        try:
            from hub.apps.billing.models import Subscription
        except (RuntimeError, ModuleNotFoundError):
            Subscription = None  # type: ignore[assignment]

        # Tenant.plan is PROTECT-style — detach references first (shared
        # DB residue tenants from earlier suites would block the delete).
        Tenant.objects.update(plan=None, ml_plan=None)
        if Subscription is not None:
            Subscription.objects.all().delete()
        TenantPlan.objects.all().delete()

    def test_seeded_plans_match_canonical_defaults(self):
        """seed_default_plans seeds EXACTLY the canonical plan_defaults data."""
        from hub.apps.tenants import plan_defaults

        self._wipe_plans()
        call_command("seed_default_plans")

        for canonical in plan_defaults.PLATFORM_PLANS + plan_defaults.ML_PLANS:
            plan = TenantPlan.objects.get(slug=canonical["slug"])
            self.assertEqual(
                plan.limits_json,
                canonical["limits_json"],
                f"Seeded plan {canonical['slug']} diverges from plan_defaults",
            )
            self.assertEqual(plan.tier, canonical["tier"].value)

        # Canonical FREE contract spot-checks (the divergence evidence):
        free = TenantPlan.objects.get(slug="free")
        self.assertEqual(free.get_limit("max_assets"), 3)
        self.assertNotIn(
            "max_storage_gb",
            free.limits_json,
            "Canonical FREE has UNLIMITED storage (no key) — the old seeder "
            "pinned a 1GB cap that plan_defaults never declares",
        )

    def test_test_support_plans_derive_from_canonical_defaults(self):
        """billing.test_support's seeded plans carry canonical plan_defaults limits."""
        from hub.apps.tenants import plan_defaults

        self._wipe_plans()
        tenant = Tenant.objects.create(
            name=f"W27 {_uid()}",
            slug=f"w27-{_uid()}",
            status="ACTIVE",
            kyc_status=KYCStatus.VERIFIED,
        )
        # marketplace is the paid layer — the sanctioned guard covers
        # both core-only absence forms (W7.1).
        try:
            from hub.apps.marketplace.tests.billing_support import (
                ensure_tenant_has_active_subscription,
            )
        except (RuntimeError, ModuleNotFoundError):
            pytest.skip("marketplace (paid layer) not installed in core-only mode")

        ensure_tenant_has_active_subscription(tenant)

        free_canonical = next(p for p in plan_defaults.PLATFORM_PLANS if p["slug"] == "free")
        free_plan = TenantPlan.objects.get(slug="free")
        self.assertEqual(
            free_plan.limits_json,
            free_canonical["limits_json"],
            "The test-support FREE plan must match canonical plan_defaults "
            "(pre-fix it hardcoded max_assets=100 — the free-plan divergence)",
        )

        # The generous test plan derives from PRO/ML-PRO canonical values.
        ops_plan = TenantPlan.objects.get(slug="scheduled-ops-test-plan")
        pro_canonical = next(p for p in plan_defaults.PLATFORM_PLANS if p["slug"] == "pro")
        self.assertEqual(
            ops_plan.get_limit("max_assets"),
            pro_canonical["limits_json"]["max_assets"],
        )

    def test_e2e_unlimited_plan_keys_cover_known_limit_catalog(self):
        """The e2e-unlimited plan keys = KNOWN_LIMIT_KEYS + ML_LIMIT_KEYS."""
        # billing is the paid layer — the sanctioned guard covers both
        # core-only absence forms (W7.1).
        try:
            from hub.apps.billing.test_support import ensure_e2e_tenant_ready
        except (RuntimeError, ModuleNotFoundError):
            pytest.skip("billing (paid layer) not installed in core-only mode")

        self._wipe_plans()
        tenant = Tenant.objects.create(
            name=f"W27 {_uid()}",
            slug=f"w27-{_uid()}",
            status="ACTIVE",
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_e2e_tenant_ready(tenant)

        plan = TenantPlan.objects.get(slug="e2e-unlimited")
        expected = set(TenantPlan.KNOWN_LIMIT_KEYS) | set(TenantPlan.ML_LIMIT_KEYS)
        self.assertTrue(
            expected.issubset(set(plan.limits_json.keys())),
            "e2e-unlimited must carry EVERY known limit key so a future "
            "key can never re-introduce a quota for E2E tenants; missing: "
            f"{sorted(expected - set(plan.limits_json.keys()))}",
        )
        for key in expected:
            self.assertIsNone(
                plan.limits_json[key],
                f"e2e-unlimited[{key}] must be None (unlimited)",
            )
