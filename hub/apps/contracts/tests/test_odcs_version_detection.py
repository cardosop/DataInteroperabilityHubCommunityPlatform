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
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract"
        }

        version = detect_odcs_version(contract_data)
        self.assertEqual(version, "3.0.2")

    def test_detect_version_from_api_version_short_format(self):
        """Test version detection from apiVersion with short format"""
        contract_data = {
            "apiVersion": "odcs/v3.0.1",
            "kind": "DataContract"
        }

        version = detect_odcs_version(contract_data)
        self.assertEqual(version, "3.0.1")

    def test_detect_version_from_version_field(self):
        """Test version detection from version field (fallback)"""
        contract_data = {
            "kind": "DataContract",
            "version": "3.0.0"
        }

        version = detect_odcs_version(contract_data)
        self.assertEqual(version, "3.0.0")

    def test_detect_version_unknown(self):
        """Test version detection returns unknown for invalid data"""
        contract_data = {
            "kind": "DataContract"
        }

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

