"""
Unit tests for DQ validation during ingestion
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from io import BytesIO

from hub.apps.scheduled_ingestion.models import ScheduledIngestion
from hub.apps.scheduled_ingestion.ingestion import ScheduledIngestionProcessor
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.files.models import File, FileStatus


pytestmark = pytest.mark.django_db(transaction=True)


class DQValidationTest(TestCase):
    """Test DQ validation during ingestion"""
    
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
        
        self.processor = ScheduledIngestionProcessor(self.scheduled_ingestion)
    
    def test_should_run_dq_check_enabled(self):
        """Test should_run_dq_check when enabled"""
        self.assertTrue(self.processor._should_run_dq_check())
    
    def test_should_run_dq_check_disabled(self):
        """Test should_run_dq_check when disabled"""
        self.scheduled_ingestion.source_config = {"bucket": "test-bucket"}
        self.scheduled_ingestion.save()
        
        processor = ScheduledIngestionProcessor(self.scheduled_ingestion)
        self.assertFalse(processor._should_run_dq_check())
    
    @patch('hub.apps.scheduled_ingestion.ingestion.DQServiceClient')
    def test_run_dq_check_success(self, mock_dq_client_class):
        """Test running DQ check successfully"""
        # Mock DQ client
        mock_dq_client = Mock()
        mock_dq_client.health_check.return_value = (True, {})
        mock_dq_client.run_dq.return_value = {
            "overall_status": "PASS",
            "quality_score": 0.95,
            "checks": [
                {"status": "PASS", "severity": "CRITICAL"},
                {"status": "PASS", "severity": "WARNING"}
            ],
            "execution_time_seconds": 2.5
        }
        mock_dq_client_class.return_value = mock_dq_client
        
        file_content = b"col1,col2\nval1,val2\n"
        file_format = "csv"
        
        result = self.processor._run_dq_check(file_content, file_format)
        
        self.assertIsNotNone(result)
        self.assertEqual(result["overall_status"], "PASS")
        self.assertEqual(result["quality_score"], 0.95)
        mock_dq_client.run_dq.assert_called_once()
    
    @patch('hub.apps.scheduled_ingestion.ingestion.DQServiceClient')
    def test_run_dq_check_service_unavailable(self, mock_dq_client_class):
        """Test running DQ check when service is unavailable"""
        # Mock DQ client
        mock_dq_client = Mock()
        mock_dq_client.health_check.return_value = (False, {})
        mock_dq_client_class.return_value = mock_dq_client
        
        file_content = b"col1,col2\nval1,val2\n"
        file_format = "csv"
        
        result = self.processor._run_dq_check(file_content, file_format)
        
        self.assertIsNone(result)
        mock_dq_client.run_dq.assert_not_called()
    
    @patch('hub.apps.scheduled_ingestion.ingestion.DQServiceClient')
    def test_run_dq_check_strict_mode_failure(self, mock_dq_client_class):
        """Test running DQ check in strict mode when check fails"""
        # Mock DQ client
        mock_dq_client = Mock()
        mock_dq_client.health_check.return_value = (True, {})
        mock_dq_client.run_dq.side_effect = Exception("DQ service error")
        mock_dq_client_class.return_value = mock_dq_client
        
        file_content = b"col1,col2\nval1,val2\n"
        file_format = "csv"
        
        with self.assertRaises(ValueError) as cm:
            self.processor._run_dq_check(file_content, file_format)
        
        self.assertIn("DQ check failed", str(cm.exception))
    
    def test_is_dq_result_valid_pass(self):
        """Test is_dq_result_valid for passing result"""
        dq_result = {
            "overall_status": "PASS",
            "quality_score": 0.95,
            "checks": [
                {"status": "PASS", "severity": "CRITICAL"},
                {"status": "PASS", "severity": "WARNING"}
            ]
        }
        
        self.assertTrue(self.processor._is_dq_result_valid(dq_result))
    
    def test_is_dq_result_valid_fail_status(self):
        """Test is_dq_result_valid for failing status"""
        dq_result = {
            "overall_status": "FAIL",
            "quality_score": 0.95,
            "checks": []
        }
        
        self.assertFalse(self.processor._is_dq_result_valid(dq_result))
    
    def test_is_dq_result_valid_low_score(self):
        """Test is_dq_result_valid for low quality score"""
        dq_result = {
            "overall_status": "PASS",
            "quality_score": 0.5,  # Below 0.8 threshold
            "checks": []
        }
        
        self.assertFalse(self.processor._is_dq_result_valid(dq_result))
    
    def test_is_dq_result_valid_critical_failure(self):
        """Test is_dq_result_valid for critical check failure"""
        dq_result = {
            "overall_status": "PASS",
            "quality_score": 0.95,
            "checks": [
                {"status": "FAIL", "severity": "CRITICAL"},
                {"status": "PASS", "severity": "WARNING"}
            ]
        }
        
        self.assertFalse(self.processor._is_dq_result_valid(dq_result))
    
    def test_format_dq_failure_message(self):
        """Test formatting DQ failure message"""
        dq_result = {
            "overall_status": "FAIL",
            "quality_score": 0.6,
            "checks": [
                {"status": "FAIL", "severity": "CRITICAL"},
                {"status": "PASS", "severity": "WARNING"},
                {"status": "FAIL", "severity": "MEDIUM"}
            ]
        }
        
        message = self.processor._format_dq_failure_message(dq_result)
        
        self.assertIn("FAIL", message)
        self.assertIn("60.00%", message)
        self.assertIn("Critical failures: 1", message)
        self.assertIn("Total failures: 2", message)

