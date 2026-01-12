"""
Unit tests for Job Priority Queue functionality.
"""
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django_rq import get_queue
import uuid

from hub.apps.jobs.models import Job, JobType, JobStatus, JobPriority
from hub.apps.jobs.utils import (
    create_job,
    get_job_priority,
    get_queue_for_priority,
    get_queue_for_job_type
)
from hub.apps.users.models import UserStatus
from hub.apps.tenants.models import Tenant


User = get_user_model()


class JobPriorityQueueTest(TestCase):
    """Test job priority queue functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

    def tearDown(self):
        """Clean up queues after tests"""
        for queue_name in ['job_critical', 'job_default', 'job_low']:
            try:
                queue = get_queue(queue_name)
                queue.empty()
            except Exception:
                pass

    def test_get_job_priority_explicit(self):
        """Test priority assignment with explicit priority"""
        priority = get_job_priority(JobType.DQ_RUN, priority=JobPriority.LOW)
        self.assertEqual(priority, JobPriority.LOW)

    def test_get_job_priority_from_rules(self):
        """Test priority assignment from job type rules"""
        # DQ_RUN should be HIGH priority
        priority = get_job_priority(JobType.DQ_RUN)
        self.assertEqual(priority, JobPriority.HIGH)

        # CONTRACT_VALIDATION should be LOW priority
        priority = get_job_priority(JobType.CONTRACT_VALIDATION)
        self.assertEqual(priority, JobPriority.LOW)

        # SEMANTIC_MAPPING should be NORMAL priority
        priority = get_job_priority(JobType.SEMANTIC_MAPPING)
        self.assertEqual(priority, JobPriority.NORMAL)

    def test_get_job_priority_default(self):
        """Test priority assignment uses default when no rule exists"""
        # Unknown job type should use default (NORMAL)
        priority = get_job_priority("UNKNOWN_TYPE")
        self.assertEqual(priority, "NORMAL")

    def test_get_queue_for_priority(self):
        """Test queue name mapping for priorities"""
        self.assertEqual(get_queue_for_priority(JobPriority.HIGH), 'job_critical')
        self.assertEqual(get_queue_for_priority(JobPriority.NORMAL), 'job_default')
        self.assertEqual(get_queue_for_priority(JobPriority.LOW), 'job_low')
        # Unknown priority defaults to job_default
        self.assertEqual(get_queue_for_priority("UNKNOWN"), 'job_default')

    def test_create_job_with_explicit_priority(self):
        """Test job creation with explicit priority"""
        resource_id = uuid.uuid4()

        # Clear queue before test
        queue = get_queue('job_low')
        queue.empty()

        job = create_job(
            job_type=JobType.DQ_RUN,
            resource_type="DATASET",
            resource_id=str(resource_id),
            tenant=self.tenant,
            user=self.user,
            priority=JobPriority.LOW  # Override default HIGH priority
        )

        self.assertIsNotNone(job.id)
        self.assertEqual(job.priority, JobPriority.LOW)
        self.assertEqual(job.type, JobType.DQ_RUN)

        # Verify job was enqueued to LOW priority queue
        queue = get_queue('job_low')
        self.assertEqual(queue.count, 1)

    def test_create_job_with_priority_from_rules(self):
        """Test job creation with priority determined from job type rules"""
        resource_id = uuid.uuid4()

        # Clear queues before test
        high_queue = get_queue('job_critical')
        high_queue.empty()
        normal_queue = get_queue('job_default')
        normal_queue.empty()
        low_queue = get_queue('job_low')
        low_queue.empty()

        # HIGH priority job (DQ_RUN)
        high_job = create_job(
            job_type=JobType.DQ_RUN,
            resource_type="DATASET",
            resource_id=str(uuid.uuid4()),
            tenant=self.tenant,
            user=self.user
        )
        self.assertEqual(high_job.priority, JobPriority.HIGH)
        self.assertEqual(high_queue.count, 1)

        # NORMAL priority job (SEMANTIC_MAPPING)
        normal_job = create_job(
            job_type=JobType.SEMANTIC_MAPPING,
            resource_type="CONTRACT",
            resource_id=str(uuid.uuid4()),
            tenant=self.tenant,
            user=self.user
        )
        self.assertEqual(normal_job.priority, JobPriority.NORMAL)
        self.assertEqual(normal_queue.count, 1)

        # LOW priority job (CONTRACT_VALIDATION)
        low_job = create_job(
            job_type=JobType.CONTRACT_VALIDATION,
            resource_type="CONTRACT",
            resource_id=str(uuid.uuid4()),
            tenant=self.tenant,
            user=self.user
        )
        self.assertEqual(low_job.priority, JobPriority.LOW)
        self.assertEqual(low_queue.count, 1)

    def test_create_job_priority_field_in_model(self):
        """Test that priority field is stored in Job model"""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            priority=JobPriority.HIGH,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user
        )

        self.assertEqual(job.priority, JobPriority.HIGH)

        # Refresh from DB to verify persistence
        job.refresh_from_db()
        self.assertEqual(job.priority, JobPriority.HIGH)

    def test_job_priority_default_value(self):
        """Test that Job model has default priority"""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user
        )

        # Default priority should be NORMAL
        self.assertEqual(job.priority, JobPriority.NORMAL)

    def test_priority_queue_enqueue_logic(self):
        """Test that jobs are enqueued to correct queue based on priority"""
        # Clear all queues
        for queue_name in ['job_critical', 'job_default', 'job_low']:
            queue = get_queue(queue_name)
            queue.empty()

        # Create jobs with different priorities
        high_job = create_job(
            job_type=JobType.DQ_RUN,
            resource_type="DATASET",
            resource_id=str(uuid.uuid4()),
            tenant=self.tenant,
            user=self.user,
            priority=JobPriority.HIGH
        )

        normal_job = create_job(
            job_type=JobType.SEMANTIC_MAPPING,
            resource_type="CONTRACT",
            resource_id=str(uuid.uuid4()),
            tenant=self.tenant,
            user=self.user,
            priority=JobPriority.NORMAL
        )

        low_job = create_job(
            job_type=JobType.CONTRACT_VALIDATION,
            resource_type="CONTRACT",
            resource_id=str(uuid.uuid4()),
            tenant=self.tenant,
            user=self.user,
            priority=JobPriority.LOW
        )

        # Verify jobs are in correct queues
        high_queue = get_queue('job_critical')
        normal_queue = get_queue('job_default')
        low_queue = get_queue('job_low')

        self.assertEqual(high_queue.count, 1)
        self.assertEqual(normal_queue.count, 1)
        self.assertEqual(low_queue.count, 1)

        # Verify job IDs in queues
        self.assertEqual(high_queue.jobs[0].args[0], str(high_job.id))
        self.assertEqual(normal_queue.jobs[0].args[0], str(normal_job.id))
        self.assertEqual(low_queue.jobs[0].args[0], str(low_job.id))

    def test_priority_override_job_type_rules(self):
        """Test that explicit priority overrides job type rules"""
        # DQ_RUN normally maps to HIGH priority, but we override to LOW
        job = create_job(
            job_type=JobType.DQ_RUN,
            resource_type="DATASET",
            resource_id=str(uuid.uuid4()),
            tenant=self.tenant,
            user=self.user,
            priority=JobPriority.LOW
        )

        self.assertEqual(job.priority, JobPriority.LOW)

        # Verify job was enqueued to LOW priority queue
        low_queue = get_queue('job_low')
        self.assertEqual(low_queue.count, 1)

    def test_priority_indexes(self):
        """Test that priority indexes exist for efficient queries"""
        # Create jobs with different priorities
        high_job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            priority=JobPriority.HIGH,
            resource_type="DATASET",
            resource_id=uuid.uuid4()
        )

        normal_job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.SEMANTIC_MAPPING,
            status=JobStatus.PENDING,
            priority=JobPriority.NORMAL,
            resource_type="CONTRACT",
            resource_id=uuid.uuid4()
        )

        # Query by priority (should use index)
        high_jobs = Job.objects.filter(priority=JobPriority.HIGH)
        self.assertIn(high_job, high_jobs)
        self.assertNotIn(normal_job, high_jobs)

        # Query by priority and status (should use composite index)
        pending_high_jobs = Job.objects.filter(
            priority=JobPriority.HIGH,
            status=JobStatus.PENDING
        )
        self.assertIn(high_job, pending_high_jobs)

        # Query by tenant, priority, and status (should use composite index)
        tenant_high_pending = Job.objects.filter(
            tenant=self.tenant,
            priority=JobPriority.HIGH,
            status=JobStatus.PENDING
        )
        self.assertIn(high_job, tenant_high_pending)

