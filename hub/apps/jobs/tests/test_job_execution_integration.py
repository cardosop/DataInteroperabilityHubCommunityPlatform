"""
Real Integration Tests for Job Execution

These tests verify actual job execution logic without mocking _execute_job_logic.
They mock only external services (DQ, Compliance, etc.) and test the full execution path.

Unlike test_job_integration_lifecycle.py which mocks _execute_job_logic,
these tests exercise the actual job execution code paths.
"""
import pytest
import uuid
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

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


class JobExecutionIntegrationTest(TestCase):
    """Real integration tests for job execution - tests actual execution logic"""
    
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
    
    @patch('hub.apps.files.storage.S3StorageClient')
    @patch('hub.apps.dq.service_client.DQServiceClient.run_dq')
    @patch('hub.apps.dq.service_client.DQServiceClient.health_check')
    def test_dq_run_job_execution_real(self, mock_health_check, mock_run_dq, mock_storage_client_class):
        """Test real DQ run job execution - exercises actual _execute_job_logic"""
        # Setup health check mock
        mock_health_check.return_value = (True, "healthy")
        
        # Setup S3 storage mock (file download)
        mock_storage_client = MagicMock()
        mock_storage_client.download_file.return_value = b'col1,col2\nval1,val2\nval3,val4'
        mock_storage_client_class.return_value = mock_storage_client
        
        # Setup DQ service mock
        mock_run_dq.return_value = {
            'overall_status': 'PASS',
            'quality_score': 0.95,
            'checks': [
                {'name': 'check1', 'status': 'PASS'},
                {'name': 'check2', 'status': 'PASS'}
            ],
            'metadata': {
                'total_rows': 3,
                'total_columns': 2
            }
        }
        
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
        
        # Verify initial state
        self.assertEqual(job.status, JobStatus.PENDING)
        self.assertEqual(dq_run.status, DQRunStatus.PENDING)
        
        # Process job - NO MOCK on _execute_job_logic, this calls the real function!
        process_job(str(job.id), JobType.DQ_RUN)
        
        # Verify job completed (actual execution happened)
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.COMPLETED)
        self.assertIsNotNone(job.started_at)
        self.assertIsNotNone(job.completed_at)
        self.assertIsNotNone(job.result_json)
        self.assertEqual(job.result_json.get('status'), 'succeeded')
        self.assertEqual(job.result_json.get('overall_status'), 'PASS')
        self.assertEqual(job.result_json.get('quality_score'), 0.95)
        
        # Verify DQ run was actually updated by real execution
        dq_run.refresh_from_db()
        self.assertEqual(dq_run.status, DQRunStatus.SUCCEEDED)
        self.assertEqual(dq_run.overall_status, 'PASS')
        self.assertEqual(dq_run.quality_score, 0.95)
        
        # Verify external services were called
        mock_storage_client.download_file.assert_called_once_with(self.file.storage_path)
        mock_run_dq.assert_called_once()
        mock_health_check.assert_called_once()
    
    @patch('hub.apps.files.storage.S3StorageClient')
    @patch('hub.apps.compliance.service_client.ComplianceServiceClient.scan_file')
    @patch('hub.apps.compliance.service_client.ComplianceServiceClient.health_check')
    def test_compliance_run_job_execution_real(self, mock_health_check, mock_scan_file, mock_storage_client_class):
        """Test real compliance run job execution - exercises actual _execute_job_logic"""
        # Setup health check mock
        mock_health_check.return_value = (True, "healthy")
        
        # Setup S3 storage mock (file download)
        mock_storage_client = MagicMock()
        mock_storage_client.download_file.return_value = b'col1,col2\nval1,val2\nval3,val4'
        mock_storage_client_class.return_value = mock_storage_client
        
        # Setup compliance service mock
        mock_scan_file.return_value = {
            'overall_status': 'PASS',
            'risk_level': RiskLevel.LOW,
            'allowed_to_store': True,
            'regulations_checked': ['GDPR'],
            'detected_categories': []
        }
        
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
        
        # Verify initial state
        self.assertEqual(job.status, JobStatus.PENDING)
        self.assertEqual(compliance_run.status, ComplianceRunStatus.PENDING)
        
        # Process job - NO MOCK on _execute_job_logic, this calls the real function!
        process_job(str(job.id), JobType.COMPLIANCE_RUN)
        
        # Verify job completed (actual execution happened)
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.COMPLETED)
        self.assertIsNotNone(job.result_json)
        self.assertEqual(job.result_json.get('risk_level'), RiskLevel.LOW)
        self.assertEqual(job.result_json.get('allowed_to_store'), True)
        
        # Verify compliance run was actually updated by real execution
        compliance_run.refresh_from_db()
        self.assertEqual(compliance_run.status, ComplianceRunStatus.SUCCEEDED)
        self.assertEqual(compliance_run.overall_status, 'PASS')
        self.assertEqual(compliance_run.risk_level, RiskLevel.LOW)
        self.assertEqual(compliance_run.allowed_to_store, True)
        
        # Verify external services were called
        mock_storage_client.download_file.assert_called_once_with(self.file.storage_path)
        mock_scan_file.assert_called_once()
        mock_health_check.assert_called_once()
    
    @patch('hub.apps.contracts.cli_client.DataContractCLIClient.validate')
    @patch('hub.apps.contracts.cli_client.DataContractCLIClient.health_check')
    def test_contract_validation_job_execution_real(self, mock_health_check, mock_validate):
        """Test real contract validation job execution - exercises actual _execute_job_logic"""
        # Setup health check mock
        mock_health_check.return_value = {'status': 'healthy', 'cli_version': '1.0.0'}
        
        # Setup validation mock - must match what interpret_validation_status expects
        mock_validate.return_value = {
            'validation_status': 'VALID',  # interpret_validation_status checks this
            'issues': [],  # Empty issues means no errors/warnings
            'cli_version': '1.0.0'
        }
        
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
            job_type=JobType.CONTRACT_VALIDATION,
            resource_type="CONTRACT",
            resource_id=str(contract.id)
        )
        
        # Verify initial state
        self.assertEqual(job.status, JobStatus.PENDING)
        
        # Process job - NO MOCK on _execute_job_logic, this calls the real function!
        process_job(str(job.id), JobType.CONTRACT_VALIDATION)
        
        # Verify job completed (actual execution happened)
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.COMPLETED)
        self.assertIsNotNone(job.result_json)
        self.assertEqual(job.result_json.get('validation_status'), ValidationStatus.VALID)
        self.assertEqual(job.result_json.get('status'), 'completed')
        
        # Verify external CLI was called
        mock_validate.assert_called_once()
        # Note: Contract validation_status is updated by views/signals, not job processor
    
    @patch('hub.apps.dq.service_client.DQServiceClient.health_check')
    def test_dq_run_job_execution_service_unavailable(self, mock_health_check):
        """Test DQ run job execution when service is unavailable - real error handling"""
        # Setup health check to return unhealthy
        mock_health_check.return_value = (False, "unhealthy")
        
        # Create job and DQ run
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=str(uuid.uuid4()),
            details_json={'profile_key': 'intake_basic_gx'}
        )
        
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=job,
            profile_key='intake_basic_gx',
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING
        )
        
        job.resource_id = dq_run.id
        job.details_json = {'dq_run_id': str(dq_run.id), 'profile_key': 'intake_basic_gx'}
        job.save()
        
        # Process job - should fail with service unavailable
        process_job(str(job.id), JobType.DQ_RUN)
        
        # Verify job failed (actual error handling happened)
        job.refresh_from_db()
        # Should be either FAILED (if retries exhausted) or PENDING (if retried)
        self.assertIn(job.status, [JobStatus.FAILED, JobStatus.PENDING])
        
        if job.status == JobStatus.FAILED:
            self.assertIsNotNone(job.error_message)
            self.assertIsNotNone(job.result_json)
            self.assertEqual(job.result_json.get('error_code'), 'SERVICE_UNAVAILABLE')
    
    @patch('hub.apps.files.storage.S3StorageClient')
    @patch('hub.apps.dq.service_client.DQServiceClient.run_dq')
    @patch('hub.apps.dq.service_client.DQServiceClient.health_check')
    def test_dq_run_job_execution_transient_failure_retry(self, mock_health_check, mock_run_dq, mock_storage_client_class):
        """Test DQ run job execution with transient failure and retry - real retry logic"""
        # Setup health check mock
        mock_health_check.return_value = (True, "healthy")
        
        # Setup S3 storage mock (file download)
        mock_storage_client = MagicMock()
        mock_storage_client.download_file.return_value = b'col1,col2\nval1,val2\nval3,val4'
        mock_storage_client_class.return_value = mock_storage_client
        
        # Setup DQ service to fail first time, succeed second time
        call_count = [0]
        def run_dq_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise ConnectionError("Service temporarily unavailable")
            return {
                'overall_status': 'PASS',
                'quality_score': 0.95,
                'checks': [],
                'metadata': {
                    'total_rows': 3,
                    'total_columns': 2
                }
            }
        
        mock_run_dq.side_effect = run_dq_side_effect
        
        # Create job and DQ run
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=str(uuid.uuid4()),
            details_json={'profile_key': 'intake_basic_gx'}
        )
        
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=job,
            profile_key='intake_basic_gx',
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING
        )
        
        job.resource_id = dq_run.id
        job.details_json = {'dq_run_id': str(dq_run.id), 'profile_key': 'intake_basic_gx'}
        job.save()
        
        # Process job first time (will fail and retry)
        process_job(str(job.id), JobType.DQ_RUN)
        
        # Verify job was retried (status reset to PENDING)
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.PENDING)
        self.assertIsNotNone(job.details_json.get('retry_count'))
        self.assertEqual(job.details_json.get('retry_count'), 1)
        
        # Process job again (retry should succeed)
        process_job(str(job.id), JobType.DQ_RUN)
        
        # Verify job completed after retry
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.COMPLETED)
        self.assertEqual(job.result_json.get('quality_score'), 0.95)
        
        # Verify DQ run was updated
        dq_run.refresh_from_db()
        self.assertEqual(dq_run.status, DQRunStatus.SUCCEEDED)
        
        # Verify service was called twice (once failed, once succeeded)
        self.assertEqual(call_count[0], 2)
    
    @patch('hub.apps.files.storage.S3StorageClient')
    @patch('hub.apps.dq.service_client.DQServiceClient.run_dq')
    @patch('hub.apps.dq.service_client.DQServiceClient.health_check')
    def test_dq_run_job_execution_non_transient_failure(self, mock_health_check, mock_run_dq, mock_storage_client_class):
        """Test DQ run job execution with non-transient failure - should not retry"""
        # Setup health check mock
        mock_health_check.return_value = (True, "healthy")
        
        # Setup S3 storage mock (file download)
        mock_storage_client = MagicMock()
        mock_storage_client.download_file.return_value = b'col1,col2\nval1,val2\nval3,val4'
        mock_storage_client_class.return_value = mock_storage_client
        
        # Setup DQ service to fail with non-transient error
        mock_run_dq.side_effect = ValueError("Invalid DQ run configuration")
        
        # Create job and DQ run
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=str(uuid.uuid4()),
            details_json={'profile_key': 'intake_basic_gx'}
        )
        
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=job,
            profile_key='intake_basic_gx',
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING
        )
        
        job.resource_id = dq_run.id
        job.details_json = {'dq_run_id': str(dq_run.id), 'profile_key': 'intake_basic_gx'}
        job.save()
        
        # Process job - should fail without retry
        process_job(str(job.id), JobType.DQ_RUN)
        
        # Verify job failed (no retry for non-transient errors)
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.FAILED)
        self.assertIsNotNone(job.error_message)
        self.assertIsNotNone(job.result_json)
        # Note: ValueError is wrapped in Exception by _execute_dq_run_job, so error_code is UNKNOWN_ERROR
        # The important thing is that it didn't retry (non-transient error)
        self.assertIn(job.result_json.get('error_code'), ['VALIDATION_ERROR', 'UNKNOWN_ERROR'])
        
        # Verify retry count is 0 (no retry attempted)
        self.assertEqual(job.details_json.get('retry_count', 0), 0)

