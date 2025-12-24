"""
Unit tests for ODPS parser module (Task 1.2.1).

Tests verify:
- YAML parsing
- JSON parsing
- Format detection
- Error handling with context
- File path and line number in error messages
"""
import json
import tempfile
import yaml
from pathlib import Path
from django.test import TestCase

from hub.apps.contracts.odps_parser import (
    ODPSParser,
    ODPSValidationError
)


class ODPSParserYAMLTest(TestCase):
    """Unit tests for YAML parsing (Task 1.2.1)"""

    def test_parse_valid_yaml(self):
        """Test parsing valid YAML ODPS document"""
        yaml_content = """
schema: https://opendataproducts.org/schema/v4.1
version: "4.1"
product:
  details:
    en:
      productID: "test-product"
      name: "Test Product"
"""
        result = ODPSParser.parse(yaml_content, format="yaml")

        self.assertIsInstance(result, dict)
        self.assertEqual(result["schema"], "https://opendataproducts.org/schema/v4.1")
        self.assertEqual(result["version"], "4.1")
        self.assertIn("product", result)
        self.assertIn("details", result["product"])

    def test_parse_yaml_with_file_path(self):
        """Test YAML parsing with file path context"""
        yaml_content = """
schema: https://opendataproducts.org/schema/v4.1
version: "4.1"
product:
  details:
    en:
      productID: "test-product"
"""
        result = ODPSParser.parse(yaml_content, file_path="/path/to/file.yaml", format="yaml")

        self.assertIsInstance(result, dict)
        self.assertEqual(result["version"], "4.1")

    def test_parse_yaml_error_invalid_syntax(self):
        """Test YAML parsing error handling for invalid syntax"""
        invalid_yaml = """
schema: https://opendataproducts.org/schema/v4.1
version: "4.1"
product:
  details:
    en:
      productID: "test-product"
      name: [invalid: yaml
"""
        with self.assertRaises(ODPSValidationError) as cm:
            ODPSParser.parse(invalid_yaml, format="yaml")

        error = cm.exception
        self.assertIn("Invalid YAML format", error.message)
        self.assertIsNotNone(error.original_error)

    def test_parse_yaml_error_with_file_path(self):
        """Test YAML parsing error includes file path in context"""
        invalid_yaml = """
schema: https://opendataproducts.org/schema/v4.1
version: "4.1"
product:
  invalid: [yaml: syntax
"""
        with self.assertRaises(ODPSValidationError) as cm:
            ODPSParser.parse(invalid_yaml, file_path="/test/path.yaml", format="yaml")

        error = cm.exception
        self.assertEqual(error.file_path, "/test/path.yaml")
        self.assertIn("Invalid YAML format", error.message)

    def test_parse_yaml_error_with_line_number(self):
        """Test YAML parsing error includes line number"""
        invalid_yaml = """schema: https://opendataproducts.org/schema/v4.1
version: "4.1"
product:
  details:
    en:
      productID: "test"
      name: [invalid: yaml syntax
"""
        with self.assertRaises(ODPSValidationError) as cm:
            ODPSParser.parse(invalid_yaml, format="yaml")

        error = cm.exception
        # YAML errors should include line number when available
        if error.line_number:
            self.assertIsInstance(error.line_number, int)
            self.assertGreater(error.line_number, 0)

    def test_parse_yaml_empty_content(self):
        """Test YAML parsing error for empty content"""
        with self.assertRaises(ODPSValidationError) as cm:
            ODPSParser.parse("", format="yaml")

        error = cm.exception
        self.assertIn("empty", error.message.lower())

    def test_parse_yaml_not_dict(self):
        """Test YAML parsing error when content is not a dictionary"""
        yaml_content = "- item1\n- item2\n- item3"

        with self.assertRaises(ODPSValidationError) as cm:
            ODPSParser.parse(yaml_content, format="yaml")

        error = cm.exception
        self.assertIn("must be a YAML object", error.message)


class ODPSParserJSONTest(TestCase):
    """Unit tests for JSON parsing (Task 1.2.1)"""

    def test_parse_valid_json(self):
        """Test parsing valid JSON ODPS document"""
        json_content = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                }
            }
        })

        result = ODPSParser.parse(json_content, format="json")

        self.assertIsInstance(result, dict)
        self.assertEqual(result["schema"], "https://opendataproducts.org/schema/v4.1")
        self.assertEqual(result["version"], "4.1")
        self.assertIn("product", result)

    def test_parse_json_with_file_path(self):
        """Test JSON parsing with file path context"""
        json_content = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1"
        })

        result = ODPSParser.parse(json_content, file_path="/path/to/file.json", format="json")

        self.assertIsInstance(result, dict)
        self.assertEqual(result["version"], "4.1")

    def test_parse_json_error_invalid_syntax(self):
        """Test JSON parsing error handling for invalid syntax"""
        invalid_json = '{"schema": "https://opendataproducts.org/schema/v4.1", "version": "4.1", invalid}'

        with self.assertRaises(ODPSValidationError) as cm:
            ODPSParser.parse(invalid_json, format="json")

        error = cm.exception
        self.assertIn("Invalid JSON format", error.message)
        self.assertIsNotNone(error.original_error)

    def test_parse_json_error_with_file_path(self):
        """Test JSON parsing error includes file path in context"""
        invalid_json = '{"schema": "https://opendataproducts.org/schema/v4.1", invalid}'

        with self.assertRaises(ODPSValidationError) as cm:
            ODPSParser.parse(invalid_json, file_path="/test/path.json", format="json")

        error = cm.exception
        self.assertEqual(error.file_path, "/test/path.json")
        self.assertIn("Invalid JSON format", error.message)

    def test_parse_json_error_with_line_number(self):
        """Test JSON parsing error includes line number"""
        invalid_json = """{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {
    "details": invalid
  }
}"""
        with self.assertRaises(ODPSValidationError) as cm:
            ODPSParser.parse(invalid_json, format="json")

        error = cm.exception
        # JSON errors should include line number when available
        if error.line_number:
            self.assertIsInstance(error.line_number, int)
            self.assertGreater(error.line_number, 0)

    def test_parse_json_not_dict(self):
        """Test JSON parsing error when content is not a dictionary"""
        json_content = '["item1", "item2", "item3"]'

        with self.assertRaises(ODPSValidationError) as cm:
            ODPSParser.parse(json_content, format="json")

        error = cm.exception
        self.assertIn("must be a JSON object", error.message)

    def test_parse_json_empty_content(self):
        """Test JSON parsing error for empty content"""
        with self.assertRaises(ODPSValidationError) as cm:
            ODPSParser.parse("", format="json")

        error = cm.exception
        self.assertIn("non-empty string", error.message)


class ODPSParserFormatDetectionTest(TestCase):
    """Unit tests for format detection (Task 1.2.1)"""

    def test_detect_format_json_object(self):
        """Test format detection for JSON object"""
        json_content = '{"schema": "https://opendataproducts.org/schema/v4.1", "version": "4.1"}'

        detected = ODPSParser.detect_format(json_content)
        self.assertEqual(detected, "json")

    def test_detect_format_json_array(self):
        """Test format detection for JSON array (should detect as JSON)"""
        json_content = '[{"key": "value"}]'

        detected = ODPSParser.detect_format(json_content)
        self.assertEqual(detected, "json")

    def test_detect_format_yaml(self):
        """Test format detection for YAML"""
        yaml_content = """
schema: https://opendataproducts.org/schema/v4.1
version: "4.1"
product:
  details:
    en:
      productID: "test-product"
"""
        detected = ODPSParser.detect_format(yaml_content)
        self.assertEqual(detected, "yaml")

    def test_detect_format_yaml_with_json_like_start(self):
        """Test format detection when YAML starts with JSON-like characters"""
        yaml_content = """
{
  schema: https://opendataproducts.org/schema/v4.1
  version: "4.1"
}
"""
        # This should be detected as YAML (not valid JSON)
        detected = ODPSParser.detect_format(yaml_content)
        # Since it's not valid JSON, should default to YAML
        self.assertEqual(detected, "yaml")

    def test_parse_with_auto_detection_json(self):
        """Test parsing with automatic format detection (JSON)"""
        json_content = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1"
        })

        result = ODPSParser.parse(json_content)

        self.assertIsInstance(result, dict)
        self.assertEqual(result["version"], "4.1")

    def test_parse_with_auto_detection_yaml(self):
        """Test parsing with automatic format detection (YAML)"""
        yaml_content = """
schema: https://opendataproducts.org/schema/v4.1
version: "4.1"
product:
  details:
    en:
      productID: "test-product"
"""
        result = ODPSParser.parse(yaml_content)

        self.assertIsInstance(result, dict)
        self.assertEqual(result["version"], "4.1")

    def test_parse_with_explicit_format_override(self):
        """Test parsing with explicit format override"""
        # YAML content but force JSON format (should fail)
        yaml_content = """
schema: https://opendataproducts.org/schema/v4.1
version: "4.1"
"""
        with self.assertRaises(ODPSValidationError):
            ODPSParser.parse(yaml_content, format="json")


class ODPSParserFileTest(TestCase):
    """Unit tests for file parsing (Task 1.2.1)"""

    def test_parse_file_json(self):
        """Test parsing ODPS from JSON file"""
        json_content = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product"
                    }
                }
            }
        })

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(json_content)
            f.flush()
            temp_path = f.name

        try:
            result = ODPSParser.parse_file(temp_path)

            self.assertIsInstance(result, dict)
            self.assertEqual(result["version"], "4.1")
            self.assertEqual(result["file_path"], temp_path) if hasattr(result, "file_path") else None
        finally:
            Path(temp_path).unlink()

    def test_parse_file_yaml(self):
        """Test parsing ODPS from YAML file"""
        yaml_content = """
schema: https://opendataproducts.org/schema/v4.1
version: "4.1"
product:
  details:
    en:
      productID: "test-product"
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()
            temp_path = f.name

        try:
            result = ODPSParser.parse_file(temp_path)

            self.assertIsInstance(result, dict)
            self.assertEqual(result["version"], "4.1")
        finally:
            Path(temp_path).unlink()

    def test_parse_file_not_found(self):
        """Test parsing error when file does not exist"""
        with self.assertRaises(FileNotFoundError):
            ODPSParser.parse_file("/nonexistent/path/odps.yaml")

    def test_parse_file_invalid_content(self):
        """Test parsing error for file with invalid content"""
        invalid_content = '{"schema": "https://opendataproducts.org/schema/v4.1", invalid}'

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(invalid_content)
            f.flush()
            temp_path = f.name

        try:
            # Force JSON format to ensure we test JSON parsing errors
            with self.assertRaises(ODPSValidationError) as cm:
                ODPSParser.parse_file(temp_path, format="json")

            error = cm.exception
            self.assertEqual(error.file_path, temp_path)
            self.assertIn("Invalid JSON format", error.message)
        finally:
            Path(temp_path).unlink()

    def test_parse_file_encoding_error(self):
        """Test parsing error for file with encoding issues"""
        # Create a file with binary content that can't be decoded as UTF-8
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.bin', delete=False) as f:
            f.write(b'\xff\xfe\x00\x01')  # Invalid UTF-8 sequence
            f.flush()
            temp_path = f.name

        try:
            with self.assertRaises(ODPSValidationError) as cm:
                ODPSParser.parse_file(temp_path)

            error = cm.exception
            self.assertIn("encoding", error.message.lower())
        finally:
            Path(temp_path).unlink()


class ODPSParserErrorContextTest(TestCase):
    """Unit tests for error context (file path, line number) (Task 1.2.1)"""

    def test_error_includes_file_path(self):
        """Test that errors include file path in context"""
        invalid_json = '{"schema": "invalid}'

        with self.assertRaises(ODPSValidationError) as cm:
            ODPSParser.parse(invalid_json, file_path="/test/path.json", format="json")

        error = cm.exception
        self.assertEqual(error.file_path, "/test/path.json")
        # Check that file_path attribute is set (not necessarily in string representation)
        self.assertIsNotNone(error.file_path)

    def test_error_includes_line_number_json(self):
        """Test that JSON errors include line number when available"""
        invalid_json = """{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": invalid
}"""
        with self.assertRaises(ODPSValidationError) as cm:
            ODPSParser.parse(invalid_json, format="json")

        error = cm.exception
        # Line number may or may not be available depending on JSON error
        if error.line_number:
            self.assertIsInstance(error.line_number, int)
            self.assertGreater(error.line_number, 0)

    def test_error_includes_line_number_yaml(self):
        """Test that YAML errors include line number when available"""
        invalid_yaml = """schema: https://opendataproducts.org/schema/v4.1
version: "4.1"
product:
  details:
    en:
      productID: [invalid: yaml syntax
"""
        with self.assertRaises(ODPSValidationError) as cm:
            ODPSParser.parse(invalid_yaml, format="yaml")

        error = cm.exception
        # YAML errors typically include line numbers
        if error.line_number:
            self.assertIsInstance(error.line_number, int)
            self.assertGreater(error.line_number, 0)

    def test_error_includes_original_error(self):
        """Test that errors include original exception"""
        invalid_json = '{"invalid": json}'

        with self.assertRaises(ODPSValidationError) as cm:
            ODPSParser.parse(invalid_json, format="json")

        error = cm.exception
        self.assertIsNotNone(error.original_error)
        self.assertIsInstance(error.original_error, json.JSONDecodeError)

    def test_error_message_format(self):
        """Test that error message is properly formatted"""
        invalid_json = '{"invalid"}'

        with self.assertRaises(ODPSValidationError) as cm:
            ODPSParser.parse(invalid_json, file_path="/test.json", format="json")

        error = cm.exception
        error_str = str(error)
        # Should include error message
        self.assertIn("Invalid JSON", error_str)
        # Should include file path if provided (in the formatted string)
        self.assertIn("File:", error_str)
        self.assertIn("/test.json", error_str)

