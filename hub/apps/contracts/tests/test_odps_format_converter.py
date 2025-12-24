"""
Unit tests for ODPS Format Converter (Task 2.2.3)

Tests verify:
1. YAML → JSON conversion
2. JSON → YAML conversion
3. Structure preservation (round-trip conversion)
4. Error handling for invalid inputs
5. Comment preservation (where possible)
"""
import json
from django.test import SimpleTestCase

from hub.apps.contracts.odps_errors import ODPSExportError
from hub.apps.contracts.odps_format_converter import (
    convert_yaml_to_json,
    convert_json_to_yaml,
)


class ODPSFormatConverterYAMLToJSONTest(SimpleTestCase):
    """Test YAML → JSON conversion"""

    def test_convert_yaml_to_json_with_simple_structure_succeeds(self):
        """Test converting simple YAML structure to JSON"""
        yaml_content = """
schema: https://opendataproducts.org/schema/v4.1
version: "4.1"
product:
  details:
    en:
      name: Test Product
      description: Test description
"""
        result = convert_yaml_to_json(yaml_content)

        # Verify result is valid JSON
        parsed = json.loads(result)
        self.assertEqual(parsed["schema"], "https://opendataproducts.org/schema/v4.1")
        self.assertEqual(parsed["version"], "4.1")
        self.assertEqual(parsed["product"]["details"]["en"]["name"], "Test Product")

    def test_convert_yaml_to_json_with_nested_structure_succeeds(self):
        """Test converting nested YAML structure to JSON"""
        yaml_content = """
schema: https://opendataproducts.org/schema/v4.1
version: "4.1"
product:
  details:
    en:
      name: Test Product
  marketplace:
    pricingPlans:
      declarative:
        - name: Basic Plan
          price: 10.00
          currency: USD
"""
        result = convert_yaml_to_json(yaml_content)

        # Verify result is valid JSON with nested structure
        parsed = json.loads(result)
        self.assertEqual(parsed["product"]["marketplace"]["pricingPlans"]["declarative"][0]["name"], "Basic Plan")
        self.assertEqual(parsed["product"]["marketplace"]["pricingPlans"]["declarative"][0]["price"], 10.00)

    def test_convert_yaml_to_json_with_arrays_succeeds(self):
        """Test converting YAML with arrays to JSON"""
        yaml_content = """
schema: https://opendataproducts.org/schema/v4.1
version: "4.1"
product:
  details:
    en:
      name: Test Product
      tags:
        - tag1
        - tag2
        - tag3
"""
        result = convert_yaml_to_json(yaml_content)

        # Verify arrays are preserved
        parsed = json.loads(result)
        self.assertEqual(parsed["product"]["details"]["en"]["tags"], ["tag1", "tag2", "tag3"])

    def test_convert_yaml_to_json_with_null_values_succeeds(self):
        """Test converting YAML with null values to JSON"""
        yaml_content = """
schema: https://opendataproducts.org/schema/v4.1
version: "4.1"
product:
  details:
    en:
      name: Test Product
      description: null
"""
        result = convert_yaml_to_json(yaml_content)

        # Verify null values are preserved
        parsed = json.loads(result)
        self.assertIsNone(parsed["product"]["details"]["en"]["description"])

    def test_convert_yaml_to_json_with_boolean_values_succeeds(self):
        """Test converting YAML with boolean values to JSON"""
        yaml_content = """
schema: https://opendataproducts.org/schema/v4.1
version: "4.1"
product:
  details:
    en:
      name: Test Product
      active: true
      deprecated: false
"""
        result = convert_yaml_to_json(yaml_content)

        # Verify boolean values are preserved
        parsed = json.loads(result)
        self.assertTrue(parsed["product"]["details"]["en"]["active"])
        self.assertFalse(parsed["product"]["details"]["en"]["deprecated"])

    def test_convert_yaml_to_json_with_numbers_succeeds(self):
        """Test converting YAML with numbers to JSON"""
        yaml_content = """
schema: https://opendataproducts.org/schema/v4.1
version: "4.1"
product:
  details:
    en:
      name: Test Product
      price: 99.99
      quantity: 42
"""
        result = convert_yaml_to_json(yaml_content)

        # Verify numbers are preserved
        parsed = json.loads(result)
        self.assertEqual(parsed["product"]["details"]["en"]["price"], 99.99)
        self.assertEqual(parsed["product"]["details"]["en"]["quantity"], 42)

    def test_convert_yaml_to_json_with_invalid_yaml_raises_error(self):
        """Test converting invalid YAML raises ODPSExportError"""
        invalid_yaml = """
schema: https://opendataproducts.org/schema/v4.1
version: "4.1"
product:
  details:
    en:
      name: Test Product
      invalid: [unclosed bracket
"""
        with self.assertRaises(ODPSExportError) as cm:
            convert_yaml_to_json(invalid_yaml)

        self.assertIn("YAML", cm.exception.message)
        self.assertEqual(cm.exception.error_code, ODPSExportError.ERROR_CODE_EXPORT_FAILED)

    def test_convert_yaml_to_json_with_empty_string_raises_error(self):
        """Test converting empty string raises ODPSExportError"""
        with self.assertRaises(ODPSExportError) as cm:
            convert_yaml_to_json("")

        self.assertIn("empty", cm.exception.message.lower())

    def test_convert_yaml_to_json_preserves_structure(self):
        """Test that YAML → JSON conversion preserves data structure"""
        yaml_content = """
schema: https://opendataproducts.org/schema/v4.1
version: "4.1"
product:
  details:
    en:
      name: Test Product
    fr:
      name: Produit de Test
  marketplace:
    pricingPlans:
      declarative:
        - name: Plan A
          price: 10.00
        - name: Plan B
          price: 20.00
"""
        result = convert_yaml_to_json(yaml_content)
        parsed = json.loads(result)

        # Verify complete structure is preserved
        self.assertIn("schema", parsed)
        self.assertIn("version", parsed)
        self.assertIn("product", parsed)
        self.assertIn("details", parsed["product"])
        self.assertIn("en", parsed["product"]["details"])
        self.assertIn("fr", parsed["product"]["details"])
        self.assertIn("marketplace", parsed["product"])
        self.assertEqual(len(parsed["product"]["marketplace"]["pricingPlans"]["declarative"]), 2)


class ODPSFormatConverterJSONToYAMLTest(SimpleTestCase):
    """Test JSON → YAML conversion"""

    def test_convert_json_to_yaml_with_simple_structure_succeeds(self):
        """Test converting simple JSON structure to YAML"""
        json_content = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "name": "Test Product",
                        "description": "Test description"
                    }
                }
            }
        }, indent=2)

        result = convert_json_to_yaml(json_content)

        # Verify result is valid YAML
        import yaml
        parsed = yaml.safe_load(result)
        self.assertEqual(parsed["schema"], "https://opendataproducts.org/schema/v4.1")
        self.assertEqual(parsed["version"], "4.1")
        self.assertEqual(parsed["product"]["details"]["en"]["name"], "Test Product")

    def test_convert_json_to_yaml_with_nested_structure_succeeds(self):
        """Test converting nested JSON structure to YAML"""
        json_content = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "name": "Test Product"
                    }
                },
                "marketplace": {
                    "pricingPlans": {
                        "declarative": [
                            {
                                "name": "Basic Plan",
                                "price": 10.00,
                                "currency": "USD"
                            }
                        ]
                    }
                }
            }
        }, indent=2)

        result = convert_json_to_yaml(json_content)

        # Verify result is valid YAML with nested structure
        import yaml
        parsed = yaml.safe_load(result)
        self.assertEqual(parsed["product"]["marketplace"]["pricingPlans"]["declarative"][0]["name"], "Basic Plan")
        self.assertEqual(parsed["product"]["marketplace"]["pricingPlans"]["declarative"][0]["price"], 10.00)

    def test_convert_json_to_yaml_with_arrays_succeeds(self):
        """Test converting JSON with arrays to YAML"""
        json_content = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "name": "Test Product",
                        "tags": ["tag1", "tag2", "tag3"]
                    }
                }
            }
        }, indent=2)

        result = convert_json_to_yaml(json_content)

        # Verify arrays are preserved
        import yaml
        parsed = yaml.safe_load(result)
        self.assertEqual(parsed["product"]["details"]["en"]["tags"], ["tag1", "tag2", "tag3"])

    def test_convert_json_to_yaml_with_null_values_succeeds(self):
        """Test converting JSON with null values to YAML"""
        json_content = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "name": "Test Product",
                        "description": None
                    }
                }
            }
        }, indent=2)

        result = convert_json_to_yaml(json_content)

        # Verify null values are preserved
        import yaml
        parsed = yaml.safe_load(result)
        self.assertIsNone(parsed["product"]["details"]["en"]["description"])

    def test_convert_json_to_yaml_with_boolean_values_succeeds(self):
        """Test converting JSON with boolean values to YAML"""
        json_content = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "name": "Test Product",
                        "active": True,
                        "deprecated": False
                    }
                }
            }
        }, indent=2)

        result = convert_json_to_yaml(json_content)

        # Verify boolean values are preserved
        import yaml
        parsed = yaml.safe_load(result)
        self.assertTrue(parsed["product"]["details"]["en"]["active"])
        self.assertFalse(parsed["product"]["details"]["en"]["deprecated"])

    def test_convert_json_to_yaml_with_numbers_succeeds(self):
        """Test converting JSON with numbers to YAML"""
        json_content = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "name": "Test Product",
                        "price": 99.99,
                        "quantity": 42
                    }
                }
            }
        }, indent=2)

        result = convert_json_to_yaml(json_content)

        # Verify numbers are preserved
        import yaml
        parsed = yaml.safe_load(result)
        self.assertEqual(parsed["product"]["details"]["en"]["price"], 99.99)
        self.assertEqual(parsed["product"]["details"]["en"]["quantity"], 42)

    def test_convert_json_to_yaml_with_invalid_json_raises_error(self):
        """Test converting invalid JSON raises ODPSExportError"""
        invalid_json = '{"schema": "https://opendataproducts.org/schema/v4.1", "version": "4.1", "product": {invalid}'
        with self.assertRaises(ODPSExportError) as cm:
            convert_json_to_yaml(invalid_json)

        self.assertIn("JSON", cm.exception.message)
        self.assertEqual(cm.exception.error_code, ODPSExportError.ERROR_CODE_EXPORT_FAILED)

    def test_convert_json_to_yaml_with_empty_string_raises_error(self):
        """Test converting empty string raises ODPSExportError"""
        with self.assertRaises(ODPSExportError) as cm:
            convert_json_to_yaml("")

        self.assertIn("empty", cm.exception.message.lower())

    def test_convert_json_to_yaml_preserves_structure(self):
        """Test that JSON → YAML conversion preserves data structure"""
        json_content = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "name": "Test Product"
                    },
                    "fr": {
                        "name": "Produit de Test"
                    }
                },
                "marketplace": {
                    "pricingPlans": {
                        "declarative": [
                            {
                                "name": "Plan A",
                                "price": 10.00
                            },
                            {
                                "name": "Plan B",
                                "price": 20.00
                            }
                        ]
                    }
                }
            }
        }, indent=2)

        result = convert_json_to_yaml(json_content)

        # Verify complete structure is preserved
        import yaml
        parsed = yaml.safe_load(result)
        self.assertIn("schema", parsed)
        self.assertIn("version", parsed)
        self.assertIn("product", parsed)
        self.assertIn("details", parsed["product"])
        self.assertIn("en", parsed["product"]["details"])
        self.assertIn("fr", parsed["product"]["details"])
        self.assertIn("marketplace", parsed["product"])
        self.assertEqual(len(parsed["product"]["marketplace"]["pricingPlans"]["declarative"]), 2)


class ODPSFormatConverterRoundTripTest(SimpleTestCase):
    """Test round-trip conversion (structure preservation)"""

    def test_round_trip_yaml_to_json_to_yaml_preserves_structure(self):
        """Test YAML → JSON → YAML round-trip preserves structure"""
        original_yaml = """
schema: https://opendataproducts.org/schema/v4.1
version: "4.1"
product:
  details:
    en:
      name: Test Product
      description: Test description
    fr:
      name: Produit de Test
  marketplace:
    pricingPlans:
      declarative:
        - name: Plan A
          price: 10.00
          currency: USD
        - name: Plan B
          price: 20.00
          currency: EUR
"""
        # YAML → JSON
        json_result = convert_yaml_to_json(original_yaml)
        # JSON → YAML
        yaml_result = convert_json_to_yaml(json_result)

        # Parse both and compare structure
        import yaml
        original_parsed = yaml.safe_load(original_yaml)
        result_parsed = yaml.safe_load(yaml_result)

        # Verify structure is preserved (data should be equivalent)
        self.assertEqual(original_parsed["schema"], result_parsed["schema"])
        self.assertEqual(original_parsed["version"], result_parsed["version"])
        self.assertEqual(original_parsed["product"]["details"]["en"]["name"], result_parsed["product"]["details"]["en"]["name"])
        self.assertEqual(len(original_parsed["product"]["marketplace"]["pricingPlans"]["declarative"]),
                        len(result_parsed["product"]["marketplace"]["pricingPlans"]["declarative"]))

    def test_round_trip_json_to_yaml_to_json_preserves_structure(self):
        """Test JSON → YAML → JSON round-trip preserves structure"""
        original_json = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "name": "Test Product",
                        "description": "Test description"
                    },
                    "fr": {
                        "name": "Produit de Test"
                    }
                },
                "marketplace": {
                    "pricingPlans": {
                        "declarative": [
                            {
                                "name": "Plan A",
                                "price": 10.00,
                                "currency": "USD"
                            },
                            {
                                "name": "Plan B",
                                "price": 20.00,
                                "currency": "EUR"
                            }
                        ]
                    }
                }
            }
        }, indent=2)

        # JSON → YAML
        yaml_result = convert_json_to_yaml(original_json)
        # YAML → JSON
        json_result = convert_yaml_to_json(yaml_result)

        # Parse both and compare structure
        original_parsed = json.loads(original_json)
        result_parsed = json.loads(json_result)

        # Verify structure is preserved (data should be equivalent)
        self.assertEqual(original_parsed["schema"], result_parsed["schema"])
        self.assertEqual(original_parsed["version"], result_parsed["version"])
        self.assertEqual(original_parsed["product"]["details"]["en"]["name"], result_parsed["product"]["details"]["en"]["name"])
        self.assertEqual(len(original_parsed["product"]["marketplace"]["pricingPlans"]["declarative"]),
                        len(result_parsed["product"]["marketplace"]["pricingPlans"]["declarative"]))

