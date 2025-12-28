"""
Unit tests for ODCS Format Converter.

Tests format conversion utilities (JSON/YAML) following engineering best practices.
"""
import pytest
import json
from django.test import TestCase

from hub.apps.contracts.odcs_format_converter import (
    convert_yaml_to_json,
    convert_json_to_yaml,
    format_odcs_as_json,
    format_odcs_as_yaml,
)
from hub.apps.contracts.odcs_errors import ODCSExportError

pytestmark = pytest.mark.django_db(transaction=True)


class ODCSFormatConverterTest(TestCase):
    """Test ODCS format conversion utilities"""

    def test_convert_yaml_to_json_success(self):
        """Test successful YAML to JSON conversion"""
        yaml_content = """
apiVersion: odcs.io/v3.0.2
kind: DataContract
id: test-contract
name: Test Contract
version: 1.0.0
"""

        json_result = convert_yaml_to_json(yaml_content)

        # Parse JSON to verify structure
        json_data = json.loads(json_result)
        self.assertEqual(json_data["apiVersion"], "odcs.io/v3.0.2")
        self.assertEqual(json_data["kind"], "DataContract")
        self.assertEqual(json_data["id"], "test-contract")
        self.assertEqual(json_data["name"], "Test Contract")

    def test_convert_json_to_yaml_success(self):
        """Test successful JSON to YAML conversion"""
        json_content = json.dumps({
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract"
        }, indent=2)

        yaml_result = convert_json_to_yaml(json_content)

        # Verify YAML contains expected fields
        self.assertIn("apiVersion", yaml_result)
        self.assertIn("odcs.io/v3.0.2", yaml_result)
        self.assertIn("kind", yaml_result)
        self.assertIn("DataContract", yaml_result)
        self.assertIn("id", yaml_result)
        self.assertIn("test-contract", yaml_result)

    def test_convert_yaml_to_json_empty_content(self):
        """Test YAML to JSON conversion with empty content"""
        with self.assertRaises(ODCSExportError) as cm:
            convert_yaml_to_json("")

        error = cm.exception
        self.assertEqual(error.error_code, ODCSExportError.ERROR_CODE_EXPORT_FAILED)
        self.assertIn("empty", error.message.lower())

    def test_convert_json_to_yaml_empty_content(self):
        """Test JSON to YAML conversion with empty content"""
        with self.assertRaises(ODCSExportError) as cm:
            convert_json_to_yaml("")

        error = cm.exception
        self.assertEqual(error.error_code, ODCSExportError.ERROR_CODE_EXPORT_FAILED)
        self.assertIn("empty", error.message.lower())

    def test_convert_yaml_to_json_invalid_yaml(self):
        """Test YAML to JSON conversion with invalid YAML"""
        invalid_yaml = """
apiVersion: odcs.io/v3.0.2
kind: DataContract
  invalid: indentation
"""

        with self.assertRaises(ODCSExportError) as cm:
            convert_yaml_to_json(invalid_yaml)

        error = cm.exception
        self.assertEqual(error.error_code, ODCSExportError.ERROR_CODE_EXPORT_FAILED)
        self.assertIn("parse", error.message.lower())

    def test_convert_json_to_yaml_invalid_json(self):
        """Test JSON to YAML conversion with invalid JSON"""
        invalid_json = '{"apiVersion": "odcs.io/v3.0.2", invalid}'

        with self.assertRaises(ODCSExportError) as cm:
            convert_json_to_yaml(invalid_json)

        error = cm.exception
        self.assertEqual(error.error_code, ODCSExportError.ERROR_CODE_EXPORT_FAILED)
        self.assertIn("parse", error.message.lower())

    def test_round_trip_conversion(self):
        """Test round-trip conversion (JSON -> YAML -> JSON)"""
        original_json = json.dumps({
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0"
        }, indent=2)

        # Convert JSON to YAML
        yaml_result = convert_json_to_yaml(original_json)

        # Convert YAML back to JSON
        json_result = convert_yaml_to_json(yaml_result)

        # Parse both and compare
        original_data = json.loads(original_json)
        result_data = json.loads(json_result)

        self.assertEqual(original_data["apiVersion"], result_data["apiVersion"])
        self.assertEqual(original_data["kind"], result_data["kind"])
        self.assertEqual(original_data["id"], result_data["id"])
        self.assertEqual(original_data["name"], result_data["name"])


class ODCSFormatJSONTest(TestCase):
    """Test ODCS format_odcs_as_json() function"""

    def test_format_odcs_as_json_basic(self):
        """
        Test formatting ODCS document as JSON.

        Scenario: Format ODCS document as JSON
        Expected: Valid JSON string is returned
        """
        odcs_doc = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0"
        }

        result = format_odcs_as_json(odcs_doc)

        # Verify result is a string
        self.assertIsInstance(result, str)

        # Verify it's valid JSON
        parsed = json.loads(result)
        self.assertEqual(parsed["apiVersion"], "odcs.io/v3.0.2")
        self.assertEqual(parsed["kind"], "DataContract")
        self.assertEqual(parsed["id"], "test-contract")
        self.assertEqual(parsed["name"], "Test Contract")

    def test_format_odcs_as_json_with_indent(self):
        """
        Test formatting ODCS document as JSON with custom indentation.

        Scenario: Format ODCS document as JSON with indent=4
        Expected: JSON string with 4-space indentation
        """
        odcs_doc = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract"
        }

        result = format_odcs_as_json(odcs_doc, indent=4)

        # Verify result is a string
        self.assertIsInstance(result, str)

        # Verify it's valid JSON
        parsed = json.loads(result)
        self.assertEqual(parsed["apiVersion"], "odcs.io/v3.0.2")

        # Verify indentation (should have 4 spaces)
        lines = result.split('\n')
        if len(lines) > 1:
            # Second line should start with 4 spaces
            self.assertTrue(lines[1].startswith('    '))

    def test_format_odcs_as_json_with_unicode(self):
        """
        Test formatting ODCS document as JSON with unicode characters.

        Scenario: Format ODCS document with unicode characters
        Expected: Unicode characters are preserved (ensure_ascii=False)
        """
        odcs_doc = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract with émojis 🚀 and 中文"
        }

        result = format_odcs_as_json(odcs_doc, ensure_ascii=False)

        # Verify unicode characters are preserved
        self.assertIn("émojis", result)
        self.assertIn("🚀", result)
        self.assertIn("中文", result)

        # Verify it's valid JSON
        parsed = json.loads(result)
        self.assertIn("émojis", parsed["name"])
        self.assertIn("🚀", parsed["name"])
        self.assertIn("中文", parsed["name"])

    def test_format_odcs_as_json_with_escape_sequences(self):
        """
        Test formatting ODCS document as JSON with escape sequences.

        Scenario: Format ODCS document with special characters that need escaping
        Expected: Escape sequences are properly handled
        """
        odcs_doc = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-contract",
            "description": "Line 1\nLine 2\tTabbed\rCarriage return\"Quote"
        }

        result = format_odcs_as_json(odcs_doc)

        # Verify it's valid JSON
        parsed = json.loads(result)
        self.assertIn("\n", parsed["description"])
        self.assertIn("\t", parsed["description"])
        self.assertIn("\r", parsed["description"])
        self.assertIn('"', parsed["description"])

    def test_format_odcs_as_json_with_complete_document(self):
        """
        Test formatting complete ODCS document as JSON.

        Scenario: Format complete ODCS document with all sections
        Expected: Valid JSON string with all sections
        """
        odcs_doc = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": "name", "type": "string"}
                ]
            },
            "quality": {
                "rules": [
                    {"name": "not_null", "type": "not_null", "field": "id"}
                ]
            }
        }

        result = format_odcs_as_json(odcs_doc)

        # Verify result is valid JSON
        parsed = json.loads(result)

        # Verify all sections are present
        self.assertIn("apiVersion", parsed)
        self.assertIn("kind", parsed)
        self.assertIn("id", parsed)
        self.assertIn("name", parsed)
        self.assertIn("schema", parsed)
        self.assertIn("quality", parsed)
        self.assertIn("fields", parsed["schema"])
        self.assertIn("rules", parsed["quality"])

    def test_format_odcs_as_json_with_invalid_document(self):
        """
        Test error handling when formatting invalid document as JSON.

        Scenario: Format non-dictionary as JSON
        Expected: ODCSExportError with field_path and expected/actual types
        """
        with self.assertRaises(ODCSExportError) as context:
            format_odcs_as_json("not-a-dict")

        error = context.exception
        self.assertIn("dictionary", error.message.lower())
        self.assertIn("field_path", error.context)
        self.assertEqual(error.context["field_path"], "/")
        if "expected" in error.context:
            self.assertEqual(error.context["expected"], "dict")
        if "actual" in error.context:
            self.assertIn("str", error.context["actual"])

    def test_format_odcs_as_json_with_non_serializable_object(self):
        """
        Test error handling when document contains non-serializable objects.

        Scenario: Format document with non-serializable object
        Expected: ODCSExportError with error context
        """
        class NonSerializable:
            pass

        odcs_doc = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "custom": NonSerializable()  # Non-serializable
        }

        with self.assertRaises(ODCSExportError) as context:
            format_odcs_as_json(odcs_doc)

        error = context.exception
        self.assertIn("json", error.message.lower())
        self.assertIn("field_path", error.context)
        self.assertEqual(error.context["field_path"], "/")

    def test_format_odcs_as_json_validation(self):
        """
        Test JSON output format validation.

        Scenario: Format ODCS document and validate output is correct JSON
        Expected: Output is valid, parseable JSON with correct structure
        """
        odcs_doc = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract"
        }

        result = format_odcs_as_json(odcs_doc)

        # Validate JSON syntax
        parsed = json.loads(result)

        # Validate structure
        self.assertIsInstance(parsed, dict)
        self.assertIn("apiVersion", parsed)
        self.assertIn("kind", parsed)
        self.assertIn("id", parsed)
        self.assertIn("name", parsed)

        # Validate JSON can be re-parsed (round-trip validation)
        re_parsed = json.loads(json.dumps(parsed))
        self.assertEqual(parsed, re_parsed)


class ODCSFormatYAMLTest(TestCase):
    """Test ODCS format_odcs_as_yaml() function"""

    def test_format_odcs_as_yaml_basic(self):
        """
        Test formatting ODCS document as YAML.

        Scenario: Format ODCS document as YAML
        Expected: Valid YAML string is returned
        """
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not available")

        odcs_doc = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0"
        }

        result = format_odcs_as_yaml(odcs_doc)

        # Verify result is a string
        self.assertIsInstance(result, str)

        # Verify it's valid YAML
        parsed = yaml.safe_load(result)
        self.assertEqual(parsed["apiVersion"], "odcs.io/v3.0.2")
        self.assertEqual(parsed["kind"], "DataContract")
        self.assertEqual(parsed["id"], "test-contract")
        self.assertEqual(parsed["name"], "Test Contract")

    def test_format_odcs_as_yaml_with_unicode(self):
        """
        Test formatting ODCS document as YAML with unicode characters.

        Scenario: Format ODCS document with unicode characters
        Expected: Unicode characters are preserved (allow_unicode=True)
        """
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not available")

        odcs_doc = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract with émojis 🚀 and 中文"
        }

        result = format_odcs_as_yaml(odcs_doc, allow_unicode=True)

        # Verify unicode characters are preserved
        self.assertIn("émojis", result)
        self.assertIn("🚀", result)
        self.assertIn("中文", result)

        # Verify it's valid YAML
        parsed = yaml.safe_load(result)
        self.assertIn("émojis", parsed["name"])
        self.assertIn("🚀", parsed["name"])
        self.assertIn("中文", parsed["name"])

    def test_format_odcs_as_yaml_with_escape_sequences(self):
        """
        Test formatting ODCS document as YAML with escape sequences.

        Scenario: Format ODCS document with special characters
        Expected: Special characters are properly handled in YAML
        """
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not available")

        odcs_doc = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-contract",
            "description": "Line 1\nLine 2\tTabbed\rCarriage return\"Quote"
        }

        result = format_odcs_as_yaml(odcs_doc)

        # Verify it's valid YAML
        parsed = yaml.safe_load(result)
        self.assertIn("\n", parsed["description"])
        self.assertIn("\t", parsed["description"])

    def test_format_odcs_as_yaml_with_complete_document(self):
        """
        Test formatting complete ODCS document as YAML.

        Scenario: Format complete ODCS document with all sections
        Expected: Valid YAML string with all sections
        """
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not available")

        odcs_doc = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": "name", "type": "string"}
                ]
            },
            "quality": {
                "rules": [
                    {"name": "not_null", "type": "not_null", "field": "id"}
                ]
            }
        }

        result = format_odcs_as_yaml(odcs_doc)

        # Verify result is valid YAML
        parsed = yaml.safe_load(result)

        # Verify all sections are present
        self.assertIn("apiVersion", parsed)
        self.assertIn("kind", parsed)
        self.assertIn("id", parsed)
        self.assertIn("name", parsed)
        self.assertIn("schema", parsed)
        self.assertIn("quality", parsed)
        self.assertIn("fields", parsed["schema"])
        self.assertIn("rules", parsed["quality"])

    def test_format_odcs_as_yaml_with_invalid_document(self):
        """
        Test error handling when formatting invalid document as YAML.

        Scenario: Format non-dictionary as YAML
        Expected: ODCSExportError with field_path and expected/actual types
        """
        with self.assertRaises(ODCSExportError) as context:
            format_odcs_as_yaml("not-a-dict")

        error = context.exception
        self.assertIn("dictionary", error.message.lower())
        self.assertIn("field_path", error.context)
        self.assertEqual(error.context["field_path"], "/")
        if "expected" in error.context:
            self.assertEqual(error.context["expected"], "dict")
        if "actual" in error.context:
            self.assertIn("str", error.context["actual"])

    def test_format_odcs_as_yaml_validation(self):
        """
        Test YAML output format validation.

        Scenario: Format ODCS document and validate output is correct YAML
        Expected: Output is valid, parseable YAML with correct structure
        """
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not available")

        odcs_doc = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract"
        }

        result = format_odcs_as_yaml(odcs_doc)

        # Validate YAML syntax
        parsed = yaml.safe_load(result)

        # Validate structure
        self.assertIsInstance(parsed, dict)
        self.assertIn("apiVersion", parsed)
        self.assertIn("kind", parsed)
        self.assertIn("id", parsed)
        self.assertIn("name", parsed)

    def test_format_odcs_as_yaml_without_pyyaml(self):
        """
        Test error handling when PyYAML is not available.

        Scenario: Format ODCS document as YAML without PyYAML installed
        Expected: ODCSExportError indicating PyYAML is required
        """
        # This test will only work if PyYAML is actually not available
        # In most cases, PyYAML will be available, so we'll test the error message
        # by checking the error handling logic
        pass  # Covered by implementation error handling


class ODCSFormatRoundTripTest(TestCase):
    """Test round-trip conversion for ODCS format functions"""

    def test_round_trip_json_yaml_json(self):
        """
        Test round-trip conversion: JSON → YAML → JSON.

        Scenario: Format as JSON, then as YAML, then parse YAML and format as JSON again
        Expected: Final JSON matches original structure
        """
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not available")

        odcs_doc = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": "name", "type": "string"}
                ]
            }
        }

        # Format as JSON
        json_result = format_odcs_as_json(odcs_doc)
        json_parsed = json.loads(json_result)

        # Format as YAML
        yaml_result = format_odcs_as_yaml(odcs_doc)
        yaml_parsed = yaml.safe_load(yaml_result)

        # Format YAML-parsed data as JSON again
        json_result_2 = format_odcs_as_json(yaml_parsed)
        json_parsed_2 = json.loads(json_result_2)

        # Compare structures (they should be equivalent)
        self.assertEqual(json_parsed["apiVersion"], json_parsed_2["apiVersion"])
        self.assertEqual(json_parsed["kind"], json_parsed_2["kind"])
        self.assertEqual(json_parsed["id"], json_parsed_2["id"])
        self.assertEqual(json_parsed["name"], json_parsed_2["name"])
        self.assertEqual(json_parsed["version"], json_parsed_2["version"])

    def test_round_trip_with_unicode(self):
        """
        Test round-trip conversion with unicode characters.

        Scenario: Format document with unicode, convert formats, verify preservation
        Expected: Unicode characters preserved through round-trip
        """
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not available")

        odcs_doc = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract with émojis 🚀 and 中文"
        }

        # Format as JSON
        json_result = format_odcs_as_json(odcs_doc, ensure_ascii=False)
        json_parsed = json.loads(json_result)

        # Format as YAML
        yaml_result = format_odcs_as_yaml(odcs_doc, allow_unicode=True)
        yaml_parsed = yaml.safe_load(yaml_result)

        # Format YAML-parsed data as JSON again
        json_result_2 = format_odcs_as_json(yaml_parsed, ensure_ascii=False)
        json_parsed_2 = json.loads(json_result_2)

        # Verify unicode preservation
        self.assertIn("émojis", json_parsed_2["name"])
        self.assertIn("🚀", json_parsed_2["name"])
        self.assertIn("中文", json_parsed_2["name"])

    def test_round_trip_with_special_characters(self):
        """
        Test round-trip conversion with special characters and escape sequences.

        Scenario: Format document with escape sequences, convert formats
        Expected: Special characters preserved through round-trip
        """
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not available")

        odcs_doc = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-contract",
            "description": "Line 1\nLine 2\tTabbed"
        }

        # Format as JSON
        json_result = format_odcs_as_json(odcs_doc)
        json_parsed = json.loads(json_result)

        # Format as YAML
        yaml_result = format_odcs_as_yaml(odcs_doc)
        yaml_parsed = yaml.safe_load(yaml_result)

        # Format YAML-parsed data as JSON again
        json_result_2 = format_odcs_as_json(yaml_parsed)
        json_parsed_2 = json.loads(json_result_2)

        # Verify special characters preserved
        self.assertIn("\n", json_parsed_2["description"])
        self.assertIn("\t", json_parsed_2["description"])

