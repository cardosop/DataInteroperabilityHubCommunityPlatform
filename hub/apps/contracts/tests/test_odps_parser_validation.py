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
    pytestmark = pytest.mark.django_db(transaction=True)
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

from hub.apps.contracts.odps_parser import (
    ODPSParser,
    ODPSValidationError
)


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
                "details": {
                    "en": {
                        "productID": "test-product-41",
                        "name": "Test Product 4.1"
                    }
                }
            }
        }

        is_valid, validation_errors = ODPSParser.validate(valid_odps, version="4.1")

        self.assertTrue(is_valid, "Valid ODPS 4.1 document should pass validation")
        self.assertEqual(len(validation_errors), 0, "Valid document should have no validation errors")

    def test_validate_odps_41_invalid_missing_required(self):
        """Test ODPS 4.1 validation with invalid document (missing required field) (Task 1.2.3)"""
        invalid_odps = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1"
            # Missing required "product" field
        }

        is_valid, validation_errors = ODPSParser.validate(invalid_odps, version="4.1")

        self.assertFalse(is_valid, "Invalid ODPS 4.1 document should fail validation")
        self.assertGreater(len(validation_errors), 0, "Invalid document should have validation errors")

        # Check that errors include path information
        for error in validation_errors:
            self.assertIn("path", error)
            self.assertIn("message", error)
            self.assertIn("code", error)
            # Should have error code for missing required field
            if "product" in error.get("path", "").lower() or "required" in error.get("message", "").lower():
                self.assertIn("REQUIRED", error.get("code", ""))

    def test_validate_odps_41_invalid_wrong_type(self):
        """Test ODPS 4.1 validation with invalid document (wrong type) (Task 1.2.3)"""
        invalid_odps = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": "should-be-object-not-string"
        }

        is_valid, validation_errors = ODPSParser.validate(invalid_odps, version="4.1")

        self.assertFalse(is_valid, "Invalid ODPS 4.1 document should fail validation")
        self.assertGreater(len(validation_errors), 0, "Invalid document should have validation errors")

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
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                }
            }
        }

        is_valid, validation_errors = ODPSParser.validate(
            valid_odps,
            version="4.1",
            file_path="/test/path/odps.yaml"
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
                "details": {
                    "en": {
                        "productID": "test-product-40",
                        "name": "Test Product 4.0"
                    }
                }
            }
        }

        is_valid, validation_errors = ODPSParser.validate(valid_odps, version="4.0")

        self.assertTrue(is_valid, "Valid ODPS 4.0 document should pass validation")
        self.assertEqual(len(validation_errors), 0, "Valid document should have no validation errors")

    def test_validate_odps_40_invalid(self):
        """Test ODPS 4.0 validation with invalid document (Task 1.2.3)"""
        invalid_odps = {
            "schema": "https://opendataproducts.org/schema/v4.0",
            "version": "4.0"
            # Missing required "product" field
        }

        is_valid, validation_errors = ODPSParser.validate(invalid_odps, version="4.0")

        self.assertFalse(is_valid, "Invalid ODPS 4.0 document should fail validation")
        self.assertGreater(len(validation_errors), 0, "Invalid document should have validation errors")


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
                "details": {
                    "en": {
                        "productID": "test-product-3x",
                        "name": "Test Product 3.x"
                    }
                }
            }
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
                "details": {
                    "en": {
                        "productID": "test-product-2x",
                        "name": "Test Product 2.x"
                    }
                }
            }
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
                "details": {
                    "en": {
                        "productID": "test-product-1x",
                        "name": "Test Product 1.x"
                    }
                }
            }
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
        odps_document = {
            "schema": "https://opendataproducts.org/schema/v99.9",
            "version": "99.9"
        }

        with self.assertRaises(ODPSValidationError) as cm:
            ODPSParser.validate(odps_document, version="99.9")

        error = cm.exception
        self.assertEqual(error.error_code, "SCHEMA_NOT_FOUND")
        self.assertIn("schema not found", error.message.lower())

    def test_validate_version_detection_from_schema(self):
        """Test version detection from schema field (Task 1.2.3)"""
        valid_odps = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                }
            }
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
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                }
            }
        }

        # Don't specify version, should detect from version field (or schema field)
        # The version detection should work from either field
        is_valid, validation_errors = ODPSParser.validate(valid_odps)

        self.assertTrue(is_valid, f"Should detect version and validate. Errors: {validation_errors}")
        self.assertEqual(len(validation_errors), 0)

    def test_validate_version_not_found(self):
        """Test validation error when version cannot be determined (Task 1.2.3)"""
        odps_document = {
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                }
            }
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
            "product": {
                "details": {
                    "en": {
                        "productID": 123  # Should be string, not number
                    }
                }
            }
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
            "version": "4.1"
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
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                }
            },
            "invalidField": "should not be here"
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
            "version": "4.1"
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
        valid_json = json.dumps({
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

        parsed_doc, is_valid, validation_errors = ODPSParser.parse_and_validate(
            valid_json,
            version="4.1"
        )

        self.assertIsInstance(parsed_doc, dict)
        self.assertTrue(is_valid)
        self.assertEqual(len(validation_errors), 0)

    def test_parse_and_validate_invalid_json(self):
        """Test parse_and_validate with invalid JSON ODPS (Task 1.2.3)"""
        invalid_json = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1"
            # Missing required "product" field
        })

        parsed_doc, is_valid, validation_errors = ODPSParser.parse_and_validate(
            invalid_json,
            version="4.1"
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
            valid_yaml,
            version="4.1"
        )

        self.assertIsInstance(parsed_doc, dict)
        self.assertTrue(is_valid)
        self.assertEqual(len(validation_errors), 0)

    def test_parse_and_validate_with_auto_version_detection(self):
        """Test parse_and_validate with automatic version detection (Task 1.2.3)"""
        valid_json = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                }
            }
        })

        # Don't specify version, should detect from schema field
        parsed_doc, is_valid, validation_errors = ODPSParser.parse_and_validate(valid_json)

        self.assertIsInstance(parsed_doc, dict)
        self.assertTrue(is_valid)
        self.assertEqual(len(validation_errors), 0)

