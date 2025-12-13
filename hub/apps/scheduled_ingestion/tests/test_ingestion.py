"""
Unit tests for Scheduled Ingestion Processor

Tests for file discovery, filtering, and dataset creation logic.
"""
import pytest
from django.test import TestCase
from unittest.mock import patch, MagicMock, Mock
from django.utils import timezone
from datetime import datetime, timedelta
import uuid
import tempfile
import os

from hub.apps.scheduled_ingestion.models import ScheduledIngestion, ScheduledIngestionStatus, SourceType
from hub.apps.scheduled_ingestion.ingestion import ScheduledIngestionProcessor
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.files.models import File, FileStatus
from hub.apps.datasets.models import Dataset


pytestmark = pytest.mark.django_db(transaction=True)


class ScheduledIngestionProcessorTest(TestCase):
    """Test ScheduledIngestionProcessor"""
    
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
            description="Test scheduled ingestion",
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
        
        self.processor = ScheduledIngestionProcessor(self.scheduled_ingestion)
    
    @patch('hub.apps.scheduled_ingestion.ingestion.SourceConnectorFactory')
    def test_discover_files_success(self, mock_factory):
        """Test successful file discovery"""
        # Setup mock connector
        mock_connector = MagicMock()
        mock_connector.discover_files.return_value = [
            "data/file1.csv",
            "data/file2.csv",
            "data/file3.json"
        ]
        mock_factory.get_connector.return_value = mock_connector
        
        # Discover files
        files = self.processor._discover_files()
        
        # Verify
        self.assertEqual(len(files), 3)
        self.assertIn("data/file1.csv", files)
        mock_connector.discover_files.assert_called_once_with(
            self.scheduled_ingestion.source_config,
            ".*\\.csv"
        )
    
    @patch('hub.apps.scheduled_ingestion.ingestion.SourceConnectorFactory')
    def test_discover_files_none_pattern(self, mock_factory):
        """Test file discovery with None pattern (should use default)"""
        # Update scheduled ingestion to have None pattern
        self.scheduled_ingestion.file_pattern = None
        self.scheduled_ingestion.save()
        self.processor = ScheduledIngestionProcessor(self.scheduled_ingestion)
        
        # Setup mock connector
        mock_connector = MagicMock()
        mock_connector.discover_files.return_value = ["data/file1.csv"]
        mock_factory.get_connector.return_value = mock_connector
        
        # Discover files
        files = self.processor._discover_files()
        
        # Verify default pattern used
        mock_connector.discover_files.assert_called_once_with(
            self.scheduled_ingestion.source_config,
            ".*"
        )
    
    @patch('hub.apps.scheduled_ingestion.ingestion.SourceConnectorFactory')
    def test_discover_files_error(self, mock_factory):
        """Test file discovery with error"""
        # Setup mock connector to raise error
        mock_connector = MagicMock()
        mock_connector.discover_files.side_effect = Exception("Connection failed")
        mock_factory.get_connector.return_value = mock_connector
        
        # Discover files - should raise ConnectionError
        with self.assertRaises(ConnectionError) as cm:
            self.processor._discover_files()
        
        self.assertIn("Failed to discover files", str(cm.exception))
    
    @patch('hub.apps.scheduled_ingestion.ingestion.SourceConnectorFactory')
    def test_filter_files_skip_processed(self, mock_factory):
        """Test file filtering skips already processed files"""
        # Setup ingestion state with processed files
        self.scheduled_ingestion.ingestion_state = {
            "processed_files": ["data/file1.csv", "data/file2.csv"]
        }
        self.scheduled_ingestion.save()
        self.processor = ScheduledIngestionProcessor(self.scheduled_ingestion)
        
        # Setup mock connector
        mock_connector = MagicMock()
        mock_factory.get_connector.return_value = mock_connector
        
        # Filter files
        files = ["data/file1.csv", "data/file2.csv", "data/file3.csv"]
        filtered = self.processor._filter_files(files)
        
        # Verify only unprocessed file remains
        self.assertEqual(len(filtered), 1)
        self.assertIn("data/file3.csv", filtered)
        self.assertNotIn("data/file1.csv", filtered)
        self.assertNotIn("data/file2.csv", filtered)
    
    @patch('hub.apps.scheduled_ingestion.ingestion.SourceConnectorFactory')
    def test_filter_files_timestamp_incremental(self, mock_factory):
        """Test file filtering with timestamp-based incremental ingestion"""
        # Setup incremental ingestion
        self.scheduled_ingestion.incremental_enabled = True
        self.scheduled_ingestion.incremental_strategy = "TIMESTAMP"
        self.scheduled_ingestion.last_processed_timestamp = timezone.now() - timedelta(days=1)
        self.scheduled_ingestion.save()
        self.processor = ScheduledIngestionProcessor(self.scheduled_ingestion)
        
        # Setup mock connector
        mock_connector = MagicMock()
        mock_connector.get_file_metadata.return_value = {
            "last_modified": timezone.now() - timedelta(days=2),  # Older than last processed
            "size": 1000
        }
        mock_factory.get_connector.return_value = mock_connector
        
        # Filter files
        files = ["data/file1.csv"]
        filtered = self.processor._filter_files(files)
        
        # Verify older file is skipped
        self.assertEqual(len(filtered), 0)
    
    @patch('hub.apps.scheduled_ingestion.ingestion.SourceConnectorFactory')
    def test_filter_files_size_limit(self, mock_factory):
        """Test file filtering with size limits"""
        # Setup source config with size limit
        self.scheduled_ingestion.source_config["max_file_size_bytes"] = 1000
        self.scheduled_ingestion.save()
        self.processor = ScheduledIngestionProcessor(self.scheduled_ingestion)
        
        # Setup mock connector
        mock_connector = MagicMock()
        mock_connector.get_file_metadata.return_value = {
            "last_modified": timezone.now(),
            "size": 2000  # Exceeds limit
        }
        mock_factory.get_connector.return_value = mock_connector
        
        # Filter files
        files = ["data/file1.csv"]
        filtered = self.processor._filter_files(files)
        
        # Verify oversized file is skipped
        self.assertEqual(len(filtered), 0)
    
    @patch('hub.apps.scheduled_ingestion.ingestion.S3StorageClient')
    @patch('hub.apps.scheduled_ingestion.ingestion.SourceConnectorFactory')
    def test_process_file_success(self, mock_factory, mock_storage_class):
        """Test successful file processing"""
        # Setup mock connector
        mock_connector = MagicMock()
        mock_result = MagicMock()
        mock_result.status.value = "SUCCESS"
        mock_connector.download_file.return_value = mock_result
        mock_factory.get_connector.return_value = mock_connector
        
        # Setup mock storage
        mock_storage = MagicMock()
        mock_storage.save_file.return_value = "tenant_id/file_id/test.csv"
        mock_storage.get_file_content.return_value = b"col1,col2\nval1,val2"
        mock_storage_class.return_value = mock_storage
        
        # Create temporary file for download
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.csv', delete=False) as temp_file:
            temp_file.write(b"col1,col2\nval1,val2")
            temp_path = temp_file.name
        
        try:
            # Mock download_file to write to temp path
            def mock_download(config, file_path, dest_path):
                import shutil
                shutil.copy(temp_path, dest_path)
                return mock_result
            
            mock_connector.download_file.side_effect = mock_download
            
            # Process file
            dataset = self.processor._process_file("data/test.csv")
            
            # Verify dataset created
            self.assertIsNotNone(dataset)
            self.assertEqual(dataset.tenant, self.tenant)
            self.assertEqual(dataset.format, "CSV")
            
            # Verify file created
            file_obj = dataset.file
            self.assertIsNotNone(file_obj)
            self.assertEqual(file_obj.name, "test.csv")
            self.assertEqual(file_obj.status, FileStatus.ACTIVE)
            
            # Verify asset created
            self.assertIsNotNone(dataset.asset)
            self.assertEqual(dataset.asset.status, AssetStatus.ACTIVE)
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    @patch('hub.apps.scheduled_ingestion.ingestion.SourceConnectorFactory')
    def test_process_file_download_failure(self, mock_factory):
        """Test file processing with download failure"""
        # Setup mock connector to fail download
        mock_connector = MagicMock()
        mock_result = MagicMock()
        mock_result.status.value = "FAILED"
        mock_result.message = "Download failed"
        mock_connector.download_file.return_value = mock_result
        mock_factory.get_connector.return_value = mock_connector
        
        # Process file - should raise exception
        with self.assertRaises(Exception) as cm:
            self.processor._process_file("data/test.csv")
        
        self.assertIn("Failed to download file", str(cm.exception))
    
    @patch('hub.apps.scheduled_ingestion.ingestion.S3StorageClient')
    @patch('hub.apps.scheduled_ingestion.ingestion.SourceConnectorFactory')
    def test_process_file_unsupported_format(self, mock_factory, mock_storage_class):
        """Test file processing with unsupported format"""
        # Setup mock connector
        mock_connector = MagicMock()
        mock_result = MagicMock()
        mock_result.status.value = "SUCCESS"
        mock_connector.download_file.return_value = mock_result
        mock_factory.get_connector.return_value = mock_connector
        
        # Setup mock storage
        mock_storage = MagicMock()
        mock_storage.save_file.return_value = "tenant_id/file_id/test.xyz"
        mock_storage_class.return_value = mock_storage
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.xyz', delete=False) as temp_file:
            temp_file.write(b"some content")
            temp_path = temp_file.name
        
        try:
            # Mock download_file
            def mock_download(config, file_path, dest_path):
                import shutil
                shutil.copy(temp_path, dest_path)
                return mock_result
            
            mock_connector.download_file.side_effect = mock_download
            
            # Process file - should raise ValueError for unsupported format
            with self.assertRaises(ValueError) as cm:
                self.processor._process_file("data/test.xyz")
            
            self.assertIn("Unsupported file format", str(cm.exception))
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    @patch('hub.apps.scheduled_ingestion.ingestion.S3StorageClient')
    @patch('hub.apps.scheduled_ingestion.ingestion.SourceConnectorFactory')
    def test_process_complete_ingestion(self, mock_factory, mock_storage_class):
        """Test complete ingestion process"""
        # Setup mock connector
        mock_connector = MagicMock()
        mock_connector.discover_files.return_value = [
            "data/file1.csv",
            "data/file2.csv"
        ]
        
        mock_result = MagicMock()
        mock_result.status.value = "SUCCESS"
        
        def mock_download(config, file_path, dest_path):
            # Create a simple CSV file
            with open(dest_path, 'wb') as f:
                f.write(b"col1,col2\nval1,val2")
            return mock_result
        
        mock_connector.download_file.side_effect = mock_download
        mock_connector.get_file_metadata.return_value = {
            "last_modified": timezone.now(),
            "size": 100
        }
        mock_factory.get_connector.return_value = mock_connector
        
        # Setup mock storage
        mock_storage = MagicMock()
        mock_storage.save_file.return_value = "tenant_id/file_id/test.csv"
        mock_storage.get_file_content.return_value = b"col1,col2\nval1,val2"
        mock_storage_class.return_value = mock_storage
        
        # Process ingestion
        result = self.processor.process()
        
        # Verify results
        self.assertEqual(result["files_found"], 2)
        self.assertEqual(result["files_processed"], 2)
        self.assertEqual(result["datasets_created"], 2)
        self.assertEqual(result["files_failed"], 0)
        self.assertIn("ingestion_state", result)
    
    @patch('hub.apps.scheduled_ingestion.ingestion.SourceConnectorFactory')
    def test_process_ingestion_no_files(self, mock_factory):
        """Test ingestion process with no files found"""
        # Setup mock connector to return empty list
        mock_connector = MagicMock()
        mock_connector.discover_files.return_value = []
        mock_factory.get_connector.return_value = mock_connector
        
        # Process ingestion
        result = self.processor.process()
        
        # Verify results
        self.assertEqual(result["files_found"], 0)
        self.assertEqual(result["files_processed"], 0)
        self.assertEqual(result["datasets_created"], 0)
    
    @patch('hub.apps.scheduled_ingestion.ingestion.S3StorageClient')
    @patch('hub.apps.scheduled_ingestion.ingestion.SourceConnectorFactory')
    def test_process_ingestion_partial_failure(self, mock_factory, mock_storage_class):
        """Test ingestion process with partial file failures"""
        # Setup mock connector
        mock_connector = MagicMock()
        mock_connector.discover_files.return_value = [
            "data/file1.csv",
            "data/file2.csv"
        ]
        
        mock_result = MagicMock()
        mock_result.status.value = "SUCCESS"
        
        call_count = [0]
        def mock_download(config, file_path, dest_path):
            call_count[0] += 1
            if call_count[0] == 1:
                # First file succeeds
                with open(dest_path, 'wb') as f:
                    f.write(b"col1,col2\nval1,val2")
                return mock_result
            else:
                # Second file fails
                raise Exception("Download failed")
        
        mock_connector.download_file.side_effect = mock_download
        mock_connector.get_file_metadata.return_value = {
            "last_modified": timezone.now(),
            "size": 100
        }
        mock_factory.get_connector.return_value = mock_connector
        
        # Setup mock storage
        mock_storage = MagicMock()
        mock_storage.save_file.return_value = "tenant_id/file_id/test.csv"
        mock_storage.get_file_content.return_value = b"col1,col2\nval1,val2"
        mock_storage_class.return_value = mock_storage
        
        # Process ingestion
        result = self.processor.process()
        
        # Verify results
        self.assertEqual(result["files_found"], 2)
        self.assertEqual(result["files_processed"], 1)
        self.assertEqual(result["files_failed"], 1)
        self.assertEqual(len(result["errors"]), 1)

