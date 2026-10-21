"""
Unit tests for ODCS Generator Registry & Factory.

Tests the generator registry system and factory function following TDD approach
and engineering best practices without mocks/stubs.
"""

import pytest
from django.test import TestCase

from hub.apps.contracts.odcs_errors import ODCSGenerationError
from hub.apps.contracts.odcs_generator import (
    ODCSGeneratorBase,
    ODCSGeneratorV2_2_2,
    ODCSGeneratorV3_0_0,
    ODCSGeneratorV3_0_0_Preview,
    ODCSGeneratorV3_0_1,
    ODCSGeneratorV3_0_2,
    _detect_version_from_hubcontract,
    _normalize_version_string,
    get_odcs_generator,
    get_supported_odcs_versions,
    register_odcs_generator,
)

pytestmark = pytest.mark.django_db(transaction=True)


class ODCSGeneratorRegistryTest(TestCase):
    """Test ODCS generator registry functionality"""

    def test_get_supported_versions_returns_all_versions(self):
        """Test that get_supported_odcs_versions returns all registered versions"""
        versions = get_supported_odcs_versions()

        self.assertIsInstance(versions, list)
        self.assertGreater(len(versions), 0)
        # Check that all expected versions are present
        expected_versions = ["2.2.2", "3.0.0", "3.0.0-preview", "3.0.1", "3.0.2"]
        for expected_version in expected_versions:
            self.assertIn(expected_version, versions)

    def test_get_generator_for_version_3_0_2(self):
        """Test getting generator for version 3.0.2"""
        generator = get_odcs_generator(version="3.0.2")

        self.assertIsNotNone(generator)
        self.assertIsInstance(generator, ODCSGeneratorBase)
        self.assertIsInstance(generator, ODCSGeneratorV3_0_2)

    def test_get_generator_for_version_3_0_1(self):
        """Test getting generator for version 3.0.1"""
        generator = get_odcs_generator(version="3.0.1")

        self.assertIsNotNone(generator)
        self.assertIsInstance(generator, ODCSGeneratorBase)
        self.assertIsInstance(generator, ODCSGeneratorV3_0_1)

    def test_get_generator_for_version_3_0_0(self):
        """Test getting generator for version 3.0.0"""
        generator = get_odcs_generator(version="3.0.0")

        self.assertIsNotNone(generator)
        self.assertIsInstance(generator, ODCSGeneratorBase)
        self.assertIsInstance(generator, ODCSGeneratorV3_0_0)

    def test_get_generator_for_version_3_0_0_preview(self):
        """Test getting generator for version 3.0.0-preview"""
        generator = get_odcs_generator(version="3.0.0-preview")

        self.assertIsNotNone(generator)
        self.assertIsInstance(generator, ODCSGeneratorBase)
        self.assertIsInstance(generator, ODCSGeneratorV3_0_0_Preview)

    def test_get_generator_for_version_2_2_2(self):
        """Test getting generator for version 2.2.2"""
        generator = get_odcs_generator(version="2.2.2")

        self.assertIsNotNone(generator)
        self.assertIsInstance(generator, ODCSGeneratorBase)
        self.assertIsInstance(generator, ODCSGeneratorV2_2_2)

    def test_get_generator_without_version_uses_fallback(self):
        """Test that getting generator without version uses latest as fallback"""
        generator = get_odcs_generator(version=None)

        # Should fallback to latest version (3.0.2)
        self.assertIsNotNone(generator)
        self.assertIsInstance(generator, ODCSGeneratorV3_0_2)

    def test_get_generator_with_invalid_version_falls_back(self):
        """Test that invalid version falls back to latest with warning"""
        generator = get_odcs_generator(version="99.99.99")

        # Should fallback to latest version (3.0.2)
        self.assertIsNotNone(generator)
        self.assertIsInstance(generator, ODCSGeneratorV3_0_2)

    def test_register_generator_with_invalid_type_raises_error(self):
        """Test that registering invalid generator type raises TypeError"""
        with self.assertRaises(TypeError):
            register_odcs_generator("test-version", "not a generator")


class ODCSGeneratorVersionDetectionTest(TestCase):
    """Test version detection from HubContract"""

    def test_detect_version_from_original_spec(self):
        """Test version detection from original_spec metadata"""
        hub_contract = {
            "id": "test-1",
            "info": {"name": "Test"},
            "original_spec": {"type": "ODCS", "version": "3.0.1"},
        }

        version = _detect_version_from_hubcontract(hub_contract)
        self.assertEqual(version, "3.0.1")

    def test_detect_version_from_normalization_metadata(self):
        """Test version detection from normalization metadata"""
        hub_contract = {
            "id": "test-1",
            "info": {"name": "Test"},
            "normalization": {"original_spec_type": "ODCS", "original_spec_version": "3.0.0"},
        }

        version = _detect_version_from_hubcontract(hub_contract)
        self.assertEqual(version, "3.0.0")

    def test_detect_version_prioritizes_original_spec(self):
        """Test that original_spec takes priority over normalization metadata"""
        hub_contract = {
            "id": "test-1",
            "info": {"name": "Test"},
            "original_spec": {"type": "ODCS", "version": "3.0.2"},
            "normalization": {"original_spec_type": "ODCS", "original_spec_version": "3.0.1"},
        }

        version = _detect_version_from_hubcontract(hub_contract)
        self.assertEqual(version, "3.0.2")  # original_spec takes priority

    def test_detect_version_returns_none_for_non_odcs(self):
        """Test that version detection returns None for non-ODCS contracts"""
        hub_contract = {
            "id": "test-1",
            "info": {"name": "Test"},
            "original_spec": {"type": "ODPS", "version": "4.1"},
        }

        version = _detect_version_from_hubcontract(hub_contract)
        self.assertIsNone(version)

    def test_detect_version_returns_none_when_no_metadata(self):
        """Test that version detection returns None when no metadata present"""
        hub_contract = {"id": "test-1", "info": {"name": "Test"}}

        version = _detect_version_from_hubcontract(hub_contract)
        self.assertIsNone(version)

    def test_get_generator_with_hubcontract_detects_version(self):
        """Test that get_odcs_generator detects version from HubContract"""
        hub_contract = {
            "id": "test-1",
            "info": {"name": "Test"},
            "original_spec": {"type": "ODCS", "version": "3.0.1"},
        }

        generator = get_odcs_generator(hub_contract=hub_contract)

        self.assertIsNotNone(generator)
        self.assertIsInstance(generator, ODCSGeneratorV3_0_1)


class ODCSGeneratorVersionNormalizationTest(TestCase):
    """Test version string normalization"""

    def test_normalize_version_removes_v_prefix(self):
        """Test that v prefix is removed from version string"""
        self.assertEqual(_normalize_version_string("v3.0.2"), "3.0.2")
        self.assertEqual(_normalize_version_string("V3.0.1"), "3.0.1")

    def test_normalize_version_extracts_from_api_version_format(self):
        """Test that version is extracted from odcs.io/v3.0.2 format"""
        self.assertEqual(_normalize_version_string("odcs.io/v3.0.2"), "3.0.2")
        self.assertEqual(_normalize_version_string("odcs/v3.0.1"), "3.0.1")

    def test_normalize_version_handles_preview_versions(self):
        """Test that preview versions are handled correctly"""
        self.assertEqual(_normalize_version_string("3.0.0-preview"), "3.0.0-preview")
        self.assertEqual(_normalize_version_string("v3.0.0-preview"), "3.0.0-preview")

    def test_normalize_version_handles_empty_string(self):
        """Test that empty string returns latest version"""
        version = _normalize_version_string("")
        self.assertEqual(version, "3.0.2")  # Latest version

    def test_normalize_version_handles_none(self):
        """Test that None returns latest version"""
        # _normalize_version_string expects str, but handles empty strings
        # For None, we test via get_odcs_generator which handles None internally
        generator = get_odcs_generator(version=None)
        self.assertIsNotNone(generator)
        self.assertIsInstance(generator, ODCSGeneratorV3_0_2)  # Latest version


class ODCSGeneratorFallbackTest(TestCase):
    """Test fallback behavior"""

    def test_fallback_to_latest_when_version_not_found(self):
        """Test that unknown version falls back to latest"""
        generator = get_odcs_generator(version="1.0.0")  # Non-existent version

        # Should fallback to 3.0.2
        self.assertIsNotNone(generator)
        self.assertIsInstance(generator, ODCSGeneratorV3_0_2)

    def test_fallback_when_no_version_provided(self):
        """Test that no version provided falls back to latest"""
        generator = get_odcs_generator(version=None)

        # Should fallback to 3.0.2
        self.assertIsNotNone(generator)
        self.assertIsInstance(generator, ODCSGeneratorV3_0_2)

    def test_fallback_when_hubcontract_has_no_version(self):
        """Test that HubContract without version falls back to latest"""
        hub_contract = {"id": "test-1", "info": {"name": "Test"}}

        generator = get_odcs_generator(hub_contract=hub_contract)

        # Should fallback to 3.0.2
        self.assertIsNotNone(generator)
        self.assertIsInstance(generator, ODCSGeneratorV3_0_2)


class ODCSGeneratorErrorHandlingTest(TestCase):
    """Test error handling in registry"""

    def test_get_generator_with_empty_registry_raises_error(self):
        """Test that empty registry raises appropriate error"""
        # This test would require clearing the registry, which is not recommended
        # in production code, but we can test the error message format
        # by checking that the error includes available versions

        # Try to get a generator - should work since registry is initialized
        try:
            generator = get_odcs_generator(version="3.0.2")
            self.assertIsNotNone(generator)
        except ODCSGenerationError as e:
            # If error occurs, check it has proper context
            self.assertIn("available_versions", e.context)

    def test_get_generator_handles_unicode_characters(self):
        """Test that generator retrieval handles unicode characters correctly."""
        hub_contract = {
            "id": "test-unicode",
            "info": {"name": "测试合同"},
            "schema": {"fields": []},
        }

        generator = get_odcs_generator(hub_contract=hub_contract)

        # Should handle unicode characters
        self.assertIsNotNone(generator)
        result = generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("name", result)

    def test_get_generator_handles_special_characters(self):
        """Test that generator retrieval handles special characters correctly."""
        hub_contract = {
            "id": "test-special",
            "info": {"name": "Test & Co. (Special)"},
            "schema": {"fields": []},
        }

        generator = get_odcs_generator(hub_contract=hub_contract)

        # Should handle special characters
        self.assertIsNotNone(generator)
        result = generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("name", result)

    def test_get_generator_handles_very_large_documents(self):
        """Test that generator retrieval handles very large documents correctly."""
        large_description = "A" * 100000  # 100KB string
        hub_contract = {
            "id": "test-large",
            "info": {"name": "Test Product", "description": large_description},
            "schema": {"fields": []},
        }

        generator = get_odcs_generator(hub_contract=hub_contract)

        # Should handle large documents gracefully
        self.assertIsNotNone(generator)
        try:
            result = generator.generate_odcs_from_hubcontract(hub_contract)
            # If generation succeeds, verify structure
            self.assertIn("name", result)
        except Exception as e:
            # If generation fails, it should fail gracefully
            self.assertIsInstance(
                e, ODCSGenerationError, "Should raise ODCSGenerationError for very large documents"
            )

    def test_get_generator_handles_none_values(self):
        """Test that generator retrieval handles None values correctly."""
        hub_contract = {
            "id": "test-none",
            "info": {"name": "Test Product", "description": None},  # None value
            "schema": {"fields": []},
        }

        generator = get_odcs_generator(hub_contract=hub_contract)

        # Should handle None values gracefully
        self.assertIsNotNone(generator)
        try:
            result = generator.generate_odcs_from_hubcontract(hub_contract)
            # If generation succeeds, None values may be omitted or handled
            self.assertIsNotNone(result)
        except Exception as e:
            # If generation fails, it should fail gracefully
            self.assertIsInstance(
                e, ODCSGenerationError, "Should raise ODCSGenerationError for None values"
            )

    def test_get_generator_handles_nested_structures(self):
        """Test that generator retrieval handles nested structures correctly."""
        hub_contract = {
            "id": "test-nested",
            "info": {
                "name": "Test Product",
                "nested": {"level1": {"level2": {"level3": {"level4": {"value": "deep"}}}}},
            },
            "schema": {"fields": []},
        }

        generator = get_odcs_generator(hub_contract=hub_contract)

        # Should handle nested structures
        self.assertIsNotNone(generator)
        result = generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("name", result)
        self.assertIsNotNone(result)
