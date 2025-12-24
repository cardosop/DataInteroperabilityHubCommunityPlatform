"""
Unit tests for ODCSNormalizerBase abstract class.

Tests the base class functionality including:
- Abstract class structure
- Version support checking
- Normalization flow
- Helper methods
- Error handling
"""
import pytest
from unittest import TestCase
from typing import Dict, Any

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
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "nullable": False}
                ]
            }
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.2")

        # Check that result has the expected attributes (using hasattr due to dynamic imports)
        assert hasattr(result, 'hub_contract')
        assert hasattr(result, 'status')
        assert hasattr(result, 'errors')
        assert hasattr(result, 'warnings')
        assert hasattr(result, 'spec_type')
        assert hasattr(result, 'spec_version')
        assert hasattr(result, 'coverage')

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
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "nullable": False}
                ]
            }
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
            "schema": {"fields": [{"name": "id", "type": "string"}]}
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.1")

        assert result.status == NormalizationStatus.NORMALIZATION_FAILED
        assert len(result.errors) > 0
        assert "does not support" in result.errors[0].lower() or "not support" in result.errors[0].lower()

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
            "schema": {}  # Missing 'fields' array
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
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "nullable": False}
                ]
            }
        }

        # This should not raise an exception
        result = normalizer.normalize(contract_data, spec_version="3.0.2")

        assert result is not None
        assert hasattr(result, 'status')


class ODCSNormalizerBaseHelperMethodsTest(TestCase):
    """Test helper methods of ODCSNormalizerBase."""

    def test_detect_odcs_version_from_api_version(self):
        """Test that _detect_odcs_version extracts version from apiVersion."""
        normalizer = ConcreteODCSNormalizer()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract"
        }

        version = normalizer._detect_odcs_version(contract_data)

        assert version == "3.0.2"

    def test_detect_odcs_version_from_version_field(self):
        """Test that _detect_odcs_version extracts version from version field."""
        normalizer = ConcreteODCSNormalizer()
        contract_data = {
            "version": "3.0.1"
        }

        version = normalizer._detect_odcs_version(contract_data)

        assert version == "3.0.1"

    def test_detect_odcs_version_defaults_to_3_0_2(self):
        """Test that _detect_odcs_version defaults to 3.0.2 if version cannot be detected."""
        normalizer = ConcreteODCSNormalizer()
        contract_data = {}

        version = normalizer._detect_odcs_version(contract_data)

        assert version == "3.0.2"

    def test_map_version_specific_fields_default_implementation(self):
        """Test that _map_version_specific_fields has a default no-op implementation."""
        normalizer = ConcreteODCSNormalizer()
        odcs_contract = {"id": "test"}
        hub_contract = {"id": "test"}
        warnings = []

        # Should not raise an exception
        normalizer._map_version_specific_fields(odcs_contract, hub_contract, warnings, "3.0.2")

        # Should not modify anything by default
        assert hub_contract == {"id": "test"}
        assert len(warnings) == 0


class ODCSNormalizerBaseNormalizationMethodsTest(TestCase):
    """Test the normalization helper methods of ODCSNormalizerBase."""

    def test_normalize_info(self):
        """Test _normalize_info method."""
        normalizer = ConcreteODCSNormalizer()
        odcs_contract = {
            "info": {
                "owners": ["owner1"],
                "tags": ["tag1"]
            },
            "owners": ["owner2"],  # Top-level owners should override
            "tags": ["tag2"]  # Top-level tags should override
        }
        hub_contract = {
            "info": {
                "name": "Test"
            }
        }
        warnings = []

        normalizer._normalize_info(odcs_contract, hub_contract, warnings)

        # Top-level owners/tags should override info section
        # Owners are normalized from strings to HubContractOwner format
        assert hub_contract["info"]["owners"] == [{"name": "owner2"}]
        assert hub_contract["info"]["tags"] == ["tag2"]

    def test_normalize_schema(self):
        """Test _normalize_schema method."""
        normalizer = ConcreteODCSNormalizer()
        odcs_contract = {
            "name": "Test Contract",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "nullable": False}
                ]
            }
        }
        hub_contract = {
            "info": {"name": "Test Contract"},
            "schema": {}
        }
        warnings = []

        normalizer._normalize_schema(odcs_contract, hub_contract, warnings)

        # Should have models and schema derived
        assert "models" in hub_contract
        assert len(hub_contract["models"]) > 0
        assert "fields" in hub_contract["schema"]

    def test_normalize_quality(self):
        """Test _normalize_quality method."""
        normalizer = ConcreteODCSNormalizer()
        odcs_contract = {
            "quality": {
                "default_profile_key": "profile1",
                "rules": []
            }
        }
        hub_contract = {}
        warnings = []

        normalizer._normalize_quality(odcs_contract, hub_contract, warnings)

        assert "quality" in hub_contract
        assert hub_contract["quality"]["default_profile_key"] == "profile1"

    def test_normalize_privacy_compliance(self):
        """Test _normalize_privacy_compliance method."""
        normalizer = ConcreteODCSNormalizer()
        odcs_contract = {
            "privacy_compliance": {
                "contains_personal_data": True,
                "personal_data_categories": ["PII"]
            }
        }
        hub_contract = {}
        warnings = []

        normalizer._normalize_privacy_compliance(odcs_contract, hub_contract, warnings)

        assert "privacy_compliance" in hub_contract
        assert hub_contract["privacy_compliance"]["contains_personal_data"] is True

    def test_normalize_lifecycle(self):
        """Test _normalize_lifecycle method."""
        normalizer = ConcreteODCSNormalizer()
        odcs_contract = {
            "lifecycle": {
                "data_source": "database",
                "refresh_cadence": "daily"
            }
        }
        hub_contract = {}
        warnings = []

        normalizer._normalize_lifecycle(odcs_contract, hub_contract, warnings)

        assert "lifecycle" in hub_contract
        assert hub_contract["lifecycle"]["data_source"] == "database"

    def test_validate_required_fields(self):
        """Test _validate_required_fields method."""
        normalizer = ConcreteODCSNormalizer()
        hub_contract = {
            "info": {
                # Missing 'name'
            },
            "schema": {
                # Missing 'fields'
            }
        }
        errors = []
        warnings = []

        normalizer._validate_required_fields(hub_contract, errors, warnings)

        assert len(errors) > 0
        assert any("name" in error.lower() for error in errors)
        assert any("fields" in error.lower() for error in errors)


