"""
Unit tests for contract validation views (critical path).
"""
import pytest
from unittest.mock import patch, Mock
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from hub.apps.tenants.models import Tenant
from hub.apps.contracts.models import Contract, ContractStatus, ValidationStatus, OriginalSpecType, OriginalFormat


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class ContractValidationViewTest(TestCase):
    """Test contract validation endpoints (critical path)"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        
        self.contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test Contract"}',
            hub_contract_version="1.0.0",
            hub_contract_json={"hub_contract_version": "1.0.0", "id": "test"},
            validation_status=ValidationStatus.ERROR,  # Use ERROR as initial state
        )
    
    @patch('hub.apps.contracts.views.DataContractCLIClient')
    def test_validate_contract_synchronous(self, mock_client_class):
        """Test synchronous contract validation"""
        self.client.force_authenticate(user=self.user)
        
        # Mock CLI client
        mock_client = Mock()
        mock_client.validate.return_value = {
            'validation_status': 'VALID',
            'issues': [],
            'cli_version': '1.0.0'
        }
        mock_client_class.return_value = mock_client
        
        # Use APIClient to make actual HTTP request
        response = self.client.post(
            f'/api/v1/contracts/contracts/{self.contract.id}/validate/',
            {'async': False},
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['validation_status'], 'VALID')
        
        # Verify contract was updated
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.validation_status, ValidationStatus.VALID)
    
    @patch('hub.apps.contracts.views.create_job')
    @patch('hub.apps.contracts.views.DataContractCLIClient')
    def test_validate_contract_asynchronous(self, mock_client_class, mock_create_job):
        """Test asynchronous contract validation"""
        self.client.force_authenticate(user=self.user)
        
        # Mock job creation
        from hub.apps.jobs.models import Job, JobStatus
        import uuid
        mock_job = Mock(spec=Job)
        mock_job.id = uuid.uuid4()
        mock_job.status = JobStatus.PENDING
        mock_create_job.return_value = mock_job
        
        # Use APIClient to make actual HTTP request
        response = self.client.post(
            f'/api/v1/contracts/contracts/{self.contract.id}/validate/',
            {'async': True},
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertIn('job_id', response.data)
        mock_create_job.assert_called_once()
    
    @patch('hub.apps.contracts.views.DataContractCLIClient')
    def test_validate_contract_with_errors(self, mock_client_class):
        """Test contract validation with errors"""
        self.client.force_authenticate(user=self.user)
        
        # Mock CLI client with errors
        mock_client = Mock()
        mock_client.validate.return_value = {
            'validation_status': 'INVALID',
            'issues': [
                {
                    'severity': 'ERROR',
                    'category': 'schema',
                    'path': '$.name',
                    'message': 'Name is required',
                    'rule_id': 'required_field'
                }
            ],
            'cli_version': '1.0.0'
        }
        mock_client_class.return_value = mock_client
        
        # Use APIClient to make actual HTTP request
        response = self.client.post(
            f'/api/v1/contracts/contracts/{self.contract.id}/validate/',
            {'async': False},
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['validation_status'], 'INVALID')
        self.assertEqual(len(response.data['errors']), 1)
        
        # Verify contract was updated
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.validation_status, ValidationStatus.INVALID)
        self.assertEqual(len(self.contract.validation_errors), 1)
    
    @patch('hub.apps.contracts.views.DataContractCLIClient')
    def test_validate_contract_with_warnings(self, mock_client_class):
        """Test contract validation with warnings only"""
        self.client.force_authenticate(user=self.user)
        
        # Mock CLI client with warnings
        mock_client = Mock()
        mock_client.validate.return_value = {
            'validation_status': 'WARNING_ONLY',
            'issues': [
                {
                    'severity': 'WARNING',
                    'category': 'style',
                    'message': 'Consider adding description'
                }
            ],
            'cli_version': '1.0.0'
        }
        mock_client_class.return_value = mock_client
        
        # Use APIClient to make actual HTTP request
        response = self.client.post(
            f'/api/v1/contracts/contracts/{self.contract.id}/validate/',
            {'async': False},
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['validation_status'], 'WARNING_ONLY')
        self.assertEqual(len(response.data['warnings']), 1)
        
        # Verify contract was updated
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.validation_status, ValidationStatus.WARNING_ONLY)
    
    @patch('hub.apps.contracts.views.DataContractCLIClient')
    def test_validate_contract_service_error(self, mock_client_class):
        """Test contract validation with service error"""
        self.client.force_authenticate(user=self.user)
        
        # Mock CLI client with error
        mock_client = Mock()
        mock_client.validate.side_effect = Exception("Service unavailable")
        mock_client_class.return_value = mock_client
        
        # Use APIClient to make actual HTTP request
        response = self.client.post(
            f'/api/v1/contracts/contracts/{self.contract.id}/validate/',
            {'async': False},
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('error', response.data)
    
    @patch('hub.apps.contracts.views.DataContractCLIClient')
    def test_validate_contract_enhanced_response(self, mock_client_class):
        """Test enhanced validation response with normalization status and field-level errors"""
        self.client.force_authenticate(user=self.user)
        
        # Set normalization status on contract
        from hub.apps.contracts.models import NormalizationStatus
        self.contract.normalization_status = NormalizationStatus.NORMALIZED_OK
        self.contract.save()
        
        # Mock CLI client with field-level errors
        mock_client = Mock()
        mock_client.validate.return_value = {
            'validation_status': 'INVALID',
            'issues': [
                {
                    'severity': 'ERROR',
                    'category': 'schema',
                    'path': '$.name',
                    'message': 'Name is required',
                    'rule_id': 'required_field'
                },
                {
                    'severity': 'ERROR',
                    'category': 'schema',
                    'path': '$.id',
                    'message': 'ID must be unique',
                    'rule_id': 'unique_id'
                },
                {
                    'severity': 'WARNING',
                    'category': 'style',
                    'path': '$.description',
                    'message': 'Consider adding description',
                    'rule_id': 'missing_description'
                }
            ],
            'cli_version': '1.0.0'
        }
        mock_client_class.return_value = mock_client
        
        # Use APIClient to make actual HTTP request
        response = self.client.post(
            f'/api/v1/contracts/contracts/{self.contract.id}/validate/',
            {'async': False},
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check enhanced response fields
        self.assertIn('validation_status', response.data)
        self.assertIn('valid', response.data)
        self.assertIn('errors', response.data)
        self.assertIn('warnings', response.data)
        self.assertIn('error_count', response.data)
        self.assertIn('warning_count', response.data)
        self.assertIn('schema_compliance', response.data)
        self.assertIn('normalization_status', response.data)
        self.assertIn('normalization_compliant', response.data)
        self.assertIn('field_errors', response.data)
        self.assertIn('cli_version', response.data)
        self.assertIn('validated_at', response.data)
        self.assertIn('contract_id', response.data)
        
        # Verify schema compliance
        self.assertEqual(response.data['schema_compliance']['status'], 'NON_COMPLIANT')
        self.assertFalse(response.data['valid'])
        
        # Verify normalization status
        self.assertEqual(response.data['normalization_status'], NormalizationStatus.NORMALIZED_OK)
        self.assertTrue(response.data['normalization_compliant'])
        
        # Verify field-level errors
        self.assertIn('$.name', response.data['field_errors'])
        self.assertIn('$.id', response.data['field_errors'])
        self.assertEqual(len(response.data['field_errors']['$.name']), 1)
        self.assertEqual(len(response.data['field_errors']['$.id']), 1)
        
        # Verify error counts
        self.assertEqual(response.data['error_count'], 2)
        self.assertEqual(response.data['warning_count'], 1)
    
    @patch('hub.apps.contracts.views.DataContractCLIClient')
    def test_validate_contract_valid_with_normalization(self, mock_client_class):
        """Test validation response for valid contract with normalization status"""
        self.client.force_authenticate(user=self.user)
        
        # Set normalization status on contract
        from hub.apps.contracts.models import NormalizationStatus
        self.contract.normalization_status = NormalizationStatus.NORMALIZED_WITH_WARNINGS
        self.contract.save()
        
        # Mock CLI client with valid status
        mock_client = Mock()
        mock_client.validate.return_value = {
            'validation_status': 'VALID',
            'issues': [],
            'cli_version': '1.0.0'
        }
        mock_client_class.return_value = mock_client
        
        # Use APIClient to make actual HTTP request
        response = self.client.post(
            f'/api/v1/contracts/contracts/{self.contract.id}/validate/',
            {'async': False},
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify schema compliance for valid contract
        self.assertEqual(response.data['schema_compliance']['status'], 'COMPLIANT')
        self.assertTrue(response.data['valid'])
        
        # Verify normalization status
        self.assertEqual(response.data['normalization_status'], NormalizationStatus.NORMALIZED_WITH_WARNINGS)
        self.assertTrue(response.data['normalization_compliant'])
        
        # Verify no field errors for valid contract
        self.assertNotIn('field_errors', response.data)
        self.assertEqual(response.data['error_count'], 0)
        self.assertEqual(response.data['warning_count'], 0)

