"""
Unit tests for job cancellation.
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
import uuid

from hub.apps.jobs.models import Job, JobType, JobStatus
from hub.apps.users.models import UserStatus
from hub.apps.tenants.models import Tenant

from hub.apps.jobs.tests.billing_support import ensure_tenant_has_active_subscription


# Use default transaction=False so the test client and middleware share the same DB
# connection; with transaction=True the client can use a different connection and
# TenantSuspensionMiddleware does not see the subscription created in setUp (403).
pytestmark = pytest.mark.django_db
User = get_user_model()


class JobCancellationTest(TestCase):
    """Test job cancellation"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        ensure_tenant_has_active_subscription(self.tenant)
    
    def test_cancel_pending_job(self):
        """Test cancelling a pending job"""
        self.client.force_authenticate(user=self.user)
        
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user
        )
        
        response = self.client.post(f"/api/v1/jobs/{job.id}/cancel/")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], JobStatus.CANCELLED)
        
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.CANCELLED)
        self.assertIsNotNone(job.completed_at)
    
    def test_cancel_running_job(self):
        """Test cancelling a running job"""
        self.client.force_authenticate(user=self.user)
        
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.RUNNING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user
        )
        
        response = self.client.post(f"/api/v1/jobs/{job.id}/cancel/")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], JobStatus.CANCELLED)
        
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.CANCELLED)
    
    def test_cancel_completed_job_fails(self):
        """Test that cancelling a completed job fails"""
        self.client.force_authenticate(user=self.user)
        
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.COMPLETED,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user
        )
        
        response = self.client.post(f"/api/v1/jobs/{job.id}/cancel/")
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cannot be cancelled", response.data["error"])
        
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.COMPLETED)  # Status unchanged
    
    def test_cancel_failed_job_fails(self):
        """Test that cancelling a failed job fails"""
        self.client.force_authenticate(user=self.user)
        
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.FAILED,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user
        )
        
        response = self.client.post(f"/api/v1/jobs/{job.id}/cancel/")
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.FAILED)  # Status unchanged
    
    def test_cancel_cancelled_job_fails(self):
        """Test that cancelling an already cancelled job fails"""
        self.client.force_authenticate(user=self.user)
        
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.CANCELLED,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user
        )
        
        response = self.client.post(f"/api/v1/jobs/{job.id}/cancel/")
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.CANCELLED)  # Status unchanged
    
    def test_cancel_running_job_releases_tenant_slot(self):
        """Test that cancelling a running job releases tenant concurrency slot"""
        self.client.force_authenticate(user=self.user)
        
        from hub.apps.jobs.utils import increment_tenant_job_counter, get_tenant_job_counter
        
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.RUNNING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user
        )
        
        # Increment running counter to simulate job running
        increment_tenant_job_counter(str(self.tenant.id), "running")
        self.assertEqual(get_tenant_job_counter(str(self.tenant.id), "running"), 1)
        
        response = self.client.post(f"/api/v1/jobs/{job.id}/cancel/")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], JobStatus.CANCELLED)
        
        # Verify tenant slot was released
        self.assertEqual(get_tenant_job_counter(str(self.tenant.id), "running"), 0)
    
    def test_cancel_pending_job_does_not_release_slot(self):
        """Test that cancelling a pending job does not release tenant slot (wasn't running)"""
        self.client.force_authenticate(user=self.user)
        
        from hub.apps.jobs.utils import get_tenant_job_counter
        
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user
        )
        
        # No running counter should exist
        self.assertEqual(get_tenant_job_counter(str(self.tenant.id), "running"), 0)
        
        response = self.client.post(f"/api/v1/jobs/{job.id}/cancel/")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], JobStatus.CANCELLED)
        
        # Still no running counter (wasn't running)
        self.assertEqual(get_tenant_job_counter(str(self.tenant.id), "running"), 0)

