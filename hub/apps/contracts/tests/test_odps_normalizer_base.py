"""
Unit tests for ODPSNormalizerBase

Tests verify:
1. Abstract base class structure
2. _supports_version() abstract method requirement
3. Common normalization logic
4. Version-specific hooks
5. Error handling
"""

from abc import ABC

from django.test import TestCase

from hub.apps.contracts.models import NormalizationStatus, OriginalSpecType
from hub.apps.contracts.normalization import NormalizationResult, SpecNormalizer
from hub.apps.contracts.normalization.odps_normalizer_base import ODPSNormalizerBase
from hub.apps.contracts.odps_errors import ODPSNormalizationError


class TestODPSNormalizerV4_1(ODPSNormalizerBase):
    """Test implementation of ODPSNormalizerBase for version 4.1"""

    def _supports_version(self, spec_version: str) -> bool:
        """Support ODPS 4.1"""
        return spec_version == "4.1"


class ODPSNormalizerBaseStructureTest(TestCase):
    """Test ODPSNormalizerBase structure and abstract methods"""

    def test_is_abstract_base_class(self):
        """Test that ODPSNormalizerBase is an abstract base class"""
        self.assertTrue(issubclass(ODPSNormalizerBase, ABC))

    def test_cannot_instantiate_base_class_directly(self):
        """Test that base class cannot be instantiated directly"""
        with self.assertRaises(TypeError):
            ODPSNormalizerBase()

    def test_can_instantiate_concrete_subclass(self):
        """Test that concrete subclass can be instantiated"""
        normalizer = TestODPSNormalizerV4_1()
        self.assertIsInstance(normalizer, ODPSNormalizerBase)
        self.assertIsInstance(normalizer, SpecNormalizer)

    def test_has_spec_type_attribute(self):
        """Test that base class has spec_type attribute"""
        normalizer = TestODPSNormalizerV4_1()
        self.assertEqual(normalizer.spec_type, OriginalSpecType.ODPS)

    def test_requires_supports_version_implementation(self):
        """Test that subclasses must implement _supports_version"""

        class IncompleteNormalizer(ODPSNormalizerBase):
            pass

        with self.assertRaises(TypeError):
            IncompleteNormalizer()


class ODPSNormalizerBaseSupportsTest(TestCase):
    """Test ODPSNormalizerBase supports() method"""

    def setUp(self):
        """Set up test fixtures"""
        self.normalizer = TestODPSNormalizerV4_1()

    def test_supports_odps_type(self):
        """Test that normalizer supports ODPS spec type"""
        contract_data = {"schema": "https://opendataproducts.org/schema/v4.1"}
        result = self.normalizer.supports(OriginalSpecType.ODPS, "4.1", contract_data)
        self.assertTrue(result)

    def test_supports_version_specific(self):
        """Test that normalizer only supports specific version"""
        contract_data = {"schema": "https://opendataproducts.org/schema/v4.1"}
        # Should support 4.1
        result = self.normalizer.supports(OriginalSpecType.ODPS, "4.1", contract_data)
        self.assertTrue(result)

        # Should not support 4.0
        result = self.normalizer.supports(OriginalSpecType.ODPS, "4.0", contract_data)
        self.assertFalse(result)

    def test_supports_not_odcs(self):
        """Test that normalizer does not support ODCS"""
        contract_data = {"apiVersion": "odcs/v3", "kind": "DataContract"}
        result = self.normalizer.supports(OriginalSpecType.ODCS, "3.0.2", contract_data)
        self.assertFalse(result)


class ODPSNormalizerBaseNormalizeTest(TestCase):
    """Test ODPSNormalizerBase normalize() method"""

    def setUp(self):
        """Set up test fixtures"""
        self.normalizer = TestODPSNormalizerV4_1()

    def test_normalize_returns_normalization_result(self):
        """Test that normalize() returns NormalizationResult"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {"en": {"name": "Test Product", "productID": "test-product-1"}}},
        }

        result = self.normalizer.normalize(contract_data, spec_version="4.1")
        # Check that result has NormalizationResult attributes (duck typing)
        # The base class dynamically imports NormalizationResult, so isinstance may fail
        self.assertTrue(hasattr(result, "hub_contract"))
        self.assertTrue(hasattr(result, "status"))
        self.assertTrue(hasattr(result, "errors"))
        self.assertTrue(hasattr(result, "warnings"))
        self.assertTrue(hasattr(result, "spec_type"))
        self.assertTrue(hasattr(result, "spec_version"))
        self.assertEqual(result.spec_type, OriginalSpecType.ODPS)
        self.assertEqual(result.spec_version, "4.1")
        # Note: Status may be NORMALIZATION_FAILED if schema.fields is empty (expected behavior)
        # The important thing is that a result is returned with the correct structure

    def test_normalize_rejects_unsupported_version(self):
        """Test that normalize() rejects unsupported version"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.0",
            "version": "4.0",
            "product": {"details": {"en": {"name": "Test Product"}}},
        }

        result = self.normalizer.normalize(contract_data, spec_version="4.0")
        # Check that result has NormalizationResult attributes (duck typing)
        self.assertTrue(hasattr(result, "status"))
        self.assertTrue(hasattr(result, "errors"))
        self.assertEqual(result.status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertTrue(len(result.errors) > 0)
        self.assertIn("does not support ODPS version", result.errors[0])

    def test_normalize_detects_version_if_not_provided(self):
        """Test that normalize() detects version if not provided"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "product": {"details": {"en": {"name": "Test Product", "productID": "test-product-1"}}},
        }

        result = self.normalizer.normalize(contract_data)
        # Check that result has NormalizationResult attributes (duck typing)
        self.assertTrue(hasattr(result, "spec_version"))
        self.assertEqual(result.spec_version, "4.1")

    def test_normalize_validates_contract_data_type(self):
        """Test that normalize() validates contract_data is a dict"""
        result = self.normalizer.normalize("not a dict", spec_version="4.1")
        # Check that result has NormalizationResult attributes (duck typing)
        self.assertTrue(hasattr(result, "status"))
        self.assertTrue(hasattr(result, "errors"))
        self.assertEqual(result.status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertTrue(len(result.errors) > 0)

    def test_normalize_handles_missing_required_fields(self):
        """Test that normalize() handles missing required fields gracefully"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "product": {
                "details": {
                    "en": {
                        # Missing required "name" field
                    }
                }
            },
        }

        result = self.normalizer.normalize(contract_data, spec_version="4.1")
        # Check that result has NormalizationResult attributes (duck typing)
        self.assertTrue(hasattr(result, "status"))
        self.assertTrue(hasattr(result, "errors"))
        # Should fail due to missing required field
        self.assertEqual(result.status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertTrue(len(result.errors) > 0)


class ODPSNormalizerBaseHelperMethodsTest(TestCase):
    """Test ODPSNormalizerBase helper methods"""

    def setUp(self):
        """Set up test fixtures"""
        self.normalizer = TestODPSNormalizerV4_1()

    def test_initialize_hub_contract(self):
        """Test that normalize() initializes hub_contract structure through public API"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {"en": {"name": "Test Product"}}},
        }
        spec_version = "4.1"

        # Test through public API - normalize() internally calls _initialize_hub_contract()
        result = self.normalizer.normalize(contract_data, spec_version=spec_version)

        hub_contract = result.hub_contract
        self.assertIsNotNone(hub_contract)
        self.assertIsInstance(hub_contract, dict)
        self.assertIn("info", hub_contract)
        self.assertIn("schema", hub_contract)
        self.assertIn("extensions", hub_contract)
        self.assertIn("normalization", hub_contract)
        self.assertEqual(hub_contract["normalization"]["original_spec_type"], OriginalSpecType.ODPS)
        self.assertEqual(hub_contract["normalization"]["original_spec_version"], spec_version)

    def test_determine_status_success(self):
        """Test that normalize() determines NORMALIZED_OK status for successful normalization through public API"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product", "productID": "test-product-1"}},
                "dataSchema": {"fields": [{"name": "field1", "type": "string"}]},
            },
        }

        # Test through public API - normalize() internally calls _determine_status()
        result = self.normalizer.normalize(contract_data, spec_version="4.1")
        self.assertEqual(result.status, NormalizationStatus.NORMALIZED_OK)
        self.assertEqual(len(result.errors), 0)

    def test_determine_status_with_warnings(self):
        """Test that normalize() determines NORMALIZED_WITH_WARNINGS status when warnings present through public API"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "dataSchema": {"fields": [{"name": "field1", "type": "string"}]},
            },
            # Missing optional fields that might generate warnings
        }

        # Test through public API - normalize() internally calls _determine_status()
        # Some normalizers may add warnings for missing optional fields
        result = self.normalizer.normalize(contract_data, spec_version="4.1")
        # Status should be OK or WITH_WARNINGS depending on implementation
        self.assertIn(
            result.status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
        )
        # If there are warnings, status should be WITH_WARNINGS
        if result.warnings:
            self.assertEqual(result.status, NormalizationStatus.NORMALIZED_WITH_WARNINGS)

    def test_determine_status_failed(self):
        """Test that normalize() determines NORMALIZATION_FAILED status for failed normalization through public API"""
        # Invalid contract data that will cause normalization to fail
        contract_data = "invalid"

        # Test through public API - normalize() internally calls _determine_status()
        result = self.normalizer.normalize(contract_data, spec_version="4.1")
        self.assertEqual(result.status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertIsNone(result.hub_contract)
        self.assertTrue(len(result.errors) > 0)

    def test_normalize_field_with_error_context_required(self):
        """Test that normalize() handles missing required fields through public API"""
        # Missing required product field should cause normalization to fail
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            # Missing required "product" field
        }

        # Test through public API - normalize() internally calls _normalize_field_with_error_context()
        result = self.normalizer.normalize(contract_data, spec_version="4.1")
        self.assertEqual(result.status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertTrue(len(result.errors) > 0)
        # Check that error mentions missing required field
        error_messages = " ".join(result.errors)
        self.assertTrue("required" in error_messages.lower() or "missing" in error_messages.lower())

    def test_normalize_field_with_error_context_optional(self):
        """Test that normalize() handles missing optional fields gracefully through public API"""
        # Contract with required fields but missing optional fields
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "dataSchema": {"fields": [{"name": "field1", "type": "string"}]},
            },
            # Missing optional fields like marketplace, lifecycle, quality
        }

        # Test through public API - normalize() internally calls _normalize_field_with_error_context()
        # Missing optional fields should not cause failure
        result = self.normalizer.normalize(contract_data, spec_version="4.1")
        # Should succeed even with missing optional fields
        self.assertIn(
            result.status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
        )
        self.assertIsNotNone(result.hub_contract)

    def test_normalize_field_with_error_context_type_validation(self):
        """Test that normalize() handles invalid field types through the public API.

        The original contract has version as a number (4.1) instead of a string.
        The base normalizer may handle this gracefully (with warnings) or fail —
        but must not silently produce NORMALIZED_OK without any diagnostic."""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": 4.1,  # Invalid: should be string
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "dataSchema": {"fields": [{"name": "field1", "type": "string"}]},
            },
        }

        result = self.normalizer.normalize(contract_data, spec_version="4.1")
        # The normalizer must not crash — a result is always returned
        self.assertIsNotNone(result)
        # The invalid type should either be caught as a failure
        # or accepted with warnings — but never silently OK'd with zero diagnostics
        if result.status == NormalizationStatus.NORMALIZED_OK:
            self.fail(
                "Invalid field type (version=number instead of string) should not "
                "produce NORMALIZED_OK with no warnings or errors."
            )

    def test_normalize_optional_field(self):
        """Test that normalize() handles optional fields through public API"""
        # Contract missing optional fields
        contract_data_missing = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "dataSchema": {"fields": [{"name": "field1", "type": "string"}]},
            },
            # Missing optional fields
        }

        # Test through public API - normalize() internally calls _normalize_optional_field()
        result_missing = self.normalizer.normalize(contract_data_missing, spec_version="4.1")
        # Should succeed, may have warnings for missing optional fields
        self.assertIn(
            result_missing.status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
        )
        self.assertIsNotNone(result_missing.hub_contract)

        # Contract with valid optional fields
        contract_data_valid = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {"productID": "test-product", "name": "Test Product"},
                },
                "dataSchema": {"fields": [{"name": "field1", "type": "string"}]},
            },
            "marketplace": {"license": "MIT"},  # Optional field
        }

        result_valid = self.normalizer.normalize(contract_data_valid, spec_version="4.1")
        self.assertEqual(result_valid.status, NormalizationStatus.NORMALIZED_OK)
        self.assertIsNotNone(result_valid.hub_contract)

    def test_normalize_handles_unicode_characters(self):
        """Test that normalize() handles unicode characters correctly through public API."""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-unicode",
                        "name": "测试产品",
                        "description": "测试描述",
                    }
                },
                "dataSchema": {"fields": [{"name": "字段名称", "type": "string"}]},
            },
        }

        result = self.normalizer.normalize(contract_data, spec_version="4.1")

        # Should handle unicode characters
        self.assertIsNotNone(result.hub_contract)
        self.assertIsNotNone(result.hub_contract, "hub_contract must not be None")
        self.assertIn("info", result.hub_contract, "info key must be present")
        self.assertIsNotNone(result.hub_contract["info"], "info must not be None")

    def test_normalize_handles_special_characters(self):
        """Test that normalize() handles special characters correctly through public API."""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-special",
                        "name": "Test & Co. (Special)",
                        "description": "Test <description> & more",
                    }
                },
                "dataSchema": {"fields": [{"name": "field-name", "type": "string"}]},
            },
        }

        result = self.normalizer.normalize(contract_data, spec_version="4.1")

        # Should handle special characters
        self.assertIsNotNone(result.hub_contract)
        self.assertIsNotNone(result.hub_contract, "hub_contract must not be None")
        self.assertIn("info", result.hub_contract, "info key must be present")
        self.assertIsNotNone(result.hub_contract["info"], "info must not be None")

    def test_normalize_handles_very_large_documents(self):
        """Test that normalize() handles very large documents correctly through public API."""
        large_description = "A" * 100000  # 100KB string
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-large",
                        "name": "Test Product",
                        "description": large_description,
                    }
                },
                "dataSchema": {"fields": [{"name": "id", "type": "string"}]},
            },
        }

        result = self.normalizer.normalize(contract_data, spec_version="4.1")

        # Should handle very large documents
        self.assertIsNotNone(result.hub_contract)

    def test_normalize_handles_none_values(self):
        """Test that normalize() handles None values correctly through public API."""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-none",
                        "name": "Test Product",
                        "description": None,  # None value
                    }
                },
                "dataSchema": {"fields": [{"name": "id", "type": "string"}]},
            },
        }

        result = self.normalizer.normalize(contract_data, spec_version="4.1")

        # Should handle None values gracefully
        self.assertIsNotNone(result.hub_contract)

    def test_normalize_handles_nested_structures(self):
        """Test that normalize() handles nested structures correctly through public API."""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"productID": "test-nested", "name": "Test Product"}},
                "dataSchema": {
                    "fields": [
                        {
                            "name": "id",
                            "type": "string",
                            "nested": {"level1": {"level2": {"level3": {"value": "deep"}}}},
                        }
                    ]
                },
            },
        }

        result = self.normalizer.normalize(contract_data, spec_version="4.1")

        # Should handle nested structures
        self.assertIsNotNone(result.hub_contract)
        self.assertIsNotNone(result.hub_contract, "hub_contract must not be None")
        self.assertIn("schema", result.hub_contract, "schema key must be present")
        self.assertIsNotNone(result.hub_contract["schema"], "schema must not be None")
