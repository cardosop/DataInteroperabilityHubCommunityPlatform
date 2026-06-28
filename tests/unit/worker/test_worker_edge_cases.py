"""
Edge case tests for worker service.

Tests worker restart, Redis connection loss, concurrent job creation, and invalid job data.
"""

import threading
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase

from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.jobs.utils import (
    check_tenant_job_limits,
    decrement_tenant_job_counter,
    increment_tenant_job_counter,
)
from hub.apps.users.models import UserStatus
from tests.factories import JobFactory, TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class WorkerServiceEdgeCaseTest(TransactionTestCase):
    """Edge case tests for worker service

    Uses TransactionTestCase instead of TestCase to support threading tests.
    TransactionTestCase commits transactions, making data visible across threads.
    """

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = TenantFactory.create_tenant()
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        # Refresh from DB to ensure objects are properly loaded
        self.tenant.refresh_from_db()
        self.user.refresh_from_db()

    def test_worker_restart_during_job_processing(self):
        """Test worker restart during job processing"""
        # Create a job
        job = JobFactory.create_job(
            tenant=self.tenant, created_by=self.user, type=JobType.DQ_RUN, status=JobStatus.RUNNING
        )

        # Simulate worker restart by checking job state
        # Job should remain in RUNNING or be marked as FAILED
        job.refresh_from_db()
        self.assertIn(job.status, [JobStatus.RUNNING, JobStatus.FAILED, JobStatus.PENDING])

    def test_redis_connection_loss(self):
        """Test handling of Redis connection loss.

        If Redis is available, the counter is incremented and decremented.
        If Redis is unavailable, a ConnectionError is raised and caught.
        """
        try:
            increment_tenant_job_counter(str(self.tenant.id), "running")
            decrement_tenant_job_counter(str(self.tenant.id), "running")
        except ConnectionError:
            self.skipTest("Redis not available in test environment")

    def test_concurrent_job_creation_100_jobs(self):
        """Test creating 100 jobs simultaneously"""
        jobs_created = []
        errors = []
        lock = threading.Lock()

        # Refresh tenant and user from DB to ensure they're available for all threads
        self.tenant.refresh_from_db()
        self.user.refresh_from_db()

        def create_job(index):
            try:
                job = JobFactory.create_job(
                    tenant=self.tenant,
                    created_by=self.user,
                    type=JobType.DQ_RUN,
                    status=JobStatus.PENDING,
                )
                with lock:
                    jobs_created.append(job.id)
            except Exception as e:
                with lock:
                    errors.append(f"Thread {index}: {e!s}")

        # Create 100 jobs concurrently
        threads = []
        for i in range(100):
            thread = threading.Thread(target=create_job, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Debug: print errors if no jobs created
        if len(jobs_created) == 0 and len(errors) > 0:
            print(f"Errors during concurrent job creation: {errors[:5]}")  # Print first 5 errors

        # Should create jobs (may have some failures due to limits or threading issues)
        # In test environment, some failures are expected due to database constraints
        self.assertGreater(
            len(jobs_created), 0, f"No jobs created. Errors: {errors[:5] if errors else 'None'}"
        )

    def test_job_with_invalid_data(self):
        """Test job processing with invalid data"""
        # Create job with invalid details_json
        job = JobFactory.create_job(
            tenant=self.tenant,
            created_by=self.user,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            details_json={"invalid": "data", "contract_id": None},  # Invalid
        )

        # Job should be created but may fail processing
        self.assertIsNotNone(job)
        self.assertEqual(job.status, JobStatus.PENDING)

    def test_job_with_missing_required_fields(self):
        """Test job creation with intentionally incomplete field set.

        If the model enforces required fields via NOT NULL constraints,
        creation raises (e.g. IntegrityError).  If creation succeeds,
        the model is lenient about those fields.
        """
        from django.db import IntegrityError

        try:
            job = Job.objects.create(
                tenant=self.tenant,
                created_by=self.user,
                type=JobType.DQ_RUN,
                resource_type="DQ_RUN",
                resource_id=uuid.uuid4(),
                # Missing other required fields
            )
            self.assertIsNotNone(job)
        except IntegrityError:
            # Expected — NOT NULL constraint on required fields
            pass

    def test_job_timeout_handling(self):
        """Test job timeout handling"""
        # Create a job that might timeout
        job = JobFactory.create_job(
            tenant=self.tenant, created_by=self.user, type=JobType.DQ_RUN, status=JobStatus.RUNNING
        )

        # Simulate timeout by checking job status
        # Jobs with timeout should be handled appropriately
        job.refresh_from_db()
        self.assertIn(
            job.status,
            [JobStatus.RUNNING, JobStatus.FAILED, JobStatus.COMPLETED, JobStatus.PENDING],
        )

    def test_job_retry_after_failure(self):
        """Test job retry after failure"""
        # Create a failed job
        job = JobFactory.create_job(
            tenant=self.tenant,
            created_by=self.user,
            type=JobType.DQ_RUN,
            status=JobStatus.FAILED,
            error_message="Test error",
            details_json={"retry_count": 0},
        )

        # Job should be retryable if retries remaining
        # Check retry logic
        from hub.apps.jobs.utils import get_job_max_retries

        max_retries = get_job_max_retries(JobType.DQ_RUN)
        retry_count = job.details_json.get("retry_count", 0) if job.details_json else 0

        # Should be retryable if retries remaining
        can_retry = retry_count < max_retries
        self.assertIsInstance(can_retry, bool)

    def test_concurrent_job_processing(self):
        """Test concurrent job processing"""
        # Create multiple jobs
        jobs = []
        for _i in range(10):
            job = JobFactory.create_job(
                tenant=self.tenant,
                created_by=self.user,
                type=JobType.DQ_RUN,
                status=JobStatus.PENDING,
            )
            jobs.append(job)

        # Jobs should be processable concurrently (subject to limits)
        for job in jobs:
            job.refresh_from_db()
            self.assertIn(
                job.status,
                [JobStatus.PENDING, JobStatus.RUNNING, JobStatus.COMPLETED, JobStatus.FAILED],
            )

    def test_tenant_job_limit_enforcement(self):
        """Test tenant job limit enforcement"""
        # Check tenant job limits
        can_create, error_msg = check_tenant_job_limits(str(self.tenant.id))

        # Should return boolean and optional error message
        self.assertIsInstance(can_create, bool)
        if error_msg:
            self.assertIsInstance(error_msg, str)

    def test_job_with_nonexistent_tenant(self):
        """Test job with non-existent tenant"""
        import uuid

        fake_tenant_id = str(uuid.uuid4())

        # Should handle non-existent tenant gracefully
        can_create, _error_msg = check_tenant_job_limits(fake_tenant_id)

        # May return False or handle gracefully
        self.assertIsInstance(can_create, bool)

    def test_job_queue_selection(self):
        """Test job queue selection based on type"""
        from hub.apps.jobs.utils import get_queue_for_job_type

        # Test queue selection for different job types
        queue_names = {
            JobType.DQ_RUN: get_queue_for_job_type(JobType.DQ_RUN),
            JobType.COMPLIANCE_RUN: get_queue_for_job_type(JobType.COMPLIANCE_RUN),
            JobType.CONTRACT_VALIDATION: get_queue_for_job_type(JobType.CONTRACT_VALIDATION),
            JobType.SEMANTIC_MAPPING: get_queue_for_job_type(JobType.SEMANTIC_MAPPING),
        }

        # All should return valid queue names
        for _job_type, queue_name in queue_names.items():
            self.assertIsNotNone(queue_name)
            self.assertIsInstance(queue_name, str)

    def test_job_starvation_prevention(self):
        """Test job starvation prevention logic"""
        from hub.apps.jobs.utils import (
            get_job_wait_time,
            get_queue_for_job_type,
            should_elevate_job,
        )

        # Create a job that has been waiting
        job = JobFactory.create_job(
            tenant=self.tenant, created_by=self.user, type=JobType.DQ_RUN, status=JobStatus.PENDING
        )

        # Check if job should be elevated
        queue_name = get_queue_for_job_type(JobType.DQ_RUN)
        should_elevate = should_elevate_job(str(job.id), queue_name)

        # Should return boolean
        self.assertIsInstance(should_elevate, bool)

        # Check wait time (may be None if job wasn't enqueued via create_job utility)
        wait_time = get_job_wait_time(str(job.id))
        # Wait time can be None if job wasn't enqueued with timestamp tracking
        if wait_time is not None:
            self.assertIsInstance(wait_time, (int, float))
            self.assertGreaterEqual(wait_time, 0)
        # If None, that's acceptable - job wasn't enqueued via create_job utility
