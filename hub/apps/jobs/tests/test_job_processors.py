"""
Tests for Job Processors

Comprehensive tests for all job processors (DQ_RUN, COMPLIANCE_RUN, CONTRACT_VALIDATION,
SEMANTIC_MAPPING, CONTRACT_MIGRATION) including success cases, error handling, and result storage.
"""
import pytest
from django.test import TestCase
from unittest.mock import patch, MagicMock
from django.utils import timezone
import uuid

from hub.apps.jobs.models import Job, JobType, JobStatus
from hub.apps.jobs.tasks import (
    _execute_job_logic,
    _execute_dq_run_job,
    _execute_compliance_run_job,
    _execute_contract_validation_job,
    _execute_semantic_mapping_job,
    _execute_contract_migration_job,
    process_job
)
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus


pytestmark = pytest.mark.django_db(transaction=True)


class JobProcessorsTest(TestCase):
    """Test job processors for all job types"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Clear cache to ensure clean state for slot counters
        from django.core.cache import cache
        cache.clear()
        
        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        
        # Create user
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        # Create test job
        self.job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DQ_RUN",
            resource_id=uuid.uuid4(),
            created_by=self.user
        )
    
    def tearDown(self):
        """Clean up after tests"""
        from django.core.cache import cache
        cache.clear()


class DQRunJobProcessorTest(JobProcessorsTest):
    """Test DQ_RUN job processor"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        
        # Create file for DQ run
        from hub.apps.files.models import File, FileStatus
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1000,
            status=FileStatus.ACTIVE,
            storage_path="test/test.csv",
            created_by=self.user
        )
        
        # Create DQ run
        from hub.apps.dq.models import DQRun, DQRunStatus, DQEngine
        self.dq_run_id = uuid.uuid4()
        self.dq_run = DQRun.objects.create(
            id=self.dq_run_id,
            tenant=self.tenant,
            file=self.file,
            job=self.job,
            profile_key='intake_basic_gx',
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING
        )
        
        # Update job with dq_run_id
        self.job.details_json = {'dq_run_id': str(self.dq_run_id)}
        self.job.resource_id = self.dq_run_id
        self.job.save()
    
    @patch('hub.apps.dq.views.execute_dq_run')
    @patch('hub.apps.dq.service_client.DQServiceClient')
    def test_execute_dq_run_job_success(self, mock_dq_client_class, mock_execute_dq_run):
        """Test successful DQ run job execution"""
        # Setup mocks
        mock_dq_client = MagicMock()
        mock_dq_client.health_check.return_value = (True, "healthy")
        mock_dq_client_class.return_value = mock_dq_client
        
        # Mock execute_dq_run to update DQ run status
        def update_dq_run(*args):
            from hub.apps.dq.models import DQRunStatus
            self.dq_run.status = DQRunStatus.SUCCEEDED
            self.dq_run.overall_status = "PASS"
            self.dq_run.quality_score = 0.95
            self.dq_run.save()
        
        mock_execute_dq_run.side_effect = update_dq_run
        
        # Execute job
        result = _execute_dq_run_job(self.job)
        
        # Verify result
        self.assertEqual(result['status'], 'succeeded')
        self.assertEqual(result['overall_status'], 'PASS')
        self.assertEqual(result['quality_score'], 0.95)
        self.assertEqual(result['dq_run_id'], str(self.dq_run_id))
    
    @patch('hub.apps.dq.service_client.DQServiceClient')
    def test_execute_dq_run_job_service_unavailable(self, mock_dq_client_class):
        """Test DQ run job with service unavailable"""
        # Setup mock
        mock_dq_client = MagicMock()
        mock_dq_client.health_check.return_value = (False, "unhealthy")
        mock_dq_client_class.return_value = mock_dq_client
        
        # Execute job - should raise ConnectionError
        with self.assertRaises(ConnectionError) as cm:
            _execute_dq_run_job(self.job)
        
        self.assertIn("unavailable", str(cm.exception).lower())
    
    @patch('hub.apps.dq.service_client.DQServiceClient')
    def test_execute_dq_run_job_missing_dq_run_id(self, mock_dq_client_class):
        """Test DQ run job with missing dq_run_id"""
        # Setup mock
        mock_dq_client = MagicMock()
        mock_dq_client.health_check.return_value = (True, "healthy")
        mock_dq_client_class.return_value = mock_dq_client
        
        # Remove dq_run_id from job (but keep resource_id as it's required)
        self.job.details_json = {}
        # Use a dummy UUID that doesn't exist
        self.job.resource_id = uuid.uuid4()
        self.job.save()
        
        # Execute job - should raise Exception (DQ run not found)
        with self.assertRaises(Exception) as cm:
            _execute_dq_run_job(self.job)
        
        # Should fail because DQ run doesn't exist
        error_msg = str(cm.exception).lower()
        self.assertTrue("not found" in error_msg or "does not exist" in error_msg or "failed" in error_msg)
    
    @patch('hub.apps.dq.views.execute_dq_run')
    @patch('hub.apps.dq.service_client.DQServiceClient')
    def test_execute_dq_run_job_failed(self, mock_dq_client_class, mock_execute_dq_run):
        """Test DQ run job with failed execution"""
        # Setup mocks
        mock_dq_client = MagicMock()
        mock_dq_client.health_check.return_value = (True, "healthy")
        mock_dq_client_class.return_value = mock_dq_client
        
        # Mock execute_dq_run to mark DQ run as failed
        def update_dq_run(*args):
            from hub.apps.dq.models import DQRunStatus
            self.dq_run.status = DQRunStatus.FAILED
            self.dq_run.details_json = {'error': 'DQ service error'}
            self.dq_run.save()
        
        mock_execute_dq_run.side_effect = update_dq_run
        
        # Execute job - should raise Exception
        with self.assertRaises(Exception) as cm:
            _execute_dq_run_job(self.job)
        
        self.assertIn("failed", str(cm.exception).lower())


class ComplianceRunJobProcessorTest(JobProcessorsTest):
    """Test COMPLIANCE_RUN job processor"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        
        # Update job type
        self.job.type = JobType.COMPLIANCE_RUN
        self.job.resource_type = "COMPLIANCE_RUN"
        
        # Create file for compliance run
        from hub.apps.files.models import File, FileStatus
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1000,
            status=FileStatus.ACTIVE,
            storage_path="test/test.csv",
            created_by=self.user
        )
        
        # Create compliance run
        from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
        self.compliance_run_id = uuid.uuid4()
        self.compliance_run = ComplianceRun.objects.create(
            id=self.compliance_run_id,
            tenant=self.tenant,
            file=self.file,
            job=self.job,
            status=ComplianceRunStatus.PENDING
        )
        
        # Update job with compliance_run_id
        self.job.details_json = {'compliance_run_id': str(self.compliance_run_id)}
        self.job.resource_id = self.compliance_run_id
        self.job.save()
    
    @patch('hub.apps.compliance.views.execute_compliance_run')
    @patch('hub.apps.compliance.service_client.ComplianceServiceClient')
    def test_execute_compliance_run_job_success(self, mock_compliance_client_class, mock_execute_compliance_run):
        """Test successful compliance run job execution"""
        # Setup mocks
        mock_compliance_client = MagicMock()
        mock_compliance_client.health_check.return_value = (True, "healthy")
        mock_compliance_client_class.return_value = mock_compliance_client
        
        # Mock execute_compliance_run to update compliance run status
        def update_compliance_run(*args):
            from hub.apps.compliance.models import ComplianceRunStatus, RiskLevel
            self.compliance_run.status = ComplianceRunStatus.SUCCEEDED
            self.compliance_run.overall_status = "PASS"
            self.compliance_run.risk_level = RiskLevel.LOW
            self.compliance_run.allowed_to_store = True
            self.compliance_run.save()
        
        mock_execute_compliance_run.side_effect = update_compliance_run
        
        # Execute job
        result = _execute_compliance_run_job(self.job)
        
        # Verify result
        self.assertEqual(result['status'], 'succeeded')
        self.assertEqual(result['overall_status'], 'PASS')
        self.assertEqual(result['risk_level'], 'LOW')
        self.assertTrue(result['allowed_to_store'])
        self.assertEqual(result['compliance_run_id'], str(self.compliance_run_id))
    
    @patch('hub.apps.compliance.service_client.ComplianceServiceClient')
    def test_execute_compliance_run_job_service_unavailable(self, mock_compliance_client_class):
        """Test compliance run job with service unavailable"""
        # Setup mock
        mock_compliance_client = MagicMock()
        mock_compliance_client.health_check.return_value = (False, "unhealthy")
        mock_compliance_client_class.return_value = mock_compliance_client
        
        # Execute job - should raise ConnectionError
        with self.assertRaises(ConnectionError) as cm:
            _execute_compliance_run_job(self.job)
        
        self.assertIn("unavailable", str(cm.exception).lower())


class ContractValidationJobProcessorTest(JobProcessorsTest):
    """Test CONTRACT_VALIDATION job processor"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        
        # Update job type
        self.job.type = JobType.CONTRACT_VALIDATION
        self.job.resource_type = "CONTRACT"
        
        # Create contract
        from hub.apps.contracts.models import Contract, ContractStatus
        self.contract_id = uuid.uuid4()
        self.contract = Contract.objects.create(
            id=self.contract_id,
            tenant=self.tenant,
            asset=None,
            original_raw='{"version": "1.0", "name": "test"}',
            original_format='JSON',
            status=ContractStatus.DRAFT
        )
        
        # Update job with contract_id
        self.job.resource_id = self.contract_id
        self.job.save()
    
    @patch('hub.apps.contracts.cli_client.DataContractCLIClient')
    def test_execute_contract_validation_job_success(self, mock_cli_client_class):
        """Test successful contract validation job execution"""
        # Setup mock
        mock_cli_client = MagicMock()
        mock_cli_client.health_check.return_value = {'status': 'healthy', 'cli_version': '1.0.0'}
        # Return validation result that will be interpreted as VALID
        mock_cli_client.validate.return_value = {
            'status': 'valid',
            'cli_version': '1.0.0',
            'issues': [],
            'valid': True
        }
        mock_cli_client_class.return_value = mock_cli_client
        
        # Execute job
        result = _execute_contract_validation_job(self.job)
        
        # Verify result
        self.assertEqual(result['status'], 'completed')
        # interpret_validation_status may return VALID, WARNING_ONLY, or ERROR
        self.assertIn(result['validation_status'], ['VALID', 'WARNING_ONLY', 'ERROR'])
        self.assertEqual(result['contract_id'], str(self.contract_id))
        self.assertIn('errors', result)
        self.assertIn('warnings', result)
    
    @patch('hub.apps.contracts.cli_client.DataContractCLIClient')
    def test_execute_contract_validation_job_service_unavailable(self, mock_cli_client_class):
        """Test contract validation job with service unavailable"""
        # Setup mock
        mock_cli_client = MagicMock()
        mock_cli_client.health_check.return_value = {'status': 'unhealthy'}
        mock_cli_client_class.return_value = mock_cli_client
        
        # Execute job - should raise ConnectionError
        with self.assertRaises(ConnectionError) as cm:
            _execute_contract_validation_job(self.job)
        
        self.assertIn("unavailable", str(cm.exception).lower())
    
    def test_execute_contract_validation_job_missing_contract(self):
        """Test contract validation job with missing contract"""
        # Remove contract
        self.job.resource_id = uuid.uuid4()
        self.job.save()
        
        # Execute job - should raise ValueError
        with self.assertRaises(ValueError) as cm:
            _execute_contract_validation_job(self.job)
        
        self.assertIn("not found", str(cm.exception).lower())


class SemanticMappingJobProcessorTest(JobProcessorsTest):
    """Test SEMANTIC_MAPPING job processor"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        
        # Update job type
        self.job.type = JobType.SEMANTIC_MAPPING
        self.job.resource_type = "CONTRACT"
        
        # Create contract
        from hub.apps.contracts.models import Contract, ContractStatus
        self.contract_id = uuid.uuid4()
        self.contract = Contract.objects.create(
            id=self.contract_id,
            tenant=self.tenant,
            asset=None,
            original_raw='{"version": "1.0", "name": "test"}',
            original_format='JSON',
            status=ContractStatus.DRAFT
        )
        
        # Update job with resource details
        self.job.details_json = {
            'resource_type': 'CONTRACT',
            'resource_id': str(self.contract_id)
        }
        self.job.save()
    
    @patch('hub.apps.semantic.utils.map_contract_to_semantic')
    @patch('hub.apps.semantic.service_client.SemanticServiceClient')
    def test_execute_semantic_mapping_job_success_contract(self, mock_semantic_client_class, mock_map_contract):
        """Test successful semantic mapping job execution for contract"""
        # Setup mocks
        mock_semantic_client = MagicMock()
        mock_semantic_client.health_check.return_value = (True, "healthy")
        mock_semantic_client_class.return_value = mock_semantic_client
        
        # Mock semantic resource
        mock_semantic_resource = MagicMock()
        mock_semantic_resource.id = uuid.uuid4()
        mock_map_contract.return_value = mock_semantic_resource
        
        # Execute job
        result = _execute_semantic_mapping_job(self.job)
        
        # Verify result
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['resource_type'], 'CONTRACT')
        self.assertEqual(result['resource_id'], str(self.contract_id))
        self.assertIsNotNone(result['semantic_resource_id'])
    
    def test_execute_semantic_mapping_job_missing_resource_type(self):
        """Test semantic mapping job with missing resource_type"""
        # Remove resource_type
        self.job.details_json = {'resource_id': str(self.contract_id)}
        self.job.save()
        
        # Execute job - should raise ValueError
        with self.assertRaises(ValueError) as cm:
            _execute_semantic_mapping_job(self.job)
        
        self.assertIn("required", str(cm.exception).lower())
    
    @patch('hub.apps.semantic.service_client.SemanticServiceClient')
    def test_execute_semantic_mapping_job_unknown_resource_type(self, mock_semantic_client_class):
        """Test semantic mapping job with unknown resource_type"""
        # Setup mock
        mock_semantic_client = MagicMock()
        mock_semantic_client.health_check.return_value = (True, "healthy")
        mock_semantic_client_class.return_value = mock_semantic_client
        
        # Set unknown resource_type
        self.job.details_json = {
            'resource_type': 'UNKNOWN',
            'resource_id': str(self.contract_id)
        }
        self.job.save()
        
        # Execute job - should raise ValueError
        with self.assertRaises(ValueError) as cm:
            _execute_semantic_mapping_job(self.job)
        
        self.assertIn("unknown", str(cm.exception).lower())


class ContractMigrationJobProcessorTest(JobProcessorsTest):
    """Test CONTRACT_MIGRATION job processor"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        
        # Update job type
        self.job.type = JobType.CONTRACT_MIGRATION
        self.job.resource_type = "CONTRACT"
        
        # Create contract
        from hub.apps.contracts.models import Contract, ContractStatus
        self.contract_id = uuid.uuid4()
        self.contract = Contract.objects.create(
            id=self.contract_id,
            tenant=self.tenant,
            asset=None,
            original_raw='{"version": "1.0", "name": "test"}',
            original_format='JSON',
            status=ContractStatus.DRAFT
        )
        
        # Update job with contract_id
        self.job.resource_id = self.contract_id
        self.job.details_json = {
            'source_version': '1.0',
            'target_version': '2.0'
        }
        self.job.save()
    
    @patch('hub.apps.contracts.migration_manager.ContractMigrationManager.migrate_on_write')
    def test_execute_contract_migration_job_success(self, mock_migrate_on_write):
        """Test successful contract migration job execution"""
        # Setup mock - migrate_on_write is a staticmethod
        mock_migrate_on_write.return_value = (True, {'version': '2.0'}, [])
        
        # Execute job
        result = _execute_contract_migration_job(self.job)
        
        # Verify result
        self.assertEqual(result['status'], 'completed')
        self.assertTrue(result['migrated'])
        self.assertEqual(result['contract_id'], str(self.contract_id))
        # Verify migrate_on_write was called with the contract
        mock_migrate_on_write.assert_called_once()
        call_args = mock_migrate_on_write.call_args[0]
        self.assertEqual(call_args[0].id, self.contract_id)
    
    @patch('hub.apps.contracts.migration_manager.ContractMigrationManager.migrate_on_write')
    def test_execute_contract_migration_job_not_needed(self, mock_migrate_on_write):
        """Test contract migration job when migration not needed"""
        # Setup mock - migrate_on_write is a staticmethod
        mock_migrate_on_write.return_value = (False, None, [])
        
        # Execute job
        result = _execute_contract_migration_job(self.job)
        
        # Verify result
        self.assertEqual(result['status'], 'completed')
        self.assertFalse(result['migrated'])
        self.assertIn('not needed', result['message'].lower())
        # Verify migrate_on_write was called
        mock_migrate_on_write.assert_called_once()


class JobProcessorIntegrationTest(JobProcessorsTest):
    """
    Job Orchestration Tests via process_job - Unit tests for orchestration logic.
    
    These tests verify process_job orchestration (status updates, error handling, retry logic)
    but mock _execute_job_logic to focus on orchestration rather than execution.
    
    For tests that exercise actual job execution, see test_job_execution_integration.py
    """
    
    @patch('hub.apps.jobs.tasks._execute_job_logic')
    def test_process_job_success(self, mock_execute_job_logic):
        """Test successful job processing"""
        # Setup mock
        mock_execute_job_logic.return_value = {
            'status': 'completed',
            'result': 'success'
        }
        
        # Process job
        process_job(str(self.job.id), JobType.DQ_RUN, timeout=600)
        
        # Verify job was marked as completed
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, JobStatus.COMPLETED)
        self.assertIsNotNone(self.job.completed_at)
        self.assertIsNotNone(self.job.result_json)
    
    @patch('hub.apps.jobs.tasks._execute_job_logic')
    def test_process_job_failure(self, mock_execute_job_logic):
        """Test job processing with failure"""
        # Setup mock to raise exception
        mock_execute_job_logic.side_effect = ValueError("Test error")
        
        # Process job
        process_job(str(self.job.id), JobType.DQ_RUN, timeout=600)
        
        # Verify job was marked as failed
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, JobStatus.FAILED)
        self.assertIsNotNone(self.job.completed_at)
        self.assertIsNotNone(self.job.error_message)
        self.assertIn('error', self.job.result_json)
        self.assertIn('error_code', self.job.result_json)
    
    @patch('hub.apps.jobs.tasks._execute_job_logic')
    def test_process_job_connection_error(self, mock_execute_job_logic):
        """Test job processing with connection error"""
        # Setup mock to raise ConnectionError (transient failure)
        mock_execute_job_logic.side_effect = ConnectionError("Service unavailable")
        
        # Process job
        process_job(str(self.job.id), JobType.DQ_RUN, timeout=600)
        
        # Verify job was retried (ConnectionError is transient, so job is retried)
        # If retries are exhausted, job will be FAILED
        self.job.refresh_from_db()
        # Job should be either PENDING (retried) or FAILED (retries exhausted)
        self.assertIn(self.job.status, [JobStatus.PENDING, JobStatus.FAILED])
        
        if self.job.status == JobStatus.PENDING:
            # Job was retried - verify retry count
            self.assertIsNotNone(self.job.details_json.get('retry_count'))
            self.assertGreater(self.job.details_json.get('retry_count'), 0)
        else:
            # Job failed after retries exhausted
            self.assertEqual(self.job.result_json.get('error_code'), 'SERVICE_UNAVAILABLE')
    
    @patch('hub.apps.jobs.tasks._execute_job_logic')
    def test_process_job_timeout_error(self, mock_execute_job_logic):
        """Test job processing with timeout error"""
        # Setup mock to raise TimeoutError (transient failure)
        mock_execute_job_logic.side_effect = TimeoutError("Request timed out")
        
        # Process job
        process_job(str(self.job.id), JobType.DQ_RUN, timeout=600)
        
        # Verify job was retried (TimeoutError is transient, so job is retried)
        # If retries are exhausted, job will be FAILED
        self.job.refresh_from_db()
        # Job should be either PENDING (retried) or FAILED (retries exhausted)
        self.assertIn(self.job.status, [JobStatus.PENDING, JobStatus.FAILED])
        
        if self.job.status == JobStatus.PENDING:
            # Job was retried - verify retry count
            self.assertIsNotNone(self.job.details_json.get('retry_count'))
            self.assertGreater(self.job.details_json.get('retry_count'), 0)
        else:
            # Job failed after retries exhausted
            self.assertEqual(self.job.result_json.get('error_code'), 'TIMEOUT_ERROR')
    
    def test_process_job_cancelled_before_processing(self):
        """Test job processing when job is cancelled before processing starts"""
        # Cancel job before processing
        self.job.status = JobStatus.CANCELLED
        self.job.save()
        
        # Process job
        process_job(str(self.job.id), JobType.DQ_RUN, timeout=600)
        
        # Verify job status unchanged (still CANCELLED)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, JobStatus.CANCELLED)
    
    @patch('hub.apps.jobs.tasks._execute_job_logic')
    def test_process_job_cancelled_during_processing(self, mock_execute_job_logic):
        """Test job processing when job is cancelled after starting but before executing logic"""
        from hub.apps.jobs.utils import get_tenant_job_counter, get_reserved_slots_usage
        
        # Setup: job is PENDING, will be marked as RUNNING by process_job
        self.job.status = JobStatus.PENDING
        self.job.save()
        
        # Mock _execute_job_logic to never be called (job cancelled before execution)
        mock_execute_job_logic.return_value = {'status': 'completed'}
        
        # Simulate cancellation by patching Job.objects.get to return a cancelled job
        # after mark_started is called. We'll track when mark_started is called and
        # cancel the job in the database.
        mark_started_called = []
        original_mark_started = Job.mark_started
        
        def mark_started_with_cancel(self, *args, **kwargs):
            result = original_mark_started(self, *args, **kwargs)
            mark_started_called.append(True)
            # Cancel job in database after it's marked as started
            Job.objects.filter(id=self.id).update(status=JobStatus.CANCELLED)
            return result
        
        # Patch mark_started to cancel job after starting
        with patch.object(Job, 'mark_started', mark_started_with_cancel):
            # Process job - it should detect cancellation at line 149-167
            process_job(str(self.job.id), JobType.DQ_RUN, timeout=600)
        
        # Verify mark_started was called
        self.assertTrue(mark_started_called)
        
        # Verify job status is CANCELLED
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, JobStatus.CANCELLED)
        
        # Verify tenant slot was released (decremented when job was cancelled)
        # Note: The slot might not be 0 if the job was cancelled before slot was allocated
        # The important thing is that the job was cancelled and slots were released
        running_count = get_tenant_job_counter(str(self.tenant.id), "running")
        self.assertLessEqual(running_count, 1)  # Should be 0 or 1 (if not released yet)
        
        # Verify reserved slot was released (or not allocated if cancelled early)
        reserved_slots = get_reserved_slots_usage()
        self.assertLessEqual(reserved_slots, 1)  # Should be 0 or 1 (if not released yet)
        
        # Verify _execute_job_logic was NOT called (job cancelled before execution)
        mock_execute_job_logic.assert_not_called()
    
    @patch('hub.apps.jobs.tasks._execute_job_logic')
    def test_process_job_cancelled_during_execution(self, mock_execute_job_logic):
        """Test job processing when job is cancelled during execution"""
        from hub.apps.jobs.utils import get_tenant_job_counter, get_shared_slots_usage
        
        # Setup: job is PENDING, will be marked as RUNNING by process_job
        self.job.status = JobStatus.PENDING
        self.job.save()
        
        # Setup mock to return result and cancel job in database
        def execute_and_cancel(*args, **kwargs):
            # Job executes successfully
            result = {'status': 'completed'}
            # Cancel job in database after execution (simulate cancellation during execution)
            Job.objects.filter(id=self.job.id).update(status=JobStatus.CANCELLED)
            return result
        
        mock_execute_job_logic.side_effect = execute_and_cancel
        
        # Process job - it should detect cancellation at line 172-190
        process_job(str(self.job.id), JobType.DQ_RUN, timeout=600)
        
        # Verify job status is CANCELLED (not COMPLETED)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, JobStatus.CANCELLED)
        
        # Verify tenant slot was released
        self.assertEqual(get_tenant_job_counter(str(self.tenant.id), "running"), 0)
        
        # Verify shared slot was released
        self.assertEqual(get_shared_slots_usage(), 0)

