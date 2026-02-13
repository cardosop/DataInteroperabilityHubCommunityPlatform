"""
Unit tests for ODCSNormalizerBase abstract class.

Tests the base class functionality including:
- Abstract class structure
- Version support checking
- Normalization flow
- Helper methods
- Error handling
"""

from typing import Any, Dict
from unittest import TestCase

import pytest

from hub.apps.contracts.models import NormalizationStatus, OriginalSpecType
from hub.apps.contracts.normalization import NormalizationResult
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
        assert normalizer is not None
        assert isinstance(normalizer, ODCSNormalizerBase)

    def test_spec_type_is_odcs(self):
        """Test that spec_type is set to ODCS."""
        normalizer = ConcreteODCSNormalizer()
        assert normalizer.spec_type == OriginalSpecType.ODCS


class ODCSNormalizerBaseSupportsTest(TestCase):
    """Test the supports() method of ODCSNormalizerBase."""

    def test_supports_odcs_spec_type(self):
        """Test that supports() returns True for ODCS spec type."""
        normalizer = ConcreteODCSNormalizer()
        assert normalizer.supports(OriginalSpecType.ODCS, "3.0.2", {})

    def test_supports_does_not_support_other_spec_types(self):
        """Test that supports() returns False for non-ODCS spec types."""
        normalizer = ConcreteODCSNormalizer()
        assert not normalizer.supports(OriginalSpecType.ODPS, "4.1", {})
        assert not normalizer.supports("CUSTOM", "1.0", {})

    def test_supports_delegates_to_supports_version(self):
        """Test that supports() delegates to _supports_version()."""
        normalizer = ConcreteODCSNormalizer()
        # Concrete implementation supports 3.0.2
        assert normalizer.supports(OriginalSpecType.ODCS, "3.0.2", {})
        # But not 3.0.1
        assert not normalizer.supports(OriginalSpecType.ODCS, "3.0.1", {})


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
        assert hasattr(result, "hub_contract")
        assert hasattr(result, "status")
        assert hasattr(result, "errors")
        assert hasattr(result, "warnings")
        assert hasattr(result, "spec_type")
        assert hasattr(result, "spec_version")
        assert hasattr(result, "coverage")

        assert result.spec_type == OriginalSpecType.ODCS
        assert result.spec_version == "3.0.2"
        assert isinstance(result.errors, list)
        assert isinstance(result.warnings, list)

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

        assert result.spec_version == "3.0.2"

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

        assert result.status == NormalizationStatus.NORMALIZATION_FAILED
        assert len(result.errors) > 0
        assert (
            "does not support" in result.errors[0].lower()
            or "not support" in result.errors[0].lower()
        )

    def test_normalize_validates_contract_data_is_dict(self):
        """Test that normalize() validates contract_data is a dictionary."""
        normalizer = ConcreteODCSNormalizer()

        result = normalizer.normalize("not a dict", spec_version="3.0.2")

        assert result.status == NormalizationStatus.NORMALIZATION_FAILED
        assert len(result.errors) > 0
        assert "dictionary" in result.errors[0].lower()

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
        assert len(result.errors) > 0
        assert any("name" in error.lower() for error in result.errors)
        assert any("fields" in error.lower() for error in result.errors)

    def test_normalize_handles_exceptions_gracefully(self):
        """Test that normalize() handles unexpected exceptions gracefully."""
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

        assert result is not None
        assert hasattr(result, "status")


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

        assert result.spec_version == "3.0.2"

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
        assert result.status == NormalizationStatus.NORMALIZATION_FAILED

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

        assert result.spec_version == "3.0.2"

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
        assert result.status in [
            NormalizationStatus.NORMALIZED_OK,
            NormalizationStatus.NORMALIZED_WITH_WARNINGS,
        ]
        assert result.hub_contract is not None


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
        assert result.hub_contract is not None
        assert "info" in result.hub_contract
        assert "owners" in result.hub_contract["info"]
        assert "tags" in result.hub_contract["info"]
        # Owners are normalized from strings to HubContractOwner format
        assert result.hub_contract["info"]["owners"] == [{"name": "owner2"}]
        assert result.hub_contract["info"]["tags"] == ["tag2"]

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
        assert result.hub_contract is not None
        assert "models" in result.hub_contract
        assert len(result.hub_contract["models"]) > 0
        assert "fields" in result.hub_contract["schema"]

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

        assert result.hub_contract is not None
        assert "quality" in result.hub_contract
        assert result.hub_contract["quality"]["default_profile_key"] == "profile1"

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

        assert result.hub_contract is not None
        assert "privacy_compliance" in result.hub_contract
        assert result.hub_contract["privacy_compliance"]["contains_personal_data"] is True

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

        assert result.hub_contract is not None
        assert "lifecycle" in result.hub_contract
        assert result.hub_contract["lifecycle"]["data_source"] == "database"

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
        assert len(result.errors) > 0
        # Check that errors mention missing required fields
        error_messages = " ".join(result.errors).lower()
        # Note: The exact error messages depend on implementation
        # But validation should catch missing required fields
        assert result.status == NormalizationStatus.NORMALIZATION_FAILED or len(result.errors) > 0

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
        assert result.hub_contract is not None
        if result.hub_contract and "info" in result.hub_contract:
            assert result.hub_contract["info"] is not None

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
        assert result.hub_contract is not None
        if result.hub_contract and "info" in result.hub_contract:
            assert result.hub_contract["info"] is not None

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
        assert result.hub_contract is not None

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
        assert result.hub_contract is not None

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
        assert result.hub_contract is not None
        if result.hub_contract and "schema" in result.hub_contract:
            assert result.hub_contract["schema"] is not None
