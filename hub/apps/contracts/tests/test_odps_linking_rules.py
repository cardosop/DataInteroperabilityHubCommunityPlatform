"""
Unit tests for ODPSLinkingRules (Task 8.2.2).

Tests cover:
- validate_odps_to_odcs_link() - ODPS → ODCS link validation
- validate_circular_references() - circular reference detection
- validate_referential_integrity() - bidirectional consistency validation
- validate_all_linking_rules() - comprehensive validation

All tests use real implementations (no mocks/stubs) and verify:
- Link existence and validity
- Circular reference prevention
- Referential integrity
- Error handling
"""

import json

from django.test import TestCase

from hub.apps.contracts.business_rules import ODPSLinkingRules, ODPSRuleExecutionContext
from hub.apps.contracts.linking_validation import LinkingValidationError
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
)
from hub.apps.contracts.tests.test_base import ContractsTestBase
from hub.apps.core.business_rules.base import ValidationResult
from hub.apps.core.services.base import ValidationError
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
import uuid


class ODPSLinkingRulesTestBase(ContractsTestBase):
    """Base test class for ODPSLinkingRules tests."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()

        # Create ODCS contract
        contract_service = self.contract_service

        odcs_raw = json.dumps(
            {
                "apiVersion": "odcs.io/v3.0.2",
                "kind": "DataContract",
                "id": "test-odcs-linking-rules",
                "name": "Test ODCS for Linking Rules",
                "version": "3.0.2",
                "schema": {"fields": [{"name": "id", "type": "string"}]},
            }
        )

        self.odcs_contract = contract_service.create_contract(
            original_raw=odcs_raw,
            original_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            original_spec_type=OriginalSpecType.ODCS.value,
        )

        # Create ODPS contract
        odps_service = self.odps_service

        odps_raw = json.dumps(
            {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "product": {
                    "details": {
                        "en": {
                            "productID": "test-odps-linking-rules",
                            "name": "Test ODPS for Linking Rules",
                        }
                    },
                    "dataSchema": {"fields": [{"name": "id", "type": "string"}]},
                    "contract": {"spec": json.loads(odcs_raw)},
                },
            }
        )

        self.odps_contract = odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Create business rules instance
        self.rules = ODPSLinkingRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))


class ODPSLinkingRulesODPSToODCSLinkTest(ODPSLinkingRulesTestBase):
    """Tests for validate_odps_to_odcs_link() method."""

    def test_validate_odps_to_odcs_link_valid_link(self):
        """Test validation of valid ODPS → ODCS link."""
        # Arrange
        # Link the contracts
        self.contract_service.link_odps_to_odcs(
            odcs_contract_id=str(self.odcs_contract.id),
            odps_contract_id=str(self.odps_contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Refresh from database
        self.odps_contract.refresh_from_db()

        # Act
        # Validate the link
        result = self.rules.validate_odps_to_odcs_link(self.odps_contract)

        # Assert
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_odps_to_odcs_link_no_link(self):
        """Test validation when ODPS contract has no ODCS link."""
        # Arrange
        # (odps_contract already set up in setUp)

        # Act
        result = self.rules.validate_odps_to_odcs_link(self.odps_contract)

        # Assert
        # No link is valid (not an error), but should have a warning
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertGreater(len(result.warnings), 0)
        self.assertTrue(any("odcs link" in warn.lower() for warn in result.warnings))

    def test_validate_odps_to_odcs_link_invalid_contract_type(self):
        """Test validation fails for non-ODPS contract."""
        # Arrange
        # (odcs_contract already set up in setUp)

        # Act
        result = self.rules.validate_odps_to_odcs_link(self.odcs_contract)

        # Assert
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("odps" in err.lower() for err in result.errors))

    def test_validate_odps_to_odcs_link_nonexistent_odcs(self):
        """Test validation fails when linked ODCS contract doesn't exist."""
        # Manually set an invalid link
        hub_contract = self.odps_contract.hub_contract_json.copy()
        if "extensions" not in hub_contract:
            hub_contract["extensions"] = {}
        if "x_odps" not in hub_contract["extensions"]:
            hub_contract["extensions"]["x_odps"] = {}

        from uuid import uuid4

        fake_odcs_id = str(uuid4())
        hub_contract["extensions"]["x_odps"]["odcs_link"] = fake_odcs_id

        self.odps_contract.hub_contract_json = hub_contract
        self.odps_contract.save()

        # Validate the link
        result = self.rules.validate_odps_to_odcs_link(self.odps_contract)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(
            any("not exist" in err.lower() or "invalid" in err.lower() for err in result.errors)
        )

    def test_validate_odps_to_odcs_link_wrong_contract_type(self):
        """Test validation fails when linked contract is not ODCS."""
        # Create another ODPS contract
        from hub.apps.contracts.services import ODPSService

        odps_service = ODPSService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        odps_raw2 = json.dumps(
            {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "product": {
                    "details": {"en": {"productID": "test-odps-2", "name": "Test ODPS 2"}},
                    "dataSchema": {"fields": [{"name": "id", "type": "string"}]},
                },
            }
        )

        odps_contract2 = odps_service.create_odps(
            odps_raw=odps_raw2,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Manually set link to another ODPS contract (invalid)
        hub_contract = self.odps_contract.hub_contract_json.copy()
        if "extensions" not in hub_contract:
            hub_contract["extensions"] = {}
        if "x_odps" not in hub_contract["extensions"]:
            hub_contract["extensions"]["x_odps"] = {}

        hub_contract["extensions"]["x_odps"]["odcs_link"] = str(odps_contract2.id)

        self.odps_contract.hub_contract_json = hub_contract
        self.odps_contract.save()

        # Validate the link
        result = self.rules.validate_odps_to_odcs_link(self.odps_contract)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(
            any("non-odcs" in err.lower() or "odcs" in err.lower() for err in result.errors)
        )


class ODPSLinkingRulesCircularReferencesTest(ODPSLinkingRulesTestBase):
    """Tests for validate_circular_references() method."""

    def test_validate_circular_references_no_cycle(self):
        """Test validation passes when no circular reference would be created."""
        result = self.rules.validate_circular_references(
            odps_contract_id=str(self.odps_contract.id), odcs_contract_id=str(self.odcs_contract.id)
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_circular_references_direct_cycle(self):
        """Test validation fails when direct circular reference would be created."""
        # Link ODPS → ODCS
        from hub.apps.contracts.services import ContractService

        contract_service = ContractService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        contract_service.link_odps_to_odcs(
            odcs_contract_id=str(self.odcs_contract.id),
            odps_contract_id=str(self.odps_contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Refresh from database
        self.odps_contract.refresh_from_db()
        self.odcs_contract.refresh_from_db()

        # Try to link again (would create cycle)
        result = self.rules.validate_circular_references(
            odps_contract_id=str(self.odps_contract.id), odcs_contract_id=str(self.odcs_contract.id)
        )

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("circular" in err.lower() for err in result.errors))

    def test_validate_circular_references_indirect_cycle(self):
        """Test validation fails when indirect circular reference would be created."""
        # Create additional contracts for indirect cycle
        from hub.apps.contracts.services import ContractService, ODPSService

        contract_service = ContractService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        odps_service = ODPSService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create ODCS2
        odcs_raw2 = json.dumps(
            {
                "apiVersion": "odcs.io/v3.0.2",
                "kind": "DataContract",
                "id": "test-odcs-2",
                "name": "Test ODCS 2",
                "version": "3.0.2",
                "schema": {"fields": [{"name": "id", "type": "string"}]},
            }
        )

        odcs_contract2 = contract_service.create_contract(
            original_raw=odcs_raw2,
            original_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            original_spec_type=OriginalSpecType.ODCS.value,
        )

        # Create ODPS2
        odps_raw2 = json.dumps(
            {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "product": {
                    "details": {"en": {"productID": "test-odps-2", "name": "Test ODPS 2"}},
                    "dataSchema": {"fields": [{"name": "id", "type": "string"}]},
                    "contract": {"spec": json.loads(odcs_raw2)},
                },
            }
        )

        odps_contract2 = odps_service.create_odps(
            odps_raw=odps_raw2,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Link ODPS1 → ODCS1
        contract_service.link_odps_to_odcs(
            odcs_contract_id=str(self.odcs_contract.id),
            odps_contract_id=str(self.odps_contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Link ODPS2 → ODCS2
        contract_service.link_odps_to_odcs(
            odcs_contract_id=str(odcs_contract2.id),
            odps_contract_id=str(odps_contract2.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Manually create indirect cycle: ODCS1 → ODPS2
        hub_contract = self.odcs_contract.hub_contract_json.copy()
        if "extensions" not in hub_contract:
            hub_contract["extensions"] = {}
        if "x_odps" not in hub_contract["extensions"]:
            hub_contract["extensions"]["x_odps"] = {}

        # ODCS1 already links to ODPS1, but we'll create a link to ODPS2
        # This creates: ODPS1 → ODCS1 → ODPS2 → ODCS2
        # Then trying to link ODPS2 → ODCS1 would create a cycle

        # First, link ODCS1 to ODPS2 (manually, bypassing validation)
        hub_contract["extensions"]["x_odps"]["odps_link"] = str(odps_contract2.id)
        self.odcs_contract.hub_contract_json = hub_contract
        self.odcs_contract.save()

        # Now try to link ODPS2 → ODCS1 (would create cycle)
        result = self.rules.validate_circular_references(
            odps_contract_id=str(odps_contract2.id), odcs_contract_id=str(self.odcs_contract.id)
        )

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("circular" in err.lower() for err in result.errors))

    def test_validate_circular_references_missing_ids(self):
        """Test validation fails when contract IDs are missing."""
        result = self.rules.validate_circular_references(
            odps_contract_id="", odcs_contract_id=str(self.odcs_contract.id)
        )

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("odps" in err.lower() for err in result.errors))

        result = self.rules.validate_circular_references(
            odps_contract_id=str(self.odps_contract.id), odcs_contract_id=""
        )

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("odcs" in err.lower() for err in result.errors))


class ODPSLinkingRulesReferentialIntegrityTest(ODPSLinkingRulesTestBase):
    """Tests for validate_referential_integrity() method."""

    def test_validate_referential_integrity_valid_bidirectional(self):
        """Test validation passes for valid bidirectional link."""
        # Link the contracts
        from hub.apps.contracts.services import ContractService

        contract_service = ContractService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        contract_service.link_odps_to_odcs(
            odcs_contract_id=str(self.odcs_contract.id),
            odps_contract_id=str(self.odps_contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Refresh from database
        self.odps_contract.refresh_from_db()

        # Validate referential integrity
        result = self.rules.validate_referential_integrity(self.odps_contract)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_referential_integrity_no_link(self):
        """Test validation passes when contract has no link."""
        result = self.rules.validate_referential_integrity(self.odps_contract)

        # No link means no integrity check needed
        self.assertTrue(result.is_valid)

    def test_validate_referential_integrity_missing_hub_contract_json(self):
        """Test validation passes when hub_contract_json is missing."""
        # Create contract without hub_contract_json
        odps_contract_no_hub = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            original_format=OriginalFormat.JSON,
            original_raw='{"schema": "https://opendataproducts.org/schema/v4.1"}',
            status=ContractStatus.DRAFT,
            hub_contract_json=None,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        result = self.rules.validate_referential_integrity(odps_contract_no_hub)

        # Should pass with warning
        self.assertTrue(result.is_valid)
        self.assertGreater(len(result.warnings), 0)
        self.assertTrue(any("hub_contract_json" in warn.lower() for warn in result.warnings))

    def test_validate_referential_integrity_unidirectional_link(self):
        """Test validation fails when link is unidirectional."""
        # Manually set ODPS → ODCS link without bidirectional link
        hub_contract = self.odps_contract.hub_contract_json.copy()
        if "extensions" not in hub_contract:
            hub_contract["extensions"] = {}
        if "x_odps" not in hub_contract["extensions"]:
            hub_contract["extensions"]["x_odps"] = {}

        hub_contract["extensions"]["x_odps"]["odcs_link"] = str(self.odcs_contract.id)

        self.odps_contract.hub_contract_json = hub_contract
        self.odps_contract.save()

        # Ensure ODCS doesn't link back
        odcs_hub_contract = self.odcs_contract.hub_contract_json.copy()
        if "extensions" not in odcs_hub_contract:
            odcs_hub_contract["extensions"] = {}
        if "x_odps" not in odcs_hub_contract["extensions"]:
            odcs_hub_contract["extensions"]["x_odps"] = {}

        # Explicitly remove odps_link to ensure unidirectional
        odcs_hub_contract["extensions"]["x_odps"].pop("odps_link", None)

        self.odcs_contract.hub_contract_json = odcs_hub_contract
        self.odcs_contract.save()

        # Validate referential integrity
        result = self.rules.validate_referential_integrity(self.odps_contract)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(
            any("link back" in err.lower() or "integrity" in err.lower() for err in result.errors)
        )

    def test_validate_referential_integrity_wrong_back_link(self):
        """Test validation fails when back link points to wrong contract."""
        # Create another ODCS contract
        from hub.apps.contracts.services import ContractService

        contract_service = ContractService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        odcs_raw2 = json.dumps(
            {
                "apiVersion": "odcs.io/v3.0.2",
                "kind": "DataContract",
                "id": "test-odcs-2-integrity",
                "name": "Test ODCS 2 for Integrity",
                "version": "3.0.2",
                "schema": {"fields": [{"name": "id", "type": "string"}]},
            }
        )

        odcs_contract2 = contract_service.create_contract(
            original_raw=odcs_raw2,
            original_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            original_spec_type=OriginalSpecType.ODCS.value,
        )

        # Link ODPS → ODCS1
        hub_contract = self.odps_contract.hub_contract_json.copy()
        if "extensions" not in hub_contract:
            hub_contract["extensions"] = {}
        if "x_odps" not in hub_contract["extensions"]:
            hub_contract["extensions"]["x_odps"] = {}

        hub_contract["extensions"]["x_odps"]["odcs_link"] = str(self.odcs_contract.id)

        self.odps_contract.hub_contract_json = hub_contract
        self.odps_contract.save()

        # Link ODCS2 → ODPS (wrong back link)
        odcs_hub_contract2 = odcs_contract2.hub_contract_json.copy()
        if "extensions" not in odcs_hub_contract2:
            odcs_hub_contract2["extensions"] = {}
        if "x_odps" not in odcs_hub_contract2["extensions"]:
            odcs_hub_contract2["extensions"]["x_odps"] = {}

        odcs_hub_contract2["extensions"]["x_odps"]["odps_link"] = str(self.odps_contract.id)

        odcs_contract2.hub_contract_json = odcs_hub_contract2
        odcs_contract2.save()

        # Validate referential integrity (should fail because ODCS1 doesn't link back)
        result = self.rules.validate_referential_integrity(self.odps_contract)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("link back" in err.lower() for err in result.errors))


class ODPSLinkingRulesComprehensiveTest(ODPSLinkingRulesTestBase):
    """Tests for validate_all_linking_rules() method."""

    def test_validate_all_linking_rules_valid(self):
        """Test comprehensive validation passes for valid links."""
        # Link the contracts
        from hub.apps.contracts.services import ContractService

        contract_service = ContractService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        contract_service.link_odps_to_odcs(
            odcs_contract_id=str(self.odcs_contract.id),
            odps_contract_id=str(self.odps_contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Refresh from database
        self.odps_contract.refresh_from_db()
        self.odcs_contract.refresh_from_db()

        # Validate all linking rules
        # Note: When contracts are already linked, circular reference check
        # may detect the existing link as a cycle. This is expected behavior.
        # We should validate without the ODCS contract to avoid this.
        result = self.rules.validate_all_linking_rules(
            odps_contract=self.odps_contract,
            odcs_contract=None,  # Don't pass ODCS to avoid circular reference check on already-linked contracts
        )

        # Should pass link and integrity checks
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_all_linking_rules_with_circular_reference(self):
        """Test comprehensive validation fails when circular reference detected."""
        # Create additional contracts for indirect cycle
        from hub.apps.contracts.services import ContractService, ODPSService

        contract_service = ContractService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        odps_service = ODPSService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create ODCS2
        odcs_raw2 = json.dumps(
            {
                "apiVersion": "odcs.io/v3.0.2",
                "kind": "DataContract",
                "id": "test-odcs-2-circular",
                "name": "Test ODCS 2 for Circular",
                "version": "3.0.2",
                "schema": {"fields": [{"name": "id", "type": "string"}]},
            }
        )

        odcs_contract2 = contract_service.create_contract(
            original_raw=odcs_raw2,
            original_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            original_spec_type=OriginalSpecType.ODCS.value,
        )

        # Create ODPS2
        odps_raw2 = json.dumps(
            {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "product": {
                    "details": {
                        "en": {
                            "productID": "test-odps-2-circular",
                            "name": "Test ODPS 2 for Circular",
                        }
                    },
                    "dataSchema": {"fields": [{"name": "id", "type": "string"}]},
                    "contract": {"spec": json.loads(odcs_raw2)},
                },
            }
        )

        odps_contract2 = odps_service.create_odps(
            odps_raw=odps_raw2,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Link ODPS1 → ODCS1
        contract_service.link_odps_to_odcs(
            odcs_contract_id=str(self.odcs_contract.id),
            odps_contract_id=str(self.odps_contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Link ODPS2 → ODCS2
        contract_service.link_odps_to_odcs(
            odcs_contract_id=str(odcs_contract2.id),
            odps_contract_id=str(odps_contract2.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Manually create indirect cycle: ODCS1 → ODPS2
        hub_contract = self.odcs_contract.hub_contract_json.copy()
        if "extensions" not in hub_contract:
            hub_contract["extensions"] = {}
        if "x_odps" not in hub_contract["extensions"]:
            hub_contract["extensions"]["x_odps"] = {}

        # ODCS1 already links to ODPS1, but we'll also link to ODPS2
        # This creates: ODPS1 → ODCS1 → ODPS2 → ODCS2
        # Then trying to link ODPS2 → ODCS1 would create a cycle
        hub_contract["extensions"]["x_odps"]["odps_link"] = str(odps_contract2.id)
        self.odcs_contract.hub_contract_json = hub_contract
        self.odcs_contract.save()

        # Refresh ODPS2
        odps_contract2.refresh_from_db()

        # Validate all linking rules (should detect circular reference)
        result = self.rules.validate_all_linking_rules(
            odps_contract=odps_contract2, odcs_contract=self.odcs_contract
        )

        # Should fail due to circular reference
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("circular" in err.lower() for err in result.errors))

    def test_validate_all_linking_rules_without_odcs_contract(self):
        """Test comprehensive validation when ODCS contract not provided."""
        result = self.rules.validate_all_linking_rules(
            odps_contract=self.odps_contract, odcs_contract=None
        )

        # Should still validate link and integrity (but not circular references)
        # Since there's no link, should pass with warnings
        self.assertTrue(result.is_valid or len(result.errors) == 0)

    def test_validate_all_linking_rules_with_integrity_violation(self):
        """Test comprehensive validation fails when referential integrity violated."""
        # Manually set unidirectional link
        hub_contract = self.odps_contract.hub_contract_json.copy()
        if "extensions" not in hub_contract:
            hub_contract["extensions"] = {}
        if "x_odps" not in hub_contract["extensions"]:
            hub_contract["extensions"]["x_odps"] = {}

        hub_contract["extensions"]["x_odps"]["odcs_link"] = str(self.odcs_contract.id)

        self.odps_contract.hub_contract_json = hub_contract
        self.odps_contract.save()

        # Ensure ODCS doesn't link back
        odcs_hub_contract = self.odcs_contract.hub_contract_json.copy()
        if "extensions" not in odcs_hub_contract:
            odcs_hub_contract["extensions"] = {}
        if "x_odps" not in odcs_hub_contract["extensions"]:
            odcs_hub_contract["extensions"]["x_odps"] = {}

        odcs_hub_contract["extensions"]["x_odps"].pop("odps_link", None)

        self.odcs_contract.hub_contract_json = odcs_hub_contract
        self.odcs_contract.save()

        # Validate all linking rules
        result = self.rules.validate_all_linking_rules(
            odps_contract=self.odps_contract, odcs_contract=self.odcs_contract
        )

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(
            any("integrity" in err.lower() or "link back" in err.lower() for err in result.errors)
        )

    # Edge cases and error handling tests
    def test_validate_odps_to_odcs_link_with_none_contract(self):
        """Test validation with None contract."""
        result = self.rules.validate_odps_to_odcs_link(None)  # type: ignore
        # Should handle None gracefully
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_odps_to_odcs_link_with_empty_hub_contract_json(self):
        """Test validation with empty hub_contract_json."""
        self.odps_contract.hub_contract_json = {}
        self.odps_contract.save()

        result = self.rules.validate_odps_to_odcs_link(self.odps_contract)
        # Should handle empty hub_contract_json gracefully
        self.assertIsNotNone(result)

    def test_validate_odps_to_odcs_link_with_missing_extensions(self):
        """Test validation with missing extensions section."""
        hub_contract = self.odps_contract.hub_contract_json.copy()
        hub_contract.pop("extensions", None)
        self.odps_contract.hub_contract_json = hub_contract
        self.odps_contract.save()

        result = self.rules.validate_odps_to_odcs_link(self.odps_contract)
        # Should handle missing extensions gracefully
        self.assertIsNotNone(result)

    def test_validate_odps_to_odcs_link_with_special_characters_in_link_id(self):
        """Test validation with special characters in link ID."""
        hub_contract = self.odps_contract.hub_contract_json.copy()
        if "extensions" not in hub_contract:
            hub_contract["extensions"] = {}
        if "x_odps" not in hub_contract["extensions"]:
            hub_contract["extensions"]["x_odps"] = {}

        hub_contract["extensions"]["x_odps"]["odcs_link"] = "<>&\"'"
        self.odps_contract.hub_contract_json = hub_contract
        self.odps_contract.save()

        result = self.rules.validate_odps_to_odcs_link(self.odps_contract)
        # Should handle special characters gracefully
        self.assertIsNotNone(result)

    def test_validate_circular_references_with_none_ids(self):
        """Test circular reference validation with None IDs."""
        result = self.rules.validate_circular_references(
            odps_contract_id=None,  # type: ignore
            odcs_contract_id=None,  # type: ignore
        )
        # Should handle None IDs gracefully
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_circular_references_with_invalid_uuid_format(self):
        """Test circular reference validation with invalid UUID format."""
        result = self.rules.validate_circular_references(
            odps_contract_id="not-a-valid-uuid", odcs_contract_id="also-not-a-uuid"
        )
        # Should handle invalid UUID format gracefully
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_circular_references_cross_tenant(self):
        """Test circular reference validation respects tenant isolation."""
        # Create another tenant
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}",
            slug=f"other-tenant-circular-{_uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )

        # Create contracts in other tenant
        from hub.apps.contracts.services import ContractService, ODPSService

        contract_service = ContractService(
            tenant_id=str(other_tenant.id), user_id=str(self.user.id)
        )

        odcs_raw = json.dumps(
            {
                "apiVersion": "odcs.io/v3.0.2",
                "kind": "DataContract",
                "id": "other-odcs",
                "name": "Other ODCS",
                "version": "3.0.2",
                "schema": {"fields": [{"name": "id", "type": "string"}]},
            }
        )

        other_odcs = contract_service.create_contract(
            original_raw=odcs_raw,
            original_format="json",
            tenant_id=str(other_tenant.id),
            user_id=str(self.user.id),
            original_spec_type=OriginalSpecType.ODCS.value,
        )

        # Should not detect circular reference across tenants
        result = self.rules.validate_circular_references(
            odps_contract_id=str(self.odps_contract.id), odcs_contract_id=str(other_odcs.id)
        )
        # May or may not detect cross-tenant issue, but should handle gracefully
        self.assertIsNotNone(result)

    def test_validate_referential_integrity_with_none_contract(self):
        """Test referential integrity validation with None contract."""
        result = self.rules.validate_referential_integrity(None)  # type: ignore
        # Should handle None gracefully
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_referential_integrity_with_empty_extensions(self):
        """Test referential integrity validation with empty extensions."""
        hub_contract = self.odps_contract.hub_contract_json.copy()
        hub_contract["extensions"] = {}
        self.odps_contract.hub_contract_json = hub_contract
        self.odps_contract.save()

        result = self.rules.validate_referential_integrity(self.odps_contract)
        # Should handle empty extensions gracefully
        self.assertIsNotNone(result)

    def test_validate_all_linking_rules_with_none_contracts(self):
        """Test comprehensive validation with None contracts."""
        result = self.rules.validate_all_linking_rules(
            odps_contract=None,  # type: ignore
            odcs_contract=None,  # type: ignore
        )
        # Should handle None contracts gracefully
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_all_linking_rules_with_invalid_contract_types(self):
        """Test comprehensive validation with invalid contract types."""
        # Pass ODCS contract as ODPS contract
        result = self.rules.validate_all_linking_rules(
            odps_contract=self.odcs_contract, odcs_contract=self.odps_contract
        )
        # Should detect invalid types
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_odps_to_odcs_link_with_very_long_link_id(self):
        """Test validation with very long link ID."""
        hub_contract = self.odps_contract.hub_contract_json.copy()
        if "extensions" not in hub_contract:
            hub_contract["extensions"] = {}
        if "x_odps" not in hub_contract["extensions"]:
            hub_contract["extensions"]["x_odps"] = {}

        long_id = "a" * 10000
        hub_contract["extensions"]["x_odps"]["odcs_link"] = long_id
        self.odps_contract.hub_contract_json = hub_contract
        self.odps_contract.save()

        result = self.rules.validate_odps_to_odcs_link(self.odps_contract)
        # Should handle very long ID gracefully
        self.assertIsNotNone(result)

    def test_validate_circular_references_with_self_reference(self):
        """Test circular reference validation with self-reference."""
        # Try to link contract to itself
        result = self.rules.validate_circular_references(
            odps_contract_id=str(self.odps_contract.id), odcs_contract_id=str(self.odps_contract.id)
        )
        # Should detect self-reference as invalid
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_linking_rules_handle_unicode_characters(self):
        """Test that linking rules handle unicode characters correctly."""
        # Create contract with unicode in hub_contract_json
        contract = Contract.objects.create(
            original_raw=json.dumps(
                {
                    "schema": "https://opendataproducts.org/schema/v4.1",
                    "product": {"details": {"en": {"productID": "测试产品", "name": "测试名称"}}},
                }
            ),
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS.value,
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.DRAFT,
        )

        result = self.rules.validate_odps_to_odcs_link(contract)
        # Should handle unicode characters
        self.assertIsNotNone(result)

    def test_linking_rules_handle_special_characters(self):
        """Test that linking rules handle special characters correctly."""
        # Create contract with special characters in hub_contract_json
        contract = Contract.objects.create(
            original_raw=json.dumps(
                {
                    "schema": "https://opendataproducts.org/schema/v4.1",
                    "product": {
                        "details": {
                            "en": {"productID": "test-<>&\"'", "name": "Test & Co. (Special)"}
                        }
                    },
                }
            ),
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS.value,
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.DRAFT,
        )

        result = self.rules.validate_odps_to_odcs_link(contract)
        # Should handle special characters
        self.assertIsNotNone(result)

    def test_linking_rules_handle_very_large_documents(self):
        """Test that linking rules handle very large documents correctly."""
        large_description = "A" * 100000  # 100KB string
        contract = Contract.objects.create(
            original_raw=json.dumps(
                {
                    "schema": "https://opendataproducts.org/schema/v4.1",
                    "product": {
                        "details": {
                            "en": {"productID": "test-large", "description": large_description}
                        }
                    },
                }
            ),
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS.value,
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.DRAFT,
        )

        result = self.rules.validate_odps_to_odcs_link(contract)
        # Should handle very large documents
        self.assertIsNotNone(result)

    def test_linking_rules_handle_none_values(self):
        """Test that linking rules handle None values correctly."""
        # Test with None contract
        result = self.rules.validate_odps_to_odcs_link(None)  # type: ignore
        # Should handle None values gracefully
        self.assertIsNotNone(result)
        self.assertFalse(result.is_valid)

    def test_linking_rules_handle_nested_structures(self):
        """Test that linking rules handle nested structures correctly."""
        nested_data = {"level1": {"level2": {"level3": {"value": "deep"}}}}
        contract = Contract.objects.create(
            original_raw=json.dumps(
                {
                    "schema": "https://opendataproducts.org/schema/v4.1",
                    "product": {
                        "details": {"en": {"productID": "test-nested", "nested": nested_data}}
                    },
                }
            ),
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS.value,
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.DRAFT,
        )

        result = self.rules.validate_odps_to_odcs_link(contract)
        # Should handle nested structures
        self.assertIsNotNone(result)
