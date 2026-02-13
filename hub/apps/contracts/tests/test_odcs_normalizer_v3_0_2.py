"""
Unit tests for ODCSNormalizerV3_0_2.

Tests the version-specific normalizer for ODCS 3.0.2 including:
- Version support checking
- Normalization flow
- Version-specific field mappings
- Integration with normalizer registry
"""

import json
from unittest import TestCase

from hub.apps.contracts.models import NormalizationStatus, OriginalSpecType
from hub.apps.contracts.normalization import (
    NormalizationResult,
    _reset_normalizer_registry,
    get_normalizer,
    register_normalizer,
)
from hub.apps.contracts.normalization.odcs_normalizer_v3_0_2 import ODCSNormalizerV3_0_2


class ODCSNormalizerV3_0_2StructureTest(TestCase):
    """Test that ODCSNormalizerV3_0_2 is properly structured."""

    def test_can_instantiate_normalizer(self):
        """Test that ODCSNormalizerV3_0_2 can be instantiated."""
        normalizer = ODCSNormalizerV3_0_2()
        assert normalizer is not None
        assert isinstance(normalizer, ODCSNormalizerV3_0_2)

    def test_spec_type_is_odcs(self):
        """Test that spec_type is set to ODCS."""
        normalizer = ODCSNormalizerV3_0_2()
        assert normalizer.spec_type == OriginalSpecType.ODCS


class ODCSNormalizerV3_0_2SupportsTest(TestCase):
    """Test the supports() and _supports_version() methods."""

    def test_supports_version_3_0_2(self):
        """Test that supports() returns True for version 3.0.2 through public API."""
        normalizer = ODCSNormalizerV3_0_2()
        contract_data = {"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract"}
        # Test through public API - supports() internally calls _supports_version()
        assert normalizer.supports(OriginalSpecType.ODCS, "3.0.2", contract_data) is True

    def test_supports_version_3_0_2_plus(self):
        """Test that supports() returns True for version 3.0.2+ through public API."""
        normalizer = ODCSNormalizerV3_0_2()
        contract_data = {"apiVersion": "odcs.io/v3.0.2+", "kind": "DataContract"}
        # Test through public API - supports() internally calls _supports_version()
        assert normalizer.supports(OriginalSpecType.ODCS, "3.0.2+", contract_data) is True

    def test_supports_version_3_0_2_with_patch(self):
        """Test that supports() returns True for version 3.0.2.x through public API."""
        normalizer = ODCSNormalizerV3_0_2()
        # Should support versions starting with 3.0.2
        # Test through public API - supports() internally calls _supports_version()
        assert (
            normalizer.supports(
                OriginalSpecType.ODCS, "3.0.2.1", {"apiVersion": "odcs.io/v3.0.2.1"}
            )
            is True
        )
        assert (
            normalizer.supports(
                OriginalSpecType.ODCS, "3.0.2.5", {"apiVersion": "odcs.io/v3.0.2.5"}
            )
            is True
        )

    def test_does_not_support_other_versions(self):
        """Test that supports() returns False for other versions through public API."""
        normalizer = ODCSNormalizerV3_0_2()
        # Test through public API - supports() internally calls _supports_version()
        assert (
            normalizer.supports(OriginalSpecType.ODCS, "3.0.1", {"apiVersion": "odcs.io/v3.0.1"})
            is False
        )
        assert (
            normalizer.supports(OriginalSpecType.ODCS, "3.0.0", {"apiVersion": "odcs.io/v3.0.0"})
            is False
        )
        assert (
            normalizer.supports(OriginalSpecType.ODCS, "3.1.0", {"apiVersion": "odcs.io/v3.1.0"})
            is False
        )
        assert (
            normalizer.supports(OriginalSpecType.ODCS, "4.0.0", {"apiVersion": "odcs.io/v4.0.0"})
            is False
        )

    def test_supports_odcs_spec_type(self):
        """Test that supports() returns True for ODCS spec type with version 3.0.2."""
        normalizer = ODCSNormalizerV3_0_2()
        assert normalizer.supports(OriginalSpecType.ODCS, "3.0.2", {}) is True

    def test_supports_does_not_support_other_spec_types(self):
        """Test that supports() returns False for non-ODCS spec types."""
        normalizer = ODCSNormalizerV3_0_2()
        assert normalizer.supports(OriginalSpecType.ODPS, "4.1", {}) is False
        assert normalizer.supports("CUSTOM", "1.0", {}) is False

    def test_supports_does_not_support_other_odcs_versions(self):
        """Test that supports() returns False for other ODCS versions."""
        normalizer = ODCSNormalizerV3_0_2()
        assert normalizer.supports(OriginalSpecType.ODCS, "3.0.1", {}) is False
        assert normalizer.supports(OriginalSpecType.ODCS, "3.0.0", {}) is False


class ODCSNormalizerV3_0_2NormalizeTest(TestCase):
    """Test the normalize() method of ODCSNormalizerV3_0_2."""

    def test_normalize_returns_normalization_result(self):
        """Test that normalize() returns a NormalizationResult."""
        normalizer = ODCSNormalizerV3_0_2()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-1",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.2")

        # Check that result has the expected attributes
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
        normalizer = ODCSNormalizerV3_0_2()
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
        normalizer = ODCSNormalizerV3_0_2()
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
        normalizer = ODCSNormalizerV3_0_2()

        result = normalizer.normalize("not a dict", spec_version="3.0.2")

        assert result.status == NormalizationStatus.NORMALIZATION_FAILED
        assert len(result.errors) > 0
        assert "dictionary" in result.errors[0].lower()

    def test_normalize_produces_valid_hub_contract(self):
        """Test that normalize() produces a valid hub_contract for 3.0.2."""
        normalizer = ODCSNormalizerV3_0_2()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-1",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "nullable": False},
                    {"name": "name", "type": "string", "nullable": False},
                ]
            },
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.2")

        assert result.hub_contract is not None
        assert result.hub_contract["id"] == "test-1"
        assert result.hub_contract["info"]["name"] == "Test Contract"
        assert result.hub_contract["info"]["version"] == "1.0.0"
        assert "schema" in result.hub_contract
        assert "fields" in result.hub_contract["schema"]
        assert len(result.hub_contract["schema"]["fields"]) == 2

    def test_normalize_handles_complex_contract(self):
        """Test that normalize() handles a complex ODCS 3.0.2 contract."""
        normalizer = ODCSNormalizerV3_0_2()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "complex-test",
            "name": "Complex Test Contract",
            "version": "1.0.0",
            "description": "A complex contract for testing",
            "info": {"owners": ["owner1", "owner2"], "tags": ["tag1", "tag2"]},
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "nullable": False},
                    {"name": "name", "type": "string", "nullable": False},
                ]
            },
            "quality": {"default_profile_key": "profile1"},
            "lifecycle": {"data_source": "database", "refresh_cadence": "daily"},
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.2")

        assert result.hub_contract is not None
        assert result.hub_contract["id"] == "complex-test"
        assert result.hub_contract["info"]["name"] == "Complex Test Contract"
        assert "owners" in result.hub_contract["info"]
        assert "tags" in result.hub_contract["info"]
        assert "quality" in result.hub_contract
        assert "lifecycle" in result.hub_contract


class ODCSNormalizerV3_0_2RegistryTest(TestCase):
    """Test ODCSNormalizerV3_0_2 integration with normalizer registry."""

    def setUp(self):
        """Save registry state before each test."""
        from hub.apps.contracts.normalization import _NORMALIZER_REGISTRY

        self.original_registry = {key: list(value) for key, value in _NORMALIZER_REGISTRY.items()}

    def tearDown(self):
        """Restore registry state after each test."""
        _reset_normalizer_registry(self.original_registry)

    def test_normalizer_can_be_registered(self):
        """Test that ODCSNormalizerV3_0_2 can be registered."""
        normalizer = ODCSNormalizerV3_0_2()
        register_normalizer(normalizer)

        # Should be able to retrieve it
        retrieved = get_normalizer(OriginalSpecType.ODCS, "3.0.2", {})
        assert retrieved is not None
        assert isinstance(retrieved, ODCSNormalizerV3_0_2)

    def test_registered_normalizer_handles_3_0_2_contracts(self):
        """Test that registered normalizer correctly handles 3.0.2 contracts."""
        normalizer = ODCSNormalizerV3_0_2()
        register_normalizer(normalizer)

        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-1",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
        }

        retrieved = get_normalizer(OriginalSpecType.ODCS, "3.0.2", contract_data)
        assert retrieved is not None
        assert isinstance(retrieved, ODCSNormalizerV3_0_2)

        result = retrieved.normalize(contract_data, spec_version="3.0.2")
        assert result.spec_version == "3.0.2"
        assert result.hub_contract is not None


class ODCSNormalizerV3_0_2RegressionTest(TestCase):
    """Regression tests to ensure ODCS 3.0.2 normalization is unchanged."""

    def test_normalization_output_matches_expected_format(self):
        """Test that normalization output matches expected format for 3.0.2."""
        normalizer = ODCSNormalizerV3_0_2()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "regression-test",
            "name": "Regression Test Contract",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "nullable": False},
                    {"name": "name", "type": "string", "nullable": False},
                ]
            },
            "info": {"owners": ["owner1", "owner2"], "tags": ["tag1", "tag2"]},
            "quality": {"default_profile_key": "profile1"},
            "lifecycle": {"data_source": "database", "refresh_cadence": "daily"},
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.2")

        # Check that all expected fields are present
        assert result.hub_contract is not None
        assert result.hub_contract["id"] == "regression-test"
        assert result.hub_contract["info"]["name"] == "Regression Test Contract"
        assert result.hub_contract["info"]["version"] == "1.0.0"
        assert "owners" in result.hub_contract["info"]
        assert "tags" in result.hub_contract["info"]
        assert "quality" in result.hub_contract
        assert "lifecycle" in result.hub_contract
        assert "schema" in result.hub_contract
        assert "fields" in result.hub_contract["schema"]
        assert len(result.hub_contract["schema"]["fields"]) == 2

    def test_normalization_preserves_extensions(self):
        """Test that normalization preserves unmappable fields in extensions."""
        normalizer = ODCSNormalizerV3_0_2()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-1",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
            "custom_field": "custom_value",
            "another_custom": {"nested": "value"},
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.2")

        # Should preserve custom fields in extensions
        assert result.hub_contract is not None
        assert "extensions" in result.hub_contract
        assert "custom_field" in result.hub_contract["extensions"]
        assert result.hub_contract["extensions"]["custom_field"] == "custom_value"
        assert "odcs" in result.hub_contract["extensions"]
        assert "custom_field" in result.hub_contract["extensions"]["odcs"]

    def test_normalization_calculates_coverage(self):
        """Test that normalization calculates coverage for 3.0.2."""
        normalizer = ODCSNormalizerV3_0_2()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-1",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
            "quality": {"default_profile_key": "profile1"},
            "lifecycle": {"data_source": "database"},
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.2")

        # Should have coverage calculated
        assert result.coverage is not None
        assert result.hub_contract is not None
        assert "normalization" in result.hub_contract
        assert "coverage" in result.hub_contract["normalization"]
        assert "original_spec_type" in result.hub_contract["normalization"]
        assert result.hub_contract["normalization"]["original_spec_type"] == OriginalSpecType.ODCS
        assert "original_spec_version" in result.hub_contract["normalization"]
        assert result.hub_contract["normalization"]["original_spec_version"] == "3.0.2"

    def test_normalization_handles_missing_required_fields(self):
        """Test that normalization handles missing required fields gracefully."""
        normalizer = ODCSNormalizerV3_0_2()
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
        # When required fields are missing, normalization fails; hub_contract may be None
        assert result.status == NormalizationStatus.NORMALIZATION_FAILED

    def test_normalization_handles_unicode_characters(self):
        """Test that normalization handles unicode characters correctly."""
        normalizer = ODCSNormalizerV3_0_2()
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
        normalizer = ODCSNormalizerV3_0_2()
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
        normalizer = ODCSNormalizerV3_0_2()
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
        normalizer = ODCSNormalizerV3_0_2()
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
        normalizer = ODCSNormalizerV3_0_2()
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
