"""
Integration tests for Scheduled Ingestion enhancements
"""
import pytest
from django.test import TestCase
from django.utils import timezone
from unittest.mock import patch, Mock

from hub.apps.scheduled_ingestion.models import ScheduledIngestion, ScheduledIngestionRun
from hub.apps.scheduled_ingestion.ingestion import ScheduledIngestionProcessor
from hub.apps.scheduled_ingestion.incremental_state import IncrementalStateManager
from hub.apps.scheduled_ingestion.templates import IngestionTemplate, IngestionTemplateManager
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.files.models import File, FileStatus
from hub.apps.datasets.models import Dataset


pytestmark = pytest.mark.django_db(transaction=True)


class IncrementalIngestionIntegrationTest(TestCase):
    """Integration tests for incremental ingestion"""
    
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
    
    @patch('hub.apps.scheduled_ingestion.ingestion.SourceConnectorFactory')
    def test_incremental_ingestion_workflow(self, mock_factory):
        """Test complete incremental ingestion workflow"""
        # Mock connector
        mock_connector = Mock()
        mock_connector.discover_files.return_value = [
            "file1.csv",
            "file2.csv",
            "file3.csv"
        ]
        mock_connector.get_file_metadata.return_value = {
            "last_modified": timezone.now(),
            "size": 1000
        }
        mock_factory.get_connector.return_value = mock_connector
        
        processor = ScheduledIngestionProcessor(self.scheduled_ingestion)
        state_manager = IncrementalStateManager(self.scheduled_ingestion)
        
        # Process first file
        state_manager.mark_file_processed("file1.csv", timezone.now(), "dataset-1")
        
        # Verify state
        self.assertTrue(state_manager.is_file_processed("file1.csv"))
        self.assertEqual(self.scheduled_ingestion.last_processed_file, "file1.csv")
        
        # Process second file (should skip file1.csv)
        filtered_files = processor._filter_files(["file1.csv", "file2.csv", "file3.csv"])
        
        self.assertNotIn("file1.csv", filtered_files)
        self.assertIn("file2.csv", filtered_files)
        self.assertIn("file3.csv", filtered_files)


class DQValidationIntegrationTest(TestCase):
    """Integration tests for DQ validation during ingestion"""
    
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
            source_config={
                "bucket": "test-bucket",
                "enable_dq_validation": True,
                "dq_profile_key": "intake_basic_gx",
                "dq_strict_mode": True,
                "min_quality_score": 0.8
            },
            schedule_type="DAILY",
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv",
            created_by=self.user
        )
    
    @patch('hub.apps.scheduled_ingestion.ingestion.DQServiceClient')
    @patch('hub.apps.scheduled_ingestion.ingestion.SourceConnectorFactory')
    def test_dq_validation_during_ingestion(self, mock_factory, mock_dq_client_class):
        """Test DQ validation integrated with ingestion"""
        # Mock connector
        mock_connector = Mock()
        mock_connector.discover_files.return_value = ["file1.csv"]
        mock_connector.get_file_metadata.return_value = {
            "last_modified": timezone.now(),
            "size": 1000
        }
        mock_connector.download_file.return_value = Mock(status=Mock(value="SUCCESS"), message="OK")
        mock_factory.get_connector.return_value = mock_connector
        
        # Mock DQ client
        mock_dq_client = Mock()
        mock_dq_client.health_check.return_value = (True, {})
        mock_dq_client.run_dq.return_value = {
            "overall_status": "PASS",
            "quality_score": 0.95,
            "checks": [],
            "execution_time_seconds": 2.5
        }
        mock_dq_client_class.return_value = mock_dq_client
        
        processor = ScheduledIngestionProcessor(self.scheduled_ingestion)
        
        # Verify DQ check is enabled
        self.assertTrue(processor._should_run_dq_check())


class TemplateIntegrationTest(TestCase):
    """Integration tests for ingestion templates"""
    
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
        
        self.template = IngestionTemplate.objects.create(
            name="S3 Daily Files",
            template_type="S3_DAILY_FILES",
            is_system_template=True,
            source_type="S3",
            source_config_template={
                "bucket_name": "{bucket_name}",
                "prefix": "{prefix}"
            },
            schedule_type="DAILY",
            schedule_config_template={"time": "{time}"},
            file_pattern_template="{file_pattern}",
            ingestion_config_template={
                "enable_dq_validation": True,
                "dq_profile_key": "intake_basic_gx"
            }
        )
    
    def test_template_to_ingestion_workflow(self):
        """Test complete workflow from template to scheduled ingestion"""
        template_variables = {
            "bucket_name": "my-bucket",
            "prefix": "data/",
            "time": "00:00",
            "file_pattern": ".*\\.csv"
        }
        
        scheduled_ingestion = IngestionTemplateManager.create_from_template(
            template=self.template,
            name="My Ingestion",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            template_variables=template_variables
        )
        
        # Verify scheduled ingestion was created
        self.assertIsNotNone(scheduled_ingestion.id)
        self.assertEqual(scheduled_ingestion.tenant, self.tenant)
        
        # Verify configuration was resolved
        self.assertEqual(scheduled_ingestion.source_config["bucket_name"], "my-bucket")
        self.assertEqual(scheduled_ingestion.source_config["prefix"], "data/")
        
        # Verify DQ configuration from template
        self.assertTrue(scheduled_ingestion.ingestion_state["enable_dq_validation"])
        self.assertEqual(scheduled_ingestion.ingestion_state["dq_profile_key"], "intake_basic_gx")
