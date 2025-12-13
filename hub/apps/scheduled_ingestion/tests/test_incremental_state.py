"""
Unit tests for Incremental State Manager
"""
import pytest
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from hub.apps.scheduled_ingestion.models import ScheduledIngestion
from hub.apps.scheduled_ingestion.incremental_state import IncrementalStateManager
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus


pytestmark = pytest.mark.django_db(transaction=True)


class IncrementalStateManagerTest(TestCase):
    """Test IncrementalStateManager"""
    
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
            status=UserStatus.ACTIVE
        )
        
        self.scheduled_ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Test Ingestion",
            source_type="S3",
            source_config={"bucket": "test-bucket"},
            schedule_type="DAILY",
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv",
            created_by=self.user
        )
        
        self.state_manager = IncrementalStateManager(self.scheduled_ingestion)
    
    def test_get_processed_files_empty(self):
        """Test getting processed files when none exist"""
        processed = self.state_manager.get_processed_files()
        self.assertEqual(processed, [])
    
    def test_mark_file_processed(self):
        """Test marking file as processed"""
        file_path = "s3://bucket/file1.csv"
        file_timestamp = timezone.now()
        
        self.state_manager.mark_file_processed(
            file_path=file_path,
            file_timestamp=file_timestamp,
            dataset_id="dataset-uuid"
        )
        
        # Verify file is marked as processed
        self.assertTrue(self.state_manager.is_file_processed(file_path))
        self.assertEqual(self.scheduled_ingestion.last_processed_file, file_path)
        self.assertEqual(self.scheduled_ingestion.last_processed_timestamp, file_timestamp)
        
        # Verify in state
        processed_files = self.state_manager.get_processed_files()
        self.assertIn(file_path, processed_files)
        
        # Verify file-to-dataset mapping
        ingestion_state = self.scheduled_ingestion.ingestion_state
        file_mappings = ingestion_state.get("file_to_dataset", {})
        self.assertEqual(file_mappings.get(file_path), "dataset-uuid")
    
    def test_is_file_processed(self):
        """Test checking if file is processed"""
        file_path = "s3://bucket/file1.csv"
        
        self.assertFalse(self.state_manager.is_file_processed(file_path))
        
        self.state_manager.mark_file_processed(file_path)
        
        self.assertTrue(self.state_manager.is_file_processed(file_path))
    
    def test_mark_file_failed_retryable(self):
        """Test marking file as failed (retryable)"""
        file_path = "s3://bucket/file1.csv"
        error_message = "Connection timeout"
        
        should_retry = self.state_manager.mark_file_failed(
            file_path=file_path,
            error_message=error_message,
            error_code="TIMEOUT",
            retry_count=0,
            max_retries=3
        )
        
        self.assertTrue(should_retry)
        self.assertTrue(self.state_manager.is_file_failed(file_path))
        
        # Verify failure record
        failed_files = self.state_manager.get_failed_files()
        self.assertEqual(len(failed_files), 1)
        self.assertEqual(failed_files[0]["file_path"], file_path)
        self.assertEqual(failed_files[0]["retry_count"], 1)
        self.assertFalse(failed_files[0]["permanent_failure"])
    
    def test_mark_file_failed_permanent(self):
        """Test marking file as permanently failed"""
        file_path = "s3://bucket/file1.csv"
        error_message = "Invalid format"
        
        # Mark as failed multiple times to exceed max retries
        for i in range(3):
            should_retry = self.state_manager.mark_file_failed(
                file_path=file_path,
                error_message=error_message,
                error_code="VALIDATION_ERROR",
                retry_count=i,
                max_retries=3
            )
        
        # Last call should return False (permanent failure)
        self.assertFalse(should_retry)
        
        # Verify permanent failure
        failed_files = self.state_manager.get_failed_files()
        self.assertEqual(len(failed_files), 1)
        self.assertTrue(failed_files[0]["permanent_failure"])
    
    def test_should_process_file_new(self):
        """Test should_process_file for new file"""
        file_path = "s3://bucket/new_file.csv"
        file_timestamp = timezone.now()
        
        self.assertTrue(self.state_manager.should_process_file(file_path, file_timestamp))
    
    def test_should_process_file_already_processed(self):
        """Test should_process_file for already processed file"""
        file_path = "s3://bucket/file1.csv"
        
        self.state_manager.mark_file_processed(file_path)
        
        self.assertFalse(self.state_manager.should_process_file(file_path))
    
    def test_should_process_file_permanently_failed(self):
        """Test should_process_file for permanently failed file"""
        file_path = "s3://bucket/file1.csv"
        
        # Mark as permanently failed
        for i in range(3):
            self.state_manager.mark_file_failed(
                file_path=file_path,
                error_message="Error",
                retry_count=i,
                max_retries=3
            )
        
        self.assertFalse(self.state_manager.should_process_file(file_path))
    
    def test_should_process_file_timestamp_filtering(self):
        """Test should_process_file with timestamp filtering"""
        file_path = "s3://bucket/file1.csv"
        old_timestamp = timezone.now() - timedelta(days=2)
        new_timestamp = timezone.now()
        
        # Set last processed timestamp
        self.scheduled_ingestion.last_processed_timestamp = timezone.now() - timedelta(days=1)
        self.scheduled_ingestion.save()
        
        # Old file should be skipped
        self.assertFalse(self.state_manager.should_process_file(file_path, old_timestamp))
        
        # New file should be processed
        self.assertTrue(self.state_manager.should_process_file(file_path, new_timestamp))
    
    def test_clear_failed_file(self):
        """Test clearing failed file record"""
        file_path = "s3://bucket/file1.csv"
        
        # Mark as failed
        self.state_manager.mark_file_failed(
            file_path=file_path,
            error_message="Error"
        )
        
        self.assertTrue(self.state_manager.is_file_failed(file_path))
        
        # Clear failure
        self.state_manager.clear_failed_file(file_path)
        
        self.assertFalse(self.state_manager.is_file_failed(file_path))
    
    def test_get_state_summary(self):
        """Test getting state summary"""
        # Process some files
        self.state_manager.mark_file_processed("file1.csv")
        self.state_manager.mark_file_processed("file2.csv")
        
        # Fail some files
        self.state_manager.mark_file_failed("file3.csv", "Error 1")
        self.state_manager.mark_file_failed("file4.csv", "Error 2")
        
        # Make one permanent failure
        for i in range(3):
            self.state_manager.mark_file_failed("file4.csv", "Error", retry_count=i, max_retries=3)
        
        summary = self.state_manager.get_state_summary()
        
        self.assertEqual(summary["total_processed"], 2)
        self.assertEqual(summary["total_failed"], 2)
        self.assertEqual(summary["permanent_failures"], 1)
        self.assertEqual(summary["retryable_failures"], 1)

