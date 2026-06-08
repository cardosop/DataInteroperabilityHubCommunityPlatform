"""
Integration tests for Job Retry Logic

Tests verify that job retry logic works correctly end-to-end,
including retry scheduling, delay calculation, and retry exhaustion.

All tests use real implementations (no mocks/stubs) and follow engineering best practices.
"""
from django.test import TestCase
from django.utils import timezone
from django_rq import get_queue
from hub.apps.jobs.models import Job, JobType, JobStatus
from hub.apps.jobs.utils import (
    retry_job,
    get_job_max_retries,
    calculate_retry_delay,
    is_transient_failure,
    get_queue_for_job_type,
)
from tests.factories import TenantFactory, UserFactory
import structlog

logger = structlog.get_logger(__name__)


class JobRetryLogicIntegrationTest(TestCase):
    """Integration tests for job retry logic"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = TenantFactory.create_tenant()
        self.user = UserFactory.create_user(tenant=self.tenant)

    def test_retry_job_transient_failure(self):
        """Test that retry_job schedules retry for transient failures"""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.RUNNING,
            resource_type='DATASET',
            resource_id='123e4567-e89b-12d3-a456-426614174000',
            created_by=self.user,
            details_json={}
        )

        # Simulate transient failure
        exception = ConnectionError("Service temporarily unavailable")

        # Use real retry_job implementation (no mocks)
        retried = retry_job(job, JobType.DQ_RUN, exception)

        self.assertTrue(retried, "Job should be retried for transient failure")
        job.refresh_from_db()
        self.assertEqual(job.details_json.get('retry_count'), 1)
        self.assertEqual(job.status, JobStatus.PENDING)
        self.assertIsNotNone(job.details_json.get('last_retry_error'))
        self.assertIsNotNone(job.details_json.get('last_retry_at'))

    def test_retry_job_non_transient_failure(self):
        """Test that retry_job does not retry non-transient failures"""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.RUNNING,
            resource_type='DATASET',
            resource_id='123e4567-e89b-12d3-a456-426614174000',
            created_by=self.user,
            details_json={}
        )

        initial_status = job.status
        initial_details = job.details_json.copy()

        # Simulate non-transient failure
        exception = ValueError("Invalid input")

        # Use real retry_job implementation (no mocks)
        retried = retry_job(job, JobType.DQ_RUN, exception)

        self.assertFalse(retried, "Job should not be retried for non-transient failure")
        job.refresh_from_db()
        # Job status should remain unchanged (not reset to PENDING)
        self.assertEqual(job.status, initial_status)
        # Retry count should not be incremented
        self.assertEqual(job.details_json.get('retry_count', 0), initial_details.get('retry_count', 0))

    def test_retry_job_exhausted_retries(self):
        """Test that retry_job does not retry when retries are exhausted"""
        max_retries = get_job_max_retries(JobType.DQ_RUN)
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.RUNNING,
            resource_type='DATASET',
            resource_id='123e4567-e89b-12d3-a456-426614174000',
            created_by=self.user,
            details_json={'retry_count': max_retries}
        )

        initial_status = job.status
        initial_retry_count = job.details_json.get('retry_count')

        exception = ConnectionError("Service temporarily unavailable")

        # Use real retry_job implementation (no mocks)
        retried = retry_job(job, JobType.DQ_RUN, exception)

        self.assertFalse(retried, "Job should not be retried when retries exhausted")
        job.refresh_from_db()
        # Job status should remain unchanged
        self.assertEqual(job.status, initial_status)
        # Retry count should not be incremented
        self.assertEqual(job.details_json.get('retry_count'), initial_retry_count)

    def test_retry_delay_calculation(self):
        """Test that retry delay is calculated correctly"""
        delay_0 = calculate_retry_delay(0, type=JobType.DQ_RUN)
        delay_1 = calculate_retry_delay(1, type=JobType.DQ_RUN)
        delay_2 = calculate_retry_delay(2, type=JobType.DQ_RUN)

        # Verify exponential backoff
        self.assertLess(delay_0, delay_1)
        self.assertLess(delay_1, delay_2)

        # Verify delay is capped at max_delay
        from hub.apps.jobs.utils import get_job_retry_max_delay
        max_delay = get_job_retry_max_delay(JobType.DQ_RUN)
        self.assertLessEqual(delay_0, max_delay)
        self.assertLessEqual(delay_1, max_delay)
        self.assertLessEqual(delay_2, max_delay)

    def test_is_transient_failure(self):
        """Test that is_transient_failure correctly identifies transient failures"""
        # Transient failures
        self.assertTrue(is_transient_failure(ConnectionError("Connection failed")))
        self.assertTrue(is_transient_failure(TimeoutError("Request timed out")))
        self.assertTrue(is_transient_failure(Exception("Service temporarily unavailable")))

        # Non-transient failures
        self.assertFalse(is_transient_failure(ValueError("Invalid input")))
        self.assertFalse(is_transient_failure(Exception("Permission denied")))

    def test_retry_job_tracks_retry_count(self):
        """Test that retry_job increments retry count correctly"""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.RUNNING,
            resource_type='DATASET',
            resource_id='123e4567-e89b-12d3-a456-426614174000',
            created_by=self.user,
            details_json={}
        )

        exception = ConnectionError("Service temporarily unavailable")

        # First retry - use real implementation
        retried = retry_job(job, JobType.DQ_RUN, exception)
        self.assertTrue(retried)
        job.refresh_from_db()
        self.assertEqual(job.details_json.get('retry_count'), 1)

        # Second retry - reset status and retry again
        job.status = JobStatus.RUNNING
        job.save()
        retried = retry_job(job, JobType.DQ_RUN, exception)
        self.assertTrue(retried)
        job.refresh_from_db()
        self.assertEqual(job.details_json.get('retry_count'), 2)

    def test_retry_job_stores_retry_metadata(self):
        """Test that retry_job stores retry metadata in details_json"""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.RUNNING,
            resource_type='DATASET',
            resource_id='123e4567-e89b-12d3-a456-426614174000',
            created_by=self.user,
            details_json={}
        )

        exception = ConnectionError("Service temporarily unavailable")

        # Use real retry_job implementation
        retried = retry_job(job, JobType.DQ_RUN, exception)
        self.assertTrue(retried)

        job.refresh_from_db()
        self.assertIn('retry_count', job.details_json)
        self.assertIn('last_retry_error', job.details_json)
        self.assertIn('last_retry_at', job.details_json)
        self.assertEqual(job.details_json.get('retry_count'), 1)
        self.assertIsNotNone(job.details_json.get('last_retry_error'))
        self.assertIsNotNone(job.details_json.get('last_retry_at'))

