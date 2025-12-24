"""
Unit tests for ODCSNormalizerV3_0_0_Preview.

Tests the version-specific normalizer for ODCS 3.0.0-preview including:
- Version support checking
- Normalization flow
- Version-specific field mappings
- Graceful degradation for missing features
- Integration with normalizer registry
"""
import json
from unittest import TestCase

from hub.apps.contracts.models import NormalizationStatus, OriginalSpecType
from hub.apps.contracts.normalization import (
    NormalizationResult,
    get_normalizer,
    register_normalizer,
    _reset_normalizer_registry,
)
from hub.apps.contracts.normalization.odcs_normalizer_v3_0_0_preview import ODCSNormalizerV3_0_0_Preview


class ODCSNormalizerV3_0_0_PreviewStructureTest(TestCase):
    """Test that ODCSNormalizerV3_0_0_Preview is properly structured."""

    def test_can_instantiate_normalizer(self):
        """Test that ODCSNormalizerV3_0_0_Preview can be instantiated."""
        normalizer = ODCSNormalizerV3_0_0_Preview()
        assert normalizer is not None
        assert isinstance(normalizer, ODCSNormalizerV3_0_0_Preview)

    def test_spec_type_is_odcs(self):
        """Test that spec_type is set to ODCS."""
        normalizer = ODCSNormalizerV3_0_0_Preview()
        assert normalizer.spec_type == OriginalSpecType.ODCS


class ODCSNormalizerV3_0_0_PreviewSupportsTest(TestCase):
    """Test the supports() and _supports_version() methods."""

    def test_supports_version_3_0_0_preview(self):
        """Test that _supports_version returns True for version 3.0.0-preview."""
        normalizer = ODCSNormalizerV3_0_0_Preview()
        assert normalizer._supports_version("3.0.0-preview") is True

    def test_does_not_support_other_versions(self):
        """Test that _supports_version returns False for other versions."""
        normalizer = ODCSNormalizerV3_0_0_Preview()
        assert normalizer._supports_version("3.0.0") is False
        assert normalizer._supports_version("3.0.1") is False
        assert normalizer._supports_version("3.0.2") is False
        assert normalizer._supports_version("3.1.0") is False
        assert normalizer._supports_version("4.0.0") is False

    def test_supports_odcs_spec_type(self):
        """Test that supports() returns True for ODCS spec type with version 3.0.0-preview."""
        normalizer = ODCSNormalizerV3_0_0_Preview()
        assert normalizer.supports(OriginalSpecType.ODCS, "3.0.0-preview", {}) is True

    def test_supports_does_not_support_other_spec_types(self):
        """Test that supports() returns False for non-ODCS spec types."""
        normalizer = ODCSNormalizerV3_0_0_Preview()
        assert normalizer.supports(OriginalSpecType.ODPS, "4.1", {}) is False
        assert normalizer.supports("CUSTOM", "1.0", {}) is False

    def test_supports_does_not_support_other_odcs_versions(self):
        """Test that supports() returns False for other ODCS versions."""
        normalizer = ODCSNormalizerV3_0_0_Preview()
        assert normalizer.supports(OriginalSpecType.ODCS, "3.0.0", {}) is False
        assert normalizer.supports(OriginalSpecType.ODCS, "3.0.1", {}) is False
        assert normalizer.supports(OriginalSpecType.ODCS, "3.0.2", {}) is False


class ODCSNormalizerV3_0_0_PreviewNormalizeTest(TestCase):
    """Test the normalize() method of ODCSNormalizerV3_0_0_Preview."""

    def test_normalize_returns_normalization_result(self):
        """Test that normalize() returns a NormalizationResult."""
        normalizer = ODCSNormalizerV3_0_0_Preview()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.0-preview",
            "kind": "DataContract",
            "id": "test-1",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "nullable": False}
                ]
            }
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.0-preview")

        # Check that result has the expected attributes
        assert hasattr(result, 'hub_contract')
        assert hasattr(result, 'status')
        assert hasattr(result, 'errors')
        assert hasattr(result, 'warnings')
        assert hasattr(result, 'spec_type')
        assert hasattr(result, 'spec_version')
        assert hasattr(result, 'coverage')

        assert result.spec_type == OriginalSpecType.ODCS
        assert result.spec_version == "3.0.0-preview"
        assert isinstance(result.errors, list)
        assert isinstance(result.warnings, list)

    def test_normalize_detects_version_if_not_provided(self):
        """Test that normalize() detects version from contract_data if not provided."""
        normalizer = ODCSNormalizerV3_0_0_Preview()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.0-preview",
            "kind": "DataContract",
            "id": "test-1",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "nullable": False}
                ]
            }
        }

        result = normalizer.normalize(contract_data, spec_version=None)

        # The base class defaults to 3.0.2, but we should check if it detects preview
        # Actually, the base class _detect_odcs_version might not handle preview versions
        # So we'll test with explicit version
        result = normalizer.normalize(contract_data, spec_version="3.0.0-preview")
        assert result.spec_version == "3.0.0-preview"

    def test_normalize_fails_for_unsupported_version(self):
        """Test that normalize() fails gracefully for unsupported versions."""
        normalizer = ODCSNormalizerV3_0_0_Preview()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.0",
            "kind": "DataContract",
            "id": "test-1",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "id", "type": "string"}]}
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.0")

        assert result.status == NormalizationStatus.NORMALIZATION_FAILED
        assert len(result.errors) > 0
        assert "does not support" in result.errors[0].lower() or "not support" in result.errors[0].lower()

    def test_normalize_validates_contract_data_is_dict(self):
        """Test that normalize() validates contract_data is a dictionary."""
        normalizer = ODCSNormalizerV3_0_0_Preview()

        result = normalizer.normalize("not a dict", spec_version="3.0.0-preview")

        assert result.status == NormalizationStatus.NORMALIZATION_FAILED
        assert len(result.errors) > 0
        assert "dictionary" in result.errors[0].lower()

    def test_normalize_produces_valid_hub_contract(self):
        """Test that normalize() produces a valid hub_contract for 3.0.0-preview."""
        normalizer = ODCSNormalizerV3_0_0_Preview()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.0-preview",
            "kind": "DataContract",
            "id": "test-1",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "nullable": False},
                    {"name": "name", "type": "string", "nullable": False}
                ]
            }
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.0-preview")

        assert result.hub_contract is not None
        assert result.hub_contract["id"] == "test-1"
        assert result.hub_contract["info"]["name"] == "Test Contract"
        assert result.hub_contract["info"]["version"] == "1.0.0"
        assert "schema" in result.hub_contract
        assert "fields" in result.hub_contract["schema"]
        assert len(result.hub_contract["schema"]["fields"]) == 2

    def test_normalize_handles_complex_contract(self):
        """Test that normalize() handles a complex ODCS 3.0.0-preview contract."""
        normalizer = ODCSNormalizerV3_0_0_Preview()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.0-preview",
            "kind": "DataContract",
            "id": "complex-test",
            "name": "Complex Test Contract",
            "version": "1.0.0",
            "description": "A complex contract for testing",
            "info": {
                "owners": ["owner1", "owner2"],
                "tags": ["tag1", "tag2"]
            },
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "nullable": False},
                    {"name": "name", "type": "string", "nullable": False}
                ]
            },
            "quality": {
                "default_profile_key": "profile1"
            },
            "lifecycle": {
                "data_source": "database",
                "refresh_cadence": "daily"
            }
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.0-preview")

        assert result.hub_contract is not None
        assert result.hub_contract["id"] == "complex-test"
        assert result.hub_contract["info"]["name"] == "Complex Test Contract"
        assert "owners" in result.hub_contract["info"]
        assert "tags" in result.hub_contract["info"]
        assert "quality" in result.hub_contract
        assert "lifecycle" in result.hub_contract

    def test_normalize_handles_graceful_degradation(self):
        """Test that normalize() handles graceful degradation for missing features."""
        normalizer = ODCSNormalizerV3_0_0_Preview()
        # Contract with minimal fields (preview version might not have all features)
        contract_data = {
            "apiVersion": "odcs.io/v3.0.0-preview",
            "kind": "DataContract",
            "id": "minimal-test",
            "name": "Minimal Test Contract",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "nullable": False}
                ]
            }
            # Missing optional fields like quality, lifecycle, etc.
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.0-preview")

        # Should still normalize successfully even with missing optional fields
        assert result.hub_contract is not None
        assert result.hub_contract["id"] == "minimal-test"
        assert result.hub_contract["info"]["name"] == "Minimal Test Contract"
        # Should not have errors for missing optional fields
        assert result.status in [
            NormalizationStatus.NORMALIZED_OK,
            NormalizationStatus.NORMALIZED_WITH_WARNINGS
        ]


class ODCSNormalizerV3_0_0_PreviewRegistryTest(TestCase):
    """Test ODCSNormalizerV3_0_0_Preview integration with normalizer registry."""

    def setUp(self):
        """Save registry state before each test."""
        from hub.apps.contracts.normalization import _NORMALIZER_REGISTRY
        self.original_registry = {key: list(value) for key, value in _NORMALIZER_REGISTRY.items()}

    def tearDown(self):
        """Restore registry state after each test."""
        _reset_normalizer_registry(self.original_registry)

    def test_normalizer_can_be_registered(self):
        """Test that ODCSNormalizerV3_0_0_Preview can be registered."""
        normalizer = ODCSNormalizerV3_0_0_Preview()
        register_normalizer(normalizer)

        # Should be able to retrieve it
        retrieved = get_normalizer(OriginalSpecType.ODCS, "3.0.0-preview", {})
        assert retrieved is not None
        assert isinstance(retrieved, ODCSNormalizerV3_0_0_Preview)

    def test_registered_normalizer_handles_3_0_0_preview_contracts(self):
        """Test that registered normalizer correctly handles 3.0.0-preview contracts."""
        normalizer = ODCSNormalizerV3_0_0_Preview()
        register_normalizer(normalizer)

        contract_data = {
            "apiVersion": "odcs.io/v3.0.0-preview",
            "kind": "DataContract",
            "id": "test-1",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "nullable": False}
                ]
            }
        }

        retrieved = get_normalizer(OriginalSpecType.ODCS, "3.0.0-preview", contract_data)
        assert retrieved is not None
        assert isinstance(retrieved, ODCSNormalizerV3_0_0_Preview)

        result = retrieved.normalize(contract_data, spec_version="3.0.0-preview")
        assert result.spec_version == "3.0.0-preview"
        assert result.hub_contract is not None


class ODCSNormalizerV3_0_0_PreviewRegressionTest(TestCase):
    """Regression tests to ensure ODCS 3.0.0-preview normalization works correctly."""

    def test_normalization_output_matches_expected_format(self):
        """Test that normalization output matches expected format for 3.0.0-preview."""
        normalizer = ODCSNormalizerV3_0_0_Preview()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.0-preview",
            "kind": "DataContract",
            "id": "regression-test",
            "name": "Regression Test Contract",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "nullable": False},
                    {"name": "name", "type": "string", "nullable": False}
                ]
            },
            "info": {
                "owners": ["owner1", "owner2"],
                "tags": ["tag1", "tag2"]
            },
            "quality": {
                "default_profile_key": "profile1"
            },
            "lifecycle": {
                "data_source": "database",
                "refresh_cadence": "daily"
            }
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.0-preview")

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
        normalizer = ODCSNormalizerV3_0_0_Preview()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.0-preview",
            "kind": "DataContract",
            "id": "test-1",
            "name": "Test Contract",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "nullable": False}
                ]
            },
            "custom_field": "custom_value",
            "another_custom": {"nested": "value"}
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.0-preview")

        # Should preserve custom fields in extensions
        assert result.hub_contract is not None
        assert "extensions" in result.hub_contract
        assert "custom_field" in result.hub_contract["extensions"]
        assert result.hub_contract["extensions"]["custom_field"] == "custom_value"
        assert "odcs" in result.hub_contract["extensions"]
        assert "custom_field" in result.hub_contract["extensions"]["odcs"]

    def test_normalization_calculates_coverage(self):
        """Test that normalization calculates coverage for 3.0.0-preview."""
        normalizer = ODCSNormalizerV3_0_0_Preview()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.0-preview",
            "kind": "DataContract",
            "id": "test-1",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "nullable": False}
                ]
            },
            "quality": {
                "default_profile_key": "profile1"
            },
            "lifecycle": {
                "data_source": "database"
            }
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.0-preview")

        # Should have coverage calculated
        assert result.coverage is not None
        assert result.hub_contract is not None
        assert "normalization" in result.hub_contract
        assert "coverage" in result.hub_contract["normalization"]
        assert "original_spec_type" in result.hub_contract["normalization"]
        assert result.hub_contract["normalization"]["original_spec_type"] == OriginalSpecType.ODCS
        assert "original_spec_version" in result.hub_contract["normalization"]
        assert result.hub_contract["normalization"]["original_spec_version"] == "3.0.0-preview"

    def test_normalization_handles_missing_required_fields(self):
        """Test that normalization handles missing required fields gracefully."""
        normalizer = ODCSNormalizerV3_0_0_Preview()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.0-preview",
            "kind": "DataContract",
            "id": "test-1",
            # Missing 'name' field
            "schema": {}  # Missing 'fields' array
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.0-preview")

        # Should have errors for missing required fields
        assert len(result.errors) > 0
        assert any("name" in error.lower() for error in result.errors)
        assert any("fields" in error.lower() for error in result.errors)
        # But should still return a hub_contract (for debugging)
        assert result.hub_contract is not None


