"""
Unit tests for NormalizationService.

Tests cover all service methods with 100% coverage target.
"""
import pytest
from django.test import TestCase
from unittest.mock import patch, Mock

from hub.apps.contracts.normalization_service import NormalizationService
from hub.apps.contracts.models import NormalizationStatus, OriginalSpecType
from hub.apps.core.services.base import ValidationError
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus


pytestmark = pytest.mark.django_db(transaction=True)


class NormalizationServiceTest(TestCase):
    """Test NormalizationService operations"""

    def setUp(self):
        """Set up test data"""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.user = User.objects.create_user(
            email="test@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.service = NormalizationService()

    def test_normalize_contract_success(self):
        """Test successful contract normalization"""
        # Use a valid ODCS contract format with schema
        raw_contract = '''{
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {
                        "name": "test_field",
                        "type": "string",
                        "nullable": false
                    }
                ]
            }
        }'''
        format = "JSON"

        hub_contract, spec_type, spec_version, status, errors, warnings = self.service.normalize_contract(
            raw_contract=raw_contract,
            format=format,
            tenant_id=str(self.tenant.id)
        )

        # Contract should normalize successfully
        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        self.assertEqual(spec_type, OriginalSpecType.ODCS)

    def test_normalize_contract_dcs_rejection(self):
        """Test that contracts with dataContractSpecification don't have DCS-specific error messages"""
        # Use camelCase key - should be treated as ODCS (no longer rejected with DCS-specific message)
        raw_contract = '{"dataContractSpecification": "1.0.0", "id": "test-contract", "name": "Test Contract"}'
        format = "JSON"

        # May normalize successfully or fail, but should not have DCS-specific error
        try:
            hub_contract, spec_type, spec_version, status, errors, warnings = self.service.normalize_contract(
                raw_contract=raw_contract,
                format=format,
                tenant_id=str(self.tenant.id)
            )
            # If normalization succeeds, verify it's treated as ODCS
            if hub_contract:
                self.assertEqual(spec_type, OriginalSpecType.ODCS)
            # Check error messages (if any)
            error_message = ' '.join(errors) if errors else ''
            self.assertNotIn('DCS contracts are no longer supported', error_message)
            self.assertNotIn('Data Contract Specification (DCS) is no longer supported', error_message)
        except ValidationError as e:
            # If validation error is raised, verify it's not DCS-specific
            self.assertNotIn('DCS contracts are no longer supported', str(e.message))
            self.assertNotIn('Data Contract Specification (DCS) is no longer supported', str(e.message))
            # Should be generic normalization failure
            self.assertEqual(e.details.get('code'), 'NORMALIZATION_FAILED')

    def test_validate_hubcontract_success(self):
        """Test successful HubContract validation"""
        hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "test-contract",
            "info": {"name": "test-contract"},
            "schema": {
                "fields": [
                    {
                        "name": "test_field",
                        "type": "string",
                        "nullable": False
                    }
                ]
            },
            "models": []
        }

        is_valid, errors = self.service.validate_hubcontract(hub_contract)

        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)

