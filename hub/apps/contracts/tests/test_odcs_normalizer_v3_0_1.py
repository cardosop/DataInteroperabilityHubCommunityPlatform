"""
Unit tests for ODCSNormalizerV3_0_1.

Tests the ODCS 3.0.1-specific normalizer implementation including:
- Version support checking
- Normalization flow for 3.0.1 contracts
- Graceful degradation for missing 3.0.2 features
- Error handling
"""

from typing import Any, Dict
from unittest import TestCase

import pytest

from hub.apps.contracts.models import NormalizationStatus, OriginalSpecType
from hub.apps.contracts.normalization import NormalizationResult, get_normalizer
from hub.apps.contracts.normalization.odcs_normalizer_v3_0_1 import ODCSNormalizerV3_0_1


class ODCSNormalizerV3_0_1StructureTest(TestCase):
    """Test that ODCSNormalizerV3_0_1 is properly structured."""

    def test_can_instantiate_normalizer(self):
        """Test that ODCSNormalizerV3_0_1 can be instantiated."""
        normalizer = ODCSNormalizerV3_0_1()
        assert normalizer is not None
        assert isinstance(normalizer, ODCSNormalizerV3_0_1)

    def test_spec_type_is_odcs(self):
        """Test that spec_type is set to ODCS."""
        normalizer = ODCSNormalizerV3_0_1()
        assert normalizer.spec_type == OriginalSpecType.ODCS


class ODCSNormalizerV3_0_1SupportsTest(TestCase):
    """Test the supports() and _supports_version() methods."""

    def test_supports_version_3_0_1(self):
        """Test that supports() returns True for version 3.0.1 through public API."""
        normalizer = ODCSNormalizerV3_0_1()
        contract_data = {"apiVersion": "odcs.io/v3.0.1", "kind": "DataContract"}
        # Test through public API - supports() internally calls _supports_version()
        assert normalizer.supports(OriginalSpecType.ODCS, "3.0.1", contract_data) is True

    def test_supports_version_does_not_support_3_0_2(self):
        """Test that supports() returns False for version 3.0.2 through public API."""
        normalizer = ODCSNormalizerV3_0_1()
        contract_data = {"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract"}
        # Test through public API - supports() internally calls _supports_version()
        assert normalizer.supports(OriginalSpecType.ODCS, "3.0.2", contract_data) is False

    def test_supports_version_does_not_support_3_0_0(self):
        """Test that supports() returns False for version 3.0.0 through public API."""
        normalizer = ODCSNormalizerV3_0_1()
        contract_data = {"apiVersion": "odcs.io/v3.0.0", "kind": "DataContract"}
        # Test through public API - supports() internally calls _supports_version()
        assert normalizer.supports(OriginalSpecType.ODCS, "3.0.0", contract_data) is False

    def test_supports_odcs_spec_type_3_0_1(self):
        """Test that supports() returns True for ODCS spec type with version 3.0.1."""
        normalizer = ODCSNormalizerV3_0_1()
        assert normalizer.supports(OriginalSpecType.ODCS, "3.0.1", {}) is True

    def test_supports_does_not_support_other_versions(self):
        """Test that supports() returns False for other ODCS versions."""
        normalizer = ODCSNormalizerV3_0_1()
        assert normalizer.supports(OriginalSpecType.ODCS, "3.0.2", {}) is False
        assert normalizer.supports(OriginalSpecType.ODCS, "3.0.0", {}) is False

    def test_supports_does_not_support_other_spec_types(self):
        """Test that supports() returns False for non-ODCS spec types."""
        normalizer = ODCSNormalizerV3_0_1()
        assert normalizer.supports(OriginalSpecType.ODPS, "4.1", {}) is False
        assert normalizer.supports("CUSTOM", "1.0", {}) is False


class ODCSNormalizerV3_0_1NormalizeTest(TestCase):
    """Test the normalize() method for ODCS 3.0.1 contracts."""

    def test_normalize_returns_normalization_result(self):
        """Test that normalize() returns a NormalizationResult for 3.0.1 contract."""
        normalizer = ODCSNormalizerV3_0_1()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.1",
            "kind": "DataContract",
            "id": "test-1",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.1")

        # Check that result has the expected attributes
        assert hasattr(result, "hub_contract")
        assert hasattr(result, "status")
        assert hasattr(result, "errors")
        assert hasattr(result, "warnings")
        assert hasattr(result, "spec_type")
        assert hasattr(result, "spec_version")
        assert hasattr(result, "coverage")

        assert result.spec_type == OriginalSpecType.ODCS
        assert result.spec_version == "3.0.1"
        assert isinstance(result.errors, list)
        assert isinstance(result.warnings, list)

    def test_normalize_detects_version_from_api_version(self):
        """Test that normalize() detects version 3.0.1 from apiVersion field."""
        normalizer = ODCSNormalizerV3_0_1()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.1",
            "kind": "DataContract",
            "id": "test-1",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
        }

        result = normalizer.normalize(contract_data, spec_version=None)

        assert result.spec_version == "3.0.1"

    def test_normalize_detects_version_from_version_field(self):
        """Test that normalize() detects version 3.0.1 from version field."""
        normalizer = ODCSNormalizerV3_0_1()
        contract_data = {
            "version": "3.0.1",
            "id": "test-1",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
        }

        result = normalizer.normalize(contract_data, spec_version=None)

        assert result.spec_version == "3.0.1"

    def test_normalize_fails_for_unsupported_version(self):
        """Test that normalize() fails gracefully for unsupported versions."""
        normalizer = ODCSNormalizerV3_0_1()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-1",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.2")

        assert result.status == NormalizationStatus.NORMALIZATION_FAILED
        assert len(result.errors) > 0
        assert (
            "does not support" in result.errors[0].lower()
            or "not support" in result.errors[0].lower()
        )

    def test_normalize_validates_contract_data_is_dict(self):
        """Test that normalize() validates contract_data is a dictionary."""
        normalizer = ODCSNormalizerV3_0_1()

        result = normalizer.normalize("not a dict", spec_version="3.0.1")

        assert result.status == NormalizationStatus.NORMALIZATION_FAILED
        assert len(result.errors) > 0
        assert "dictionary" in result.errors[0].lower()

    def test_normalize_handles_missing_required_fields(self):
        """Test that normalize() handles missing required fields gracefully."""
        normalizer = ODCSNormalizerV3_0_1()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.1",
            "kind": "DataContract",
            "id": "test-1",
            # Missing 'name' field
            "schema": {},  # Missing 'fields' array
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.1")

        # Should have errors for missing required fields
        assert len(result.errors) > 0
        assert any("name" in error.lower() for error in result.errors)
        assert any("fields" in error.lower() for error in result.errors)

    def test_normalize_successful_normalization(self):
        """Test successful normalization of a complete 3.0.1 contract."""
        normalizer = ODCSNormalizerV3_0_1()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.1",
            "kind": "DataContract",
            "id": "test-contract-3-0-1",
            "name": "Test Contract 3.0.1",
            "version": "1.0.0",
            "description": "A test contract for ODCS 3.0.1",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "nullable": False},
                    {"name": "value", "type": "integer", "nullable": True},
                ]
            },
            "info": {"owners": ["owner1@example.com"], "tags": ["test", "3.0.1"]},
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.1")

        assert result.status in [
            NormalizationStatus.NORMALIZED_OK,
            NormalizationStatus.NORMALIZED_WITH_WARNINGS,
        ]
        assert result.hub_contract is not None
        assert result.hub_contract["id"] == "test-contract-3-0-1"
        assert result.hub_contract["info"]["name"] == "Test Contract 3.0.1"
        assert result.hub_contract["info"]["description"] == "A test contract for ODCS 3.0.1"
        assert "models" in result.hub_contract
        assert len(result.hub_contract["models"]) > 0


class ODCSNormalizerV3_0_1GracefulDegradationTest(TestCase):
    """Test graceful degradation for missing 3.0.2 features."""

    def test_normalize_handles_missing_optional_fields(self):
        """Test that normalize() handles missing optional fields gracefully."""
        normalizer = ODCSNormalizerV3_0_1()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.1",
            "kind": "DataContract",
            "id": "test-1",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
            # Missing optional fields like quality, lifecycle, marketplace, etc.
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.1")

        # Should succeed even without optional fields
        assert result.status in [
            NormalizationStatus.NORMALIZED_OK,
            NormalizationStatus.NORMALIZED_WITH_WARNINGS,
        ]
        assert result.hub_contract is not None
        assert result.hub_contract["id"] == "test-1"
        assert result.hub_contract["info"]["name"] == "Test Contract"

    def test_map_version_specific_fields_handles_unexpected_version(self):
        """Test that _map_version_specific_fields logs warning for unexpected version."""
        normalizer = ODCSNormalizerV3_0_1()
        odcs_contract = {"id": "test"}
        hub_contract = {"id": "test"}
        warnings = []

        # Should not raise an exception even with unexpected version
        normalizer._map_version_specific_fields(odcs_contract, hub_contract, warnings, "3.0.2")

        # Should not modify hub_contract structure
        assert hub_contract["id"] == "test"

    def test_normalize_with_complex_3_0_1_contract(self):
        """Test normalization of a complex 3.0.1 contract with multiple sections."""
        normalizer = ODCSNormalizerV3_0_1()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.1",
            "kind": "DataContract",
            "id": "complex-contract-3-0-1",
            "name": "Complex Contract 3.0.1",
            "version": "2.0.0",
            "description": "A complex test contract",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "nullable": False},
                    {"name": "timestamp", "type": "datetime", "nullable": False},
                    {"name": "data", "type": "string", "nullable": True},
                ]
            },
            "info": {
                "owners": ["owner1@example.com", "owner2@example.com"],
                "tags": ["production", "critical"],
            },
            "quality": {"default_profile_key": "profile1", "rules": []},
            "privacy_compliance": {
                "contains_personal_data": True,
                "personal_data_categories": ["PII"],
            },
            "lifecycle": {"data_source": "database", "refresh_cadence": "daily"},
            "marketplace": {"license_summary": "MIT", "intended_use": "Analytics"},
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.1")

        assert result.status in [
            NormalizationStatus.NORMALIZED_OK,
            NormalizationStatus.NORMALIZED_WITH_WARNINGS,
        ]
        assert result.hub_contract is not None
        assert result.hub_contract["id"] == "complex-contract-3-0-1"
        assert "quality" in result.hub_contract
        assert "privacy_compliance" in result.hub_contract
        assert "lifecycle" in result.hub_contract
        assert "marketplace" in result.hub_contract


class ODCSNormalizerV3_0_1RegistryTest(TestCase):
    """Test that ODCSNormalizerV3_0_1 is properly registered."""

    def test_normalizer_is_registered(self):
        """Test that ODCSNormalizerV3_0_1 can be retrieved from registry."""
        normalizer = get_normalizer(OriginalSpecType.ODCS, "3.0.1", {})
        assert normalizer is not None
        assert isinstance(normalizer, ODCSNormalizerV3_0_1)

    def test_registry_returns_correct_normalizer_for_3_0_1(self):
        """Test that registry returns ODCSNormalizerV3_0_1 for version 3.0.1."""
        contract_data = {
            "apiVersion": "odcs.io/v3.0.1",
            "kind": "DataContract",
            "id": "test",
            "name": "Test",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }

        normalizer = get_normalizer(OriginalSpecType.ODCS, "3.0.1", contract_data)

        assert normalizer is not None
        assert isinstance(normalizer, ODCSNormalizerV3_0_1)

    def test_registry_normalizes_3_0_1_contract(self):
        """Test that registered normalizer can normalize a 3.0.1 contract."""
        contract_data = {
            "apiVersion": "odcs.io/v3.0.1",
            "kind": "DataContract",
            "id": "test-registry",
            "name": "Test Registry",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
        }

        normalizer = get_normalizer(OriginalSpecType.ODCS, "3.0.1", contract_data)
        assert normalizer is not None

        result = normalizer.normalize(contract_data, spec_version="3.0.1")

        assert result.status in [
            NormalizationStatus.NORMALIZED_OK,
            NormalizationStatus.NORMALIZED_WITH_WARNINGS,
        ]
        assert result.hub_contract is not None
        assert result.spec_version == "3.0.1"

    def test_normalization_handles_unicode_characters(self):
        """Test that normalization handles unicode characters correctly."""
        normalizer = ODCSNormalizerV3_0_1()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.1",
            "kind": "DataContract",
            "id": "test-unicode",
            "name": "测试合同",
            "version": "1.0.0",
            "description": "测试描述",
            "schema": {"fields": [{"name": "字段名称", "type": "string"}]},
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.1")

        # Should handle unicode characters
        assert result.hub_contract is not None
        if result.hub_contract and "info" in result.hub_contract:
            assert result.hub_contract["info"] is not None

    def test_normalization_handles_special_characters(self):
        """Test that normalization handles special characters correctly."""
        normalizer = ODCSNormalizerV3_0_1()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.1",
            "kind": "DataContract",
            "id": "test-special",
            "name": "Test & Co. (Special)",
            "version": "1.0.0",
            "description": "Test <description> & more",
            "schema": {"fields": [{"name": "field-name", "type": "string"}]},
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.1")

        # Should handle special characters
        assert result.hub_contract is not None
        if result.hub_contract and "info" in result.hub_contract:
            assert result.hub_contract["info"] is not None

    def test_normalization_handles_very_large_documents(self):
        """Test that normalization handles very large documents correctly."""
        normalizer = ODCSNormalizerV3_0_1()
        large_description = "A" * 100000  # 100KB string
        contract_data = {
            "apiVersion": "odcs.io/v3.0.1",
            "kind": "DataContract",
            "id": "test-large",
            "name": "Test Product",
            "version": "1.0.0",
            "description": large_description,
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.1")

        # Should handle very large documents
        assert result.hub_contract is not None

    def test_normalization_handles_none_values(self):
        """Test that normalization handles None values correctly."""
        normalizer = ODCSNormalizerV3_0_1()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.1",
            "kind": "DataContract",
            "id": "test-none",
            "name": "Test Product",
            "version": "1.0.0",
            "description": None,  # None value
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.1")

        # Should handle None values gracefully
        assert result.hub_contract is not None

    def test_normalization_handles_nested_structures(self):
        """Test that normalization handles nested structures correctly."""
        normalizer = ODCSNormalizerV3_0_1()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.1",
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

        result = normalizer.normalize(contract_data, spec_version="3.0.1")

        # Should handle nested structures
        assert result.hub_contract is not None
        if result.hub_contract and "schema" in result.hub_contract:
            assert result.hub_contract["schema"] is not None
