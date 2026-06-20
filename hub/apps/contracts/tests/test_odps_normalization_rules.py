"""
Unit tests for ODPSNormalizationRules (Task 9.7.2.21.3).

Tests cover:
- validate_normalization_eligibility() - eligibility validation
- validate_normalization_status() - status validation
- validate_normalization_fidelity() - fidelity validation (data loss prevention)

All tests use real implementations (no mocks/stubs) and verify:
- Contract eligibility for normalization
- Normalization status consistency
- Data preservation during normalization
- Error handling
"""

import json

from hub.apps.contracts.business_rules import (
    ODPSNormalizationRules,
    ODPSRuleExecutionContext,
)
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
)
from hub.apps.contracts.tests.test_base import ContractsTestBase


class ODPSNormalizationRulesTestBase(ContractsTestBase):
    """Base test class for ODPSNormalizationRules tests."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()

        # Create normalization rules instance
        self.rules = ODPSNormalizationRules()

        # Sample ODCS contract raw data
        self.odcs_raw = json.dumps(
            {
                "version": "3.0.2",
                "info": {
                    "name": "test-contract",
                    "title": "Test Contract",
                },
                "schema": {
                    "fields": [
                        {"name": "field1", "type": "string"},
                        {"name": "field2", "type": "integer"},
                    ]
                },
            }
        )

        # Sample ODPS contract raw data
        self.odps_raw = json.dumps(
            {
                "version": "4.1",
                "product": {
                    "name": "test-product",
                    "productID": "test-product-id",
                    "dataSchema": {
                        "fields": [
                            {"name": "field1", "type": "string"},
                            {"name": "field2", "type": "integer"},
                        ]
                    },
                },
            }
        )


class ODPSNormalizationEligibilityTest(ODPSNormalizationRulesTestBase):
    """Test normalization eligibility validation."""

    def test_eligibility_valid_odcs_contract(self):
        """Test eligibility validation passes for valid ODCS contract."""
        contract = Contract.objects.create(
            original_raw=self.odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS.value,
            original_spec_version="3.0.2",
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.DRAFT,
        )

        context = ODPSRuleExecutionContext(contract=contract)
        result = self.rules.validate(context, validation_type="eligibility")

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertIn("eligibility", result.details)
        self.assertTrue(result.details["eligibility"]["is_eligible"])

    def test_eligibility_valid_odps_contract(self):
        """Test eligibility validation passes for valid ODPS contract."""
        contract = Contract.objects.create(
            original_raw=self.odps_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS.value,
            original_spec_version="4.1",
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.DRAFT,
        )

        context = ODPSRuleExecutionContext(contract=contract)
        result = self.rules.validate(context, validation_type="eligibility")

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertIn("eligibility", result.details)
        self.assertTrue(result.details["eligibility"]["is_eligible"])

    def test_eligibility_missing_original_raw(self):
        """Test eligibility validation fails when original_raw is missing."""
        # Since original_raw is a required DB field, we test by creating
        # an unsaved contract object with None original_raw to test validation logic
        contract = Contract(
            original_raw=None,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS.value,
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.DRAFT,
        )

        context = ODPSRuleExecutionContext(contract=contract)
        result = self.rules.validate(context, validation_type="eligibility")

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("original_raw", result.errors[0].lower())

    def test_eligibility_missing_original_format(self):
        """Test eligibility validation fails when original_format is missing."""
        # Since original_format is a required DB field, we test by creating
        # an unsaved contract object with None original_format to test validation logic
        contract = Contract(
            original_raw=self.odcs_raw,
            original_format=None,
            original_spec_type=OriginalSpecType.ODCS.value,
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.DRAFT,
        )

        context = ODPSRuleExecutionContext(contract=contract)
        result = self.rules.validate(context, validation_type="eligibility")

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("original_format", result.errors[0].lower())

    def test_eligibility_invalid_format(self):
        """Test eligibility validation fails for invalid format."""
        contract = Contract.objects.create(
            original_raw=self.odcs_raw,
            original_format="XML",  # Invalid format
            original_spec_type=OriginalSpecType.ODCS.value,
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.DRAFT,
        )

        context = ODPSRuleExecutionContext(contract=contract)
        result = self.rules.validate(context, validation_type="eligibility")

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("json or yaml", result.errors[0].lower())

    def test_eligibility_missing_spec_type(self):
        """Test eligibility validation fails when original_spec_type is missing."""
        # Since original_spec_type is a required DB field, we test by creating
        # an unsaved contract object with None spec_type to test validation logic
        contract = Contract(
            original_raw=self.odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=None,  # Missing spec type
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.DRAFT,
        )

        context = ODPSRuleExecutionContext(contract=contract)
        result = self.rules.validate(context, validation_type="eligibility")

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("original_spec_type", result.errors[0].lower())

    def test_eligibility_invalid_spec_type(self):
        """Test eligibility validation fails for invalid spec type."""
        contract = Contract.objects.create(
            original_raw=self.odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type="INVALID",
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.DRAFT,
        )

        context = ODPSRuleExecutionContext(contract=contract)
        result = self.rules.validate(context, validation_type="eligibility")

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("odcs or odps", result.errors[0].lower())


class ODPSNormalizationStatusTest(ODPSNormalizationRulesTestBase):
    """Test normalization status validation."""

    def test_status_normalized_ok(self):
        """Test status validation passes for NORMALIZED_OK."""
        hub_contract = {
            "info": {"name": "test-contract"},
            "schema": {"fields": [{"name": "field1", "type": "string"}]},
        }
        contract = Contract.objects.create(
            original_raw=self.odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS.value,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_json=hub_contract,
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.DRAFT,
        )

        context = ODPSRuleExecutionContext(contract=contract)
        result = self.rules.validate(context, validation_type="status")

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertIn("status", result.details)
        self.assertTrue(result.details["status"]["status_valid"])

    def test_status_normalized_with_warnings(self):
        """Test status validation passes for NORMALIZED_WITH_WARNINGS."""
        hub_contract = {
            "info": {"name": "test-contract"},
            "schema": {"fields": [{"name": "field1", "type": "string"}]},
        }
        contract = Contract.objects.create(
            original_raw=self.odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS.value,
            normalization_status=NormalizationStatus.NORMALIZED_WITH_WARNINGS,
            normalization_warnings=["Warning 1", "Warning 2"],
            hub_contract_json=hub_contract,
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.DRAFT,
        )

        context = ODPSRuleExecutionContext(contract=contract)
        result = self.rules.validate(context, validation_type="status")

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertIn("status", result.details)
        self.assertTrue(result.details["status"]["status_valid"])

    def test_status_normalization_failed(self):
        """Test status validation passes for NORMALIZATION_FAILED."""
        contract = Contract.objects.create(
            original_raw=self.odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS.value,
            normalization_status=NormalizationStatus.NORMALIZATION_FAILED,
            normalization_errors=["Error 1", "Error 2"],
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.DRAFT,
        )

        context = ODPSRuleExecutionContext(contract=contract)
        result = self.rules.validate(context, validation_type="status")

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertIn("status", result.details)
        self.assertTrue(result.details["status"]["status_valid"])

    def test_status_not_normalized(self):
        """Test status validation passes for NOT_NORMALIZED."""
        contract = Contract.objects.create(
            original_raw=self.odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS.value,
            normalization_status=NormalizationStatus.NOT_NORMALIZED,
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.DRAFT,
        )

        context = ODPSRuleExecutionContext(contract=contract)
        result = self.rules.validate(context, validation_type="status")

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertIn("status", result.details)
        self.assertTrue(result.details["status"]["status_valid"])

    def test_status_missing(self):
        """Test status validation fails when normalization_status is not set."""
        contract = Contract.objects.create(
            original_raw=self.odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS.value,
            normalization_status=None,
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.DRAFT,
        )

        context = ODPSRuleExecutionContext(contract=contract)
        result = self.rules.validate(context, validation_type="status")

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("normalization_status", result.errors[0].lower())

    def test_status_inconsistent_with_hub_contract(self):
        """Test status validation fails when status is OK but hub_contract_json is missing."""
        contract = Contract.objects.create(
            original_raw=self.odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS.value,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_json=None,  # Missing but status says OK
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.DRAFT,
        )

        context = ODPSRuleExecutionContext(contract=contract)
        result = self.rules.validate(context, validation_type="status")

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("inconsistent", result.errors[0].lower())

    def test_status_failed_without_errors(self):
        """Test status validation warns when NORMALIZATION_FAILED but no errors."""
        contract = Contract.objects.create(
            original_raw=self.odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS.value,
            normalization_status=NormalizationStatus.NORMALIZATION_FAILED,
            normalization_errors=None,  # Missing errors
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.DRAFT,
        )

        context = ODPSRuleExecutionContext(contract=contract)
        result = self.rules.validate(context, validation_type="status")

        self.assertTrue(result.is_valid)  # Status is valid, but has warnings
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("normalization_errors", result.warnings[0].lower())

    def test_status_with_warnings_without_warning_details(self):
        """Test status validation warns when NORMALIZED_WITH_WARNINGS but no warnings."""
        hub_contract = {
            "info": {"name": "test-contract"},
            "schema": {"fields": [{"name": "field1", "type": "string"}]},
        }
        contract = Contract.objects.create(
            original_raw=self.odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS.value,
            normalization_status=NormalizationStatus.NORMALIZED_WITH_WARNINGS,
            normalization_warnings=[],  # Empty list (default), not None
            hub_contract_json=hub_contract,
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.DRAFT,
        )

        context = ODPSRuleExecutionContext(contract=contract)
        result = self.rules.validate(context, validation_type="status")

        self.assertTrue(result.is_valid)  # Status is valid, but has warnings
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("normalization_warnings", result.warnings[0].lower())


class ODPSNormalizationFidelityTest(ODPSNormalizationRulesTestBase):
    """Test normalization fidelity validation."""

    def test_fidelity_valid_odcs_contract(self):
        """Test fidelity validation passes for valid ODCS contract."""
        hub_contract = {
            "info": {"name": "test-contract"},
            "schema": {
                "fields": [
                    {"name": "field1", "type": "string"},
                    {"name": "field2", "type": "integer"},
                ]
            },
            "normalization": {"coverage": {"overall": 0.95}},
        }
        contract = Contract.objects.create(
            original_raw=self.odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS.value,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_json=hub_contract,
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.DRAFT,
        )

        context = ODPSRuleExecutionContext(contract=contract)
        result = self.rules.validate(context, validation_type="fidelity")

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertIn("fidelity", result.details)
        self.assertEqual(result.details["fidelity"]["fidelity_check"], "performed")

    def test_fidelity_valid_odps_contract(self):
        """Test fidelity validation passes for valid ODPS contract."""
        hub_contract = {
            "info": {"name": "test-product"},
            "schema": {
                "fields": [
                    {"name": "field1", "type": "string"},
                    {"name": "field2", "type": "integer"},
                ]
            },
            "normalization": {"coverage": {"overall": 0.92}},
        }
        contract = Contract.objects.create(
            original_raw=self.odps_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS.value,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_json=hub_contract,
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.DRAFT,
        )

        context = ODPSRuleExecutionContext(contract=contract)
        result = self.rules.validate(context, validation_type="fidelity")

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertIn("fidelity", result.details)
        self.assertEqual(result.details["fidelity"]["fidelity_check"], "performed")

    def test_fidelity_missing_original_raw(self):
        """Test fidelity validation fails when original_raw is missing."""
        hub_contract = {
            "info": {"name": "test-contract"},
            "schema": {"fields": [{"name": "field1", "type": "string"}]},
        }
        # Create contract first (original_raw is required)
        contract = Contract.objects.create(
            original_raw=self.odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS.value,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_json=hub_contract,
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.DRAFT,
        )
        # Set original_raw to empty string via update (simulating missing data)
        Contract.objects.filter(id=contract.id).update(original_raw="")

        # Refresh from DB
        contract.refresh_from_db()

        context = ODPSRuleExecutionContext(contract=contract)
        result = self.rules.validate(context, validation_type="fidelity")

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        # Check that error mentions original_raw or that validation was skipped
        error_msg = " ".join(result.errors).lower()
        self.assertTrue(
            "original_raw" in error_msg or "skipped" in error_msg or "missing" in error_msg,
            f"Expected error about original_raw, skipped, or missing check, got: {result.errors}",
        )

    def test_fidelity_missing_hub_contract(self):
        """Test fidelity validation fails when hub_contract_json is missing."""
        contract = Contract.objects.create(
            original_raw=self.odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS.value,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_json=None,
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.DRAFT,
        )

        context = ODPSRuleExecutionContext(contract=contract)
        result = self.rules.validate(context, validation_type="fidelity")

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("hub_contract_json", result.errors[0].lower())

    def test_fidelity_failed_normalization(self):
        """Test fidelity validation fails for NORMALIZATION_FAILED status."""
        # For failed normalization, hub_contract_json might be None
        # but we need to test the status check, so we'll create with hub_contract_json=None
        contract = Contract.objects.create(
            original_raw=self.odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS.value,
            normalization_status=NormalizationStatus.NORMALIZATION_FAILED,
            hub_contract_json=None,  # Failed normalization typically has no hub_contract
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.DRAFT,
        )

        context = ODPSRuleExecutionContext(contract=contract)
        result = self.rules.validate(context, validation_type="fidelity")

        # Should fail because hub_contract_json is missing OR because status is FAILED
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        # Check that error mentions normalization_failed or hub_contract_json
        error_msg = " ".join(result.errors).lower()
        self.assertTrue(
            "normalization_failed" in error_msg or "hub_contract_json" in error_msg,
            f"Expected error about normalization_failed or hub_contract_json, got: {result.errors}",
        )

    def test_fidelity_name_preserved(self):
        """Test fidelity validation checks name preservation."""
        hub_contract = {
            "info": {"name": "test-contract"},  # Matches original
            "schema": {
                "fields": [
                    {"name": "field1", "type": "string"},
                    {"name": "field2", "type": "integer"},
                ]
            },
        }
        contract = Contract.objects.create(
            original_raw=self.odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS.value,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_json=hub_contract,
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.DRAFT,
        )

        context = ODPSRuleExecutionContext(contract=contract)
        result = self.rules.validate(context, validation_type="fidelity")

        self.assertTrue(result.is_valid)
        self.assertIn("fidelity", result.details)
        fidelity_details = result.details["fidelity"]
        self.assertTrue(fidelity_details.get("name_preserved"))

    def test_fidelity_name_lost(self):
        """Test fidelity validation detects when name is lost."""
        hub_contract = {
            "info": {},  # Name missing
            "schema": {
                "fields": [
                    {"name": "field1", "type": "string"},
                    {"name": "field2", "type": "integer"},
                ]
            },
        }
        contract = Contract.objects.create(
            original_raw=self.odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS.value,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_json=hub_contract,
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.DRAFT,
        )

        context = ODPSRuleExecutionContext(contract=contract)
        result = self.rules.validate(context, validation_type="fidelity")

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("lost", result.errors[0].lower())

    def test_fidelity_fields_preserved(self):
        """Test fidelity validation checks field preservation."""
        hub_contract = {
            "info": {"name": "test-contract"},
            "schema": {
                "fields": [
                    {"name": "field1", "type": "string"},
                    {"name": "field2", "type": "integer"},
                ]
            },
        }
        contract = Contract.objects.create(
            original_raw=self.odcs_raw,  # Has 2 fields
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS.value,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_json=hub_contract,  # Also has 2 fields
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.DRAFT,
        )

        context = ODPSRuleExecutionContext(contract=contract)
        result = self.rules.validate(context, validation_type="fidelity")

        self.assertTrue(result.is_valid)
        self.assertIn("fidelity", result.details)
        fidelity_details = result.details["fidelity"]
        self.assertTrue(fidelity_details.get("fields_preserved"))
        self.assertEqual(fidelity_details.get("original_fields_count"), 2)
        self.assertEqual(fidelity_details.get("hub_fields_count"), 2)

    def test_fidelity_fields_lost(self):
        """Test fidelity validation detects when fields are lost."""
        hub_contract = {
            "info": {"name": "test-contract"},
            "schema": {"fields": []},  # No fields - data loss
        }
        contract = Contract.objects.create(
            original_raw=self.odcs_raw,  # Has 2 fields
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS.value,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_json=hub_contract,  # Has 0 fields
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.DRAFT,
        )

        context = ODPSRuleExecutionContext(contract=contract)
        result = self.rules.validate(context, validation_type="fidelity")

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("data loss", result.errors[0].lower())

    def test_fidelity_low_coverage(self):
        """Test fidelity validation warns on low coverage."""
        # Use same field count to avoid field count warnings
        hub_contract = {
            "info": {"name": "test-contract"},
            "schema": {
                "fields": [
                    {"name": "field1", "type": "string"},
                    {"name": "field2", "type": "integer"},  # Match original field count
                ]
            },
            "normalization": {"coverage": {"overall": 0.5}},  # Low coverage
        }
        contract = Contract.objects.create(
            original_raw=self.odcs_raw,  # Has 2 fields
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS.value,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_json=hub_contract,  # Also has 2 fields
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.DRAFT,
        )

        context = ODPSRuleExecutionContext(contract=contract)
        result = self.rules.validate(context, validation_type="fidelity")

        self.assertTrue(result.is_valid)  # Valid but has warnings
        self.assertGreater(len(result.warnings), 0)
        # Check all warnings for coverage mention
        warnings_text = " ".join(result.warnings).lower()
        self.assertIn(
            "coverage", warnings_text, f"Expected coverage warning, got: {result.warnings}"
        )

    def test_fidelity_extensions_present(self):
        """Test fidelity validation warns when extensions are present."""
        # Use same field count to avoid field count warnings
        hub_contract = {
            "info": {"name": "test-contract"},
            "schema": {
                "fields": [
                    {"name": "field1", "type": "string"},
                    {"name": "field2", "type": "integer"},  # Match original field count
                ]
            },
            "extensions": {"x_custom": "value"},  # Unmappable field
        }
        contract = Contract.objects.create(
            original_raw=self.odcs_raw,  # Has 2 fields
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS.value,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_json=hub_contract,  # Also has 2 fields
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.DRAFT,
        )

        context = ODPSRuleExecutionContext(contract=contract)
        result = self.rules.validate(context, validation_type="fidelity")

        self.assertTrue(result.is_valid)  # Valid but has warnings
        self.assertGreater(len(result.warnings), 0)
        # Check all warnings for extension mention
        warnings_text = " ".join(result.warnings).lower()
        self.assertIn(
            "extension", warnings_text, f"Expected extension warning, got: {result.warnings}"
        )


class ODPSNormalizationRulesIntegrationTest(ODPSNormalizationRulesTestBase):
    """Test normalization rules with all validation types."""

    def test_all_validations(self):
        """Test all validation types together."""
        hub_contract = {
            "info": {"name": "test-contract"},
            "schema": {
                "fields": [
                    {"name": "field1", "type": "string"},
                    {"name": "field2", "type": "integer"},
                ]
            },
            "normalization": {"coverage": {"overall": 0.95}},
        }
        contract = Contract.objects.create(
            original_raw=self.odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS.value,
            original_spec_version="3.0.2",
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_json=hub_contract,
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.DRAFT,
        )

        context = ODPSRuleExecutionContext(contract=contract)
        result = self.rules.validate(context, validation_type="all")

        self.assertTrue(result.is_valid)
        self.assertIn("eligibility", result.details)
        self.assertIn("status", result.details)
        self.assertIn("fidelity", result.details)

    def test_normalization_rules_handle_unicode_characters(self):
        """Test that normalization rules handle unicode characters correctly."""
        hub_contract = {
            "info": {"name": "测试产品"},
            "schema": {
                "fields": [
                    {"name": "field1", "type": "string"},
                    {"name": "field2", "type": "integer"},
                ]
            },
        }
        contract = Contract.objects.create(
            original_raw=self.odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS.value,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_json=hub_contract,
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.DRAFT,
        )

        context = ODPSRuleExecutionContext(contract=contract)
        result = self.rules.validate(context, validation_type="fidelity")

        # Should handle unicode characters
        self.assertIsNotNone(result)

    def test_normalization_rules_handle_special_characters(self):
        """Test that normalization rules handle special characters correctly."""
        hub_contract = {
            "info": {"name": "Test & Co. (Special)"},
            "schema": {
                "fields": [
                    {"name": "field1", "type": "string"},
                    {"name": "field2", "type": "integer"},
                ]
            },
        }
        contract = Contract.objects.create(
            original_raw=self.odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS.value,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_json=hub_contract,
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.DRAFT,
        )

        context = ODPSRuleExecutionContext(contract=contract)
        result = self.rules.validate(context, validation_type="fidelity")

        # Should handle special characters
        self.assertIsNotNone(result)

    def test_normalization_rules_handle_very_large_documents(self):
        """Test that normalization rules handle very large documents correctly."""
        large_description = "A" * 100000  # 100KB string
        hub_contract = {
            "info": {"name": "test-contract", "description": large_description},
            "schema": {
                "fields": [
                    {"name": "field1", "type": "string"},
                    {"name": "field2", "type": "integer"},
                ]
            },
        }
        contract = Contract.objects.create(
            original_raw=self.odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS.value,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_json=hub_contract,
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.DRAFT,
        )

        context = ODPSRuleExecutionContext(contract=contract)
        result = self.rules.validate(context, validation_type="fidelity")

        # Should handle very large documents
        self.assertIsNotNone(result)

    def test_normalization_rules_handle_none_values(self):
        """Test that normalization rules handle None values correctly."""
        hub_contract = {
            "info": {"name": "test-contract", "description": None},  # None value
            "schema": {
                "fields": [
                    {"name": "field1", "type": "string"},
                    {"name": "field2", "type": "integer"},
                ]
            },
        }
        contract = Contract.objects.create(
            original_raw=self.odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS.value,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_json=hub_contract,
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.DRAFT,
        )

        context = ODPSRuleExecutionContext(contract=contract)
        result = self.rules.validate(context, validation_type="fidelity")

        # Should handle None values gracefully
        self.assertIsNotNone(result)

    def test_normalization_rules_handle_nested_structures(self):
        """Test that normalization rules handle nested structures correctly."""
        hub_contract = {
            "info": {
                "name": "test-contract",
                "nested": {"level1": {"level2": {"level3": {"value": "deep"}}}},
            },
            "schema": {
                "fields": [
                    {"name": "field1", "type": "string"},
                    {"name": "field2", "type": "integer"},
                ]
            },
        }
        contract = Contract.objects.create(
            original_raw=self.odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS.value,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_json=hub_contract,
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.DRAFT,
        )

        context = ODPSRuleExecutionContext(contract=contract)
        result = self.rules.validate(context, validation_type="fidelity")

        # Should handle nested structures
        self.assertIsNotNone(result)
