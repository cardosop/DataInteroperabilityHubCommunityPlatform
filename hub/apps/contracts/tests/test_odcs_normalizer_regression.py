"""
Regression tests for ODCSNormalizer refactoring.

These tests ensure that the refactoring of ODCSNormalizer into ODCSNormalizerBase
does not change the existing normalization behavior. All existing ODCS normalization
should produce identical results after the refactoring.
"""
import json
from unittest import TestCase

from hub.apps.contracts.models import NormalizationStatus, OriginalSpecType
from hub.apps.contracts.normalization import (
    ODCSNormalizer,
    normalize_odcs_to_hubcontract,
    NormalizationResult,
)


class ODCSNormalizerRegressionTest(TestCase):
    """Regression tests to ensure ODCSNormalizer behavior is unchanged."""

    def test_odcs_normalizer_api_unchanged(self):
        """Test that ODCSNormalizer API is unchanged."""
        normalizer = ODCSNormalizer()

        # Check that spec_type is still ODCS
        assert normalizer.spec_type == OriginalSpecType.ODCS

        # Check that supports() method still works
        assert normalizer.supports(OriginalSpecType.ODCS, "3.0.2", {})
        assert not normalizer.supports(OriginalSpecType.ODPS, "4.1", {})

    def test_odcs_normalizer_normalize_returns_same_format(self):
        """Test that ODCSNormalizer.normalize() returns the same format as before."""
        normalizer = ODCSNormalizer()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
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

        result = normalizer.normalize(contract_data, spec_version="3.0.2")

        # Check that result is a NormalizationResult
        assert hasattr(result, 'hub_contract')
        assert hasattr(result, 'status')
        assert hasattr(result, 'errors')
        assert hasattr(result, 'warnings')
        assert hasattr(result, 'spec_type')
        assert hasattr(result, 'spec_version')
        assert hasattr(result, 'coverage')

        # Check that spec_type and spec_version are correct
        assert result.spec_type == OriginalSpecType.ODCS
        assert result.spec_version == "3.0.2"

        # Check that hub_contract is not None for valid input
        assert result.hub_contract is not None
        assert result.hub_contract["id"] == "test-1"
        assert result.hub_contract["info"]["name"] == "Test Contract"

    def test_normalize_odcs_to_hubcontract_function_unchanged(self):
        """Test that normalize_odcs_to_hubcontract() function still works."""
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
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

        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(contract_data)

        # Check that return format is unchanged (tuple)
        assert isinstance(hub_contract, dict)
        assert isinstance(status, NormalizationStatus)
        assert isinstance(errors, list)
        assert isinstance(warnings, list)

        # Check that normalization succeeded
        assert status in [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS]
        assert hub_contract["id"] == "test-1"
        assert hub_contract["info"]["name"] == "Test Contract"

    def test_normalize_odcs_to_hubcontract_produces_same_output(self):
        """Test that normalize_odcs_to_hubcontract() produces the same output as before."""
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
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

        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(contract_data)

        # Check that all expected fields are present
        assert hub_contract is not None
        assert hub_contract["id"] == "regression-test"
        assert hub_contract["info"]["name"] == "Regression Test Contract"
        assert hub_contract["info"]["version"] == "1.0.0"
        assert "owners" in hub_contract["info"]
        assert "tags" in hub_contract["info"]
        assert "quality" in hub_contract
        assert "lifecycle" in hub_contract
        assert "schema" in hub_contract
        assert "fields" in hub_contract["schema"]
        assert len(hub_contract["schema"]["fields"]) == 2

    def test_odcs_normalizer_supports_all_versions(self):
        """Test that ODCSNormalizer (via default implementation) supports all versions."""
        normalizer = ODCSNormalizer()

        # Should support all ODCS versions (backward compatibility)
        assert normalizer.supports(OriginalSpecType.ODCS, "3.0.2", {})
        assert normalizer.supports(OriginalSpecType.ODCS, "3.0.1", {})
        assert normalizer.supports(OriginalSpecType.ODCS, "3.0.0", {})

    def test_odcs_normalizer_handles_missing_fields_gracefully(self):
        """Test that ODCSNormalizer handles missing fields gracefully (unchanged behavior)."""
        normalizer = ODCSNormalizer()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-1",
            # Missing 'name' field
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "nullable": False}
                ]
            }
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.2")

        # Should have errors for missing required fields
        assert len(result.errors) > 0
        assert any("name" in error.lower() for error in result.errors)
        # But should still return a hub_contract (for debugging)
        assert result.hub_contract is not None

    def test_odcs_normalizer_handles_empty_schema(self):
        """Test that ODCSNormalizer handles empty schema (unchanged behavior)."""
        normalizer = ODCSNormalizer()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-1",
            "name": "Test Contract",
            "schema": {
                "fields": []
            }
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.2")

        # Should have warnings for empty schema
        assert len(result.warnings) > 0
        assert any("fields" in warning.lower() for warning in result.warnings)

    def test_odcs_normalizer_preserves_extensions(self):
        """Test that ODCSNormalizer preserves unmappable fields in extensions (unchanged behavior)."""
        normalizer = ODCSNormalizer()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
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

        result = normalizer.normalize(contract_data, spec_version="3.0.2")

        # Should preserve custom fields in extensions
        assert result.hub_contract is not None
        assert "extensions" in result.hub_contract
        assert "custom_field" in result.hub_contract["extensions"]
        assert result.hub_contract["extensions"]["custom_field"] == "custom_value"
        assert "odcs" in result.hub_contract["extensions"]
        assert "custom_field" in result.hub_contract["extensions"]["odcs"]

    def test_odcs_normalizer_version_detection(self):
        """Test that ODCSNormalizer detects version correctly (unchanged behavior)."""
        normalizer = ODCSNormalizer()

        # Test with apiVersion
        contract_data1 = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-1",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "id", "type": "string"}]}
        }
        result1 = normalizer.normalize(contract_data1, spec_version=None)
        assert result1.spec_version == "3.0.2"

        # Test with version field
        contract_data2 = {
            "id": "test-2",
            "name": "Test Contract",
            "version": "3.0.1",
            "schema": {"fields": [{"name": "id", "type": "string"}]}
        }
        result2 = normalizer.normalize(contract_data2, spec_version=None)
        assert result2.spec_version == "3.0.1"

        # Test default
        contract_data3 = {
            "id": "test-3",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "id", "type": "string"}]}
        }
        result3 = normalizer.normalize(contract_data3, spec_version=None)
        assert result3.spec_version == "3.0.2"  # Default

    def test_odcs_normalizer_coverage_calculation(self):
        """Test that ODCSNormalizer calculates coverage (unchanged behavior)."""
        normalizer = ODCSNormalizer()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
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


