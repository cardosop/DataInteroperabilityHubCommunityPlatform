"""
Unit tests for ODCSNormalizerV2_2_2.

Tests the version-specific normalizer for ODCS 2.2.2 including:
- Version support checking
- Normalization flow
- Version-specific field mappings
- Graceful degradation for missing 3.x features
- Integration with normalizer registry
"""

from unittest import TestCase

from hub.apps.contracts.models import NormalizationStatus, OriginalSpecType
from hub.apps.contracts.normalization import (
    _reset_normalizer_registry,
    get_normalizer,
    register_normalizer,
)
from hub.apps.contracts.normalization.odcs_normalizer_v2_2_2 import ODCSNormalizerV2_2_2
from hub.apps.contracts.tests.normalizer_edge_case_mixin import ODCSEdgeCaseMixin


class ODCSNormalizerV2_2_2StructureTest(TestCase):
    """Test that ODCSNormalizerV2_2_2 is properly structured."""

    def test_can_instantiate_normalizer(self):
        """Test that ODCSNormalizerV2_2_2 can be instantiated."""
        normalizer = ODCSNormalizerV2_2_2()
        self.assertIsNotNone(normalizer)
        self.assertIsInstance(normalizer, ODCSNormalizerV2_2_2)

    def test_spec_type_is_odcs(self):
        """Test that spec_type is set to ODCS."""
        normalizer = ODCSNormalizerV2_2_2()
        self.assertEqual(normalizer.spec_type, OriginalSpecType.ODCS)


class ODCSNormalizerV2_2_2SupportsTest(TestCase):
    """Test the supports() and _supports_version() methods."""

    def test_supports_version_2_2_2(self):
        """Test that supports() returns True for version 2.2.2 through public API."""
        normalizer = ODCSNormalizerV2_2_2()
        contract_data = {"apiVersion": "odcs.io/v2.2.2", "kind": "DataContract"}
        self.assertTrue(normalizer.supports(OriginalSpecType.ODCS, "2.2.2", contract_data) is True)

    def test_does_not_support_other_versions(self):
        """Test that supports() returns False for other versions through public API."""
        normalizer = ODCSNormalizerV2_2_2()
        contract_data_3_0_0 = {"apiVersion": "odcs.io/v3.0.0", "kind": "DataContract"}
        contract_data_3_0_1 = {"apiVersion": "odcs.io/v3.0.1", "kind": "DataContract"}
        contract_data_3_0_2 = {"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract"}
        contract_data_2_2_1 = {"apiVersion": "odcs.io/v2.2.1", "kind": "DataContract"}
        contract_data_2_2_3 = {"apiVersion": "odcs.io/v2.2.3", "kind": "DataContract"}
        contract_data_2_3_0 = {"apiVersion": "odcs.io/v2.3.0", "kind": "DataContract"}
        self.assertTrue(
            normalizer.supports(OriginalSpecType.ODCS, "3.0.0", contract_data_3_0_0) is False
        )
        self.assertTrue(
            normalizer.supports(OriginalSpecType.ODCS, "3.0.1", contract_data_3_0_1) is False
        )
        self.assertTrue(
            normalizer.supports(OriginalSpecType.ODCS, "3.0.2", contract_data_3_0_2) is False
        )
        self.assertTrue(
            normalizer.supports(OriginalSpecType.ODCS, "2.2.1", contract_data_2_2_1) is False
        )
        self.assertTrue(
            normalizer.supports(OriginalSpecType.ODCS, "2.2.3", contract_data_2_2_3) is False
        )
        self.assertTrue(
            normalizer.supports(OriginalSpecType.ODCS, "2.3.0", contract_data_2_3_0) is False
        )

    def test_supports_odcs_spec_type(self):
        """Test that supports() returns True for ODCS spec type with version 2.2.2."""
        normalizer = ODCSNormalizerV2_2_2()
        self.assertTrue(normalizer.supports(OriginalSpecType.ODCS, "2.2.2", {}) is True)

    def test_supports_does_not_support_other_spec_types(self):
        """Test that supports() returns False for non-ODCS spec types."""
        normalizer = ODCSNormalizerV2_2_2()
        self.assertTrue(normalizer.supports(OriginalSpecType.ODPS, "4.1", {}) is False)
        self.assertTrue(normalizer.supports("CUSTOM", "1.0", {}) is False)

    def test_supports_does_not_support_other_odcs_versions(self):
        """Test that supports() returns False for other ODCS versions."""
        normalizer = ODCSNormalizerV2_2_2()
        self.assertTrue(normalizer.supports(OriginalSpecType.ODCS, "3.0.0", {}) is False)
        self.assertTrue(normalizer.supports(OriginalSpecType.ODCS, "3.0.1", {}) is False)
        self.assertTrue(normalizer.supports(OriginalSpecType.ODCS, "3.0.2", {}) is False)
        self.assertTrue(normalizer.supports(OriginalSpecType.ODCS, "2.2.1", {}) is False)


class ODCSNormalizerV2_2_2NormalizeTest(TestCase):
    """Test the normalize() method of ODCSNormalizerV2_2_2."""

    def test_normalize_returns_normalization_result(self):
        """Test that normalize() returns a NormalizationResult."""
        normalizer = ODCSNormalizerV2_2_2()
        contract_data = {
            "apiVersion": "odcs.io/v2.2.2",
            "kind": "DataContract",
            "id": "test-1",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
        }

        result = normalizer.normalize(contract_data, spec_version="2.2.2")

        # Check that result has the expected attributes
        self.assertTrue(hasattr(result, "hub_contract"))
        self.assertTrue(hasattr(result, "status"))
        self.assertTrue(hasattr(result, "errors"))
        self.assertTrue(hasattr(result, "warnings"))
        self.assertTrue(hasattr(result, "spec_type"))
        self.assertTrue(hasattr(result, "spec_version"))
        self.assertTrue(hasattr(result, "coverage"))

        self.assertEqual(result.spec_type, OriginalSpecType.ODCS)
        self.assertEqual(result.spec_version, "2.2.2")
        self.assertIsInstance(result.errors, list)
        self.assertIsInstance(result.warnings, list)

    def test_normalize_detects_version_if_not_provided(self):
        """Test that normalize() detects version from contract_data if not provided."""
        normalizer = ODCSNormalizerV2_2_2()
        contract_data = {
            "apiVersion": "odcs.io/v2.2.2",
            "kind": "DataContract",
            "id": "test-1",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
        }

        result = normalizer.normalize(contract_data, spec_version=None)

        self.assertEqual(result.spec_version, "2.2.2")

    def test_normalize_fails_for_unsupported_version(self):
        """Test that normalize() fails gracefully for unsupported versions."""
        normalizer = ODCSNormalizerV2_2_2()
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
        normalizer = ODCSNormalizerV2_2_2()

        result = normalizer.normalize("not a dict", spec_version="2.2.2")

        self.assertEqual(result.status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("dictionary", result.errors[0].lower())

    def test_normalize_produces_valid_hub_contract(self):
        """Test that normalize() produces a valid hub_contract for 2.2.2."""
        normalizer = ODCSNormalizerV2_2_2()
        contract_data = {
            "apiVersion": "odcs.io/v2.2.2",
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

        result = normalizer.normalize(contract_data, spec_version="2.2.2")

        self.assertIsNotNone(result.hub_contract)
        self.assertEqual(result.hub_contract["id"], "test-1")
        self.assertEqual(result.hub_contract["info"]["name"], "Test Contract")
        self.assertEqual(result.hub_contract["info"]["version"], "1.0.0")
        self.assertIn("schema", result.hub_contract)
        self.assertIn("fields", result.hub_contract["schema"])
        self.assertEqual(len(result.hub_contract["schema"]["fields"]), 2)

    def test_normalize_handles_complex_contract(self):
        """Test that normalize() handles a complex ODCS 2.2.2 contract."""
        normalizer = ODCSNormalizerV2_2_2()
        contract_data = {
            "apiVersion": "odcs.io/v2.2.2",
            "kind": "DataContract",
            "id": "complex-test",
            "name": "Complex Test Contract",
            "version": "1.0.0",
            "description": "A complex contract for testing",
            "info": {"owners": ["owner1", "owner2"], "tags": ["tag1", "tag2"]},
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "nullable": False},
                    {"name": "value", "type": "number", "nullable": True},
                ]
            },
            "quality": {"rules": [{"type": "completeness", "field": "id", "threshold": 1.0}]},
        }

        result = normalizer.normalize(contract_data, spec_version="2.2.2")

        self.assertIsNotNone(result.hub_contract)
        self.assertEqual(result.hub_contract["id"], "complex-test")
        self.assertEqual(result.hub_contract["info"]["name"], "Complex Test Contract")
        self.assertIn("owners", result.hub_contract["info"])
        self.assertIn("tags", result.hub_contract["info"])
        self.assertIn("quality", result.hub_contract)


class ODCSNormalizerV2_2_2GracefulDegradationTest(TestCase):
    """Test graceful degradation for missing 3.x features."""

    def test_graceful_degradation_for_missing_marketplace(self):
        """Test that missing marketplace section is handled gracefully."""
        normalizer = ODCSNormalizerV2_2_2()
        contract_data = {
            "apiVersion": "odcs.io/v2.2.2",
            "kind": "DataContract",
            "id": "test-1",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
        }

        result = normalizer.normalize(contract_data, spec_version="2.2.2")

        # Should succeed even without marketplace (3.x feature)
        self.assertNotEqual(result.status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertIsNotNone(result.hub_contract)
        # Marketplace is optional, so it may or may not be present
        # The key is that normalization succeeds

    def test_graceful_degradation_for_missing_lifecycle(self):
        """Test that missing lifecycle section is handled gracefully."""
        normalizer = ODCSNormalizerV2_2_2()
        contract_data = {
            "apiVersion": "odcs.io/v2.2.2",
            "kind": "DataContract",
            "id": "test-1",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
        }

        result = normalizer.normalize(contract_data, spec_version="2.2.2")

        # Should succeed even without lifecycle (3.x feature)
        self.assertNotEqual(result.status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertIsNotNone(result.hub_contract)

    def test_graceful_degradation_for_3_x_features_in_contract(self):
        """Test that 3.x features present in contract are ignored gracefully."""
        normalizer = ODCSNormalizerV2_2_2()
        # Contract with 3.x features that should be ignored
        contract_data = {
            "apiVersion": "odcs.io/v2.2.2",
            "kind": "DataContract",
            "id": "test-1",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
            # These 3.x features should be ignored/not processed
            "marketplace": {"license_summary": "test", "intended_use": ["analytics"]},
            "lifecycle": {"data_source": "api", "refresh_cadence": "daily"},
        }

        result = normalizer.normalize(contract_data, spec_version="2.2.2")

        # Should succeed - 3.x features are ignored but don't cause errors
        self.assertNotEqual(result.status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertIsNotNone(result.hub_contract)
        # The contract should normalize successfully even with 3.x features present
        # (they may be preserved in extensions or ignored)

    def test_normalize_with_minimal_2_2_2_contract(self):
        """Test normalization with minimal valid ODCS 2.2.2 contract."""
        normalizer = ODCSNormalizerV2_2_2()
        contract_data = {
            "apiVersion": "odcs.io/v2.2.2",
            "kind": "DataContract",
            "id": "minimal",
            "name": "Minimal Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
        }

        result = normalizer.normalize(contract_data, spec_version="2.2.2")

        self.assertIsNotNone(result.hub_contract)
        self.assertEqual(result.hub_contract["id"], "minimal")
        self.assertEqual(result.hub_contract["info"]["name"], "Minimal Contract")
        self.assertIn("schema", result.hub_contract)


class ODCSNormalizerV2_2_2RegistryTest(TestCase):
    """Test integration with normalizer registry."""

    def setUp(self):
        """Set up test fixtures."""
        # Save registry state
        from hub.apps.contracts.normalization import _NORMALIZER_REGISTRY

        self.original_registry = {k: list(v) for k, v in _NORMALIZER_REGISTRY.items()}

    def tearDown(self):
        """Restore registry state."""
        _reset_normalizer_registry(self.original_registry)

    def test_normalizer_can_be_registered(self):
        """Test that ODCSNormalizerV2_2_2 can be registered."""
        normalizer = ODCSNormalizerV2_2_2()
        register_normalizer(normalizer)

        # Verify it can be retrieved
        retrieved = get_normalizer(OriginalSpecType.ODCS, "2.2.2", {})
        self.assertIsNotNone(retrieved)
        self.assertIsInstance(retrieved, ODCSNormalizerV2_2_2)

    def test_registry_returns_v2_2_2_normalizer(self):
        """Test that registry returns ODCSNormalizerV2_2_2 for version 2.2.2."""
        normalizer = ODCSNormalizerV2_2_2()
        register_normalizer(normalizer)

        retrieved = get_normalizer(
            OriginalSpecType.ODCS, "2.2.2", {"apiVersion": "odcs.io/v2.2.2", "kind": "DataContract"}
        )

        self.assertIsNotNone(retrieved)
        self.assertIsInstance(retrieved, ODCSNormalizerV2_2_2)
        self.assertTrue(retrieved.supports(OriginalSpecType.ODCS, "2.2.2", {}))

    def test_registry_normalization_works(self):
        """Test that normalization works through registry."""
        normalizer = ODCSNormalizerV2_2_2()
        register_normalizer(normalizer)

        contract_data = {
            "apiVersion": "odcs.io/v2.2.2",
            "kind": "DataContract",
            "id": "registry-test",
            "name": "Registry Test",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
        }

        retrieved = get_normalizer(OriginalSpecType.ODCS, "2.2.2", contract_data)
        self.assertIsNotNone(retrieved)

        result = retrieved.normalize(contract_data, spec_version="2.2.2")

        self.assertIsNotNone(result.hub_contract)
        self.assertEqual(result.spec_version, "2.2.2")


class ODCSNormalizerV2_2_2RegressionTest(TestCase):
    """Regression tests to ensure no breaking changes."""

    def test_normalize_preserves_required_fields(self):
        """Test that normalization preserves all required fields."""
        normalizer = ODCSNormalizerV2_2_2()
        contract_data = {
            "apiVersion": "odcs.io/v2.2.2",
            "kind": "DataContract",
            "id": "regression-test",
            "name": "Regression Test",
            "version": "1.0.0",
            "description": "Test description",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "nullable": False},
                    {"name": "name", "type": "string", "nullable": False},
                ]
            },
        }

        result = normalizer.normalize(contract_data, spec_version="2.2.2")

        self.assertIsNotNone(result.hub_contract)
        self.assertEqual(result.hub_contract["id"], "regression-test")
        self.assertEqual(result.hub_contract["info"]["name"], "Regression Test")
        self.assertEqual(result.hub_contract["info"]["version"], "1.0.0")
        self.assertEqual(result.hub_contract["info"]["description"], "Test description")
        self.assertIn("schema", result.hub_contract)
        self.assertIn("fields", result.hub_contract["schema"])
        self.assertEqual(len(result.hub_contract["schema"]["fields"]), 2)


class ODCSNormalizerV2_2_2EdgeCaseTest(ODCSEdgeCaseMixin, TestCase):
    """Standard edge-case tests for ODCS 2.2.2 normalizer (via shared mixin)."""

    normalizer_class = ODCSNormalizerV2_2_2
    spec_version = "2.2.2"

    def setUp(self):
        self.normalizer = self.normalizer_class()


class ODCSNormalizerV2_2_2VersionRoutingTest(TestCase):
    """Verify version-routing behavior — ODCS 2.2.2 is a version-specific normalizer
    that routes contracts to the correct normalization path and delegates to the
    base class for common normalization logic."""

    def test_version_routing_via_registry(self):
        """Registry returns ODCSNormalizerV2_2_2 for version 2.2.2 contracts."""
        normalizer = ODCSNormalizerV2_2_2()
        register_normalizer(normalizer)
        contract_data = {
            "apiVersion": "odcs.io/v2.2.2",
            "kind": "DataContract",
            "id": "test",
            "name": "Test",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }
        retrieved = get_normalizer(OriginalSpecType.ODCS, "2.2.2", contract_data)
        self.assertIsNotNone(retrieved)
        self.assertIsInstance(retrieved, ODCSNormalizerV2_2_2)

    def test_map_version_specific_fields_with_correct_version(self):
        """_map_version_specific_fields runs without error for matching version."""
        normalizer = ODCSNormalizerV2_2_2()
        odcs_contract = {"id": "test", "name": "Test", "extra_field": "value"}
        hub_contract = {"id": "test", "info": {"name": "Test"}}
        warnings = []
        normalizer._map_version_specific_fields(odcs_contract, hub_contract, warnings, "2.2.2")
        self.assertEqual(hub_contract["id"], "test")
        self.assertEqual(hub_contract["info"]["name"], "Test")

    def test_normalize_routes_version_2_2_2_correctly(self):
        """Full normalization pipeline routes 2.2.2 contracts correctly."""
        normalizer = ODCSNormalizerV2_2_2()
        contract_data = {
            "apiVersion": "odcs.io/v2.2.2",
            "kind": "DataContract",
            "id": "routing-test",
            "name": "Routing Test",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
        }
        result = normalizer.normalize(contract_data, spec_version="2.2.2")
        self.assertEqual(result.status, NormalizationStatus.NORMALIZED_OK)
        self.assertEqual(result.spec_version, "2.2.2")
        self.assertEqual(result.spec_type, OriginalSpecType.ODCS)
        self.assertIsNotNone(result.hub_contract)
