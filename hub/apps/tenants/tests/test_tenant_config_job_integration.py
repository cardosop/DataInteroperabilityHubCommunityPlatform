"""
Integration tests for TenantConfig with Job Orchestration.

GAP-1.2.4: Tests for job orchestration integration with tenant configuration.
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock
from django.core.cache import cache

from hub.apps.tenants.models import Tenant, TenantConfig
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.services import get_tenant_job_limits
from hub.apps.jobs.utils import (
    create_job,
    check_tenant_job_limits,
    increment_tenant_job_counter,
    decrement_tenant_job_counter
)
from hub.apps.tenants.validators import get_platform_defaults


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class TenantConfigJobIntegrationTest(TestCase):
    """Test Job Orchestration integration with tenant configuration"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        
        self.platform_defaults = get_platform_defaults()
        
        # Clear Redis cache
        cache.clear()
    
    def tearDown(self):
        """Clean up after tests"""
        cache.clear()
    
    def test_job_creation_within_tenant_concurrency_limit(self):
        """Test job creation succeeds when within tenant concurrency limit"""
        # Create tenant config with custom limits
        TenantConfig.objects.create(
            tenant=self.tenant,
            max_job_concurrency=3,
            max_queued_jobs=10
        )
        
        self.client.force_authenticate(user=self.user)
        
        # Use real Redis queue (clear it first)
        from django_rq import get_queue
        queue = get_queue('job_critical')
        queue.empty()
        
        # Create job (should succeed)
        # URL pattern: /api/v1/jobs/ includes router that registers "jobs", so full path is /api/v1/jobs/jobs/
        response = self.client.post("/api/v1/jobs/jobs/", {
            "type": JobType.DQ_RUN,
            "resource_type": "DATASET",
            "resource_id": "123e4567-e89b-12d3-a456-426614174000"
        }, format="json")
        
        # Should succeed
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify job was actually enqueued to Redis
        self.assertEqual(queue.count, 1)
    
    def test_job_creation_exceeding_concurrency_limit(self):
        """Test job creation fails when tenant concurrency limit exceeded"""
        # Create tenant config with low concurrency limit
        TenantConfig.objects.create(
            tenant=self.tenant,
            max_job_concurrency=2,
            max_queued_jobs=10
        )
        
        # Set running jobs to limit (simulate existing running jobs)
        running_key = f"job:tenant:{self.tenant.id}:running"
        cache.set(running_key, 2, timeout=86400)
        
        self.client.force_authenticate(user=self.user)
        
        # Try to create job (should fail - concurrency limit exceeded)
        response = self.client.post("/api/v1/jobs/jobs/", {
            "type": JobType.DQ_RUN,
            "resource_type": "DATASET",
            "resource_id": "123e4567-e89b-12d3-a456-426614174000"
        }, format="json")
        
        # Should return 429 Too Many Requests
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn("error", response.data)
        self.assertEqual(response.data["error"]["code"], "JOB_RATE_LIMITED")
        self.assertIn("concurrent job limit", str(response.data["error"]["message"]))
    
    def test_job_creation_exceeding_queued_jobs_limit(self):
        """Test job creation fails when tenant queued jobs limit exceeded"""
        # Create tenant config with low queue depth limit
        TenantConfig.objects.create(
            tenant=self.tenant,
            max_job_concurrency=5,
            max_queued_jobs=3
        )
        
        # Set queued jobs to limit (simulate existing queued jobs)
        queued_key = f"job:tenant:{self.tenant.id}:queued"
        cache.set(queued_key, 3, timeout=86400)
        
        self.client.force_authenticate(user=self.user)
        
        # Try to create job (should fail - queue depth limit exceeded)
        response = self.client.post("/api/v1/jobs/jobs/", {
            "type": JobType.DQ_RUN,
            "resource_type": "DATASET",
            "resource_id": "123e4567-e89b-12d3-a456-426614174000"
        }, format="json")
        
        # Should return 429 Too Many Requests
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn("error", response.data)
        self.assertEqual(response.data["error"]["code"], "JOB_RATE_LIMITED")
        self.assertIn("queued job limit", str(response.data["error"]["message"]))
    
    def test_job_creation_with_platform_defaults(self):
        """Test job creation uses platform defaults when tenant config not set"""
        # No tenant config exists
        
        self.client.force_authenticate(user=self.user)
        
        # Use real Redis queue (clear it first)
        from django_rq import get_queue
        queue = get_queue('job_critical')
        queue.empty()
        
        # Create job (should succeed with platform defaults)
        response = self.client.post("/api/v1/jobs/jobs/", {
            "type": JobType.DQ_RUN,
            "resource_type": "DATASET",
            "resource_id": "123e4567-e89b-12d3-a456-426614174000"
        }, format="json")
        
        # Should succeed
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify job was actually enqueued to Redis
        self.assertEqual(queue.count, 1)
    
    def test_job_counters_increment_decrement(self):
        """Test job counters increment/decrement correctly"""
        # Test queued counter increment
        increment_tenant_job_counter(str(self.tenant.id), "queued")
        queued_key = f"job:tenant:{self.tenant.id}:queued"
        self.assertEqual(cache.get(queued_key), 1)
        
        # Test running counter increment
        increment_tenant_job_counter(str(self.tenant.id), "running")
        running_key = f"job:tenant:{self.tenant.id}:running"
        self.assertEqual(cache.get(running_key), 1)
        
        # Test queued counter decrement (when job starts)
        decrement_tenant_job_counter(str(self.tenant.id), "queued")
        self.assertEqual(cache.get(queued_key), 0)
        
        # Test running counter decrement (when job completes)
        decrement_tenant_job_counter(str(self.tenant.id), "running")
        self.assertEqual(cache.get(running_key), 0)
    
    def test_check_tenant_job_limits_utility_function(self):
        """Test check_tenant_job_limits utility function"""
        # Test with tenant config
        TenantConfig.objects.create(
            tenant=self.tenant,
            max_job_concurrency=3,
            max_queued_jobs=10
        )
        
        # Test within limits
        can_create, error = check_tenant_job_limits(str(self.tenant.id))
        self.assertTrue(can_create)
        self.assertIsNone(error)
        
        # Test exceeding concurrency limit
        running_key = f"job:tenant:{self.tenant.id}:running"
        cache.set(running_key, 3, timeout=86400)  # At limit
        
        can_create, error = check_tenant_job_limits(str(self.tenant.id))
        self.assertFalse(can_create)
        self.assertIn("concurrent job limit", error)
        
        # Reset
        cache.delete(running_key)
        
        # Test exceeding queued limit
        queued_key = f"job:tenant:{self.tenant.id}:queued"
        cache.set(queued_key, 10, timeout=86400)  # At limit
        
        can_create, error = check_tenant_job_limits(str(self.tenant.id))
        self.assertFalse(can_create)
        self.assertIn("queued job limit", error)
    
    def test_get_tenant_job_limits_utility_function(self):
        """Test get_tenant_job_limits utility function"""
        # Test with tenant config
        TenantConfig.objects.create(
            tenant=self.tenant,
            max_job_concurrency=10,
            max_queued_jobs=100
        )
        
        limits = get_tenant_job_limits(str(self.tenant.id))
        self.assertEqual(limits["max_job_concurrency"], 10)
        self.assertEqual(limits["max_queued_jobs"], 100)
        
        # Test without tenant config (platform defaults)
        tenant2 = Tenant.objects.create(name="Test Tenant 2", slug="test-tenant-2")
        limits = get_tenant_job_limits(str(tenant2.id))
        self.assertEqual(limits["max_job_concurrency"], self.platform_defaults["max_job_concurrency"])
        self.assertEqual(limits["max_queued_jobs"], self.platform_defaults["max_queued_jobs"])
    
    def test_job_slot_release_on_completion(self):
        """Test tenant concurrency slot is released when job completes"""
        # Create tenant config
        TenantConfig.objects.create(
            tenant=self.tenant,
            max_job_concurrency=2,
            max_queued_jobs=10
        )
        
        # Simulate job running (increment running counter)
        increment_tenant_job_counter(str(self.tenant.id), "running")
        running_key = f"job:tenant:{self.tenant.id}:running"
        self.assertEqual(cache.get(running_key), 1)
        
        # Use real Redis queue (clear it first)
        from django_rq import get_queue
        queue = get_queue('job_critical')
        queue.empty()
        
        # Create job (should succeed - 1 running, limit is 2)
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.DQ_RUN,
            resource_type="DATASET",
            resource_id="123e4567-e89b-12d3-a456-426614174000"
        )
        
        # Verify job was created
        self.assertIsNotNone(job)
        # Verify job was actually enqueued to Redis
        self.assertEqual(queue.count, 1)
        
        # Simulate job completion (decrement running counter)
        decrement_tenant_job_counter(str(self.tenant.id), "running")
        self.assertEqual(cache.get(running_key), 0)
        
        # Now should be able to create another job
        job2 = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.COMPLIANCE_RUN,
            resource_type="DATASET",
            resource_id="223e4567-e89b-12d3-a456-426614174000"
        )
        
        # Should succeed
        self.assertIsNotNone(job2)

