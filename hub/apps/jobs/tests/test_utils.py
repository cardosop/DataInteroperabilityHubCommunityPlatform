"""
Unit tests for job utilities.
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from hub.apps.tenants.models import Tenant
from hub.apps.jobs.models import Job, JobType
from hub.apps.jobs.utils import (


    get_job_timeout,
    create_job,
    get_queue_for_job_type,
)


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class JobUtilsTest(TestCase):
    """Test job utilities"""
    
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
    
    def test_get_job_timeout(self):
        """Test get_job_timeout"""
        timeout = get_job_timeout(JobType.DQ_RUN)
        self.assertEqual(timeout, 1800)  # 30 minutes
        
        timeout = get_job_timeout(JobType.CONTRACT_VALIDATION)
        self.assertEqual(timeout, 300)  # 5 minutes
        
        # Default timeout for unknown type
        timeout = get_job_timeout("UNKNOWN_TYPE")
        self.assertEqual(timeout, 600)  # 10 minutes default
    
    def test_create_job(self):
        """Test create_job"""
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.DQ_RUN,
            resource_type="ASSET",
            resource_id="123e4567-e89b-12d3-a456-426614174000",
            details_json={"key": "value"}
        )
        
        self.assertEqual(job.tenant, self.tenant)
        self.assertEqual(job.type, JobType.DQ_RUN)
        self.assertEqual(job.resource_type, "ASSET")
        self.assertEqual(job.timeout_seconds, 1800)  # From get_job_timeout
    
    def test_get_queue_for_job_type(self):
        """Test get_queue_for_job_type"""
        # High priority queue for long-running jobs
        queue = get_queue_for_job_type(JobType.DQ_RUN)
        self.assertEqual(queue, "high")
        
        queue = get_queue_for_job_type(JobType.COMPLIANCE_RUN)
        self.assertEqual(queue, "high")
        
        # Low priority queue for quick jobs
        queue = get_queue_for_job_type(JobType.CONTRACT_VALIDATION)
        self.assertEqual(queue, "low")
        
        # Default queue for others
        queue = get_queue_for_job_type(JobType.SEMANTIC_MAPPING)
        self.assertEqual(queue, "default")

