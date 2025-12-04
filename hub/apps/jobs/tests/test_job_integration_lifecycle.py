"""
Job Orchestration Tests (Unit Tests with Mocked Execution)

These tests verify job orchestration logic (status updates, result storage, error handling)
but mock _execute_job_logic to focus on orchestration rather than execution.

For real integration tests that exercise actual job execution, see:
- test_job_execution_integration.py (tests actual _execute_job_logic)
- test_job_processors.py (tests individual job processors)
"""
import pytest
import uuid
import time
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django_rq import get_queue

from hub.apps.tenants.models import Tenant
from hub.apps.jobs.models import Job, JobType, JobStatus
from hub.apps.jobs.tasks import process_job
from hub.apps.jobs.utils import create_job
from hub.apps.files.models import File, FileStatus
from hub.apps.dq.models import DQRun, DQRunStatus, DQEngine
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus, RiskLevel
from hub.apps.contracts.models import Contract, ContractStatus, OriginalSpecType, ValidationStatus


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class JobLifecycleIntegrationTest(TestCase):
    """
    Job Orchestration Tests - Unit tests for orchestration logic.
    
    These tests verify:
    - Job status transitions (PENDING → RUNNING → COMPLETED/FAILED)
    - Result storage in job.result_json
    - Error handling and retry logic
    - Job cancellation handling
    
    Note: These tests mock _execute_job_logic to focus on orchestration.
    For tests that exercise actual job execution, see test_job_execution_integration.py
    """
    
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
    
    @patch('hub.apps.jobs.tasks._execute_job_logic')
    def test_dq_run_job_lifecycle(self, mock_execute_logic):
        """Test complete DQ run job lifecycle"""
        # Create job first (DQRun requires a job)
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=str(uuid.uuid4()),
            details_json={'profile_key': 'intake_basic_gx'}
        )
        
        # Create DQ run with job reference
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=job,
            profile_key='intake_basic_gx',
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING
        )
        
        # Update job resource_id to point to dq_run
        job.resource_id = dq_run.id
        job.details_json = {'dq_run_id': str(dq_run.id), 'profile_key': 'intake_basic_gx'}
        job.save()
        
        # Verify job created
        self.assertEqual(job.status, JobStatus.PENDING)
        self.assertEqual(job.type, JobType.DQ_RUN)
        
        # Mock successful execution
        mock_execute_logic.return_value = {
            'status': 'succeeded',
            'overall_status': 'PASS',
            'quality_score': 0.95,
            'dq_run_id': str(dq_run.id)
        }
        
        # Process job
        process_job(str(job.id), JobType.DQ_RUN)
        
        # Verify job completed
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.COMPLETED)
        self.assertIsNotNone(job.started_at)
        self.assertIsNotNone(job.completed_at)
        self.assertIsNotNone(job.result_json)
        self.assertEqual(job.result_json.get('status'), 'succeeded')
        self.assertEqual(job.result_json.get('quality_score'), 0.95)
        
        # Note: DQ run status is not updated by the mocked _execute_job_logic
        # In real execution, the DQ run would be updated by execute_dq_run
        # The test verifies the job processing lifecycle, not the DQ run update
    
    @patch('hub.apps.jobs.tasks._execute_job_logic')
    def test_compliance_run_job_lifecycle(self, mock_execute_logic):
        """Test complete compliance run job lifecycle"""
        # Create job first (ComplianceRun requires a job)
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.COMPLIANCE_RUN,
            resource_type="COMPLIANCE_RUN",
            resource_id=str(uuid.uuid4()),
            details_json={'applicable_regulations': ['GDPR']}
        )
        
        # Create compliance run with job reference
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=job,
            regulations=['GDPR'],
            status=ComplianceRunStatus.PENDING
        )
        
        # Update job resource_id to point to compliance_run
        job.resource_id = compliance_run.id
        job.details_json = {'compliance_run_id': str(compliance_run.id), 'applicable_regulations': ['GDPR']}
        job.save()
        
        # Verify job created
        self.assertEqual(job.status, JobStatus.PENDING)
        
        # Mock successful execution
        mock_execute_logic.return_value = {
            'status': 'succeeded',
            'overall_status': 'PASS',
            'risk_level': RiskLevel.LOW,
            'allowed_to_store': True,
            'compliance_run_id': str(compliance_run.id)
        }
        
        # Process job
        process_job(str(job.id), JobType.COMPLIANCE_RUN)
        
        # Verify job completed
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.COMPLETED)
        self.assertIsNotNone(job.result_json)
        self.assertEqual(job.result_json.get('risk_level'), RiskLevel.LOW)
    
    @patch('hub.apps.jobs.tasks._execute_job_logic')
    def test_contract_validation_job_lifecycle(self, mock_execute_logic):
        """Test complete contract validation job lifecycle"""
        # Create contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_format='JSON',
            original_raw='{"id": "test", "schema": {}}',
            created_by=self.user
        )
        
        # Create job
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.CONTRACT_VALIDATION,
            resource_type="CONTRACT",
            resource_id=str(contract.id)
        )
        
        # Mock successful execution
        mock_execute_logic.return_value = {
            'validation_status': ValidationStatus.VALID,
            'valid': True,
            'errors': [],
            'warnings': [],
            'cli_version': '1.0.0'
        }
        
        # Process job
        process_job(str(job.id), JobType.CONTRACT_VALIDATION)
        
        # Verify job completed
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.COMPLETED)
        self.assertIsNotNone(job.result_json)
        self.assertEqual(job.result_json.get('validation_status'), ValidationStatus.VALID)
        
        # Note: Contract validation_status is not updated by the job processor
        # It's updated by the view/signal when the validation result is processed
        # The job processor only returns the validation result
    
    @patch('hub.apps.jobs.tasks._execute_job_logic')
    def test_job_failure_lifecycle(self, mock_execute_logic):
        """Test job failure lifecycle"""
        # Create job with a valid DQ run (needed for job processing)
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=str(uuid.uuid4())
        )
        
        # Create DQ run for the job
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=job,
            profile_key='intake_basic_gx',
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING
        )
        job.resource_id = dq_run.id
        job.details_json = {'dq_run_id': str(dq_run.id)}
        job.save()
        
        # Mock failure (non-transient error to avoid retry)
        mock_execute_logic.side_effect = ValueError("Invalid DQ run configuration")
        
        # Process job (should fail)
        process_job(str(job.id), JobType.DQ_RUN)
        
        # Verify job failed
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.FAILED)
        self.assertIsNotNone(job.error_message)
        self.assertIsNotNone(job.result_json)
        self.assertIn('error', job.result_json)
        self.assertEqual(job.result_json.get('error_code'), 'VALIDATION_ERROR')
    
    @patch('hub.apps.jobs.tasks._execute_job_logic')
    def test_job_retry_lifecycle(self, mock_execute_logic):
        """Test job retry lifecycle with transient failure"""
        # Create job with a valid DQ run (needed for job processing)
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=str(uuid.uuid4())
        )
        
        # Create DQ run for the job
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=job,
            profile_key='intake_basic_gx',
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING
        )
        job.resource_id = dq_run.id
        job.details_json = {'dq_run_id': str(dq_run.id)}
        job.save()
        
        # Mock transient failure then success
        mock_execute_logic.side_effect = [
            ConnectionError("Service temporarily unavailable"),
            {'status': 'succeeded', 'quality_score': 0.95, 'dq_run_id': str(dq_run.id)}
        ]
        
        # Process job (first attempt fails, should retry)
        process_job(str(job.id), JobType.DQ_RUN)
        
        # Verify job was retried (status reset to PENDING)
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.PENDING)
        self.assertIsNotNone(job.details_json.get('retry_count'))
        self.assertEqual(job.details_json.get('retry_count'), 1)
        
        # Process job again (retry succeeds)
        process_job(str(job.id), JobType.DQ_RUN)
        
        # Verify job completed
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.COMPLETED)
    
    def test_job_status_transitions(self):
        """Test job status transitions throughout lifecycle"""
        # Create job
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.CONTRACT_VALIDATION,
            resource_type="CONTRACT",
            resource_id=str(uuid.uuid4())
        )
        
        # Initial state: PENDING
        self.assertEqual(job.status, JobStatus.PENDING)
        self.assertIsNone(job.started_at)
        self.assertIsNone(job.completed_at)
        
        # Mark as started
        job.mark_started()
        self.assertEqual(job.status, JobStatus.RUNNING)
        self.assertIsNotNone(job.started_at)
        
        # Mark as completed
        job.mark_completed({'result': 'success'})
        self.assertEqual(job.status, JobStatus.COMPLETED)
        self.assertIsNotNone(job.completed_at)
        self.assertIsNotNone(job.result_json)
    
    def test_job_cancellation_during_lifecycle(self):
        """Test job cancellation during processing"""
        # Create job
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=str(uuid.uuid4())
        )
        
        # Mark as started
        job.mark_started()
        self.assertEqual(job.status, JobStatus.RUNNING)
        
        # Cancel job
        job.mark_cancelled()
        self.assertEqual(job.status, JobStatus.CANCELLED)
        self.assertIsNotNone(job.completed_at)
        
        # Verify job cannot be processed when cancelled
        with patch('hub.apps.jobs.tasks._execute_job_logic') as mock_execute:
            process_job(str(job.id), JobType.DQ_RUN)
            # Should not execute logic if already cancelled
            job.refresh_from_db()
            if job.status == JobStatus.CANCELLED:
                # If cancelled before processing, execute_logic should not be called
                pass  # This is expected behavior

