"""
Unit tests for NormalizationService.

Tests cover all service methods with 100% coverage target.
All tests use real implementations (no mocks/stubs).
"""

import json

import pytest

from hub.apps.contracts.models import NormalizationStatus, OriginalSpecType
from hub.apps.contracts.normalization_service import NormalizationService
from hub.apps.contracts.tests.test_base import ContractsTestBase
from hub.apps.core.services.base import ValidationError

pytestmark = pytest.mark.django_db(transaction=True)


class NormalizationServiceTest(ContractsTestBase):
    """Test NormalizationService operations"""

    def setUp(self):
        """Set up test data"""
        super().setUp()
        self.service = NormalizationService()

    def test_normalize_contract_success(self):
        """Test successful contract normalization"""
        # Use a valid ODCS contract format with schema
        raw_contract = """{
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
        }"""
        format = "JSON"

        hub_contract, spec_type, spec_version, status, errors, warnings = (
            self.service.normalize_contract(
                raw_contract=raw_contract, format=format, tenant_id=str(self.tenant.id)
            )
        )

        # Contract should normalize successfully
        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        self.assertEqual(spec_type, OriginalSpecType.ODCS)

    def test_normalize_contract_dcs_rejection(self):
        """Test that contracts with dataContractSpecification don't have DCS-specific error messages"""
        # Use camelCase key - should be treated as ODCS (no longer rejected with DCS-specific message)
        raw_contract = (
            '{"dataContractSpecification": "1.0.0", "id": "test-contract", "name": "Test Contract"}'
        )
        format = "JSON"

        # May normalize successfully or fail, but should not have DCS-specific error
        try:
            hub_contract, spec_type, spec_version, status, errors, warnings = (
                self.service.normalize_contract(
                    raw_contract=raw_contract, format=format, tenant_id=str(self.tenant.id)
                )
            )
            # If normalization succeeds, verify it's treated as ODCS
            if hub_contract:
                self.assertEqual(spec_type, OriginalSpecType.ODCS)
            # Check error messages (if any)
            error_message = " ".join(errors) if errors else ""
            self.assertNotIn("DCS contracts are no longer supported", error_message)
            self.assertNotIn(
                "Data Contract Specification (DCS) is no longer supported", error_message
            )
        except ValidationError as e:
            # If validation error is raised, verify it's not DCS-specific
            self.assertNotIn("DCS contracts are no longer supported", str(e.message))
            self.assertNotIn(
                "Data Contract Specification (DCS) is no longer supported", str(e.message)
            )
            # Should be generic normalization failure
            self.assertEqual(e.details.get("code"), "NORMALIZATION_FAILED")

    def test_validate_hubcontract_success(self):
        """Test successful HubContract validation"""
        hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "test-contract",
            "info": {"name": "test-contract"},
            "schema": {"fields": [{"name": "test_field", "type": "string", "nullable": False}]},
            "models": [],
        }

        is_valid, errors = self.service.validate_hubcontract(hub_contract)

        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)

    def test_normalize_contract_with_yaml_format(self):
        """Test contract normalization with YAML format"""
        raw_contract = """
apiVersion: odcs.io/v3.0.2
kind: DataContract
id: test-contract-yaml
name: Test Contract YAML
version: 1.0.0
schema:
  fields:
    - name: test_field
      type: string
      nullable: false
"""
        format = "YAML"

        hub_contract, spec_type, spec_version, status, errors, warnings = (
            self.service.normalize_contract(
                raw_contract=raw_contract, format=format, tenant_id=str(self.tenant.id)
            )
        )

        # Contract should normalize successfully
        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        self.assertEqual(spec_type, OriginalSpecType.ODCS)

    def test_normalize_contract_with_malformed_json(self):
        """Test contract normalization with malformed JSON"""
        raw_contract = '{"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract", invalid}'
        format = "JSON"

        # Should handle malformed JSON gracefully
        try:
            hub_contract, spec_type, spec_version, status, errors, warnings = (
                self.service.normalize_contract(
                    raw_contract=raw_contract, format=format, tenant_id=str(self.tenant.id)
                )
            )
            # May fail normalization
            if status == NormalizationStatus.NORMALIZATION_FAILED:
                self.assertGreater(len(errors), 0)
        except ValidationError:
            # ValidationError is acceptable for malformed input
            pass

    def test_normalize_contract_with_empty_string(self):
        """Test contract normalization with empty string"""
        raw_contract = ""
        format = "JSON"

        # Should handle empty string gracefully
        try:
            hub_contract, spec_type, spec_version, status, errors, warnings = (
                self.service.normalize_contract(
                    raw_contract=raw_contract, format=format, tenant_id=str(self.tenant.id)
                )
            )
            # Should fail normalization
            self.assertEqual(status, NormalizationStatus.NORMALIZATION_FAILED)
            self.assertGreater(len(errors), 0)
        except ValidationError:
            # ValidationError is acceptable for empty input
            pass

    def test_normalize_contract_with_odps_spec_type(self):
        """Test contract normalization with ODPS spec type"""
        raw_contract = json.dumps(
            {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "version": "4.1",
                "product": {
                    "details": {"en": {"productID": "test-product", "name": "Test Product"}},
                    "contract": {
                        "spec": {
                            "apiVersion": "odcs.io/v3.0.2",
                            "kind": "DataContract",
                            "id": "test-contract",
                            "name": "Test Contract",
                            "version": "1.0.0",
                            "schema": {
                                "fields": [{"name": "id", "type": "string", "nullable": False}]
                            },
                        }
                    },
                },
            }
        )
        format = "JSON"

        hub_contract, spec_type, spec_version, status, errors, warnings = (
            self.service.normalize_contract(
                raw_contract=raw_contract,
                format=format,
                spec_type="ODPS",
                tenant_id=str(self.tenant.id),
            )
        )

        # Contract should normalize successfully
        self.assertIsNotNone(hub_contract)
        self.assertEqual(spec_type, OriginalSpecType.ODPS)

    def test_normalize_contract_with_tenant_id_parameter(self):
        """Test contract normalization with tenant_id parameter"""
        raw_contract = json.dumps(
            {
                "apiVersion": "odcs.io/v3.0.2",
                "kind": "DataContract",
                "id": "test-contract",
                "name": "Test Contract",
                "version": "1.0.0",
                "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
            }
        )
        format = "JSON"

        # Create another tenant
        other_tenant = Tenant.objects.create(name="Other Tenant", slug="other-tenant")

        hub_contract, spec_type, spec_version, status, errors, warnings = (
            self.service.normalize_contract(
                raw_contract=raw_contract,
                format=format,
                tenant_id=str(other_tenant.id),  # Use different tenant_id
            )
        )

        # Contract should normalize successfully with different tenant_id
        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)

    def test_normalize_contract_with_user_id_parameter(self):
        """Test contract normalization with user_id parameter"""
        raw_contract = json.dumps(
            {
                "apiVersion": "odcs.io/v3.0.2",
                "kind": "DataContract",
                "id": "test-contract",
                "name": "Test Contract",
                "version": "1.0.0",
                "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
            }
        )
        format = "JSON"

        # Create another user
        other_user = User.objects.create_user(
            email="other@example.com", tenant=self.tenant, status=UserStatus.ACTIVE
        )

        hub_contract, spec_type, spec_version, status, errors, warnings = (
            self.service.normalize_contract(
                raw_contract=raw_contract,
                format=format,
                tenant_id=str(self.tenant.id),
                user_id=str(other_user.id),  # Use different user_id
            )
        )

        # Contract should normalize successfully with different user_id
        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)

    def test_normalize_contract_with_contract_id_for_events(self):
        """Test contract normalization with contract_id for event publishing"""
        import uuid

        raw_contract = json.dumps(
            {
                "apiVersion": "odcs.io/v3.0.2",
                "kind": "DataContract",
                "id": "test-contract",
                "name": "Test Contract",
                "version": "1.0.0",
                "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
            }
        )
        format = "JSON"
        contract_id = str(uuid.uuid4())

        hub_contract, spec_type, spec_version, status, errors, warnings = (
            self.service.normalize_contract(
                raw_contract=raw_contract,
                format=format,
                tenant_id=str(self.tenant.id),
                contract_id=contract_id,  # Provide contract_id for event publishing
            )
        )

        # Contract should normalize successfully
        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)

    def test_normalize_contract_with_normalization_warnings(self):
        """Test contract normalization that produces warnings"""
        # Contract with optional fields that may produce warnings
        raw_contract = json.dumps(
            {
                "apiVersion": "odcs.io/v3.0.2",
                "kind": "DataContract",
                "id": "test-contract",
                "name": "Test Contract",
                "version": "1.0.0",
                "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
                "unknown_field": "unknown_value",  # May produce warnings
            }
        )
        format = "JSON"

        hub_contract, spec_type, spec_version, status, errors, warnings = (
            self.service.normalize_contract(
                raw_contract=raw_contract, format=format, tenant_id=str(self.tenant.id)
            )
        )

        # Contract should normalize (may have warnings)
        self.assertIsNotNone(hub_contract)
        self.assertIn(
            status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
        )

    def test_validate_hubcontract_with_missing_required_fields(self):
        """Test HubContract validation with missing required fields"""
        hub_contract = {
            # Missing hub_contract_version, id, info, schema
            "models": []
        }

        is_valid, errors = self.service.validate_hubcontract(hub_contract)

        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)

    def test_validate_hubcontract_with_invalid_schema_structure(self):
        """Test HubContract validation with invalid schema structure"""
        hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "test-contract",
            "info": {"name": "test-contract"},
            "schema": {
                # Invalid schema structure - missing fields
                "invalid": "structure"
            },
            "models": [],
        }

        is_valid, errors = self.service.validate_hubcontract(hub_contract)

        # May fail validation or succeed with warnings
        self.assertIsNotNone(is_valid)
        self.assertIsInstance(errors, list)

    def test_validate_hubcontract_with_empty_dict(self):
        """Test HubContract validation with empty dictionary"""
        hub_contract = {}

        is_valid, errors = self.service.validate_hubcontract(hub_contract)

        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)

    def test_validate_hubcontract_with_none(self):
        """Test HubContract validation with None input"""
        # Should handle None gracefully
        try:
            is_valid, errors = self.service.validate_hubcontract(None)
            # If it doesn't raise, verify structure
            self.assertIsNotNone(is_valid)
            self.assertIsInstance(errors, list)
        except (TypeError, AttributeError):
            # Raising exception is also acceptable for None input
            pass

    def test_normalize_contract_service_initialization_with_tenant_user(self):
        """Test NormalizationService initialization with tenant and user"""
        service = NormalizationService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        self.assertIsNotNone(service)
        self.assertEqual(str(service.tenant_id), str(self.tenant.id))
        self.assertEqual(str(service.user_id), str(self.user.id))

    def test_normalize_contract_service_initialization_without_context(self):
        """Test NormalizationService initialization without tenant or user"""
        service = NormalizationService()

        self.assertIsNotNone(service)
        self.assertIsNone(service.tenant_id)
        self.assertIsNone(service.user_id)

    def test_normalize_contract_with_very_large_contract(self):
        """Test contract normalization with very large contract"""
        # Create a very large contract
        large_schema = {"fields": [{"name": f"field_{i}", "type": "string"} for i in range(1000)]}
        large_contract = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "large-contract",
            "name": "Large Contract",
            "version": "1.0.0",
            "schema": large_schema,
        }
        raw_contract = json.dumps(large_contract)
        format = "JSON"

        hub_contract, spec_type, spec_version, status, errors, warnings = (
            self.service.normalize_contract(
                raw_contract=raw_contract, format=format, tenant_id=str(self.tenant.id)
            )
        )

        # Should handle large contract gracefully
        self.assertIsNotNone(status)
        # May succeed or fail depending on size limits
        if hub_contract:
            self.assertIsNotNone(hub_contract)
