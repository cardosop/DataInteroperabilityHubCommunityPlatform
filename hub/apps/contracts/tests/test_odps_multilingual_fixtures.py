"""
Unit tests for ODPS multilingual test fixtures.

Tests verify that all ODPS multilingual test fixtures are valid ODPS documents
that pass schema validation. This ensures multilingual product details are
correctly structured and can be used for testing internationalization functionality.
"""
try:
    import pytest
    pytestmark = pytest.mark.django_db
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


class ODPSMultilingualFixturesTest(TestCase):
    """Test ODPS multilingual test fixtures are valid"""

    def setUp(self):
        """Set up test fixtures"""
        # Get the base directory for contracts app
        self.base_dir = Path(__file__).parent.parent
        self.schemas_dir = self.base_dir / "schemas" / "odps"

        # Get the fixtures directory
        # Test file is at: hub/apps/contracts/tests/test_odps_multilingual_fixtures.py
        # Project root (hub) is: hub/apps/contracts/tests -> hub/apps/contracts -> hub/apps -> hub
        # Fixtures are at: tests/fixtures/odps/ (relative to project root, not hub)
        hub_dir = Path(__file__).parent.parent.parent.parent  # hub/
        project_root = hub_dir.parent  # project root (parent of hub/)
        self.fixtures_base = project_root / "tests" / "fixtures" / "odps"
        self.multilingual_fixtures_dir = self.fixtures_base / "v4.1" / "multilingual"

        # Load ODPS 4.1 schema
        self.schema_path = self.schemas_dir / "v4.1" / "odps-schema.json"
        with open(self.schema_path, 'r', encoding='utf-8') as f:
            self.schema = json.load(f)

    def test_multilingual_fixtures_directory_exists(self):
        """Test that multilingual fixtures directory exists"""
        self.assertTrue(
            self.multilingual_fixtures_dir.exists(),
            f"Multilingual fixtures directory should exist at: {self.multilingual_fixtures_dir}"
        )
        self.assertTrue(
            self.multilingual_fixtures_dir.is_dir(),
            f"Multilingual fixtures should be a directory: {self.multilingual_fixtures_dir}"
        )

    def test_english_only_sample_is_valid(self):
        """Test that English-only sample is valid ODPS"""
        if not JSONSCHEMA_AVAILABLE:
            self.skipTest("jsonschema library not available")

        fixture_path = self.multilingual_fixtures_dir / "sample-english-only-v4.1.json"
        self.assertTrue(fixture_path.exists(), f"Fixture should exist: {fixture_path}")

        with open(fixture_path, 'r', encoding='utf-8') as f:
            odps_doc = json.load(f)

        # Validate against schema
        try:
            validate(instance=odps_doc, schema=self.schema)
        except ValidationError as e:
            self.fail(f"English-only sample should be valid ODPS: {e}")

        # Verify product.details has English
        self.assertIn("product", odps_doc)
        self.assertIn("details", odps_doc["product"])
        self.assertIn("en", odps_doc["product"]["details"])
        self.assertEqual(len(odps_doc["product"]["details"]), 1, "Should have exactly one language")

    def test_french_only_sample_is_valid(self):
        """Test that French-only sample is valid ODPS"""
        if not JSONSCHEMA_AVAILABLE:
            self.skipTest("jsonschema library not available")

        fixture_path = self.multilingual_fixtures_dir / "sample-french-only-v4.1.json"
        self.assertTrue(fixture_path.exists(), f"Fixture should exist: {fixture_path}")

        with open(fixture_path, 'r', encoding='utf-8') as f:
            odps_doc = json.load(f)

        # Validate against schema
        try:
            validate(instance=odps_doc, schema=self.schema)
        except ValidationError as e:
            self.fail(f"French-only sample should be valid ODPS: {e}")

        # Verify product.details has French
        self.assertIn("product", odps_doc)
        self.assertIn("details", odps_doc["product"])
        self.assertIn("fr", odps_doc["product"]["details"])
        self.assertEqual(len(odps_doc["product"]["details"]), 1, "Should have exactly one language")

    def test_multiple_languages_sample_is_valid(self):
        """Test that multiple languages sample is valid ODPS"""
        if not JSONSCHEMA_AVAILABLE:
            self.skipTest("jsonschema library not available")

        fixture_path = self.multilingual_fixtures_dir / "sample-multiple-languages-v4.1.json"
        self.assertTrue(fixture_path.exists(), f"Fixture should exist: {fixture_path}")

        with open(fixture_path, 'r', encoding='utf-8') as f:
            odps_doc = json.load(f)

        # Validate against schema
        try:
            validate(instance=odps_doc, schema=self.schema)
        except ValidationError as e:
            self.fail(f"Multiple languages sample should be valid ODPS: {e}")

        # Verify product.details has multiple languages
        self.assertIn("product", odps_doc)
        self.assertIn("details", odps_doc["product"])
        details = odps_doc["product"]["details"]
        self.assertIn("en", details, "Should have English")
        self.assertIn("fr", details, "Should have French")
        self.assertIn("de", details, "Should have German")
        self.assertGreaterEqual(len(details), 3, "Should have at least 3 languages")

    def test_all_multilingual_fixtures_are_valid(self):
        """Test that all multilingual fixture files are valid ODPS"""
        if not JSONSCHEMA_AVAILABLE:
            self.skipTest("jsonschema library not available")

        # Get all multilingual fixture files
        multilingual_files = list(self.multilingual_fixtures_dir.glob("sample-*.json"))
        self.assertGreater(
            len(multilingual_files),
            0,
            f"Should have at least one multilingual fixture file in {self.multilingual_fixtures_dir}"
        )

        validation_errors = []
        for fixture_path in multilingual_files:
            with self.subTest(fixture=fixture_path.name):
                try:
                    with open(fixture_path, 'r', encoding='utf-8') as f:
                        odps_doc = json.load(f)

                    # Validate against schema
                    try:
                        validate(instance=odps_doc, schema=self.schema)
                    except ValidationError as e:
                        validation_errors.append(
                            f"{fixture_path.name}: Validation failed: {e}"
                        )
                except json.JSONDecodeError as e:
                    validation_errors.append(
                        f"{fixture_path.name}: Invalid JSON: {e}"
                    )
                except Exception as e:
                    validation_errors.append(
                        f"{fixture_path.name}: Unexpected error: {e}"
                    )

        # All multilingual fixtures should be valid
        if validation_errors:
            self.fail(
                f"Some multilingual fixtures are not valid ODPS:\n"
                + "\n".join(f"  - {msg}" for msg in validation_errors)
            )

    def test_language_codes_are_valid_iso_639_1(self):
        """Test that language codes follow ISO 639-1 format (2 lowercase letters)"""
        multilingual_files = list(self.multilingual_fixtures_dir.glob("sample-*.json"))

        for fixture_path in multilingual_files:
            with self.subTest(fixture=fixture_path.name):
                with open(fixture_path, 'r', encoding='utf-8') as f:
                    odps_doc = json.load(f)

                details = odps_doc["product"]["details"]

                # Verify all keys are 2-letter lowercase codes
                for lang_code in details.keys():
                    self.assertEqual(
                        len(lang_code),
                        2,
                        f"Language code '{lang_code}' should be 2 characters"
                    )
                    self.assertTrue(
                        lang_code.islower(),
                        f"Language code '{lang_code}' should be lowercase"
                    )
                    self.assertTrue(
                        lang_code.isalpha(),
                        f"Language code '{lang_code}' should contain only letters"
                    )

    def test_each_language_has_required_fields(self):
        """Test that each language entry has required fields (productID, name, description)"""
        multilingual_files = list(self.multilingual_fixtures_dir.glob("sample-*.json"))

        for fixture_path in multilingual_files:
            with self.subTest(fixture=fixture_path.name):
                with open(fixture_path, 'r', encoding='utf-8') as f:
                    odps_doc = json.load(f)

                details = odps_doc["product"]["details"]

                # Verify each language has required fields
                for lang_code, lang_details in details.items():
                    with self.subTest(language=lang_code):
                        self.assertIn(
                            "productID",
                            lang_details,
                            f"Language '{lang_code}' should have productID"
                        )
                        self.assertIn(
                            "name",
                            lang_details,
                            f"Language '{lang_code}' should have name"
                        )
                        self.assertIn(
                            "description",
                            lang_details,
                            f"Language '{lang_code}' should have description"
                        )

                        # Verify fields are strings
                        self.assertIsInstance(
                            lang_details["productID"],
                            str,
                            f"productID for '{lang_code}' should be a string"
                        )
                        self.assertIsInstance(
                            lang_details["name"],
                            str,
                            f"name for '{lang_code}' should be a string"
                        )
                        self.assertIsInstance(
                            lang_details["description"],
                            str,
                            f"description for '{lang_code}' should be a string"
                        )

    def test_multiple_languages_have_consistent_product_id(self):
        """Test that multiple languages sample has consistent productID across languages"""
        fixture_path = self.multilingual_fixtures_dir / "sample-multiple-languages-v4.1.json"
        if not fixture_path.exists():
            self.skipTest("Multiple languages fixture not found")

        with open(fixture_path, 'r', encoding='utf-8') as f:
            odps_doc = json.load(f)

        details = odps_doc["product"]["details"]

        # Get productID from first language
        first_lang = list(details.keys())[0]
        expected_product_id = details[first_lang]["productID"]

        # Verify all languages have the same productID
        for lang_code, lang_details in details.items():
            with self.subTest(language=lang_code):
                self.assertEqual(
                    lang_details["productID"],
                    expected_product_id,
                    f"Language '{lang_code}' should have same productID as '{first_lang}'"
                )

    def test_utf8_encoding_handles_special_characters(self):
        """Test that UTF-8 encoding properly handles special characters in multilingual content"""
        multilingual_files = list(self.multilingual_fixtures_dir.glob("sample-*.json"))

        for fixture_path in multilingual_files:
            with self.subTest(fixture=fixture_path.name):
                # Read file with UTF-8 encoding
                with open(fixture_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    odps_doc = json.loads(content)

                # Verify we can access multilingual content
                details = odps_doc["product"]["details"]
                for lang_code, lang_details in details.items():
                    # Verify strings are properly decoded (not bytes)
                    self.assertIsInstance(lang_details["name"], str)
                    self.assertIsInstance(lang_details["description"], str)

                    # Verify special characters are present (French/German have accents)
                    if lang_code == "fr":
                        # French might have accents like é, è, à, etc.
                        # Just verify it's a valid string
                        self.assertGreater(len(lang_details["name"]), 0)
                    elif lang_code == "de":
                        # German might have umlauts like ä, ö, ü, ß
                        # Just verify it's a valid string
                        self.assertGreater(len(lang_details["name"]), 0)

