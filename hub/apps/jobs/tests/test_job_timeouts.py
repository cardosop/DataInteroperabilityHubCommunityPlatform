"""
Unit tests for job timeout handling.
"""
import pytest
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
import uuid

from hub.apps.jobs.models import Job, JobType, JobStatus
from hub.apps.jobs.tasks import check_job_timeouts
from hub.apps.users.models import UserStatus
from hub.apps.tenants.models import Tenant
from django.contrib.auth import get_user_model


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class JobTimeoutTest(TestCase):
    """Test job timeout handling"""
    
    def setUp(self):
        """Set up test fixtures"""
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
    
    def test_check_job_timeouts_no_timeout(self):
        """Test that jobs without timeout are not affected"""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.RUNNING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user,
            started_at=timezone.now() - timedelta(minutes=10),
            timeout_seconds=None  # No timeout
        )
        
        check_job_timeouts()
        
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.RUNNING)  # Status unchanged
    
    def test_check_job_timeouts_within_timeout(self):
        """Test that jobs within timeout are not affected"""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.RUNNING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user,
            started_at=timezone.now() - timedelta(minutes=5),
            timeout_seconds=1800  # 30 minutes
        )
        
        check_job_timeouts()
        
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.RUNNING)  # Status unchanged
    
    def test_check_job_timeouts_exceeded(self):
        """Test that jobs exceeding timeout are marked as failed"""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.RUNNING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user,
            started_at=timezone.now() - timedelta(minutes=35),  # Exceeds 30 min timeout
            timeout_seconds=1800  # 30 minutes
        )
        
        check_job_timeouts()
        
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.FAILED)
        self.assertIn("exceeded timeout", job.error_message)
        self.assertIsNotNone(job.completed_at)
        self.assertIn("timeout", job.result_json)
    
    def test_check_job_timeouts_pending_jobs_not_affected(self):
        """Test that pending jobs are not affected by timeout check"""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user,
            timeout_seconds=1800
        )
        
        check_job_timeouts()
        
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.PENDING)  # Status unchanged
    
    def test_check_job_timeouts_completed_jobs_not_affected(self):
        """Test that completed jobs are not affected by timeout check"""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.COMPLETED,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user,
            started_at=timezone.now() - timedelta(minutes=35),
            timeout_seconds=1800
        )
        
        check_job_timeouts()
        
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.COMPLETED)  # Status unchanged
    
    def test_job_timeout_during_processing(self):
        """Test that job timeout is checked during processing"""
        # This test verifies that the timeout check in process_job works
        # The actual timeout check happens in the task, but we can test the logic
        
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user,
            timeout_seconds=60  # 1 minute
        )
        
        # Simulate job starting in the past
        job.mark_started()
        job.started_at = timezone.now() - timedelta(minutes=2)  # Started 2 minutes ago
        job.save()
        
        # Check timeout
        check_job_timeouts()
        
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.FAILED)

