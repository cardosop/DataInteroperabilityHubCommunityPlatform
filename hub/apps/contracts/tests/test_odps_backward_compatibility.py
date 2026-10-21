"""
Unit tests for ODPS backward compatibility normalizers (Task 1.5.4)

Tests for ODPS 3.x, 2.x, and 1.x normalizers to ensure:
- Version detection and support
- Graceful degradation for missing features
- Version-specific mappings
"""

from django.test import TestCase

from hub.apps.contracts.models import NormalizationStatus, OriginalSpecType
from hub.apps.contracts.normalization.odps_normalizer_v1_x import ODPSNormalizerV1_X
from hub.apps.contracts.normalization.odps_normalizer_v2_x import ODPSNormalizerV2_X
from hub.apps.contracts.normalization.odps_normalizer_v3_x import ODPSNormalizerV3_X


class ODPSNormalizerV3_XTest(TestCase):
    """Test ODPSNormalizerV3_X for ODPS 3.x versions"""

    def setUp(self):
        """Set up test fixtures"""
        self.normalizer = ODPSNormalizerV3_X()

    def test_supports_version_3_9(self):
        """Test that normalizer supports ODPS 3.9 through public API"""
        contract_data = {"schema": "https://opendataproducts.org/schema/v3.9", "version": "3.9"}
        # Test through public API - supports() internally calls _supports_version()
        self.assertTrue(self.normalizer.supports(OriginalSpecType.ODPS, "3.9", contract_data))

    def test_supports_version_3_0(self):
        """Test that normalizer supports ODPS 3.0 through public API"""
        contract_data = {"schema": "https://opendataproducts.org/schema/v3.0", "version": "3.0"}
        # Test through public API - supports() internally calls _supports_version()
        self.assertTrue(self.normalizer.supports(OriginalSpecType.ODPS, "3.0", contract_data))

    def test_supports_version_3_x(self):
        """Test that normalizer supports generic 3.x version through public API"""
        contract_data = {"schema": "https://opendataproducts.org/schema/v3.x", "version": "3.x"}
        # Test through public API - supports() internally calls _supports_version()
        self.assertTrue(self.normalizer.supports(OriginalSpecType.ODPS, "3.x", contract_data))

    def test_does_not_support_version_4_0(self):
        """Test that normalizer does not support ODPS 4.0 through public API"""
        contract_data = {"schema": "https://opendataproducts.org/schema/v4.0", "version": "4.0"}
        # Test through public API - supports() internally calls _supports_version()
        self.assertFalse(self.normalizer.supports(OriginalSpecType.ODPS, "4.0", contract_data))

    def test_does_not_support_version_2_x(self):
        """Test that normalizer does not support ODPS 2.x through public API"""
        contract_data = {"schema": "https://opendataproducts.org/schema/v2.9", "version": "2.9"}
        # Test through public API - supports() internally calls _supports_version()
        self.assertFalse(self.normalizer.supports(OriginalSpecType.ODPS, "2.9", contract_data))

    def test_supports_method_3_9(self):
        """Test that supports() method works for ODPS 3.9"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v3.9",
            "version": "3.9",
            "product": {"details": {"en": {"productID": "test-product", "name": "Test Product"}}},
        }
        self.assertTrue(self.normalizer.supports(OriginalSpecType.ODPS, "3.9", contract_data))

    def test_normalize_3_9_basic(self):
        """Test basic normalization for ODPS 3.9"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v3.9",
            "version": "3.9",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product-3x",
                        "name": "ODPS 3.x Test Product",
                        "description": "Test description",
                    }
                },
                "dataSchema": {"fields": [{"name": "test_field", "type": "string"}]},
            },
        }

        result = self.normalizer.normalize(contract_data, spec_version="3.9")

        self.assertIsNotNone(result.hub_contract)
        self.assertEqual(result.spec_type, OriginalSpecType.ODPS)
        self.assertEqual(result.spec_version, "3.9")
        self.assertEqual(result.status, NormalizationStatus.NORMALIZED_OK)
        self.assertEqual(result.hub_contract["id"], "test-product-3x")
        self.assertEqual(result.hub_contract["info"]["name"], "ODPS 3.x Test Product")

    def test_normalize_3_9_graceful_degradation_product_strategy(self):
        """Test that productStrategy is gracefully skipped for ODPS 3.9"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v3.9",
            "version": "3.9",
            "product": {
                "details": {"en": {"productID": "test-product", "name": "Test Product"}},
                "dataSchema": {"fields": [{"name": "test_field", "type": "string"}]},
            },
            # productStrategy is not available in 3.x, but if present, should be skipped
            "productStrategy": {"objectives": ["Should be ignored"]},
        }

        result = self.normalizer.normalize(contract_data, spec_version="3.9")

        self.assertIsNotNone(result.hub_contract)
        # productStrategy should be gracefully skipped — either absent from
        # extensions entirely, or present in x_odps without product_strategy.
        self.assertIn("extensions", result.hub_contract)
        extensions = result.hub_contract["extensions"]
        if "x_odps" in extensions:
            self.assertNotIn("product_strategy", extensions["x_odps"])
        # If x_odps is absent, productStrategy was silently dropped entirely,
        # which is also acceptable graceful degradation.

    def test_normalize_3_9_missing_optional_fields(self):
        """Test graceful handling of missing optional fields in ODPS 3.9"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v3.9",
            "version": "3.9",
            "product": {
                "details": {"en": {"productID": "test-product", "name": "Test Product"}},
                "dataSchema": {"fields": [{"name": "test_field", "type": "string"}]},
            },
            # Missing optional fields: marketplace, lifecycle, quality
        }

        result = self.normalizer.normalize(contract_data, spec_version="3.9")

        self.assertIsNotNone(result.hub_contract)
        # Should normalize successfully even with missing optional fields
        self.assertEqual(result.status, NormalizationStatus.NORMALIZED_OK)


class ODPSNormalizerV2_XTest(TestCase):
    """Test ODPSNormalizerV2_X for ODPS 2.x versions"""

    def setUp(self):
        """Set up test fixtures"""
        self.normalizer = ODPSNormalizerV2_X()

    def test_supports_version_2_9(self):
        """Test that normalizer supports ODPS 2.9 through public API"""
        contract_data = {"schema": "https://opendataproducts.org/schema/v2.9", "version": "2.9"}
        # Test through public API - supports() internally calls _supports_version()
        self.assertTrue(self.normalizer.supports(OriginalSpecType.ODPS, "2.9", contract_data))

    def test_supports_version_2_0(self):
        """Test that normalizer supports ODPS 2.0 through public API"""
        contract_data = {"schema": "https://opendataproducts.org/schema/v2.0", "version": "2.0"}
        # Test through public API - supports() internally calls _supports_version()
        self.assertTrue(self.normalizer.supports(OriginalSpecType.ODPS, "2.0", contract_data))

    def test_supports_version_2_x(self):
        """Test that normalizer supports generic 2.x version through public API"""
        contract_data = {"schema": "https://opendataproducts.org/schema/v2.x", "version": "2.x"}
        # Test through public API - supports() internally calls _supports_version()
        self.assertTrue(self.normalizer.supports(OriginalSpecType.ODPS, "2.x", contract_data))

    def test_does_not_support_version_3_0(self):
        """Test that normalizer does not support ODPS 3.0 through public API"""
        contract_data = {"schema": "https://opendataproducts.org/schema/v3.0", "version": "3.0"}
        # Test through public API - supports() internally calls _supports_version()
        self.assertFalse(self.normalizer.supports(OriginalSpecType.ODPS, "3.0", contract_data))

    def test_does_not_support_version_1_x(self):
        """Test that normalizer does not support ODPS 1.x through public API"""
        contract_data = {"schema": "https://opendataproducts.org/schema/v1.9", "version": "1.9"}
        # Test through public API - supports() internally calls _supports_version()
        self.assertFalse(self.normalizer.supports(OriginalSpecType.ODPS, "1.9", contract_data))

    def test_supports_method_2_9(self):
        """Test that supports() method works for ODPS 2.9"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v2.9",
            "version": "2.9",
            "product": {"details": {"en": {"productID": "test-product", "name": "Test Product"}}},
        }
        self.assertTrue(self.normalizer.supports(OriginalSpecType.ODPS, "2.9", contract_data))

    def test_normalize_2_9_basic(self):
        """Test basic normalization for ODPS 2.9"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v2.9",
            "version": "2.9",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product-2x",
                        "name": "ODPS 2.x Test Product",
                        "description": "Test description",
                    }
                },
                "dataSchema": {"fields": [{"name": "test_field", "type": "string"}]},
            },
        }

        result = self.normalizer.normalize(contract_data, spec_version="2.9")

        self.assertIsNotNone(result.hub_contract)
        self.assertEqual(result.spec_type, OriginalSpecType.ODPS)
        self.assertEqual(result.spec_version, "2.9")
        self.assertEqual(result.status, NormalizationStatus.NORMALIZED_OK)
        self.assertEqual(result.hub_contract["id"], "test-product-2x")
        self.assertEqual(result.hub_contract["info"]["name"], "ODPS 2.x Test Product")

    def test_normalize_2_9_graceful_degradation_product_strategy(self):
        """Test that productStrategy is gracefully skipped for ODPS 2.9"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v2.9",
            "version": "2.9",
            "product": {
                "details": {"en": {"productID": "test-product", "name": "Test Product"}},
                "dataSchema": {"fields": [{"name": "test_field", "type": "string"}]},
            },
            # productStrategy is not available in 2.x, but if present, should be skipped
            "productStrategy": {"objectives": ["Should be ignored"]},
        }

        result = self.normalizer.normalize(contract_data, spec_version="2.9")

        self.assertIsNotNone(result.hub_contract)
        # productStrategy should be gracefully skipped — either absent from
        # extensions entirely, or present in x_odps without product_strategy.
        self.assertIn("extensions", result.hub_contract)
        extensions = result.hub_contract["extensions"]
        if "x_odps" in extensions:
            self.assertNotIn("product_strategy", extensions["x_odps"])
        # If x_odps is absent, productStrategy was silently dropped entirely,
        # which is also acceptable graceful degradation.

    def test_normalize_2_9_missing_optional_fields(self):
        """Test graceful handling of missing optional fields in ODPS 2.9"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v2.9",
            "version": "2.9",
            "product": {
                "details": {"en": {"productID": "test-product", "name": "Test Product"}},
                "dataSchema": {"fields": [{"name": "test_field", "type": "string"}]},
            },
            # Missing optional fields: marketplace, lifecycle, quality
        }

        result = self.normalizer.normalize(contract_data, spec_version="2.9")

        self.assertIsNotNone(result.hub_contract)
        # Should normalize successfully even with missing optional fields
        self.assertEqual(result.status, NormalizationStatus.NORMALIZED_OK)


class ODPSNormalizerV1_XTest(TestCase):
    """Test ODPSNormalizerV1_X for ODPS 1.x versions"""

    def setUp(self):
        """Set up test fixtures"""
        self.normalizer = ODPSNormalizerV1_X()

    def test_supports_version_1_9(self):
        """Test that normalizer supports ODPS 1.9 through public API"""
        contract_data = {"schema": "https://opendataproducts.org/schema/v1.9", "version": "1.9"}
        # Test through public API - supports() internally calls _supports_version()
        self.assertTrue(self.normalizer.supports(OriginalSpecType.ODPS, "1.9", contract_data))

    def test_supports_version_1_0(self):
        """Test that normalizer supports ODPS 1.0 through public API"""
        contract_data = {"schema": "https://opendataproducts.org/schema/v1.0", "version": "1.0"}
        # Test through public API - supports() internally calls _supports_version()
        self.assertTrue(self.normalizer.supports(OriginalSpecType.ODPS, "1.0", contract_data))

    def test_supports_version_1_x(self):
        """Test that normalizer supports generic 1.x version through public API"""
        contract_data = {"schema": "https://opendataproducts.org/schema/v1.x", "version": "1.x"}
        # Test through public API - supports() internally calls _supports_version()
        self.assertTrue(self.normalizer.supports(OriginalSpecType.ODPS, "1.x", contract_data))

    def test_does_not_support_version_2_0(self):
        """Test that normalizer does not support ODPS 2.0 through public API"""
        contract_data = {"schema": "https://opendataproducts.org/schema/v2.0", "version": "2.0"}
        # Test through public API - supports() internally calls _supports_version()
        self.assertFalse(self.normalizer.supports(OriginalSpecType.ODPS, "2.0", contract_data))

    def test_supports_method_1_9(self):
        """Test that supports() method works for ODPS 1.9"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v1.9",
            "version": "1.9",
            "product": {"details": {"en": {"productID": "test-product", "name": "Test Product"}}},
        }
        self.assertTrue(self.normalizer.supports(OriginalSpecType.ODPS, "1.9", contract_data))

    def test_normalize_1_9_basic(self):
        """Test basic normalization for ODPS 1.9"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v1.9",
            "version": "1.9",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product-1x",
                        "name": "ODPS 1.x Test Product",
                        "description": "Test description",
                    }
                },
                "dataSchema": {"fields": [{"name": "test_field", "type": "string"}]},
            },
        }

        result = self.normalizer.normalize(contract_data, spec_version="1.9")

        self.assertIsNotNone(result.hub_contract)
        self.assertEqual(result.spec_type, OriginalSpecType.ODPS)
        self.assertEqual(result.spec_version, "1.9")
        self.assertEqual(result.status, NormalizationStatus.NORMALIZED_OK)
        self.assertEqual(result.hub_contract["id"], "test-product-1x")
        self.assertEqual(result.hub_contract["info"]["name"], "ODPS 1.x Test Product")

    def test_normalize_1_9_graceful_degradation_product_strategy(self):
        """Test that productStrategy is gracefully skipped for ODPS 1.9"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v1.9",
            "version": "1.9",
            "product": {
                "details": {"en": {"productID": "test-product", "name": "Test Product"}},
                "dataSchema": {"fields": [{"name": "test_field", "type": "string"}]},
            },
            # productStrategy is not available in 1.x, but if present, should be skipped
            "productStrategy": {"objectives": ["Should be ignored"]},
        }

        result = self.normalizer.normalize(contract_data, spec_version="1.9")

        self.assertIsNotNone(result.hub_contract)
        # productStrategy should be gracefully skipped — either absent from
        # extensions entirely, or present in x_odps without product_strategy.
        self.assertIn("extensions", result.hub_contract)
        extensions = result.hub_contract["extensions"]
        if "x_odps" in extensions:
            self.assertNotIn("product_strategy", extensions["x_odps"])
        # If x_odps is absent, productStrategy was silently dropped entirely,
        # which is also acceptable graceful degradation.

    def test_normalize_1_9_missing_optional_fields(self):
        """Test graceful handling of missing optional fields in ODPS 1.9"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v1.9",
            "version": "1.9",
            "product": {
                "details": {"en": {"productID": "test-product", "name": "Test Product"}},
                "dataSchema": {"fields": [{"name": "test_field", "type": "string"}]},
            },
            # Missing optional fields: marketplace, lifecycle, quality
        }

        result = self.normalizer.normalize(contract_data, spec_version="1.9")

        self.assertIsNotNone(result.hub_contract)
        # Should normalize successfully even with missing optional fields
        self.assertEqual(result.status, NormalizationStatus.NORMALIZED_OK)


class ODPSBackwardCompatibilityIntegrationTest(TestCase):
    """Integration tests for backward compatibility normalizers"""

    def test_all_versions_registered(self):
        """Test that all backward compatibility normalizers are registered"""
        from hub.apps.contracts.models import OriginalSpecType
        from hub.apps.contracts.normalization import get_normalizer

        # Check that all versions have normalizers
        versions = ["3.9", "2.9", "1.9"]

        for version in versions:
            contract_data = {
                "schema": f"https://opendataproducts.org/schema/v{version}",
                "version": version,
                "product": {
                    "details": {"en": {"productID": f"test-{version}", "name": f"Test {version}"}}
                },
            }

            normalizer = get_normalizer(OriginalSpecType.ODPS, version, contract_data)
            self.assertIsNotNone(normalizer, f"Normalizer not found for version {version}")

    def test_version_specific_normalizer_selection(self):
        """Test that correct version-specific normalizer is selected"""
        from hub.apps.contracts.models import OriginalSpecType
        from hub.apps.contracts.normalization import get_normalizer

        # Test 3.x normalizer
        contract_data_3x = {
            "schema": "https://opendataproducts.org/schema/v3.9",
            "version": "3.9",
            "product": {"details": {"en": {"productID": "test-3x", "name": "Test 3.x"}}},
        }
        normalizer_3x = get_normalizer(OriginalSpecType.ODPS, "3.9", contract_data_3x)
        self.assertIsNotNone(normalizer_3x)
        self.assertTrue(normalizer_3x.supports(OriginalSpecType.ODPS, "3.9", contract_data_3x))

        # Test 2.x normalizer
        contract_data_2x = {
            "schema": "https://opendataproducts.org/schema/v2.9",
            "version": "2.9",
            "product": {"details": {"en": {"productID": "test-2x", "name": "Test 2.x"}}},
        }
        normalizer_2x = get_normalizer(OriginalSpecType.ODPS, "2.9", contract_data_2x)
        self.assertIsNotNone(normalizer_2x)
        self.assertTrue(normalizer_2x.supports(OriginalSpecType.ODPS, "2.9", contract_data_2x))

        # Test 1.x normalizer
        contract_data_1x = {
            "schema": "https://opendataproducts.org/schema/v1.9",
            "version": "1.9",
            "product": {"details": {"en": {"productID": "test-1x", "name": "Test 1.x"}}},
        }
        normalizer_1x = get_normalizer(OriginalSpecType.ODPS, "1.9", contract_data_1x)
        self.assertIsNotNone(normalizer_1x)
        self.assertTrue(normalizer_1x.supports(OriginalSpecType.ODPS, "1.9", contract_data_1x))

    def test_backward_compatibility_handles_unicode_characters(self):
        """Test that backward compatibility normalizers handle unicode characters correctly."""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v3.9",
            "version": "3.9",
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

        normalizer = ODPSNormalizerV3_X()
        result = normalizer.normalize(contract_data, spec_version="3.9")

        # Should handle unicode characters
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("info", result.hub_contract)
        self.assertEqual(result.hub_contract["info"]["name"], "测试产品")

    def test_backward_compatibility_handles_special_characters(self):
        """Test that backward compatibility normalizers handle special characters correctly."""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v3.9",
            "version": "3.9",
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

        normalizer = ODPSNormalizerV3_X()
        result = normalizer.normalize(contract_data, spec_version="3.9")

        # Should handle special characters
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("info", result.hub_contract)
        self.assertIn("name", result.hub_contract["info"])
        self.assertEqual(result.hub_contract["info"]["name"], "Test & Co. (Special)")

    def test_backward_compatibility_handles_very_large_documents(self):
        """Test that backward compatibility normalizers handle very large documents correctly."""
        large_description = "A" * 100000  # 100KB string
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v3.9",
            "version": "3.9",
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

        normalizer = ODPSNormalizerV3_X()
        result = normalizer.normalize(contract_data, spec_version="3.9")

        # Should handle very large documents
        self.assertIsNotNone(result.hub_contract)
        # Verify description length is preserved
        desc = result.hub_contract.get("description")
        if desc is None and "info" in result.hub_contract:
            desc = result.hub_contract["info"].get("description")
        self.assertIsNotNone(desc, "Description should be preserved in normalized output")
        self.assertEqual(len(desc), 100000, "Description length should be preserved")

    def test_backward_compatibility_handles_none_values(self):
        """Test that backward compatibility normalizers handle None values correctly."""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v3.9",
            "version": "3.9",
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

        normalizer = ODPSNormalizerV3_X()
        result = normalizer.normalize(contract_data, spec_version="3.9")

        # Should handle None values gracefully
        self.assertIsNotNone(result.hub_contract)
        # None values should be either preserved as None or handled per spec
        has_description = "description" in result.hub_contract
        has_info_description = (
            "info" in result.hub_contract and "description" in result.hub_contract["info"]
        )
        if has_description:
            self.assertTrue(
                result.hub_contract["description"] is None
                or isinstance(result.hub_contract["description"], str),
                "None description should be preserved as None or converted to string",
            )
        if has_info_description:
            self.assertTrue(
                result.hub_contract["info"]["description"] is None
                or isinstance(result.hub_contract["info"]["description"], str),
                "None description in info should be preserved as None or converted to string",
            )

    def test_backward_compatibility_handles_nested_structures(self):
        """Test that backward compatibility normalizers handle nested structures correctly."""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v3.9",
            "version": "3.9",
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

        normalizer = ODPSNormalizerV3_X()
        result = normalizer.normalize(contract_data, spec_version="3.9")

        # Should handle nested structures
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("schema", result.hub_contract)
        self.assertIn("fields", result.hub_contract["schema"])
        self.assertEqual(
            result.hub_contract["schema"]["fields"][0]["nested"]["level1"]["level2"]["level3"][
                "value"
            ],
            "deep",
        )
