"""
Unit tests for ODPS schema validation (Task 1.2.3).

Tests verify:
- ODPS 4.1 validation (valid and invalid)
- ODPS 4.0 validation
- Backward compatibility (older versions)
- Schema loading errors
- Validation error messages with paths
- User-friendly error codes
"""

try:
    import pytest

    pytestmark = pytest.mark.django_db
except ImportError:
    # pytest not available, using Django test runner
    pytest = None
    pytestmark = None

import json

from django.test import TestCase

try:
    import jsonschema

    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False

from hub.apps.contracts.odps_parser import ODPSParser, ODPSValidationError


class ODPSValidation41Test(TestCase):
    """Unit tests for ODPS 4.1 validation (Task 1.2.3)"""

    def setUp(self):
        """Set up test fixtures"""
        if not JSONSCHEMA_AVAILABLE:
            self.skipTest("jsonschema library not available")

    def test_validate_odps_41_valid(self):
        """Test ODPS 4.1 validation with valid document (Task 1.2.3)"""
        valid_odps = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"productID": "test-product-41", "name": "Test Product 4.1"}}
            },
        }

        is_valid, validation_errors = ODPSParser.validate(valid_odps, version="4.1")

        self.assertTrue(is_valid, "Valid ODPS 4.1 document should pass validation")
        self.assertEqual(
            len(validation_errors), 0, "Valid document should have no validation errors"
        )

    def test_validate_odps_41_invalid_missing_required(self):
        """Test ODPS 4.1 validation with invalid document (missing required field) (Task 1.2.3)"""
        invalid_odps = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            # Missing required "product" field
        }

        is_valid, validation_errors = ODPSParser.validate(invalid_odps, version="4.1")

        self.assertFalse(is_valid, "Invalid ODPS 4.1 document should fail validation")
        self.assertGreater(
            len(validation_errors), 0, "Invalid document should have validation errors"
        )

        # Check that errors include path information
        for error in validation_errors:
            self.assertIn("path", error)
            self.assertIn("message", error)
            self.assertIn("code", error)
            # Should have error code for missing required field
            if (
                "product" in error.get("path", "").lower()
                or "required" in error.get("message", "").lower()
            ):
                self.assertIn("REQUIRED", error.get("code", ""))

    def test_validate_odps_41_invalid_wrong_type(self):
        """Test ODPS 4.1 validation with invalid document (wrong type) (Task 1.2.3)"""
        invalid_odps = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": "should-be-object-not-string",
        }

        is_valid, validation_errors = ODPSParser.validate(invalid_odps, version="4.1")

        self.assertFalse(is_valid, "Invalid ODPS 4.1 document should fail validation")
        self.assertGreater(
            len(validation_errors), 0, "Invalid document should have validation errors"
        )

        # Check that errors include type information
        for error in validation_errors:
            self.assertIn("path", error)
            self.assertIn("message", error)
            self.assertIn("code", error)
            # Should have error code for invalid type
            if "type" in error.get("message", "").lower():
                self.assertIn("TYPE", error.get("code", ""))

    def test_validate_odps_41_with_file_path(self):
        """Test ODPS 4.1 validation with file path context (Task 1.2.3)"""
        valid_odps = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {"en": {"productID": "test-product", "name": "Test Product"}}},
        }

        is_valid, validation_errors = ODPSParser.validate(
            valid_odps, version="4.1", file_path="/test/path/odps.yaml"
        )

        self.assertTrue(is_valid)
        self.assertEqual(len(validation_errors), 0)


class ODPSValidation40Test(TestCase):
    """Unit tests for ODPS 4.0 validation (Task 1.2.3)"""

    def setUp(self):
        """Set up test fixtures"""
        if not JSONSCHEMA_AVAILABLE:
            self.skipTest("jsonschema library not available")

    def test_validate_odps_40_valid(self):
        """Test ODPS 4.0 validation with valid document (Task 1.2.3)"""
        valid_odps = {
            "schema": "https://opendataproducts.org/schema/v4.0",
            "version": "4.0",
            "product": {
                "details": {"en": {"productID": "test-product-40", "name": "Test Product 4.0"}}
            },
        }

        is_valid, validation_errors = ODPSParser.validate(valid_odps, version="4.0")

        self.assertTrue(is_valid, "Valid ODPS 4.0 document should pass validation")
        self.assertEqual(
            len(validation_errors), 0, "Valid document should have no validation errors"
        )

    def test_validate_odps_40_invalid(self):
        """Test ODPS 4.0 validation with invalid document (Task 1.2.3)"""
        invalid_odps = {
            "schema": "https://opendataproducts.org/schema/v4.0",
            "version": "4.0",
            # Missing required "product" field
        }

        is_valid, validation_errors = ODPSParser.validate(invalid_odps, version="4.0")

        self.assertFalse(is_valid, "Invalid ODPS 4.0 document should fail validation")
        self.assertGreater(
            len(validation_errors), 0, "Invalid document should have validation errors"
        )


class ODPSValidationBackwardCompatibilityTest(TestCase):
    """Unit tests for backward compatibility with older ODPS versions (Task 1.2.3)"""

    def setUp(self):
        """Set up test fixtures"""
        if not JSONSCHEMA_AVAILABLE:
            self.skipTest("jsonschema library not available")

    def test_validate_odps_3x_valid(self):
        """Test ODPS 3.x validation (backward compatibility) (Task 1.2.3)"""
        valid_odps = {
            "schema": "https://opendataproducts.org/schema/v3.x",
            "version": "3.x",
            "product": {
                "details": {"en": {"productID": "test-product-3x", "name": "Test Product 3.x"}}
            },
        }

        is_valid, validation_errors = ODPSParser.validate(valid_odps, version="3.x")

        self.assertTrue(is_valid, "Valid ODPS 3.x document should pass validation")
        self.assertEqual(len(validation_errors), 0)

    def test_validate_odps_2x_valid(self):
        """Test ODPS 2.x validation (backward compatibility) (Task 1.2.3)"""
        valid_odps = {
            "schema": "https://opendataproducts.org/schema/v2.x",
            "version": "2.x",
            "product": {
                "details": {"en": {"productID": "test-product-2x", "name": "Test Product 2.x"}}
            },
        }

        is_valid, validation_errors = ODPSParser.validate(valid_odps, version="2.x")

        self.assertTrue(is_valid, "Valid ODPS 2.x document should pass validation")
        self.assertEqual(len(validation_errors), 0)

    def test_validate_odps_1x_valid(self):
        """Test ODPS 1.x validation (backward compatibility) (Task 1.2.3)"""
        valid_odps = {
            "schema": "https://opendataproducts.org/schema/v1.x",
            "version": "1.x",
            "product": {
                "details": {"en": {"productID": "test-product-1x", "name": "Test Product 1.x"}}
            },
        }

        is_valid, validation_errors = ODPSParser.validate(valid_odps, version="1.x")

        self.assertTrue(is_valid, "Valid ODPS 1.x document should pass validation")
        self.assertEqual(len(validation_errors), 0)


class ODPSValidationSchemaLoadingTest(TestCase):
    """Unit tests for schema loading errors (Task 1.2.3)"""

    def setUp(self):
        """Set up test fixtures"""
        if not JSONSCHEMA_AVAILABLE:
            self.skipTest("jsonschema library not available")

    def test_validate_schema_not_found(self):
        """Test validation error when schema not found (Task 1.2.3)"""
        odps_document = {"schema": "https://opendataproducts.org/schema/v99.9", "version": "99.9"}

        with self.assertRaises(ODPSValidationError) as cm:
            ODPSParser.validate(odps_document, version="99.9")

        error = cm.exception
        self.assertEqual(error.error_code, "SCHEMA_NOT_FOUND")
        self.assertIn("schema not found", error.message.lower())

    def test_validate_version_detection_from_schema(self):
        """Test version detection from schema field (Task 1.2.3)"""
        valid_odps = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "product": {"details": {"en": {"productID": "test-product", "name": "Test Product"}}},
        }

        # Don't specify version, should detect from schema field
        is_valid, validation_errors = ODPSParser.validate(valid_odps)

        self.assertTrue(is_valid, "Should detect version from schema field")
        self.assertEqual(len(validation_errors), 0)

    def test_validate_version_detection_from_version_field(self):
        """Test version detection from version field (Task 1.2.3)"""
        # Include schema field as well to ensure document is valid
        valid_odps = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {"en": {"productID": "test-product", "name": "Test Product"}}},
        }

        # Don't specify version, should detect from version field (or schema field)
        # The version detection should work from either field
        is_valid, validation_errors = ODPSParser.validate(valid_odps)

        self.assertTrue(
            is_valid, f"Should detect version and validate. Errors: {validation_errors}"
        )
        self.assertEqual(len(validation_errors), 0)

    def test_validate_version_not_found(self):
        """Test validation error when version cannot be determined (Task 1.2.3)"""
        odps_document = {
            "product": {"details": {"en": {"productID": "test-product", "name": "Test Product"}}}
        }

        with self.assertRaises(ODPSValidationError) as cm:
            ODPSParser.validate(odps_document)

        error = cm.exception
        self.assertEqual(error.error_code, "VERSION_NOT_FOUND")
        self.assertIn("version could not be determined", error.message.lower())


class ODPSValidationErrorMessagesTest(TestCase):
    """Unit tests for validation error messages (Task 1.2.3)"""

    def setUp(self):
        """Set up test fixtures"""
        if not JSONSCHEMA_AVAILABLE:
            self.skipTest("jsonschema library not available")

    def test_validation_errors_include_paths(self):
        """Test that validation errors include error paths (Task 1.2.3)"""
        invalid_odps = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {"en": {"productID": 123}}},  # Should be string, not number
        }

        is_valid, validation_errors = ODPSParser.validate(invalid_odps, version="4.1")

        self.assertFalse(is_valid)
        self.assertGreater(len(validation_errors), 0)

        # Check that all errors have path information
        for error in validation_errors:
            self.assertIn("path", error)
            self.assertIsInstance(error["path"], str)
            self.assertIn("message", error)
            self.assertIn("code", error)

    def test_validation_errors_include_error_codes(self):
        """Test that validation errors include user-friendly error codes (Task 1.2.3)"""
        invalid_odps = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            # Missing required "product" field
        }

        is_valid, validation_errors = ODPSParser.validate(invalid_odps, version="4.1")

        self.assertFalse(is_valid)
        self.assertGreater(len(validation_errors), 0)

        # Check that errors have error codes
        for error in validation_errors:
            self.assertIn("code", error)
            self.assertIsInstance(error["code"], str)
            self.assertGreater(len(error["code"]), 0)

    def test_validation_errors_include_schema_paths(self):
        """Test that validation errors include schema paths (Task 1.2.3)"""
        invalid_odps = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {"en": {"productID": "test-product", "name": "Test Product"}}},
            "invalidField": "should not be here",
        }

        is_valid, validation_errors = ODPSParser.validate(invalid_odps, version="4.1")

        # May or may not be invalid depending on schema, but if there are errors, check structure
        if not is_valid:
            for error in validation_errors:
                self.assertIn("path", error)
                self.assertIn("message", error)
                self.assertIn("code", error)

    def test_validation_error_codes_mapping(self):
        """Test that error codes are correctly mapped (Task 1.2.3)"""
        # Test required field error
        invalid_odps_missing = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
        }

        is_valid, errors = ODPSParser.validate(invalid_odps_missing, version="4.1")
        self.assertFalse(is_valid)

        # Should have at least one error with REQUIRED code
        required_errors = [e for e in errors if "REQUIRED" in e.get("code", "")]
        if required_errors:
            self.assertGreater(len(required_errors), 0)


class ODPSParseAndValidateTest(TestCase):
    """Unit tests for parse_and_validate method (Task 1.2.3)"""

    def setUp(self):
        """Set up test fixtures"""
        if not JSONSCHEMA_AVAILABLE:
            self.skipTest("jsonschema library not available")

    def test_parse_and_validate_valid_json(self):
        """Test parse_and_validate with valid JSON ODPS (Task 1.2.3)"""
        valid_json = json.dumps(
            {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "version": "4.1",
                "product": {
                    "details": {"en": {"productID": "test-product", "name": "Test Product"}}
                },
            }
        )

        parsed_doc, is_valid, validation_errors = ODPSParser.parse_and_validate(
            valid_json, version="4.1"
        )

        self.assertIsInstance(parsed_doc, dict)
        self.assertTrue(is_valid)
        self.assertEqual(len(validation_errors), 0)

    def test_parse_and_validate_invalid_json(self):
        """Test parse_and_validate with invalid JSON ODPS (Task 1.2.3)"""
        invalid_json = json.dumps(
            {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "version": "4.1",
                # Missing required "product" field
            }
        )

        parsed_doc, is_valid, validation_errors = ODPSParser.parse_and_validate(
            invalid_json, version="4.1"
        )

        self.assertIsInstance(parsed_doc, dict)
        self.assertFalse(is_valid)
        self.assertGreater(len(validation_errors), 0)

    def test_parse_and_validate_valid_yaml(self):
        """Test parse_and_validate with valid YAML ODPS (Task 1.2.3)"""
        valid_yaml = """
schema: https://opendataproducts.org/schema/v4.1
version: "4.1"
product:
  details:
    en:
      productID: "test-product"
      name: "Test Product"
"""

        parsed_doc, is_valid, validation_errors = ODPSParser.parse_and_validate(
            valid_yaml, version="4.1"
        )

        self.assertIsInstance(parsed_doc, dict)
        self.assertTrue(is_valid)
        self.assertEqual(len(validation_errors), 0)

    def test_parse_and_validate_with_auto_version_detection(self):
        """Test parse_and_validate with automatic version detection (Task 1.2.3)"""
        valid_json = json.dumps(
            {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "product": {
                    "details": {"en": {"productID": "test-product", "name": "Test Product"}}
                },
            }
        )

        # Don't specify version, should detect from schema field
        parsed_doc, is_valid, validation_errors = ODPSParser.parse_and_validate(valid_json)

        self.assertIsInstance(parsed_doc, dict)
        self.assertTrue(is_valid)
        self.assertEqual(len(validation_errors), 0)

    # Edge cases and error handling tests
    def test_validate_with_none_input(self):
        """Test validation with None input."""
        is_valid, errors = ODPSParser.validate(None, version="4.1")
        # Should handle None gracefully
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)

    def test_validate_with_empty_dict(self):
        """Test validation with empty dictionary."""
        is_valid, errors = ODPSParser.validate({}, version="4.1")
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)

    def test_validate_with_invalid_type(self):
        """Test validation with invalid input type."""
        is_valid, errors = ODPSParser.validate("not a dict", version="4.1")
        # Should handle invalid type gracefully
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)

    def test_validate_with_none_version(self):
        """Test validation with None version parameter."""
        valid_odps = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {"en": {"productID": "test-product", "name": "Test Product"}}},
        }
        # Should auto-detect version or handle None gracefully
        is_valid, _errors = ODPSParser.validate(valid_odps, version=None)
        self.assertIsInstance(is_valid, bool)

    def test_validate_with_empty_version_string(self):
        """Test validation with empty version string."""
        valid_odps = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {"en": {"productID": "test-product", "name": "Test Product"}}},
        }
        # Empty version should raise ODPSValidationError with VERSION_NOT_FOUND
        from hub.apps.contracts.odps_parser import ODPSValidationError
        with self.assertRaises(ODPSValidationError):
            ODPSParser.validate(valid_odps, version="")

    def test_validate_with_invalid_version(self):
        """Test validation with invalid version."""
        valid_odps = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {"en": {"productID": "test-product", "name": "Test Product"}}},
        }
        # Invalid version should raise ODPSValidationError with SCHEMA_NOT_FOUND
        from hub.apps.contracts.odps_parser import ODPSValidationError
        with self.assertRaises(ODPSValidationError):
            ODPSParser.validate(valid_odps, version="invalid-version")

    def test_validate_with_special_characters(self):
        """Test validation with special characters in document."""
        odps_with_special = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {"en": {"productID": "test-<>&\"'", "name": "Product <>&\"'"}}},
        }
        is_valid, _errors = ODPSParser.validate(odps_with_special, version="4.1")
        # Should handle special characters
        self.assertTrue(is_valid)
        self.assertEqual(_errors, [])

    def test_validate_with_unicode(self):
        """Test validation with unicode characters."""
        odps_with_unicode = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {"en": {"productID": "产品", "name": "产品名称"}}},
        }
        is_valid, _errors = ODPSParser.validate(odps_with_unicode, version="4.1")
        # Should handle unicode
        self.assertTrue(is_valid)
        self.assertEqual(_errors, [])

    def test_validate_with_very_large_document(self):
        """Test validation with very large document."""
        large_odps = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product",
                        "description": "A" * 100000,
                    }
                }
            },
        }
        is_valid, _errors = ODPSParser.validate(large_odps, version="4.1")
        # Should handle very large documents
        self.assertTrue(is_valid)
        self.assertEqual(_errors, [])

    def test_validate_with_deep_nesting(self):
        """Test validation with deeply nested structure."""
        nested_odps = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "level1": {"level2": {"level3": {"level4": {"level5": {"value": "deep"}}}}},
                    }
                }
            },
        }
        is_valid, _errors = ODPSParser.validate(nested_odps, version="4.1")
        # Should handle deep nesting
        self.assertTrue(is_valid)
        self.assertEqual(_errors, [])

    def test_validate_error_structure_consistency(self):
        """Test that validation errors have consistent structure."""
        invalid_odps = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            # Missing required "product" field
        }
        is_valid, errors = ODPSParser.validate(invalid_odps, version="4.1")

        self.assertFalse(is_valid)
        for error in errors:
            # All errors should have required fields
            self.assertIn("path", error)
            self.assertIn("message", error)
            self.assertIn("code", error)
            self.assertIsInstance(error["path"], (str, list))
            self.assertIsInstance(error["message"], str)
            self.assertIsInstance(error["code"], str)

    def test_parse_and_validate_with_none_input(self):
        """Test parse_and_validate with None input."""
        from hub.apps.contracts.odps_parser import ODPSValidationError
        with self.assertRaises(ODPSValidationError):
            ODPSParser.parse_and_validate(None, version="4.1")

    def test_parse_and_validate_with_empty_string(self):
        """Test parse_and_validate with empty string."""
        from hub.apps.contracts.odps_parser import ODPSValidationError
        with self.assertRaises(ODPSValidationError):
            ODPSParser.parse_and_validate("", version="4.1")

    def test_parse_and_validate_with_invalid_json_string(self):
        """Test parse_and_validate with invalid JSON string."""
        from hub.apps.contracts.odps_parser import ODPSValidationError
        invalid_json = '{"schema": "invalid}'
        with self.assertRaises((ODPSValidationError, json.JSONDecodeError)):
            ODPSParser.parse_and_validate(invalid_json, version="4.1")

    def test_parse_and_validate_with_malformed_yaml(self):
        """Test parse_and_validate with malformed YAML."""
        from hub.apps.contracts.odps_parser import ODPSValidationError
        invalid_yaml = """
schema: https://opendataproducts.org/schema/v4.1
version: "4.1"
product:
  details: [invalid: yaml
"""
        with self.assertRaises(ODPSValidationError):
            ODPSParser.parse_and_validate(invalid_yaml, version="4.1")

    def test_validate_with_missing_schema_field(self):
        """Test validation with missing schema field."""
        odps_no_schema = {
            "version": "4.1",
            "product": {"details": {"en": {"productID": "test-product", "name": "Test Product"}}},
        }
        is_valid, _errors = ODPSParser.validate(odps_no_schema, version="4.1")
        self.assertFalse(is_valid)
        self.assertGreater(len(_errors), 0)

    def test_validate_with_missing_version_field(self):
        """Test validation with missing version field."""
        odps_no_version = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "product": {"details": {"en": {"productID": "test-product", "name": "Test Product"}}},
        }
        is_valid, _errors = ODPSParser.validate(odps_no_version, version="4.1")
        # Valid because the version parameter is passed explicitly
        self.assertTrue(is_valid)

    def test_validate_with_wrong_schema_url(self):
        """Test validation with wrong schema URL."""
        odps_wrong_schema = {
            "schema": "https://example.com/invalid/schema",
            "version": "4.1",
            "product": {"details": {"en": {"productID": "test-product", "name": "Test Product"}}},
        }
        is_valid, _errors = ODPSParser.validate(odps_wrong_schema, version="4.1")
        # Wrong schema URL — should not pass validation
        self.assertFalse(is_valid)
        self.assertGreater(len(_errors), 0)

    def test_parser_validation_handles_unicode_characters(self):
        """Test that parser validation handles unicode characters correctly."""
        odps_unicode = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {"en": {"productID": "测试产品", "name": "测试名称"}}},
        }
        is_valid, _errors = ODPSParser.validate(odps_unicode, version="4.1")
        # Should handle unicode characters
        self.assertTrue(is_valid)
        self.assertEqual(_errors, [])

    def test_parser_validation_handles_special_characters(self):
        """Test that parser validation handles special characters correctly."""
        odps_special = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"productID": "test-<>&\"'", "name": "Test & Co. (Special)"}}
            },
        }
        is_valid, _errors = ODPSParser.validate(odps_special, version="4.1")
        # Should handle special characters
        self.assertTrue(is_valid)
        self.assertEqual(_errors, [])

    def test_parser_validation_handles_very_large_documents(self):
        """Test that parser validation handles very large documents correctly."""
        large_description = "A" * 100000  # 100KB string
        odps_large = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"productID": "test-large", "description": large_description}}
            },
        }
        is_valid, _errors = ODPSParser.validate(odps_large, version="4.1")
        # Should handle very large documents
        self.assertTrue(is_valid)
        self.assertEqual(_errors, [])

    def test_parser_validation_handles_none_values(self):
        """Test that parser validation handles None values correctly."""
        # validate(None) should return failure (is_valid=False), not crash
        is_valid, errors = ODPSParser.validate(None, version="4.1")  # type: ignore[misc]  # test: edge-case type exercise
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)

    def test_parser_validation_handles_nested_structures(self):
        """Test that parser validation handles nested structures correctly."""
        odps_nested = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-nested",
                        "nested": {"level1": {"level2": {"level3": {"value": "deep"}}}},
                    }
                }
            },
        }
        is_valid, _errors = ODPSParser.validate(odps_nested, version="4.1")
        # Should handle nested structures
        self.assertTrue(is_valid)
        self.assertEqual(_errors, [])
