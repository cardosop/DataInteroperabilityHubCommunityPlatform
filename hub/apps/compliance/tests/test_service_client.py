"""
Unit tests for compliance service client (critical path).
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from hub.apps.compliance.service_client import ComplianceServiceClient



pytestmark = pytest.mark.django_db(transaction=True)
class ComplianceServiceClientTest(TestCase):
    """Test compliance service client (critical path for compliance)"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = ComplianceServiceClient()
    
    @patch('hub.apps.compliance.service_client.httpx.Client')
    def test_run_compliance_success(self, mock_client_class):
        """Test successful compliance run"""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.json.return_value = {
            'overall_status': 'PASS',
            'risk_level': 'LOW',
            'allowed_to_store': True,
            'detected_categories': {},
            'column_findings': [],
            'regulation_mapping': {
                'GDPR': 'COMPLIANT',
                'CCPA': 'COMPLIANT'
            }
        }
        mock_response.raise_for_status = Mock()
        
        # Mock the client's _request_with_retry method
        with patch.object(self.client, '_request_with_retry', return_value=mock_response):
            result = self.client.scan_file(
                file_content=b'id,name\n1,Test',
                file_format='csv',
                scan_mode='internal'
            )
        
        self.assertEqual(result['overall_status'], 'PASS')
        self.assertEqual(result['risk_level'], 'LOW')
        self.assertTrue(result['allowed_to_store'])
    
    @patch('hub.apps.compliance.service_client.httpx.Client')
    def test_run_compliance_with_pii(self, mock_client_class):
        """Test compliance run with PII detected"""
        mock_response = Mock()
        mock_response.json.return_value = {
            'overall_status': 'FAIL',
            'risk_level': 'HIGH',
            'allowed_to_store': False,
            'detected_categories': {
                'EMAIL': 100,
                'PHONE': 50
            },
            'column_findings': [
                {
                    'column': 'email',
                    'pii_types': ['EMAIL'],
                    'count': 100
                },
                {
                    'column': 'phone',
                    'pii_types': ['PHONE'],
                    'count': 50
                }
            ],
            'regulation_mapping': {
                'GDPR': 'NON_COMPLIANT',
                'CCPA': 'NON_COMPLIANT'
            }
        }
        mock_response.raise_for_status = Mock()
        
        # Mock the client's _request_with_retry method
        with patch.object(self.client, '_request_with_retry', return_value=mock_response):
            result = self.client.scan_file(
                file_content=b'email,phone\ntest@example.com,555-1234',
                file_format='csv',
                scan_mode='internal'
            )
        
        self.assertEqual(result['overall_status'], 'FAIL')
        self.assertEqual(result['risk_level'], 'HIGH')
        self.assertFalse(result['allowed_to_store'])
        self.assertEqual(len(result['column_findings']), 2)
    
    @patch('hub.apps.compliance.service_client.httpx.Client')
    def test_run_compliance_scan_only(self, mock_client_class):
        """Test compliance run in scan-only mode"""
        mock_response = Mock()
        mock_response.json.return_value = {
            'overall_status': 'WARN',
            'risk_level': 'MEDIUM',
            'allowed_to_store': None,  # Not determined in scan-only mode
            'detected_categories': {
                'EMAIL': 10
            },
            'column_findings': [
                {
                    'column': 'email',
                    'pii_types': ['EMAIL'],
                    'count': 10
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        
        # Mock the client's _request_with_retry method
        with patch.object(self.client, '_request_with_retry', return_value=mock_response):
            result = self.client.scan_file(
                file_content=b'email\ntest@example.com',
                file_format='csv',
                scan_mode='external'  # scan-only mode
            )
        
        self.assertEqual(result['overall_status'], 'WARN')
        self.assertIsNone(result.get('allowed_to_store'))
        self.assertEqual(len(result['column_findings']), 1)

