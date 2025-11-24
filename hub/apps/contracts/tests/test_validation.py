"""
Unit tests for contract validation.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock

from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    ValidationStatus,
    OriginalSpecType,
    OriginalFormat
)
from hub.apps.contracts.cli_client import (
    DataContractCLIClient,
    interpret_validation_status,
    group_errors_by_category
)
from hub.apps.users.models import UserStatus
from hub.apps.tenants.models import Tenant

User = get_user_model()


class ContractValidationTest(TestCase):
    """Test contract validation"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        
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
    
    @patch('hub.apps.contracts.cli_client.DataContractCLIClient.validate')
    def test_validate_contract_sync(self, mock_validate):
        """Test synchronous contract validation"""
        self.client.force_authenticate(user=self.user)
        
        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test", "schema": {"fields": [{"name": "id", "type": "string"}]}}',
            created_by=self.user
        )
        
        # Mock validation result
        mock_validate.return_value = {
            'validation_status': 'VALID',
            'issues': [],
            'cli_version': '1.0.0'
        }
        
        response = self.client.post(f"/api/v1/contracts/contracts/{contract.id}/validate/", {}, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['validation_status'], 'VALID')
        
        # Verify contract was updated
        contract.refresh_from_db()
        self.assertEqual(contract.validation_status, ValidationStatus.VALID)
        self.assertEqual(contract.cli_version, '1.0.0')
        self.assertIsNotNone(contract.last_validated_at)
    
    @patch('hub.apps.contracts.cli_client.DataContractCLIClient.validate')
    def test_validate_contract_with_errors(self, mock_validate):
        """Test contract validation with errors"""
        self.client.force_authenticate(user=self.user)
        
        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            created_by=self.user
        )
        
        # Mock validation result with errors
        mock_validate.return_value = {
            'validation_status': 'INVALID',
            'issues': [
                {
                    'severity': 'ERROR',
                    'category': 'schema',
                    'path': '/schema',
                    'message': 'Schema is required',
                    'rule_id': 'schema_required'
                }
            ],
            'cli_version': '1.0.0'
        }
        
        response = self.client.post(f"/api/v1/contracts/contracts/{contract.id}/validate/", {}, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['validation_status'], 'INVALID')
        self.assertEqual(len(response.data['errors']), 1)
        self.assertIn('grouped_errors', response.data)
        
        # Verify contract was updated
        contract.refresh_from_db()
        self.assertEqual(contract.validation_status, ValidationStatus.INVALID)
        self.assertEqual(len(contract.validation_errors), 1)
    
    @patch('hub.apps.contracts.views.create_job')
    def test_validate_contract_async(self, mock_create_job):
        """Test asynchronous contract validation"""
        self.client.force_authenticate(user=self.user)
        
        # Create large contract (triggers async)
        large_contract = '{"id": "test", "name": "Test"}' * 10000  # Large contract
        
        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw=large_contract,
            created_by=self.user
        )
        
        # Mock job creation
        from hub.apps.jobs.models import Job, JobStatus
        mock_job = Job.objects.create(
            tenant=self.tenant,
            type='CONTRACT_VALIDATION',
            status=JobStatus.PENDING,
            resource_type='CONTRACT',
            resource_id=contract.id,
            created_by=self.user
        )
        mock_create_job.return_value = mock_job
        
        response = self.client.post(
            f"/api/v1/contracts/contracts/{contract.id}/validate/",
            {'async': True},
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertIn('job_id', response.data)
        self.assertEqual(response.data['status'], 'pending')
    
    @patch('hub.apps.contracts.cli_client.DataContractCLIClient.lint')
    def test_lint_contract(self, mock_lint):
        """Test contract linting"""
        self.client.force_authenticate(user=self.user)
        
        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            created_by=self.user
        )
        
        # Mock lint result
        mock_lint.return_value = {
            'issues': [
                {
                    'severity': 'WARNING',
                    'message': 'Consider adding description',
                    'rule_id': 'missing_description'
                }
            ],
            'cli_version': '1.0.0'
        }
        
        response = self.client.post(f"/api/v1/contracts/contracts/{contract.id}/lint/", {}, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('issues', response.data)
        self.assertEqual(len(response.data['issues']), 1)
    
    @patch('hub.apps.contracts.cli_client.DataContractCLIClient.convert')
    def test_convert_contract(self, mock_convert):
        """Test contract conversion"""
        self.client.force_authenticate(user=self.user)
        
        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            created_by=self.user
        )
        
        # Mock conversion result
        mock_convert.return_value = {
            'converted_contract': 'id: test\nname: Test\n',
            'cli_version': '1.0.0'
        }
        
        response = self.client.post(
            f"/api/v1/contracts/contracts/{contract.id}/convert/",
            {'target_format': 'YAML'},
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('converted_contract', response.data)
        self.assertEqual(response.data['format'], 'YAML')
    
    def test_interpret_validation_status_valid(self):
        """Test interpreting VALID validation status"""
        result = {
            'validation_status': 'VALID',
            'issues': []
        }
        
        status, errors, warnings = interpret_validation_status(result)
        
        self.assertEqual(status, 'VALID')
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(warnings), 0)
    
    def test_interpret_validation_status_with_errors(self):
        """Test interpreting validation status with errors"""
        result = {
            'validation_status': 'INVALID',
            'issues': [
                {
                    'severity': 'ERROR',
                    'category': 'schema',
                    'path': '/schema',
                    'message': 'Schema required',
                    'rule_id': 'schema_required'
                },
                {
                    'severity': 'WARNING',
                    'category': 'style',
                    'path': '/name',
                    'message': 'Consider adding description',
                    'rule_id': 'missing_description'
                }
            ]
        }
        
        status, errors, warnings = interpret_validation_status(result)
        
        self.assertEqual(status, 'INVALID')
        self.assertEqual(len(errors), 1)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(errors[0]['category'], 'schema')
    
    def test_group_errors_by_category(self):
        """Test grouping errors by category"""
        errors = [
            {'category': 'schema', 'message': 'Schema error 1'},
            {'category': 'schema', 'message': 'Schema error 2'},
            {'category': 'format', 'message': 'Format error'},
            {'category': 'unknown', 'message': 'Unknown error'}
        ]
        
        grouped = group_errors_by_category(errors)
        
        self.assertEqual(len(grouped['schema']), 2)
        self.assertEqual(len(grouped['format']), 1)
        self.assertEqual(len(grouped['unknown']), 1)

