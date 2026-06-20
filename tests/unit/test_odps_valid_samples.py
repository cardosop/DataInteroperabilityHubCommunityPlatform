"""
Unit tests for valid ODPS test sample files.

Tests verify that all valid ODPS sample files:
1. Are valid JSON
2. Pass schema validation against their respective ODPS schemas
3. Contain all required fields
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
    from jsonschema import Draft202012Validator, ValidationError, validate

    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False
    ValidationError = Exception


class ODPSValidSamplesTest(TestCase):
    """Test valid ODPS sample files"""

    def setUp(self):
        """Set up test fixtures"""
        # Get the base directory for tests
        self.base_dir = Path(__file__).parent.parent.parent
        self.fixtures_dir = self.base_dir / "tests" / "fixtures" / "odps"

        # Import ODPS schema loading utility
        from hub.apps.contracts.odps_schema import load_odps_schema

        self.load_odps_schema = load_odps_schema

        # Map version directories to version strings for schema loading
        self.version_map = {
            "v4.1": "4.1",
            "v4.0": "4.0",
            "v3.x": "3.x",
            "v2.x": "2.x",
            "v1.x": "1.x",
        }

    def test_v4_1_valid_sample_exists_and_is_valid_json(self):
        """Test that v4.1 valid sample file exists and is valid JSON"""
        sample_path = self.fixtures_dir / "v4.1" / "valid" / "sample-valid-v4.1.json"

        self.assertTrue(
            sample_path.exists(), f"Valid ODPS 4.1 sample file should exist at: {sample_path}"
        )

        try:
            with open(sample_path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertIsInstance(data, dict, "Sample file should contain a JSON object")
        except json.JSONDecodeError as e:
            self.fail(f"Valid ODPS 4.1 sample file is not valid JSON: {e}")

    def test_v4_1_valid_sample_passes_schema_validation(self):
        """Test that v4.1 valid sample passes schema validation"""
        if not JSONSCHEMA_AVAILABLE:
            self.skipTest("jsonschema library not available")

        sample_path = self.fixtures_dir / "v4.1" / "valid" / "sample-valid-v4.1.json"
        schema = self.load_odps_schema("4.1")

        with open(sample_path, encoding="utf-8") as f:
            sample_data = json.load(f)

        try:
            validate(instance=sample_data, schema=schema)
        except ValidationError as e:
            error_details = [f"Error: {e.message}"]
            if hasattr(e, "absolute_path") and e.absolute_path:
                error_details.append(f"Instance path: {list(e.absolute_path)}")
            if hasattr(e, "schema_path") and e.schema_path:
                error_details.append(f"Schema path: {list(e.schema_path)}")
            error_details.append(f"Sample file: {sample_path}")
            self.fail(
                "Valid ODPS 4.1 sample file failed schema validation:\n" + "\n".join(error_details)
            )
        except Exception as e:
            self.fail(
                f"Unexpected error validating ODPS 4.1 sample file: {type(e).__name__}: {e}\n"
                f"Sample file: {sample_path}"
            )

    def test_v4_0_valid_sample_exists_and_is_valid_json(self):
        """Test that v4.0 valid sample file exists and is valid JSON"""
        sample_path = self.fixtures_dir / "v4.0" / "valid" / "sample-valid-v4.0.json"

        self.assertTrue(
            sample_path.exists(), f"Valid ODPS 4.0 sample file should exist at: {sample_path}"
        )

        try:
            with open(sample_path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertIsInstance(data, dict, "Sample file should contain a JSON object")
        except json.JSONDecodeError as e:
            self.fail(f"Valid ODPS 4.0 sample file is not valid JSON: {e}")

    def test_v4_0_valid_sample_passes_schema_validation(self):
        """Test that v4.0 valid sample passes schema validation"""
        if not JSONSCHEMA_AVAILABLE:
            self.skipTest("jsonschema library not available")

        sample_path = self.fixtures_dir / "v4.0" / "valid" / "sample-valid-v4.0.json"
        schema = self.load_odps_schema("4.0")

        with open(sample_path, encoding="utf-8") as f:
            sample_data = json.load(f)

        try:
            validate(instance=sample_data, schema=schema)
        except ValidationError as e:
            error_details = [f"Error: {e.message}"]
            if hasattr(e, "absolute_path") and e.absolute_path:
                error_details.append(f"Instance path: {list(e.absolute_path)}")
            if hasattr(e, "schema_path") and e.schema_path:
                error_details.append(f"Schema path: {list(e.schema_path)}")
            error_details.append(f"Sample file: {sample_path}")
            self.fail(
                "Valid ODPS 4.0 sample file failed schema validation:\n" + "\n".join(error_details)
            )
        except Exception as e:
            self.fail(
                f"Unexpected error validating ODPS 4.0 sample file: {type(e).__name__}: {e}\n"
                f"Sample file: {sample_path}"
            )

    def test_v3_x_valid_sample_exists_and_is_valid_json(self):
        """Test that v3.x valid sample file exists and is valid JSON"""
        sample_path = self.fixtures_dir / "v3.x" / "valid" / "sample-valid-v3.9.json"

        self.assertTrue(
            sample_path.exists(), f"Valid ODPS 3.x sample file should exist at: {sample_path}"
        )

        try:
            with open(sample_path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertIsInstance(data, dict, "Sample file should contain a JSON object")
        except json.JSONDecodeError as e:
            self.fail(f"Valid ODPS 3.x sample file is not valid JSON: {e}")

    def test_v3_x_valid_sample_passes_schema_validation(self):
        """Test that v3.x valid sample passes schema validation"""
        if not JSONSCHEMA_AVAILABLE:
            self.skipTest("jsonschema library not available")

        sample_path = self.fixtures_dir / "v3.x" / "valid" / "sample-valid-v3.9.json"
        schema = self.load_odps_schema("3.x")

        with open(sample_path, encoding="utf-8") as f:
            sample_data = json.load(f)

        try:
            validate(instance=sample_data, schema=schema)
        except ValidationError as e:
            error_details = [f"Error: {e.message}"]
            if hasattr(e, "absolute_path") and e.absolute_path:
                error_details.append(f"Instance path: {list(e.absolute_path)}")
            if hasattr(e, "schema_path") and e.schema_path:
                error_details.append(f"Schema path: {list(e.schema_path)}")
            error_details.append(f"Sample file: {sample_path}")
            self.fail(
                "Valid ODPS 3.x sample file failed schema validation:\n" + "\n".join(error_details)
            )
        except Exception as e:
            self.fail(
                f"Unexpected error validating ODPS 3.x sample file: {type(e).__name__}: {e}\n"
                f"Sample file: {sample_path}"
            )

    def test_v2_x_valid_sample_exists_and_is_valid_json(self):
        """Test that v2.x valid sample file exists and is valid JSON"""
        sample_path = self.fixtures_dir / "v2.x" / "valid" / "sample-valid-v2.9.json"

        self.assertTrue(
            sample_path.exists(), f"Valid ODPS 2.x sample file should exist at: {sample_path}"
        )

        try:
            with open(sample_path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertIsInstance(data, dict, "Sample file should contain a JSON object")
        except json.JSONDecodeError as e:
            self.fail(f"Valid ODPS 2.x sample file is not valid JSON: {e}")

    def test_v2_x_valid_sample_passes_schema_validation(self):
        """Test that v2.x valid sample passes schema validation"""
        if not JSONSCHEMA_AVAILABLE:
            self.skipTest("jsonschema library not available")

        sample_path = self.fixtures_dir / "v2.x" / "valid" / "sample-valid-v2.9.json"
        schema = self.load_odps_schema("2.x")

        with open(sample_path, encoding="utf-8") as f:
            sample_data = json.load(f)

        try:
            validate(instance=sample_data, schema=schema)
        except ValidationError as e:
            error_details = [f"Error: {e.message}"]
            if hasattr(e, "absolute_path") and e.absolute_path:
                error_details.append(f"Instance path: {list(e.absolute_path)}")
            if hasattr(e, "schema_path") and e.schema_path:
                error_details.append(f"Schema path: {list(e.schema_path)}")
            error_details.append(f"Sample file: {sample_path}")
            self.fail(
                "Valid ODPS 2.x sample file failed schema validation:\n" + "\n".join(error_details)
            )
        except Exception as e:
            self.fail(
                f"Unexpected error validating ODPS 2.x sample file: {type(e).__name__}: {e}\n"
                f"Sample file: {sample_path}"
            )

    def test_v1_x_valid_sample_exists_and_is_valid_json(self):
        """Test that v1.x valid sample file exists and is valid JSON"""
        sample_path = self.fixtures_dir / "v1.x" / "valid" / "sample-valid-v1.9.json"

        self.assertTrue(
            sample_path.exists(), f"Valid ODPS 1.x sample file should exist at: {sample_path}"
        )

        try:
            with open(sample_path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertIsInstance(data, dict, "Sample file should contain a JSON object")
        except json.JSONDecodeError as e:
            self.fail(f"Valid ODPS 1.x sample file is not valid JSON: {e}")

    def test_v1_x_valid_sample_passes_schema_validation(self):
        """Test that v1.x valid sample passes schema validation"""
        if not JSONSCHEMA_AVAILABLE:
            self.skipTest("jsonschema library not available")

        sample_path = self.fixtures_dir / "v1.x" / "valid" / "sample-valid-v1.9.json"
        schema = self.load_odps_schema("1.x")

        with open(sample_path, encoding="utf-8") as f:
            sample_data = json.load(f)

        try:
            validate(instance=sample_data, schema=schema)
        except ValidationError as e:
            error_details = [f"Error: {e.message}"]
            if hasattr(e, "absolute_path") and e.absolute_path:
                error_details.append(f"Instance path: {list(e.absolute_path)}")
            if hasattr(e, "schema_path") and e.schema_path:
                error_details.append(f"Schema path: {list(e.schema_path)}")
            error_details.append(f"Sample file: {sample_path}")
            self.fail(
                "Valid ODPS 1.x sample file failed schema validation:\n" + "\n".join(error_details)
            )
        except Exception as e:
            self.fail(
                f"Unexpected error validating ODPS 1.x sample file: {type(e).__name__}: {e}\n"
                f"Sample file: {sample_path}"
            )

    def test_all_valid_samples_have_required_fields(self):
        """Test that all valid samples have required fields (schema, version, product.details)"""
        version_samples = {
            "v4.1": "sample-valid-v4.1.json",
            "v4.0": "sample-valid-v4.0.json",
            "v3.x": "sample-valid-v3.9.json",
            "v2.x": "sample-valid-v2.9.json",
            "v1.x": "sample-valid-v1.9.json",
        }

        for version_dir, filename in version_samples.items():
            sample_path = self.fixtures_dir / version_dir / "valid" / filename

            with self.subTest(version=version_dir, file=filename):
                self.assertTrue(sample_path.exists(), f"Sample file should exist: {sample_path}")

                with open(sample_path, encoding="utf-8") as f:
                    data = json.load(f)

                # Check required top-level fields
                self.assertIn("schema", data, f"Sample {filename} should have 'schema' field")
                self.assertIn("version", data, f"Sample {filename} should have 'version' field")
                self.assertIn("product", data, f"Sample {filename} should have 'product' field")

                # Check required product.details
                self.assertIn(
                    "details",
                    data["product"],
                    f"Sample {filename} should have 'product.details' field",
                )
                self.assertIsInstance(
                    data["product"]["details"],
                    dict,
                    f"Sample {filename} 'product.details' should be an object",
                )

                # Check that details has at least one language entry
                self.assertGreater(
                    len(data["product"]["details"]),
                    0,
                    f"Sample {filename} 'product.details' should have at least one language",
                )

                # Check that each language entry has required fields
                for lang_code, lang_data in data["product"]["details"].items():
                    self.assertIn(
                        "productID",
                        lang_data,
                        f"Sample {filename} language '{lang_code}' should have 'productID'",
                    )
                    self.assertIn(
                        "name",
                        lang_data,
                        f"Sample {filename} language '{lang_code}' should have 'name'",
                    )
                    self.assertIn(
                        "description",
                        lang_data,
                        f"Sample {filename} language '{lang_code}' should have 'description'",
                    )

    def test_all_valid_samples_pass_schema_validation(self):
        """Test that all valid samples pass schema validation (comprehensive test)"""
        if not JSONSCHEMA_AVAILABLE:
            self.skipTest("jsonschema library not available")

        version_samples = {
            "4.1": ("v4.1", "sample-valid-v4.1.json"),
            "4.0": ("v4.0", "sample-valid-v4.0.json"),
            "3.x": ("v3.x", "sample-valid-v3.9.json"),
            "2.x": ("v2.x", "sample-valid-v2.9.json"),
            "1.x": ("v1.x", "sample-valid-v1.9.json"),
        }

        for version, (version_dir, filename) in version_samples.items():
            with self.subTest(version=version):
                sample_path = self.fixtures_dir / version_dir / "valid" / filename
                schema = self.load_odps_schema(version)

                with open(sample_path, encoding="utf-8") as f:
                    sample_data = json.load(f)

                try:
                    validate(instance=sample_data, schema=schema)
                except ValidationError as e:
                    # Provide detailed error information for debugging
                    error_details = []
                    error_details.append(f"Error: {e.message}")

                    # Add path information if available
                    if hasattr(e, "absolute_path") and e.absolute_path:
                        error_details.append(f"Instance path: {list(e.absolute_path)}")
                    if hasattr(e, "schema_path") and e.schema_path:
                        error_details.append(f"Schema path: {list(e.schema_path)}")
                    if hasattr(e, "context") and e.context:
                        error_details.append(f"Context: {[str(c) for c in e.context]}")

                    # Add sample file path for reference
                    error_details.append(f"Sample file: {sample_path}")

                    self.fail(
                        f"Valid ODPS {version} sample file '{filename}' failed schema validation:\n"
                        + "\n".join(error_details)
                    )
                except Exception as e:
                    # Catch any other unexpected errors
                    self.fail(
                        f"Unexpected error validating ODPS {version} sample file '{filename}': {type(e).__name__}: {e}\n"
                        f"Sample file: {sample_path}"
                    )
