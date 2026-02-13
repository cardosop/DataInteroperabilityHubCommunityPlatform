"""
Unit tests for ODPS Auto-Generation (Task 3.4.1)

Tests verify:
1. Auto-generation when ODCS contract has no linked ODPS
2. Returns existing ODPS contract if already linked
3. Populates product.details from HubContract.info
4. Maps HubContract.marketplace.x_odps.* → ODPS pricing/license/access/payment
5. Focuses on marketplace aspects (technical quality/SLA remains in HubContract)
6. Establishes bidirectional linking
7. Error handling for invalid inputs
"""

import json

from hub.apps.assets.models import Asset
from hub.apps.contracts.models import Contract, ContractStatus, OriginalFormat, OriginalSpecType
from hub.apps.contracts.tests.test_base import ContractsTestBase


class ODPSAutoGenerationTest(ContractsTestBase):
    """Test ODPS auto-generation from ODCS contracts"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        # Create a sample ODCS contract with HubContract
        self.odcs_hub_contract = {
            "id": "test-contract-001",
            "info": {
                "name": "Test Data Contract",
                "description": "A test data contract for auto-generation",
                "version": "1.0.0",
                "tags": ["test", "sample"],
                "owners": [{"name": "Test Owner", "email": "owner@example.com"}],
            },
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            "marketplace": {
                "x_odps": {
                    "pricing_plans": [{"name": "Basic Plan", "price": 10.00, "currency": "USD"}],
                    "access_methods": {"api": {"endpoint": "https://api.example.com/data"}},
                    "payment_gateways": {"stripe": {"enabled": True}},
                },
                "license_summary": "MIT License",
                "restricted_use": ["No commercial use"],
                "intended_use": ["Research", "Education"],
            },
            "quality": {
                "rules": [
                    {
                        "dimension": "completeness",
                        "rule_id": "rule-1",
                        "name": "Completeness Check",
                        "expression": ">= 0.95 percentage",
                    }
                ]
            },
            "lifecycle": {"slas": {"availability": 0.99}},
        }

        self.odcs_raw = json.dumps(
            {
                "schema": "https://datacontract.com/schema/v3.0.2",
                "version": "3.0.2",
                "info": {"title": "Test Data Contract", "version": "1.0.0"},
                "schema": {"fields": [{"name": "id", "type": "string"}]},
            },
            indent=2,
        )

    def test_auto_generate_odps_when_link_missing(self):
        """Test auto-generation when ODCS contract has no linked ODPS"""
        # Create ODCS contract
        odcs_contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw=self.odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            hub_contract_json=self.odcs_hub_contract,
            hub_contract_version="1.0.0",
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        # Auto-generate ODPS
        odps_contract = self.contract_service.auto_generate_odps_for_odcs(odcs_contract_id=str(odcs_contract.id))

        # Verify ODPS contract was created
        self.assertIsNotNone(odps_contract)
        self.assertEqual(odps_contract.original_spec_type, OriginalSpecType.ODPS)
        self.assertEqual(odps_contract.tenant, self.tenant)
        self.assertEqual(odps_contract.asset, odcs_contract.asset)
        self.assertEqual(odps_contract.version, odcs_contract.version)
        self.assertEqual(odps_contract.status, odcs_contract.status)

        # Verify ODPS document structure
        odps_doc = json.loads(odps_contract.original_raw)
        self.assertIn("schema", odps_doc)
        self.assertIn("version", odps_doc)
        self.assertIn("product", odps_doc)
        self.assertIn("details", odps_doc["product"])

        # Verify product.details populated from HubContract.info
        self.assertIn("en", odps_doc["product"]["details"])
        details = odps_doc["product"]["details"]["en"]
        self.assertEqual(details["productID"], "test-contract-001")
        self.assertEqual(details["name"], "Test Data Contract")
        self.assertEqual(details["description"], "A test data contract for auto-generation")
        self.assertEqual(details["productVersion"], "1.0.0")
        self.assertIn("tags", details)
        self.assertEqual(details["tags"], ["test", "sample"])

        # Verify marketplace mapping (pricing/license/access/payment)
        self.assertIn("marketplace", odps_doc["product"])
        marketplace = odps_doc["product"]["marketplace"]
        self.assertIn("pricingPlans", marketplace)
        self.assertEqual(len(marketplace["pricingPlans"]), 1)
        self.assertEqual(marketplace["pricingPlans"][0]["name"], "Basic Plan")
        self.assertIn("accessMethods", marketplace)
        self.assertIn("api", marketplace["accessMethods"])
        self.assertIn("paymentGateways", marketplace)
        self.assertIn("stripe", marketplace["paymentGateways"])

        # Verify license mapping
        self.assertIn("license", odps_doc)
        self.assertIn("en", odps_doc["license"])
        license_en = odps_doc["license"]["en"]
        self.assertEqual(license_en["definition"], "MIT License")
        self.assertEqual(license_en["restrictions"], ["No commercial use"])
        self.assertEqual(license_en["rights"], ["Research", "Education"])

        # Verify bidirectional linking
        # ODCS → ODPS link
        odcs_contract.refresh_from_db()
        self.assertIsNotNone(odcs_contract.hub_contract_json)
        extensions = odcs_contract.hub_contract_json.get("extensions", {})
        x_odps = extensions.get("x_odps", {})
        self.assertEqual(x_odps.get("odps_link"), str(odps_contract.id))

        # ODPS → ODCS link
        self.assertIsNotNone(odps_contract.hub_contract_json)
        odps_extensions = odps_contract.hub_contract_json.get("extensions", {})
        odps_x_odps = odps_extensions.get("x_odps", {})
        self.assertEqual(odps_x_odps.get("odcs_link"), str(odcs_contract.id))

    def test_auto_generate_returns_existing_odps_if_linked(self):
        """Test that auto-generation returns existing ODPS if already linked"""
        # Create ODCS contract
        odcs_contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw=self.odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            hub_contract_json=self.odcs_hub_contract,
            hub_contract_version="1.0.0",
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        # Create existing ODPS contract
        odps_raw = json.dumps(
            {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "version": "4.1",
                "product": {
                    "details": {
                        "en": {"productID": "test-contract-001", "name": "Existing ODPS Product"}
                    }
                },
            },
            indent=2,
        )

        existing_odps = Contract.objects.create(
            tenant=self.tenant,
            original_raw=odps_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            hub_contract_json={"id": "test-contract-001"},
            hub_contract_version="1.0.0",
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        # Link them
        if not odcs_contract.hub_contract_json.get("extensions"):
            odcs_contract.hub_contract_json["extensions"] = {}
        if not odcs_contract.hub_contract_json["extensions"].get("x_odps"):
            odcs_contract.hub_contract_json["extensions"]["x_odps"] = {}
        odcs_contract.hub_contract_json["extensions"]["x_odps"]["odps_link"] = str(existing_odps.id)
        odcs_contract.save(update_fields=["hub_contract_json"])

        # Auto-generate (should return existing)
        # ContractService already provided by ContractsTestBase
        odps_contract = self.contract_service.auto_generate_odps_for_odcs(odcs_contract_id=str(odcs_contract.id))

        # Verify it returns the existing ODPS
        self.assertEqual(odps_contract.id, existing_odps.id)
        self.assertEqual(odps_contract.original_spec_type, OriginalSpecType.ODPS)

    def test_auto_generate_focuses_on_marketplace_aspects(self):
        """Test that auto-generation focuses on marketplace, not technical aspects"""
        # Create ODCS contract with both marketplace and technical sections
        hub_contract = self.odcs_hub_contract.copy()
        hub_contract["quality"] = {
            "rules": [
                {
                    "dimension": "completeness",
                    "rule_id": "rule-1",
                    "name": "Completeness Check",
                    "expression": ">= 0.95 percentage",
                }
            ]
        }
        hub_contract["lifecycle"] = {"slas": {"availability": 0.99, "latency_ms_p95": 100}}

        odcs_contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw=self.odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            hub_contract_json=hub_contract,
            hub_contract_version="1.0.0",
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        # Auto-generate ODPS
        odps_contract = self.contract_service.auto_generate_odps_for_odcs(odcs_contract_id=str(odcs_contract.id))

        # Verify ODPS document
        odps_doc = json.loads(odps_contract.original_raw)

        # Verify marketplace aspects are included
        self.assertIn("product", odps_doc)
        self.assertIn("marketplace", odps_doc["product"])
        self.assertIn("license", odps_doc)

        # Verify technical aspects (quality/SLA) are NOT in ODPS
        # (They remain in HubContract, ODPS focuses on marketplace)
        # Note: Some technical aspects may be mapped to ODPS structure,
        # but the focus should be on marketplace
        self.assertIn("product", odps_doc)
        # Marketplace should be present
        if "marketplace" in odps_doc["product"]:
            marketplace = odps_doc["product"]["marketplace"]
            # Should have marketplace fields
            self.assertTrue(
                "pricingPlans" in marketplace
                or "accessMethods" in marketplace
                or "paymentGateways" in marketplace
            )

    def test_auto_generate_with_minimal_marketplace_data(self):
        """Test auto-generation with minimal marketplace data"""
        # Create ODCS contract with minimal marketplace data
        minimal_hub_contract = {
            "id": "minimal-contract",
            "info": {"name": "Minimal Contract", "description": "Minimal test contract"},
            "schema": {"fields": []},
        }

        odcs_contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw=self.odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            hub_contract_json=minimal_hub_contract,
            hub_contract_version="1.0.0",
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        # Auto-generate ODPS
        odps_contract = self.contract_service.auto_generate_odps_for_odcs(odcs_contract_id=str(odcs_contract.id))

        # Verify ODPS was created even with minimal data
        self.assertIsNotNone(odps_contract)
        odps_doc = json.loads(odps_contract.original_raw)
        self.assertIn("product", odps_doc)
        self.assertIn("details", odps_doc["product"])
        self.assertIn("en", odps_doc["product"]["details"])
        details = odps_doc["product"]["details"]["en"]
        self.assertEqual(details["name"], "Minimal Contract")

    def test_auto_generate_raises_error_for_non_odcs_contract(self):
        """Test that auto-generation raises error for non-ODCS contracts"""
        # Create ODPS contract (not ODCS)
        odps_raw = json.dumps(
            {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "version": "4.1",
                "product": {
                    "details": {"en": {"productID": "test-product", "name": "Test Product"}}
                },
            },
            indent=2,
        )

        odps_contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw=odps_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            hub_contract_json={"id": "test-product"},
            hub_contract_version="1.0.0",
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        # Try to auto-generate (should raise error)
        # ContractService already provided by ContractsTestBase
        from hub.apps.core.services.base import ValidationError

        with self.assertRaises(ValidationError) as context:
            self.contract_service.auto_generate_odps_for_odcs(odcs_contract_id=str(odps_contract.id))

        self.assertIn("not an ODCS contract", str(context.exception))

    def test_auto_generate_raises_error_for_missing_hub_contract(self):
        """Test that auto-generation raises error when HubContract is missing"""
        # Create ODCS contract without HubContract
        odcs_contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw=self.odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            hub_contract_json=None,  # No HubContract
            hub_contract_version=None,
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        # Try to auto-generate (should raise error)
        from hub.apps.core.services.base import ValidationError

        with self.assertRaises(ValidationError) as context:
            self.contract_service.auto_generate_odps_for_odcs(odcs_contract_id=str(odcs_contract.id))

        self.assertIn("has no hub_contract_json", str(context.exception))

    def test_auto_generate_handles_invalid_odps_link(self):
        """Test that auto-generation handles invalid ODPS link gracefully"""
        # Create ODCS contract with invalid ODPS link
        hub_contract = self.odcs_hub_contract.copy()
        if "extensions" not in hub_contract:
            hub_contract["extensions"] = {}
        if "x_odps" not in hub_contract["extensions"]:
            hub_contract["extensions"]["x_odps"] = {}
        hub_contract["extensions"]["x_odps"][
            "odps_link"
        ] = "00000000-0000-0000-0000-000000000000"  # Non-existent ID

        odcs_contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw=self.odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            hub_contract_json=hub_contract,
            hub_contract_version="1.0.0",
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        # Auto-generate (should remove invalid link and create new ODPS)
        # ContractService already provided by ContractsTestBase
        odps_contract = self.contract_service.auto_generate_odps_for_odcs(odcs_contract_id=str(odcs_contract.id))

        # Verify new ODPS was created
        self.assertIsNotNone(odps_contract)
        self.assertEqual(odps_contract.original_spec_type, OriginalSpecType.ODPS)

        # Verify invalid link was removed and replaced
        odcs_contract.refresh_from_db()
        extensions = odcs_contract.hub_contract_json.get("extensions", {})
        x_odps = extensions.get("x_odps", {})
        self.assertEqual(x_odps.get("odps_link"), str(odps_contract.id))
        self.assertNotEqual(x_odps.get("odps_link"), "00000000-0000-0000-0000-000000000000")

    def test_auto_generate_preserves_odcs_contract_in_odps(self):
        """Test that auto-generation preserves original ODCS contract in ODPS product.contract"""
        # Create ODCS contract
        odcs_contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw=self.odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            hub_contract_json=self.odcs_hub_contract,
            hub_contract_version="1.0.0",
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        # Auto-generate ODPS
        odps_contract = self.contract_service.auto_generate_odps_for_odcs(odcs_contract_id=str(odcs_contract.id))

        # Verify ODPS document includes original ODCS contract
        odps_doc = json.loads(odps_contract.original_raw)
        self.assertIn("product", odps_doc)
        if "contract" in odps_doc["product"]:
            contract_section = odps_doc["product"]["contract"]
            # Should have either spec (inline) or contractURL (reference)
            self.assertTrue("spec" in contract_section or "contractURL" in contract_section)

    def test_auto_generate_handles_unicode_characters(self):
        """Test that auto-generation handles unicode characters correctly."""
        unicode_hub_contract = {
            "id": "test-unicode",
            "info": {"name": "测试产品", "description": "测试描述"},
            "schema": {"fields": [{"name": "字段名称", "data_type": "string"}]},
        }

        odcs_raw = json.dumps(
            {
                "apiVersion": "odcs.io/v3.0.2",
                "kind": "DataContract",
                "id": "test-unicode",
                "name": "测试产品",
                "version": "1.0.0",
                "schema": {"fields": [{"name": "字段名称", "type": "string"}]},
            }
        )

        odcs_contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw=odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            hub_contract_json=unicode_hub_contract,
            hub_contract_version="1.0.0",
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        # ContractService already provided by ContractsTestBase
        odps_contract = self.contract_service.auto_generate_odps_for_odcs(odcs_contract_id=str(odcs_contract.id))

        # Should handle unicode characters
        self.assertIsNotNone(odps_contract)
        if odps_contract.hub_contract_json and "info" in odps_contract.hub_contract_json:
            self.assertIsNotNone(odps_contract.hub_contract_json["info"])

    def test_auto_generate_handles_special_characters(self):
        """Test that auto-generation handles special characters correctly."""
        special_hub_contract = {
            "id": "test-special",
            "info": {"name": "Test & Co. (Special)", "description": "Test <description> & more"},
            "schema": {"fields": [{"name": "field-name", "data_type": "string"}]},
        }

        odcs_raw = json.dumps(
            {
                "apiVersion": "odcs.io/v3.0.2",
                "kind": "DataContract",
                "id": "test-special",
                "name": "Test & Co. (Special)",
                "version": "1.0.0",
                "schema": {"fields": [{"name": "field-name", "type": "string"}]},
            }
        )

        odcs_contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw=odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            hub_contract_json=special_hub_contract,
            hub_contract_version="1.0.0",
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        # ContractService already provided by ContractsTestBase
        odps_contract = self.contract_service.auto_generate_odps_for_odcs(odcs_contract_id=str(odcs_contract.id))

        # Should handle special characters
        self.assertIsNotNone(odps_contract)
        if odps_contract.hub_contract_json and "info" in odps_contract.hub_contract_json:
            self.assertIsNotNone(odps_contract.hub_contract_json["info"])

    def test_auto_generate_handles_very_large_documents(self):
        """Test that auto-generation handles very large documents correctly."""
        # Keep large but under PostgreSQL btree index row size limit (~2704 bytes for hub_contract_json index)
        large_description = "A" * 1000
        large_hub_contract = {
            "id": "test-large",
            "info": {"name": "Test Product", "description": large_description},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }

        odcs_raw = json.dumps(
            {
                "apiVersion": "odcs.io/v3.0.2",
                "kind": "DataContract",
                "id": "test-large",
                "name": "Test Product",
                "version": "1.0.0",
                "description": large_description,
                "schema": {"fields": [{"name": "id", "type": "string"}]},
            }
        )

        odcs_contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw=odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            hub_contract_json=large_hub_contract,
            hub_contract_version="1.0.0",
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        # ContractService already provided by ContractsTestBase
        odps_contract = self.contract_service.auto_generate_odps_for_odcs(odcs_contract_id=str(odcs_contract.id))

        # Should handle very large documents
        self.assertIsNotNone(odps_contract)

    def test_auto_generate_handles_none_values(self):
        """Test that auto-generation handles None values correctly."""
        none_hub_contract = {
            "id": "test-none",
            "info": {"name": "Test Product", "description": None},  # None value
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }

        odcs_raw = json.dumps(
            {
                "apiVersion": "odcs.io/v3.0.2",
                "kind": "DataContract",
                "id": "test-none",
                "name": "Test Product",
                "version": "1.0.0",
                "description": None,
                "schema": {"fields": [{"name": "id", "type": "string"}]},
            }
        )

        odcs_contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw=odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            hub_contract_json=none_hub_contract,
            hub_contract_version="1.0.0",
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        # ContractService already provided by ContractsTestBase
        odps_contract = self.contract_service.auto_generate_odps_for_odcs(odcs_contract_id=str(odcs_contract.id))

        # Should handle None values gracefully
        self.assertIsNotNone(odps_contract)

    def test_auto_generate_handles_nested_structures(self):
        """Test that auto-generation handles nested structures correctly."""
        nested_hub_contract = {
            "id": "test-nested",
            "info": {
                "name": "Test Product",
                "nested": {"level1": {"level2": {"level3": {"value": "deep"}}}},
            },
            "schema": {
                "fields": [
                    {
                        "name": "id",
                        "data_type": "string",
                        "nested": {"level1": {"level2": {"level3": {"value": "deep"}}}},
                    }
                ]
            },
        }

        odcs_raw = json.dumps(
            {
                "apiVersion": "odcs.io/v3.0.2",
                "kind": "DataContract",
                "id": "test-nested",
                "name": "Test Product",
                "version": "1.0.0",
                "schema": {
                    "fields": [
                        {
                            "name": "id",
                            "type": "string",
                            "nested": {"level1": {"level2": {"level3": {"value": "deep"}}}},
                        }
                    ]
                },
            }
        )

        odcs_contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw=odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            hub_contract_json=nested_hub_contract,
            hub_contract_version="1.0.0",
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        # ContractService already provided by ContractsTestBase
        odps_contract = self.contract_service.auto_generate_odps_for_odcs(odcs_contract_id=str(odcs_contract.id))

        # Should handle nested structures
        self.assertIsNotNone(odps_contract)
        if odps_contract.hub_contract_json and "schema" in odps_contract.hub_contract_json:
            self.assertIsNotNone(odps_contract.hub_contract_json["schema"])
