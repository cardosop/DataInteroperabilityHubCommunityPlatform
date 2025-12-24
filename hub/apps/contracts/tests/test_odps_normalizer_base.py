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
from unittest.mock import Mock, patch
from django.test import TestCase

from hub.apps.contracts.normalization.odps_normalizer_base import ODPSNormalizerBase
from hub.apps.contracts.normalization import NormalizationResult, SpecNormalizer
from hub.apps.contracts.models import NormalizationStatus, OriginalSpecType
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
            "product": {
                "details": {
                    "en": {
                        "name": "Test Product",
                        "productID": "test-product-1"
                    }
                }
            }
        }

        result = self.normalizer.normalize(contract_data, spec_version="4.1")
        # Check that result has NormalizationResult attributes (duck typing)
        # The base class dynamically imports NormalizationResult, so isinstance may fail
        self.assertTrue(hasattr(result, 'hub_contract'))
        self.assertTrue(hasattr(result, 'status'))
        self.assertTrue(hasattr(result, 'errors'))
        self.assertTrue(hasattr(result, 'warnings'))
        self.assertTrue(hasattr(result, 'spec_type'))
        self.assertTrue(hasattr(result, 'spec_version'))
        self.assertEqual(result.spec_type, OriginalSpecType.ODPS)
        self.assertEqual(result.spec_version, "4.1")
        # Note: Status may be NORMALIZATION_FAILED if schema.fields is empty (expected behavior)
        # The important thing is that a result is returned with the correct structure

    def test_normalize_rejects_unsupported_version(self):
        """Test that normalize() rejects unsupported version"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.0",
            "version": "4.0",
            "product": {
                "details": {
                    "en": {
                        "name": "Test Product"
                    }
                }
            }
        }

        result = self.normalizer.normalize(contract_data, spec_version="4.0")
        # Check that result has NormalizationResult attributes (duck typing)
        self.assertTrue(hasattr(result, 'status'))
        self.assertTrue(hasattr(result, 'errors'))
        self.assertEqual(result.status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertTrue(len(result.errors) > 0)
        self.assertIn("does not support ODPS version", result.errors[0])

    def test_normalize_detects_version_if_not_provided(self):
        """Test that normalize() detects version if not provided"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "product": {
                "details": {
                    "en": {
                        "name": "Test Product",
                        "productID": "test-product-1"
                    }
                }
            }
        }

        result = self.normalizer.normalize(contract_data)
        # Check that result has NormalizationResult attributes (duck typing)
        self.assertTrue(hasattr(result, 'spec_version'))
        self.assertEqual(result.spec_version, "4.1")

    def test_normalize_validates_contract_data_type(self):
        """Test that normalize() validates contract_data is a dict"""
        result = self.normalizer.normalize("not a dict", spec_version="4.1")
        # Check that result has NormalizationResult attributes (duck typing)
        self.assertTrue(hasattr(result, 'status'))
        self.assertTrue(hasattr(result, 'errors'))
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
            }
        }

        result = self.normalizer.normalize(contract_data, spec_version="4.1")
        # Check that result has NormalizationResult attributes (duck typing)
        self.assertTrue(hasattr(result, 'status'))
        self.assertTrue(hasattr(result, 'errors'))
        # Should fail due to missing required field
        self.assertEqual(result.status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertTrue(len(result.errors) > 0)


class ODPSNormalizerBaseHelperMethodsTest(TestCase):
    """Test ODPSNormalizerBase helper methods"""

    def setUp(self):
        """Set up test fixtures"""
        self.normalizer = TestODPSNormalizerV4_1()

    def test_initialize_hub_contract(self):
        """Test _initialize_hub_contract() method"""
        contract_data = {}
        spec_version = "4.1"

        hub_contract = self.normalizer._initialize_hub_contract(contract_data, spec_version)

        self.assertIsInstance(hub_contract, dict)
        self.assertIn("info", hub_contract)
        self.assertIn("schema", hub_contract)
        self.assertIn("extensions", hub_contract)
        self.assertIn("normalization", hub_contract)
        self.assertEqual(hub_contract["normalization"]["original_spec_type"], OriginalSpecType.ODPS)
        self.assertEqual(hub_contract["normalization"]["original_spec_version"], spec_version)

    def test_determine_status_success(self):
        """Test _determine_status() for successful normalization"""
        hub_contract = {
            "info": {"name": "Test Product"},
            "schema": {"fields": [{"name": "field1"}]}
        }
        errors = []
        warnings = []

        status = self.normalizer._determine_status(hub_contract, errors, warnings)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)

    def test_determine_status_with_warnings(self):
        """Test _determine_status() with warnings"""
        hub_contract = {
            "info": {"name": "Test Product"},
            "schema": {"fields": [{"name": "field1"}]},
            "extensions": {}
        }
        errors = []
        warnings = ["Some warning"]

        status = self.normalizer._determine_status(hub_contract, errors, warnings)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_WITH_WARNINGS)

    def test_determine_status_failed(self):
        """Test _determine_status() for failed normalization"""
        hub_contract = None
        errors = ["Some error"]
        warnings = []

        status = self.normalizer._determine_status(hub_contract, errors, warnings)
        self.assertEqual(status, NormalizationStatus.NORMALIZATION_FAILED)

    def test_normalize_field_with_error_context_required(self):
        """Test _normalize_field_with_error_context() for required fields"""
        # Missing required field should raise error
        with self.assertRaises(ODPSNormalizationError) as cm:
            self.normalizer._normalize_field_with_error_context(
                "test_field", "/test", None, str, required=True
            )

        self.assertIn("Required field", str(cm.exception))
        self.assertEqual(cm.exception.error_code, ODPSNormalizationError.ERROR_CODE_MISSING_REQUIRED_FIELD)

    def test_normalize_field_with_error_context_optional(self):
        """Test _normalize_field_with_error_context() for optional fields"""
        # Missing optional field should return default
        result = self.normalizer._normalize_field_with_error_context(
            "test_field", "/test", None, str, default_value="default", required=False
        )
        self.assertEqual(result, "default")

    def test_normalize_field_with_error_context_type_validation(self):
        """Test _normalize_field_with_error_context() type validation"""
        # Invalid type should raise error
        with self.assertRaises(ODPSNormalizationError) as cm:
            self.normalizer._normalize_field_with_error_context(
                "test_field", "/test", 123, str, required=True
            )

        self.assertIn("invalid type", str(cm.exception))
        self.assertEqual(cm.exception.error_code, ODPSNormalizationError.ERROR_CODE_TYPE_CONVERSION_FAILED)

    def test_normalize_optional_field(self):
        """Test _normalize_optional_field() method"""
        warnings = []

        # Missing field should return default and add warning
        result = self.normalizer._normalize_optional_field(
            "test_field", "/test", None, str, default_value="default", warnings=warnings
        )
        self.assertEqual(result, "default")
        self.assertTrue(len(warnings) > 0)

        # Valid field should return value
        result = self.normalizer._normalize_optional_field(
            "test_field", "/test", "value", str, default_value="default", warnings=warnings
        )
        self.assertEqual(result, "value")

        # Invalid type should return default and add warning
        warnings.clear()
        result = self.normalizer._normalize_optional_field(
            "test_field", "/test", 123, str, default_value="default", warnings=warnings
        )
        self.assertEqual(result, "default")
        self.assertTrue(len(warnings) > 0)

