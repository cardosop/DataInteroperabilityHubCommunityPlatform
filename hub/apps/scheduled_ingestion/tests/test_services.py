"""
Unit tests for IngestionService.

Tests cover all service methods with 100% coverage target.
"""
import pytest
from django.test import TestCase
from unittest.mock import patch, Mock

from hub.apps.scheduled_ingestion.services import IngestionService
from hub.apps.scheduled_ingestion.models import ScheduledIngestion, SourceType, ScheduleType
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus


pytestmark = pytest.mark.django_db(transaction=True)


class IngestionServiceTest(TestCase):
    """Test IngestionService operations"""
    
    def setUp(self):
        """Set up test data"""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.user = User.objects.create_user(
            email="test@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.service = IngestionService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )
        
        # Create scheduled ingestion
        self.scheduled_ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Test Ingestion",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv"
        )
    
    def test_execute_ingestion_success(self):
        """Test successful ingestion execution"""
        with patch('hub.apps.scheduled_ingestion.services.ScheduledIngestionWorkflow') as mock_workflow:
            mock_workflow.execute.return_value = {
                "output_data": {
                    "files_found": 5,
                    "state_summary": {
                        "total_processed": 4,
                        "total_failed": 1
                    }
                },
                "workflow_instance_id": "test-instance-id"
            }
            
            result = self.service.execute_ingestion(
                scheduled_ingestion_id=str(self.scheduled_ingestion.id),
                tenant_id=str(self.tenant.id)
            )
            
            self.assertEqual(result["files_found"], 5)
            self.assertEqual(result["files_processed"], 4)
            self.assertEqual(result["files_failed"], 1)
    
    def test_get_ingestion_status_success(self):
        """Test successful ingestion status retrieval"""
        retrieved = self.service.get_ingestion_status(
            scheduled_ingestion_id=str(self.scheduled_ingestion.id),
            tenant_id=str(self.tenant.id)
        )
        
        self.assertEqual(retrieved.id, self.scheduled_ingestion.id)

