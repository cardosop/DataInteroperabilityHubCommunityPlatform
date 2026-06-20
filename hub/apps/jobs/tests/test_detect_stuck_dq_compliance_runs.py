"""
285.10.3.5.1 — Tests for detect_stuck_dq_compliance_runs management command.

Covers:
- DQ runs stuck in RUNNING >2x timeout are marked FAILED with STUCK_RUN_DETECTED
- Compliance runs stuck in RUNNING >2x timeout are marked FAILED with STUCK_RUN_DETECTED
- Associated Jobs are transitioned to FAILED
- DLQ entries are written for stuck runs
- Runs within timeout are not affected
- Non-RUNNING runs are not affected
- --dry-run reports without modifying
- --tenant-id filter works
- --direction filter works
- warehouse_config.query_timeout_seconds is respected
"""

import uuid
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.dq.models import DQEngine, DQRun, DQRunStatus
from hub.apps.jobs.models import FailedJobDLQ, Job, JobStatus, JobType
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)

from django.contrib.auth import get_user_model

User = get_user_model()


# ── Helpers ────────────────────────────────────────────────────────────


def _make_tenant(slug_prefix: str = "t") -> Tenant:
    from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

    slug = f"{slug_prefix}-{uuid.uuid4().hex[:8]}"
    tenant = Tenant.objects.create(
        name=f"Tenant-{slug}",
        slug=slug,
        status="ACTIVE",
    )
    ensure_tenant_has_active_subscription(tenant)
    return tenant


def _make_user(tenant: Tenant) -> tuple:
    email = f"user_{uuid.uuid4().hex[:8]}@test.local"
    user = User.objects.create_user(email=email, password="Pass1234!", tenant=tenant)
    user.status = UserStatus.ACTIVE
    user.save(update_fields=["status"])
    return user, email


def _make_dataset(tenant: Tenant) -> "Dataset":
    """Create a minimal Dataset for FK validation in ComplianceRun/DQRun tests."""
    from hub.apps.datasets.models import Dataset

    return Dataset.objects.create(
        tenant=tenant,
        format="CSV",
        row_count=0,
    )


def _make_job(tenant: Tenant, job_type: str = JobType.DQ_RUN) -> Job:
    dataset = _make_dataset(tenant)
    return Job.objects.create(
        tenant=tenant,
        type=job_type,
        status=JobStatus.RUNNING,
        resource_type="DATASET",
        resource_id=dataset.id,
        started_at=timezone.now(),
    )


# ── DQ Stuck Run Detection ────────────────────────────────────────────


@pytest.mark.integration
class TestDetectStuckDQComplianceRuns(TestCase):
    """285.10.3.5.1 — Stuck run detector for DQ/Compliance runs."""

    def setUp(self):
        self.tenant = _make_tenant(slug_prefix="stuckdq")
        self.user, _ = _make_user(self.tenant)

    # ── DQ: within timeout → no effect ──────────────────────────────

    @pytest.mark.integration
    def test_dq_run_within_timeout_not_affected(self):
        """DQ run started recently should not be touched."""
        job = _make_job(self.tenant, JobType.DQ_RUN)
        run = DQRun.objects.create(
            tenant=self.tenant,
            job=job,
            asset_id=None,
            dataset_id=job.resource_id,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.RUNNING,
            started_at=timezone.now() - timedelta(seconds=60),
            warehouse_config={"query_timeout_seconds": 300},
        )

        call_command("detect_stuck_dq_compliance_runs", stdout=StringIO())

        run.refresh_from_db()
        self.assertEqual(run.status, DQRunStatus.RUNNING)

    # ── DQ: >2x warehouse timeout → FAILED ─────────────────────────

    @pytest.mark.integration
    def test_dq_run_exceeds_2x_warehouse_timeout_marked_failed(self):
        """DQ run stuck >2x warehouse_config.query_timeout_seconds → FAILED."""
        job = _make_job(self.tenant, JobType.DQ_RUN)
        run = DQRun.objects.create(
            tenant=self.tenant,
            job=job,
            dataset_id=job.resource_id,
            profile_key="intake_basic_gx",
            engine=DQEngine.SODA,
            status=DQRunStatus.RUNNING,
            started_at=timezone.now() - timedelta(seconds=700),  # >2*300=600
            warehouse_config={"query_timeout_seconds": 300},
        )

        call_command("detect_stuck_dq_compliance_runs", stdout=StringIO())

        run.refresh_from_db()
        self.assertEqual(run.status, DQRunStatus.FAILED)
        details = run.details_json or {}
        self.assertEqual(details.get("error_code"), "STUCK_RUN_DETECTED")
        # error_message contains descriptive text like "stuck in RUNNING for Ns"
        self.assertIn("stuck in RUNNING", details.get("error_message", ""))
        self.assertIsNotNone(run.completed_at)
        self.assertIn("stuck_duration_seconds", details)

    # ── DQ: associated Job also failed ──────────────────────────────

    @pytest.mark.integration
    def test_dq_stuck_run_fails_associated_job(self):
        """When a DQ run is stuck, its RUNNING Job is also marked FAILED."""
        job = _make_job(self.tenant, JobType.DQ_RUN)
        DQRun.objects.create(
            tenant=self.tenant,
            job=job,
            dataset_id=job.resource_id,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.RUNNING,
            started_at=timezone.now() - timedelta(seconds=3700),  # >2*1800=3600
        )

        call_command("detect_stuck_dq_compliance_runs", stdout=StringIO())

        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.FAILED)
        self.assertIn("stuck in RUNNING", job.error_message or "")
        self.assertEqual((job.result_json or {}).get("error_code"), "STUCK_RUN_DETECTED")

    # ── DQ: DLQ entry written ───────────────────────────────────────

    @pytest.mark.integration
    def test_dq_stuck_run_writes_dlq_entry(self):
        """A stuck DQ run writes a DLQ entry for the associated Job."""
        job = _make_job(self.tenant, JobType.DQ_RUN)
        DQRun.objects.create(
            tenant=self.tenant,
            job=job,
            dataset_id=job.resource_id,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.RUNNING,
            started_at=timezone.now() - timedelta(seconds=3700),
        )

        call_command("detect_stuck_dq_compliance_runs", stdout=StringIO())

        dlq_exists = FailedJobDLQ.objects.filter(job_id=job.id).exists()
        self.assertTrue(dlq_exists, "DLQ entry should be written for stuck run")

    # ── DQ: non-RUNNING runs not touched ────────────────────────────

    @pytest.mark.integration
    def test_dq_non_running_runs_not_affected(self):
        """SUCCEEDED / PENDING DQ runs should not be touched."""
        job = _make_job(self.tenant, JobType.DQ_RUN)
        succeeded = DQRun.objects.create(
            tenant=self.tenant,
            job=job,
            dataset_id=job.resource_id,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
            started_at=timezone.now() - timedelta(seconds=3700),
        )

        call_command("detect_stuck_dq_compliance_runs", stdout=StringIO())

        succeeded.refresh_from_db()
        self.assertEqual(succeeded.status, DQRunStatus.SUCCEEDED)

    # ── Compliance: >2x timeout → FAILED ────────────────────────────

    @pytest.mark.integration
    def test_compliance_run_exceeds_2x_timeout_marked_failed(self):
        """Compliance run stuck >2x warehouse timeout → FAILED."""
        job = _make_job(self.tenant, JobType.COMPLIANCE_RUN)
        run = ComplianceRun.objects.create(
            tenant=self.tenant,
            job=job,
            dataset_id=job.resource_id,
            scan_mode="WAREHOUSE_SQL",
            status=ComplianceRunStatus.RUNNING,
            started_at=timezone.now() - timedelta(seconds=700),  # >2*300=600
            warehouse_config={"query_timeout_seconds": 300},
        )

        call_command("detect_stuck_dq_compliance_runs", stdout=StringIO())

        run.refresh_from_db()
        self.assertEqual(run.status, ComplianceRunStatus.FAILED)
        metadata = run.metadata_json or {}
        self.assertEqual(metadata.get("error_code"), "STUCK_RUN_DETECTED")
        self.assertIn("stuck in RUNNING", metadata.get("error_message", ""))
        self.assertIsNotNone(run.completed_at)

    # ── Compliance: associated Job also failed ──────────────────────

    @pytest.mark.integration
    def test_compliance_stuck_run_fails_associated_job(self):
        """When a Compliance run is stuck, its RUNNING Job is also FAILED."""
        job = _make_job(self.tenant, JobType.COMPLIANCE_RUN)
        ComplianceRun.objects.create(
            tenant=self.tenant,
            job=job,
            dataset_id=job.resource_id,
            scan_mode="FILE_SCAN",
            status=ComplianceRunStatus.RUNNING,
            started_at=timezone.now() - timedelta(seconds=3700),  # >2*1800=3600
        )

        call_command("detect_stuck_dq_compliance_runs", stdout=StringIO())

        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.FAILED)

    # ── Compliance: within timeout → no effect ──────────────────────

    @pytest.mark.integration
    def test_compliance_run_within_timeout_not_affected(self):
        """Compliance run started recently should not be touched."""
        job = _make_job(self.tenant, JobType.COMPLIANCE_RUN)
        run = ComplianceRun.objects.create(
            tenant=self.tenant,
            job=job,
            dataset_id=job.resource_id,
            scan_mode="FILE_SCAN",
            status=ComplianceRunStatus.RUNNING,
            started_at=timezone.now() - timedelta(seconds=30),
        )

        call_command("detect_stuck_dq_compliance_runs", stdout=StringIO())

        run.refresh_from_db()
        self.assertEqual(run.status, ComplianceRunStatus.RUNNING)

    # ── Compliance: DLQ entry written ───────────────────────────────

    @pytest.mark.integration
    def test_compliance_stuck_run_writes_dlq_entry(self):
        """A stuck Compliance run writes a DLQ entry."""
        job = _make_job(self.tenant, JobType.COMPLIANCE_RUN)
        ComplianceRun.objects.create(
            tenant=self.tenant,
            job=job,
            dataset_id=job.resource_id,
            scan_mode="WAREHOUSE_SQL",
            status=ComplianceRunStatus.RUNNING,
            started_at=timezone.now() - timedelta(seconds=3700),
        )

        call_command("detect_stuck_dq_compliance_runs", stdout=StringIO())

        dlq_exists = FailedJobDLQ.objects.filter(job_id=job.id).exists()
        self.assertTrue(dlq_exists, "DLQ entry should be written for stuck compliance run")

    # ── --dry-run ───────────────────────────────────────────────────

    @pytest.mark.integration
    def test_dry_run_reports_but_does_not_modify(self):
        """--dry-run should list stuck runs without changing status."""
        job = _make_job(self.tenant, JobType.DQ_RUN)
        run = DQRun.objects.create(
            tenant=self.tenant,
            job=job,
            dataset_id=job.resource_id,
            profile_key="intake_basic_gx",
            engine=DQEngine.SODA,
            status=DQRunStatus.RUNNING,
            started_at=timezone.now() - timedelta(seconds=700),
            warehouse_config={"query_timeout_seconds": 300},
        )

        out = StringIO()
        call_command(
            "detect_stuck_dq_compliance_runs",
            dry_run=True,
            stdout=out,
        )

        run.refresh_from_db()
        self.assertEqual(run.status, DQRunStatus.RUNNING, "dry-run must not modify")
        self.assertIn("DRY-RUN", out.getvalue())

    # ── --tenant-id filter ──────────────────────────────────────────

    @pytest.mark.integration
    def test_tenant_id_filter_only_affects_target_tenant(self):
        """--tenant-id should only process the specified tenant."""
        other_tenant = _make_tenant(slug_prefix="other")

        # Stuck run in target tenant
        job_a = _make_job(self.tenant, JobType.DQ_RUN)
        run_a = DQRun.objects.create(
            tenant=self.tenant,
            job=job_a,
            dataset_id=job_a.resource_id,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.RUNNING,
            started_at=timezone.now() - timedelta(seconds=3700),
        )

        # Stuck run in other tenant (should be untouched)
        job_b = _make_job(other_tenant, JobType.DQ_RUN)
        run_b = DQRun.objects.create(
            tenant=other_tenant,
            job=job_b,
            dataset_id=job_b.resource_id,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.RUNNING,
            started_at=timezone.now() - timedelta(seconds=3700),
        )

        call_command(
            "detect_stuck_dq_compliance_runs",
            tenant_id=str(self.tenant.id),
            stdout=StringIO(),
        )

        run_a.refresh_from_db()
        run_b.refresh_from_db()
        self.assertEqual(run_a.status, DQRunStatus.FAILED, "target tenant run should be failed")
        self.assertEqual(run_b.status, DQRunStatus.RUNNING, "other tenant run should be untouched")

        # Cleanup other tenant
        DQRun.objects.filter(tenant=other_tenant).delete()
        Job.objects.filter(tenant=other_tenant).delete()
        other_tenant.delete()

    # ── --direction filter ──────────────────────────────────────────

    @pytest.mark.integration
    def test_direction_dq_only_skips_compliance(self):
        """--direction=dq should only check DQ runs."""
        # Stuck DQ run
        dq_job = _make_job(self.tenant, JobType.DQ_RUN)
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            job=dq_job,
            dataset_id=dq_job.resource_id,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.RUNNING,
            started_at=timezone.now() - timedelta(seconds=3700),
        )

        # Stuck Compliance run
        comp_job = _make_job(self.tenant, JobType.COMPLIANCE_RUN)
        comp_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            job=comp_job,
            dataset_id=comp_job.resource_id,
            scan_mode="FILE_SCAN",
            status=ComplianceRunStatus.RUNNING,
            started_at=timezone.now() - timedelta(seconds=3700),
        )

        call_command(
            "detect_stuck_dq_compliance_runs",
            direction="dq",
            stdout=StringIO(),
        )

        dq_run.refresh_from_db()
        comp_run.refresh_from_db()
        self.assertEqual(dq_run.status, DQRunStatus.FAILED, "DQ run should be failed")
        self.assertEqual(
            comp_run.status, ComplianceRunStatus.RUNNING, "Compliance run should be untouched"
        )

    @pytest.mark.integration
    def test_direction_compliance_only_skips_dq(self):
        """--direction=compliance should only check Compliance runs."""
        # Stuck DQ run
        dq_job = _make_job(self.tenant, JobType.DQ_RUN)
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            job=dq_job,
            dataset_id=dq_job.resource_id,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.RUNNING,
            started_at=timezone.now() - timedelta(seconds=3700),
        )

        # Stuck Compliance run
        comp_job = _make_job(self.tenant, JobType.COMPLIANCE_RUN)
        comp_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            job=comp_job,
            dataset_id=comp_job.resource_id,
            scan_mode="FILE_SCAN",
            status=ComplianceRunStatus.RUNNING,
            started_at=timezone.now() - timedelta(seconds=3700),
        )

        call_command(
            "detect_stuck_dq_compliance_runs",
            direction="compliance",
            stdout=StringIO(),
        )

        dq_run.refresh_from_db()
        comp_run.refresh_from_db()
        self.assertEqual(dq_run.status, DQRunStatus.RUNNING, "DQ run should be untouched")
        self.assertEqual(
            comp_run.status, ComplianceRunStatus.FAILED, "Compliance run should be failed"
        )

    # ── --threshold-multiplier ──────────────────────────────────────

    @pytest.mark.integration
    def test_threshold_multiplier_changes_stuck_cutoff(self):
        """A higher multiplier means only older runs are detected."""
        job = _make_job(self.tenant, JobType.DQ_RUN)
        run = DQRun.objects.create(
            tenant=self.tenant,
            job=job,
            dataset_id=job.resource_id,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.RUNNING,
            started_at=timezone.now() - timedelta(seconds=3700),  # >2x=3600
            warehouse_config={"query_timeout_seconds": 1800},
        )

        # With multiplier=3, threshold is 3*1800=5400, so 3700 is NOT stuck
        call_command(
            "detect_stuck_dq_compliance_runs",
            threshold_multiplier=3.0,
            stdout=StringIO(),
        )

        run.refresh_from_db()
        self.assertEqual(run.status, DQRunStatus.RUNNING, "multiplier=3: 3700s < 3*1800=5400s")

    # ── Job already COMPLETED while DQRun still RUNNING ─────────────

    @pytest.mark.integration
    def test_dq_run_stuck_job_already_terminal(self):
        """If the Job is already in a terminal state, only the DQ run is failed."""
        job = _make_job(self.tenant, JobType.DQ_RUN)
        job.status = JobStatus.COMPLETED
        job.save()

        run = DQRun.objects.create(
            tenant=self.tenant,
            job=job,
            dataset_id=job.resource_id,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.RUNNING,
            started_at=timezone.now() - timedelta(seconds=3700),
        )

        call_command("detect_stuck_dq_compliance_runs", stdout=StringIO())

        run.refresh_from_db()
        job.refresh_from_db()
        self.assertEqual(run.status, DQRunStatus.FAILED)
        self.assertEqual(job.status, JobStatus.COMPLETED, "terminal Job should not be changed")

    # ── Timeout from Job.timeout_seconds ────────────────────────────

    @pytest.mark.integration
    def test_dq_run_timeout_from_job_timeout_seconds(self):
        """Timeout falls back to Job.timeout_seconds when no warehouse_config."""
        job = _make_job(self.tenant, JobType.DQ_RUN)
        job.timeout_seconds = 600  # 10 minutes
        job.save()

        run = DQRun.objects.create(
            tenant=self.tenant,
            job=job,
            dataset_id=job.resource_id,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.RUNNING,
            started_at=timezone.now() - timedelta(seconds=1300),  # >2*600=1200
            warehouse_config=None,
        )

        call_command("detect_stuck_dq_compliance_runs", stdout=StringIO())

        run.refresh_from_db()
        self.assertEqual(run.status, DQRunStatus.FAILED)

    # ── No started_at → skipped ─────────────────────────────────────

    @pytest.mark.integration
    def test_run_without_started_at_skipped(self):
        """RUNNING DQ run without started_at should be skipped (defensive)."""
        job = _make_job(self.tenant, JobType.DQ_RUN)
        run = DQRun.objects.create(
            tenant=self.tenant,
            job=job,
            dataset_id=job.resource_id,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.RUNNING,
            started_at=None,
        )

        call_command("detect_stuck_dq_compliance_runs", stdout=StringIO())

        run.refresh_from_db()
        self.assertEqual(
            run.status, DQRunStatus.RUNNING, "run without started_at should be skipped"
        )

    # ── QUEUED ComplianceRun detection ───────────────────────────────

    @pytest.mark.integration
    def test_queued_compliance_run_exceeding_stale_minutes_marked_failed(self):
        """QUEUED ComplianceRun older than --stale-queued-minutes → FAILED."""
        job = _make_job(self.tenant, JobType.COMPLIANCE_RUN)
        run = ComplianceRun.objects.create(
            tenant=self.tenant,
            job=job,
            dataset_id=job.resource_id,
            scan_mode="WAREHOUSE_SQL",
            status=ComplianceRunStatus.QUEUED,
        )
        # auto_now_add overrides explicit created_at; force via queryset update
        ComplianceRun.objects.filter(id=run.id).update(
            created_at=timezone.now() - timedelta(minutes=90),
        )

        call_command(
            "detect_stuck_dq_compliance_runs",
            stale_queued_minutes=60,
            stdout=StringIO(),
        )

        run.refresh_from_db()
        self.assertEqual(run.status, ComplianceRunStatus.FAILED)
        metadata = run.metadata_json or {}
        self.assertEqual(metadata.get("error_code"), "STUCK_RUN_DETECTED")
        # error_message describes stuck-in-QUEUED details (see management command)
        self.assertTrue(metadata.get("error_message"))
        self.assertIsNotNone(run.completed_at)

    @pytest.mark.integration
    def test_queued_compliance_run_within_limit_not_affected(self):
        """QUEUED ComplianceRun within stale threshold is NOT touched."""
        job = _make_job(self.tenant, JobType.COMPLIANCE_RUN)
        run = ComplianceRun.objects.create(
            tenant=self.tenant,
            job=job,
            dataset_id=job.resource_id,
            scan_mode="FILE_SCAN",
            status=ComplianceRunStatus.QUEUED,
        )
        # auto_now_add overrides explicit created_at; force via queryset update
        ComplianceRun.objects.filter(id=run.id).update(
            created_at=timezone.now() - timedelta(minutes=30),
        )

        call_command(
            "detect_stuck_dq_compliance_runs",
            stale_queued_minutes=60,
            stdout=StringIO(),
        )

        run.refresh_from_db()
        self.assertEqual(run.status, ComplianceRunStatus.QUEUED)

    @pytest.mark.integration
    def test_dry_run_lists_queued_runs(self):
        """--dry-run reports QUEUED runs without changing status."""
        job = _make_job(self.tenant, JobType.COMPLIANCE_RUN)
        run = ComplianceRun.objects.create(
            tenant=self.tenant,
            job=job,
            dataset_id=job.resource_id,
            scan_mode="WAREHOUSE_SQL",
            status=ComplianceRunStatus.QUEUED,
        )
        # auto_now_add overrides explicit created_at; force via queryset update
        ComplianceRun.objects.filter(id=run.id).update(
            created_at=timezone.now() - timedelta(minutes=90),
        )

        out = StringIO()
        call_command(
            "detect_stuck_dq_compliance_runs",
            dry_run=True,
            stale_queued_minutes=60,
            stdout=out,
        )

        run.refresh_from_db()
        self.assertEqual(run.status, ComplianceRunStatus.QUEUED, "dry-run must not modify")
        self.assertIn("DRY-RUN", out.getvalue())

    @pytest.mark.integration
    def test_queued_run_fails_associated_job(self):
        """QUEUED ComplianceRun stuck → associated RUNNING Job also FAILED."""
        job = _make_job(self.tenant, JobType.COMPLIANCE_RUN)
        run = ComplianceRun.objects.create(
            tenant=self.tenant,
            job=job,
            dataset_id=job.resource_id,
            scan_mode="WAREHOUSE_SQL",
            status=ComplianceRunStatus.QUEUED,
        )
        # auto_now_add overrides explicit created_at; force via queryset update
        ComplianceRun.objects.filter(id=run.id).update(
            created_at=timezone.now() - timedelta(minutes=90),
        )

        call_command(
            "detect_stuck_dq_compliance_runs",
            stale_queued_minutes=60,
            stdout=StringIO(),
        )

        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.FAILED)
        self.assertIn("stuck in QUEUED", job.error_message or "")

    @pytest.mark.integration
    def test_queued_run_writes_dlq_entry(self):
        """QUEUED ComplianceRun stuck → DLQ entry written."""
        job = _make_job(self.tenant, JobType.COMPLIANCE_RUN)
        run = ComplianceRun.objects.create(
            tenant=self.tenant,
            job=job,
            dataset_id=job.resource_id,
            scan_mode="WAREHOUSE_SQL",
            status=ComplianceRunStatus.QUEUED,
        )
        # auto_now_add overrides explicit created_at; force via queryset update
        ComplianceRun.objects.filter(id=run.id).update(
            created_at=timezone.now() - timedelta(minutes=90),
        )

        call_command(
            "detect_stuck_dq_compliance_runs",
            stale_queued_minutes=60,
            stdout=StringIO(),
        )

        self.assertTrue(FailedJobDLQ.objects.filter(job_id=job.id).exists())

    # ── Error code constant propagation ──────────────────────────────

    @pytest.mark.integration
    def test_stuck_dq_run_sets_error_code_in_details_json(self):
        """details_json should include stuck metadata after detection."""
        job = _make_job(self.tenant, JobType.DQ_RUN)
        run = DQRun.objects.create(
            tenant=self.tenant,
            job=job,
            dataset_id=job.resource_id,
            profile_key="intake_basic_gx",
            engine=DQEngine.SODA,
            status=DQRunStatus.RUNNING,
            started_at=timezone.now() - timedelta(seconds=3700),
        )

        call_command("detect_stuck_dq_compliance_runs", stdout=StringIO())

        run.refresh_from_db()
        self.assertIsNotNone(run.details_json)
        self.assertIn("stuck_detected_at", run.details_json)
        self.assertIn("stuck_duration_seconds", run.details_json)

    @pytest.mark.integration
    def test_error_message_capped(self):
        """error_message should be capped at MAX_ERROR_MESSAGE_LENGTH (2000)."""
        job = _make_job(self.tenant, JobType.DQ_RUN)
        run = DQRun.objects.create(
            tenant=self.tenant,
            job=job,
            dataset_id=job.resource_id,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.RUNNING,
            started_at=timezone.now() - timedelta(seconds=3700),
        )

        call_command("detect_stuck_dq_compliance_runs", stdout=StringIO())

        run.refresh_from_db()
        # error_code / error_message now live in details_json
        # (fields were removed in migration 0105).
        details = run.details_json or {}
        self.assertIsNotNone(details.get("error_code"))
        self.assertTrue(len(details.get("error_message", "")) <= 2000)
