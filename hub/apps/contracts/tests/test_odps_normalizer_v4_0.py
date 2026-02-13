"""
Unit tests for ODPSNormalizerV4_0

Tests verify:
1. Version support (4.0 only)
2. ODPS 4.0 normalization
3. Graceful degradation for missing ODPS 4.1 features (productStrategy, paymentGateways)
4. All common normalization features working correctly
"""

from django.test import TestCase

from hub.apps.contracts.models import NormalizationStatus, OriginalSpecType
from hub.apps.contracts.normalization.odps_normalizer_v4_0 import ODPSNormalizerV4_0


class ODPSNormalizerV4_0SupportsTest(TestCase):
    """Test ODPSNormalizerV4_0 supports() method"""

    def setUp(self):
        """Set up test fixtures"""
        self.normalizer = ODPSNormalizerV4_0()

    def test_supports_odps_4_0(self):
        """Test that normalizer supports ODPS 4.0"""
        contract_data = {"schema": "https://opendataproducts.org/schema/v4.0"}
        result = self.normalizer.supports(OriginalSpecType.ODPS, "4.0", contract_data)
        self.assertTrue(result)

    def test_supports_not_odps_4_1(self):
        """Test that normalizer does not support ODPS 4.1"""
        contract_data = {"schema": "https://opendataproducts.org/schema/v4.1"}
        result = self.normalizer.supports(OriginalSpecType.ODPS, "4.1", contract_data)
        self.assertFalse(result)

    def test_supports_not_odps_3_x(self):
        """Test that normalizer does not support ODPS 3.x"""
        contract_data = {"schema": "https://opendataproducts.org/schema/v3.9"}
        result = self.normalizer.supports(OriginalSpecType.ODPS, "3.9", contract_data)
        self.assertFalse(result)

    def test_supports_not_odcs(self):
        """Test that normalizer does not support ODCS"""
        contract_data = {"apiVersion": "odcs/v3", "kind": "DataContract"}
        result = self.normalizer.supports(OriginalSpecType.ODCS, "3.0.2", contract_data)
        self.assertFalse(result)

    def test_spec_type_attribute(self):
        """Test that normalizer has spec_type attribute"""
        self.assertEqual(self.normalizer.spec_type, OriginalSpecType.ODPS)


class ODPSNormalizerV4_0NormalizeTest(TestCase):
    """Test ODPSNormalizerV4_0 normalize() method"""

    def setUp(self):
        """Set up test fixtures"""
        self.normalizer = ODPSNormalizerV4_0()

    def test_normalize_odps_4_0_contract(self):
        """Test normalization of a complete ODPS 4.0 contract"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.0",
            "version": "4.0",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product-4.0",
                        "name": "Test Product 4.0",
                        "description": "A test product for ODPS 4.0",
                        "productVersion": "1.0.0",
                        "tags": ["test", "odps"],
                        "categories": ["data-product"],
                    }
                },
                "dataQuality": {
                    "declarative": {
                        "default": "default-profile",
                        "dimensions": {
                            "completeness": {
                                "objectives": {"min": 0.95},
                                "unit": "percentage",
                                "threshold": 0.90,
                            }
                        },
                    }
                },
                "SLA": {"declarative": {"dimensions": {"availability": {"target": 99.9}}}},
                "marketplace": {
                    "pricingPlans": [{"name": "Basic", "price": 10.00}],
                    "accessMethods": {"api": {"endpoint": "https://api.example.com"}},
                    # Note: paymentGateways is NOT present (4.1+ feature)
                },
            },
            "dataHolder": {"en": {"legalName": "Test Company", "email": "test@example.com"}},
            "license": {
                "en": {
                    "definition": "MIT License",
                    "restrictions": ["No commercial use"],
                    "rights": ["Read", "Write"],
                }
            },
        }

        result = self.normalizer.normalize(contract_data, spec_version="4.0")

        # Check result structure
        self.assertTrue(hasattr(result, "hub_contract"))
        self.assertTrue(hasattr(result, "status"))
        self.assertTrue(hasattr(result, "errors"))
        self.assertTrue(hasattr(result, "warnings"))
        self.assertTrue(hasattr(result, "spec_type"))
        self.assertTrue(hasattr(result, "spec_version"))

        # Check spec type and version
        self.assertEqual(result.spec_type, OriginalSpecType.ODPS)
        self.assertEqual(result.spec_version, "4.0")

        # Check hub_contract structure
        self.assertIsNotNone(result.hub_contract)
        hub_contract = result.hub_contract

        # Check info section
        self.assertIn("info", hub_contract)
        self.assertEqual(hub_contract["id"], "test-product-4.0")
        self.assertEqual(hub_contract["info"]["name"], "Test Product 4.0")
        self.assertEqual(hub_contract["info"]["description"], "A test product for ODPS 4.0")
        self.assertEqual(hub_contract["info"]["version"], "1.0.0")
        self.assertIn("tags", hub_contract["info"])
        self.assertIn("test", hub_contract["info"]["tags"])
        self.assertIn("odps", hub_contract["info"]["tags"])
        self.assertIn("data-product", hub_contract["info"]["tags"])

        # Check owners
        self.assertIn("owners", hub_contract["info"])
        self.assertEqual(len(hub_contract["info"]["owners"]), 1)
        self.assertEqual(hub_contract["info"]["owners"][0]["name"], "Test Company")
        self.assertEqual(hub_contract["info"]["owners"][0]["email"], "test@example.com")

        # Check quality section
        self.assertIn("quality", hub_contract)
        self.assertEqual(hub_contract["quality"]["default_profile_key"], "default-profile")
        self.assertIn("rules", hub_contract["quality"])
        self.assertEqual(len(hub_contract["quality"]["rules"]), 1)
        self.assertEqual(hub_contract["quality"]["rules"][0]["dimension"], "completeness")

        # Check lifecycle section
        self.assertIn("lifecycle", hub_contract)
        self.assertIn("slas", hub_contract["lifecycle"])
        self.assertEqual(hub_contract["lifecycle"]["slas"]["availability"], 99.9)

        # Check marketplace section
        self.assertIn("marketplace", hub_contract)
        self.assertEqual(hub_contract["marketplace"]["license_summary"], "MIT License")
        self.assertIn("restricted_use", hub_contract["marketplace"])
        self.assertIn("intended_use", hub_contract["marketplace"])
        self.assertIn("x_odps", hub_contract["marketplace"])
        self.assertIn("pricing_plans", hub_contract["marketplace"]["x_odps"])
        self.assertIn("access_methods", hub_contract["marketplace"]["x_odps"])

        # Verify paymentGateways is NOT present (4.1+ feature, gracefully skipped)
        self.assertNotIn("payment_gateways", hub_contract["marketplace"]["x_odps"])

        # Verify productStrategy is NOT present (4.1+ feature, gracefully skipped)
        if "extensions" in hub_contract and "x_odps" in hub_contract["extensions"]:
            self.assertNotIn("product_strategy", hub_contract["extensions"]["x_odps"])

    def test_normalize_rejects_odps_4_1(self):
        """Test that normalizer rejects ODPS 4.1 contracts"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {"en": {"name": "Test Product", "productID": "test-product"}}},
        }

        result = self.normalizer.normalize(contract_data, spec_version="4.1")

        # Should fail with version not supported error
        self.assertEqual(result.status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertTrue(len(result.errors) > 0)
        self.assertIn("does not support ODPS version", result.errors[0])

    def test_normalize_gracefully_handles_missing_payment_gateways(self):
        """Test that normalizer gracefully handles missing paymentGateways (4.1+ feature)"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.0",
            "version": "4.0",
            "product": {
                "details": {"en": {"name": "Test Product", "productID": "test-product"}},
                "marketplace": {
                    "pricingPlans": [],
                    "accessMethods": {},
                    # paymentGateways is missing (expected for 4.0)
                },
            },
        }

        result = self.normalizer.normalize(contract_data, spec_version="4.0")

        # Should succeed without errors
        self.assertTrue(hasattr(result, "hub_contract"))
        if result.hub_contract:
            # Marketplace should be normalized without paymentGateways
            if (
                "marketplace" in result.hub_contract
                and "x_odps" in result.hub_contract["marketplace"]
            ):
                self.assertNotIn("payment_gateways", result.hub_contract["marketplace"]["x_odps"])

    def test_normalize_gracefully_handles_product_strategy(self):
        """Test that normalizer gracefully skips productStrategy (4.1+ feature)"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.0",
            "version": "4.0",
            "product": {"details": {"en": {"name": "Test Product", "productID": "test-product"}}},
            # productStrategy is present but should be ignored (4.1+ feature)
            "productStrategy": {
                "objectives": ["Objective 1"],
                "strategicAlignment": ["Alignment 1"],
                "productKPIs": ["KPI 1"],
            },
        }

        result = self.normalizer.normalize(contract_data, spec_version="4.0")

        # Should succeed without errors
        self.assertTrue(hasattr(result, "hub_contract"))
        if result.hub_contract:
            # productStrategy should NOT be normalized (4.1+ feature)
            if (
                "extensions" in result.hub_contract
                and "x_odps" in result.hub_contract["extensions"]
            ):
                self.assertNotIn("product_strategy", result.hub_contract["extensions"]["x_odps"])

    def test_normalize_detects_version_if_not_provided(self):
        """Test that normalize() detects ODPS 4.0 version if not provided"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.0",
            "product": {"details": {"en": {"name": "Test Product", "productID": "test-product"}}},
        }

        result = self.normalizer.normalize(contract_data)

        # Should detect version 4.0
        self.assertTrue(hasattr(result, "spec_version"))
        self.assertEqual(result.spec_version, "4.0")

    def test_normalize_handles_minimal_contract(self):
        """Test normalization of minimal ODPS 4.0 contract"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.0",
            "version": "4.0",
            "product": {
                "details": {"en": {"name": "Minimal Product", "productID": "minimal-product"}}
            },
        }

        result = self.normalizer.normalize(contract_data, spec_version="4.0")

        # Should return a result (may fail due to missing schema fields, but structure should be correct)
        self.assertTrue(hasattr(result, "hub_contract"))
        self.assertTrue(hasattr(result, "status"))
        self.assertTrue(hasattr(result, "spec_version"))
        self.assertEqual(result.spec_version, "4.0")

        if result.hub_contract:
            # Should have basic structure
            self.assertIn("info", result.hub_contract)
            self.assertEqual(result.hub_contract["info"]["name"], "Minimal Product")
            self.assertEqual(result.hub_contract["id"], "minimal-product")

    def test_normalize_validates_contract_data_type(self):
        """Test that normalize() validates contract_data is a dict"""
        result = self.normalizer.normalize("not a dict", spec_version="4.0")

        # Should fail with type error
        self.assertEqual(result.status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertTrue(len(result.errors) > 0)
        self.assertIn("must be a dictionary", result.errors[0])


class ODPSNormalizerV4_0GracefulDegradationTest(TestCase):
    """Test graceful degradation for missing ODPS 4.1 features"""

    def setUp(self):
        """Set up test fixtures"""
        self.normalizer = ODPSNormalizerV4_0()

    def test_graceful_degradation_payment_gateways(self):
        """Test that paymentGateways (4.1+ feature) is gracefully skipped"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.0",
            "version": "4.0",
            "product": {
                "details": {"en": {"name": "Test Product", "productID": "test-product"}},
                "marketplace": {
                    "pricingPlans": [],
                    "accessMethods": {},
                    # paymentGateways is missing (expected for 4.0)
                },
            },
        }

        result = self.normalizer.normalize(contract_data, spec_version="4.0")

        # Should not have errors related to missing paymentGateways
        if result.errors:
            for error in result.errors:
                self.assertNotIn("paymentGateways", error)
                self.assertNotIn("payment_gateways", error)

        # Should not have paymentGateways in output
        if result.hub_contract and "marketplace" in result.hub_contract:
            if "x_odps" in result.hub_contract["marketplace"]:
                self.assertNotIn("payment_gateways", result.hub_contract["marketplace"]["x_odps"])

    def test_graceful_degradation_product_strategy(self):
        """Test that productStrategy (4.1+ feature) is gracefully skipped"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.0",
            "version": "4.0",
            "product": {"details": {"en": {"name": "Test Product", "productID": "test-product"}}},
            # productStrategy is missing (expected for 4.0)
        }

        result = self.normalizer.normalize(contract_data, spec_version="4.0")

        # Should not have errors related to missing productStrategy
        if result.errors:
            for error in result.errors:
                self.assertNotIn("productStrategy", error)
                self.assertNotIn("product_strategy", error)

        # Should not have productStrategy in output
        if result.hub_contract and "extensions" in result.hub_contract:
            if "x_odps" in result.hub_contract["extensions"]:
                self.assertNotIn("product_strategy", result.hub_contract["extensions"]["x_odps"])

    def test_normalize_handles_unicode_characters(self):
        """Test that normalization handles unicode characters correctly."""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.0",
            "version": "4.0",
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

        result = self.normalizer.normalize(contract_data, spec_version="4.0")

        # Should handle unicode characters
        self.assertIsNotNone(result.hub_contract)
        if result.hub_contract and "info" in result.hub_contract:
            self.assertIsNotNone(result.hub_contract["info"])

    def test_normalize_handles_special_characters(self):
        """Test that normalization handles special characters correctly."""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.0",
            "version": "4.0",
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

        result = self.normalizer.normalize(contract_data, spec_version="4.0")

        # Should handle special characters
        self.assertIsNotNone(result.hub_contract)
        if result.hub_contract and "info" in result.hub_contract:
            self.assertIsNotNone(result.hub_contract["info"])

    def test_normalize_handles_very_large_documents(self):
        """Test that normalization handles very large documents correctly."""
        large_description = "A" * 100000  # 100KB string
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.0",
            "version": "4.0",
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

        result = self.normalizer.normalize(contract_data, spec_version="4.0")

        # Should handle very large documents
        self.assertIsNotNone(result.hub_contract)

    def test_normalize_handles_none_values(self):
        """Test that normalization handles None values correctly."""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.0",
            "version": "4.0",
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

        result = self.normalizer.normalize(contract_data, spec_version="4.0")

        # Should handle None values gracefully
        self.assertIsNotNone(result.hub_contract)

    def test_normalize_handles_nested_structures(self):
        """Test that normalization handles nested structures correctly."""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.0",
            "version": "4.0",
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

        result = self.normalizer.normalize(contract_data, spec_version="4.0")

        # Should handle nested structures
        self.assertIsNotNone(result.hub_contract)
        if result.hub_contract and "schema" in result.hub_contract:
            self.assertIsNotNone(result.hub_contract["schema"])
