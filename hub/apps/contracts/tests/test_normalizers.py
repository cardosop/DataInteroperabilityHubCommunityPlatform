"""
Tests for pluggable SpecNormalizer registry.
"""
import json

import pytest

from hub.apps.contracts.models import NormalizationStatus, OriginalSpecType
from hub.apps.contracts.normalization import (
    NormalizationResult,
    ODCSNormalizer,
    _NORMALIZER_REGISTRY,
    _reset_normalizer_registry,
    get_normalizer,
    normalize_contract,
    register_normalizer,
)


class DummyNormalizer:
    spec_type = "CUSTOM"

    def supports(self, spec_type: str, spec_version: str, contract_data):
        return spec_type == self.spec_type

    def normalize(self, contract_data, spec_version=None) -> NormalizationResult:
        hub_contract = contract_data.copy()
        hub_contract.setdefault("hub_contract_version", "1.0.0")
        hub_contract.setdefault("schema", {"fields": [{"name": "id", "data_type": "string"}]})
        return NormalizationResult(
            hub_contract=hub_contract,
            status=NormalizationStatus.NORMALIZED_OK,
            errors=[],
            warnings=[],
            spec_type=self.spec_type,
            spec_version=spec_version or "1.0",
            coverage=None,
        )


class TestNormalizerRegistry:
    """Tests for normalizer registry functionality."""

    def test_registry_returns_odcs_normalizer_by_default(self):
        """Test that ODCS normalizer is registered by default."""
        normalizer = get_normalizer(OriginalSpecType.ODCS, "3.0.2", {})
        assert normalizer is not None
        assert isinstance(normalizer, ODCSNormalizer)

    def test_register_and_select_custom_normalizer(self):
        """Test registering and selecting a custom normalizer."""
        snapshot = {key: list(value) for key, value in _NORMALIZER_REGISTRY.items()}
        dummy = DummyNormalizer()
        try:
            register_normalizer(dummy)
            selected = get_normalizer(dummy.spec_type, "1.0", {"id": "x"})
            assert selected is dummy
        finally:
            _reset_normalizer_registry(snapshot)

    def test_normalize_contract_uses_registry(self):
        """Test that normalize_contract uses the registry."""
        snapshot = {key: list(value) for key, value in _NORMALIZER_REGISTRY.items()}
        dummy = DummyNormalizer()
        try:
            _reset_normalizer_registry(snapshot)
            register_normalizer(dummy)

            payload = {"id": "custom-id", "name": "Custom", "schema": {"fields": [{"name": "id", "type": "string"}]}}
            hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
                raw_contract=json.dumps(payload),
                format="JSON",
                spec_type=dummy.spec_type,
            )

            assert status == NormalizationStatus.NORMALIZED_OK
            assert spec_type == dummy.spec_type
            assert not errors
            assert hub_contract["id"] == "custom-id"
        finally:
            _reset_normalizer_registry(snapshot)

    def test_get_normalizer_returns_none_for_unsupported_spec(self):
        """Test that get_normalizer returns None for unsupported spec types."""
        normalizer = get_normalizer("UNSUPPORTED", "1.0", {})
        assert normalizer is None

    def test_multiple_normalizers_same_spec_type(self):
        """Test that multiple normalizers can be registered for the same spec type."""
        snapshot = {key: list(value) for key, value in _NORMALIZER_REGISTRY.items()}
        dummy1 = DummyNormalizer()
        dummy2 = DummyNormalizer()
        try:
            register_normalizer(dummy1)
            register_normalizer(dummy2)

            # Should return the first one that supports
            selected = get_normalizer(dummy1.spec_type, "1.0", {"id": "x"})
            assert selected is not None
            assert selected in [dummy1, dummy2]
        finally:
            _reset_normalizer_registry(snapshot)

    def test_reset_normalizer_registry(self):
        """Test that registry can be reset to a snapshot."""
        snapshot = {key: list(value) for key, value in _NORMALIZER_REGISTRY.items()}
        dummy = DummyNormalizer()
        try:
            register_normalizer(dummy)
            assert dummy.spec_type in _NORMALIZER_REGISTRY
            _reset_normalizer_registry(snapshot)
            # Should be back to original state
            assert _NORMALIZER_REGISTRY == snapshot or len(_NORMALIZER_REGISTRY.get(dummy.spec_type, [])) == len(
                snapshot.get(dummy.spec_type, [])
            )
        finally:
            _reset_normalizer_registry(snapshot)


class TestODCSNormalizer:
    """Tests for ODCSNormalizer implementation."""

    def test_odcs_normalizer_supports_odcs(self):
        """Test that ODCSNormalizer supports ODCS spec type."""
        normalizer = ODCSNormalizer()
        assert normalizer.supports(OriginalSpecType.ODCS, "3.0.2", {"apiVersion": "odcs/v3", "kind": "DataContract"})

    def test_odcs_normalizer_does_not_support_other_specs(self):
        """Test that ODCSNormalizer does not support other spec types."""
        normalizer = ODCSNormalizer()
        assert not normalizer.supports("CUSTOM", "1.0", {})

    def test_odcs_normalizer_normalize_returns_result(self):
        """Test that ODCSNormalizer.normalize returns NormalizationResult."""
        normalizer = ODCSNormalizer()
        contract_data = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-1",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.2")

        assert isinstance(result, NormalizationResult)
        assert result.spec_type == OriginalSpecType.ODCS
        assert result.spec_version == "3.0.2"
        assert result.hub_contract is not None
        assert isinstance(result.errors, list)
        assert isinstance(result.warnings, list)
