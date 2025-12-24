"""
Unit tests for ODPS version detection (Task 1.2.2)

Tests cover:
1. Version detection from schema URL (primary method)
2. Version detection from version field (fallback)
3. All supported versions: 4.1, 4.0, 3.x, 2.x, 1.x
4. Unknown version handling
5. Edge cases and error handling
"""
from django.test import TestCase
from hub.apps.contracts.odps_version_detection import (
    detect_odps_version,
    _extract_version_from_schema_url,
    _normalize_version_from_field,
    _normalize_version_string
)


class ODPSVersionDetectionTest(TestCase):
    """Test ODPS version detection functionality"""

    def test_detect_version_4_1_from_schema_url_opendataproducts_org(self):
        """Test: Unit test for version 4.1 detection from opendataproducts.org schema URL"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {"en": {"productID": "test"}}}
        }
        version = detect_odps_version(contract_data)
        self.assertEqual(version, "4.1")

    def test_detect_version_4_1_from_schema_url_schemas_opendataproducts_io(self):
        """Test: Unit test for version 4.1 detection from schemas.opendataproducts.io URL"""
        contract_data = {
            "schema": "https://schemas.opendataproducts.io/spec/v4.1/product.json",
            "version": "4.1"
        }
        version = detect_odps_version(contract_data)
        self.assertEqual(version, "4.1")

    def test_detect_version_4_1_from_version_field(self):
        """Test: Unit test for version 4.1 detection from version field (fallback)"""
        contract_data = {
            "version": "4.1",
            "product": {"details": {"en": {"productID": "test"}}}
        }
        version = detect_odps_version(contract_data)
        self.assertEqual(version, "4.1")

    def test_detect_version_4_0_from_schema_url(self):
        """Test: Unit test for version 4.0 detection"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.0",
            "version": "4.0"
        }
        version = detect_odps_version(contract_data)
        self.assertEqual(version, "4.0")

    def test_detect_version_4_0_from_version_field(self):
        """Test: Unit test for version 4.0 detection from version field"""
        contract_data = {
            "version": "4.0"
        }
        version = detect_odps_version(contract_data)
        self.assertEqual(version, "4.0")

    def test_detect_version_3_x_from_schema_url_3_9(self):
        """Test: Unit test for version 3.x detection (3.9)"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v3.9",
            "version": "3.9"
        }
        version = detect_odps_version(contract_data)
        self.assertEqual(version, "3.x")

    def test_detect_version_3_x_from_schema_url_3_8(self):
        """Test: Unit test for version 3.x detection (3.8)"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v3.8",
            "version": "3.8"
        }
        version = detect_odps_version(contract_data)
        self.assertEqual(version, "3.x")

    def test_detect_version_3_x_from_version_field(self):
        """Test: Unit test for version 3.x detection from version field"""
        contract_data = {
            "version": "3.9"
        }
        version = detect_odps_version(contract_data)
        self.assertEqual(version, "3.x")

    def test_detect_version_2_x_from_schema_url_2_9(self):
        """Test: Unit test for version 2.x detection (2.9)"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v2.9",
            "version": "2.9"
        }
        version = detect_odps_version(contract_data)
        self.assertEqual(version, "2.x")

    def test_detect_version_2_x_from_schema_url_2_8(self):
        """Test: Unit test for version 2.x detection (2.8)"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v2.8",
            "version": "2.8"
        }
        version = detect_odps_version(contract_data)
        self.assertEqual(version, "2.x")

    def test_detect_version_2_x_from_version_field(self):
        """Test: Unit test for version 2.x detection from version field"""
        contract_data = {
            "version": "2.9"
        }
        version = detect_odps_version(contract_data)
        self.assertEqual(version, "2.x")

    def test_detect_version_1_x_from_schema_url_1_9(self):
        """Test: Unit test for version 1.x detection (1.9)"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v1.9",
            "version": "1.9"
        }
        version = detect_odps_version(contract_data)
        self.assertEqual(version, "1.x")

    def test_detect_version_1_x_from_schema_url_1_8(self):
        """Test: Unit test for version 1.x detection (1.8)"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v1.8",
            "version": "1.8"
        }
        version = detect_odps_version(contract_data)
        self.assertEqual(version, "1.x")

    def test_detect_version_1_x_from_version_field(self):
        """Test: Unit test for version 1.x detection from version field"""
        contract_data = {
            "version": "1.9"
        }
        version = detect_odps_version(contract_data)
        self.assertEqual(version, "1.x")

    def test_detect_unknown_version_no_schema_no_version(self):
        """Test: Unit test for unknown version (no schema, no version field)"""
        contract_data = {
            "product": {"details": {"en": {"productID": "test"}}}
        }
        version = detect_odps_version(contract_data)
        self.assertEqual(version, "unknown")

    def test_detect_unknown_version_invalid_schema_url(self):
        """Test: Unit test for unknown version (invalid schema URL)"""
        contract_data = {
            "schema": "https://example.com/invalid/schema",
            "version": "invalid"
        }
        version = detect_odps_version(contract_data)
        self.assertEqual(version, "unknown")

    def test_detect_unknown_version_unsupported_major(self):
        """Test: Unit test for unknown version (unsupported major version)"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v5.0",
            "version": "5.0"
        }
        version = detect_odps_version(contract_data)
        self.assertEqual(version, "unknown")

    def test_schema_url_primary_over_version_field(self):
        """Test that schema URL takes precedence over version field"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "3.9"  # Should be ignored
        }
        version = detect_odps_version(contract_data)
        self.assertEqual(version, "4.1")

    def test_version_field_fallback_when_schema_missing(self):
        """Test that version field is used when schema URL is missing"""
        contract_data = {
            "version": "4.0"
        }
        version = detect_odps_version(contract_data)
        self.assertEqual(version, "4.0")

    def test_version_field_fallback_when_schema_invalid(self):
        """Test that version field is used when schema URL is invalid"""
        contract_data = {
            "schema": "invalid-url",
            "version": "4.1"
        }
        version = detect_odps_version(contract_data)
        self.assertEqual(version, "4.1")

    def test_extract_version_from_schema_url_various_formats(self):
        """Test _extract_version_from_schema_url with various URL formats"""
        test_cases = [
            ("https://opendataproducts.org/schema/v4.1", "4.1"),
            ("https://opendataproducts.org/schema/v4.0", "4.0"),
            ("https://opendataproducts.org/schema/v3.9", "3.x"),
            ("https://opendataproducts.org/schema/v2.9", "2.x"),
            ("https://opendataproducts.org/schema/v1.9", "1.x"),
            ("https://schemas.opendataproducts.io/spec/v4.1/product.json", "4.1"),
            ("https://schemas.opendataproducts.io/spec/v4.0/product.json", "4.0"),
            ("https://schemas.opendataproducts.io/spec/v3.9/product.json", "3.x"),
            ("http://opendataproducts.org/schema/v4.1", "4.1"),  # HTTP instead of HTTPS
            ("OPENDATAPRODUCTS.ORG/SCHEMA/V4.1", "4.1"),  # Case insensitive
        ]

        for url, expected in test_cases:
            with self.subTest(url=url, expected=expected):
                result = _extract_version_from_schema_url(url)
                self.assertEqual(result, expected, f"Failed for URL: {url}")

    def test_normalize_version_from_field_various_formats(self):
        """Test _normalize_version_from_field with various formats"""
        test_cases = [
            ("4.1", "4.1"),
            ("4.0", "4.0"),
            ("3.9", "3.x"),
            ("3.8", "3.x"),
            ("2.9", "2.x"),
            ("1.9", "1.x"),
            ("v4.1", "4.1"),  # With v prefix
            ("V4.0", "4.0"),  # With V prefix
            (4.1, "4.1"),  # Float
            (4, "4.0"),  # Integer
            ("4", "4.0"),  # String integer
        ]

        for version_input, expected in test_cases:
            with self.subTest(version_input=version_input, expected=expected):
                result = _normalize_version_from_field(version_input)
                self.assertEqual(result, expected, f"Failed for input: {version_input}")

    def test_normalize_version_string_edge_cases(self):
        """Test _normalize_version_string with edge cases"""
        test_cases = [
            ("4.1", "4.1"),
            ("4.0", "4.0"),
            ("4.2", "4.0"),  # Other 4.x -> 4.0
            ("3.9", "3.x"),
            ("3.0", "3.x"),
            ("2.9", "2.x"),
            ("1.9", "1.x"),
            ("3.x", "3.x"),  # Already normalized
            ("", "unknown"),
            (None, "unknown"),
            ("invalid", "unknown"),
            ("5.0", "unknown"),  # Unsupported major
            ("0.1", "unknown"),  # Unsupported major
        ]

        for version_str, expected in test_cases:
            with self.subTest(version_str=version_str, expected=expected):
                result = _normalize_version_string(version_str)
                self.assertEqual(result, expected, f"Failed for version: {version_str}")

    def test_detect_version_with_empty_dict(self):
        """Test version detection with empty dictionary"""
        version = detect_odps_version({})
        self.assertEqual(version, "unknown")

    def test_detect_version_with_none(self):
        """Test version detection with None input"""
        version = detect_odps_version(None)
        self.assertEqual(version, "unknown")

    def test_detect_version_with_invalid_type(self):
        """Test version detection with invalid input type"""
        version = detect_odps_version("not a dict")
        self.assertEqual(version, "unknown")

    def test_detect_version_schema_url_case_insensitive(self):
        """Test that schema URL matching is case insensitive"""
        contract_data = {
            "schema": "HTTPS://OPENDATAPRODUCTS.ORG/SCHEMA/V4.1"
        }
        version = detect_odps_version(contract_data)
        self.assertEqual(version, "4.1")

    def test_detect_version_with_whitespace(self):
        """Test version detection with whitespace in version field"""
        contract_data = {
            "version": "  4.1  "
        }
        version = detect_odps_version(contract_data)
        self.assertEqual(version, "4.1")

    def test_detect_version_4_1_from_schema_url_with_path(self):
        """Test version 4.1 detection from schema URL with additional path"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1/odps-schema.json"
        }
        version = detect_odps_version(contract_data)
        self.assertEqual(version, "4.1")

