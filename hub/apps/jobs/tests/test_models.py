"""
Unit tests for Job model.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from hub.apps.tenants.models import Tenant
from hub.apps.jobs.models import Job, JobType, JobStatus

User = get_user_model()


class JobModelTest(TestCase):
    """Test Job model"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )
    
    def test_create_job(self):
        """Test job creation"""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="ASSET",
            resource_id="123e4567-e89b-12d3-a456-426614174000",
            created_by=self.user
        )
        
        self.assertEqual(job.tenant, self.tenant)
        self.assertEqual(job.type, JobType.DQ_RUN)
        self.assertEqual(job.status, JobStatus.PENDING)
    
    def test_is_terminal(self):
        """Test is_terminal method"""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="ASSET",
            resource_id="123e4567-e89b-12d3-a456-426614174000",
        )
        
        self.assertFalse(job.is_terminal())
        
        job.status = JobStatus.COMPLETED
        job.save()
        self.assertTrue(job.is_terminal())
    
    def test_can_cancel(self):
        """Test can_cancel method"""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="ASSET",
            resource_id="123e4567-e89b-12d3-a456-426614174000",
        )
        
        self.assertTrue(job.can_cancel())
        
        job.status = JobStatus.COMPLETED
        job.save()
        self.assertFalse(job.can_cancel())

