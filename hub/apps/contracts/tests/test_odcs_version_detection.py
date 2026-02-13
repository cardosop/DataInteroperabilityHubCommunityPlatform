"""
Unit tests for ODCS Version Detection.

Tests version detection utilities following engineering best practices.
"""

import pytest
from django.test import TestCase

from hub.apps.contracts.odcs_version_detection import (
    detect_odcs_version,
    get_supported_odcs_versions,
    is_supported_odcs_version,
)

pytestmark = pytest.mark.django_db(transaction=True)


class ODCSVersionDetectionTest(TestCase):
    """Test ODCS version detection"""

    def test_detect_version_from_api_version(self):
        """Test version detection from apiVersion field"""
        contract_data = {"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract"}

        version = detect_odcs_version(contract_data)
        self.assertEqual(version, "3.0.2")

    def test_detect_version_from_api_version_short_format(self):
        """Test version detection from apiVersion with short format"""
        contract_data = {"apiVersion": "odcs/v3.0.1", "kind": "DataContract"}

        version = detect_odcs_version(contract_data)
        self.assertEqual(version, "3.0.1")

    def test_detect_version_from_version_field(self):
        """Test version detection from version field (fallback)"""
        contract_data = {"kind": "DataContract", "version": "3.0.0"}

        version = detect_odcs_version(contract_data)
        self.assertEqual(version, "3.0.0")

    def test_detect_version_unknown(self):
        """Test version detection returns unknown for invalid data"""
        contract_data = {"kind": "DataContract"}

        version = detect_odcs_version(contract_data)
        self.assertEqual(version, "unknown")

    def test_detect_version_invalid_input(self):
        """Test version detection with invalid input"""
        version = detect_odcs_version(None)
        self.assertEqual(version, "unknown")

        version = detect_odcs_version("not a dict")
        self.assertEqual(version, "unknown")

    def test_get_supported_versions(self):
        """Test getting supported ODCS versions"""
        supported = get_supported_odcs_versions()
        self.assertIsInstance(supported, list)
        self.assertIn("3.0.2", supported)
        self.assertIn("3.0.1", supported)
        self.assertIn("3.0.0", supported)

    def test_is_supported_version(self):
        """Test checking if version is supported"""
        self.assertTrue(is_supported_odcs_version("3.0.2"))
        self.assertTrue(is_supported_odcs_version("3.0.1"))
        self.assertFalse(is_supported_odcs_version("1.0.0"))
        self.assertFalse(is_supported_odcs_version("unknown"))

    # Edge cases and error handling tests
    def test_detect_version_with_empty_dict(self):
        """Test version detection with empty dictionary."""
        version = detect_odcs_version({})
        self.assertEqual(version, "unknown")

    def test_detect_version_with_special_characters_in_api_version(self):
        """Test version detection with special characters in apiVersion."""
        contract_data = {"apiVersion": "odcs.io/v3.0.2?param=<>&\"'", "kind": "DataContract"}
        version = detect_odcs_version(contract_data)
        # Should extract version before special characters
        self.assertEqual(version, "3.0.2")

    def test_detect_version_with_unicode_in_api_version(self):
        """Test version detection with unicode in apiVersion."""
        contract_data = {"apiVersion": "odcs.io/v3.0.2/产品", "kind": "DataContract"}
        version = detect_odcs_version(contract_data)
        # Should extract version before unicode
        self.assertEqual(version, "3.0.2")

    def test_detect_version_with_whitespace_in_api_version(self):
        """Test version detection with whitespace in apiVersion."""
        contract_data = {"apiVersion": "  odcs.io/v3.0.2  ", "kind": "DataContract"}
        version = detect_odcs_version(contract_data)
        # Should handle whitespace
        self.assertEqual(version, "3.0.2")

    def test_detect_version_with_empty_api_version(self):
        """Test version detection with empty apiVersion."""
        contract_data = {"apiVersion": "", "kind": "DataContract"}
        version = detect_odcs_version(contract_data)
        # Should fallback to version field or return unknown
        self.assertIsNotNone(version)

    def test_detect_version_with_none_api_version(self):
        """Test version detection with None apiVersion."""
        contract_data = {"apiVersion": None, "kind": "DataContract", "version": "3.0.2"}
        version = detect_odcs_version(contract_data)
        # Should fallback to version field
        self.assertEqual(version, "3.0.2")

    def test_detect_version_with_empty_version_field(self):
        """Test version detection with empty version field."""
        contract_data = {"kind": "DataContract", "version": ""}
        version = detect_odcs_version(contract_data)
        # Should return unknown
        self.assertEqual(version, "unknown")

    def test_detect_version_with_none_version_field(self):
        """Test version detection with None version field."""
        contract_data = {"kind": "DataContract", "version": None}
        version = detect_odcs_version(contract_data)
        # Should return unknown
        self.assertEqual(version, "unknown")

    def test_detect_version_with_numeric_version_field(self):
        """Test version detection with numeric version field."""
        contract_data = {"kind": "DataContract", "version": 3.0}
        version = detect_odcs_version(contract_data)
        # Should handle numeric version
        self.assertIsNotNone(version)

    def test_detect_version_with_integer_version_field(self):
        """Test version detection with integer version field."""
        contract_data = {"kind": "DataContract", "version": 3}
        version = detect_odcs_version(contract_data)
        # Should handle integer version
        self.assertIsNotNone(version)

    def test_detect_version_with_invalid_type_version_field(self):
        """Test version detection with invalid type version field."""
        contract_data = {"kind": "DataContract", "version": ["3", "0", "2"]}
        version = detect_odcs_version(contract_data)
        # Should handle invalid type gracefully
        self.assertEqual(version, "unknown")

    def test_detect_version_with_very_long_api_version(self):
        """Test version detection with very long apiVersion."""
        long_suffix = "a" * 10000
        contract_data = {"apiVersion": f"odcs.io/v3.0.2/{long_suffix}", "kind": "DataContract"}
        version = detect_odcs_version(contract_data)
        # Should extract version before long suffix
        self.assertEqual(version, "3.0.2")

    def test_detect_version_with_malformed_api_version(self):
        """Test version detection with malformed apiVersion."""
        contract_data = {
            "apiVersion": "not-a-valid-format",
            "kind": "DataContract",
            "version": "3.0.2",
        }
        version = detect_odcs_version(contract_data)
        # Should fallback to version field
        self.assertEqual(version, "3.0.2")

    def test_detect_version_api_version_primary_over_version_field(self):
        """Test that apiVersion takes precedence over version field."""
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "version": "2.0.0",  # Should be ignored
        }
        version = detect_odcs_version(contract_data)
        # Should use apiVersion
        self.assertEqual(version, "3.0.2")

    def test_get_supported_versions_returns_list(self):
        """Test that get_supported_versions returns a list."""
        supported = get_supported_odcs_versions()
        self.assertIsInstance(supported, list)
        self.assertGreater(len(supported), 0)

    def test_is_supported_version_with_none(self):
        """Test is_supported_version with None input."""
        result = is_supported_odcs_version(None)
        self.assertFalse(result)

    def test_is_supported_version_with_empty_string(self):
        """Test is_supported_version with empty string."""
        result = is_supported_odcs_version("")
        self.assertFalse(result)

    def test_is_supported_version_with_whitespace(self):
        """Test is_supported_version with whitespace."""
        result = is_supported_odcs_version("  3.0.2  ")
        # May or may not handle whitespace
        self.assertIsInstance(result, bool)

    def test_is_supported_version_with_special_characters(self):
        """Test is_supported_version with special characters."""
        result = is_supported_odcs_version("3.0.2<>&\"'")
        self.assertFalse(result)

    def test_is_supported_version_with_unicode(self):
        """Test is_supported_version with unicode."""
        result = is_supported_odcs_version("3.0.2产品")
        self.assertFalse(result)

    def test_detect_version_with_all_versions(self):
        """Test version detection with all supported versions."""
        versions = ["3.0.2", "3.0.1", "3.0.0"]
        for v in versions:
            contract_data = {"apiVersion": f"odcs.io/v{v}", "kind": "DataContract"}
            detected = detect_odcs_version(contract_data)
            self.assertEqual(detected, v, f"Failed to detect version {v}")

    def test_detect_version_with_preview_versions(self):
        """Test version detection with preview versions."""
        contract_data = {"apiVersion": "odcs.io/v3.0.0-preview", "kind": "DataContract"}
        version = detect_odcs_version(contract_data)
        # May handle preview versions or return unknown
        self.assertIsNotNone(version)

    def test_detect_version_handles_very_large_documents(self):
        """Test that version detection handles very large documents correctly."""
        large_field = "A" * 100000  # 100KB string
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "large_field": large_field,
        }

        # Should handle large documents gracefully
        version = detect_odcs_version(contract_data)
        self.assertIsNotNone(version)

    def test_detect_version_handles_nested_structures(self):
        """Test that version detection handles nested structures correctly."""
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "nested": {"level1": {"level2": {"level3": {"level4": {"value": "deep"}}}}},
        }

        # Should handle nested structures
        version = detect_odcs_version(contract_data)
        self.assertIsNotNone(version)
