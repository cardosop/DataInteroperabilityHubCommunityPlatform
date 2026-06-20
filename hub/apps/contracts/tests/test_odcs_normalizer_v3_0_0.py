"""
Unit tests for ODCSNormalizerV3_0_0.

Tests the version-specific normalizer for ODCS 3.0.0 including:
- Version support checking
- Normalization flow
- Version-specific field mappings
- Graceful degradation for missing 3.0.1/3.0.2 features
- Integration with normalizer registry
"""

from unittest import TestCase

from hub.apps.contracts.models import NormalizationStatus, OriginalSpecType
from hub.apps.contracts.normalization import (
    _reset_normalizer_registry,
    get_normalizer,
    register_normalizer,
)
from hub.apps.contracts.normalization.odcs_normalizer_v3_0_0 import ODCSNormalizerV3_0_0
from hub.apps.contracts.tests.normalizer_edge_case_mixin import ODCSEdgeCaseMixin


class ODCSNormalizerV3_0_0StructureTest(TestCase):
    """Test that ODCSNormalizerV3_0_0 is properly structured."""

    def test_can_instantiate_normalizer(self):
        """Test that ODCSNormalizerV3_0_0 can be instantiated."""
        normalizer = ODCSNormalizerV3_0_0()
        self.assertIsNotNone(normalizer)
        self.assertIsInstance(normalizer, ODCSNormalizerV3_0_0)

    def test_spec_type_is_odcs(self):
        """Test that spec_type is set to ODCS."""
        normalizer = ODCSNormalizerV3_0_0()
        self.assertEqual(normalizer.spec_type, OriginalSpecType.ODCS)


class ODCSNormalizerV3_0_0SupportsTest(TestCase):
    """Test the supports() and _supports_version() methods."""

    def test_supports_version_3_0_0(self):
        """Test that supports() returns True for version 3.0.0 through public API."""
        normalizer = ODCSNormalizerV3_0_0()
        contract_data = {"apiVersion": "odcs.io/v3.0.0", "kind": "DataContract"}
        # Test through public API - supports() internally calls _supports_version()
        self.assertTrue(normalizer.supports(OriginalSpecType.ODCS, "3.0.0", contract_data) is True)

    def test_does_not_support_other_versions(self):
        """Test that supports() returns False for other versions through public API."""
        normalizer = ODCSNormalizerV3_0_0()
        # Test through public API - supports() internally calls _supports_version()
        self.assertTrue(
            normalizer.supports(OriginalSpecType.ODCS, "3.0.1", {"apiVersion": "odcs.io/v3.0.1"})
            is False
        )
        self.assertTrue(
            normalizer.supports(OriginalSpecType.ODCS, "3.0.2", {"apiVersion": "odcs.io/v3.0.2"})
            is False
        )
        self.assertTrue(
            normalizer.supports(OriginalSpecType.ODCS, "3.1.0", {"apiVersion": "odcs.io/v3.1.0"})
            is False
        )
        self.assertTrue(
            normalizer.supports(OriginalSpecType.ODCS, "4.0.0", {"apiVersion": "odcs.io/v4.0.0"})
            is False
        )
        self.assertTrue(
            normalizer.supports(OriginalSpecType.ODCS, "2.2.2", {"apiVersion": "odcs.io/v2.2.2"})
            is False
        )

    def test_supports_odcs_spec_type(self):
        """Test that supports() returns True for ODCS spec type with version 3.0.0."""
        normalizer = ODCSNormalizerV3_0_0()
        self.assertTrue(normalizer.supports(OriginalSpecType.ODCS, "3.0.0", {}) is True)

    def test_supports_does_not_support_other_spec_types(self):
        """Test that supports() returns False for non-ODCS spec types."""
        normalizer = ODCSNormalizerV3_0_0()
        self.assertTrue(normalizer.supports(OriginalSpecType.ODPS, "4.1", {}) is False)
        self.assertTrue(normalizer.supports("CUSTOM", "1.0", {}) is False)

    def test_supports_does_not_support_other_odcs_versions(self):
        """Test that supports() returns False for other ODCS versions."""
        normalizer = ODCSNormalizerV3_0_0()
        self.assertTrue(normalizer.supports(OriginalSpecType.ODCS, "3.0.1", {}) is False)
        self.assertTrue(normalizer.supports(OriginalSpecType.ODCS, "3.0.2", {}) is False)
        self.assertTrue(normalizer.supports(OriginalSpecType.ODCS, "2.2.2", {}) is False)


class ODCSNormalizerV3_0_0NormalizeTest(TestCase):
    """Test the normalize() method of ODCSNormalizerV3_0_0."""

    def test_normalize_returns_normalization_result(self):
        """Test that normalize() returns a NormalizationResult."""
        normalizer = ODCSNormalizerV3_0_0()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.0",
            "kind": "DataContract",
            "id": "test-1",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.0")

        # Check that result has the expected attributes
        self.assertTrue(hasattr(result, "hub_contract"))
        self.assertTrue(hasattr(result, "status"))
        self.assertTrue(hasattr(result, "errors"))
        self.assertTrue(hasattr(result, "warnings"))
        self.assertTrue(hasattr(result, "spec_type"))
        self.assertTrue(hasattr(result, "spec_version"))
        self.assertTrue(hasattr(result, "coverage"))

        self.assertEqual(result.spec_type, OriginalSpecType.ODCS)
        self.assertEqual(result.spec_version, "3.0.0")
        self.assertIsInstance(result.errors, list)
        self.assertIsInstance(result.warnings, list)

    def test_normalize_detects_version_if_not_provided(self):
        """Test that normalize() detects version from contract_data if not provided."""
        normalizer = ODCSNormalizerV3_0_0()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.0",
            "kind": "DataContract",
            "id": "test-1",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
        }

        result = normalizer.normalize(contract_data, spec_version=None)

        self.assertEqual(result.spec_version, "3.0.0")

    def test_normalize_fails_for_unsupported_version(self):
        """Test that normalize() fails gracefully for unsupported versions."""
        normalizer = ODCSNormalizerV3_0_0()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.1",
            "kind": "DataContract",
            "id": "test-1",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.1")

        self.assertEqual(result.status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(
            "does not support" in result.errors[0].lower()

        )

    def test_normalize_validates_contract_data_is_dict(self):
        """Test that normalize() validates contract_data is a dictionary."""
        normalizer = ODCSNormalizerV3_0_0()

        result = normalizer.normalize("not a dict", spec_version="3.0.0")

        self.assertEqual(result.status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("dictionary", result.errors[0].lower())

    def test_normalize_produces_valid_hub_contract(self):
        """Test that normalize() produces a valid hub_contract for 3.0.0."""
        normalizer = ODCSNormalizerV3_0_0()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.0",
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

        result = normalizer.normalize(contract_data, spec_version="3.0.0")

        self.assertIsNotNone(result.hub_contract)
        self.assertEqual(result.hub_contract["id"], "test-1")
        self.assertEqual(result.hub_contract["info"]["name"], "Test Contract")
        self.assertEqual(result.hub_contract["info"]["version"], "1.0.0")
        self.assertIn("schema", result.hub_contract)
        self.assertIn("fields", result.hub_contract["schema"])
        self.assertEqual(len(result.hub_contract["schema"]["fields"]), 2)

    def test_normalize_handles_complex_contract(self):
        """Test that normalize() handles a complex ODCS 3.0.0 contract."""
        normalizer = ODCSNormalizerV3_0_0()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.0",
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

        result = normalizer.normalize(contract_data, spec_version="3.0.0")

        self.assertIsNotNone(result.hub_contract)
        self.assertEqual(result.hub_contract["id"], "complex-test")
        self.assertEqual(result.hub_contract["info"]["name"], "Complex Test Contract")
        self.assertIn("owners", result.hub_contract["info"])
        self.assertIn("tags", result.hub_contract["info"])
        self.assertIn("quality", result.hub_contract)
        self.assertIn("lifecycle", result.hub_contract)


class ODCSNormalizerV3_0_0GracefulDegradationTest(TestCase):
    """Test graceful degradation for missing 3.0.1/3.0.2 features."""

    def test_normalize_handles_contract_without_3_0_1_features(self):
        """Test that normalize() gracefully handles contracts without 3.0.1 features."""
        normalizer = ODCSNormalizerV3_0_0()
        # Minimal 3.0.0 contract without any 3.0.1+ features
        contract_data = {
            "apiVersion": "odcs.io/v3.0.0",
            "kind": "DataContract",
            "id": "test-1",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.0")

        # Should normalize successfully without errors
        self.assertIsNotNone(result.hub_contract)
        self.assertNotEqual(result.status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertEqual(result.hub_contract["id"], "test-1")
        self.assertEqual(result.hub_contract["info"]["name"], "Test Contract")

    def test_normalize_handles_contract_with_unknown_fields(self):
        """Test that normalize() gracefully handles contracts with unknown/3.0.1+ fields."""
        normalizer = ODCSNormalizerV3_0_0()
        # Contract with fields that might be 3.0.1+ specific (unknown to 3.0.0)
        contract_data = {
            "apiVersion": "odcs.io/v3.0.0",
            "kind": "DataContract",
            "id": "test-1",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
            # Unknown field that might be from 3.0.1+ (should be preserved in extensions)
            "unknown_field_3_0_1": "value",
            "another_unknown": {"nested": "value"},
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.0")

        # Should normalize successfully and preserve unknown fields in extensions
        self.assertIsNotNone(result.hub_contract)
        self.assertNotEqual(result.status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertIn("extensions", result.hub_contract)
        self.assertIn("unknown_field_3_0_1", result.hub_contract["extensions"])
        self.assertEqual(result.hub_contract["extensions"]["unknown_field_3_0_1"], "value")

    def test_normalize_handles_missing_optional_fields(self):
        """Test that normalize() gracefully handles missing optional fields."""
        normalizer = ODCSNormalizerV3_0_0()
        # Minimal contract with only required fields
        contract_data = {
            "apiVersion": "odcs.io/v3.0.0",
            "kind": "DataContract",
            "id": "test-1",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.0")

        # Should normalize successfully even without optional fields
        self.assertIsNotNone(result.hub_contract)
        self.assertNotEqual(result.status, NormalizationStatus.NORMALIZATION_FAILED)
        # Optional fields like quality, lifecycle, marketplace should be absent but not cause errors
        self.assertTrue(
            "quality" not in result.hub_contract or result.hub_contract.get("quality") is None
        )
        self.assertTrue(
            "lifecycle" not in result.hub_contract or result.hub_contract.get("lifecycle") is None
        )

    def test_normalize_preserves_3_0_0_features(self):
        """Test that normalize() correctly preserves and processes 3.0.0 features."""
        normalizer = ODCSNormalizerV3_0_0()
        # Contract with all 3.0.0 features
        contract_data = {
            "apiVersion": "odcs.io/v3.0.0",
            "kind": "DataContract",
            "id": "test-1",
            "name": "Test Contract",
            "version": "1.0.0",
            "description": "Test description",
            "info": {"owners": ["owner1"], "tags": ["tag1"]},
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
            "quality": {"default_profile_key": "profile1"},
            "lifecycle": {"data_source": "database"},
            "marketplace": {"license_summary": "MIT"},
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.0")

        # Should normalize all 3.0.0 features correctly
        self.assertIsNotNone(result.hub_contract)
        self.assertNotEqual(result.status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertEqual(result.hub_contract["info"]["name"], "Test Contract")
        self.assertEqual(result.hub_contract["info"]["description"], "Test description")
        self.assertIn("owners", result.hub_contract["info"])
        self.assertIn("quality", result.hub_contract)
        self.assertIn("lifecycle", result.hub_contract)
        self.assertIn("marketplace", result.hub_contract)


class ODCSNormalizerV3_0_0RegistryTest(TestCase):
    """Test ODCSNormalizerV3_0_0 integration with normalizer registry."""

    def setUp(self):
        """Save registry state before each test."""
        from hub.apps.contracts.normalization import _NORMALIZER_REGISTRY

        self.original_registry = {key: list(value) for key, value in _NORMALIZER_REGISTRY.items()}

    def tearDown(self):
        """Restore registry state after each test."""
        _reset_normalizer_registry(self.original_registry)

    def test_normalizer_can_be_registered(self):
        """Test that ODCSNormalizerV3_0_0 can be registered."""
        normalizer = ODCSNormalizerV3_0_0()
        register_normalizer(normalizer)

        # Should be able to retrieve it
        retrieved = get_normalizer(OriginalSpecType.ODCS, "3.0.0", {})
        self.assertIsNotNone(retrieved)
        self.assertIsInstance(retrieved, ODCSNormalizerV3_0_0)

    def test_registered_normalizer_handles_3_0_0_contracts(self):
        """Test that registered normalizer correctly handles 3.0.0 contracts."""
        normalizer = ODCSNormalizerV3_0_0()
        register_normalizer(normalizer)

        contract_data = {
            "apiVersion": "odcs.io/v3.0.0",
            "kind": "DataContract",
            "id": "test-1",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
        }

        retrieved = get_normalizer(OriginalSpecType.ODCS, "3.0.0", contract_data)
        self.assertIsNotNone(retrieved)
        self.assertIsInstance(retrieved, ODCSNormalizerV3_0_0)

        result = retrieved.normalize(contract_data, spec_version="3.0.0")
        self.assertEqual(result.spec_version, "3.0.0")
        self.assertIsNotNone(result.hub_contract)


class ODCSNormalizerV3_0_0RegressionTest(TestCase):
    """Regression tests to ensure ODCS 3.0.0 normalization is consistent."""

    def test_normalization_output_matches_expected_format(self):
        """Test that normalization output matches expected format for 3.0.0."""
        normalizer = ODCSNormalizerV3_0_0()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.0",
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

        result = normalizer.normalize(contract_data, spec_version="3.0.0")

        # Check that all expected fields are present
        self.assertIsNotNone(result.hub_contract)
        self.assertEqual(result.hub_contract["id"], "regression-test")
        self.assertEqual(result.hub_contract["info"]["name"], "Regression Test Contract")
        self.assertEqual(result.hub_contract["info"]["version"], "1.0.0")
        self.assertIn("owners", result.hub_contract["info"])
        self.assertIn("tags", result.hub_contract["info"])
        self.assertIn("quality", result.hub_contract)
        self.assertIn("lifecycle", result.hub_contract)
        self.assertIn("schema", result.hub_contract)
        self.assertIn("fields", result.hub_contract["schema"])
        self.assertEqual(len(result.hub_contract["schema"]["fields"]), 2)

    def test_normalization_preserves_extensions(self):
        """Test that normalization preserves unmappable fields in extensions."""
        normalizer = ODCSNormalizerV3_0_0()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.0",
            "kind": "DataContract",
            "id": "test-1",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
            "custom_field": "custom_value",
            "another_custom": {"nested": "value"},
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.0")

        # Should preserve custom fields in extensions
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("extensions", result.hub_contract)
        self.assertIn("custom_field", result.hub_contract["extensions"])
        self.assertEqual(result.hub_contract["extensions"]["custom_field"], "custom_value")
        self.assertIn("odcs", result.hub_contract["extensions"])
        self.assertIn("custom_field", result.hub_contract["extensions"]["odcs"])

    def test_normalization_calculates_coverage(self):
        """Test that normalization calculates coverage for 3.0.0."""
        normalizer = ODCSNormalizerV3_0_0()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.0",
            "kind": "DataContract",
            "id": "test-1",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
            "quality": {"default_profile_key": "profile1"},
            "lifecycle": {"data_source": "database"},
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.0")

        # Should have coverage calculated
        self.assertIsNotNone(result.coverage)
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("normalization", result.hub_contract)
        self.assertIn("coverage", result.hub_contract["normalization"])
        self.assertIn("original_spec_type", result.hub_contract["normalization"])
        self.assertEqual(
            result.hub_contract["normalization"]["original_spec_type"], OriginalSpecType.ODCS
        )
        self.assertIn("original_spec_version", result.hub_contract["normalization"])
        self.assertEqual(result.hub_contract["normalization"]["original_spec_version"], "3.0.0")

    def test_normalization_handles_missing_required_fields(self):
        """Test that normalization handles missing required fields gracefully."""
        normalizer = ODCSNormalizerV3_0_0()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.0",
            "kind": "DataContract",
            "id": "test-1",
            # Missing 'name' field
            "schema": {},  # Missing 'fields' array
        }

        result = normalizer.normalize(contract_data, spec_version="3.0.0")

        # Should have errors for missing required fields
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("name" in error.lower() for error in result.errors))
        self.assertTrue(any("fields" in error.lower() for error in result.errors))
        # When required fields are missing, normalization fails; hub_contract may be None
        self.assertEqual(result.status, NormalizationStatus.NORMALIZATION_FAILED)


class ODCSNormalizerV3_0_0EdgeCaseTest(ODCSEdgeCaseMixin, TestCase):
    """Standard edge-case tests for ODCS 3.0.0 normalizer (via shared mixin)."""

    normalizer_class = ODCSNormalizerV3_0_0
    spec_version = "3.0.0"

    def setUp(self):
        self.normalizer = self.normalizer_class()


class ODCSNormalizerV3_0_0VersionRoutingTest(TestCase):
    """Verify version-routing behavior — ODCS 3.0.0 is a version-specific normalizer
    that routes contracts to the correct normalization path and delegates to the
    base class for common normalization logic."""

    def test_version_routing_via_registry(self):
        """Registry returns ODCSNormalizerV3_0_0 for version 3.0.0 contracts."""
        normalizer = ODCSNormalizerV3_0_0()
        register_normalizer(normalizer)
        contract_data = {
            "apiVersion": "odcs.io/v3.0.0",
            "kind": "DataContract",
            "id": "test",
            "name": "Test",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }
        retrieved = get_normalizer(OriginalSpecType.ODCS, "3.0.0", contract_data)
        self.assertIsNotNone(retrieved)
        self.assertIsInstance(retrieved, ODCSNormalizerV3_0_0)

    def test_map_version_specific_fields_with_correct_version(self):
        """_map_version_specific_fields runs without error for matching version."""
        normalizer = ODCSNormalizerV3_0_0()
        odcs_contract = {"id": "test", "name": "Test", "extra_field": "value"}
        hub_contract = {"id": "test", "info": {"name": "Test"}}
        warnings = []
        normalizer._map_version_specific_fields(odcs_contract, hub_contract, warnings, "3.0.0")
        self.assertEqual(hub_contract["id"], "test")
        self.assertEqual(hub_contract["info"]["name"], "Test")

    def test_normalize_routes_version_3_0_0_correctly(self):
        """Full normalization pipeline routes 3.0.0 contracts correctly."""
        normalizer = ODCSNormalizerV3_0_0()
        contract_data = {
            "apiVersion": "odcs.io/v3.0.0",
            "kind": "DataContract",
            "id": "routing-test",
            "name": "Routing Test",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
        }
        result = normalizer.normalize(contract_data, spec_version="3.0.0")
        self.assertEqual(result.status, NormalizationStatus.NORMALIZED_OK)
        self.assertEqual(result.spec_version, "3.0.0")
        self.assertEqual(result.spec_type, OriginalSpecType.ODCS)
        self.assertIsNotNone(result.hub_contract)
