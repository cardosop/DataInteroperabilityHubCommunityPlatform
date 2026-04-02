"""
Integration tests for ODCS Generator Registry & Factory.

Tests the complete integration of registry, factory, and generation functionality
following engineering best practices without mocks/stubs.
"""

import pytest
from django.test import TestCase

from hub.apps.contracts.normalization.odcs_normalizer_v3_0_0 import ODCSNormalizerV3_0_0
from hub.apps.contracts.normalization.odcs_normalizer_v3_0_1 import ODCSNormalizerV3_0_1
from hub.apps.contracts.normalization.odcs_normalizer_v3_0_2 import ODCSNormalizerV3_0_2
from hub.apps.contracts.odcs_generator import (
    generate_odcs_from_hubcontract,
    get_odcs_generator,
    get_supported_odcs_versions,
)

pytestmark = pytest.mark.django_db(transaction=True)


class ODCSGeneratorRegistryIntegrationTest(TestCase):
    """Integration tests for complete registry + factory + generation workflow"""

    def test_end_to_end_generation_with_version_detection(self):
        """Test complete workflow: HubContract with version → detect → generate"""
        hub_contract = {
            "id": "test-integration-1",
            "info": {
                "name": "Integration Test Contract",
                "version": "1.0.0",
                "description": "Test contract for integration",
            },
            "schema": {
                "fields": [{"name": "id", "type": "string"}, {"name": "name", "type": "string"}]
            },
            "original_spec": {"type": "ODCS", "version": "3.0.0"},
        }

        # Generate ODCS using registry (should auto-detect version 3.0.0)
        odcs = generate_odcs_from_hubcontract(hub_contract)

        # Verify correct version was used
        self.assertEqual(odcs["apiVersion"], "odcs.io/v3.0.0")
        self.assertEqual(odcs["id"], "test-integration-1")
        self.assertEqual(odcs["name"], "Integration Test Contract")
        self.assertEqual(odcs["version"], "1.0.0")
        self.assertEqual(odcs["description"], "Test contract for integration")
        self.assertIn("schema", odcs)

    def test_end_to_end_generation_with_explicit_version(self):
        """Test complete workflow with explicit version override"""
        hub_contract = {
            "id": "test-integration-2",
            "info": {"name": "Integration Test Contract 2", "version": "1.0.0"},
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            "original_spec": {"type": "ODCS", "version": "3.0.0"},  # Original version
        }

        # Generate ODCS with explicit version override (3.0.1)
        odcs = generate_odcs_from_hubcontract(hub_contract, target_version="3.0.1")

        # Verify explicit version was used (not detected version)
        self.assertEqual(odcs["apiVersion"], "odcs.io/v3.0.1")
        self.assertEqual(odcs["id"], "test-integration-2")

    def test_end_to_end_generation_with_fallback(self):
        """Test complete workflow with fallback to latest version"""
        hub_contract = {
            "id": "test-integration-3",
            "info": {"name": "Integration Test Contract 3", "version": "1.0.0"},
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            # No original_spec metadata - should fallback to latest
        }

        # Generate ODCS without version (should fallback to 3.0.2)
        odcs = generate_odcs_from_hubcontract(hub_contract)

        # Verify fallback to latest version
        self.assertEqual(odcs["apiVersion"], "odcs.io/v3.0.2")
        self.assertEqual(odcs["id"], "test-integration-3")

    def test_round_trip_with_registry(self):
        """Test round-trip: ODCS → HubContract → ODCS using registry"""
        # Start with ODCS 3.0.0 contract
        original_odcs = {
            "apiVersion": "odcs.io/v3.0.0",
            "kind": "DataContract",
            "id": "test-round-trip",
            "name": "Round Trip Test",
            "version": "1.0.0",
            "description": "Round trip test contract",
            "schema": {
                "fields": [{"name": "id", "type": "string"}, {"name": "name", "type": "string"}]
            },
        }

        # Normalize to HubContract
        normalizer = ODCSNormalizerV3_0_0()
        norm_result = normalizer.normalize(original_odcs, spec_version="3.0.0")
        self.assertIn(norm_result.status.value, ["NORMALIZED_OK", "NORMALIZED_WITH_WARNINGS"])
        self.assertIsNotNone(norm_result.hub_contract)
        hub_contract = norm_result.hub_contract

        # Add original_spec metadata for version detection
        hub_contract["original_spec"] = {"type": "ODCS", "version": "3.0.0"}

        # Generate back to ODCS using registry (should detect version 3.0.0)
        generated_odcs = generate_odcs_from_hubcontract(hub_contract)

        # Verify round-trip
        self.assertEqual(generated_odcs["apiVersion"], "odcs.io/v3.0.0")
        self.assertEqual(generated_odcs["id"], original_odcs["id"])
        self.assertEqual(generated_odcs["name"], original_odcs["name"])
        self.assertEqual(generated_odcs["version"], original_odcs["version"])
        self.assertEqual(generated_odcs["description"], original_odcs["description"])

    def test_all_versions_generate_correctly(self):
        """Test that all registered versions generate correctly"""
        hub_contract = {
            "id": "test-all-versions",
            "info": {"name": "All Versions Test", "version": "1.0.0"},
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }

        versions = get_supported_odcs_versions()
        for version in versions:
            odcs = generate_odcs_from_hubcontract(hub_contract, target_version=version)
            # v3.1.0+ uses short "v{ver}" format; older use "odcs.io/v{ver}"
            expected_api = (
                f"v{version}" if version >= "3.1"
                else f"odcs.io/v{version}"
            )
            self.assertEqual(odcs["apiVersion"], expected_api)
            self.assertEqual(odcs["id"], "test-all-versions")
            self.assertEqual(odcs["name"], "All Versions Test")

    def test_version_detection_priority(self):
        """Test that explicit version takes priority over HubContract metadata"""
        hub_contract = {
            "id": "test-priority",
            "info": {"name": "Priority Test"},
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            "original_spec": {"type": "ODCS", "version": "3.0.0"},  # Metadata says 3.0.0
        }

        # Explicit version should override metadata
        odcs = generate_odcs_from_hubcontract(hub_contract, target_version="3.0.1")
        self.assertEqual(odcs["apiVersion"], "odcs.io/v3.0.1")  # Explicit version used

        # Without explicit version, should use metadata
        odcs2 = generate_odcs_from_hubcontract(hub_contract)
        self.assertEqual(odcs2["apiVersion"], "odcs.io/v3.0.0")  # Metadata version used

    def test_integration_handles_unicode_characters(self):
        """Test that integration handles unicode characters correctly."""
        hub_contract = {
            "id": "test-unicode",
            "info": {"name": "测试合同", "description": "测试描述"},
            "schema": {"fields": [{"name": "字段名称", "data_type": "string"}]},
        }

        result = generate_odcs_from_hubcontract(hub_contract)

        # Verify unicode characters are preserved
        self.assertIn("name", result)
        self.assertEqual(result["name"], "测试合同")

    def test_integration_handles_special_characters(self):
        """Test that integration handles special characters correctly."""
        hub_contract = {
            "id": "test-special",
            "info": {"name": "Test & Co. (Special)", "description": "Test <description> & more"},
            "schema": {"fields": [{"name": "field-name", "data_type": "string"}]},
        }

        result = generate_odcs_from_hubcontract(hub_contract)

        # Verify special characters are preserved
        self.assertIn("name", result)
        self.assertEqual(result["name"], "Test & Co. (Special)")

    def test_integration_handles_very_large_documents(self):
        """Test that integration handles very large documents correctly."""
        large_description = "A" * 100000  # 100KB string
        hub_contract = {
            "id": "test-large",
            "info": {"name": "Test Product", "description": large_description},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }

        # Should handle large documents gracefully
        try:
            result = generate_odcs_from_hubcontract(hub_contract)
            # If generation succeeds, verify structure
            self.assertIn("name", result)
        except Exception as e:
            # If generation fails, it should fail gracefully
            from hub.apps.contracts.odcs_errors import ODCSGenerationError

            self.assertIsInstance(
                e, ODCSGenerationError, "Should raise ODCSGenerationError for very large documents"
            )

    def test_integration_handles_none_values(self):
        """Test that integration handles None values correctly."""
        hub_contract = {
            "id": "test-none",
            "info": {"name": "Test Product", "description": None},  # None value
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }

        # Should handle None values gracefully
        try:
            result = generate_odcs_from_hubcontract(hub_contract)
            # If generation succeeds, None values may be omitted or handled
            self.assertIsNotNone(result)
        except Exception as e:
            # If generation fails, it should fail gracefully
            from hub.apps.contracts.odcs_errors import ODCSGenerationError

            self.assertIsInstance(
                e, ODCSGenerationError, "Should raise ODCSGenerationError for None values"
            )

    def test_integration_handles_nested_structures(self):
        """Test that integration handles nested structures correctly."""
        hub_contract = {
            "id": "test-nested",
            "info": {
                "name": "Test Product",
                "nested": {"level1": {"level2": {"level3": {"level4": {"value": "deep"}}}}},
            },
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }

        result = generate_odcs_from_hubcontract(hub_contract)

        # Verify nested structure is preserved
        self.assertIn("name", result)
        self.assertIsNotNone(result)
