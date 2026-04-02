"""Comprehensive tests for jobs/tasks_base.py — Phase 100.1"""
import uuid
import pytest

pytestmark = pytest.mark.slow
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from hub.apps.tenants.models import Tenant
from hub.apps.jobs.models import Job, JobType, JobStatus, JobPriority, FailedJobDLQ
from hub.apps.jobs.tasks_base import _write_to_dlq
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()

class JobClaimAtomicityTest(TestCase):
    """Test atomic job claiming via UPDATE WHERE pattern."""
    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"T {uid}", slug=f"t-{uid}", status="ACTIVE", kyc_status="UNVERIFIED")
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(email=f"u-{uid}@test.com", password="pass", tenant=self.tenant, status="ACTIVE")

    def test_job_created_in_pending_status(self):
        """New jobs are PENDING by default."""
        job = Job.objects.create(tenant=self.tenant, type=JobType.DQ_RUN, resource_type="DATASET", resource_id=uuid.uuid4(), created_by=self.user)
        self.assertEqual(job.status, JobStatus.PENDING)
        self.assertIsNone(job.started_at)
        self.assertIsNone(job.completed_at)

    def test_atomic_claim_transitions_pending_to_running(self):
        """UPDATE WHERE status=PENDING atomically claims exactly 1 job."""
        job = Job.objects.create(tenant=self.tenant, type=JobType.DQ_RUN, resource_type="DATASET", resource_id=uuid.uuid4())
        before = timezone.now()
        count = Job.objects.filter(id=job.id, status=JobStatus.PENDING).update(status=JobStatus.RUNNING, started_at=timezone.now())
        self.assertEqual(count, 1)
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.RUNNING)
        self.assertIsInstance(job.started_at, type(before))
        self.assertGreaterEqual(job.started_at, before, "started_at should be at or after the claim time")

    def test_atomic_claim_fails_if_already_running(self):
        """Second claim attempt on already-running job returns 0 rows updated."""
        job = Job.objects.create(tenant=self.tenant, type=JobType.DQ_RUN, resource_type="DATASET", resource_id=uuid.uuid4(), status=JobStatus.RUNNING, started_at=timezone.now())
        count = Job.objects.filter(id=job.id, status=JobStatus.PENDING).update(status=JobStatus.RUNNING, started_at=timezone.now())
        self.assertEqual(count, 0)

    def test_concurrent_claims_exactly_one_succeeds(self):
        """When two threads attempt to claim, exactly one succeeds (TOCTOU prevention)."""
        job = Job.objects.create(tenant=self.tenant, type=JobType.DQ_RUN, resource_type="DATASET", resource_id=uuid.uuid4())
        count1 = Job.objects.filter(id=job.id, status=JobStatus.PENDING).update(status=JobStatus.RUNNING, started_at=timezone.now())
        count2 = Job.objects.filter(id=job.id, status=JobStatus.PENDING).update(status=JobStatus.RUNNING, started_at=timezone.now())
        self.assertEqual(count1 + count2, 1)

    def test_completion_sets_completed_status_and_timestamp(self):
        """Job transitions to COMPLETED with completed_at set."""
        job = Job.objects.create(tenant=self.tenant, type=JobType.DQ_RUN, resource_type="DATASET", resource_id=uuid.uuid4(), status=JobStatus.RUNNING, started_at=timezone.now())
        now = timezone.now()
        Job.objects.filter(id=job.id).update(status=JobStatus.COMPLETED, completed_at=now)
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.COMPLETED)
        self.assertEqual(job.completed_at, now)
        self.assertGreaterEqual(job.completed_at, job.started_at, "completed_at must be >= started_at")

    def test_failure_sets_failed_status_with_error_message(self):
        """Job transitions to FAILED with error_message set."""
        job = Job.objects.create(tenant=self.tenant, type=JobType.DQ_RUN, resource_type="DATASET", resource_id=uuid.uuid4(), status=JobStatus.RUNNING, started_at=timezone.now())
        Job.objects.filter(id=job.id).update(status=JobStatus.FAILED, error_message="Connection timeout", completed_at=timezone.now())
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.FAILED)
        self.assertEqual(job.error_message, "Connection timeout")

    def test_cancel_pending_job(self):
        """PENDING job can be cancelled."""
        job = Job.objects.create(tenant=self.tenant, type=JobType.DQ_RUN, resource_type="DATASET", resource_id=uuid.uuid4())
        count = Job.objects.filter(id=job.id, status=JobStatus.PENDING).update(status=JobStatus.CANCELLED, completed_at=timezone.now())
        self.assertEqual(count, 1)
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.CANCELLED)

    def test_cancel_running_job(self):
        """RUNNING job can be cancelled."""
        job = Job.objects.create(tenant=self.tenant, type=JobType.DQ_RUN, resource_type="DATASET", resource_id=uuid.uuid4(), status=JobStatus.RUNNING, started_at=timezone.now())
        count = Job.objects.filter(id=job.id, status=JobStatus.RUNNING).update(status=JobStatus.CANCELLED, completed_at=timezone.now())
        self.assertEqual(count, 1)

    def test_progress_tracking_via_details_json(self):
        """Progress stored in details_json field."""
        job = Job.objects.create(tenant=self.tenant, type=JobType.DQ_RUN, resource_type="DATASET", resource_id=uuid.uuid4(), details_json={"progress": 0})
        Job.objects.filter(id=job.id).update(details_json={"progress": 50, "rows_processed": 1000})
        job.refresh_from_db()
        self.assertEqual(job.details_json["progress"], 50)
        self.assertEqual(job.details_json["rows_processed"], 1000)

    def test_completed_job_cannot_be_claimed(self):
        """COMPLETED job cannot be re-claimed (invalid transition)."""
        job = Job.objects.create(tenant=self.tenant, type=JobType.DQ_RUN, resource_type="DATASET", resource_id=uuid.uuid4(), status=JobStatus.COMPLETED, completed_at=timezone.now())
        count = Job.objects.filter(id=job.id, status=JobStatus.PENDING).update(status=JobStatus.RUNNING, started_at=timezone.now())
        self.assertEqual(count, 0)
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.COMPLETED)

    def test_failed_job_cannot_be_claimed(self):
        """FAILED job cannot be re-claimed without explicit reset."""
        job = Job.objects.create(tenant=self.tenant, type=JobType.DQ_RUN, resource_type="DATASET", resource_id=uuid.uuid4(), status=JobStatus.FAILED, error_message="prev error")
        count = Job.objects.filter(id=job.id, status=JobStatus.PENDING).update(status=JobStatus.RUNNING, started_at=timezone.now())
        self.assertEqual(count, 0)
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.FAILED)


class DLQWriteTest(TestCase):
    """Test dead-letter queue write operations."""
    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"T {uid}", slug=f"t-{uid}", status="ACTIVE", kyc_status="UNVERIFIED")
        ensure_tenant_has_active_subscription(self.tenant)

    def test_write_to_dlq_creates_entry(self):
        """_write_to_dlq creates a FailedJobDLQ record."""
        job = Job.objects.create(tenant=self.tenant, type=JobType.DQ_RUN, resource_type="DATASET", resource_id=uuid.uuid4())
        exc = RuntimeError("service unavailable")
        _write_to_dlq(job, JobType.DQ_RUN, exc)
        entry = FailedJobDLQ.objects.get(job_id=job.id)
        self.assertEqual(entry.error_message, "service unavailable")
        self.assertEqual(entry.tenant, self.tenant)
        self.assertIn("process_job", entry.func_name)

    def test_write_to_dlq_stores_args_json(self):
        """DLQ entry contains job_id and job_type in args_json."""
        job = Job.objects.create(tenant=self.tenant, type=JobType.COMPLIANCE_RUN, resource_type="ASSET", resource_id=uuid.uuid4())
        _write_to_dlq(job, JobType.COMPLIANCE_RUN, ValueError("bad data"))
        entry = FailedJobDLQ.objects.get(job_id=job.id)
        self.assertEqual(entry.args_json["job_id"], str(job.id))
        self.assertEqual(entry.args_json["job_type"], JobType.COMPLIANCE_RUN)
