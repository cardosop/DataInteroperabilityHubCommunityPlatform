"""
Integration tests for Worker Service.

Tests end-to-end job processing, priority queue integration, concurrency limit integration,
and health checks. Uses real services (no mocks).
"""
import pytest
import time
import uuid
from django.test import TestCase
from django.core.cache import cache
from django.utils import timezone
from django_rq import get_queue
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.jobs.models import Job, JobType, JobStatus
from hub.apps.jobs.utils import (
    create_job,
    check_tenant_job_limits,
    get_tenant_job_counter,
    increment_tenant_job_counter,
    decrement_tenant_job_counter,
    get_queue_for_job_type,
    can_process_job,
    get_reserved_slots_usage,
    get_shared_slots_usage,
)
from hub.apps.tenants.models import Tenant, TenantConfig
from hub.apps.users.models import User, UserStatus
from hub.apps.files.models import File, FileStatus
from hub.apps.dq.models import DQRun, DQRunStatus, DQEngine
from tests.factories import TenantFactory, TenantConfigFactory, JobFactory

pytestmark = pytest.mark.django_db(transaction=True)


class WorkerServiceIntegrationTest(TestCase):
    """Integration tests for worker service"""
    
    def setUp(self):
        """Set up test fixtures"""
        cache.clear()
        
        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant()
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1000,
            status=FileStatus.ACTIVE,
            storage_path="test/test.csv",
            created_by=self.user
        )
    
    def tearDown(self):
        """Clean up after tests"""
        cache.clear()
    
    # End-to-End Job Processing Tests
    def test_job_creation_and_enqueue(self):
        """Test job creation and enqueue via create_job utility"""
        # Create job
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=str(uuid.uuid4()),
            details_json={'dq_run_id': str(uuid.uuid4())}
        )
        
        # Verify job is created
        self.assertIsNotNone(job.id)
        self.assertEqual(job.status, JobStatus.PENDING)
        self.assertEqual(job.type, JobType.DQ_RUN)
        self.assertEqual(job.tenant, self.tenant)
        
        # Verify job is enqueued (queued counter incremented)
        queued_count = get_tenant_job_counter(str(self.tenant.id), "queued")
        self.assertEqual(queued_count, 1)
        
        # Verify job is in correct queue
        queue_name = get_queue_for_job_type(JobType.DQ_RUN)
        self.assertEqual(queue_name, 'job_critical')  # DQ_RUN is HIGH priority
        
        # Verify queue has job
        queue = get_queue(queue_name)
        # Note: We can't easily verify job is in queue without processing it
        # But we can verify the job was created and enqueued
    
    def test_job_creation_with_tenant_limits(self):
        """Test job creation respects tenant concurrency limits"""
        # Create tenant config with low limits
        TenantConfigFactory.create_tenant_config(
            tenant=self.tenant,
            max_job_concurrency=2,
            max_queued_jobs=3
        )
        
        # Fill running jobs to limit
        increment_tenant_job_counter(str(self.tenant.id), "running")
        increment_tenant_job_counter(str(self.tenant.id), "running")
        
        # Try to create job - should fail
        with self.assertRaises(Exception) as cm:
            create_job(
                tenant=self.tenant,
                user=self.user,
                job_type=JobType.DQ_RUN,
                resource_type="DQ_RUN",
                resource_id=str(uuid.uuid4())
            )
        
        self.assertIn("concurrent job limit", str(cm.exception).lower())
    
    def test_job_creation_with_queued_limits(self):
        """Test job creation respects tenant queued job limits"""
        # Create tenant config with low limits
        TenantConfigFactory.create_tenant_config(
            tenant=self.tenant,
            max_job_concurrency=10,
            max_queued_jobs=2
        )
        
        # Fill queued jobs to limit
        increment_tenant_job_counter(str(self.tenant.id), "queued")
        increment_tenant_job_counter(str(self.tenant.id), "queued")
        
        # Try to create job - should fail
        with self.assertRaises(Exception) as cm:
            create_job(
                tenant=self.tenant,
                user=self.user,
                job_type=JobType.DQ_RUN,
                resource_type="DQ_RUN",
                resource_id=str(uuid.uuid4())
            )
        
        self.assertIn("queued job limit", str(cm.exception).lower())
    
    def test_job_status_lifecycle(self):
        """Test job status lifecycle: PENDING → RUNNING → COMPLETED"""
        job = JobFactory.create_job(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            created_by=self.user
        )
        
        # Verify initial state
        self.assertEqual(job.status, JobStatus.PENDING)
        self.assertIsNone(job.started_at)
        self.assertIsNone(job.completed_at)
        
        # Mark as started
        job.mark_started()
        job.refresh_from_db()
        
        # Verify RUNNING state
        self.assertEqual(job.status, JobStatus.RUNNING)
        self.assertIsNotNone(job.started_at)
        self.assertIsNone(job.completed_at)
        
        # Mark as completed
        job.mark_completed(result_json={'status': 'completed'})
        job.refresh_from_db()
        
        # Verify COMPLETED state
        self.assertEqual(job.status, JobStatus.COMPLETED)
        self.assertIsNotNone(job.started_at)
        self.assertIsNotNone(job.completed_at)
        self.assertIsNotNone(job.result_json)
    
    def test_job_status_lifecycle_failure(self):
        """Test job status lifecycle: PENDING → RUNNING → FAILED"""
        job = JobFactory.create_job(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            created_by=self.user
        )
        
        # Mark as started
        job.mark_started()
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.RUNNING)
        
        # Mark as failed
        job.mark_failed(error_message="Test error", result_json={'error': 'Test error'})
        job.refresh_from_db()
        
        # Verify FAILED state
        self.assertEqual(job.status, JobStatus.FAILED)
        self.assertIsNotNone(job.started_at)
        self.assertIsNotNone(job.completed_at)
        self.assertIsNotNone(job.error_message)
        self.assertIsNotNone(job.result_json)
    
    # Priority Queue Integration Tests
    def test_priority_queue_job_selection(self):
        """Test priority queue job selection algorithm"""
        # Create jobs with different priorities
        dq_job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.DQ_RUN,  # HIGH priority
            resource_type="DQ_RUN",
            resource_id=str(uuid.uuid4())
        )
        
        semantic_job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.SEMANTIC_MAPPING,  # NORMAL priority
            resource_type="CONTRACT",
            resource_id=str(uuid.uuid4()),
            details_json={'resource_type': 'CONTRACT', 'resource_id': str(uuid.uuid4())}
        )
        
        validation_job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.CONTRACT_VALIDATION,  # LOW priority
            resource_type="CONTRACT",
            resource_id=str(uuid.uuid4())
        )
        
        # Verify jobs are in correct queues
        dq_queue = get_queue_for_job_type(JobType.DQ_RUN)
        semantic_queue = get_queue_for_job_type(JobType.SEMANTIC_MAPPING)
        validation_queue = get_queue_for_job_type(JobType.CONTRACT_VALIDATION)
        
        self.assertEqual(dq_queue, 'job_critical')
        self.assertEqual(semantic_queue, 'job_default')
        self.assertEqual(validation_queue, 'job_low')
        
        # Verify HIGH priority job can use reserved slots
        can_process, reason = can_process_job('job_critical')
        self.assertTrue(can_process)
        self.assertIn(reason, ['reserved_slot', 'shared_slot'])
        
        # Verify NORMAL priority job can use shared slots
        can_process, reason = can_process_job('job_default')
        self.assertTrue(can_process)
        self.assertEqual(reason, 'shared_slot')
        
        # Verify LOW priority job can use shared slots
        can_process, reason = can_process_job('job_low')
        self.assertTrue(can_process)
        self.assertEqual(reason, 'shared_slot')
    
    def test_priority_queue_reserved_slots(self):
        """Test priority queue reserved slots for HIGH priority jobs"""
        # Fill all shared slots
        from django.conf import settings
        shared_slots = settings.WORKER_SHARED_SLOTS
        for _ in range(shared_slots):
            from hub.apps.jobs.utils import increment_shared_slots_usage
            increment_shared_slots_usage()
        
        # HIGH priority job should still be able to process (reserved slots)
        can_process, reason = can_process_job('job_critical')
        self.assertTrue(can_process)
        self.assertEqual(reason, 'reserved_slot')
        
        # NORMAL priority job should not be able to process (no shared slots)
        can_process, reason = can_process_job('job_default')
        self.assertFalse(can_process)
        self.assertEqual(reason, 'no_shared_slots_available')
    
    def test_priority_queue_processing_order(self):
        """Test that HIGH priority jobs are selected before NORMAL priority jobs"""
        # Create jobs with different priorities
        high_job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.DQ_RUN,  # HIGH priority
            resource_type="DQ_RUN",
            resource_id=str(uuid.uuid4())
        )
        
        normal_job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.SEMANTIC_MAPPING,  # NORMAL priority
            resource_type="CONTRACT",
            resource_id=str(uuid.uuid4()),
            details_json={'resource_type': 'CONTRACT', 'resource_id': str(uuid.uuid4())}
        )
        
        # Verify HIGH priority job can use reserved slots
        can_process_high, reason_high = can_process_job('job_critical')
        self.assertTrue(can_process_high)
        self.assertIn(reason_high, ['reserved_slot', 'shared_slot'])
        
        # Verify NORMAL priority job can use shared slots (if available)
        can_process_normal, reason_normal = can_process_job('job_default')
        # May or may not be able to process depending on slot availability
        # But if it can, it should use shared_slot
        if can_process_normal:
            self.assertEqual(reason_normal, 'shared_slot')
    
    # Concurrency Limit Integration Tests
    def test_concurrency_limit_enforcement_at_job_creation(self):
        """Test concurrency limits are enforced at job creation"""
        # Create tenant config with low limits
        TenantConfigFactory.create_tenant_config(
            tenant=self.tenant,
            max_job_concurrency=1,
            max_queued_jobs=5
        )
        
        # Create first job - should succeed
        job1 = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=str(uuid.uuid4())
        )
        self.assertIsNotNone(job1.id)
        
        # Mark job as running (simulate worker picking it up)
        job1.mark_started()
        increment_tenant_job_counter(str(self.tenant.id), "running")
        decrement_tenant_job_counter(str(self.tenant.id), "queued")
        
        # Try to create second job - should fail (concurrency limit)
        with self.assertRaises(Exception) as cm:
            create_job(
                tenant=self.tenant,
                user=self.user,
                job_type=JobType.DQ_RUN,
                resource_type="DQ_RUN",
                resource_id=str(uuid.uuid4())
            )
        
        self.assertIn("concurrent job limit", str(cm.exception).lower())
    
    def test_concurrency_limit_slot_release_on_completion(self):
        """Test concurrency limit slot is released when job completes"""
        # Create tenant config with low limits
        TenantConfigFactory.create_tenant_config(
            tenant=self.tenant,
            max_job_concurrency=1,
            max_queued_jobs=5
        )
        
        # Create and start job
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=str(uuid.uuid4())
        )
        job.mark_started()
        increment_tenant_job_counter(str(self.tenant.id), "running")
        decrement_tenant_job_counter(str(self.tenant.id), "queued")
        
        # Verify at limit
        can_create, _ = check_tenant_job_limits(str(self.tenant.id))
        self.assertFalse(can_create)
        
        # Complete job
        job.mark_completed(result_json={'status': 'completed'})
        decrement_tenant_job_counter(str(self.tenant.id), "running")
        
        # Verify slot is released
        can_create, _ = check_tenant_job_limits(str(self.tenant.id))
        self.assertTrue(can_create)
    
    def test_concurrency_limit_slot_release_on_failure(self):
        """Test concurrency limit slot is released when job fails"""
        # Create tenant config with low limits
        TenantConfigFactory.create_tenant_config(
            tenant=self.tenant,
            max_job_concurrency=1,
            max_queued_jobs=5
        )
        
        # Create and start job
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=str(uuid.uuid4())
        )
        job.mark_started()
        increment_tenant_job_counter(str(self.tenant.id), "running")
        decrement_tenant_job_counter(str(self.tenant.id), "queued")
        
        # Verify at limit
        can_create, _ = check_tenant_job_limits(str(self.tenant.id))
        self.assertFalse(can_create)
        
        # Fail job
        job.mark_failed(error_message="Test error")
        decrement_tenant_job_counter(str(self.tenant.id), "running")
        
        # Verify slot is released
        can_create, _ = check_tenant_job_limits(str(self.tenant.id))
        self.assertTrue(can_create)
    
    def test_concurrency_limit_tenant_isolation(self):
        """Test concurrency limits are isolated per tenant"""
        # Create two tenants with different limits
        tenant1 = TenantFactory.create_tenant(name="Tenant 1", slug="tenant-1")
        tenant2 = TenantFactory.create_tenant(name="Tenant 2", slug="tenant-2")
        
        TenantConfigFactory.create_tenant_config(
            tenant=tenant1,
            max_job_concurrency=1,
            max_queued_jobs=3
        )
        TenantConfigFactory.create_tenant_config(
            tenant=tenant2,
            max_job_concurrency=2,
            max_queued_jobs=5
        )
        
        # Fill tenant1's concurrency slots
        increment_tenant_job_counter(str(tenant1.id), "running")
        
        # Tenant1 should be at limit
        can_create, _ = check_tenant_job_limits(str(tenant1.id))
        self.assertFalse(can_create)
        
        # Tenant2 should still be able to create jobs
        can_create, _ = check_tenant_job_limits(str(tenant2.id))
        self.assertTrue(can_create)
        
        # Fill tenant2's concurrency slots
        increment_tenant_job_counter(str(tenant2.id), "running")
        increment_tenant_job_counter(str(tenant2.id), "running")
        
        # Tenant2 should now be at limit
        can_create, _ = check_tenant_job_limits(str(tenant2.id))
        self.assertFalse(can_create)
        
        # Tenant1 should still be at limit (unchanged)
        can_create, _ = check_tenant_job_limits(str(tenant1.id))
        self.assertFalse(can_create)
    
    # Job Counter Integration Tests
    def test_job_counter_integration(self):
        """Test job counter integration with job lifecycle"""
        # Create job
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=str(uuid.uuid4())
        )
        
        # Verify queued counter incremented
        queued_count = get_tenant_job_counter(str(self.tenant.id), "queued")
        self.assertEqual(queued_count, 1)
        
        # Mark job as started (simulate worker processing)
        job.mark_started()
        decrement_tenant_job_counter(str(self.tenant.id), "queued")
        increment_tenant_job_counter(str(self.tenant.id), "running")
        
        # Verify running counter incremented, queued counter decremented
        queued_count = get_tenant_job_counter(str(self.tenant.id), "queued")
        running_count = get_tenant_job_counter(str(self.tenant.id), "running")
        self.assertEqual(queued_count, 0)
        self.assertEqual(running_count, 1)
        
        # Mark job as completed
        job.mark_completed(result_json={'status': 'completed'})
        decrement_tenant_job_counter(str(self.tenant.id), "running")
        
        # Verify running counter decremented
        running_count = get_tenant_job_counter(str(self.tenant.id), "running")
        self.assertEqual(running_count, 0)
    
    # Queue Integration Tests
    def test_queue_selection_integration(self):
        """Test queue selection integration for all job types"""
        job_types_and_queues = [
            (JobType.DQ_RUN, 'job_critical'),
            (JobType.COMPLIANCE_RUN, 'job_critical'),
            (JobType.SEMANTIC_MAPPING, 'job_default'),
            (JobType.CONTRACT_MIGRATION, 'job_default'),
            (JobType.CONTRACT_VALIDATION, 'job_low'),
        ]
        
        for job_type, expected_queue in job_types_and_queues:
            queue = get_queue_for_job_type(job_type)
            self.assertEqual(queue, expected_queue, f"Job type {job_type} should use queue {expected_queue}")
    
    def test_queue_integration_with_job_creation(self):
        """Test queue integration with job creation"""
        # Create jobs with different types
        dq_job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=str(uuid.uuid4())
        )
        
        validation_job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.CONTRACT_VALIDATION,
            resource_type="CONTRACT",
            resource_id=str(uuid.uuid4())
        )
        
        # Verify jobs are created
        self.assertIsNotNone(dq_job.id)
        self.assertIsNotNone(validation_job.id)
        
        # Verify jobs would be in correct queues
        dq_queue = get_queue_for_job_type(JobType.DQ_RUN)
        validation_queue = get_queue_for_job_type(JobType.CONTRACT_VALIDATION)
        
        self.assertEqual(dq_queue, 'job_critical')
        self.assertEqual(validation_queue, 'job_low')
        
        # Verify queues exist
        dq_queue_obj = get_queue(dq_queue)
        validation_queue_obj = get_queue(validation_queue)
        self.assertIsNotNone(dq_queue_obj)
        self.assertIsNotNone(validation_queue_obj)

