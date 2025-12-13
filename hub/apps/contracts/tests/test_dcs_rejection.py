"""
Tests for DCS (Data Contract Specification) rejection.

These tests verify that DCS contracts are properly rejected with clear error messages
directing users to migrate to ODCS.
"""
import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from hub.apps.tenants.models import Tenant
from hub.apps.contracts.models import Contract, OriginalSpecType, NormalizationStatus
from hub.apps.contracts.normalization import normalize_contract
from hub.apps.contracts.spec_detection import detect_spec_type

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class DCSRejectionTestCase(TestCase):
    """Test cases for DCS contract rejection"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            slug='test-tenant'
        )
        self.user.tenant = self.tenant
        self.user.save()
        self.client.force_authenticate(user=self.user)
    
    def test_dcs_contract_detection_in_spec_detection(self):
        """Test that DCS contracts are detected (but will be rejected during normalization)"""
        dcs_contract = {
            'dataContractSpecification': '0.9.0',
            'id': 'test-contract',
            'info': {
                'title': 'Test Contract',
                'version': '1.0.0'
            }
        }
        
        # Detection should return ODCS (but normalization will reject it)
        spec_type, spec_version = detect_spec_type(dcs_contract)
        self.assertEqual(spec_type, OriginalSpecType.ODCS)
        self.assertEqual(spec_version, '3.0.2')
    
    def test_dcs_contract_rejection_in_normalization(self):
        """Test that DCS contracts are rejected during normalization with clear error message"""
        dcs_contract_yaml = """
dataContractSpecification: 0.9.0
id: test-contract
info:
  title: Test Contract
  version: 1.0.0
schema:
  type: object
  properties:
    field1:
      type: string
"""
        
        hub_contract, spec_type, spec_version, norm_status, errors, warnings = normalize_contract(
            dcs_contract_yaml,
            format='yaml'
        )
        
        # Normalization should fail
        self.assertIsNone(hub_contract)
        self.assertEqual(norm_status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertGreater(len(errors), 0)
        
        # Error message should mention DCS deprecation and migration guidance
        error_message = ' '.join(errors)
        self.assertIn('Data Contract Specification', error_message)
        self.assertIn('DCS', error_message)
        self.assertIn('ODCS', error_message)
        self.assertIn('migrate', error_message.lower())
        self.assertIn('https://bitol-io.github.io/open-data-contract-standard', error_message)
    
    def test_dcs_contract_rejection_via_api(self):
        """Test that DCS contracts are rejected via API with proper error response"""
        dcs_contract_yaml = """
dataContractSpecification: 0.9.0
id: test-contract
info:
  title: Test Contract
  version: 1.0.0
schema:
  type: object
  properties:
    field1:
      type: string
"""
        
        response = self.client.post(
            '/api/v1/contracts/contracts/',
            {
                'original_raw': dcs_contract_yaml,
                'original_format': 'YAML'
            },
            format='json'
        )
        
        # Should return 400 Bad Request
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Error message should be clear and helpful
        error_data = response.data
        self.assertIn('error', str(error_data).lower() or 'errors' in error_data or 'detail' in error_data)
        
        # Check error message content
        error_message = str(error_data)
        if 'errors' in error_data:
            error_message = ' '.join(str(e) for e in error_data.get('errors', []))
        elif 'detail' in error_data:
            error_message = str(error_data['detail'])
        
        self.assertIn('DCS', error_message or 'Data Contract Specification' in error_message)
        self.assertIn('ODCS', error_message)
    
    def test_odcs_contract_acceptance(self):
        """Test that ODCS contracts are still accepted (regression test)"""
        odcs_contract_yaml = """
apiVersion: odcs.io/v3.0.2
kind: DataContract
id: test-contract
name: Test Contract
version: 1.0.0
schema:
  fields:
    - name: field1
      type: string
      nullable: false
"""
        
        hub_contract, spec_type, spec_version, norm_status, errors, warnings = normalize_contract(
            odcs_contract_yaml,
            format='yaml'
        )
        
        # Normalization should succeed
        self.assertIsNotNone(hub_contract)
        self.assertEqual(spec_type, OriginalSpecType.ODCS)
        self.assertIn(norm_status, [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS])
    
    def test_dcs_contract_with_api_version_field(self):
        """Test that contracts with both DCS and ODCS-like fields are properly rejected"""
        import json
        # Contract with dataContractSpecification (DCS) but also has apiVersion
        mixed_contract = {
            'dataContractSpecification': '0.9.0',
            'apiVersion': 'odcs.io/v3.0.2',
            'kind': 'DataContract',
            'id': 'test-contract'
        }
        
        # Should detect DCS and reject
        hub_contract, spec_type, spec_version, norm_status, errors, warnings = normalize_contract(
            json.dumps(mixed_contract),
            format='json'
        )
        
        # Should be rejected because dataContractSpecification is present
        self.assertIsNone(hub_contract)
        self.assertEqual(norm_status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertGreater(len(errors), 0)
        
        error_message = ' '.join(errors)
        self.assertIn('DCS', error_message or 'Data Contract Specification' in error_message)
    
    def test_error_message_contains_migration_link(self):
        """Test that error messages contain migration guidance link"""
        dcs_contract_yaml = """
dataContractSpecification: 0.9.0
id: test-contract
"""
        
        hub_contract, spec_type, spec_version, norm_status, errors, warnings = normalize_contract(
            dcs_contract_yaml,
            format='yaml'
        )
        
        error_message = ' '.join(errors)
        # Should contain ODCS documentation link
        self.assertIn('bitol-io.github.io/open-data-contract-standard', error_message)


class DCSRejectionIntegrationTestCase(TestCase):
    """Integration tests for DCS rejection in full workflow"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            slug='test-tenant'
        )
        self.user.tenant = self.tenant
        self.user.save()
        self.client.force_authenticate(user=self.user)
    
    def test_dcs_contract_creation_fails(self):
        """Test that creating a contract with DCS format fails via API"""
        dcs_contract_yaml = """
dataContractSpecification: 0.9.0
id: test-contract
info:
  title: Test Contract
  version: 1.0.0
schema:
  type: object
  properties:
    field1:
      type: string
"""
        
        response = self.client.post(
            '/api/v1/contracts/contracts/',
            {
                'original_raw': dcs_contract_yaml,
                'original_format': 'YAML'
            },
            format='json'
        )
        
        # Should fail
        self.assertIn(response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY])
        
        # No contract should be created
        contract_count = Contract.objects.filter(tenant=self.tenant).count()
        self.assertEqual(contract_count, 0)
    
    def test_dcs_contract_update_fails(self):
        """Test that updating a contract to DCS format fails"""
        # First create an ODCS contract
        odcs_contract_yaml = """
apiVersion: odcs.io/v3.0.2
kind: DataContract
id: test-contract
name: Test Contract
version: 1.0.0
schema:
  fields:
    - name: field1
      type: string
      nullable: false
"""
        
        create_response = self.client.post(
            '/api/v1/contracts/contracts/',
            {
                'original_raw': odcs_contract_yaml,
                'original_format': 'YAML'
            },
            format='json'
        )
        
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        contract_id = create_response.data['id']
        
        # Try to update with DCS format
        dcs_contract_yaml = """
dataContractSpecification: 0.9.0
id: test-contract
info:
  title: Test Contract
  version: 1.0.0
"""
        
        update_response = self.client.put(
            f'/api/v1/contracts/contracts/{contract_id}/',
            {
                'original_raw': dcs_contract_yaml,
                'original_format': 'YAML'
            },
            format='json'
        )
        
        # Should fail
        self.assertIn(update_response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY])

