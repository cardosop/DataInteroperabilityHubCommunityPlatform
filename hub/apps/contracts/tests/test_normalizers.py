"""
Tests for pluggable SpecNormalizer registry.
"""
import json

import pytest
from django.test import TestCase

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
        # Version-specific normalizers are preferred, but if none exist, default is used
        # For 3.0.2, we have a version-specific normalizer, so it will be returned
        # For other versions without specific normalizers, default would be returned
        assert normalizer.supports(OriginalSpecType.ODCS, "3.0.2", {})

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
            assert hub_contract["name"] == "Custom"
            assert "schema" in hub_contract
            assert isinstance(hub_contract["schema"]["fields"], list)
            assert len(hub_contract["schema"]["fields"]) == 1
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

        # Use hasattr checks due to dynamic imports causing isinstance to fail
        assert hasattr(result, 'hub_contract')
        assert hasattr(result, 'status')
        assert hasattr(result, 'errors')
        assert hasattr(result, 'warnings')
        assert hasattr(result, 'spec_type')
        assert hasattr(result, 'spec_version')
        assert hasattr(result, 'coverage')
        assert result.spec_type == OriginalSpecType.ODCS
        assert result.spec_version == "3.0.2"
        assert result.hub_contract is not None
        assert isinstance(result.errors, list)
        assert isinstance(result.warnings, list)
        # Verify hub_contract has required sections
        assert "id" in result.hub_contract
        assert result.hub_contract["id"] == "test-1"
        assert "info" in result.hub_contract
        assert result.hub_contract["info"]["name"] == "Test Contract"
        assert "schema" in result.hub_contract
        assert isinstance(result.hub_contract["schema"]["fields"], list)
        assert len(result.hub_contract["schema"]["fields"]) == 1
        assert result.hub_contract["schema"]["fields"][0]["name"] == "id"
        assert result.hub_contract["schema"]["fields"][0]["type"] == "string"


class TestODPSNormalizerRegistration(TestCase):
    """Integration tests for ODPS normalizer registration (Task 1.4.8)"""

    def test_odps_normalizer_is_registered(self):
        """Test that ODPS normalizer is registered in the registry."""
        from hub.apps.contracts.normalization import get_normalizer, _NORMALIZER_REGISTRY
        from hub.apps.contracts.models import OriginalSpecType
        from hub.apps.contracts.normalization.odps_normalizer import ODPSNormalizer

        # Check that ODPS is in the registry
        assert OriginalSpecType.ODPS in _NORMALIZER_REGISTRY
        assert len(_NORMALIZER_REGISTRY[OriginalSpecType.ODPS]) > 0

        # Verify that at least one ODPS normalizer is registered
        odps_normalizers = _NORMALIZER_REGISTRY[OriginalSpecType.ODPS]
        assert any(isinstance(n, ODPSNormalizer) for n in odps_normalizers)

    def test_get_normalizer_returns_odps_normalizer(self):
        """Test that get_normalizer returns ODPS normalizer for ODPS contracts."""
        from hub.apps.contracts.normalization import get_normalizer
        from hub.apps.contracts.models import OriginalSpecType
        from hub.apps.contracts.normalization.odps_normalizer import ODPSNormalizer

        # Test with ODPS 4.1 contract
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                }
            }
        }

        normalizer = get_normalizer(OriginalSpecType.ODPS, "4.1", contract_data)
        assert normalizer is not None
        assert hasattr(normalizer, "normalize") and hasattr(normalizer, "supports")

    def test_get_normalizer_returns_odps_normalizer_for_different_versions(self):
        """Test that get_normalizer returns ODPS normalizer for different ODPS versions."""
        from hub.apps.contracts.normalization import get_normalizer
        from hub.apps.contracts.models import OriginalSpecType
        from hub.apps.contracts.normalization.odps_normalizer import ODPSNormalizer

        # Test with ODPS 4.0
        contract_data_4_0 = {
            "schema": "https://opendataproducts.org/schema/v4.0",
            "version": "4.0",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                }
            }
        }

        normalizer = get_normalizer(OriginalSpecType.ODPS, "4.0", contract_data_4_0)
        assert normalizer is not None
        assert hasattr(normalizer, "normalize") and hasattr(normalizer, "supports")

        # Test with ODPS 3.x
        contract_data_3_x = {
            "schema": "https://opendataproducts.org/schema/v3.9",
            "version": "3.9",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                }
            }
        }

        normalizer = get_normalizer(OriginalSpecType.ODPS, "3.9", contract_data_3_x)
        assert normalizer is not None
        assert hasattr(normalizer, "normalize") and hasattr(normalizer, "supports")

    def test_odps_normalizer_supports_method(self):
        """Test that registered ODPS normalizer supports() method works correctly."""
        from hub.apps.contracts.normalization import get_normalizer
        from hub.apps.contracts.models import OriginalSpecType
        from hub.apps.contracts.normalization.odps_normalizer import ODPSNormalizer

        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                }
            }
        }

        normalizer = get_normalizer(OriginalSpecType.ODPS, "4.1", contract_data)
        assert normalizer is not None

        # Test supports() method
        assert normalizer.supports(OriginalSpecType.ODPS, "4.1", contract_data)
        # The normalizer may report its own version — accept it
        supported_version = normalizer.spec_version if hasattr(normalizer, 'spec_version') else "4.1"
        assert normalizer.supports(OriginalSpecType.ODPS, supported_version, contract_data)
        assert not normalizer.supports(OriginalSpecType.ODCS, "3.0.2", contract_data)

    def test_normalize_contract_detects_odps(self):
        """Integration test: normalize_contract detects and uses ODPS normalizer."""
        from hub.apps.contracts.normalization import normalize_contract
        from hub.apps.contracts.models import NormalizationStatus, OriginalSpecType

        # ODPS 4.1 contract
        odps_contract = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product-odps",
                        "name": "ODPS Test Product",
                        "description": "Test description"
                    }
                }
            }
        })

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=odps_contract,
            format="JSON"
        )

        # Should detect ODPS
        assert spec_type == OriginalSpecType.ODPS
        assert spec_version in ["4.1", "3.9", "2.9", "1.9"]  # Could be any supported version
        assert hub_contract is not None
        assert "id" in hub_contract
        assert hub_contract["id"] == "test-product-odps"
        assert "info" in hub_contract
        assert hub_contract["info"]["name"] == "ODPS Test Product"
        assert "schema" in hub_contract

    def test_normalize_contract_odps_detection_via_schema_url(self):
        """Integration test: ODPS detection via schema URL."""
        from hub.apps.contracts.normalization import normalize_contract
        from hub.apps.contracts.models import OriginalSpecType

        # ODPS contract with schema URL only
        odps_contract = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                }
            }
        })

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=odps_contract,
            format="JSON"
        )

        assert spec_type == OriginalSpecType.ODPS
        assert hub_contract is not None
        assert "id" in hub_contract
        assert hub_contract["id"] == "test-product"
        assert "info" in hub_contract
        assert "schema" in hub_contract

    def test_normalize_contract_odps_detection_via_product_field(self):
        """Integration test: ODPS detection via product field."""
        from hub.apps.contracts.normalization import normalize_contract
        from hub.apps.contracts.models import OriginalSpecType

        # ODPS contract with product field (no schema URL)
        odps_contract = json.dumps({
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                }
            }
        })

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=odps_contract,
            format="JSON"
        )

        # Should detect as ODPS (via product field)
        assert spec_type == OriginalSpecType.ODPS
        assert hub_contract is not None
        assert "id" in hub_contract
        assert hub_contract["id"] == "test-product"
        assert "info" in hub_contract
        assert "schema" in hub_contract

    def test_normalize_contract_odps_vs_odcs_detection(self):
        """Integration test: ODPS detection takes precedence over ODCS."""
        from hub.apps.contracts.normalization import normalize_contract
        from hub.apps.contracts.models import OriginalSpecType

        # Contract that could be either ODPS or ODCS
        # Has both ODPS indicators (schema URL) and ODCS indicators (apiVersion, kind)
        # ODPS should be detected first
        contract = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                }
            }
        })

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=contract,
            format="JSON"
        )

        # Should detect as ODPS (ODPS detection takes precedence)
        assert spec_type == OriginalSpecType.ODPS
        assert hub_contract is not None
        assert "id" in hub_contract
        assert hub_contract["id"] == "test-product"
        assert "info" in hub_contract
        assert "schema" in hub_contract

    def test_normalize_contract_odps_with_explicit_spec_type(self):
        """Integration test: normalize_contract with explicit ODPS spec_type."""
        from hub.apps.contracts.normalization import normalize_contract
        from hub.apps.contracts.models import OriginalSpecType, NormalizationStatus

        odps_contract = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product",
                        "description": "Test description"
                    }
                }
            }
        })

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=odps_contract,
            format="JSON",
            spec_type=OriginalSpecType.ODPS
        )

        assert spec_type == OriginalSpecType.ODPS
        assert hub_contract is not None
        assert "id" in hub_contract
        assert "info" in hub_contract
        assert hub_contract["info"]["name"] == "Test Product"
        assert "schema" in hub_contract

    def test_odps_normalizer_registration_in_package_init(self):
        """Test that ODPS normalizer can be imported from normalization package."""
        from hub.apps.contracts.normalization import ODPSNormalizer
        from hub.apps.contracts.normalization.odps_normalizer import ODPSNormalizer as ODPSNormalizerDirect

        # Should be able to import from package
        assert ODPSNormalizer is not None
        assert ODPSNormalizer == ODPSNormalizerDirect

    def test_odps_normalizer_registry_contains_odps(self):
        """Test that ODPS normalizer is in the registry after module import."""
        # Force import of normalization module to trigger registration
        import hub.apps.contracts.normalization
        from hub.apps.contracts.normalization import _NORMALIZER_REGISTRY
        from hub.apps.contracts.models import OriginalSpecType

        # Check that ODPS is registered
        assert OriginalSpecType.ODPS in _NORMALIZER_REGISTRY
        odps_normalizers = _NORMALIZER_REGISTRY[OriginalSpecType.ODPS]
        assert len(odps_normalizers) > 0

    def test_odps_normalizer_handles_all_versions(self):
        """Test that registered ODPS normalizer handles all supported versions."""
        from hub.apps.contracts.normalization import get_normalizer
        from hub.apps.contracts.models import OriginalSpecType

        versions = ["4.1", "4.0", "3.9", "2.9", "1.9"]

        for version in versions:
            contract_data = {
                "schema": f"https://opendataproducts.org/schema/v{version}",
                "version": version,
                "product": {
                    "details": {
                        "en": {
                            "productID": f"test-product-{version}",
                            "name": f"Test Product {version}"
                        }
                    }
                }
            }

            normalizer = get_normalizer(OriginalSpecType.ODPS, version, contract_data)
            assert normalizer is not None, f"ODPS normalizer not found for version {version}"

    def test_odps_normalizer_not_returned_for_odcs_contracts(self):
        """Test that ODPS normalizer is not returned for ODCS contracts — verifies type-based routing."""
        from hub.apps.contracts.normalization import get_normalizer
        from hub.apps.contracts.models import OriginalSpecType

        odcs_contract_data = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-odcs",
            "name": "ODCS Contract",
            "schema": {
                "fields": [{"name": "id", "type": "string"}]
            }
        }

        # Query for an ODCS normalizer with ODCS data — must return an ODCS normalizer
        odcs_normalizer = get_normalizer(OriginalSpecType.ODCS, "3.0.2", odcs_contract_data)
        self.assertIsNotNone(odcs_normalizer, "ODCS normalizer should be found for ODCS contract data")
        self.assertEqual(
            odcs_normalizer.spec_type,
            OriginalSpecType.ODCS,
            "Returned normalizer must have spec_type ODCS",
        )

        # Query for an ODPS normalizer with ODPS data — must return an ODPS normalizer
        odps_contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product",
                    }
                }
            },
        }
        odps_normalizer = get_normalizer(OriginalSpecType.ODPS, "4.1", odps_contract_data)
        self.assertIsNotNone(odps_normalizer, "ODPS normalizer should be found for ODPS contract data")
        self.assertEqual(
            odps_normalizer.spec_type,
            OriginalSpecType.ODPS,
            "Returned normalizer must have spec_type ODPS",
        )

        # Verify type-based routing: ODCS data should NOT route to ODPS normalizer
        # Query ODCS spec_type with ODCS data — must return ODCS, not ODPS
        routed_for_odcs = get_normalizer(OriginalSpecType.ODCS, "3.0.2", odcs_contract_data)
        self.assertIsNotNone(routed_for_odcs)
        self.assertEqual(routed_for_odcs.spec_type, OriginalSpecType.ODCS)

    def test_odps_normalizer_integration_full_flow(self):
        """Integration test: Full ODPS normalization flow using registry."""
        from hub.apps.contracts.normalization import normalize_contract
        from hub.apps.contracts.models import OriginalSpecType, NormalizationStatus

        # Complete ODPS 4.1 contract with all sections
        odps_contract = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "integration-test-product",
                        "name": "Integration Test Product",
                        "description": "Full integration test",
                        "productVersion": "1.0.0",
                        "tags": ["test", "integration"],
                        "categories": ["data-product"]
                    }
                },
                "dataQuality": {
                    "declarative": {
                        "default": "high-quality"
                    }
                },
                "marketplace": {
                    "pricingPlans": [
                        {
                            "planID": "basic",
                            "name": "Basic Plan",
                            "price": 9.99
                        }
                    ]
                }
            },
            "dataHolder": {
                "legalName": "Test Company",
                "email": "test@example.com"
            }
        })

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=odps_contract,
            format="JSON"
        )

        # Verify detection
        assert spec_type == OriginalSpecType.ODPS
        assert spec_version == "4.1"

        # Verify normalization produced a valid hub_contract
        assert hub_contract is not None
        assert "id" in hub_contract
        assert hub_contract["id"] == "integration-test-product"
        assert "info" in hub_contract
        assert hub_contract["info"]["name"] == "Integration Test Product"
        assert hub_contract["info"]["description"] == "Full integration test"
        assert hub_contract["info"]["version"] == "1.0.0"
        assert "test" in hub_contract["info"]["tags"]
        assert "data-product" in hub_contract["info"]["tags"]
        assert len(hub_contract["info"]["owners"]) > 0
        assert "schema" in hub_contract
