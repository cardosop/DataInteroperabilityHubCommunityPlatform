"""
Integration tests for DCS removal.

These tests verify that DCS removal works correctly across the entire system,
including API endpoints, normalization, validation, and semantic mapping.
"""
import pytest
import json
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from hub.apps.tenants.models import Tenant
from hub.apps.contracts.models import Contract, OriginalSpecType, NormalizationStatus
from hub.apps.contracts.normalization import normalize_contract
from hub.apps.contracts.spec_detection import detect_spec_type

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class DCSRemovalIntegrationTest(TransactionTestCase):
    """Integration tests for DCS removal across the system"""
    
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
    
    def test_odcs_contract_full_workflow(self):
        """Test complete ODCS contract workflow: creation -> normalization -> validation"""
        odcs_contract_yaml = """
apiVersion: odcs.io/v3.0.2
kind: DataContract
id: test-contract-integration
name: Test Contract Integration
version: 1.0.0
description: Test contract for integration testing
schema:
  fields:
    - name: id
      type: string
      nullable: false
      description: Unique identifier
    - name: name
      type: string
      nullable: true
      description: Name field
info:
  owners:
    - name: Test Owner
      email: owner@example.com
  tags:
    - test
    - integration
"""
        
        # Step 1: Create contract via API
        response = self.client.post(
            '/api/v1/contracts/contracts/',
            {
                'original_raw': odcs_contract_yaml,
                'original_format': 'YAML'
            },
            format='json'
        )
        
        # Should succeed
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        contract_id = response.data['id']
        
        # Step 2: Verify contract was created with correct spec type
        contract = Contract.objects.get(id=contract_id)
        self.assertEqual(contract.original_spec_type, OriginalSpecType.ODCS)
        self.assertEqual(contract.original_spec_version, '3.0.2')
        
        # Step 3: Verify normalization succeeded
        self.assertIsNotNone(contract.hub_contract_json)
        self.assertIn(contract.normalization_status, [
            NormalizationStatus.NORMALIZED_OK,
            NormalizationStatus.NORMALIZED_WITH_WARNINGS
        ])
        
        # Step 4: Verify HubContract structure
        hub_contract = contract.hub_contract_json
        self.assertEqual(hub_contract['id'], 'test-contract-integration')
        # Name is in info.name, not at root level
        self.assertIn('info', hub_contract)
        self.assertEqual(hub_contract['info'].get('name'), 'Test Contract Integration')
        self.assertIn('schema', hub_contract)
        self.assertIn('fields', hub_contract['schema'])
        self.assertEqual(len(hub_contract['schema']['fields']), 2)
        
        # Step 5: Verify original_spec metadata
        self.assertIn('original_spec', hub_contract)
        self.assertEqual(hub_contract['original_spec']['type'], 'ODCS')
        self.assertEqual(hub_contract['original_spec']['version'], '3.0.2')
    
    def test_dcs_contract_rejection_full_workflow(self):
        """Test that DCS contracts are rejected throughout the workflow"""
        dcs_contract_yaml = """
dataContractSpecification: 0.9.0
id: test-dcs-contract
info:
  title: Test DCS Contract
  version: 1.0.0
schema:
  type: object
  properties:
    field1:
      type: string
"""
        
        # Step 1: Try to create contract via API
        response = self.client.post(
            '/api/v1/contracts/contracts/',
            {
                'original_raw': dcs_contract_yaml,
                'original_format': 'YAML'
            },
            format='json'
        )
        
        # Should fail
        self.assertIn(response.status_code, [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ])
        
        # Step 2: Verify no contract was created
        contract_count = Contract.objects.filter(
            tenant=self.tenant,
            hub_contract_json__id='test-dcs-contract'
        ).count()
        self.assertEqual(contract_count, 0)
        
        # Step 3: Verify error message contains migration guidance
        error_data = response.data
        error_message = str(error_data)
        if 'errors' in error_data:
            error_message = ' '.join(str(e) for e in error_data.get('errors', []))
        elif 'detail' in error_data:
            error_message = str(error_data['detail'])
        
        self.assertIn('DCS', error_message or 'Data Contract Specification' in error_message)
        self.assertIn('ODCS', error_message)
    
    def test_normalization_rejects_dcs_directly(self):
        """Test that normalization function directly rejects DCS contracts"""
        dcs_contract_yaml = """
dataContractSpecification: 0.9.0
id: test-dcs
info:
  title: Test
"""
        
        hub_contract, spec_type, spec_version, norm_status, errors, warnings = normalize_contract(
            dcs_contract_yaml,
            format='yaml'
        )
        
        # Should fail
        self.assertIsNone(hub_contract)
        self.assertEqual(norm_status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertGreater(len(errors), 0)
        
        # Error should mention DCS and migration
        error_message = ' '.join(errors)
        self.assertIn('DCS', error_message or 'Data Contract Specification' in error_message)
        self.assertIn('migrate', error_message.lower())
    
    def test_spec_detection_handles_dcs(self):
        """Test that spec detection properly identifies DCS contracts for error messaging"""
        dcs_contract = {
            'dataContractSpecification': '0.9.0',
            'id': 'test'
        }
        
        # Detection should return ODCS (but normalization will reject)
        spec_type, spec_version = detect_spec_type(dcs_contract)
        self.assertEqual(spec_type, OriginalSpecType.ODCS)
        
        # But normalization should detect and reject
        import yaml
        dcs_yaml = yaml.dump(dcs_contract)
        hub_contract, spec_type, spec_version, norm_status, errors, warnings = normalize_contract(
            dcs_yaml,
            format='yaml'
        )
        
        self.assertIsNone(hub_contract)
        self.assertEqual(norm_status, NormalizationStatus.NORMALIZATION_FAILED)
    
    def test_odcs_contract_with_all_sections(self):
        """Test ODCS contract with all sections normalizes correctly"""
        odcs_contract_yaml = """
apiVersion: odcs.io/v3.0.2
kind: DataContract
id: full-contract
name: Full Contract Test
version: 1.0.0
description: Contract with all sections
schema:
  fields:
    - name: id
      type: string
      nullable: false
info:
  owners:
    - name: Owner 1
      email: owner1@example.com
  tags:
    - tag1
    - tag2
quality:
  default_profile_key: intake_basic
  rules:
    - rule_id: not_null_id
      dimension: completeness
      expression: id IS NOT NULL
      severity: ERROR
privacy_compliance:
  contains_personal_data: true
  personal_data_categories:
    - EMAIL
  jurisdictions:
    - GDPR
lifecycle:
  data_source: OLTP.orders
  refresh_cadence: DAILY
  slas:
    availability: "99.0"
    latency_ms_p95: 5000
marketplace:
  license_summary: MIT License
  intended_use:
    - analytics
  restricted_use:
    - resale
"""
        
        response = self.client.post(
            '/api/v1/contracts/contracts/',
            {
                'original_raw': odcs_contract_yaml,
                'original_format': 'YAML'
            },
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        contract = Contract.objects.get(id=response.data['id'])
        
        # Verify all sections are present
        hub_contract = contract.hub_contract_json
        self.assertIn('info', hub_contract)
        self.assertIn('schema', hub_contract)
        self.assertIn('quality', hub_contract)
        self.assertIn('privacy_compliance', hub_contract)
        self.assertIn('lifecycle', hub_contract)
        self.assertIn('marketplace', hub_contract)
        
        # Verify owners
        self.assertEqual(len(hub_contract['info']['owners']), 1)
        self.assertEqual(hub_contract['info']['owners'][0]['name'], 'Owner 1')
        
        # Verify tags
        self.assertEqual(len(hub_contract['info']['tags']), 2)
        self.assertIn('tag1', hub_contract['info']['tags'])
        
        # Verify quality rules
        self.assertEqual(len(hub_contract['quality']['rules']), 1)
        self.assertEqual(hub_contract['quality']['rules'][0]['rule_id'], 'not_null_id')
    
    def test_original_spec_type_enum_only_odcs(self):
        """Test that OriginalSpecType enum only contains ODCS"""
        from hub.apps.contracts.models import OriginalSpecType
        
        # Get all choices
        choices = [choice[0] for choice in OriginalSpecType.choices]
        
        # Should only contain ODCS
        self.assertEqual(len(choices), 1)
        self.assertEqual(choices[0], OriginalSpecType.ODCS)
        self.assertNotIn('DATACONTRACT_COM', choices)

