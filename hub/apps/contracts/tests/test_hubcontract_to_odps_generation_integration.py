"""
Integration tests for HubContract → ODPS generation (Task 2.3.1)

Comprehensive integration tests verifying:
1. Complete generation flow (end-to-end)
2. All HubContract sections are properly mapped
3. Missing sections handled gracefully (graceful degradation)
4. Complete integration test for full generation

Tests use real implementations (no mocks/stubs) and follow TDD principles.
"""

import json
from django.test import TestCase

from hub.apps.contracts.odps_generator import generate_odps_from_hubcontract
from hub.apps.contracts.odps_errors import ODPSExportError


class HubContractToODPSGenerationIntegrationTest(TestCase):
    """Integration tests for HubContract → ODPS generation"""

    def setUp(self):
        """Set up test fixtures"""
        # Base HubContract with minimal required fields
        self.base_hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "test-product-integration",
            "info": {
                "name": "Integration Test Product",
                "description": "Test product for integration testing",
                "version": "1.0.0",
            },
        }

    def _create_complete_hub_contract(self) -> dict:
        """Create a complete HubContract with all sections"""
        return {
            "hub_contract_version": "1.0.0",
            "id": "test-product-complete",
            "info": {
                "name": "Complete Test Product",
                "description": "A complete test product with all sections",
                "version": "2.0.0",
                "tags": ["data", "test", "integration"],
                "owners": [
                    {
                        "name": "Test Organization",
                        "email": "test@example.com",
                    }
                ],
            },
            "marketplace": {
                "x_odps": {
                    "pricing_plans": [
                        {
                            "planID": "basic",
                            "name": "Basic Plan",
                            "price": 9.99,
                            "currency": "USD",
                        },
                        {
                            "planID": "premium",
                            "name": "Premium Plan",
                            "price": 29.99,
                            "currency": "USD",
                        },
                    ],
                    "access_methods": {
                        "api": {
                            "type": "REST API",
                            "endpoint": "https://api.example.com/v1",
                        },
                        "download": {
                            "type": "File Download",
                            "format": "CSV",
                        },
                    },
                    "payment_gateways": {
                        "stripe": {
                            "enabled": True,
                            "publicKey": "pk_test_123",
                        },
                        "paypal": {
                            "enabled": False,
                        },
                    },
                },
                "license_summary": "MIT License",
                "restricted_use": ["No commercial use", "No redistribution"],
                "intended_use": ["Research", "Education"],
            },
            "quality": {
                "default_profile_key": "default",
                "rules": [
                    {
                        "dimension": "completeness",
                        "field": "id",
                        "rule": "not_null",
                        "level": "error",
                    },
                    {
                        "dimension": "validity",
                        "field": "email",
                        "rule": "is_email",
                        "level": "warning",
                    },
                ],
            },
            "lifecycle": {
                "slas": {
                    "availability": 99.9,
                    "latency_ms_p95": 100,
                },
                "x_odps": {
                    "status": "active",
                },
            },
            "schema": {
                "fields": [
                    {
                        "name": "id",
                        "type": "string",
                        "description": "Unique identifier",
                        "required": True,
                    },
                    {
                        "name": "name",
                        "type": "string",
                        "description": "Name field",
                        "required": True,
                    },
                    {
                        "name": "email",
                        "type": "string",
                        "description": "Email address",
                        "required": False,
                    },
                ],
            },
        }

    def test_complete_generation_flow_with_all_sections(self):
        """
        Test complete generation flow with all HubContract sections.

        Scenario: Generate ODPS from complete HubContract with all sections
        Expected: All sections are properly mapped to ODPS structure
        """
        hub_contract = self._create_complete_hub_contract()

        # Generate ODPS
        odps_doc = generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        # Verify basic structure
        self.assertIsInstance(odps_doc, dict)
        self.assertEqual(odps_doc["schema"], "https://opendataproducts.org/schema/v4.1")
        self.assertEqual(odps_doc["version"], "4.1")
        self.assertIn("product", odps_doc)

        # Verify product.details (from info section)
        self.assertIn("details", odps_doc["product"])
        self.assertIn("en", odps_doc["product"]["details"])
        details = odps_doc["product"]["details"]["en"]
        self.assertEqual(details["productID"], "test-product-complete")
        self.assertEqual(details["name"], "Complete Test Product")
        self.assertEqual(details["description"], "A complete test product with all sections")
        self.assertEqual(details["productVersion"], "2.0.0")
        self.assertEqual(details["tags"], ["data", "test", "integration"])

        # Verify dataHolder (from info.owners)
        self.assertIn("dataHolder", odps_doc)
        self.assertIn("en", odps_doc["dataHolder"])
        data_holder = odps_doc["dataHolder"]["en"]
        self.assertEqual(data_holder["legalName"], "Test Organization")
        self.assertEqual(data_holder["email"], "test@example.com")

        # Verify product.marketplace (from marketplace.x_odps)
        self.assertIn("marketplace", odps_doc["product"])
        marketplace = odps_doc["product"]["marketplace"]
        self.assertIn("pricingPlans", marketplace)
        self.assertEqual(len(marketplace["pricingPlans"]), 2)
        self.assertEqual(marketplace["pricingPlans"][0]["planID"], "basic")
        self.assertEqual(marketplace["pricingPlans"][0]["price"], 9.99)

        self.assertIn("accessMethods", marketplace)
        self.assertIn("api", marketplace["accessMethods"])
        self.assertEqual(marketplace["accessMethods"]["api"]["type"], "REST API")

        self.assertIn("paymentGateways", marketplace)
        self.assertIn("stripe", marketplace["paymentGateways"])
        self.assertTrue(marketplace["paymentGateways"]["stripe"]["enabled"])

        # Verify license (from marketplace.license_summary, restricted_use, intended_use)
        self.assertIn("license", odps_doc)
        self.assertIn("en", odps_doc["license"])
        license_obj = odps_doc["license"]["en"]
        self.assertEqual(license_obj["definition"], "MIT License")
        self.assertEqual(license_obj["restrictions"], ["No commercial use", "No redistribution"])
        self.assertEqual(license_obj["rights"], ["Research", "Education"])

        # Verify product.dataQuality (from quality section)
        self.assertIn("dataQuality", odps_doc["product"])
        data_quality = odps_doc["product"]["dataQuality"]
        self.assertIn("declarative", data_quality)
        self.assertEqual(data_quality["declarative"]["default"], "default")
        self.assertIn("dimensions", data_quality["declarative"])
        dimensions = data_quality["declarative"]["dimensions"]
        self.assertIn("completeness", dimensions)
        self.assertIn("validity", dimensions)

        # Verify product.SLA (from lifecycle section)
        self.assertIn("SLA", odps_doc["product"])
        sla = odps_doc["product"]["SLA"]
        self.assertIn("declarative", sla)
        self.assertIn("dimensions", sla["declarative"])
        dimensions = sla["declarative"]["dimensions"]
        self.assertIn("availability", dimensions)
        self.assertIn("latency", dimensions)

        # Verify lifecycle.x_odps.status → product.details.en.status
        self.assertIn("status", odps_doc["product"]["details"]["en"])
        self.assertEqual(odps_doc["product"]["details"]["en"]["status"], "active")

        # Note: Schema section mapping to product.dataSchema is not yet implemented
        # This is expected behavior - schema mapping may be added in future tasks
        # For now, we verify that the generation succeeds even with schema section present

    def test_generation_with_minimal_hub_contract(self):
        """
        Test generation with minimal HubContract (only required fields).

        Scenario: Generate ODPS from HubContract with only required fields
        Expected: ODPS generated successfully with only required sections
        """
        hub_contract = self.base_hub_contract.copy()

        # Generate ODPS
        odps_doc = generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        # Verify basic structure
        self.assertIsInstance(odps_doc, dict)
        self.assertEqual(odps_doc["schema"], "https://opendataproducts.org/schema/v4.1")
        self.assertEqual(odps_doc["version"], "4.1")
        self.assertIn("product", odps_doc)

        # Verify product.details exists
        self.assertIn("details", odps_doc["product"])
        self.assertIn("en", odps_doc["product"]["details"])
        details = odps_doc["product"]["details"]["en"]
        self.assertEqual(details["productID"], "test-product-integration")
        self.assertEqual(details["name"], "Integration Test Product")

        # Verify optional sections are not present
        self.assertNotIn("dataHolder", odps_doc)
        self.assertNotIn("marketplace", odps_doc["product"])
        self.assertNotIn("license", odps_doc)
        self.assertNotIn("dataQuality", odps_doc["product"])
        self.assertNotIn("lifecycle", odps_doc["product"])
        self.assertNotIn("dataSchema", odps_doc["product"])

    def test_generation_with_missing_marketplace_section(self):
        """
        Test generation with missing marketplace section (graceful degradation).

        Scenario: Generate ODPS from HubContract without marketplace section
        Expected: ODPS generated successfully without marketplace/license sections
        """
        hub_contract = self.base_hub_contract.copy()
        hub_contract["info"]["tags"] = ["test"]
        hub_contract["quality"] = {
            "default_profile_key": "default",
        }

        # Generate ODPS
        odps_doc = generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        # Verify basic structure exists
        self.assertIn("product", odps_doc)
        self.assertIn("details", odps_doc["product"])

        # Verify marketplace section is not present
        self.assertNotIn("marketplace", odps_doc["product"])
        self.assertNotIn("license", odps_doc)

        # Verify other sections still work
        self.assertIn("dataQuality", odps_doc["product"])

    def test_generation_with_missing_quality_section(self):
        """
        Test generation with missing quality section (graceful degradation).

        Scenario: Generate ODPS from HubContract without quality section
        Expected: ODPS generated successfully without dataQuality section
        """
        hub_contract = self.base_hub_contract.copy()
        hub_contract["marketplace"] = {
            "license_summary": "MIT License",
        }

        # Generate ODPS
        odps_doc = generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        # Verify basic structure exists
        self.assertIn("product", odps_doc)
        self.assertIn("details", odps_doc["product"])

        # Verify quality section is not present
        self.assertNotIn("dataQuality", odps_doc["product"])

        # Verify marketplace section still works
        self.assertIn("license", odps_doc)

    def test_generation_with_missing_lifecycle_section(self):
        """
        Test generation with missing lifecycle section (graceful degradation).

        Scenario: Generate ODPS from HubContract without lifecycle section
        Expected: ODPS generated successfully without lifecycle section
        """
        hub_contract = self.base_hub_contract.copy()
        hub_contract["marketplace"] = {
            "license_summary": "MIT License",
        }
        hub_contract["quality"] = {
            "default_profile_key": "default",
        }

        # Generate ODPS
        odps_doc = generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        # Verify basic structure exists
        self.assertIn("product", odps_doc)

        # Verify SLA section is not present (no lifecycle.slas)
        self.assertNotIn("SLA", odps_doc["product"])

        # Verify other sections still work
        self.assertIn("dataQuality", odps_doc["product"])
        self.assertIn("license", odps_doc)

    def test_generation_with_missing_schema_section(self):
        """
        Test generation with missing schema section (graceful degradation).

        Scenario: Generate ODPS from HubContract without schema section
        Expected: ODPS generated successfully without dataSchema section
        """
        hub_contract = self.base_hub_contract.copy()
        hub_contract["marketplace"] = {
            "license_summary": "MIT License",
        }

        # Generate ODPS
        odps_doc = generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        # Verify basic structure exists
        self.assertIn("product", odps_doc)

        # Verify schema section is not present
        self.assertNotIn("dataSchema", odps_doc["product"])

        # Verify other sections still work
        self.assertIn("license", odps_doc)

    def test_generation_with_partial_marketplace_section(self):
        """
        Test generation with partial marketplace section (graceful degradation).

        Scenario: Generate ODPS from HubContract with only some marketplace fields
        Expected: ODPS generated successfully with only available marketplace fields
        """
        hub_contract = self.base_hub_contract.copy()
        hub_contract["marketplace"] = {
            "license_summary": "MIT License",
            # Missing x_odps, restricted_use, intended_use
        }

        # Generate ODPS
        odps_doc = generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        # Verify basic structure exists
        self.assertIn("product", odps_doc)

        # Verify marketplace section is empty or not present (no x_odps)
        # The generator may create an empty marketplace dict, which is acceptable
        if "marketplace" in odps_doc["product"]:
            marketplace = odps_doc["product"]["marketplace"]
            # If marketplace exists, it should be empty (no pricingPlans, accessMethods, etc.)
            self.assertNotIn("pricingPlans", marketplace)
            self.assertNotIn("accessMethods", marketplace)
            self.assertNotIn("paymentGateways", marketplace)

        # Verify license section exists with only definition
        self.assertIn("license", odps_doc)
        self.assertIn("en", odps_doc["license"])
        license_obj = odps_doc["license"]["en"]
        self.assertEqual(license_obj["definition"], "MIT License")
        # Note: restrictions and rights are optional, so they may or may not be present

    def test_generation_with_partial_quality_section(self):
        """
        Test generation with partial quality section (graceful degradation).

        Scenario: Generate ODPS from HubContract with only default_profile_key
        Expected: ODPS generated successfully with only default profile
        """
        hub_contract = self.base_hub_contract.copy()
        hub_contract["quality"] = {
            "default_profile_key": "default",
            # Missing rules
        }

        # Generate ODPS
        odps_doc = generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        # Verify basic structure exists
        self.assertIn("product", odps_doc)

        # Verify dataQuality section exists with only default
        self.assertIn("dataQuality", odps_doc["product"])
        data_quality = odps_doc["product"]["dataQuality"]
        self.assertIn("declarative", data_quality)
        self.assertEqual(data_quality["declarative"]["default"], "default")
        self.assertNotIn("dimensions", data_quality["declarative"])

    def test_generation_with_original_odcs_contract_embedded(self):
        """
        Test generation with original ODCS contract embedded inline.

        Scenario: Generate ODPS with original_odcs_contract parameter
        Expected: ODPS includes product.contract.spec with embedded ODCS
        """
        hub_contract = self.base_hub_contract.copy()
        original_odcs = {
            "id": "test-odcs-contract",
            "name": "Test ODCS Contract",
            "version": "3.0.2",
        }

        # Generate ODPS with embedded ODCS
        odps_doc = generate_odps_from_hubcontract(
            hub_contract,
            target_version="4.1",
            original_odcs_contract=original_odcs,
        )

        # Verify contract section exists
        self.assertIn("product", odps_doc)
        self.assertIn("contract", odps_doc["product"])
        self.assertIn("spec", odps_doc["product"]["contract"])
        self.assertEqual(odps_doc["product"]["contract"]["spec"], original_odcs)
        self.assertNotIn("contractURL", odps_doc["product"]["contract"])

    def test_generation_with_original_odcs_url_referenced(self):
        """
        Test generation with original ODCS contract URL referenced.

        Scenario: Generate ODPS with original_odcs_url parameter
        Expected: ODPS includes product.contract.contractURL
        """
        hub_contract = self.base_hub_contract.copy()
        original_odcs_url = "https://example.com/contracts/test-odcs.json"

        # Generate ODPS with referenced ODCS URL
        odps_doc = generate_odps_from_hubcontract(
            hub_contract,
            target_version="4.1",
            original_odcs_url=original_odcs_url,
        )

        # Verify contract section exists
        self.assertIn("product", odps_doc)
        self.assertIn("contract", odps_doc["product"])
        self.assertIn("contractURL", odps_doc["product"]["contract"])
        self.assertEqual(odps_doc["product"]["contract"]["contractURL"], original_odcs_url)
        self.assertNotIn("spec", odps_doc["product"]["contract"])

    def test_generation_with_both_odcs_contract_and_url(self):
        """
        Test generation with both original_odcs_contract and original_odcs_url.

        Scenario: Generate ODPS with both parameters (contract takes precedence)
        Expected: ODPS includes product.contract.spec (contract takes precedence)
        """
        hub_contract = self.base_hub_contract.copy()
        original_odcs = {
            "id": "test-odcs-contract",
            "name": "Test ODCS Contract",
        }
        original_odcs_url = "https://example.com/contracts/test-odcs.json"

        # Generate ODPS with both parameters
        odps_doc = generate_odps_from_hubcontract(
            hub_contract,
            target_version="4.1",
            original_odcs_contract=original_odcs,
            original_odcs_url=original_odcs_url,
        )

        # Verify contract section uses spec (contract takes precedence)
        self.assertIn("product", odps_doc)
        self.assertIn("contract", odps_doc["product"])
        self.assertIn("spec", odps_doc["product"]["contract"])
        self.assertEqual(odps_doc["product"]["contract"]["spec"], original_odcs)
        self.assertNotIn("contractURL", odps_doc["product"]["contract"])

    def test_generation_without_odcs_contract_or_url(self):
        """
        Test generation without original ODCS contract or URL.

        Scenario: Generate ODPS without original_odcs_contract or original_odcs_url
        Expected: ODPS does not include product.contract section
        """
        hub_contract = self.base_hub_contract.copy()

        # Generate ODPS without ODCS
        odps_doc = generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        # Verify contract section is not present
        self.assertIn("product", odps_doc)
        self.assertNotIn("contract", odps_doc["product"])

    def test_complete_integration_generation_flow(self):
        """
        Test complete integration generation flow (end-to-end).

        Scenario: Complete HubContract → ODPS generation with all sections
        Expected: Valid ODPS document with all sections properly mapped
        """
        hub_contract = self._create_complete_hub_contract()
        original_odcs = {
            "id": "test-odcs-contract",
            "name": "Test ODCS Contract",
            "version": "3.0.2",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": "name", "type": "string"},
                ]
            },
        }

        # Generate ODPS
        odps_doc = generate_odps_from_hubcontract(
            hub_contract,
            target_version="4.1",
            original_odcs_contract=original_odcs,
        )

        # Verify complete structure
        self.assertIsInstance(odps_doc, dict)
        self.assertEqual(odps_doc["schema"], "https://opendataproducts.org/schema/v4.1")
        self.assertEqual(odps_doc["version"], "4.1")

        # Verify all sections are present
        self.assertIn("product", odps_doc)
        self.assertIn("details", odps_doc["product"])
        self.assertIn("marketplace", odps_doc["product"])
        self.assertIn("dataQuality", odps_doc["product"])
        self.assertIn("SLA", odps_doc["product"])  # From lifecycle section
        # Note: dataSchema mapping not yet implemented
        self.assertIn("contract", odps_doc["product"])
        self.assertIn("dataHolder", odps_doc)
        self.assertIn("license", odps_doc)

        # Verify data can be serialized to JSON (valid structure)
        json_str = json.dumps(odps_doc)
        self.assertIsInstance(json_str, str)
        parsed = json.loads(json_str)
        self.assertEqual(parsed["version"], "4.1")

    def test_generation_requires_info_section(self):
        """
        Test that generation requires info section (required field).

        Scenario: Generate ODPS from HubContract without info section
        Expected: ODPSExportError raised with appropriate context
        """
        hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "test-product",
            # Missing info section
        }

        with self.assertRaises(ODPSExportError) as context:
            generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        error = context.exception
        self.assertIn("info", error.message.lower())
        self.assertEqual(error.context["field_path"], "/info")

    def test_generation_requires_info_name(self):
        """
        Test that generation requires info.name (required field).

        Scenario: Generate ODPS from HubContract without info.name
        Expected: ODPSExportError raised with appropriate context
        """
        hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "test-product",
            "info": {
                # Missing name
                "description": "Test description",
            },
        }

        with self.assertRaises(ODPSExportError) as context:
            generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        error = context.exception
        self.assertIn("name", error.message.lower())
        self.assertIn("/info/name", error.context["field_path"])

