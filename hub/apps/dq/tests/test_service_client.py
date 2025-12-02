"""
Unit tests for DQ service client (critical path).
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from hub.apps.dq.service_client import DQServiceClient



pytestmark = pytest.mark.django_db(transaction=True)
class DQServiceClientTest(TestCase):
    """Test DQ service client (critical path for data quality)"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = DQServiceClient()
    
    @patch('hub.apps.dq.service_client.httpx.Client')
    def test_run_dq_success(self, mock_client_class):
        """Test successful DQ run"""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.json.return_value = {
            'overall_status': 'PASS',
            'quality_score': 0.95,
            'checks': [
                {
                    'name': 'expect_column_values_to_not_be_null',
                    'status': 'PASS',
                    'result': {'observed_value': 100}
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        
        # Mock the client's _request_with_retry method
        with patch.object(self.client, '_request_with_retry', return_value=mock_response):
            result = self.client.run_dq(
                file_content=b'id,name\n1,Test',
                file_format='csv',
                profile_key='intake_basic_gx'
            )
        
        self.assertEqual(result['overall_status'], 'PASS')
        self.assertEqual(result['quality_score'], 0.95)
    
    @patch('hub.apps.dq.service_client.httpx.Client')
    def test_run_dq_with_failures(self, mock_client_class):
        """Test DQ run with failures"""
        mock_response = Mock()
        mock_response.json.return_value = {
            'overall_status': 'FAIL',
            'quality_score': 0.60,
            'checks': [
                {
                    'name': 'expect_column_values_to_not_be_null',
                    'status': 'FAIL',
                    'result': {'observed_value': 50, 'expected_value': 100}
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        
        # Use unique file content to avoid cache interference from other tests
        unique_content = b'id,name\n1,TestFailure\n2,AnotherFailure'
        
        # Mock the client's _request_with_retry method
        with patch.object(self.client, '_request_with_retry', return_value=mock_response):
            result = self.client.run_dq(
                file_content=unique_content,
                file_format='csv',
                profile_key='intake_basic_gx',
                use_cache=False  # Disable cache to avoid interference
            )
        
        self.assertEqual(result['overall_status'], 'FAIL')
        self.assertEqual(result['quality_score'], 0.60)
        self.assertEqual(result['checks'][0]['status'], 'FAIL')

