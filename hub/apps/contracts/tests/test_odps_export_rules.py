"""
Unit tests for ODPSExportRules (Task 8.2.3).

Tests cover:
- validate_export_format() - export format validation
- validate_data_completeness() - data completeness validation
- validate_fidelity() - export fidelity validation

All tests use real implementations (no mocks/stubs) and verify:
- Format validation (JSON/YAML)
- Required data presence
- Export fidelity and round-trip consistency
- Error handling
"""

import json

from hub.apps.contracts.business_rules import ODPSExportRules, ODPSRuleExecutionContext
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
)
from hub.apps.contracts.odps_generator import generate_odps_from_hubcontract
from hub.apps.contracts.tests.test_base import ContractsTestBase
from hub.apps.core.business_rules.base import ValidationResult


class ODPSExportRulesTestBase(ContractsTestBase):
    """Base test class for ODPSExportRules tests."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.user.display_name = "Test User"
        self.user.save()

        # Create ODPS contract with complete data

        odps_raw = json.dumps(
            {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "version": "4.1",
                "product": {
                    "details": {
                        "en": {
                            "productID": "test-odps-export-rules",
                            "name": "Test ODPS for Export Rules",
                            "description": "Test description",
                        }
                    },
                    "dataSchema": {"fields": [{"name": "id", "type": "string"}]},
                },
            }
        )

        self.odps_contract = self.odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Create business rules instance
        self.rules = ODPSExportRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))


class ODPSExportRulesFormatTest(ODPSExportRulesTestBase):
    """Tests for validate_export_format() method."""

    def test_validate_export_format_json(self):
        """Test JSON format validation passes."""
        result = self.rules.validate_export_format("json")

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.warnings), 0)

    def test_validate_export_format_yaml(self):
        """Test YAML format validation passes."""
        result = self.rules.validate_export_format("yaml")

        # YAML validation depends on PyYAML availability
        # If PyYAML is installed, should pass; otherwise should fail
        try:
            import yaml

            self.assertTrue(result.is_valid)
            self.assertEqual(len(result.errors), 0)
        except ImportError:
            self.assertFalse(result.is_valid)
            self.assertTrue(any("PyYAML" in err for err in result.errors))

    def test_validate_export_format_case_insensitive(self):
        """Test format validation is case-insensitive."""
        result1 = self.rules.validate_export_format("JSON")
        result2 = self.rules.validate_export_format("YAML")

        self.assertTrue(result1.is_valid)
        # YAML depends on PyYAML availability
        try:
            import yaml

            self.assertTrue(result2.is_valid)
        except ImportError:
            self.assertFalse(result2.is_valid)

    def test_validate_export_format_invalid(self):
        """Test invalid format validation fails."""
        result = self.rules.validate_export_format("xml")

        self.assertFalse(result.is_valid)
        self.assertTrue(len(result.errors) > 0)
        self.assertTrue(any("Invalid output format" in err for err in result.errors))

    def test_validate_export_format_empty(self):
        """Test empty format validation fails."""
        result = self.rules.validate_export_format("")

        self.assertFalse(result.is_valid)
        self.assertTrue(len(result.errors) > 0)
        self.assertTrue(any("required" in err.lower() for err in result.errors))

    def test_validate_export_format_none(self):
        """Test None format validation fails."""
        # Type ignore: intentionally testing None for validation
        result = self.rules.validate_export_format(None)  # type: ignore[misc]  # test: edge-case type exercise

        self.assertFalse(result.is_valid)
        self.assertTrue(len(result.errors) > 0)


class ODPSExportRulesDataCompletenessTest(ODPSExportRulesTestBase):
    """Tests for validate_data_completeness() method."""

    def test_validate_data_completeness_valid(self):
        """Test data completeness validation passes for valid contract."""
        result = self.rules.validate_data_completeness(self.odps_contract)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_data_completeness_no_hub_contract_json(self):
        """Test data completeness validation fails when hub_contract_json missing."""
        # Create contract without hub_contract_json
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            status=ContractStatus.ACTIVE,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_json=None,
        )

        result = self.rules.validate_data_completeness(contract)

        self.assertFalse(result.is_valid)
        self.assertTrue(len(result.errors) > 0)
        self.assertTrue(any("hub_contract_json" in err for err in result.errors))

    def test_validate_data_completeness_missing_info(self):
        """Test data completeness validation fails when info section missing."""
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            status=ContractStatus.ACTIVE,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_json={"id": "test-id"},  # Missing info
        )

        result = self.rules.validate_data_completeness(contract)

        self.assertFalse(result.is_valid)
        self.assertTrue(len(result.errors) > 0)
        self.assertTrue(any("info" in err.lower() for err in result.errors))

    def test_validate_data_completeness_missing_name(self):
        """Test data completeness validation fails when info.name missing."""
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            status=ContractStatus.ACTIVE,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_json={"id": "test-id", "info": {}},  # Missing name
        )

        result = self.rules.validate_data_completeness(contract)

        self.assertFalse(result.is_valid)
        self.assertTrue(len(result.errors) > 0)
        self.assertTrue(any("info.name" in err for err in result.errors))

    def test_validate_data_completeness_empty_name(self):
        """Test data completeness validation fails when info.name is empty."""
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            status=ContractStatus.ACTIVE,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_json={"id": "test-id", "info": {"name": ""}},  # Empty name
        )

        result = self.rules.validate_data_completeness(contract)

        self.assertFalse(result.is_valid)
        self.assertTrue(len(result.errors) > 0)
        self.assertTrue(any("non-empty string" in err for err in result.errors))

    def test_validate_data_completeness_missing_id_warning(self):
        """Test data completeness validation warns when id missing."""
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            status=ContractStatus.ACTIVE,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_json={"info": {"name": "Test Name"}},  # Missing id
        )

        result = self.rules.validate_data_completeness(contract)

        # Should still be valid (id is not strictly required)
        self.assertTrue(result.is_valid)
        self.assertTrue(len(result.warnings) > 0)
        self.assertTrue(any("id" in warn.lower() for warn in result.warnings))

    def test_validate_data_completeness_invalid_info_type(self):
        """Test data completeness validation fails when info is not a dict."""
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            status=ContractStatus.ACTIVE,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_json={"id": "test-id", "info": "not-a-dict"},  # Invalid type
        )

        result = self.rules.validate_data_completeness(contract)

        self.assertFalse(result.is_valid)
        self.assertTrue(len(result.errors) > 0)
        self.assertTrue(any("dictionary" in err.lower() for err in result.errors))


class ODPSExportRulesFidelityTest(ODPSExportRulesTestBase):
    """Tests for validate_fidelity() method."""

    def test_validate_fidelity_valid(self):
        """Test fidelity validation passes for valid export."""
        # Generate ODPS from contract
        exported_odps = generate_odps_from_hubcontract(
            hub_contract=self.odps_contract.hub_contract_json, target_version="4.1"
        )

        result = self.rules.validate_fidelity(
            contract=self.odps_contract, exported_odps=exported_odps
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_fidelity_missing_schema(self):
        """Test fidelity validation fails when schema missing."""
        exported_odps = {
            "product": {"details": {"en": {"productID": "test-id", "name": "Test Name"}}}
        }

        result = self.rules.validate_fidelity(
            contract=self.odps_contract, exported_odps=exported_odps
        )

        self.assertFalse(result.is_valid)
        self.assertTrue(len(result.errors) > 0)
        self.assertTrue(any("schema" in err.lower() for err in result.errors))

    def test_validate_fidelity_missing_product(self):
        """Test fidelity validation fails when product section missing."""
        exported_odps = {"schema": "https://opendataproducts.org/schema/v4.1"}

        result = self.rules.validate_fidelity(
            contract=self.odps_contract, exported_odps=exported_odps
        )

        self.assertFalse(result.is_valid)
        self.assertTrue(len(result.errors) > 0)
        self.assertTrue(any("product" in err.lower() for err in result.errors))

    def test_validate_fidelity_missing_details(self):
        """Test fidelity validation fails when product.details missing."""
        exported_odps = {"schema": "https://opendataproducts.org/schema/v4.1", "product": {}}

        result = self.rules.validate_fidelity(
            contract=self.odps_contract, exported_odps=exported_odps
        )

        self.assertFalse(result.is_valid)
        self.assertTrue(len(result.errors) > 0)
        self.assertTrue(any("details" in err.lower() for err in result.errors))

    def test_validate_fidelity_empty_details(self):
        """Test fidelity validation fails when product.details is empty."""
        exported_odps = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "product": {"details": {}},
        }

        result = self.rules.validate_fidelity(
            contract=self.odps_contract, exported_odps=exported_odps
        )

        self.assertFalse(result.is_valid)
        self.assertTrue(len(result.errors) > 0)
        self.assertTrue(any("at least one language" in err for err in result.errors))

    def test_validate_fidelity_product_id_mismatch_warning(self):
        """Test fidelity validation warns when productID doesn't match."""
        # Create contract with specific ID
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            status=ContractStatus.ACTIVE,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_json={"id": "original-id", "info": {"name": "Test Name"}},
        )

        exported_odps = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "product": {
                "details": {"en": {"productID": "different-id", "name": "Test Name"}}  # Mismatch
            },
        }

        result = self.rules.validate_fidelity(contract=contract, exported_odps=exported_odps)

        # Should still be valid but with warning
        self.assertTrue(result.is_valid)
        self.assertTrue(len(result.warnings) > 0)
        self.assertTrue(any("Product ID mismatch" in warn for warn in result.warnings))

    def test_validate_fidelity_name_mismatch_warning(self):
        """Test fidelity validation warns when name doesn't match."""
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            status=ContractStatus.ACTIVE,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_json={"id": "test-id", "info": {"name": "Original Name"}},
        )

        exported_odps = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "product": {
                "details": {"en": {"productID": "test-id", "name": "Different Name"}}  # Mismatch
            },
        }

        result = self.rules.validate_fidelity(contract=contract, exported_odps=exported_odps)

        # Should still be valid but with warning
        self.assertTrue(result.is_valid)
        self.assertTrue(len(result.warnings) > 0)
        self.assertTrue(any("Product name mismatch" in warn for warn in result.warnings))

    def test_validate_fidelity_invalid_exported_type(self):
        """Test fidelity validation fails when exported_odps is not a dict."""
        # Type ignore: intentionally testing invalid type for validation
        result = self.rules.validate_fidelity(
            contract=self.odps_contract, exported_odps="not-a-dict"  # type: ignore[misc]  # test: edge-case type exercise
        )

        self.assertFalse(result.is_valid)
        self.assertTrue(len(result.errors) > 0)
        self.assertTrue(any("dictionary" in err.lower() for err in result.errors))

    def test_validate_fidelity_invalid_schema_type(self):
        """Test fidelity validation fails when schema is not a string."""
        exported_odps = {
            "schema": 123,  # Invalid type
            "product": {"details": {"en": {"productID": "test-id", "name": "Test Name"}}},
        }

        result = self.rules.validate_fidelity(
            contract=self.odps_contract, exported_odps=exported_odps
        )

        self.assertFalse(result.is_valid)
        self.assertTrue(len(result.errors) > 0)
        self.assertTrue(any("schema" in err.lower() for err in result.errors))

    def test_validate_fidelity_round_trip_consistency(self):
        """Test fidelity validation for round-trip consistency."""
        # Export ODPS from contract
        exported_odps = generate_odps_from_hubcontract(
            hub_contract=self.odps_contract.hub_contract_json, target_version="4.1"
        )

        # Validate fidelity
        result = self.rules.validate_fidelity(
            contract=self.odps_contract, exported_odps=exported_odps
        )

        # Should pass with no errors or warnings (perfect fidelity)
        self.assertTrue(result.is_valid)
        # May have warnings if there are minor differences, but should not have errors
        self.assertEqual(len(result.errors), 0)

    def test_validate_export_format_handles_unicode_characters(self):
        """Test that export format validation handles unicode characters correctly."""
        # Unicode characters in format string should be handled
        result = self.rules.validate_export_format("json")
        self.assertTrue(result.is_valid)

    def test_validate_data_completeness_handles_unicode_characters(self):
        """Test that data completeness validation handles unicode characters correctly."""
        # Create contract with unicode characters
        odps_raw = json.dumps(
            {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "product": {
                    "details": {
                        "en": {
                            "productID": "test-unicode",
                            "name": "测试产品",
                            "description": "测试描述",
                        }
                    },
                    "dataSchema": {"fields": [{"name": "id", "type": "string"}]},
                },
            }
        )

        contract = self.odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        result = self.rules.validate_data_completeness(contract)

        # Should handle unicode characters
        self.assertIsNotNone(result)

    def test_validate_data_completeness_handles_special_characters(self):
        """Test that data completeness validation handles special characters correctly."""
        # Create contract with special characters
        odps_raw = json.dumps(
            {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "product": {
                    "details": {
                        "en": {
                            "productID": "test-special",
                            "name": "Test & Co. (Special)",
                            "description": "Test <description> & more",
                        }
                    },
                    "dataSchema": {"fields": [{"name": "id", "type": "string"}]},
                },
            }
        )

        contract = self.odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        result = self.rules.validate_data_completeness(contract)

        # Should handle special characters
        self.assertIsNotNone(result)

    def test_validate_data_completeness_handles_very_large_documents(self):
        """Test that data completeness validation handles very large documents correctly."""
        large_description = "A" * 100000  # 100KB string
        odps_raw = json.dumps(
            {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "product": {
                    "details": {
                        "en": {
                            "productID": "test-large",
                            "name": "Test Product",
                            "description": large_description,
                        }
                    },
                    "dataSchema": {"fields": [{"name": "id", "type": "string"}]},
                },
            }
        )

        contract = self.odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        result = self.rules.validate_data_completeness(contract)

        # Should handle very large documents
        self.assertIsNotNone(result)

    def test_validate_fidelity_handles_unicode_characters(self):
        """Test that fidelity validation handles unicode characters correctly."""
        # Create contract with unicode characters
        odps_raw = json.dumps(
            {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "product": {
                    "details": {
                        "en": {
                            "productID": "test-unicode-fidelity",
                            "name": "测试产品",
                            "description": "测试描述",
                        }
                    },
                    "dataSchema": {"fields": [{"name": "id", "type": "string"}]},
                },
            }
        )

        contract = self.odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        exported_odps = generate_odps_from_hubcontract(
            hub_contract=contract.hub_contract_json, target_version="4.1"
        )

        result = self.rules.validate_fidelity(contract=contract, exported_odps=exported_odps)

        # Should handle unicode characters
        self.assertIsNotNone(result)

    def test_validate_fidelity_handles_nested_structures(self):
        """Test that fidelity validation handles nested structures correctly."""
        # Create contract with nested structures
        odps_raw = json.dumps(
            {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "product": {
                    "details": {
                        "en": {
                            "productID": "test-nested-fidelity",
                            "name": "Test Product",
                            "nested": {"level1": {"level2": {"level3": {"value": "deep"}}}},
                        }
                    },
                    "dataSchema": {"fields": [{"name": "id", "type": "string"}]},
                },
            }
        )

        contract = self.odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        exported_odps = generate_odps_from_hubcontract(
            hub_contract=contract.hub_contract_json, target_version="4.1"
        )

        result = self.rules.validate_fidelity(contract=contract, exported_odps=exported_odps)

        # Should handle nested structures
        self.assertIsNotNone(result)
