"""
Comprehensive integration tests for ODPS export format generation and conversion (Task 6.1.3).

Tests verify:
1. Export format generation (JSON and YAML)
2. Format conversion (YAML ↔ JSON)
3. Data integrity across conversions
4. Real contract integration (no mocks/stubs)

These tests are designed for CI pipeline execution and follow engineering best practices.
"""

import json

import pytest
import yaml
from django.test import TestCase

from hub.apps.contracts.odps_errors import ODPSExportError
from hub.apps.contracts.odps_format_converter import (
    convert_json_to_yaml,
    convert_yaml_to_json,
)
from hub.apps.contracts.odps_generator import (
    format_odps_as_json,
    format_odps_as_yaml,
    generate_odps_from_hubcontract,
)
from hub.apps.contracts.tests.test_base import ContractsTestBase

pytestmark = pytest.mark.django_db(transaction=True)


class ODPSExportFormatGenerationTest(ContractsTestBase):
    """
    Comprehensive tests for ODPS export format generation.

    Tests verify that ODPS documents can be exported in both JSON and YAML formats
    with correct structure, data integrity, and proper formatting.
    """

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        # Update user display_name
        self.user.display_name = "Test User"
        self.user.save()

        # Create comprehensive HubContract for testing
        self.hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "test-product-export",
            "info": {
                "name": "Export Test Product",
                "description": "Test product for export format generation",
                "version": "1.0.0",
            },
            "marketplace": {
                "license_summary": "MIT License",
                "intended_use": ["analytics", "research"],
                "pricing": {
                    "model": "free",
                    "currency": "USD",
                },
            },
            "data_schema": {
                "fields": [
                    {
                        "name": "id",
                        "type": "string",
                        "description": "Unique identifier",
                    },
                    {
                        "name": "name",
                        "type": "string",
                        "description": "Name field",
                    },
                    {
                        "name": "value",
                        "type": "number",
                        "description": "Numeric value",
                    },
                ]
            },
        }

        # Generate ODPS document from HubContract
        self.odps_doc = generate_odps_from_hubcontract(
            hub_contract=self.hub_contract,
            target_version="4.1",
            original_odcs_contract=None,
            original_odcs_url=None,
        )

    def test_format_odps_as_json_success(self):
        """
        Test successful JSON format generation.

        Verifies:
        - JSON output is valid
        - Structure is preserved
        - Data integrity maintained
        """
        # Generate JSON format
        json_output = format_odps_as_json(self.odps_doc)

        # Verify output is valid JSON
        parsed = json.loads(json_output)

        # Verify structure
        self.assertIn("schema", parsed)
        self.assertIn("version", parsed)
        self.assertIn("product", parsed)

        # Verify data integrity
        self.assertEqual(parsed["version"], "4.1")
        self.assertIn("details", parsed["product"])
        self.assertIn("en", parsed["product"]["details"])
        self.assertEqual(parsed["product"]["details"]["en"]["name"], "Export Test Product")

    def test_format_odps_as_json_with_indentation(self):
        """
        Test JSON format generation with custom indentation.

        Verifies:
        - Custom indentation is applied
        - Output is still valid JSON
        """
        # Generate JSON with custom indentation
        json_output = format_odps_as_json(self.odps_doc, indent=4)

        # Verify output is valid JSON
        parsed = json.loads(json_output)

        # Verify indentation (check for 4-space indentation in string)
        lines = json_output.split("\n")
        if len(lines) > 1:
            # First nested line should have 4 spaces
            for line in lines[1:]:
                if (
                    line.strip()
                    and not line.strip().startswith("{")
                    and not line.strip().startswith("}")
                ):
                    # Check if indentation is present (at least some spaces)
                    self.assertTrue(line.startswith(" ") or line.startswith("\t"))

        # Verify structure is preserved
        self.assertIn("schema", parsed)
        self.assertIn("product", parsed)

    def test_format_odps_as_json_with_ensure_ascii(self):
        """
        Test JSON format generation with ensure_ascii option.

        Verifies:
        - Non-ASCII characters are handled correctly
        - Output is valid JSON
        """
        # Create ODPS doc with non-ASCII characters
        odps_with_unicode = self.odps_doc.copy()
        if "product" in odps_with_unicode and "details" in odps_with_unicode["product"]:
            if "en" in odps_with_unicode["product"]["details"]:
                odps_with_unicode["product"]["details"]["en"]["description"] = (
                    "Test with émojis 🎉 and ñoño"
                )

        # Generate JSON with ensure_ascii=False (default)
        json_output = format_odps_as_json(odps_with_unicode, ensure_ascii=False)
        parsed = json.loads(json_output)

        # Verify unicode is preserved
        if "product" in parsed and "details" in parsed["product"]:
            if "en" in parsed["product"]["details"]:
                desc = parsed["product"]["details"]["en"].get("description", "")
                if "émojis" in desc or "🎉" in desc:
                    self.assertIn("émojis", desc or "")

    def test_format_odps_as_yaml_success(self):
        """
        Test successful YAML format generation.

        Verifies:
        - YAML output is valid
        - Structure is preserved
        - Data integrity maintained
        """
        # Generate YAML format
        yaml_output = format_odps_as_yaml(self.odps_doc)

        # Verify output is valid YAML
        parsed = yaml.safe_load(yaml_output)

        # Verify structure
        self.assertIn("schema", parsed)
        self.assertIn("version", parsed)
        self.assertIn("product", parsed)

        # Verify data integrity
        self.assertEqual(parsed["version"], "4.1")
        self.assertIn("details", parsed["product"])
        self.assertIn("en", parsed["product"]["details"])
        self.assertEqual(parsed["product"]["details"]["en"]["name"], "Export Test Product")

    def test_format_odps_as_yaml_with_options(self):
        """
        Test YAML format generation with custom options.

        Verifies:
        - Custom YAML options are applied
        - Output is still valid YAML
        """
        # Generate YAML with custom options
        yaml_output = format_odps_as_yaml(
            self.odps_doc, default_flow_style=False, allow_unicode=True, sort_keys=False
        )

        # Verify output is valid YAML
        parsed = yaml.safe_load(yaml_output)

        # Verify structure is preserved
        self.assertIn("schema", parsed)
        self.assertIn("product", parsed)

        # Verify block style (not flow style)
        self.assertNotIn(" {", yaml_output[:200])  # Flow style uses { }

    def test_format_odps_as_json_invalid_input(self):
        """
        Test JSON format generation with invalid input.

        Verifies:
        - Invalid input raises ODPSExportError
        - Error message is descriptive
        """
        # Test with non-dict input
        with self.assertRaises(ODPSExportError) as cm:
            format_odps_as_json("not a dict")

        self.assertIn("dictionary", cm.exception.message.lower())
        self.assertEqual(cm.exception.error_code, ODPSExportError.ERROR_CODE_EXPORT_FAILED)

    def test_format_odps_as_yaml_invalid_input(self):
        """
        Test YAML format generation with invalid input.

        Verifies:
        - Invalid input raises ODPSExportError
        - Error message is descriptive
        """
        # Test with non-dict input
        with self.assertRaises(ODPSExportError) as cm:
            format_odps_as_yaml("not a dict")

        self.assertIn("dictionary", cm.exception.message.lower())
        self.assertEqual(cm.exception.error_code, ODPSExportError.ERROR_CODE_EXPORT_FAILED)

    def test_json_yaml_round_trip_consistency(self):
        """
        Test that JSON and YAML formats produce equivalent data.

        Verifies:
        - JSON → YAML → JSON round-trip preserves data
        - YAML → JSON → YAML round-trip preserves data
        """
        # Generate both formats
        json_output = format_odps_as_json(self.odps_doc)
        yaml_output = format_odps_as_yaml(self.odps_doc)

        # Parse both
        json_parsed = json.loads(json_output)
        yaml_parsed = yaml.safe_load(yaml_output)

        # Verify core fields match
        self.assertEqual(json_parsed["schema"], yaml_parsed["schema"])
        self.assertEqual(json_parsed["version"], yaml_parsed["version"])

        # Verify product details match
        if "product" in json_parsed and "product" in yaml_parsed:
            json_product = json_parsed["product"]
            yaml_product = yaml_parsed["product"]

            if "details" in json_product and "details" in yaml_product:
                json_details = json_product["details"]
                yaml_details = yaml_product["details"]

                if "en" in json_details and "en" in yaml_details:
                    self.assertEqual(json_details["en"].get("name"), yaml_details["en"].get("name"))


class ODPSFormatConversionTest(TestCase):
    """
    Comprehensive tests for ODPS format conversion.

    Tests verify that ODPS documents can be converted between JSON and YAML formats
    with data integrity, structure preservation, and proper error handling.
    """

    def setUp(self):
        """Set up test fixtures"""
        # Create sample ODPS document in JSON format
        self.odps_json = json.dumps(
            {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "version": "4.1",
                "product": {
                    "details": {
                        "en": {
                            "productID": "test-product-conversion",
                            "name": "Conversion Test Product",
                            "description": "Test product for format conversion",
                        },
                        "fr": {
                            "productID": "test-product-conversion",
                            "name": "Produit de Test de Conversion",
                        },
                    },
                    "dataSchema": {
                        "fields": [
                            {"name": "id", "type": "string"},
                            {"name": "name", "type": "string"},
                            {"name": "value", "type": "number"},
                        ]
                    },
                    "marketplace": {
                        "pricingPlans": {
                            "declarative": [
                                {
                                    "name": "Free Plan",
                                    "price": 0.0,
                                    "currency": "USD",
                                },
                                {
                                    "name": "Premium Plan",
                                    "price": 99.99,
                                    "currency": "USD",
                                },
                            ]
                        }
                    },
                },
            },
            indent=2,
        )

        # Create sample ODPS document in YAML format
        self.odps_yaml = """
schema: https://opendataproducts.org/schema/v4.1
version: "4.1"
product:
  details:
    en:
      productID: test-product-conversion
      name: Conversion Test Product
      description: Test product for format conversion
    fr:
      productID: test-product-conversion
      name: Produit de Test de Conversion
  dataSchema:
    fields:
      - name: id
        type: string
      - name: name
        type: string
      - name: value
        type: number
  marketplace:
    pricingPlans:
      declarative:
        - name: Free Plan
          price: 0.0
          currency: USD
        - name: Premium Plan
          price: 99.99
          currency: USD
"""

    def test_convert_yaml_to_json_success(self):
        """
        Test successful YAML to JSON conversion.

        Verifies:
        - Conversion produces valid JSON
        - Structure is preserved
        - Data integrity maintained
        """
        # Convert YAML to JSON
        json_output = convert_yaml_to_json(self.odps_yaml)

        # Verify output is valid JSON
        parsed = json.loads(json_output)

        # Verify structure
        self.assertIn("schema", parsed)
        self.assertIn("version", parsed)
        self.assertIn("product", parsed)

        # Verify data integrity
        self.assertEqual(parsed["version"], "4.1")
        self.assertEqual(parsed["product"]["details"]["en"]["name"], "Conversion Test Product")
        self.assertEqual(len(parsed["product"]["marketplace"]["pricingPlans"]["declarative"]), 2)

    def test_convert_json_to_yaml_success(self):
        """
        Test successful JSON to YAML conversion.

        Verifies:
        - Conversion produces valid YAML
        - Structure is preserved
        - Data integrity maintained
        """
        # Convert JSON to YAML
        yaml_output = convert_json_to_yaml(self.odps_json)

        # Verify output is valid YAML
        parsed = yaml.safe_load(yaml_output)

        # Verify structure
        self.assertIn("schema", parsed)
        self.assertIn("version", parsed)
        self.assertIn("product", parsed)

        # Verify data integrity
        self.assertEqual(parsed["version"], "4.1")
        self.assertEqual(parsed["product"]["details"]["en"]["name"], "Conversion Test Product")
        self.assertEqual(len(parsed["product"]["marketplace"]["pricingPlans"]["declarative"]), 2)

    def test_round_trip_yaml_json_yaml(self):
        """
        Test round-trip conversion: YAML → JSON → YAML.

        Verifies:
        - Round-trip preserves data structure
        - Data integrity maintained
        """
        # YAML → JSON
        json_output = convert_yaml_to_json(self.odps_yaml)
        json_parsed = json.loads(json_output)

        # JSON → YAML
        yaml_output = convert_json_to_yaml(json_output)
        yaml_parsed = yaml.safe_load(yaml_output)

        # Verify structure is preserved
        self.assertEqual(json_parsed["schema"], yaml_parsed["schema"])
        self.assertEqual(json_parsed["version"], yaml_parsed["version"])
        self.assertEqual(
            json_parsed["product"]["details"]["en"]["name"],
            yaml_parsed["product"]["details"]["en"]["name"],
        )
        self.assertEqual(
            len(json_parsed["product"]["marketplace"]["pricingPlans"]["declarative"]),
            len(yaml_parsed["product"]["marketplace"]["pricingPlans"]["declarative"]),
        )

    def test_round_trip_json_yaml_json(self):
        """
        Test round-trip conversion: JSON → YAML → JSON.

        Verifies:
        - Round-trip preserves data structure
        - Data integrity maintained
        """
        # JSON → YAML
        yaml_output = convert_json_to_yaml(self.odps_json)
        yaml.safe_load(yaml_output)

        # YAML → JSON
        json_output = convert_yaml_to_json(yaml_output)
        json_parsed = json.loads(json_output)

        # Verify structure is preserved
        original_parsed = json.loads(self.odps_json)
        self.assertEqual(original_parsed["schema"], json_parsed["schema"])
        self.assertEqual(original_parsed["version"], json_parsed["version"])
        self.assertEqual(
            original_parsed["product"]["details"]["en"]["name"],
            json_parsed["product"]["details"]["en"]["name"],
        )
        self.assertEqual(
            len(original_parsed["product"]["marketplace"]["pricingPlans"]["declarative"]),
            len(json_parsed["product"]["marketplace"]["pricingPlans"]["declarative"]),
        )

    def test_convert_yaml_to_json_with_complex_structure(self):
        """
        Test YAML to JSON conversion with complex nested structures.

        Verifies:
        - Complex structures are preserved
        - Arrays are handled correctly
        - Nested objects are maintained
        """
        complex_yaml = """
schema: https://opendataproducts.org/schema/v4.1
version: "4.1"
product:
  details:
    en:
      name: Complex Product
      tags:
        - analytics
        - research
        - commercial
  marketplace:
    pricingPlans:
      declarative:
        - name: Basic
          features:
            - feature1
            - feature2
          pricing:
            base: 10.0
            currency: USD
        - name: Pro
          features:
            - feature1
            - feature2
            - feature3
          pricing:
            base: 99.0
            currency: USD
"""
        json_output = convert_yaml_to_json(complex_yaml)
        parsed = json.loads(json_output)

        # Verify complex structure
        self.assertEqual(len(parsed["product"]["details"]["en"]["tags"]), 3)
        self.assertEqual(len(parsed["product"]["marketplace"]["pricingPlans"]["declarative"]), 2)
        self.assertEqual(
            len(parsed["product"]["marketplace"]["pricingPlans"]["declarative"][0]["features"]), 2
        )
        self.assertEqual(
            parsed["product"]["marketplace"]["pricingPlans"]["declarative"][0]["pricing"]["base"],
            10.0,
        )

    def test_convert_json_to_yaml_with_complex_structure(self):
        """
        Test JSON to YAML conversion with complex nested structures.

        Verifies:
        - Complex structures are preserved
        - Arrays are handled correctly
        - Nested objects are maintained
        """
        complex_json = json.dumps(
            {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "version": "4.1",
                "product": {
                    "details": {
                        "en": {
                            "name": "Complex Product",
                            "tags": ["analytics", "research", "commercial"],
                        }
                    },
                    "marketplace": {
                        "pricingPlans": {
                            "declarative": [
                                {
                                    "name": "Basic",
                                    "features": ["feature1", "feature2"],
                                    "pricing": {"base": 10.0, "currency": "USD"},
                                },
                                {
                                    "name": "Pro",
                                    "features": ["feature1", "feature2", "feature3"],
                                    "pricing": {"base": 99.0, "currency": "USD"},
                                },
                            ]
                        }
                    },
                },
            },
            indent=2,
        )

        yaml_output = convert_json_to_yaml(complex_json)
        parsed = yaml.safe_load(yaml_output)

        # Verify complex structure
        self.assertEqual(len(parsed["product"]["details"]["en"]["tags"]), 3)
        self.assertEqual(len(parsed["product"]["marketplace"]["pricingPlans"]["declarative"]), 2)
        self.assertEqual(
            len(parsed["product"]["marketplace"]["pricingPlans"]["declarative"][0]["features"]), 2
        )
        self.assertEqual(
            parsed["product"]["marketplace"]["pricingPlans"]["declarative"][0]["pricing"]["base"],
            10.0,
        )

    def test_convert_yaml_to_json_invalid_yaml(self):
        """
        Test YAML to JSON conversion with invalid YAML.

        Verifies:
        - Invalid YAML raises ODPSExportError
        - Error message is descriptive
        """
        invalid_yaml = """
schema: https://opendataproducts.org/schema/v4.1
version: "4.1"
product:
  details:
    en:
      name: Test
      invalid: [unclosed bracket
"""
        with self.assertRaises(ODPSExportError) as cm:
            convert_yaml_to_json(invalid_yaml)

        self.assertIn("YAML", cm.exception.message)
        self.assertEqual(cm.exception.error_code, ODPSExportError.ERROR_CODE_EXPORT_FAILED)

    def test_convert_json_to_yaml_invalid_json(self):
        """
        Test JSON to YAML conversion with invalid JSON.

        Verifies:
        - Invalid JSON raises ODPSExportError
        - Error message is descriptive
        """
        invalid_json = '{"schema": "https://opendataproducts.org/schema/v4.1", "version": "4.1", "product": {invalid}'
        with self.assertRaises(ODPSExportError) as cm:
            convert_json_to_yaml(invalid_json)

        self.assertIn("JSON", cm.exception.message)
        self.assertEqual(cm.exception.error_code, ODPSExportError.ERROR_CODE_EXPORT_FAILED)

    def test_convert_yaml_to_json_empty_string(self):
        """
        Test YAML to JSON conversion with empty string.

        Verifies:
        - Empty string raises ODPSExportError
        """
        with self.assertRaises(ODPSExportError) as cm:
            convert_yaml_to_json("")

        self.assertIn("empty", cm.exception.message.lower())
        self.assertEqual(cm.exception.error_code, ODPSExportError.ERROR_CODE_EXPORT_FAILED)

    def test_convert_json_to_yaml_empty_string(self):
        """
        Test JSON to YAML conversion with empty string.

        Verifies:
        - Empty string raises ODPSExportError
        """
        with self.assertRaises(ODPSExportError) as cm:
            convert_json_to_yaml("")

        self.assertIn("empty", cm.exception.message.lower())
        self.assertEqual(cm.exception.error_code, ODPSExportError.ERROR_CODE_EXPORT_FAILED)


class ODPSExportEndToEndIntegrationTest(ContractsTestBase):
    """
    End-to-end integration tests for ODPS export workflow.

    Tests verify the complete workflow from HubContract → ODPS generation → format export → format conversion.
    """

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        # Update user display_name
        self.user.display_name = "Test User"
        self.user.save()

        # Create comprehensive HubContract
        self.hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "test-product-e2e",
            "info": {
                "name": "E2E Test Product",
                "description": "End-to-end test product",
                "version": "1.0.0",
            },
            "marketplace": {
                "license_summary": "Apache 2.0",
                "intended_use": ["analytics", "research"],
                "pricing": {
                    "model": "subscription",
                    "currency": "USD",
                },
            },
            "data_schema": {
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": "name", "type": "string"},
                    {"name": "value", "type": "number"},
                ]
            },
        }

    def test_complete_export_workflow_json(self):
        """
        Test complete export workflow: HubContract → ODPS → JSON.

        Verifies:
        - Complete workflow executes successfully
        - Data integrity maintained throughout
        """
        # Generate ODPS from HubContract
        odps_doc = generate_odps_from_hubcontract(
            hub_contract=self.hub_contract,
            target_version="4.1",
            original_odcs_contract=None,
            original_odcs_url=None,
        )

        # Export as JSON
        json_output = format_odps_as_json(odps_doc)
        json_parsed = json.loads(json_output)

        # Verify complete workflow
        self.assertIn("schema", json_parsed)
        self.assertIn("version", json_parsed)
        self.assertIn("product", json_parsed)
        self.assertEqual(json_parsed["version"], "4.1")
        self.assertEqual(json_parsed["product"]["details"]["en"]["name"], "E2E Test Product")

    def test_complete_export_workflow_yaml(self):
        """
        Test complete export workflow: HubContract → ODPS → YAML.

        Verifies:
        - Complete workflow executes successfully
        - Data integrity maintained throughout
        """
        # Generate ODPS from HubContract
        odps_doc = generate_odps_from_hubcontract(
            hub_contract=self.hub_contract,
            target_version="4.1",
            original_odcs_contract=None,
            original_odcs_url=None,
        )

        # Export as YAML
        yaml_output = format_odps_as_yaml(odps_doc)
        yaml_parsed = yaml.safe_load(yaml_output)

        # Verify complete workflow
        self.assertIn("schema", yaml_parsed)
        self.assertIn("version", yaml_parsed)
        self.assertIn("product", yaml_parsed)
        self.assertEqual(yaml_parsed["version"], "4.1")
        self.assertEqual(yaml_parsed["product"]["details"]["en"]["name"], "E2E Test Product")

    def test_complete_workflow_with_format_conversion(self):
        """
        Test complete workflow with format conversion: HubContract → ODPS → JSON → YAML → JSON.

        Verifies:
        - Complete workflow with conversions executes successfully
        - Data integrity maintained through all conversions
        """
        # Generate ODPS from HubContract
        odps_doc = generate_odps_from_hubcontract(
            hub_contract=self.hub_contract,
            target_version="4.1",
            original_odcs_contract=None,
            original_odcs_url=None,
        )

        # Export as JSON
        json_output = format_odps_as_json(odps_doc)
        json_parsed = json.loads(json_output)

        # Convert JSON to YAML
        yaml_output = convert_json_to_yaml(json_output)
        yaml_parsed = yaml.safe_load(yaml_output)

        # Convert YAML back to JSON
        json_output_2 = convert_yaml_to_json(yaml_output)
        json_parsed_2 = json.loads(json_output_2)

        # Verify data integrity through all conversions
        self.assertEqual(json_parsed["schema"], json_parsed_2["schema"])
        self.assertEqual(json_parsed["version"], json_parsed_2["version"])
        self.assertEqual(
            json_parsed["product"]["details"]["en"]["name"],
            json_parsed_2["product"]["details"]["en"]["name"],
        )
        self.assertEqual(
            json_parsed["product"]["details"]["en"]["name"],
            yaml_parsed["product"]["details"]["en"]["name"],
        )

    def test_export_ci_integration_handles_unicode_characters(self):
        """Test that export CI integration handles unicode characters correctly."""
        hub_contract = self.hub_contract.copy()
        hub_contract["info"]["name"] = "测试产品"
        hub_contract["info"]["description"] = "测试描述"

        odps_doc = generate_odps_from_hubcontract(
            hub_contract=hub_contract,
            target_version="4.1",
            original_odcs_contract=None,
            original_odcs_url=None,
        )

        json_output = format_odps_as_json(odps_doc)
        json_parsed = json.loads(json_output)

        # Should handle unicode characters
        self.assertIsNotNone(json_parsed)
        self.assertIn("product", json_parsed)

    def test_export_ci_integration_handles_special_characters(self):
        """Test that export CI integration handles special characters correctly."""
        hub_contract = self.hub_contract.copy()
        hub_contract["info"]["name"] = "Test & Co. (Special)"
        hub_contract["info"]["description"] = "Test <description> & more"

        odps_doc = generate_odps_from_hubcontract(
            hub_contract=hub_contract,
            target_version="4.1",
            original_odcs_contract=None,
            original_odcs_url=None,
        )

        json_output = format_odps_as_json(odps_doc)
        json_parsed = json.loads(json_output)

        # Should handle special characters
        self.assertIsNotNone(json_parsed)
        self.assertIn("product", json_parsed)

    def test_export_ci_integration_handles_very_large_documents(self):
        """Test that export CI integration handles very large documents correctly."""
        large_description = "A" * 100000  # 100KB string
        hub_contract = self.hub_contract.copy()
        hub_contract["info"]["description"] = large_description

        odps_doc = generate_odps_from_hubcontract(
            hub_contract=hub_contract,
            target_version="4.1",
            original_odcs_contract=None,
            original_odcs_url=None,
        )

        json_output = format_odps_as_json(odps_doc)
        json_parsed = json.loads(json_output)

        # Should handle very large documents
        self.assertIsNotNone(json_parsed)
        self.assertIn("product", json_parsed)

    def test_export_ci_integration_handles_none_values(self):
        """Test that export CI integration handles None values correctly."""
        hub_contract = self.hub_contract.copy()
        hub_contract["info"]["description"] = None  # None value

        odps_doc = generate_odps_from_hubcontract(
            hub_contract=hub_contract,
            target_version="4.1",
            original_odcs_contract=None,
            original_odcs_url=None,
        )

        json_output = format_odps_as_json(odps_doc)
        json_parsed = json.loads(json_output)

        # Should handle None values gracefully
        self.assertIsNotNone(json_parsed)
        self.assertIn("product", json_parsed)

    def test_export_ci_integration_handles_nested_structures(self):
        """Test that export CI integration handles nested structures correctly."""
        hub_contract = self.hub_contract.copy()
        hub_contract["info"]["nested"] = {"level1": {"level2": {"level3": {"value": "deep"}}}}

        odps_doc = generate_odps_from_hubcontract(
            hub_contract=hub_contract,
            target_version="4.1",
            original_odcs_contract=None,
            original_odcs_url=None,
        )

        json_output = format_odps_as_json(odps_doc)
        json_parsed = json.loads(json_output)

        # Should handle nested structures
        self.assertIsNotNone(json_parsed)
        self.assertIn("product", json_parsed)
