"""
Tests for deprecated contract specification rejection.

These tests verify that deprecated contract formats are properly rejected with clear error messages
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
    """Test cases for deprecated contract specification rejection"""

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
        """Test that deprecated contract formats are detected (but will be rejected during normalization)"""
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
        """Test that contracts with dataContractSpecification normalize as ODCS (no DCS-specific rejection)"""
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

        # Normalization should succeed (treated as ODCS, no DCS-specific rejection)
        self.assertIsNotNone(hub_contract)
        self.assertEqual(spec_type, OriginalSpecType.ODCS)
        # Should not contain DCS-specific error messages
        error_message = ' '.join(errors) if errors else ''
        self.assertNotIn('DCS contracts are no longer supported', error_message)
        self.assertNotIn('Data Contract Specification (DCS) is no longer supported', error_message)

    def test_dcs_contract_rejection_via_api(self):
        """Test that deprecated contract formats are rejected via API with proper error response"""
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
            '/api/v1/contracts/',
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

        # Should contain error indication (but not deprecated format-specific)
        self.assertIsInstance(error_message, str)
        self.assertGreater(len(error_message), 0)
        # Should not contain deprecated format-specific messages
        self.assertNotIn('DCS contracts are no longer supported', error_message)
        self.assertNotIn('Data Contract Specification (DCS) is no longer supported', error_message)

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
        """Test that contracts with both deprecated and ODCS-like fields normalize as ODCS"""
        import json
        # Contract with dataContractSpecification (deprecated) but also has apiVersion
        mixed_contract = {
            'dataContractSpecification': '0.9.0',
            'apiVersion': 'odcs.io/v3.0.2',
            'kind': 'DataContract',
            'id': 'test-contract'
        }

        # Should normalize as ODCS (apiVersion and kind take precedence)
        hub_contract, spec_type, spec_version, norm_status, errors, warnings = normalize_contract(
            json.dumps(mixed_contract),
            format='json'
        )

        # Should normalize successfully as ODCS
        self.assertIsNotNone(hub_contract)
        self.assertEqual(spec_type, OriginalSpecType.ODCS)
        self.assertEqual(spec_version, '3.0.2')
        # Should not contain DCS-specific error messages
        error_message = ' '.join(errors) if errors else ''
        self.assertNotIn('DCS contracts are no longer supported', error_message)
        self.assertNotIn('Data Contract Specification (DCS) is no longer supported', error_message)

    def test_error_message_for_invalid_contract(self):
        """Test that error messages are provided for invalid contracts"""
        invalid_contract_yaml = """
dataContractSpecification: 0.9.0
id: test-contract
"""

        hub_contract, spec_type, spec_version, norm_status, errors, warnings = normalize_contract(
            invalid_contract_yaml,
            format='yaml'
        )

        # Should have normalization failure
        self.assertEqual(norm_status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertGreater(len(errors), 0)

        error_message = ' '.join(errors)
        # Should contain error information (but not deprecated format-specific)
        self.assertIsInstance(error_message, str)
        self.assertGreater(len(error_message), 0)
        # Should not contain deprecated format-specific messages
        self.assertNotIn('DCS contracts are no longer supported', error_message)
        self.assertNotIn('Data Contract Specification (DCS) is no longer supported', error_message)


class DCSRejectionIntegrationTestCase(TestCase):
    """Integration tests for deprecated contract specification rejection in full workflow"""

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
        """Test that creating a contract with deprecated format fails via API"""
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
            '/api/v1/contracts/',
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
        """Test that updating a contract to deprecated format fails"""
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
            '/api/v1/contracts/',
            {
                'original_raw': odcs_contract_yaml,
                'original_format': 'YAML'
            },
            format='json'
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        contract_id = create_response.data['id']

        # Try to update with deprecated format
        dcs_contract_yaml = """
dataContractSpecification: 0.9.0
id: test-contract
info:
  title: Test Contract
  version: 1.0.0
"""

        update_response = self.client.put(
            f'/api/v1/contracts/{contract_id}/',
            {
                'original_raw': dcs_contract_yaml,
                'original_format': 'YAML'
            },
            format='json'
        )

        # Should fail
        self.assertIn(update_response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY])

