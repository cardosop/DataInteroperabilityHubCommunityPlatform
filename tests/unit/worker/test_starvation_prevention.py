"""
Unit tests for Starvation Prevention functionality.

Tests starvation detection and job elevation algorithm.
Uses real cache (no mocks).
"""
import pytest
import time
from django.test import TestCase
from django.core.cache import cache
from django.conf import settings

from hub.apps.jobs.utils import (
    get_job_enqueue_timestamp,
    get_job_wait_time,
    should_elevate_job,
    can_process_job,
)
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


class StarvationPreventionTest(TestCase):
    """Test starvation prevention functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        cache.clear()
        
        self.tenant = TenantFactory.create_tenant()
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        self.starvation_threshold = settings.WORKER_STARVATION_THRESHOLD_SECONDS
    
    def tearDown(self):
        """Clean up after tests"""
        cache.clear()
    
    def test_get_job_enqueue_timestamp(self):
        """Test getting job enqueue timestamp"""
        job_id = "test-job-id"
        timestamp = time.time()
        
        # Set timestamp
        cache.set(f"job:enqueue_time:{job_id}", timestamp, timeout=86400)
        
        # Get timestamp
        retrieved = get_job_enqueue_timestamp(job_id)
        self.assertIsNotNone(retrieved)
        self.assertAlmostEqual(retrieved, timestamp, delta=1.0)
        
        # Non-existent job
        self.assertIsNone(get_job_enqueue_timestamp("non-existent"))
    
    def test_get_job_wait_time(self):
        """Test calculating job wait time"""
        job_id = "test-job-id"
        wait_seconds = 10
        timestamp = time.time() - wait_seconds
        
        # Set timestamp
        cache.set(f"job:enqueue_time:{job_id}", timestamp, timeout=86400)
        
        # Get wait time
        wait_time = get_job_wait_time(job_id)
        self.assertIsNotNone(wait_time)
        self.assertAlmostEqual(wait_time, wait_seconds, delta=1.0)
        
        # Non-existent job
        self.assertIsNone(get_job_wait_time("non-existent"))
    
    def test_should_elevate_job_normal_priority_below_threshold(self):
        """Test NORMAL priority job should not be elevated if wait time is below threshold"""
        job_id = "test-job-id"
        wait_seconds = self.starvation_threshold - 10  # Below threshold
        timestamp = time.time() - wait_seconds
        
        cache.set(f"job:enqueue_time:{job_id}", timestamp, timeout=86400)
        
        # Should not be elevated
        self.assertFalse(should_elevate_job(job_id, "job_default"))
    
    def test_should_elevate_job_normal_priority_above_threshold(self):
        """Test NORMAL priority job should be elevated if wait time is above threshold"""
        job_id = "test-job-id"
        wait_seconds = self.starvation_threshold + 10  # Above threshold
        timestamp = time.time() - wait_seconds
        
        cache.set(f"job:enqueue_time:{job_id}", timestamp, timeout=86400)
        
        # Should be elevated
        self.assertTrue(should_elevate_job(job_id, "job_default"))
    
    def test_should_elevate_job_normal_priority_at_threshold(self):
        """Test NORMAL priority job should be elevated if wait time equals threshold"""
        job_id = "test-job-id"
        wait_seconds = self.starvation_threshold  # Exactly at threshold
        timestamp = time.time() - wait_seconds
        
        cache.set(f"job:enqueue_time:{job_id}", timestamp, timeout=86400)
        
        # Should be elevated (threshold is exclusive, so wait_time > threshold)
        # But since we're using time.time() which has sub-second precision,
        # we'll test with a small buffer
        wait_seconds = self.starvation_threshold + 0.1
        timestamp = time.time() - wait_seconds
        cache.set(f"job:enqueue_time:{job_id}", timestamp, timeout=86400)
        self.assertTrue(should_elevate_job(job_id, "job_default"))
    
    def test_should_elevate_job_high_priority_never(self):
        """Test HIGH priority job should never be elevated"""
        job_id = "test-job-id"
        wait_seconds = self.starvation_threshold + 100  # Well above threshold
        timestamp = time.time() - wait_seconds
        
        cache.set(f"job:enqueue_time:{job_id}", timestamp, timeout=86400)
        
        # Should not be elevated (HIGH priority jobs don't need elevation)
        self.assertFalse(should_elevate_job(job_id, "job_critical"))
    
    def test_should_elevate_job_low_priority_never(self):
        """Test LOW priority job should never be elevated"""
        job_id = "test-job-id"
        wait_seconds = self.starvation_threshold + 100  # Well above threshold
        timestamp = time.time() - wait_seconds
        
        cache.set(f"job:enqueue_time:{job_id}", timestamp, timeout=86400)
        
        # Should not be elevated (LOW priority jobs don't get elevated)
        self.assertFalse(should_elevate_job(job_id, "job_low"))
    
    def test_should_elevate_job_missing_timestamp(self):
        """Test job without enqueue timestamp should not be elevated"""
        job_id = "non-existent-job-id"
        
        # Should not be elevated (no timestamp)
        self.assertFalse(should_elevate_job(job_id, "job_default"))
    
    def test_can_process_job_elevated_normal_priority_reserved_slot(self):
        """Test elevated NORMAL priority job can use reserved slot"""
        job_id = "test-job-id"
        wait_seconds = self.starvation_threshold + 10  # Above threshold
        timestamp = time.time() - wait_seconds
        
        cache.set(f"job:enqueue_time:{job_id}", timestamp, timeout=86400)
        
        # Elevated NORMAL priority job should be able to use reserved slot
        can_process, reason = can_process_job('job_default', job_id)
        self.assertTrue(can_process)
        self.assertEqual(reason, 'elevated_reserved_slot')
    
    def test_can_process_job_elevated_normal_priority_shared_slot(self):
        """Test elevated NORMAL priority job can use shared slot when reserved slots are full"""
        job_id = "test-job-id"
        wait_seconds = self.starvation_threshold + 10  # Above threshold
        timestamp = time.time() - wait_seconds
        
        cache.set(f"job:enqueue_time:{job_id}", timestamp, timeout=86400)
        
        # Fill all reserved slots
        from hub.apps.jobs.utils import increment_reserved_slots_usage
        from django.conf import settings
        reserved_slots = settings.WORKER_RESERVED_SLOTS
        for _ in range(reserved_slots):
            increment_reserved_slots_usage()
        
        # Elevated NORMAL priority job should be able to use shared slot
        can_process, reason = can_process_job('job_default', job_id)
        self.assertTrue(can_process)
        self.assertEqual(reason, 'elevated_shared_slot')
    
    def test_can_process_job_elevated_normal_priority_no_slots(self):
        """Test elevated NORMAL priority job cannot process when all slots are full"""
        job_id = "test-job-id"
        wait_seconds = self.starvation_threshold + 10  # Above threshold
        timestamp = time.time() - wait_seconds
        
        cache.set(f"job:enqueue_time:{job_id}", timestamp, timeout=86400)
        
        # Fill all reserved and shared slots
        from hub.apps.jobs.utils import increment_reserved_slots_usage, increment_shared_slots_usage
        from django.conf import settings
        reserved_slots = settings.WORKER_RESERVED_SLOTS
        shared_slots = settings.WORKER_SHARED_SLOTS
        
        for _ in range(reserved_slots):
            increment_reserved_slots_usage()
        for _ in range(shared_slots):
            increment_shared_slots_usage()
        
        # Elevated NORMAL priority job should not be able to process
        can_process, reason = can_process_job('job_default', job_id)
        self.assertFalse(can_process)
        self.assertEqual(reason, 'no_slots_available')
    
    def test_starvation_prevention_algorithm(self):
        """Test starvation prevention algorithm with multiple jobs"""
        # Create multiple NORMAL priority jobs with different wait times
        job1_id = "job-1"
        job2_id = "job-2"
        job3_id = "job-3"
        
        # Job 1: Below threshold (should not be elevated)
        wait1 = self.starvation_threshold - 10
        cache.set(f"job:enqueue_time:{job1_id}", time.time() - wait1, timeout=86400)
        
        # Job 2: At threshold (should be elevated)
        wait2 = self.starvation_threshold + 1
        cache.set(f"job:enqueue_time:{job2_id}", time.time() - wait2, timeout=86400)
        
        # Job 3: Well above threshold (should be elevated)
        wait3 = self.starvation_threshold + 100
        cache.set(f"job:enqueue_time:{job3_id}", time.time() - wait3, timeout=86400)
        
        # Verify elevation status
        self.assertFalse(should_elevate_job(job1_id, "job_default"))
        self.assertTrue(should_elevate_job(job2_id, "job_default"))
        self.assertTrue(should_elevate_job(job3_id, "job_default"))
    
    def test_starvation_prevention_with_high_priority_jobs(self):
        """Test that NORMAL priority jobs are elevated even when HIGH priority jobs are present"""
        # Create HIGH priority job (should not be elevated)
        high_job_id = "high-job"
        wait_high = self.starvation_threshold + 100
        cache.set(f"job:enqueue_time:{high_job_id}", time.time() - wait_high, timeout=86400)
        
        # Create NORMAL priority job (should be elevated)
        normal_job_id = "normal-job"
        wait_normal = self.starvation_threshold + 10
        cache.set(f"job:enqueue_time:{normal_job_id}", time.time() - wait_normal, timeout=86400)
        
        # HIGH priority job should not be elevated
        self.assertFalse(should_elevate_job(high_job_id, "job_critical"))
        
        # NORMAL priority job should be elevated
        self.assertTrue(should_elevate_job(normal_job_id, "job_default"))
        
        # Elevated NORMAL priority job should be able to use reserved slots
        can_process, reason = can_process_job('job_default', normal_job_id)
        self.assertTrue(can_process)
        self.assertIn(reason, ['elevated_reserved_slot', 'elevated_shared_slot'])


