"""
Tests for Job Queue Infrastructure

Tests for priority queues, reserved slots, starvation prevention, and job selection algorithm.
"""
import time
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.core.cache import cache
from django.utils import timezone
from hub.apps.jobs.models import Job, JobType, JobStatus
from hub.apps.jobs.utils import (
    get_job_enqueue_timestamp,
    get_job_wait_time,
    should_elevate_job,
    get_reserved_slots_usage,
    increment_reserved_slots_usage,
    decrement_reserved_slots_usage,
    get_shared_slots_usage,
    increment_shared_slots_usage,
    decrement_shared_slots_usage,
    can_use_reserved_slot,
    can_use_shared_slot,
    can_process_job,
    get_queue_for_job_type,
)
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User


class JobQueueInfrastructureTest(TestCase):
    """Test job queue infrastructure (priority queues, reserved slots, starvation prevention)"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Clear cache
        cache.clear()
        
        # Create test tenant and user
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )
    
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
        timestamp = time.time() - 10  # 10 seconds ago
        
        # Set timestamp
        cache.set(f"job:enqueue_time:{job_id}", timestamp, timeout=86400)
        
        # Get wait time
        wait_time = get_job_wait_time(job_id)
        self.assertIsNotNone(wait_time)
        self.assertAlmostEqual(wait_time, 10, delta=1.0)
        
        # Non-existent job
        self.assertIsNone(get_job_wait_time("non-existent"))
    
    def test_should_elevate_job(self):
        """Test starvation prevention - job elevation"""
        job_id = "test-job-id"
        
        # NORMAL priority job (job_default) waiting less than threshold
        timestamp = time.time() - 100  # 100 seconds ago (less than 300s threshold)
        cache.set(f"job:enqueue_time:{job_id}", timestamp, timeout=86400)
        self.assertFalse(should_elevate_job(job_id, "job_default"))
        
        # NORMAL priority job waiting more than threshold
        timestamp = time.time() - 400  # 400 seconds ago (more than 300s threshold)
        cache.set(f"job:enqueue_time:{job_id}", timestamp, timeout=86400)
        self.assertTrue(should_elevate_job(job_id, "job_default"))
        
        # HIGH priority job should not be elevated
        self.assertFalse(should_elevate_job(job_id, "job_critical"))
        
        # LOW priority job should not be elevated
        self.assertFalse(should_elevate_job(job_id, "job_low"))
    
    def test_reserved_slots_usage(self):
        """Test reserved slots usage tracking"""
        # Initially zero
        self.assertEqual(get_reserved_slots_usage(), 0)
        
        # Increment
        count = increment_reserved_slots_usage()
        self.assertEqual(count, 1)
        self.assertEqual(get_reserved_slots_usage(), 1)
        
        # Increment again
        count = increment_reserved_slots_usage()
        self.assertEqual(count, 2)
        self.assertEqual(get_reserved_slots_usage(), 2)
        
        # Decrement
        count = decrement_reserved_slots_usage()
        self.assertEqual(count, 1)
        self.assertEqual(get_reserved_slots_usage(), 1)
        
        # Decrement to zero
        count = decrement_reserved_slots_usage()
        self.assertEqual(count, 0)
        self.assertEqual(get_reserved_slots_usage(), 0)
        
        # Decrement below zero should not go negative
        count = decrement_reserved_slots_usage()
        self.assertEqual(count, 0)
        self.assertEqual(get_reserved_slots_usage(), 0)
    
    def test_shared_slots_usage(self):
        """Test shared slots usage tracking"""
        # Initially zero
        self.assertEqual(get_shared_slots_usage(), 0)
        
        # Increment
        count = increment_shared_slots_usage()
        self.assertEqual(count, 1)
        self.assertEqual(get_shared_slots_usage(), 1)
        
        # Increment again
        count = increment_shared_slots_usage()
        self.assertEqual(count, 2)
        self.assertEqual(get_shared_slots_usage(), 2)
        
        # Decrement
        count = decrement_shared_slots_usage()
        self.assertEqual(count, 1)
        self.assertEqual(get_shared_slots_usage(), 1)
        
        # Decrement to zero
        count = decrement_shared_slots_usage()
        self.assertEqual(count, 0)
        self.assertEqual(get_shared_slots_usage(), 0)
        
        # Decrement below zero should not go negative
        count = decrement_shared_slots_usage()
        self.assertEqual(count, 0)
        self.assertEqual(get_shared_slots_usage(), 0)
    
    def test_can_use_reserved_slot(self):
        """Test reserved slot availability"""
        from django.conf import settings
        
        # Initially available
        self.assertTrue(can_use_reserved_slot())
        
        # Fill all reserved slots
        for _ in range(settings.WORKER_RESERVED_SLOTS):
            increment_reserved_slots_usage()
        
        # Should not be available
        self.assertFalse(can_use_reserved_slot())
        
        # Free one slot
        decrement_reserved_slots_usage()
        self.assertTrue(can_use_reserved_slot())
    
    def test_can_use_shared_slot(self):
        """Test shared slot availability"""
        from django.conf import settings
        
        # Initially available
        self.assertTrue(can_use_shared_slot())
        
        # Fill all shared slots
        for _ in range(settings.WORKER_SHARED_SLOTS):
            increment_shared_slots_usage()
        
        # Should not be available
        self.assertFalse(can_use_shared_slot())
        
        # Free one slot
        decrement_shared_slots_usage()
        self.assertTrue(can_use_shared_slot())
    
    def test_can_process_job_high_priority(self):
        """Test job processing check for HIGH priority jobs"""
        job_id = "test-job-id"
        
        # HIGH priority job with available reserved slot
        can_process, reason = can_process_job("job_critical", job_id)
        self.assertTrue(can_process)
        self.assertEqual(reason, "reserved_slot")
        
        # Fill all reserved slots
        from django.conf import settings
        for _ in range(settings.WORKER_RESERVED_SLOTS):
            increment_reserved_slots_usage()
        
        # HIGH priority job with no reserved slots but available shared slot
        can_process, reason = can_process_job("job_critical", job_id)
        self.assertTrue(can_process)
        self.assertEqual(reason, "shared_slot")
        
        # Fill all shared slots too
        for _ in range(settings.WORKER_SHARED_SLOTS):
            increment_shared_slots_usage()
        
        # HIGH priority job with no slots available
        can_process, reason = can_process_job("job_critical", job_id)
        self.assertFalse(can_process)
        self.assertEqual(reason, "no_slots_available")
    
    def test_can_process_job_normal_priority(self):
        """Test job processing check for NORMAL priority jobs"""
        job_id = "test-job-id"
        
        # NORMAL priority job with available shared slot
        can_process, reason = can_process_job("job_default", job_id)
        self.assertTrue(can_process)
        self.assertEqual(reason, "shared_slot")
        
        # Fill all shared slots
        from django.conf import settings
        for _ in range(settings.WORKER_SHARED_SLOTS):
            increment_shared_slots_usage()
        
        # NORMAL priority job with no shared slots available
        can_process, reason = can_process_job("job_default", job_id)
        self.assertFalse(can_process)
        self.assertEqual(reason, "no_shared_slots_available")
        
        # NORMAL priority job elevated due to starvation
        timestamp = time.time() - 400  # 400 seconds ago (more than threshold)
        cache.set(f"job:enqueue_time:{job_id}", timestamp, timeout=86400)
        
        # Free one reserved slot
        decrement_reserved_slots_usage()
        
        # Elevated job can use reserved slot
        can_process, reason = can_process_job("job_default", job_id)
        self.assertTrue(can_process)
        self.assertEqual(reason, "elevated_reserved_slot")
    
    def test_can_process_job_low_priority(self):
        """Test job processing check for LOW priority jobs"""
        job_id = "test-job-id"
        
        # LOW priority job with available shared slot
        can_process, reason = can_process_job("job_low", job_id)
        self.assertTrue(can_process)
        self.assertEqual(reason, "shared_slot")
        
        # Fill all shared slots
        from django.conf import settings
        for _ in range(settings.WORKER_SHARED_SLOTS):
            increment_shared_slots_usage()
        
        # LOW priority job with no shared slots available
        can_process, reason = can_process_job("job_low", job_id)
        self.assertFalse(can_process)
        self.assertEqual(reason, "no_shared_slots_available")
    
    def test_get_queue_for_job_type(self):
        """Test queue selection for different job types"""
        # HIGH priority jobs
        self.assertEqual(get_queue_for_job_type(JobType.DQ_RUN), "job_critical")
        self.assertEqual(get_queue_for_job_type(JobType.COMPLIANCE_RUN), "job_critical")
        
        # LOW priority jobs
        self.assertEqual(get_queue_for_job_type(JobType.CONTRACT_VALIDATION), "job_low")
        
        # NORMAL priority jobs
        self.assertEqual(get_queue_for_job_type(JobType.SEMANTIC_MAPPING), "job_default")
        self.assertEqual(get_queue_for_job_type(JobType.CONTRACT_MIGRATION), "job_default")
    
    def test_reserved_slots_ratio(self):
        """Test that reserved slots are calculated correctly"""
        from django.conf import settings
        
        # With default WORKER_MAX_CONCURRENCY=4 and WORKER_RESERVED_SLOTS_RATIO=0.5
        # Reserved slots should be 2, shared slots should be 2
        self.assertEqual(settings.WORKER_RESERVED_SLOTS, 2)
        self.assertEqual(settings.WORKER_SHARED_SLOTS, 2)
        
        # Total should equal max concurrency
        self.assertEqual(
            settings.WORKER_RESERVED_SLOTS + settings.WORKER_SHARED_SLOTS,
            settings.WORKER_MAX_CONCURRENCY
        )
    
    def test_starvation_threshold(self):
        """Test starvation threshold configuration"""
        from django.conf import settings
        
        # Default threshold should be 300 seconds (5 minutes)
        self.assertEqual(settings.WORKER_STARVATION_THRESHOLD_SECONDS, 300)
        
        # Job waiting less than threshold should not be elevated
        job_id = "test-job-id"
        timestamp = time.time() - 200  # 200 seconds ago
        cache.set(f"job:enqueue_time:{job_id}", timestamp, timeout=86400)
        self.assertFalse(should_elevate_job(job_id, "job_default"))
        
        # Job waiting more than threshold should be elevated
        timestamp = time.time() - 400  # 400 seconds ago
        cache.set(f"job:enqueue_time:{job_id}", timestamp, timeout=86400)
        self.assertTrue(should_elevate_job(job_id, "job_default"))

