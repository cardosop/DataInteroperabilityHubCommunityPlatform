"""
Unit tests for Priority Queue functionality.

Tests job selection algorithm, processing order, and reserved slots.
Uses real cache (no mocks).
"""
import pytest
import time
from django.test import TestCase
from django.core.cache import cache
from django.utils import timezone

from hub.apps.jobs.models import Job, JobType, JobStatus
from hub.apps.jobs.utils import (
    get_queue_for_job_type,
    can_process_job,
    can_use_reserved_slot,
    can_use_shared_slot,
    get_reserved_slots_usage,
    get_shared_slots_usage,
    increment_reserved_slots_usage,
    decrement_reserved_slots_usage,
    increment_shared_slots_usage,
    decrement_shared_slots_usage,
)
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


class PriorityQueueTest(TestCase):
    """Test priority queue functionality"""
    
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
    
    def tearDown(self):
        """Clean up after tests"""
        cache.clear()
    
    def test_get_queue_for_job_type_high_priority(self):
        """Test queue selection for HIGH priority job types"""
        # DQ_RUN should use job_critical (HIGH priority)
        queue = get_queue_for_job_type(JobType.DQ_RUN)
        self.assertEqual(queue, 'job_critical')
        
        # COMPLIANCE_RUN should use job_critical (HIGH priority)
        queue = get_queue_for_job_type(JobType.COMPLIANCE_RUN)
        self.assertEqual(queue, 'job_critical')
    
    def test_get_queue_for_job_type_low_priority(self):
        """Test queue selection for LOW priority job types"""
        # CONTRACT_VALIDATION should use job_low (LOW priority)
        queue = get_queue_for_job_type(JobType.CONTRACT_VALIDATION)
        self.assertEqual(queue, 'job_low')
    
    def test_get_queue_for_job_type_normal_priority(self):
        """Test queue selection for NORMAL priority job types"""
        # SEMANTIC_MAPPING should use job_default (NORMAL priority)
        queue = get_queue_for_job_type(JobType.SEMANTIC_MAPPING)
        self.assertEqual(queue, 'job_default')
        
        # CONTRACT_MIGRATION should use job_default (NORMAL priority)
        queue = get_queue_for_job_type(JobType.CONTRACT_MIGRATION)
        self.assertEqual(queue, 'job_default')
    
    def test_can_use_reserved_slot_available(self):
        """Test reserved slot availability when slots are available"""
        # Initially, reserved slots should be available
        self.assertTrue(can_use_reserved_slot())
        
        # Use all reserved slots
        from django.conf import settings
        reserved_slots = settings.WORKER_RESERVED_SLOTS
        for _ in range(reserved_slots):
            increment_reserved_slots_usage()
        
        # No reserved slots available
        self.assertFalse(can_use_reserved_slot())
        
        # Release one slot
        decrement_reserved_slots_usage()
        self.assertTrue(can_use_reserved_slot())
    
    def test_can_use_shared_slot_available(self):
        """Test shared slot availability when slots are available"""
        # Initially, shared slots should be available
        self.assertTrue(can_use_shared_slot())
        
        # Use all shared slots
        from django.conf import settings
        shared_slots = settings.WORKER_SHARED_SLOTS
        for _ in range(shared_slots):
            increment_shared_slots_usage()
        
        # No shared slots available
        self.assertFalse(can_use_shared_slot())
        
        # Release one slot
        decrement_shared_slots_usage()
        self.assertTrue(can_use_shared_slot())
    
    def test_can_process_job_high_priority_reserved_slot(self):
        """Test HIGH priority job can use reserved slot"""
        # HIGH priority job should be able to use reserved slot
        can_process, reason = can_process_job('job_critical')
        self.assertTrue(can_process)
        self.assertEqual(reason, 'reserved_slot')
    
    def test_can_process_job_high_priority_shared_slot(self):
        """Test HIGH priority job can use shared slot when reserved slots are full"""
        # Fill all reserved slots
        from django.conf import settings
        reserved_slots = settings.WORKER_RESERVED_SLOTS
        for _ in range(reserved_slots):
            increment_reserved_slots_usage()
        
        # HIGH priority job should be able to use shared slot
        can_process, reason = can_process_job('job_critical')
        self.assertTrue(can_process)
        self.assertEqual(reason, 'shared_slot')
    
    def test_can_process_job_high_priority_no_slots(self):
        """Test HIGH priority job cannot process when all slots are full"""
        # Fill all reserved and shared slots
        from django.conf import settings
        reserved_slots = settings.WORKER_RESERVED_SLOTS
        shared_slots = settings.WORKER_SHARED_SLOTS
        
        for _ in range(reserved_slots):
            increment_reserved_slots_usage()
        for _ in range(shared_slots):
            increment_shared_slots_usage()
        
        # HIGH priority job should not be able to process
        can_process, reason = can_process_job('job_critical')
        self.assertFalse(can_process)
        self.assertEqual(reason, 'no_slots_available')
    
    def test_can_process_job_normal_priority_shared_slot(self):
        """Test NORMAL priority job can use shared slot"""
        # NORMAL priority job should be able to use shared slot
        can_process, reason = can_process_job('job_default')
        self.assertTrue(can_process)
        self.assertEqual(reason, 'shared_slot')
    
    def test_can_process_job_normal_priority_no_slots(self):
        """Test NORMAL priority job cannot process when shared slots are full"""
        # Fill all shared slots
        from django.conf import settings
        shared_slots = settings.WORKER_SHARED_SLOTS
        for _ in range(shared_slots):
            increment_shared_slots_usage()
        
        # NORMAL priority job should not be able to process
        can_process, reason = can_process_job('job_default')
        self.assertFalse(can_process)
        self.assertEqual(reason, 'no_shared_slots_available')
    
    def test_can_process_job_low_priority_shared_slot(self):
        """Test LOW priority job can use shared slot"""
        # LOW priority job should be able to use shared slot
        can_process, reason = can_process_job('job_low')
        self.assertTrue(can_process)
        self.assertEqual(reason, 'shared_slot')
    
    def test_can_process_job_low_priority_no_slots(self):
        """Test LOW priority job cannot process when shared slots are full"""
        # Fill all shared slots
        from django.conf import settings
        shared_slots = settings.WORKER_SHARED_SLOTS
        for _ in range(shared_slots):
            increment_shared_slots_usage()
        
        # LOW priority job should not be able to process
        can_process, reason = can_process_job('job_low')
        self.assertFalse(can_process)
        self.assertEqual(reason, 'no_shared_slots_available')
    
    def test_reserved_slots_usage_tracking(self):
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
    
    def test_shared_slots_usage_tracking(self):
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
    
    def test_priority_processing_order(self):
        """Test that HIGH priority jobs are selected before NORMAL priority jobs"""
        # Fill all shared slots to force HIGH priority to use reserved slots
        from django.conf import settings
        shared_slots = settings.WORKER_SHARED_SLOTS
        for _ in range(shared_slots):
            increment_shared_slots_usage()
        
        # HIGH priority job should still be able to process (reserved slot)
        can_process_high, reason_high = can_process_job('job_critical')
        self.assertTrue(can_process_high)
        self.assertEqual(reason_high, 'reserved_slot')
        
        # NORMAL priority job should not be able to process (no shared slots)
        can_process_normal, reason_normal = can_process_job('job_default')
        self.assertFalse(can_process_normal)
        self.assertEqual(reason_normal, 'no_shared_slots_available')
    
    def test_reserved_slots_exclusive_to_high_priority(self):
        """Test that reserved slots are exclusive to HIGH priority jobs"""
        # Fill all shared slots
        from django.conf import settings
        shared_slots = settings.WORKER_SHARED_SLOTS
        for _ in range(shared_slots):
            increment_shared_slots_usage()
        
        # NORMAL priority job should not be able to use reserved slots
        can_process, reason = can_process_job('job_default')
        self.assertFalse(can_process)
        self.assertEqual(reason, 'no_shared_slots_available')
        
        # LOW priority job should not be able to use reserved slots
        can_process, reason = can_process_job('job_low')
        self.assertFalse(can_process)
        self.assertEqual(reason, 'no_shared_slots_available')

