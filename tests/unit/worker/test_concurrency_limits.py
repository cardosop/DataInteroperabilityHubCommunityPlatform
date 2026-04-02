"""
Unit tests for Concurrency Limits functionality.

Tests per-tenant limits, slot release, and job counter management.
Uses real cache (no mocks).
"""
import pytest
from django.test import TestCase
from django.core.cache import cache
from django.utils import timezone

from hub.apps.jobs.models import Job, JobType, JobStatus
from hub.apps.jobs.utils import (
    check_tenant_job_limits,
    get_tenant_job_counter,
    increment_tenant_job_counter,
    decrement_tenant_job_counter,
    create_job,
)
from hub.apps.tenants.models import Tenant, TenantConfig
from hub.apps.users.models import User, UserStatus
from tests.factories import TenantFactory, TenantConfigFactory
import uuid

pytestmark = pytest.mark.django_db(transaction=True)


class ConcurrencyLimitsTest(TestCase):
    """Test concurrency limits functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        cache.clear()
        
        self.tenant = TenantFactory.create_tenant()
        self.tenant2 = TenantFactory.create_tenant(name="Tenant 2", slug="tenant-2")
        
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
    
    def tearDown(self):
        """Clean up after tests"""
        cache.clear()
    
    def test_get_tenant_job_counter_initial(self):
        """Test getting tenant job counter when initially zero"""
        counter = get_tenant_job_counter(str(self.tenant.id), "running")
        self.assertEqual(counter, 0)
        
        counter = get_tenant_job_counter(str(self.tenant.id), "queued")
        self.assertEqual(counter, 0)
    
    def test_increment_tenant_job_counter_running(self):
        """Test incrementing tenant running job counter"""
        # Initially zero
        self.assertEqual(get_tenant_job_counter(str(self.tenant.id), "running"), 0)
        
        # Increment
        increment_tenant_job_counter(str(self.tenant.id), "running")
        self.assertEqual(get_tenant_job_counter(str(self.tenant.id), "running"), 1)
        
        # Increment again
        increment_tenant_job_counter(str(self.tenant.id), "running")
        self.assertEqual(get_tenant_job_counter(str(self.tenant.id), "running"), 2)
    
    def test_increment_tenant_job_counter_queued(self):
        """Test incrementing tenant queued job counter"""
        # Initially zero
        self.assertEqual(get_tenant_job_counter(str(self.tenant.id), "queued"), 0)
        
        # Increment
        increment_tenant_job_counter(str(self.tenant.id), "queued")
        self.assertEqual(get_tenant_job_counter(str(self.tenant.id), "queued"), 1)
        
        # Increment again
        increment_tenant_job_counter(str(self.tenant.id), "queued")
        self.assertEqual(get_tenant_job_counter(str(self.tenant.id), "queued"), 2)
    
    def test_decrement_tenant_job_counter_running(self):
        """Test decrementing tenant running job counter"""
        # Set to 2
        increment_tenant_job_counter(str(self.tenant.id), "running")
        increment_tenant_job_counter(str(self.tenant.id), "running")
        self.assertEqual(get_tenant_job_counter(str(self.tenant.id), "running"), 2)
        
        # Decrement
        decrement_tenant_job_counter(str(self.tenant.id), "running")
        self.assertEqual(get_tenant_job_counter(str(self.tenant.id), "running"), 1)
        
        # Decrement to zero
        decrement_tenant_job_counter(str(self.tenant.id), "running")
        self.assertEqual(get_tenant_job_counter(str(self.tenant.id), "running"), 0)
        
        # Decrement below zero should not go negative
        decrement_tenant_job_counter(str(self.tenant.id), "running")
        self.assertEqual(get_tenant_job_counter(str(self.tenant.id), "running"), 0)
    
    def test_decrement_tenant_job_counter_queued(self):
        """Test decrementing tenant queued job counter"""
        # Set to 2
        increment_tenant_job_counter(str(self.tenant.id), "queued")
        increment_tenant_job_counter(str(self.tenant.id), "queued")
        self.assertEqual(get_tenant_job_counter(str(self.tenant.id), "queued"), 2)
        
        # Decrement
        decrement_tenant_job_counter(str(self.tenant.id), "queued")
        self.assertEqual(get_tenant_job_counter(str(self.tenant.id), "queued"), 1)
        
        # Decrement to zero
        decrement_tenant_job_counter(str(self.tenant.id), "queued")
        self.assertEqual(get_tenant_job_counter(str(self.tenant.id), "queued"), 0)
    
    def test_check_tenant_job_limits_within_concurrency_limit(self):
        """Test checking tenant job limits when within concurrency limit"""
        # Create tenant config with max_job_concurrency = 5
        TenantConfigFactory.create_tenant_config(
            tenant=self.tenant,
            max_job_concurrency=5,
            max_queued_jobs=10
        )
        
        # Set running jobs to 3 (below limit)
        for _ in range(3):
            increment_tenant_job_counter(str(self.tenant.id), "running")
        
        # Should be able to create job
        can_create, error_message = check_tenant_job_limits(str(self.tenant.id))
        self.assertTrue(can_create)
        self.assertIsNone(error_message)
    
    def test_check_tenant_job_limits_at_concurrency_limit(self):
        """Test checking tenant job limits when at concurrency limit"""
        # Create tenant config with max_job_concurrency = 2
        TenantConfigFactory.create_tenant_config(
            tenant=self.tenant,
            max_job_concurrency=2,
            max_queued_jobs=10
        )
        
        # Set running jobs to 2 (at limit)
        for _ in range(2):
            increment_tenant_job_counter(str(self.tenant.id), "running")
        
        # Should not be able to create job
        can_create, error_message = check_tenant_job_limits(str(self.tenant.id))
        self.assertFalse(can_create)
        self.assertIn("concurrent job limit", error_message)
        self.assertIn("2", error_message)
    
    def test_check_tenant_job_limits_exceeds_concurrency_limit(self):
        """Test checking tenant job limits when exceeds concurrency limit"""
        # Create tenant config with max_job_concurrency = 2
        TenantConfigFactory.create_tenant_config(
            tenant=self.tenant,
            max_job_concurrency=2,
            max_queued_jobs=10
        )
        
        # Set running jobs to 3 (above limit)
        for _ in range(3):
            increment_tenant_job_counter(str(self.tenant.id), "running")
        
        # Should not be able to create job
        can_create, error_message = check_tenant_job_limits(str(self.tenant.id))
        self.assertFalse(can_create)
        self.assertIn("concurrent job limit", error_message)
    
    def test_check_tenant_job_limits_within_queued_limit(self):
        """Test checking tenant job limits when within queued limit"""
        # Create tenant config with max_queued_jobs = 5
        TenantConfigFactory.create_tenant_config(
            tenant=self.tenant,
            max_job_concurrency=10,
            max_queued_jobs=5
        )
        
        # Set queued jobs to 3 (below limit)
        for _ in range(3):
            increment_tenant_job_counter(str(self.tenant.id), "queued")
        
        # Should be able to create job
        can_create, error_message = check_tenant_job_limits(str(self.tenant.id))
        self.assertTrue(can_create)
        self.assertIsNone(error_message)
    
    def test_check_tenant_job_limits_at_queued_limit(self):
        """Test checking tenant job limits when at queued limit"""
        # Create tenant config with max_queued_jobs = 3
        TenantConfigFactory.create_tenant_config(
            tenant=self.tenant,
            max_job_concurrency=10,
            max_queued_jobs=3
        )
        
        # Set queued jobs to 3 (at limit)
        for _ in range(3):
            increment_tenant_job_counter(str(self.tenant.id), "queued")
        
        # Should not be able to create job
        can_create, error_message = check_tenant_job_limits(str(self.tenant.id))
        self.assertFalse(can_create)
        self.assertIn("queued job limit", error_message)
        self.assertIn("3", error_message)
    
    def test_check_tenant_job_limits_exceeds_queued_limit(self):
        """Test checking tenant job limits when exceeds queued limit"""
        # Create tenant config with max_queued_jobs = 2
        TenantConfigFactory.create_tenant_config(
            tenant=self.tenant,
            max_job_concurrency=10,
            max_queued_jobs=2
        )
        
        # Set queued jobs to 3 (above limit)
        for _ in range(3):
            increment_tenant_job_counter(str(self.tenant.id), "queued")
        
        # Should not be able to create job
        can_create, error_message = check_tenant_job_limits(str(self.tenant.id))
        self.assertFalse(can_create)
        self.assertIn("queued job limit", error_message)
    
    def test_check_tenant_job_limits_both_limits(self):
        """Test checking tenant job limits when both limits are checked"""
        # Create tenant config
        TenantConfigFactory.create_tenant_config(
            tenant=self.tenant,
            max_job_concurrency=2,
            max_queued_jobs=3
        )
        
        # Set running jobs to 1, queued jobs to 1 (both below limits)
        increment_tenant_job_counter(str(self.tenant.id), "running")
        increment_tenant_job_counter(str(self.tenant.id), "queued")
        
        # Should be able to create job
        can_create, error_message = check_tenant_job_limits(str(self.tenant.id))
        self.assertTrue(can_create)
        self.assertIsNone(error_message)
        
        # Set running jobs to 2 (at limit), queued jobs to 1 (below limit)
        increment_tenant_job_counter(str(self.tenant.id), "running")
        decrement_tenant_job_counter(str(self.tenant.id), "queued")
        
        # Should not be able to create job (concurrency limit)
        can_create, error_message = check_tenant_job_limits(str(self.tenant.id))
        self.assertFalse(can_create)
        self.assertIn("concurrent job limit", error_message)
    
    def test_slot_release_on_job_completion(self):
        """Test slot release when job completes"""
        # Create tenant config with max_job_concurrency = 2
        TenantConfigFactory.create_tenant_config(
            tenant=self.tenant,
            max_job_concurrency=2,
            max_queued_jobs=10
        )
        
        # Fill all concurrency slots
        increment_tenant_job_counter(str(self.tenant.id), "running")
        increment_tenant_job_counter(str(self.tenant.id), "running")
        
        # Verify at limit
        can_create, _ = check_tenant_job_limits(str(self.tenant.id))
        self.assertFalse(can_create)
        
        # Complete one job (decrement running)
        decrement_tenant_job_counter(str(self.tenant.id), "running")
        
        # Should be able to create new job
        can_create, _ = check_tenant_job_limits(str(self.tenant.id))
        self.assertTrue(can_create)
    
    def test_slot_release_on_job_failure(self):
        """Test slot release when job fails"""
        # Create tenant config with max_job_concurrency = 2
        TenantConfigFactory.create_tenant_config(
            tenant=self.tenant,
            max_job_concurrency=2,
            max_queued_jobs=10
        )
        
        # Fill all concurrency slots
        increment_tenant_job_counter(str(self.tenant.id), "running")
        increment_tenant_job_counter(str(self.tenant.id), "running")
        
        # Verify at limit
        can_create, _ = check_tenant_job_limits(str(self.tenant.id))
        self.assertFalse(can_create)
        
        # Fail one job (decrement running)
        decrement_tenant_job_counter(str(self.tenant.id), "running")
        
        # Should be able to create new job
        can_create, _ = check_tenant_job_limits(str(self.tenant.id))
        self.assertTrue(can_create)
    
    def test_tenant_isolation(self):
        """Test that tenant job counters are isolated per tenant"""
        # Create tenant configs for both tenants
        TenantConfigFactory.create_tenant_config(
            tenant=self.tenant,
            max_job_concurrency=2,
            max_queued_jobs=5
        )
        TenantConfigFactory.create_tenant_config(
            tenant=self.tenant2,
            max_job_concurrency=3,
            max_queued_jobs=7
        )
        
        # Fill tenant1's concurrency slots
        increment_tenant_job_counter(str(self.tenant.id), "running")
        increment_tenant_job_counter(str(self.tenant.id), "running")
        
        # Tenant1 should be at limit
        can_create, _ = check_tenant_job_limits(str(self.tenant.id))
        self.assertFalse(can_create)
        
        # Tenant2 should still be able to create jobs
        can_create, _ = check_tenant_job_limits(str(self.tenant2.id))
        self.assertTrue(can_create)
        
        # Fill tenant2's concurrency slots
        increment_tenant_job_counter(str(self.tenant2.id), "running")
        increment_tenant_job_counter(str(self.tenant2.id), "running")
        increment_tenant_job_counter(str(self.tenant2.id), "running")
        
        # Tenant2 should now be at limit
        can_create, _ = check_tenant_job_limits(str(self.tenant2.id))
        self.assertFalse(can_create)
        
        # Tenant1 should still be at limit (unchanged)
        can_create, _ = check_tenant_job_limits(str(self.tenant.id))
        self.assertFalse(can_create)
    
    def test_check_tenant_job_limits_no_config(self):
        """Test checking tenant job limits when no config exists (uses platform defaults)"""
        # No tenant config - should use platform defaults
        # Platform defaults should allow job creation
        can_create, error_message = check_tenant_job_limits(str(self.tenant.id))
        # Should allow (graceful degradation on error)
        self.assertTrue(can_create)


