"""
Unit tests for invalid ODPS test fixtures.

Tests verify that all invalid ODPS test fixtures correctly fail schema validation.
This ensures that our validation logic properly rejects invalid ODPS documents.
"""
try:
    import pytest
    pytestmark = pytest.mark.django_db(transaction=True)
except ImportError:
    # pytest not available, using Django test runner
    pytest = None
    pytestmark = None

import json
from pathlib import Path
from django.test import TestCase

try:
    import jsonschema
    from jsonschema import validate, Draft202012Validator, ValidationError
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False
    # Create mock classes for when jsonschema is not available
    class ValidationError(Exception):
        pass


class ODPSInvalidFixturesTest(TestCase):
    """Test invalid ODPS test fixtures fail validation"""

    def setUp(self):
        """Set up test fixtures"""
        # Get the base directory for contracts app
        self.base_dir = Path(__file__).parent.parent
        self.schemas_dir = self.base_dir / "schemas" / "odps"

        # Get the fixtures directory
        # Test file is at: hub/apps/contracts/tests/test_odps_invalid_fixtures.py
        # Project root (hub) is: hub/apps/contracts/tests -> hub/apps/contracts -> hub/apps -> hub
        # Fixtures are at: tests/fixtures/odps/ (relative to project root, not hub)
        # So from hub/, we need to go up one level to project root, then to tests/fixtures/odps
        hub_dir = Path(__file__).parent.parent.parent.parent  # hub/
        project_root = hub_dir.parent  # project root (parent of hub/)
        self.fixtures_base = project_root / "tests" / "fixtures" / "odps"
        self.invalid_fixtures_dir = self.fixtures_base / "v4.1" / "invalid"

        # Load ODPS 4.1 schema
        self.schema_path = self.schemas_dir / "v4.1" / "odps-schema.json"
        with open(self.schema_path, 'r', encoding='utf-8') as f:
            self.schema = json.load(f)

    def test_invalid_fixtures_directory_exists(self):
        """Test that invalid fixtures directory exists"""
        self.assertTrue(
            self.invalid_fixtures_dir.exists(),
            f"Invalid fixtures directory should exist at: {self.invalid_fixtures_dir}"
        )
        self.assertTrue(
            self.invalid_fixtures_dir.is_dir(),
            f"Invalid fixtures should be a directory: {self.invalid_fixtures_dir}"
        )

    def test_invalid_schema_violation_fails_validation(self):
        """Test that invalid schema violation sample fails validation"""
        if not JSONSCHEMA_AVAILABLE:
            self.skipTest("jsonschema library not available")

        fixture_path = self.invalid_fixtures_dir / "invalid-schema-violation-v4.1.json"
        self.assertTrue(fixture_path.exists(), f"Fixture should exist: {fixture_path}")

        with open(fixture_path, 'r', encoding='utf-8') as f:
            invalid_doc = json.load(f)

        # Validation should fail
        with self.assertRaises(ValidationError) as cm:
            validate(instance=invalid_doc, schema=self.schema)

        # Verify the error message indicates schema violation
        error_message = str(cm.exception).lower()
        self.assertTrue(
            "schema" in error_message or "pattern" in error_message,
            f"Error message should mention schema/pattern violation: {error_message}"
        )

    def test_invalid_missing_required_field_schema_fails_validation(self):
        """Test that invalid sample with missing 'schema' field fails validation"""
        if not JSONSCHEMA_AVAILABLE:
            self.skipTest("jsonschema library not available")

        fixture_path = self.invalid_fixtures_dir / "invalid-missing-required-field-v4.1.json"
        self.assertTrue(fixture_path.exists(), f"Fixture should exist: {fixture_path}")

        with open(fixture_path, 'r', encoding='utf-8') as f:
            invalid_doc = json.load(f)

        # Validation should fail
        with self.assertRaises(ValidationError) as cm:
            validate(instance=invalid_doc, schema=self.schema)

        # Verify the error message indicates missing required field
        error_message = str(cm.exception).lower()
        self.assertTrue(
            "schema" in error_message or "required" in error_message,
            f"Error message should mention missing required field: {error_message}"
        )

    def test_invalid_missing_required_field_product_fails_validation(self):
        """Test that invalid sample with missing 'product' field fails validation"""
        if not JSONSCHEMA_AVAILABLE:
            self.skipTest("jsonschema library not available")

        fixture_path = self.invalid_fixtures_dir / "invalid-missing-product-v4.1.json"
        self.assertTrue(fixture_path.exists(), f"Fixture should exist: {fixture_path}")

        with open(fixture_path, 'r', encoding='utf-8') as f:
            invalid_doc = json.load(f)

        # Validation should fail
        with self.assertRaises(ValidationError) as cm:
            validate(instance=invalid_doc, schema=self.schema)

        # Verify the error message indicates missing required field
        error_message = str(cm.exception).lower()
        self.assertTrue(
            "product" in error_message or "required" in error_message,
            f"Error message should mention missing required field: {error_message}"
        )

    def test_invalid_wrong_data_type_schema_fails_validation(self):
        """Test that invalid sample with wrong data type for 'schema' fails validation"""
        if not JSONSCHEMA_AVAILABLE:
            self.skipTest("jsonschema library not available")

        fixture_path = self.invalid_fixtures_dir / "invalid-wrong-data-type-schema-v4.1.json"
        self.assertTrue(fixture_path.exists(), f"Fixture should exist: {fixture_path}")

        with open(fixture_path, 'r', encoding='utf-8') as f:
            invalid_doc = json.load(f)

        # Validation should fail
        with self.assertRaises(ValidationError) as cm:
            validate(instance=invalid_doc, schema=self.schema)

        # Verify the error message indicates wrong data type
        error_message = str(cm.exception).lower()
        self.assertTrue(
            "schema" in error_message or "string" in error_message or "type" in error_message,
            f"Error message should mention wrong data type: {error_message}"
        )

    def test_invalid_wrong_data_type_product_fails_validation(self):
        """Test that invalid sample with wrong data type for 'product' fails validation"""
        if not JSONSCHEMA_AVAILABLE:
            self.skipTest("jsonschema library not available")

        fixture_path = self.invalid_fixtures_dir / "invalid-wrong-data-type-product-v4.1.json"
        self.assertTrue(fixture_path.exists(), f"Fixture should exist: {fixture_path}")

        with open(fixture_path, 'r', encoding='utf-8') as f:
            invalid_doc = json.load(f)

        # Validation should fail
        with self.assertRaises(ValidationError) as cm:
            validate(instance=invalid_doc, schema=self.schema)

        # Verify the error message indicates wrong data type
        error_message = str(cm.exception).lower()
        self.assertTrue(
            "product" in error_message or "object" in error_message or "type" in error_message,
            f"Error message should mention wrong data type: {error_message}"
        )

    def test_invalid_wrong_data_type_details_fails_validation(self):
        """Test that invalid sample with wrong data type for 'details' fails validation"""
        if not JSONSCHEMA_AVAILABLE:
            self.skipTest("jsonschema library not available")

        fixture_path = self.invalid_fixtures_dir / "invalid-wrong-data-type-details-v4.1.json"
        self.assertTrue(fixture_path.exists(), f"Fixture should exist: {fixture_path}")

        with open(fixture_path, 'r', encoding='utf-8') as f:
            invalid_doc = json.load(f)

        # Validation should fail
        with self.assertRaises(ValidationError) as cm:
            validate(instance=invalid_doc, schema=self.schema)

        # Verify the error message indicates wrong data type
        error_message = str(cm.exception).lower()
        self.assertTrue(
            "details" in error_message or "object" in error_message or "type" in error_message,
            f"Error message should mention wrong data type: {error_message}"
        )

    def test_invalid_schema_pattern_fails_validation(self):
        """Test that invalid sample with wrong schema URL pattern fails validation"""
        if not JSONSCHEMA_AVAILABLE:
            self.skipTest("jsonschema library not available")

        fixture_path = self.invalid_fixtures_dir / "invalid-schema-pattern-v4.1.json"
        self.assertTrue(fixture_path.exists(), f"Fixture should exist: {fixture_path}")

        with open(fixture_path, 'r', encoding='utf-8') as f:
            invalid_doc = json.load(f)

        # Validation should fail
        with self.assertRaises(ValidationError) as cm:
            validate(instance=invalid_doc, schema=self.schema)

        # Verify the error message indicates pattern violation
        error_message = str(cm.exception).lower()
        self.assertTrue(
            "schema" in error_message or "pattern" in error_message,
            f"Error message should mention pattern violation: {error_message}"
        )

    def test_invalid_version_pattern_fails_validation(self):
        """Test that invalid sample with wrong version pattern fails validation"""
        if not JSONSCHEMA_AVAILABLE:
            self.skipTest("jsonschema library not available")

        fixture_path = self.invalid_fixtures_dir / "invalid-version-pattern-v4.1.json"
        self.assertTrue(fixture_path.exists(), f"Fixture should exist: {fixture_path}")

        with open(fixture_path, 'r', encoding='utf-8') as f:
            invalid_doc = json.load(f)

        # Validation should fail
        with self.assertRaises(ValidationError) as cm:
            validate(instance=invalid_doc, schema=self.schema)

        # Verify the error message indicates pattern violation
        error_message = str(cm.exception).lower()
        self.assertTrue(
            "version" in error_message or "pattern" in error_message,
            f"Error message should mention pattern violation: {error_message}"
        )

    def test_all_invalid_fixtures_fail_validation(self):
        """Test that all invalid fixture files fail validation"""
        if not JSONSCHEMA_AVAILABLE:
            self.skipTest("jsonschema library not available")

        # Get all invalid fixture files
        invalid_files = list(self.invalid_fixtures_dir.glob("invalid-*.json"))
        self.assertGreater(
            len(invalid_files),
            0,
            f"Should have at least one invalid fixture file in {self.invalid_fixtures_dir}"
        )

        failed_validations = []
        for fixture_path in invalid_files:
            with self.subTest(fixture=fixture_path.name):
                try:
                    with open(fixture_path, 'r', encoding='utf-8') as f:
                        invalid_doc = json.load(f)

                    # Validation should fail
                    try:
                        validate(instance=invalid_doc, schema=self.schema)
                        # If we get here, validation passed when it shouldn't
                        failed_validations.append(
                            f"{fixture_path.name}: Validation passed but should have failed"
                        )
                    except ValidationError:
                        # Expected - validation should fail
                        pass
                except json.JSONDecodeError as e:
                    # JSON parsing error - this is also a validation failure
                    failed_validations.append(
                        f"{fixture_path.name}: Invalid JSON: {e}"
                    )
                except Exception as e:
                    # Other errors are also validation failures
                    failed_validations.append(
                        f"{fixture_path.name}: Unexpected error: {e}"
                    )

        # All invalid fixtures should have failed validation
        if failed_validations:
            self.fail(
                f"Some invalid fixtures did not fail validation as expected:\n"
                + "\n".join(f"  - {msg}" for msg in failed_validations)
            )

