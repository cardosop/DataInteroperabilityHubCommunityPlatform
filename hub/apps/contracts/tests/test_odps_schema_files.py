"""
Unit tests for ODPS JSON Schema files.

Tests verify that all ODPS schema files are:
1. Valid JSON
2. Valid JSON Schema (Draft 2020-12 or compatible)
"""

try:
    import pytest

    pytestmark = pytest.mark.django_db
except ImportError:
    # pytest not available, using Django test runner
    pytest = None
    pytestmark = None

import json
import os
from pathlib import Path

from django.test import TestCase

try:
    import jsonschema
    from jsonschema import Draft202012Validator, SchemaError, ValidationError, validate

    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False

    # Create mock classes for when jsonschema is not available
    class Draft202012Validator:
        pass

    class SchemaError(Exception):
        pass

    class ValidationError(Exception):
        pass


class ODPSSchemaFilesTest(TestCase):
    """Test ODPS JSON Schema files"""

    def setUp(self):
        """Set up test fixtures"""
        # Get the base directory for contracts app
        self.base_dir = Path(__file__).parent.parent
        self.schemas_dir = self.base_dir / "schemas" / "odps"
        self.required_versions = ["v4.1", "v4.0", "v3.x", "v2.x", "v1.x"]
        self.schema_filename = "odps-schema.json"

    def test_all_schema_files_exist(self):
        """Test that all required ODPS schema files exist"""
        for version in self.required_versions:
            schema_path = self.schemas_dir / version / self.schema_filename
            with self.subTest(version=version):
                self.assertTrue(
                    schema_path.exists(),
                    f"ODPS schema file should exist for version {version} at: {schema_path}",
                )
                self.assertTrue(
                    schema_path.is_file(),
                    f"ODPS schema file should be a file for version {version}: {schema_path}",
                )

    def test_all_schema_files_are_valid_json(self):
        """Test that all ODPS schema files are valid JSON"""
        for version in self.required_versions:
            schema_path = self.schemas_dir / version / self.schema_filename
            with self.subTest(version=version):
                # Read and parse JSON
                try:
                    with open(schema_path, encoding="utf-8") as f:
                        schema_data = json.load(f)

                    # Verify it's a dictionary/object
                    self.assertIsInstance(
                        schema_data,
                        dict,
                        f"ODPS schema file for version {version} should be a JSON object",
                    )

                    # Verify it has required top-level properties
                    self.assertIn(
                        "$schema",
                        schema_data,
                        f"ODPS schema file for version {version} should have $schema property",
                    )
                    self.assertIn(
                        "type",
                        schema_data,
                        f"ODPS schema file for version {version} should have type property",
                    )

                except json.JSONDecodeError as e:
                    self.fail(f"ODPS schema file for version {version} is not valid JSON: {e}")
                except Exception as e:
                    self.fail(f"Error reading ODPS schema file for version {version}: {e}")

    def test_all_schema_files_have_required_structure(self):
        """Test that all ODPS schema files have required JSON Schema structure"""
        for version in self.required_versions:
            schema_path = self.schemas_dir / version / self.schema_filename
            with self.subTest(version=version):
                with open(schema_path, encoding="utf-8") as f:
                    schema_data = json.load(f)

                # Verify required JSON Schema properties
                required_properties = ["$schema", "type"]
                for prop in required_properties:
                    self.assertIn(
                        prop,
                        schema_data,
                        f"ODPS schema file for version {version} should have {prop} property",
                    )

                # Verify $schema points to a valid JSON Schema draft
                schema_url = schema_data.get("$schema", "")
                self.assertTrue(
                    schema_url.startswith("https://json-schema.org/draft/"),
                    f"ODPS schema file for version {version} should have valid $schema URL",
                )

                # Verify type is "object" (for object schemas)
                schema_type = schema_data.get("type")
                if schema_type:
                    self.assertIn(
                        schema_type,
                        ["object", "array"],
                        f"ODPS schema file for version {version} should have type 'object' or 'array'",
                    )

    def test_all_schema_files_are_valid_json_schema(self):
        """Test that all ODPS schema files are valid JSON Schema"""
        if not JSONSCHEMA_AVAILABLE:
            self.skipTest("jsonschema library not available")

        for version in self.required_versions:
            schema_path = self.schemas_dir / version / self.schema_filename
            with self.subTest(version=version):
                with open(schema_path, encoding="utf-8") as f:
                    schema_data = json.load(f)

                # Validate that the schema itself is valid JSON Schema
                try:
                    # Try to create a validator - this will raise SchemaError if invalid
                    Draft202012Validator.check_schema(schema_data)
                except SchemaError as e:
                    self.fail(
                        f"ODPS schema file for version {version} is not valid JSON Schema: {e}"
                    )
                except Exception:
                    # For older drafts, try basic validation
                    try:
                        validate(instance={}, schema=schema_data)
                    except Exception as validation_error:
                        self.fail(
                            f"ODPS schema file for version {version} validation failed: {validation_error}"
                        )

    def test_schema_files_can_validate_sample_odps_documents(self):
        """Test that schema files can validate sample ODPS documents"""
        if not JSONSCHEMA_AVAILABLE:
            self.skipTest("jsonschema library not available")

        # Create minimal valid ODPS documents for each version
        sample_documents = {
            "v4.1": {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "version": "4.1",
                "product": {
                    "details": {
                        "en": {
                            "productID": "test-product-1",
                            "name": "Test Product",
                            "description": "A test product",
                        }
                    }
                },
            },
            "v4.0": {
                "schema": "https://opendataproducts.org/schema/v4.0",
                "version": "4.0",
                "product": {
                    "details": {
                        "en": {
                            "productID": "test-product-1",
                            "name": "Test Product",
                            "description": "A test product",
                        }
                    }
                },
            },
            "v3.x": {
                "schema": "https://opendataproducts.org/schema/v3.9",
                "version": "3.9",
                "product": {
                    "details": {
                        "en": {
                            "productID": "test-product-1",
                            "name": "Test Product",
                            "description": "A test product",
                        }
                    }
                },
            },
            "v2.x": {
                "schema": "https://opendataproducts.org/schema/v2.9",
                "version": "2.9",
                "product": {
                    "details": {
                        "en": {
                            "productID": "test-product-1",
                            "name": "Test Product",
                            "description": "A test product",
                        }
                    }
                },
            },
            "v1.x": {
                "schema": "https://opendataproducts.org/schema/v1.9",
                "version": "1.9",
                "product": {
                    "details": {
                        "en": {
                            "productID": "test-product-1",
                            "name": "Test Product",
                            "description": "A test product",
                        }
                    }
                },
            },
        }

        for version in self.required_versions:
            schema_path = self.schemas_dir / version / self.schema_filename
            sample_doc = sample_documents.get(version, {})

            if not sample_doc:
                continue

            with self.subTest(version=version):
                with open(schema_path, encoding="utf-8") as f:
                    schema_data = json.load(f)

                try:
                    # Validate sample document against schema
                    validate(instance=sample_doc, schema=schema_data)
                except ValidationError as e:
                    self.fail(
                        f"ODPS schema file for version {version} failed to validate sample document: {e}"
                    )
                except Exception as e:
                    # If validation fails for other reasons, that's also a problem
                    self.fail(
                        f"Error validating sample document against schema for version {version}: {e}"
                    )

    def test_schema_files_have_correct_naming(self):
        """Test that schema files follow the correct naming convention"""
        for version in self.required_versions:
            schema_path = self.schemas_dir / version / self.schema_filename
            with self.subTest(version=version):
                # Verify filename is exactly "odps-schema.json"
                self.assertEqual(
                    schema_path.name,
                    self.schema_filename,
                    f"ODPS schema file for version {version} should be named '{self.schema_filename}'",
                )

    def test_schema_files_are_readable(self):
        """Test that all schema files are readable and have content"""
        for version in self.required_versions:
            schema_path = self.schemas_dir / version / self.schema_filename
            with self.subTest(version=version):
                # Verify file is readable
                self.assertTrue(
                    os.access(schema_path, os.R_OK),
                    f"ODPS schema file for version {version} should be readable",
                )

                # Verify file has content (not empty)
                file_size = schema_path.stat().st_size
                self.assertGreater(
                    file_size, 0, f"ODPS schema file for version {version} should not be empty"
                )

                # Verify file has reasonable size (not suspiciously large)
                self.assertLess(
                    file_size,
                    10 * 1024 * 1024,  # 10MB max
                    f"ODPS schema file for version {version} should be reasonable size (<10MB)",
                )

    def test_schema_files_have_version_specific_identifiers(self):
        """Test that schema files have version-specific identifiers in their content"""
        for version in self.required_versions:
            schema_path = self.schemas_dir / version / self.schema_filename
            with self.subTest(version=version):
                with open(schema_path, encoding="utf-8") as f:
                    schema_data = json.load(f)

                # Verify $id contains version information
                schema_id = schema_data.get("$id", "")
                self.assertIn(
                    version.replace(".x", "").replace("v", ""),
                    schema_id,
                    f"ODPS schema file for version {version} should have version in $id",
                )

                # Verify title contains version information
                title = schema_data.get("title", "")
                self.assertIn(
                    version.replace("v", "").upper(),
                    title.upper(),
                    f"ODPS schema file for version {version} should have version in title",
                )
