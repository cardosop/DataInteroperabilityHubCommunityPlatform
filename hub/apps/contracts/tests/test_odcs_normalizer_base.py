"""
Unit tests for ODCSNormalizerBase abstract class.

Tests the base class functionality including:
- Abstract class structure
- Version support checking
- Normalization flow
- Helper methods
- Error handling
"""

from unittest import TestCase

import pytest

from hub.apps.contracts.models import NormalizationStatus, OriginalSpecType
from hub.apps.contracts.normalization.odcs_normalizer_base import ODCSNormalizerBase


class ConcreteODCSNormalizer(ODCSNormalizerBase):
    """Concrete implementation of ODCSNormalizerBase for testing."""

    def _supports_version(self, spec_version: str) -> bool:
        """Support version 3.0.2 for testing."""
        return spec_version == "3.0.2"


class ODCSNormalizerBaseStructureTest(TestCase):
    """Test that ODCSNormalizerBase is properly structured as an abstract class."""

    def test_cannot_instantiate_base_class_directly(self):
        """Test that ODCSNormalizerBase cannot be instantiated directly."""
        with pytest.raises(TypeError):
            ODCSNormalizerBase()

    def test_can_instantiate_concrete_subclass(self):
        """Test that a concrete subclass can be instantiated."""
        normalizer = ConcreteODCSNormalizer()
        self.assertIsNotNone(normalizer)
        self.assertIsInstance(normalizer, ODCSNormalizerBase)

    def test_spec_type_is_odcs(self):
        """Test that spec_type is set to ODCS."""
        normalizer = ConcreteODCSNormalizer()
        self.assertEqual(normalizer.spec_type, OriginalSpecType.ODCS)


class ODCSNormalizerBaseSupportsTest(TestCase):
    """Test the supports() method of ODCSNormalizerBase."""

    def test_supports_odcs_spec_type(self):
        """Test that supports() returns True for ODCS spec type."""
        normalizer = ConcreteODCSNormalizer()
        self.assertTrue(normalizer.supports(OriginalSpecType.ODCS, "3.0.2", {}))

    def test_supports_does_not_support_other_spec_types(self):
        """Test that supports() returns False for non-ODCS spec types."""
        normalizer = ConcreteODCSNormalizer()
        self.assertFalse(normalizer.supports(OriginalSpecType.ODPS, "4.1", {}))
        self.assertFalse(normalizer.supports("CUSTOM", "1.0", {}))

    def test_supports_delegates_to_supports_version(self):
        """Test that supports() delegates to _supports_version()."""
        normalizer = ConcreteODCSNormalizer()
        # Concrete implementation supports 3.0.2
        self.assertTrue(normalizer.supports(OriginalSpecType.ODCS, "3.0.2", {}))
        # But not 3.0.1
        self.assertFalse(normalizer.supports(OriginalSpecType.ODCS, "3.0.1", {}))


class ODCSNormalizerBaseNormalizeTest(TestCase):
    """Test the normalize() method of ODCSNormalizerBase."""

    def test_normalize_returns_normalization_result(self):
        """Test that normalize() returns a NormalizationResult."""
        normalizer = ConcreteODCSNormalizer()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-1",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.2")

        # Check that result has the expected attributes (using hasattr due to dynamic imports)
        self.assertTrue(hasattr(result, "hub_contract"))
        self.assertTrue(hasattr(result, "status"))
        self.assertTrue(hasattr(result, "errors"))
        self.assertTrue(hasattr(result, "warnings"))
        self.assertTrue(hasattr(result, "spec_type"))
        self.assertTrue(hasattr(result, "spec_version"))
        self.assertTrue(hasattr(result, "coverage"))

        self.assertEqual(result.spec_type, OriginalSpecType.ODCS)
        self.assertEqual(result.spec_version, "3.0.2")
        self.assertIsInstance(result.errors, list)
        self.assertIsInstance(result.warnings, list)

    def test_normalize_detects_version_if_not_provided(self):
        """Test that normalize() detects version from contract_data if not provided."""
        normalizer = ConcreteODCSNormalizer()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-1",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
        }

        result = normalizer.normalize(contract_data, spec_version=None)

        self.assertEqual(result.spec_version, "3.0.2")

    def test_normalize_fails_for_unsupported_version(self):
        """Test that normalize() fails gracefully for unsupported versions."""
        normalizer = ConcreteODCSNormalizer()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.1",
            "kind": "DataContract",
            "id": "test-1",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.1")

        self.assertEqual(result.status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(
            "does not support" in result.errors[0].lower()
        )

    def test_normalize_validates_contract_data_is_dict(self):
        """Test that normalize() validates contract_data is a dictionary."""
        normalizer = ConcreteODCSNormalizer()

        result = normalizer.normalize("not a dict", spec_version="3.0.2")

        self.assertEqual(result.status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("dictionary", result.errors[0].lower())

    def test_normalize_handles_missing_required_fields(self):
        """Test that normalize() handles missing required fields gracefully."""
        normalizer = ConcreteODCSNormalizer()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-1",
            # Missing 'name' field
            "schema": {},  # Missing 'fields' array
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.2")

        # Should have errors for missing required fields
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("name" in error.lower() for error in result.errors))
        self.assertTrue(any("fields" in error.lower() for error in result.errors))

    def test_normalize_contract_with_valid_data(self):
        """Normalize valid contract data without raising — returns result with status."""
        normalizer = ConcreteODCSNormalizer()
        # Create contract data that might cause issues
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-1",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
        }

        # This should not raise an exception
        result = normalizer.normalize(contract_data, spec_version="3.0.2")

        self.assertIsNotNone(result)
        self.assertTrue(hasattr(result, "status"))


class ODCSNormalizerBaseHelperMethodsTest(TestCase):
    """Test helper methods of ODCSNormalizerBase."""

    def test_detect_odcs_version_from_api_version(self):
        """Test that normalize() detects version from apiVersion through public API."""
        normalizer = ConcreteODCSNormalizer()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }

        # Test through public API - normalize() internally calls _detect_odcs_version()
        result = normalizer.normalize(contract_data, spec_version=None)

        self.assertEqual(result.spec_version, "3.0.2")

    def test_detect_odcs_version_from_version_field(self):
        """Test that normalize() detects version from version field through public API."""
        normalizer = ConcreteODCSNormalizer()
        contract_data = {
            "version": "3.0.1",
            "id": "test",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }

        # Test through public API - normalize() internally calls _detect_odcs_version()
        # Note: ConcreteODCSNormalizer only supports 3.0.2, so this will fail
        # But we can verify version detection by checking the error or by using a supported version
        result = normalizer.normalize(contract_data, spec_version=None)
        # Version detection should work, but normalization will fail because 3.0.1 is not supported
        # The version detection happens before version support check
        self.assertEqual(result.status, NormalizationStatus.NORMALIZATION_FAILED)

    def test_detect_odcs_version_defaults_to_3_0_2(self):
        """Test that normalize() defaults to 3.0.2 if version cannot be detected through public API."""
        normalizer = ConcreteODCSNormalizer()
        contract_data = {
            "id": "test",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }

        # Test through public API - normalize() internally calls _detect_odcs_version()
        # and defaults to 3.0.2 if version cannot be detected
        result = normalizer.normalize(contract_data, spec_version=None)

        self.assertEqual(result.spec_version, "3.0.2")

    def test_map_version_specific_fields_default_implementation(self):
        """Test that _map_version_specific_fields has a default no-op implementation through public API."""
        normalizer = ConcreteODCSNormalizer()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }

        # Test through public API - normalize() internally calls _map_version_specific_fields()
        # Default implementation should be no-op, so normalization should succeed
        result = normalizer.normalize(contract_data, spec_version="3.0.2")

        # Should succeed - default implementation doesn't modify anything
        self.assertEqual(result.status, NormalizationStatus.NORMALIZED_OK)
        self.assertIsNotNone(result.hub_contract)

    def test_detect_odcs_version_from_shorthand_api_version(self):
        """_detect_odcs_version handles shorthand apiVersion like 'odcs/v3.0.2'."""
        normalizer = ConcreteODCSNormalizer()
        contract_data = {
            "apiVersion": "odcs/v3.0.2",
            "kind": "DataContract",
            "id": "test",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }
        # Test through public API - normalize() internally calls _detect_odcs_version()
        result = normalizer.normalize(contract_data, spec_version=None)
        # The shorthand "odcs/v3.0.2" should be detected as version "3.0.2"
        self.assertEqual(result.spec_version, "3.0.2")

    def test_detect_odcs_version_with_v_prefix(self):
        """_detect_odcs_version handles v-prefixed apiVersion like 'v3.0.2'."""
        normalizer = ConcreteODCSNormalizer()
        contract_data = {
            "apiVersion": "v3.0.2",
            "kind": "DataContract",
            "id": "test",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }
        result = normalizer.normalize(contract_data, spec_version=None)
        # "v3.0.2" should be detected as version "3.0.2"
        self.assertEqual(result.spec_version, "3.0.2")

    def test_detect_odcs_version_with_build_metadata(self):
        """_detect_odcs_version handles apiVersion with build metadata like 'odcs.io/v3.0.2+build.1'."""
        normalizer = ConcreteODCSNormalizer()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2+build.1",
            "kind": "DataContract",
            "id": "test",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }
        result = normalizer.normalize(contract_data, spec_version=None)
        # Build metadata is preserved as part of the version string by the split logic
        self.assertIsNotNone(result)
        # The version detection should extract something meaningful
        self.assertTrue(result.spec_version.startswith("3.0.2"))

    def test_detect_odcs_version_shorthand_with_build_metadata(self):
        """_detect_odcs_version handles shorthand apiVersion with build metadata like 'odcs/v3.0.2+build.1'."""
        normalizer = ConcreteODCSNormalizer()
        contract_data = {
            "apiVersion": "odcs/v3.0.2+build.1",
            "kind": "DataContract",
            "id": "test",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }
        result = normalizer.normalize(contract_data, spec_version=None)
        self.assertIsNotNone(result)
        # Should extract version from the shorthand + build metadata format
        self.assertTrue(result.spec_version.startswith("3.0.2"))


class ODCSNormalizerBaseNormalizationMethodsTest(TestCase):
    """Test the normalization helper methods of ODCSNormalizerBase."""

    def test_normalize_info(self):
        """Test _normalize_info method through public API."""
        normalizer = ConcreteODCSNormalizer()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test",
            "name": "Test Contract",
            "info": {"owners": ["owner1"], "tags": ["tag1"]},
            "owners": ["owner2"],  # Top-level owners should override
            "tags": ["tag2"],  # Top-level tags should override
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }

        # Test through public API - normalize() internally calls _normalize_info()
        result = normalizer.normalize(contract_data, spec_version="3.0.2")

        # Top-level owners/tags should override info section
        # Owners are normalized from strings to HubContractOwner format
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("info", result.hub_contract)
        self.assertIn("owners", result.hub_contract["info"])
        self.assertIn("tags", result.hub_contract["info"])
        # Owners are normalized from strings to HubContractOwner format
        self.assertEqual(result.hub_contract["info"]["owners"], [{"name": "owner2"}])
        self.assertEqual(result.hub_contract["info"]["tags"], ["tag2"])

    def test_normalize_schema(self):
        """Test _normalize_schema method through public API."""
        normalizer = ConcreteODCSNormalizer()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
        }

        # Test through public API - normalize() internally calls _normalize_schema()
        result = normalizer.normalize(contract_data, spec_version="3.0.2")

        # Should have models and schema derived
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("models", result.hub_contract)
        self.assertGreater(len(result.hub_contract["models"]), 0)
        self.assertIn("fields", result.hub_contract["schema"])

    def test_normalize_quality(self):
        """Test _normalize_quality method through public API."""
        normalizer = ConcreteODCSNormalizer()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            "quality": {"default_profile_key": "profile1", "rules": []},
        }

        # Test through public API - normalize() internally calls _normalize_quality()
        result = normalizer.normalize(contract_data, spec_version="3.0.2")

        self.assertIsNotNone(result.hub_contract)
        self.assertIn("quality", result.hub_contract)
        self.assertEqual(result.hub_contract["quality"]["default_profile_key"], "profile1")

    def test_normalize_privacy_compliance(self):
        """Test _normalize_privacy_compliance method through public API."""
        normalizer = ConcreteODCSNormalizer()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            "privacy_compliance": {
                "contains_personal_data": True,
                "personal_data_categories": ["PII"],
            },
        }

        # Test through public API - normalize() internally calls _normalize_privacy_compliance()
        result = normalizer.normalize(contract_data, spec_version="3.0.2")

        self.assertIsNotNone(result.hub_contract)
        self.assertIn("privacy_compliance", result.hub_contract)
        self.assertTrue(result.hub_contract["privacy_compliance"]["contains_personal_data"] is True)

    def test_normalize_lifecycle(self):
        """Test _normalize_lifecycle method through public API."""
        normalizer = ConcreteODCSNormalizer()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            "lifecycle": {"data_source": "database", "refresh_cadence": "daily"},
        }

        # Test through public API - normalize() internally calls _normalize_lifecycle()
        result = normalizer.normalize(contract_data, spec_version="3.0.2")

        self.assertIsNotNone(result.hub_contract)
        self.assertIn("lifecycle", result.hub_contract)
        self.assertEqual(result.hub_contract["lifecycle"]["data_source"], "database")

    def test_validate_required_fields(self):
        """Test _validate_required_fields method through public API."""
        normalizer = ConcreteODCSNormalizer()
        # Create contract data that will result in missing required fields
        # This happens when schema is empty or info.name is missing
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test",
            # Missing 'name' field
            "schema": {
                # Missing 'fields' - empty schema
            },
        }

        # Test through public API - normalize() internally calls _validate_required_fields()
        result = normalizer.normalize(contract_data, spec_version="3.0.2")

        # Should have validation errors for missing required fields
        self.assertGreater(len(result.errors), 0)
        # Validation should catch missing required fields.
        self.assertEqual(result.status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertGreater(len(result.errors), 0)

    def test_normalization_handles_unicode_characters(self):
        """Test that normalization handles unicode characters correctly."""
        normalizer = ConcreteODCSNormalizer()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-unicode",
            "name": "测试合同",
            "version": "1.0.0",
            "description": "测试描述",
            "schema": {"fields": [{"name": "字段名称", "type": "string"}]},
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.2")

        # Should handle unicode characters
        self.assertIsNotNone(result.hub_contract)
        self.assertIsNotNone(result.hub_contract, "hub_contract must not be None")
        self.assertIn("info", result.hub_contract, "info key must be present")
        self.assertIsNotNone(result.hub_contract["info"], "info must not be None")

    def test_normalization_handles_special_characters(self):
        """Test that normalization handles special characters correctly."""
        normalizer = ConcreteODCSNormalizer()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-special",
            "name": "Test & Co. (Special)",
            "version": "1.0.0",
            "description": "Test <description> & more",
            "schema": {"fields": [{"name": "field-name", "type": "string"}]},
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.2")

        # Should handle special characters
        self.assertIsNotNone(result.hub_contract)
        self.assertIsNotNone(result.hub_contract, "hub_contract must not be None")
        self.assertIn("info", result.hub_contract, "info key must be present")
        self.assertIsNotNone(result.hub_contract["info"], "info must not be None")

    def test_normalization_handles_very_large_documents(self):
        """Test that normalization handles very large documents correctly."""
        normalizer = ConcreteODCSNormalizer()
        large_description = "A" * 100000  # 100KB string
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-large",
            "name": "Test Product",
            "version": "1.0.0",
            "description": large_description,
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.2")

        # Should handle very large documents
        self.assertIsNotNone(result.hub_contract)

    def test_normalization_handles_none_values(self):
        """Test that normalization handles None values correctly."""
        normalizer = ConcreteODCSNormalizer()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-none",
            "name": "Test Product",
            "version": "1.0.0",
            "description": None,  # None value
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.2")

        # Should handle None values gracefully
        self.assertIsNotNone(result.hub_contract)

    def test_normalization_handles_nested_structures(self):
        """Test that normalization handles nested structures correctly."""
        normalizer = ConcreteODCSNormalizer()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-nested",
            "name": "Test Product",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {
                        "name": "id",
                        "type": "string",
                        "nested": {"level1": {"level2": {"level3": {"value": "deep"}}}},
                    }
                ]
            },
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.2")

        # Should handle nested structures
        self.assertIsNotNone(result.hub_contract)
        self.assertIsNotNone(result.hub_contract, "hub_contract must not be None")
        self.assertIn("schema", result.hub_contract, "schema key must be present")
        self.assertIsNotNone(result.hub_contract["schema"], "schema must not be None")
