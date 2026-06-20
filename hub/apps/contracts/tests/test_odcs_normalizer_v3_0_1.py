"""
Unit tests for ODCSNormalizerV3_0_1.

Tests the ODCS 3.0.1-specific normalizer implementation including:
- Version support checking
- Normalization flow for 3.0.1 contracts
- Graceful degradation for missing 3.0.2 features
- Error handling
"""

from unittest import TestCase

from hub.apps.contracts.models import NormalizationStatus, OriginalSpecType
from hub.apps.contracts.normalization import get_normalizer
from hub.apps.contracts.normalization.odcs_normalizer_v3_0_1 import ODCSNormalizerV3_0_1
from hub.apps.contracts.tests.normalizer_edge_case_mixin import ODCSEdgeCaseMixin


class ODCSNormalizerV3_0_1StructureTest(TestCase):
    """Test that ODCSNormalizerV3_0_1 is properly structured."""

    def test_can_instantiate_normalizer(self):
        """Test that ODCSNormalizerV3_0_1 can be instantiated."""
        normalizer = ODCSNormalizerV3_0_1()
        self.assertIsNotNone(normalizer)
        self.assertIsInstance(normalizer, ODCSNormalizerV3_0_1)

    def test_spec_type_is_odcs(self):
        """Test that spec_type is set to ODCS."""
        normalizer = ODCSNormalizerV3_0_1()
        self.assertEqual(normalizer.spec_type, OriginalSpecType.ODCS)


class ODCSNormalizerV3_0_1SupportsTest(TestCase):
    """Test the supports() and _supports_version() methods."""

    def test_supports_version_3_0_1(self):
        """Test that supports() returns True for version 3.0.1 through public API."""
        normalizer = ODCSNormalizerV3_0_1()
        contract_data = {"apiVersion": "odcs.io/v3.0.1", "kind": "DataContract"}
        # Test through public API - supports() internally calls _supports_version()
        self.assertTrue(normalizer.supports(OriginalSpecType.ODCS, "3.0.1", contract_data) is True)

    def test_supports_version_does_not_support_3_0_2(self):
        """Test that supports() returns False for version 3.0.2 through public API."""
        normalizer = ODCSNormalizerV3_0_1()
        contract_data = {"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract"}
        # Test through public API - supports() internally calls _supports_version()
        self.assertTrue(normalizer.supports(OriginalSpecType.ODCS, "3.0.2", contract_data) is False)

    def test_supports_version_does_not_support_3_0_0(self):
        """Test that supports() returns False for version 3.0.0 through public API."""
        normalizer = ODCSNormalizerV3_0_1()
        contract_data = {"apiVersion": "odcs.io/v3.0.0", "kind": "DataContract"}
        # Test through public API - supports() internally calls _supports_version()
        self.assertTrue(normalizer.supports(OriginalSpecType.ODCS, "3.0.0", contract_data) is False)

    def test_supports_odcs_spec_type_3_0_1(self):
        """Test that supports() returns True for ODCS spec type with version 3.0.1."""
        normalizer = ODCSNormalizerV3_0_1()
        self.assertTrue(normalizer.supports(OriginalSpecType.ODCS, "3.0.1", {}) is True)

    def test_supports_does_not_support_other_versions(self):
        """Test that supports() returns False for other ODCS versions."""
        normalizer = ODCSNormalizerV3_0_1()
        self.assertTrue(normalizer.supports(OriginalSpecType.ODCS, "3.0.2", {}) is False)
        self.assertTrue(normalizer.supports(OriginalSpecType.ODCS, "3.0.0", {}) is False)

    def test_supports_does_not_support_other_spec_types(self):
        """Test that supports() returns False for non-ODCS spec types."""
        normalizer = ODCSNormalizerV3_0_1()
        self.assertTrue(normalizer.supports(OriginalSpecType.ODPS, "4.1", {}) is False)
        self.assertTrue(normalizer.supports("CUSTOM", "1.0", {}) is False)


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
        self.assertTrue(hasattr(result, "hub_contract"))
        self.assertTrue(hasattr(result, "status"))
        self.assertTrue(hasattr(result, "errors"))
        self.assertTrue(hasattr(result, "warnings"))
        self.assertTrue(hasattr(result, "spec_type"))
        self.assertTrue(hasattr(result, "spec_version"))
        self.assertTrue(hasattr(result, "coverage"))

        self.assertEqual(result.spec_type, OriginalSpecType.ODCS)
        self.assertEqual(result.spec_version, "3.0.1")
        self.assertIsInstance(result.errors, list)
        self.assertIsInstance(result.warnings, list)

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

        self.assertEqual(result.spec_version, "3.0.1")

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

        self.assertEqual(result.spec_version, "3.0.1")

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

        self.assertEqual(result.status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(
            "does not support" in result.errors[0].lower()

        )

    def test_normalize_validates_contract_data_is_dict(self):
        """Test that normalize() validates contract_data is a dictionary."""
        normalizer = ODCSNormalizerV3_0_1()

        result = normalizer.normalize("not a dict", spec_version="3.0.1")

        self.assertEqual(result.status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("dictionary", result.errors[0].lower())

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
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("name" in error.lower() for error in result.errors))
        self.assertTrue(any("fields" in error.lower() for error in result.errors))

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

        self.assertEqual(result.status, NormalizationStatus.NORMALIZED_OK)
        self.assertIsNotNone(result.hub_contract)
        self.assertEqual(result.hub_contract["id"], "test-contract-3-0-1")
        self.assertEqual(result.hub_contract["info"]["name"], "Test Contract 3.0.1")
        self.assertEqual(
            result.hub_contract["info"]["description"], "A test contract for ODCS 3.0.1"
        )
        self.assertIn("models", result.hub_contract)
        self.assertGreater(len(result.hub_contract["models"]), 0)


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
        self.assertEqual(result.status, NormalizationStatus.NORMALIZED_OK)
        self.assertIsNotNone(result.hub_contract)
        self.assertEqual(result.hub_contract["id"], "test-1")
        self.assertEqual(result.hub_contract["info"]["name"], "Test Contract")

    def test_map_version_specific_fields_handles_unexpected_version(self):
        """Test that _map_version_specific_fields logs warning for unexpected version."""
        normalizer = ODCSNormalizerV3_0_1()
        odcs_contract = {"id": "test"}
        hub_contract = {"id": "test"}
        warnings = []

        # Should not raise an exception even with unexpected version
        normalizer._map_version_specific_fields(odcs_contract, hub_contract, warnings, "3.0.2")

        # Should not modify hub_contract structure
        self.assertEqual(hub_contract["id"], "test")

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

        self.assertEqual(result.status, NormalizationStatus.NORMALIZED_OK)
        self.assertIsNotNone(result.hub_contract)
        self.assertEqual(result.hub_contract["id"], "complex-contract-3-0-1")
        self.assertIn("quality", result.hub_contract)
        self.assertIn("privacy_compliance", result.hub_contract)
        self.assertIn("lifecycle", result.hub_contract)
        self.assertIn("marketplace", result.hub_contract)


class ODCSNormalizerV3_0_1RegistryTest(TestCase):
    """Test that ODCSNormalizerV3_0_1 is properly registered."""

    def test_normalizer_is_registered(self):
        """Test that ODCSNormalizerV3_0_1 can be retrieved from registry."""
        normalizer = get_normalizer(OriginalSpecType.ODCS, "3.0.1", {})
        self.assertIsNotNone(normalizer)
        self.assertIsInstance(normalizer, ODCSNormalizerV3_0_1)

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

        self.assertIsNotNone(normalizer)
        self.assertIsInstance(normalizer, ODCSNormalizerV3_0_1)

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
        self.assertIsNotNone(normalizer)

        result = normalizer.normalize(contract_data, spec_version="3.0.1")

        self.assertEqual(result.status, NormalizationStatus.NORMALIZED_OK)
        self.assertIsNotNone(result.hub_contract)
        self.assertEqual(result.spec_version, "3.0.1")


class ODCSNormalizerV3_0_1EdgeCaseTest(ODCSEdgeCaseMixin, TestCase):
    """Standard edge-case tests for ODCS 3.0.1 normalizer (via shared mixin)."""

    normalizer_class = ODCSNormalizerV3_0_1
    spec_version = "3.0.1"

    def setUp(self):
        self.normalizer = self.normalizer_class()


class ODCSNormalizerV3_0_1VersionRoutingTest(TestCase):
    """Verify version-routing behavior — ODCS 3.0.1 is a version-specific normalizer
    that routes contracts to the correct normalization path and delegates to the
    base class for common normalization logic."""

    def test_version_routing_via_registry(self):
        """Registry returns ODCSNormalizerV3_0_1 for version 3.0.1 contracts."""
        contract_data = {
            "apiVersion": "odcs.io/v3.0.1",
            "kind": "DataContract",
            "id": "test",
            "name": "Test",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }
        normalizer = get_normalizer(OriginalSpecType.ODCS, "3.0.1", contract_data)
        self.assertIsNotNone(normalizer)
        self.assertIsInstance(normalizer, ODCSNormalizerV3_0_1)

    def test_map_version_specific_fields_with_correct_version(self):
        """_map_version_specific_fields runs without error for matching version."""
        normalizer = ODCSNormalizerV3_0_1()
        odcs_contract = {"id": "test", "name": "Test", "extra_field": "value"}
        hub_contract = {"id": "test", "info": {"name": "Test"}}
        warnings = []
        normalizer._map_version_specific_fields(odcs_contract, hub_contract, warnings, "3.0.1")
        self.assertEqual(hub_contract["id"], "test")
        self.assertEqual(hub_contract["info"]["name"], "Test")

    def test_normalize_routes_version_3_0_1_correctly(self):
        """Full normalization pipeline routes 3.0.1 contracts correctly."""
        normalizer = ODCSNormalizerV3_0_1()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.1",
            "kind": "DataContract",
            "id": "routing-test",
            "name": "Routing Test",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
        }
        result = normalizer.normalize(contract_data, spec_version="3.0.1")
        self.assertEqual(result.status, NormalizationStatus.NORMALIZED_OK)
        self.assertEqual(result.spec_version, "3.0.1")
        self.assertEqual(result.spec_type, OriginalSpecType.ODCS)
        self.assertIsNotNone(result.hub_contract)
