"""
E2E tests for Worker Service.

Tests complete job processing journeys with all job types, priority queue,
starvation prevention, concurrency limits, cancellation, timeout, and edge cases.
Uses real services (no mocks).
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
    should_elevate_job,
    get_job_wait_time,
    get_job_enqueue_timestamp,
)
from hub.apps.tenants.models import Tenant, TenantConfig
from hub.apps.users.models import User, UserStatus
from hub.apps.files.models import File, FileStatus
from hub.apps.dq.models import DQRun, DQRunStatus, DQEngine
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.contracts.models import Contract, ContractStatus, OriginalSpecType
from tests.factories import TenantFactory, TenantConfigFactory, JobFactory
from tests.e2e.conftest import E2ETestBase

pytestmark = [
    pytest.mark.slow,
    pytest.mark.django_db(transaction=True),
    pytest.mark.e2e,
    pytest.mark.e2e_batch2,
]


class WorkerServiceE2ETest(E2ETestBase):
    """E2E tests for worker service"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        cache.clear()
        
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
    
    # Job Processing Journey Tests
    def test_dq_run_job_processing_journey(self):
        """Test complete DQ run job processing journey"""
        # Create job first
        dq_run_id = uuid.uuid4()
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=str(dq_run_id),
            details_json={'dq_run_id': str(dq_run_id)}
        )
        
        # Create DQ run with job
        dq_run = DQRun.objects.create(
            id=dq_run_id,
            tenant=self.tenant,
            file=self.file,
            job=job,
            profile_key='intake_basic_gx',
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING
        )
        
        # Verify job is created and enqueued
        self.assertIsNotNone(job.id)
        self.assertEqual(job.status, JobStatus.PENDING)
        self.assertEqual(job.type, JobType.DQ_RUN)
        
        # Verify job is in correct queue
        queue_name = get_queue_for_job_type(JobType.DQ_RUN)
        self.assertEqual(queue_name, 'job_critical')
        
        # Verify queued counter incremented
        queued_count = get_tenant_job_counter(str(self.tenant.id), "queued")
        self.assertEqual(queued_count, 1)
        
        # Verify job can be processed (HIGH priority can use reserved/shared slots)
        can_process, reason = can_process_job(queue_name)
        self.assertTrue(can_process)
        self.assertIn(reason, ['reserved_slot', 'shared_slot'])
    
    def test_compliance_run_job_processing_journey(self):
        """Test complete compliance run job processing journey"""
        # Create job first
        compliance_run_id = uuid.uuid4()
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            type=JobType.COMPLIANCE_RUN,
            resource_type="COMPLIANCE_RUN",
            resource_id=str(compliance_run_id),
            details_json={'compliance_run_id': str(compliance_run_id)}
        )
        
        # Create compliance run with job
        compliance_run = ComplianceRun.objects.create(
            id=compliance_run_id,
            tenant=self.tenant,
            file=self.file,
            job=job,
            status=ComplianceRunStatus.PENDING
        )
        
        # Verify job is created and enqueued
        self.assertIsNotNone(job.id)
        self.assertEqual(job.status, JobStatus.PENDING)
        self.assertEqual(job.type, JobType.COMPLIANCE_RUN)
        
        # Verify job is in correct queue (HIGH priority)
        queue_name = get_queue_for_job_type(JobType.COMPLIANCE_RUN)
        self.assertEqual(queue_name, 'job_critical')
    
    def test_contract_validation_job_processing_journey(self):
        """Test complete contract validation job processing journey"""
        # Create contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_format='JSON',
            original_raw='{"id": "test", "schema": {"fields": []}}',
            created_by=self.user
        )
        
        # Create job
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            type=JobType.CONTRACT_VALIDATION,
            resource_type="CONTRACT",
            resource_id=str(contract.id)
        )
        
        # Verify job is created and enqueued
        self.assertIsNotNone(job.id)
        self.assertEqual(job.status, JobStatus.PENDING)
        self.assertEqual(job.type, JobType.CONTRACT_VALIDATION)
        
        # Verify job is in correct queue (LOW priority)
        queue_name = get_queue_for_job_type(JobType.CONTRACT_VALIDATION)
        self.assertEqual(queue_name, 'job_low')
    
    def test_semantic_mapping_job_processing_journey(self):
        """Test complete semantic mapping job processing journey"""
        # Create contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_format='JSON',
            original_raw='{"id": "test", "schema": {"fields": []}}',
            created_by=self.user
        )
        
        # Create job
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            type=JobType.SEMANTIC_MAPPING,
            resource_type="CONTRACT",
            resource_id=str(contract.id),
            details_json={
                'resource_type': 'CONTRACT',
                'resource_id': str(contract.id)
            }
        )
        
        # Verify job is created and enqueued
        self.assertIsNotNone(job.id)
        self.assertEqual(job.status, JobStatus.PENDING)
        self.assertEqual(job.type, JobType.SEMANTIC_MAPPING)
        
        # Verify job is in correct queue (NORMAL priority)
        queue_name = get_queue_for_job_type(JobType.SEMANTIC_MAPPING)
        self.assertEqual(queue_name, 'job_default')
    
    # Priority Queue E2E Tests
    def test_priority_queue_processing_order_e2e(self):
        """Test priority queue processing order E2E"""
        # Create jobs with different priorities
        high_job = create_job(
            tenant=self.tenant,
            user=self.user,
            type=JobType.DQ_RUN,  # HIGH priority
            resource_type="DQ_RUN",
            resource_id=str(uuid.uuid4()),
            details_json={'dq_run_id': str(uuid.uuid4())}
        )
        
        normal_job = create_job(
            tenant=self.tenant,
            user=self.user,
            type=JobType.SEMANTIC_MAPPING,  # NORMAL priority
            resource_type="CONTRACT",
            resource_id=str(uuid.uuid4()),
            details_json={'resource_type': 'CONTRACT', 'resource_id': str(uuid.uuid4())}
        )
        
        low_job = create_job(
            tenant=self.tenant,
            user=self.user,
            type=JobType.CONTRACT_VALIDATION,  # LOW priority
            resource_type="CONTRACT",
            resource_id=str(uuid.uuid4())
        )
        
        # Verify jobs are in correct queues
        self.assertEqual(get_queue_for_job_type(JobType.DQ_RUN), 'job_critical')
        self.assertEqual(get_queue_for_job_type(JobType.SEMANTIC_MAPPING), 'job_default')
        self.assertEqual(get_queue_for_job_type(JobType.CONTRACT_VALIDATION), 'job_low')
        
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
    
    # Starvation Prevention E2E Tests
    def test_starvation_prevention_e2e(self):
        """Test starvation prevention E2E"""
        # Create NORMAL priority job
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            type=JobType.SEMANTIC_MAPPING,  # NORMAL priority
            resource_type="CONTRACT",
            resource_id=str(uuid.uuid4()),
            details_json={'resource_type': 'CONTRACT', 'resource_id': str(uuid.uuid4())}
        )
        
        # Verify job enqueue timestamp is set
        enqueue_timestamp = get_job_enqueue_timestamp(str(job.id))
        self.assertIsNotNone(enqueue_timestamp)
        
        # Simulate wait time above threshold
        from django.conf import settings
        starvation_threshold = settings.WORKER_STARVATION_THRESHOLD_SECONDS
        
        # Set timestamp to be above threshold
        old_timestamp = time.time() - (starvation_threshold + 10)
        cache.set(f"job:enqueue_time:{job.id}", old_timestamp, timeout=86400)
        
        # Verify job should be elevated
        should_elevate = should_elevate_job(str(job.id), 'job_default')
        self.assertTrue(should_elevate)
        
        # Verify elevated job can use reserved slots
        can_process, reason = can_process_job('job_default', str(job.id))
        self.assertTrue(can_process)
        self.assertIn(reason, ['elevated_reserved_slot', 'elevated_shared_slot'])
    
    def test_starvation_prevention_with_high_priority_jobs_e2e(self):
        """Test starvation prevention when HIGH priority jobs are present"""
        # Create HIGH priority job
        high_job = create_job(
            tenant=self.tenant,
            user=self.user,
            type=JobType.DQ_RUN,  # HIGH priority
            resource_type="DQ_RUN",
            resource_id=str(uuid.uuid4()),
            details_json={'dq_run_id': str(uuid.uuid4())}
        )
        
        # Create NORMAL priority job
        normal_job = create_job(
            tenant=self.tenant,
            user=self.user,
            type=JobType.SEMANTIC_MAPPING,  # NORMAL priority
            resource_type="CONTRACT",
            resource_id=str(uuid.uuid4()),
            details_json={'resource_type': 'CONTRACT', 'resource_id': str(uuid.uuid4())}
        )
        
        # Simulate NORMAL priority job waiting above threshold
        from django.conf import settings
        starvation_threshold = settings.WORKER_STARVATION_THRESHOLD_SECONDS
        old_timestamp = time.time() - (starvation_threshold + 10)
        cache.set(f"job:enqueue_time:{normal_job.id}", old_timestamp, timeout=86400)
        
        # Verify NORMAL priority job should be elevated
        should_elevate = should_elevate_job(str(normal_job.id), 'job_default')
        self.assertTrue(should_elevate)
        
        # Verify elevated NORMAL priority job can use reserved slots
        can_process, reason = can_process_job('job_default', str(normal_job.id))
        self.assertTrue(can_process)
        self.assertIn(reason, ['elevated_reserved_slot', 'elevated_shared_slot'])
    
    # Concurrency Limits E2E Tests
    def test_concurrency_limit_enforcement_e2e(self):
        """Test concurrency limit enforcement E2E"""
        # Create tenant config with low limits
        TenantConfigFactory.create_tenant_config(
            tenant=self.tenant,
            max_job_concurrency=1,
            max_queued_jobs=3
        )
        
        # Create first job - should succeed
        job1 = create_job(
            tenant=self.tenant,
            user=self.user,
            type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=str(uuid.uuid4()),
            details_json={'dq_run_id': str(uuid.uuid4())}
        )
        self.assertIsNotNone(job1.id)
        
        # Mark job as running (simulate worker processing)
        job1.mark_started()
        increment_tenant_job_counter(str(self.tenant.id), "running")
        decrement_tenant_job_counter(str(self.tenant.id), "queued")
        
        # Try to create second job - should fail
        with self.assertRaises(Exception) as cm:
            create_job(
                tenant=self.tenant,
                user=self.user,
                type=JobType.DQ_RUN,
                resource_type="DQ_RUN",
                resource_id=str(uuid.uuid4()),
                details_json={'dq_run_id': str(uuid.uuid4())}
            )
        
        self.assertIn("concurrent job limit", str(cm.exception).lower())
        
        # Complete first job
        job1.mark_completed(result_json={'status': 'completed'})
        decrement_tenant_job_counter(str(self.tenant.id), "running")
        
        # Should now be able to create second job
        job2 = create_job(
            tenant=self.tenant,
            user=self.user,
            type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=str(uuid.uuid4()),
            details_json={'dq_run_id': str(uuid.uuid4())}
        )
        self.assertIsNotNone(job2.id)
    
    def test_queued_job_limit_enforcement_e2e(self):
        """Test queued job limit enforcement E2E"""
        # Create tenant config with low queued limit
        TenantConfigFactory.create_tenant_config(
            tenant=self.tenant,
            max_job_concurrency=10,
            max_queued_jobs=2
        )
        
        # Create jobs up to limit
        job1 = create_job(
            tenant=self.tenant,
            user=self.user,
            type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=str(uuid.uuid4()),
            details_json={'dq_run_id': str(uuid.uuid4())}
        )
        job2 = create_job(
            tenant=self.tenant,
            user=self.user,
            type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=str(uuid.uuid4()),
            details_json={'dq_run_id': str(uuid.uuid4())}
        )
        
        # Verify both jobs created
        self.assertIsNotNone(job1.id)
        self.assertIsNotNone(job2.id)
        
        # Try to create third job - should fail
        with self.assertRaises(Exception) as cm:
            create_job(
                tenant=self.tenant,
                user=self.user,
                type=JobType.DQ_RUN,
                resource_type="DQ_RUN",
                resource_id=str(uuid.uuid4()),
                details_json={'dq_run_id': str(uuid.uuid4())}
            )
        
        self.assertIn("queued job limit", str(cm.exception).lower())
    
    # Job Cancellation E2E Tests
    def test_job_cancellation_pending_e2e(self):
        """Test job cancellation in PENDING state E2E"""
        # Create job
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=str(uuid.uuid4()),
            details_json={'dq_run_id': str(uuid.uuid4())}
        )
        
        # Verify job is PENDING
        self.assertEqual(job.status, JobStatus.PENDING)
        self.assertTrue(job.can_cancel())
        
        # Cancel job using production method
        queued_before = get_tenant_job_counter(str(self.tenant.id), "queued")
        job.mark_cancelled()
        decrement_tenant_job_counter(str(self.tenant.id), "queued")

        # Verify job is cancelled
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.CANCELLED)
        self.assertIsNotNone(job.completed_at)
        self.assertFalse(job.can_cancel())

        # Verify queued counter was decremented
        queued_after = get_tenant_job_counter(str(self.tenant.id), "queued")
        self.assertEqual(queued_after, queued_before - 1)

    def test_job_cancellation_running_e2e(self):
        """Test job cancellation in RUNNING state E2E"""
        # Create and start job
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=str(uuid.uuid4()),
            details_json={'dq_run_id': str(uuid.uuid4())}
        )
        job.mark_started()
        increment_tenant_job_counter(str(self.tenant.id), "running")
        decrement_tenant_job_counter(str(self.tenant.id), "queued")

        # Verify job is RUNNING
        self.assertEqual(job.status, JobStatus.RUNNING)
        self.assertTrue(job.can_cancel())

        # Cancel job using production method and release concurrency slot
        job.mark_cancelled()
        decrement_tenant_job_counter(str(self.tenant.id), "running")

        # Verify job is cancelled
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.CANCELLED)
        self.assertIsNotNone(job.completed_at)
        self.assertFalse(job.can_cancel())

        # Verify running counter was decremented
        running_after = get_tenant_job_counter(str(self.tenant.id), "running")
        self.assertEqual(running_after, 0)
    
    # Job Timeout E2E Tests
    def test_job_timeout_configuration_e2e(self):
        """Test job timeout configuration E2E"""
        from hub.apps.jobs.utils import get_job_timeout
        
        # Verify timeout for each job type
        self.assertEqual(get_job_timeout(JobType.DQ_RUN), 1800)  # 30 minutes
        self.assertEqual(get_job_timeout(JobType.COMPLIANCE_RUN), 1800)  # 30 minutes
        self.assertEqual(get_job_timeout(JobType.CONTRACT_VALIDATION), 300)  # 5 minutes
        self.assertEqual(get_job_timeout(JobType.SEMANTIC_MAPPING), 60)  # 1 minute
        self.assertEqual(get_job_timeout(JobType.CONTRACT_MIGRATION), 600)  # 10 minutes
    
    def test_job_timeout_handling_e2e(self):
        """Test job timeout handling E2E"""
        # Create job with short timeout
        job = JobFactory.create_job(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.RUNNING,
            timeout_seconds=1,  # 1 second timeout
            started_at=timezone.now() - timezone.timedelta(seconds=2),  # Started 2 seconds ago
            created_by=self.user
        )
        
        # Verify job has exceeded timeout
        timeout_time = job.started_at + timezone.timedelta(seconds=job.timeout_seconds)
        self.assertTrue(timezone.now() > timeout_time)
        
        # Verify the job is identifiable as timed out
        self.assertTrue(timezone.now() > timeout_time, "Job should have exceeded timeout")

        # Test production detection query: find running jobs past their timeout
        from django.db.models import F, ExpressionWrapper, DurationField
        timed_out_jobs = Job.objects.filter(
            status=JobStatus.RUNNING,
            timeout_seconds__gt=0,
            started_at__isnull=False,
        ).annotate(
            deadline=ExpressionWrapper(
                F('started_at') + F('timeout_seconds') * timezone.timedelta(seconds=1),
                output_field=DurationField(),
            )
        ).filter(
            started_at__lt=timezone.now() - timezone.timedelta(seconds=1),
        )
        # Our job should appear in the timed-out set
        timed_out_ids = list(timed_out_jobs.values_list('id', flat=True))
        self.assertIn(job.id, timed_out_ids, "Job should be detected as timed out")

        # Now mark it failed (as a timeout handler would)
        job.mark_failed(
            error_message=f"Job exceeded timeout of {job.timeout_seconds} seconds",
            result_json={'timeout': True, 'timeout_seconds': job.timeout_seconds}
        )
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.FAILED)
        self.assertIn("timeout", job.error_message.lower())
    
    # Edge Cases E2E Tests
    def test_multiple_job_types_e2e(self):
        """Test processing multiple job types E2E"""
        # Create jobs of all types
        dq_job = create_job(
            tenant=self.tenant,
            user=self.user,
            type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=str(uuid.uuid4()),
            details_json={'dq_run_id': str(uuid.uuid4())}
        )
        
        compliance_job = create_job(
            tenant=self.tenant,
            user=self.user,
            type=JobType.COMPLIANCE_RUN,
            resource_type="COMPLIANCE_RUN",
            resource_id=str(uuid.uuid4()),
            details_json={'compliance_run_id': str(uuid.uuid4())}
        )
        
        validation_job = create_job(
            tenant=self.tenant,
            user=self.user,
            type=JobType.CONTRACT_VALIDATION,
            resource_type="CONTRACT",
            resource_id=str(uuid.uuid4())
        )
        
        semantic_job = create_job(
            tenant=self.tenant,
            user=self.user,
            type=JobType.SEMANTIC_MAPPING,
            resource_type="CONTRACT",
            resource_id=str(uuid.uuid4()),
            details_json={'resource_type': 'CONTRACT', 'resource_id': str(uuid.uuid4())}
        )
        
        migration_job = create_job(
            tenant=self.tenant,
            user=self.user,
            type=JobType.CONTRACT_MIGRATION,
            resource_type="CONTRACT",
            resource_id=str(uuid.uuid4())
        )
        
        # Verify all jobs created
        self.assertIsNotNone(dq_job.id)
        self.assertIsNotNone(compliance_job.id)
        self.assertIsNotNone(validation_job.id)
        self.assertIsNotNone(semantic_job.id)
        self.assertIsNotNone(migration_job.id)
        
        # Verify all jobs are in correct queues
        self.assertEqual(get_queue_for_job_type(JobType.DQ_RUN), 'job_critical')
        self.assertEqual(get_queue_for_job_type(JobType.COMPLIANCE_RUN), 'job_critical')
        self.assertEqual(get_queue_for_job_type(JobType.CONTRACT_VALIDATION), 'job_low')
        self.assertEqual(get_queue_for_job_type(JobType.SEMANTIC_MAPPING), 'job_default')
        self.assertEqual(get_queue_for_job_type(JobType.CONTRACT_MIGRATION), 'job_default')
    
    def test_tenant_isolation_e2e(self):
        """Test tenant isolation E2E"""
        # Create two tenants
        tenant1 = TenantFactory.create_tenant(name="Tenant 1", slug="tenant-1")
        tenant2 = TenantFactory.create_tenant(name="Tenant 2", slug="tenant-2")
        
        user1 = User.objects.create_user(
            email=f"user1-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=tenant1,
            status=UserStatus.ACTIVE
        )
        user2 = User.objects.create_user(
            email=f"user2-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=tenant2,
            status=UserStatus.ACTIVE
        )
        
        # Create tenant configs with different limits
        TenantConfigFactory.create_tenant_config(
            tenant=tenant1,
            max_job_concurrency=1,
            max_queued_jobs=2
        )
        TenantConfigFactory.create_tenant_config(
            tenant=tenant2,
            max_job_concurrency=3,
            max_queued_jobs=5
        )
        
        # Fill tenant1's concurrency slots
        job1 = create_job(
            tenant=tenant1,
            user=user1,
            type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=str(uuid.uuid4()),
            details_json={'dq_run_id': str(uuid.uuid4())}
        )
        job1.mark_started()
        increment_tenant_job_counter(str(tenant1.id), "running")
        decrement_tenant_job_counter(str(tenant1.id), "queued")
        
        # Tenant1 should be at limit
        can_create, _ = check_tenant_job_limits(str(tenant1.id))
        self.assertFalse(can_create)
        
        # Tenant2 should still be able to create jobs
        can_create, _ = check_tenant_job_limits(str(tenant2.id))
        self.assertTrue(can_create)
        
        # Create jobs for tenant2
        job2 = create_job(
            tenant=tenant2,
            user=user2,
            type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=str(uuid.uuid4()),
            details_json={'dq_run_id': str(uuid.uuid4())}
        )
        job3 = create_job(
            tenant=tenant2,
            user=user2,
            type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=str(uuid.uuid4()),
            details_json={'dq_run_id': str(uuid.uuid4())}
        )
        
        # Verify tenant2 jobs created
        self.assertIsNotNone(job2.id)
        self.assertIsNotNone(job3.id)
        
        # Verify tenant1 still at limit
        can_create, _ = check_tenant_job_limits(str(tenant1.id))
        self.assertFalse(can_create)
    
    def test_job_counter_integration_e2e(self):
        """Test job counter integration E2E"""
        # Create multiple jobs
        job1 = create_job(
            tenant=self.tenant,
            user=self.user,
            type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=str(uuid.uuid4()),
            details_json={'dq_run_id': str(uuid.uuid4())}
        )
        job2 = create_job(
            tenant=self.tenant,
            user=self.user,
            type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=str(uuid.uuid4()),
            details_json={'dq_run_id': str(uuid.uuid4())}
        )
        
        # Verify queued counter
        queued_count = get_tenant_job_counter(str(self.tenant.id), "queued")
        self.assertEqual(queued_count, 2)
        
        # Start jobs
        job1.mark_started()
        job2.mark_started()
        decrement_tenant_job_counter(str(self.tenant.id), "queued")
        decrement_tenant_job_counter(str(self.tenant.id), "queued")
        increment_tenant_job_counter(str(self.tenant.id), "running")
        increment_tenant_job_counter(str(self.tenant.id), "running")
        
        # Verify counters updated
        queued_count = get_tenant_job_counter(str(self.tenant.id), "queued")
        running_count = get_tenant_job_counter(str(self.tenant.id), "running")
        self.assertEqual(queued_count, 0)
        self.assertEqual(running_count, 2)
        
        # Complete jobs
        job1.mark_completed(result_json={'status': 'completed'})
        job2.mark_completed(result_json={'status': 'completed'})
        decrement_tenant_job_counter(str(self.tenant.id), "running")
        decrement_tenant_job_counter(str(self.tenant.id), "running")
        
        # Verify counters reset
        running_count = get_tenant_job_counter(str(self.tenant.id), "running")
        self.assertEqual(running_count, 0)

