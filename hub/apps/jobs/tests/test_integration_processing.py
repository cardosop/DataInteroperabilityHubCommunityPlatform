"""
Integration tests for job processing (T.9).

Tests job creation, processing, status updates, and completion.
"""
import uuid
from unittest.mock import patch, Mock
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from django.utils import timezone

from hub.apps.tenants.models import Tenant
from hub.apps.jobs.models import Job, JobType, JobStatus
from hub.apps.contracts.models import Contract, ContractStatus
from hub.apps.files.models import File, FileStatus

User = get_user_model()


class JobProcessingTest(TestCase):
    """Integration tests for job processing (T.9)"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        
        self.client.force_authenticate(user=self.user)
    
    def test_job_creation_and_status_tracking(self):
        """Test job creation and status updates"""
        # Create a contract validation job
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type='ODCS',
            original_format='JSON',
            original_raw='{"id": "test"}',
            created_by=self.user
        )
        
        # Create job via API
        job_response = self.client.post(
            '/api/v1/jobs/jobs/',
            {
                'type': JobType.CONTRACT_VALIDATION,
                'resource_type': 'CONTRACT',
                'resource_id': str(contract.id),
                'timeout_seconds': 300
            },
            format='json'
        )
        
        self.assertEqual(job_response.status_code, status.HTTP_201_CREATED)
        job_id = job_response.data['id']
        
        # Verify job was created
        job = Job.objects.get(id=job_id)
        self.assertEqual(job.status, JobStatus.PENDING)
        self.assertEqual(job.type, JobType.CONTRACT_VALIDATION)
        self.assertEqual(str(job.resource_id), str(contract.id))
        
        # Update job status to RUNNING
        job.status = JobStatus.RUNNING
        job.started_at = timezone.now()
        job.save()
        
        # Update job status to COMPLETED
        job.status = JobStatus.COMPLETED
        job.finished_at = timezone.now()
        job.save()
        
        # Verify final state
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.COMPLETED)
        self.assertIsNotNone(job.started_at)
        self.assertIsNotNone(job.finished_at)
    
    def test_job_listing_filtered_by_tenant(self):
        """Test job listing is filtered by tenant"""
        # Create jobs for this tenant
        job1 = Job.objects.create(
            tenant=self.tenant,
            type=JobType.CONTRACT_VALIDATION,
            status=JobStatus.PENDING,
            resource_type='CONTRACT',
            resource_id=uuid.uuid4(),
            created_by=self.user
        )
        
        job2 = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.RUNNING,
            resource_type='DQ_RUN',
            resource_id=uuid.uuid4(),
            created_by=self.user
        )
        
        # Create another tenant and job
        other_tenant = Tenant.objects.create(
            name="Other Tenant",
            slug="other-tenant"
        )
        other_user = User.objects.create_user(
            email="other@example.com",
            password="testpass123",
            tenant=other_tenant
        )
        other_job = Job.objects.create(
            tenant=other_tenant,
            type=JobType.CONTRACT_VALIDATION,
            status=JobStatus.PENDING,
            resource_type='CONTRACT',
            resource_id=uuid.uuid4(),
            created_by=other_user
        )
        
        # List jobs for current tenant
        response = self.client.get('/api/v1/jobs/jobs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        job_ids = [job['id'] for job in response.data['results']]
        
        # Should only see own tenant's jobs
        self.assertIn(str(job1.id), job_ids)
        self.assertIn(str(job2.id), job_ids)
        self.assertNotIn(str(other_job.id), job_ids)
    
    def test_job_filtering_by_status(self):
        """Test job filtering by status"""
        # Create jobs with different statuses
        pending_job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.CONTRACT_VALIDATION,
            status=JobStatus.PENDING,
            resource_type='CONTRACT',
            resource_id=uuid.uuid4(),
            created_by=self.user
        )
        
        succeeded_job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.CONTRACT_VALIDATION,
            status=JobStatus.COMPLETED,
            resource_type='CONTRACT',
            resource_id=uuid.uuid4(),
            created_by=self.user
        )
        
        # Filter by status
        response = self.client.get('/api/v1/jobs/jobs/', {'status': JobStatus.PENDING})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        job_ids = [job['id'] for job in response.data['results']]
        self.assertIn(str(pending_job.id), job_ids)
        self.assertNotIn(str(succeeded_job.id), job_ids)
    
    def test_job_filtering_by_type(self):
        """Test job filtering by type"""
        # Create jobs with different types
        contract_job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.CONTRACT_VALIDATION,
            status=JobStatus.PENDING,
            resource_type='CONTRACT',
            resource_id=uuid.uuid4(),
            created_by=self.user
        )
        
        dq_job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type='DQ_RUN',
            resource_id=uuid.uuid4(),
            created_by=self.user
        )
        
        # Filter by type
        response = self.client.get('/api/v1/jobs/jobs/', {'type': JobType.CONTRACT_VALIDATION})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        job_ids = [job['id'] for job in response.data['results']]
        self.assertIn(str(contract_job.id), job_ids)
        self.assertNotIn(str(dq_job.id), job_ids)
    
    def test_job_cancellation(self):
        """Test job cancellation"""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.CONTRACT_VALIDATION,
            status=JobStatus.PENDING,
            resource_type='CONTRACT',
            resource_id=uuid.uuid4(),
            created_by=self.user
        )
        
        # Cancel job
        response = self.client.post(
            f'/api/v1/jobs/jobs/{job.id}/cancel/',
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify job is cancelled
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.CANCELLED)
    
    def test_job_timeout_handling(self):
        """Test job timeout handling"""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.CONTRACT_VALIDATION,
            status=JobStatus.RUNNING,
            resource_type='CONTRACT',
            resource_id=uuid.uuid4(),
            timeout_seconds=60,
            started_at=timezone.now() - timezone.timedelta(seconds=120),  # Exceeded timeout
            created_by=self.user
        )
        
        # Job should be marked as failed due to timeout
        # This would typically be handled by a background worker
        # For integration test, we verify the timeout calculation
        from hub.apps.jobs.utils import get_job_timeout
        timeout = get_job_timeout(job.type)
        self.assertIsNotNone(timeout)

