"""
Unit tests for SCHEDULED_INGESTION job processing

Tests for the _execute_scheduled_ingestion_job function.
"""
import pytest
from django.test import TestCase
from unittest.mock import patch, MagicMock
from django.utils import timezone
import uuid

from hub.apps.jobs.models import Job, JobType, JobStatus
from hub.apps.jobs.tasks import _execute_scheduled_ingestion_job
from hub.apps.scheduled_ingestion.models import (
    ScheduledIngestion,
    ScheduledIngestionRun,
    ScheduledIngestionStatus,
    ScheduledIngestionRunStatus,
    SourceType
)
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus


pytestmark = pytest.mark.django_db(transaction=True)


class ScheduledIngestionJobTest(TestCase):
    """Test SCHEDULED_INGESTION job processing"""
    
    def setUp(self):
        """Set up test fixtures"""
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
        
        # Create scheduled ingestion
        self.scheduled_ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Test Ingestion",
            source_type=SourceType.S3,
            source_config={
                "bucket": "test-bucket",
                "prefix": "data/",
                "access_key_id": "test-key",
                "secret_access_key": "test-secret"
            },
            schedule="0 0 * * *",
            file_pattern=".*\\.csv",
            auto_create_asset=True,
            auto_activate=True,
            status=ScheduledIngestionStatus.ACTIVE,
            created_by=self.user
        )
        
        # Create job
        self.job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.SCHEDULED_INGESTION,
            status=JobStatus.PENDING,
            resource_type="SCHEDULED_INGESTION",
            resource_id=str(self.scheduled_ingestion.id),
            details_json={
                "prefect_flow_run_id": str(uuid.uuid4())
            },
            created_by=self.user
        )
    
    @patch('hub.apps.scheduled_ingestion.ingestion.ScheduledIngestionProcessor')
    def test_execute_scheduled_ingestion_job_success(self, mock_processor_class):
        """Test successful scheduled ingestion job execution"""
        # Setup mock processor
        mock_processor = MagicMock()
        mock_processor.run_ingestion.return_value = {
            "files_found": 2,
            "files_processed": 2,
            "files_skipped": 0,
            "files_failed": 0,
            "datasets_created": 2,
            "errors": [],
            "ingestion_state": {"processed_files": ["file1.csv", "file2.csv"]},
            "last_incremental_value": None
        }
        mock_processor_class.return_value = mock_processor
        
        # Execute job
        result = _execute_scheduled_ingestion_job(self.job)
        
        # Verify result
        self.assertEqual(result["files_processed"], 2)
        self.assertEqual(result["datasets_created"], 2)
        self.assertEqual(result["files_failed"], 0)
        
        # Verify processor called correctly
        mock_processor_class.assert_called_once()
        call_kwargs = mock_processor_class.call_args[1]
        self.assertEqual(call_kwargs['scheduled_ingestion_id'], self.scheduled_ingestion.id)
        self.assertEqual(call_kwargs['tenant_id'], self.tenant.id)
        self.assertEqual(call_kwargs['source_type'], SourceType.S3)
        
        # Verify run created and updated
        run = ScheduledIngestionRun.objects.get(job=self.job)
        self.assertEqual(run.status, ScheduledIngestionRunStatus.COMPLETED)
        self.assertIsNotNone(run.completed_at)
        self.assertIsNone(run.error_message)
        
        # Verify scheduled ingestion updated
        self.scheduled_ingestion.refresh_from_db()
        self.assertIsNotNone(self.scheduled_ingestion.last_run_at)
        self.assertEqual(self.scheduled_ingestion.status, ScheduledIngestionStatus.ACTIVE)
    
    @patch('hub.apps.scheduled_ingestion.ingestion.ScheduledIngestionProcessor')
    def test_execute_scheduled_ingestion_job_with_failures(self, mock_processor_class):
        """Test scheduled ingestion job execution with file failures"""
        # Setup mock processor with failures
        mock_processor = MagicMock()
        mock_processor.run_ingestion.return_value = {
            "files_found": 3,
            "files_processed": 1,
            "files_skipped": 0,
            "files_failed": 2,
            "datasets_created": 1,
            "errors": [
                "Failed to process file file2.csv: Download error",
                "Failed to process file file3.csv: Invalid format"
            ],
            "ingestion_state": {"processed_files": ["file1.csv"]},
            "last_incremental_value": None
        }
        mock_processor_class.return_value = mock_processor
        
        # Execute job
        result = _execute_scheduled_ingestion_job(self.job)
        
        # Verify result
        self.assertEqual(result["files_processed"], 1)
        self.assertEqual(result["files_failed"], 2)
        self.assertEqual(len(result["errors"]), 2)
        
        # Verify run marked as failed
        run = ScheduledIngestionRun.objects.get(job=self.job)
        self.assertEqual(run.status, ScheduledIngestionRunStatus.FAILED)
        self.assertIsNotNone(run.error_message)
        self.assertIn("file2.csv", run.error_message)
        
        # Verify scheduled ingestion status set to ERROR
        self.scheduled_ingestion.refresh_from_db()
        self.assertEqual(self.scheduled_ingestion.status, ScheduledIngestionStatus.ERROR)
    
    @patch('hub.apps.scheduled_ingestion.ingestion.ScheduledIngestionProcessor')
    def test_execute_scheduled_ingestion_job_processor_exception(self, mock_processor_class):
        """Test scheduled ingestion job execution with processor exception"""
        # Setup mock processor to raise exception
        mock_processor = MagicMock()
        mock_processor.run_ingestion.side_effect = Exception("Processor error")
        mock_processor_class.return_value = mock_processor
        
        # Execute job - should raise exception
        with self.assertRaises(Exception) as cm:
            _execute_scheduled_ingestion_job(self.job)
        
        self.assertIn("Processor error", str(cm.exception))
    
    def test_execute_scheduled_ingestion_job_missing_id(self):
        """Test scheduled ingestion job execution with missing scheduled ingestion ID"""
        # Remove resource_id from job
        self.job.resource_id = None
        self.job.save()
        
        # Execute job - should raise ValueError
        with self.assertRaises(ValueError) as cm:
            _execute_scheduled_ingestion_job(self.job)
        
        self.assertIn("Scheduled Ingestion ID is required", str(cm.exception))
    
    def test_execute_scheduled_ingestion_job_not_found(self):
        """Test scheduled ingestion job execution with non-existent scheduled ingestion"""
        # Set invalid resource_id
        self.job.resource_id = uuid.uuid4()
        self.job.save()
        
        # Execute job - should raise DoesNotExist
        from django.core.exceptions import ObjectDoesNotExist
        with self.assertRaises(ObjectDoesNotExist):
            _execute_scheduled_ingestion_job(self.job)
    
    @patch('hub.apps.scheduled_ingestion.ingestion.ScheduledIngestionProcessor')
    def test_execute_scheduled_ingestion_job_incremental_timestamp(self, mock_processor_class):
        """Test scheduled ingestion job with incremental timestamp strategy"""
        # Setup incremental ingestion
        self.scheduled_ingestion.incremental_enabled = True
        self.scheduled_ingestion.incremental_strategy = "TIMESTAMP"
        self.scheduled_ingestion.last_incremental_value = "2024-01-01T00:00:00Z"
        self.scheduled_ingestion.save()
        
        # Setup mock processor
        mock_processor = MagicMock()
        mock_processor.run_ingestion.return_value = {
            "files_found": 1,
            "files_processed": 1,
            "files_skipped": 0,
            "files_failed": 0,
            "datasets_created": 1,
            "errors": [],
            "ingestion_state": {"processed_files": ["file1.csv"]},
            "last_incremental_value": "2024-01-02T00:00:00Z"
        }
        mock_processor_class.return_value = mock_processor
        
        # Execute job
        result = _execute_scheduled_ingestion_job(self.job)
        
        # Verify incremental value updated
        self.scheduled_ingestion.refresh_from_db()
        self.assertEqual(
            self.scheduled_ingestion.last_incremental_value,
            "2024-01-02T00:00:00Z"
        )
    
    @patch('hub.apps.scheduled_ingestion.ingestion.ScheduledIngestionProcessor')
    def test_execute_scheduled_ingestion_job_existing_run(self, mock_processor_class):
        """Test scheduled ingestion job with existing run"""
        # Create existing run
        existing_run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.scheduled_ingestion,
            job=self.job,
            status=ScheduledIngestionRunStatus.RUNNING,
            started_at=timezone.now() - timedelta(minutes=5)
        )
        
        # Setup mock processor
        mock_processor = MagicMock()
        mock_processor.run_ingestion.return_value = {
            "files_found": 1,
            "files_processed": 1,
            "files_skipped": 0,
            "files_failed": 0,
            "datasets_created": 1,
            "errors": [],
            "ingestion_state": {},
            "last_incremental_value": None
        }
        mock_processor_class.return_value = mock_processor
        
        # Execute job
        result = _execute_scheduled_ingestion_job(self.job)
        
        # Verify existing run updated (not new one created)
        runs = ScheduledIngestionRun.objects.filter(job=self.job)
        self.assertEqual(runs.count(), 1)
        run = runs.first()
        self.assertEqual(run.id, existing_run.id)
        self.assertEqual(run.status, ScheduledIngestionRunStatus.COMPLETED)

