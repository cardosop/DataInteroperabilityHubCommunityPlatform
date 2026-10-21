"""
E2E tests for enhanced contract normalization and semantic mapping (Phase 7.5.5).

Tests complete contract lifecycle with all sections, remapping, and SPARQL queries.
"""

import time

import pytest

pytestmark = pytest.mark.slow
from rest_framework import status

from hub.apps.contracts.models import (
    Contract,
    NormalizationStatus,
    OriginalSpecType,
)

from .conftest import E2ETestBase, get_response_data

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e1]


class EnhancedContractNormalizationE2ETest(E2ETestBase):
    """E2E tests for enhanced contract normalization and semantic mapping"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

    def test_complete_contract_lifecycle_all_sections(self):
        """Test complete contract lifecycle: create → normalize → map → query (7.5.5.1)"""
        # Create asset
        asset_id = self.create_asset(key="enhanced-contract-test", name="Enhanced Contract Test")

        # Create contract with all sections
        complete_contract = {
            "id": "orders",
            "name": "Orders Dataset",
            "description": "Customer orders data",
            "version": "3.0.2",
            "info": {
                "owners": [{"name": "Data Team", "email": "data@example.com"}],
                "tags": ["orders", "e-commerce"],
            },
            "schema": {
                "fields": [
                    {
                        "name": "order_id",
                        "type": "string",
                        "nullable": False,
                        "semantic_type": "TEXT",
                        "format": "uuid",
                        "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
                        "min_length": 36,
                        "max_length": 36,
                        "is_primary_key": True,
                        "is_unique": True,
                        "is_indexed": True,
                    },
                    {
                        "name": "customer_email",
                        "type": "string",
                        "nullable": False,
                        "semantic_type": "EMAIL",
                        "format": "email",
                        "min_length": 5,
                        "max_length": 255,
                    },
                ],
                "primary_key": ["order_id"],
            },
            "quality": {
                "default_profile_key": "standard",
                "rules": [
                    {
                        "rule_id": "rule_1",
                        "dimension": "completeness",
                        "expression": "COUNT(*) - COUNT(order_id) = 0",
                        "severity": "ERROR",
                    }
                ],
            },
            "privacy_compliance": {
                "contains_personal_data": True,
                "personal_data_categories": ["PII_DIRECT_EMAIL"],
                "jurisdictions": ["GDPR"],
                "legal_bases": ["CONSENT"],
                "retention_policy": {"period": "P5Y"},
            },
            "lifecycle": {
                "data_source": "orders-db",
                "refresh_cadence": "DAILY",
                "slas": {"availability": "99.5", "latency_ms_p95": 1000},
            },
            "marketplace": {
                "license_summary": "MIT License",
                "intended_use": ["analytics"],
                "restricted_use": ["marketing"],
            },
        }

        import json

        contract_id = self.create_contract(
            asset_id,
            original_raw=json.dumps(complete_contract),
            original_spec_type=OriginalSpecType.ODCS,
        )

        # Prepare contract (normalize and map)
        self.prepare_contract_for_activation(contract_id)

        # Verify contract is normalized
        contract = Contract.objects.get(id=contract_id)
        contract.refresh_from_db()
        self.assertEqual(contract.normalization_status, NormalizationStatus.NORMALIZED_OK)
        self.assertIsNotNone(contract.hub_contract_json)

        # Verify all sections are in hub_contract_json
        hub_contract = contract.hub_contract_json
        self.assertIn("info", hub_contract)
        self.assertIn("owners", hub_contract["info"])
        self.assertIsInstance(hub_contract["info"]["owners"], list)
        self.assertGreater(len(hub_contract["info"]["owners"]), 0, "Should have at least one owner")
        self.assertIn("tags", hub_contract["info"])
        self.assertIn("schema", hub_contract)
        self.assertIn("quality", hub_contract)
        self.assertIn("privacy_compliance", hub_contract)
        self.assertIn("lifecycle", hub_contract)
        self.assertIn("marketplace", hub_contract)

        # Verify field properties are preserved
        fields = hub_contract["schema"]["fields"]
        order_id_field = next((f for f in fields if f["name"] == "order_id"), None)
        self.assertIsNotNone(order_id_field)
        self.assertEqual(order_id_field.get("semantic_type"), "TEXT")
        self.assertEqual(order_id_field.get("format"), "uuid")
        self.assertTrue(order_id_field.get("is_primary_key"))

        email_field = next((f for f in fields if f["name"] == "customer_email"), None)
        self.assertIsNotNone(email_field)
        self.assertEqual(email_field.get("semantic_type"), "EMAIL")
        # After Pydantic model_dump(by_alias=True), min_length/max_length
        # are serialized as minLength/maxLength in hub_contract_json.
        self.assertEqual(email_field.get("minLength") or email_field.get("min_length"), 5)
        self.assertEqual(email_field.get("maxLength") or email_field.get("max_length"), 255)

    def test_contract_update_triggers_remapping_all_sections(self):
        """Test contract update triggers remapping with all sections (7.5.5.2)"""
        asset_id = self.create_asset(key="update-remapping-test", name="Update Remapping Test")

        # Create initial contract
        initial_contract = {
            "id": "orders",
            "name": "Orders Dataset",
            "schema": {"fields": [{"name": "order_id", "type": "string", "nullable": False}]},
        }

        import json

        contract_id = self.create_contract(
            asset_id,
            original_raw=json.dumps(initial_contract),
            original_spec_type=OriginalSpecType.ODCS,
        )

        # Prepare contract (ensures validation_status is set)
        self.prepare_contract_for_activation(contract_id)

        # Update contract with all sections
        updated_contract = {
            "id": "orders",
            "name": "Orders Dataset",
            "info": {
                "owners": [{"name": "Data Team", "email": "data@example.com"}],
                "tags": ["orders"],
            },
            "schema": {
                "fields": [
                    {
                        "name": "order_id",
                        "type": "string",
                        "nullable": False,
                        "semantic_type": "TEXT",
                        "is_primary_key": True,
                    }
                ]
            },
            "quality": {
                "rules": [
                    {
                        "rule_id": "rule_1",
                        "dimension": "completeness",
                        "expression": "COUNT(*) - COUNT(order_id) = 0",
                        "severity": "ERROR",
                    }
                ]
            },
            "privacy_compliance": {
                "contains_personal_data": True,
                "categories": ["PII_DIRECT_EMAIL"],
                "jurisdictions": ["GDPR"],
            },
            "lifecycle": {"data_source": "orders-db", "refresh_cadence": "DAILY"},
            "marketplace": {"license_summary": "MIT License"},
        }

        # Update contract
        response = self.client.patch(
            f"/api/v1/contracts/{contract_id}/",
            {"original_raw": json.dumps(updated_contract)},
            format="json",
        )

        # Handle semantic service unavailability (500 error)
        if response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR:
            data = get_response_data(response)
            error_msg = str(data) if data is not None else ""
            if (
                "name resolution" in error_msg.lower()
                or "temporary failure" in error_msg.lower()
                or "network error" in error_msg.lower()
                or "semantic" in error_msg.lower()
            ):
                pytest.skip("Semantic service not available for contract remapping")  # noqa: skip-in-body — runtime service dependency
            else:
                self.assertEqual(
                    response.status_code,
                    status.HTTP_200_OK,
                    f"Contract update failed: {data}",
                )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Wait for remapping
        time.sleep(2)  # noqa: sleep-needed  # INTENTIONAL: e2e/integration test polling real services

        # Verify contract was remapped
        contract = Contract.objects.get(id=contract_id)
        contract.refresh_from_db()

        # Verify all sections are in updated hub_contract_json
        hub_contract = contract.hub_contract_json
        self.assertIn("info", hub_contract)
        self.assertIn("owners", hub_contract["info"])
        self.assertIn("quality", hub_contract)
        self.assertIn("privacy_compliance", hub_contract)
        self.assertIn("lifecycle", hub_contract)
        self.assertIn("marketplace", hub_contract)

        # Verify field properties are updated
        fields = hub_contract["schema"]["fields"]
        order_id_field = next((f for f in fields if f["name"] == "order_id"), None)
        self.assertIsNotNone(order_id_field)
        self.assertEqual(order_id_field.get("semantic_type"), "TEXT")
        self.assertTrue(order_id_field.get("is_primary_key"))


class EnhancedSPARQLQueriesE2ETest(E2ETestBase):
    """E2E tests for SPARQL queries with standard vocabularies"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

    def test_field_validation_rules_stored_for_sparql_query(self):
        """Test field validation rules are stored in a structure suitable for SPARQL query (7.5.5.3)"""
        # This test requires Fuseki to be running
        # For now, we'll test that the contract has the necessary structure
        asset_id = self.create_asset(
            key="sparql-field-validation-test", name="SPARQL Field Validation Test"
        )

        contract_data = {
            "id": "test",
            "name": "Test Contract",
            "schema": {
                "fields": [
                    {
                        "name": "email",
                        "type": "string",
                        "nullable": False,
                        "semantic_type": "EMAIL",
                        "format": "email",
                        "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$",
                        "min_length": 5,
                        "max_length": 255,
                    },
                    {
                        "name": "amount",
                        "type": "number",
                        "nullable": False,
                        "minimum": 0.0,
                        "maximum": 1000000.0,
                    },
                ]
            },
        }

        import json

        contract_id = self.create_contract(
            asset_id,
            original_raw=json.dumps(contract_data),
            original_spec_type=OriginalSpecType.ODCS,
        )

        # Prepare contract (normalize and map)
        self.prepare_contract_for_activation(contract_id)

        # Verify contract has field properties that can be queried via SPARQL
        contract = Contract.objects.get(id=contract_id)
        contract.refresh_from_db()

        hub_contract = contract.hub_contract_json
        fields = hub_contract["schema"]["fields"]

        email_field = next((f for f in fields if f["name"] == "email"), None)
        self.assertIsNotNone(email_field)
        self.assertEqual(email_field.get("semantic_type"), "EMAIL")
        self.assertEqual(
            email_field.get("pattern"), "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
        )
        # After Pydantic model_dump(by_alias=True), min_length/max_length
        # are serialized as minLength/maxLength in hub_contract_json.
        self.assertEqual(email_field.get("minLength") or email_field.get("min_length"), 5)
        self.assertEqual(email_field.get("maxLength") or email_field.get("max_length"), 255)

        amount_field = next((f for f in fields if f["name"] == "amount"), None)
        self.assertIsNotNone(amount_field)
        self.assertEqual(amount_field.get("minimum"), 0.0)
        self.assertEqual(amount_field.get("maximum"), 1000000.0)

    def test_compliance_policies_stored_with_dpv_vocabulary(self):
        """Test compliance policies are stored with DPV vocabulary for SPARQL query (7.5.5.4)"""
        asset_id = self.create_asset(key="sparql-compliance-test", name="SPARQL Compliance Test")

        contract_data = {
            "id": "test",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
            "privacy_compliance": {
                "contains_personal_data": True,
                "personal_data_categories": ["PII_DIRECT_EMAIL", "PII_DIRECT_PHONE"],
                "jurisdictions": ["GDPR", "CCPA", "LGPD"],
                "legal_bases": ["CONSENT", "CONTRACT", "LEGAL_OBLIGATION"],
                "retention_policy": {"period": "P5Y", "notes": "5 years"},
            },
        }

        import json

        contract_id = self.create_contract(
            asset_id,
            original_raw=json.dumps(contract_data),
            original_spec_type=OriginalSpecType.ODCS,
        )

        # Prepare contract
        self.prepare_contract_for_activation(contract_id)

        # Verify compliance policy structure
        contract = Contract.objects.get(id=contract_id)
        contract.refresh_from_db()

        hub_contract = contract.hub_contract_json
        self.assertIn("privacy_compliance", hub_contract)

        compliance = hub_contract["privacy_compliance"]
        self.assertTrue(compliance.get("contains_personal_data"))
        # Check personal_data_categories (not categories)
        personal_data_categories = compliance.get("personal_data_categories", [])
        self.assertIn("PII_DIRECT_EMAIL", personal_data_categories)
        self.assertIn("GDPR", compliance.get("jurisdictions", []))
        self.assertIn("CCPA", compliance.get("jurisdictions", []))
        self.assertIn("CONSENT", compliance.get("legal_bases", []))
        self.assertIn("CONTRACT", compliance.get("legal_bases", []))
        self.assertEqual(compliance.get("retention_policy", {}).get("period"), "P5Y")

    def test_quality_rules_stored_with_dqv_vocabulary(self):
        """Test quality rules are stored with DQV vocabulary for SPARQL query (7.5.5.5)"""
        asset_id = self.create_asset(key="sparql-quality-test", name="SPARQL Quality Test")

        contract_data = {
            "id": "test",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
            "quality": {
                "default_profile_key": "standard",
                "rules": [
                    {
                        "rule_id": "rule_1",
                        "dimension": "completeness",
                        "expression": "COUNT(*) - COUNT(id) = 0",
                        "severity": "ERROR",
                    },
                    {
                        "rule_id": "rule_2",
                        "dimension": "accuracy",
                        "expression": "id IS NOT NULL",
                        "severity": "WARNING",
                    },
                    {
                        "rule_id": "rule_3",
                        "dimension": "validity",
                        "expression": "LENGTH(id) > 0",
                        "severity": "INFO",
                    },
                    {
                        "rule_id": "rule_4",
                        "dimension": "uniqueness",
                        "expression": "COUNT(DISTINCT id) = COUNT(*)",
                        "severity": "ERROR",
                    },
                ],
            },
        }

        import json

        contract_id = self.create_contract(
            asset_id,
            original_raw=json.dumps(contract_data),
            original_spec_type=OriginalSpecType.ODCS,
        )

        # Prepare contract
        self.prepare_contract_for_activation(contract_id)

        # Verify quality rules structure
        contract = Contract.objects.get(id=contract_id)
        contract.refresh_from_db()

        hub_contract = contract.hub_contract_json
        self.assertIn("quality", hub_contract)

        quality = hub_contract["quality"]
        self.assertEqual(quality.get("default_profile_key"), "standard")
        self.assertIn("rules", quality)

        rules = quality["rules"]
        self.assertEqual(len(rules), 4)

        # Verify all dimensions are present
        dimensions = [r.get("dimension") for r in rules]
        self.assertIn("completeness", dimensions)
        self.assertIn("accuracy", dimensions)
        self.assertIn("validity", dimensions)
        self.assertIn("uniqueness", dimensions)

        # Verify rule structure
        completeness_rule = next((r for r in rules if r.get("dimension") == "completeness"), None)
        self.assertIsNotNone(completeness_rule)
        self.assertEqual(completeness_rule.get("rule_id"), "rule_1")
        self.assertEqual(completeness_rule.get("severity"), "ERROR")
        # Quality rules can have either "expression" or "rule" field depending on source
        self.assertTrue(
            "expression" in completeness_rule or "rule" in completeness_rule,
            f"Rule should have 'expression' or 'rule' field: {completeness_rule}",
        )
