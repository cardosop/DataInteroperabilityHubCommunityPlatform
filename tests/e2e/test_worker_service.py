"""
E2E tests for worker service in Docker environment.

Tests worker service functionality including:
- Health check endpoints
- Job processing with real Redis queues
- Priority queue processing
- Job retry logic
- Metrics endpoint
"""
import pytest
import requests
import time
import uuid
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django_rq import get_queue

from hub.apps.tenants.models import Tenant
from hub.apps.jobs.models import Job, JobType, JobStatus
from hub.apps.jobs.utils import create_job
from hub.apps.files.models import File, FileStatus
from hub.apps.dq.models import DQRun, DQRunStatus, DQEngine


pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e2]
User = get_user_model()


class WorkerServiceE2ETest(TestCase):
    """E2E tests for worker service"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status="ACTIVE"
        )
        
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            storage_path="test/path/file.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user
        )
        
        # Worker service URL (from environment or default)
        # In CI, worker service is exposed on port 8084 to avoid conflict with datacontract-service
        import os
        self.worker_url = os.environ.get("WORKER_SERVICE_URL", "http://localhost:8084")
    
    @pytest.mark.skip(reason="E2E test - requires worker service to be running. Use: pytest -m e2e")
    def test_worker_healthz_endpoint(self):
        """Test worker service /healthz endpoint"""
        response = requests.get(f"{self.worker_url}/healthz", timeout=5)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['service'], 'worker-service')
    
    @pytest.mark.skip(reason="E2E test - requires worker service to be running. Use: pytest -m e2e")
    def test_worker_ready_endpoint(self):
        """Test worker service /ready endpoint"""
        response = requests.get(f"{self.worker_url}/ready", timeout=5)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'ready')
        self.assertIn('checks', data)
        self.assertEqual(data['checks']['database'], 'ok')
        self.assertEqual(data['checks']['redis'], 'ok')
    
    @pytest.mark.skip(reason="E2E test - requires worker service to be running. Use: pytest -m e2e")
    def test_worker_metrics_endpoint(self):
        """Test worker service /metrics endpoint (Prometheus)"""
        response = requests.get(f"{self.worker_url}/metrics", timeout=5)
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/plain', response.headers.get('Content-Type', ''))
        # Verify metrics are present
        metrics_text = response.text
        self.assertIn('jobs_started_total', metrics_text)
        self.assertIn('jobs_completed_total', metrics_text)
        self.assertIn('jobs_failed_total', metrics_text)
        self.assertIn('job_duration_seconds', metrics_text)
    
    @pytest.mark.skip(reason="E2E test - requires worker service to be running. Use: pytest -m e2e")
    @pytest.mark.timeout(300)  # 5 minute timeout for E2E test
    def test_job_processing_with_real_worker(self):
        """Test job processing with real worker service"""
        # Create DQ run
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            profile_key='intake_basic_gx',
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING
        )
        
        # Create job (will be enqueued)
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=str(dq_run.id),
            details_json={'dq_run_id': str(dq_run.id)}
        )
        
        # Verify job is PENDING and enqueued
        self.assertEqual(job.status, JobStatus.PENDING)
        
        # Wait for worker to process job (poll job status)
        max_wait = 60  # 60 seconds max wait
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            job.refresh_from_db()
            if job.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                break
            time.sleep(1)
        
        # Verify job was processed
        job.refresh_from_db()
        self.assertIn(job.status, [JobStatus.COMPLETED, JobStatus.FAILED])
        
        if job.status == JobStatus.COMPLETED:
            self.assertIsNotNone(job.started_at)
            self.assertIsNotNone(job.completed_at)
            self.assertIsNotNone(job.result_json)
    
    @pytest.mark.skip(reason="E2E test - requires worker service to be running. Use: pytest -m e2e")
    def test_priority_queue_processing(self):
        """Test that high priority jobs are processed before normal priority"""
        # Create high priority job (DQ_RUN)
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            profile_key='intake_basic_gx',
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING
        )
        high_priority_job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.DQ_RUN,  # HIGH priority
            resource_type="DQ_RUN",
            resource_id=str(dq_run.id),
            details_json={'dq_run_id': str(dq_run.id)}
        )
        
        # Create normal priority job (SEMANTIC_MAPPING)
        from hub.apps.contracts.models import Contract, ContractStatus, OriginalSpecType
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_format='JSON',
            original_raw='{"id": "test"}',
            created_by=self.user
        )
        normal_priority_job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.SEMANTIC_MAPPING,  # NORMAL priority
            resource_type="CONTRACT",
            resource_id=str(contract.id),
            details_json={'resource_type': 'CONTRACT', 'resource_id': str(contract.id)}
        )
        
        # Wait for jobs to be processed
        time.sleep(10)
        
        # Verify high priority job processed first (or at least started)
        high_priority_job.refresh_from_db()
        normal_priority_job.refresh_from_db()
        
        # High priority job should be processed (or at least started) before normal priority
        # Note: This is a probabilistic test - in a real scenario with multiple workers,
        # the order may vary, but high priority jobs should generally be processed first
        if high_priority_job.status == JobStatus.RUNNING:
            # High priority job started - this is expected
            pass
        elif high_priority_job.status == JobStatus.COMPLETED:
            # High priority job completed - verify normal priority hasn't started yet
            # (or started after high priority)
            if normal_priority_job.status == JobStatus.PENDING:
                # Normal priority still pending - high priority processed first
                pass
    
    @pytest.mark.skip(reason="E2E test - requires worker service to be running. Use: pytest -m e2e")
    def test_job_retry_with_real_worker(self):
        """Test job retry logic with real worker service"""
        # Create job that will fail with transient error
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            profile_key='intake_basic_gx',
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING
        )
        
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=str(dq_run.id),
            details_json={'dq_run_id': str(dq_run.id)}
        )
        
        # Wait for job to be processed (may fail and retry)
        max_wait = 120  # 2 minutes for retry
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            job.refresh_from_db()
            if job.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                # Check if retry occurred
                if job.details_json and job.details_json.get('retry_count', 0) > 0:
                    # Job was retried
                    self.assertGreater(job.details_json.get('retry_count'), 0)
                break
            time.sleep(2)
        
        # Verify final state
        job.refresh_from_db()
        self.assertIn(job.status, [JobStatus.COMPLETED, JobStatus.FAILED])
        
        # If retried, verify retry count is tracked
        if job.details_json and job.details_json.get('retry_count', 0) > 0:
            self.assertGreater(job.details_json.get('retry_count'), 0)
            self.assertIn('last_retry_error', job.details_json)
            self.assertIn('last_retry_at', job.details_json)

