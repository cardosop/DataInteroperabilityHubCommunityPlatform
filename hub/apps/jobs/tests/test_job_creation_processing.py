"""
Unit tests for job creation and processing.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock
import uuid

from hub.apps.jobs.models import Job, JobType, JobStatus, JobPriority
from hub.apps.jobs.utils import create_job, get_job_timeout, get_queue_for_job_type
from hub.apps.users.models import UserStatus
from hub.apps.tenants.models import Tenant


User = get_user_model()


class JobCreationProcessingTest(TestCase):
    """Test job creation and processing"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )

        # Create user
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

    def test_get_job_timeout(self):
        """Test getting timeout for different job types"""
        self.assertEqual(get_job_timeout(JobType.DQ_RUN), 1800)
        self.assertEqual(get_job_timeout(JobType.COMPLIANCE_RUN), 1800)
        self.assertEqual(get_job_timeout(JobType.CONTRACT_VALIDATION), 300)
        self.assertEqual(get_job_timeout(JobType.SEMANTIC_MAPPING), 60)
        self.assertEqual(get_job_timeout(JobType.CONTRACT_MIGRATION), 600)
        self.assertEqual(get_job_timeout("UNKNOWN_TYPE"), 600)  # Default

    def test_get_queue_for_job_type(self):
        """Test queue selection for different job types"""
        # HIGH priority jobs go to job_critical queue
        self.assertEqual(get_queue_for_job_type(JobType.DQ_RUN), 'job_critical')
        self.assertEqual(get_queue_for_job_type(JobType.COMPLIANCE_RUN), 'job_critical')
        # LOW priority jobs go to job_low queue
        self.assertEqual(get_queue_for_job_type(JobType.CONTRACT_VALIDATION), 'job_low')
        # NORMAL priority jobs go to job_default queue
        self.assertEqual(get_queue_for_job_type(JobType.SEMANTIC_MAPPING), 'job_default')
        self.assertEqual(get_queue_for_job_type(JobType.CONTRACT_MIGRATION), 'job_default')

    def test_create_job(self):
        """Test job creation with real Redis queue"""
        from django_rq import get_queue

        resource_id = uuid.uuid4()

        # Clear queue before test
        queue = get_queue('job_critical')
        queue.empty()

        job = create_job(
            job_type=JobType.DQ_RUN,
            resource_type="DATASET",
            resource_id=str(resource_id),
            tenant=self.tenant,
            user=self.user
        )

        self.assertIsNotNone(job.id)
        self.assertEqual(job.type, JobType.DQ_RUN)
        self.assertEqual(job.status, JobStatus.PENDING)
        self.assertEqual(job.resource_type, "DATASET")
        self.assertEqual(str(job.resource_id), str(resource_id))
        self.assertEqual(job.tenant, self.tenant)
        self.assertEqual(job.created_by, self.user)
        self.assertEqual(job.timeout_seconds, 1800)

        # Verify job was actually enqueued to Redis
        queue = get_queue('job_critical')
        self.assertEqual(queue.count, 1)

        # Verify job details in queue
        rq_job = queue.jobs[0]
        self.assertEqual(rq_job.args[0], str(job.id))
        self.assertEqual(rq_job.kwargs['job_type'], JobType.DQ_RUN)

    def test_create_job_api(self):
        """Test job creation via API with real Redis queue"""
        from django_rq import get_queue

        self.client.force_authenticate(user=self.user)

        resource_id = uuid.uuid4()

        data = {
            "type": JobType.DQ_RUN,
            "resource_type": "DATASET",
            "resource_id": str(resource_id),
            "details_json": {"test": "data"}
        }

        # Clear queue before test
        queue = get_queue('job_critical')
        queue.empty()

        response = self.client.post("/api/v1/jobs/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertEqual(response.data["type"], JobType.DQ_RUN)
        self.assertEqual(response.data["status"], JobStatus.PENDING)

        # Verify job was created
        job_id = response.data["id"]
        job = Job.objects.get(id=job_id)
        self.assertEqual(job.resource_id, resource_id)

        # Verify job was actually enqueued to Redis
        queue = get_queue('job_critical')
        self.assertEqual(queue.count, 1)

        # Verify job details in queue
        rq_job = queue.jobs[0]
        self.assertEqual(rq_job.args[0], str(job_id))
        self.assertEqual(rq_job.kwargs['job_type'], JobType.DQ_RUN)

    def test_job_mark_started(self):
        """Test marking job as started"""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user
        )

        job.mark_started()

        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.RUNNING)
        self.assertIsNotNone(job.started_at)

    def test_job_mark_completed(self):
        """Test marking job as completed"""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.RUNNING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user
        )

        result = {"status": "success", "rows_processed": 1000}
        job.mark_completed(result_json=result)

        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.COMPLETED)
        self.assertIsNotNone(job.completed_at)
        self.assertEqual(job.result_json, result)

    def test_job_mark_failed(self):
        """Test marking job as failed"""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.RUNNING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user
        )

        error_message = "Processing failed"
        job.mark_failed(error_message=error_message)

        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.FAILED)
        self.assertIsNotNone(job.completed_at)
        self.assertEqual(job.error_message, error_message)

    def test_job_is_terminal(self):
        """Test job terminal state check"""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.COMPLETED,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user
        )

        self.assertTrue(job.is_terminal())

        job.status = JobStatus.FAILED
        self.assertTrue(job.is_terminal())

        job.status = JobStatus.CANCELLED
        self.assertTrue(job.is_terminal())

        job.status = JobStatus.PENDING
        self.assertFalse(job.is_terminal())

    def test_job_can_cancel(self):
        """Test job cancellation check"""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user
        )

        self.assertTrue(job.can_cancel())

        job.status = JobStatus.RUNNING
        self.assertTrue(job.can_cancel())

        job.status = JobStatus.COMPLETED
        self.assertFalse(job.can_cancel())

    def test_list_jobs_tenant_scoped(self):
        """Test that users can only see jobs in their tenant"""
        self.client.force_authenticate(user=self.user)

        # Create another tenant and job
        other_tenant = Tenant.objects.create(
            name="Other Tenant",
            slug="other-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        other_job = Job.objects.create(
            tenant=other_tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4()
        )

        # Create job in user's tenant
        my_job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user
        )

        response = self.client.get("/api/v1/jobs/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        job_ids = [j["id"] for j in response.data["results"]]

        # Should only see jobs in own tenant
        self.assertIn(str(my_job.id), job_ids)
        self.assertNotIn(str(other_job.id), job_ids)

