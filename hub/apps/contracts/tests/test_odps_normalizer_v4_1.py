"""
Unit tests for ODPSNormalizerV4_1

Tests verify:
1. Version support detection
2. ODPS 4.1-specific normalization
3. Product strategy support
4. Enhanced marketplace features (paymentGateways)
5. Integration with base class functionality
"""
from django.test import TestCase

from hub.apps.contracts.normalization.odps_normalizer_v4_1 import ODPSNormalizerV4_1
from hub.apps.contracts.models import NormalizationStatus, OriginalSpecType


class ODPSNormalizerV4_1StructureTest(TestCase):
    """Test ODPSNormalizerV4_1 structure and inheritance"""

    def setUp(self):
        """Set up test fixtures"""
        self.normalizer = ODPSNormalizerV4_1()

    def test_inherits_from_base(self):
        """Test that ODPSNormalizerV4_1 inherits from ODPSNormalizerBase"""
        from hub.apps.contracts.normalization.odps_normalizer_base import ODPSNormalizerBase
        self.assertIsInstance(self.normalizer, ODPSNormalizerBase)

    def test_has_spec_type(self):
        """Test that normalizer has correct spec_type"""
        self.assertEqual(self.normalizer.spec_type, OriginalSpecType.ODPS)

    def test_supports_version_4_1(self):
        """Test that normalizer supports ODPS 4.1"""
        self.assertTrue(self.normalizer._supports_version("4.1"))

    def test_does_not_support_4_0(self):
        """Test that normalizer does not support ODPS 4.0"""
        self.assertFalse(self.normalizer._supports_version("4.0"))

    def test_does_not_support_3_x(self):
        """Test that normalizer does not support ODPS 3.x"""
        self.assertFalse(self.normalizer._supports_version("3.9"))
        self.assertFalse(self.normalizer._supports_version("3.0"))

    def test_supports_method_4_1(self):
        """Test that supports() method correctly identifies ODPS 4.1"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1"
        }
        result = self.normalizer.supports(OriginalSpecType.ODPS, "4.1", contract_data)
        self.assertTrue(result)

    def test_supports_method_4_0(self):
        """Test that supports() method correctly rejects ODPS 4.0"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.0",
            "version": "4.0"
        }
        result = self.normalizer.supports(OriginalSpecType.ODPS, "4.0", contract_data)
        self.assertFalse(result)


class ODPSNormalizerV4_1BasicNormalizationTest(TestCase):
    """Test basic normalization functionality for ODPS 4.1"""

    def setUp(self):
        """Set up test fixtures"""
        self.normalizer = ODPSNormalizerV4_1()

    def test_normalize_minimal_4_1_contract(self):
        """Test normalization of minimal ODPS 4.1 contract"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                },
                "dataSchema": {
                    "fields": [
                        {
                            "name": "test_field",
                            "type": "string"
                        }
                    ]
                }
            }
        }

        result = self.normalizer.normalize(contract_data)
        self.assertIsNotNone(result.hub_contract)
        self.assertEqual(result.status, NormalizationStatus.NORMALIZED_OK)
        self.assertEqual(result.spec_version, "4.1")
        self.assertIn("info", result.hub_contract)
        self.assertEqual(result.hub_contract["info"]["name"], "Test Product")

    def test_normalize_with_marketplace_4_1(self):
        """Test normalization with ODPS 4.1 marketplace features"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                },
                "marketplace": {
                    "pricingPlans": [
                        {
                            "planID": "free",
                            "name": "Free Plan",
                            "price": 0
                        }
                    ],
                    "accessMethods": {
                        "api": {
                            "type": "REST API"
                        }
                    },
                    "paymentGateways": {
                        "stripe": {
                            "enabled": True,
                            "publicKey": "pk_test_123"
                        }
                    }
                },
                "dataSchema": {
                    "fields": [
                        {
                            "name": "test_field",
                            "type": "string"
                        }
                    ]
                }
            }
        }

        result = self.normalizer.normalize(contract_data)
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("marketplace", result.hub_contract)
        self.assertIn("x_odps", result.hub_contract["marketplace"])
        # Verify paymentGateways is stored (ODPS 4.1 feature)
        self.assertIn("payment_gateways", result.hub_contract["marketplace"]["x_odps"])
        self.assertIn("stripe", result.hub_contract["marketplace"]["x_odps"]["payment_gateways"])


class ODPSNormalizerV4_1ProductStrategyTest(TestCase):
    """Test product strategy normalization for ODPS 4.1"""

    def setUp(self):
        """Set up test fixtures"""
        self.normalizer = ODPSNormalizerV4_1()

    def test_normalize_product_strategy_objectives(self):
        """Test normalization of productStrategy.objectives"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                },
                "dataSchema": {
                    "fields": [
                        {
                            "name": "test_field",
                            "type": "string"
                        }
                    ]
                }
            },
            "productStrategy": {
                "objectives": [
                    "Increase data accessibility",
                    "Improve data quality"
                ]
            }
        }

        result = self.normalizer.normalize(contract_data)
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("extensions", result.hub_contract)
        self.assertIn("x_odps", result.hub_contract["extensions"])
        self.assertIn("product_strategy", result.hub_contract["extensions"]["x_odps"])
        self.assertIn("objectives", result.hub_contract["extensions"]["x_odps"]["product_strategy"])
        objectives = result.hub_contract["extensions"]["x_odps"]["product_strategy"]["objectives"]
        self.assertEqual(len(objectives), 2)
        self.assertIn("Increase data accessibility", objectives)
        self.assertIn("Improve data quality", objectives)

    def test_normalize_product_strategy_strategic_alignment(self):
        """Test normalization of productStrategy.strategicAlignment"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                },
                "dataSchema": {
                    "fields": [
                        {
                            "name": "test_field",
                            "type": "string"
                        }
                    ]
                }
            },
            "productStrategy": {
                "strategicAlignment": [
                    {
                        "goal": "Digital transformation",
                        "priority": "high"
                    }
                ]
            }
        }

        result = self.normalizer.normalize(contract_data)
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("extensions", result.hub_contract)
        self.assertIn("x_odps", result.hub_contract["extensions"])
        self.assertIn("product_strategy", result.hub_contract["extensions"]["x_odps"])
        self.assertIn("strategicAlignment", result.hub_contract["extensions"]["x_odps"]["product_strategy"])
        alignment = result.hub_contract["extensions"]["x_odps"]["product_strategy"]["strategicAlignment"]
        self.assertEqual(len(alignment), 1)
        self.assertEqual(alignment[0]["goal"], "Digital transformation")

    def test_normalize_product_strategy_product_kpis(self):
        """Test normalization of productStrategy.productKPIs"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                },
                "dataSchema": {
                    "fields": [
                        {
                            "name": "test_field",
                            "type": "string"
                        }
                    ]
                }
            },
            "productStrategy": {
                "productKPIs": [
                    {
                        "name": "User adoption",
                        "target": 1000,
                        "unit": "users"
                    }
                ]
            }
        }

        result = self.normalizer.normalize(contract_data)
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("extensions", result.hub_contract)
        self.assertIn("x_odps", result.hub_contract["extensions"])
        self.assertIn("product_strategy", result.hub_contract["extensions"]["x_odps"])
        self.assertIn("productKPIs", result.hub_contract["extensions"]["x_odps"]["product_strategy"])
        kpis = result.hub_contract["extensions"]["x_odps"]["product_strategy"]["productKPIs"]
        self.assertEqual(len(kpis), 1)
        self.assertEqual(kpis[0]["name"], "User adoption")

    def test_normalize_product_strategy_complete(self):
        """Test normalization of complete productStrategy object"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                },
                "dataSchema": {
                    "fields": [
                        {
                            "name": "test_field",
                            "type": "string"
                        }
                    ]
                }
            },
            "productStrategy": {
                "objectives": [
                    "Increase data accessibility"
                ],
                "strategicAlignment": [
                    {
                        "goal": "Digital transformation"
                    }
                ],
                "productKPIs": [
                    {
                        "name": "User adoption",
                        "target": 1000
                    }
                ]
            }
        }

        result = self.normalizer.normalize(contract_data)
        self.assertIsNotNone(result.hub_contract)
        product_strategy = result.hub_contract["extensions"]["x_odps"]["product_strategy"]
        self.assertIn("objectives", product_strategy)
        self.assertIn("strategicAlignment", product_strategy)
        self.assertIn("productKPIs", product_strategy)

    def test_normalize_product_strategy_missing_optional(self):
        """Test that missing productStrategy is handled gracefully"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                },
                "dataSchema": {
                    "fields": [
                        {
                            "name": "test_field",
                            "type": "string"
                        }
                    ]
                }
            }
        }

        result = self.normalizer.normalize(contract_data)
        self.assertIsNotNone(result.hub_contract)
        # Should not fail if productStrategy is missing
        self.assertEqual(result.status, NormalizationStatus.NORMALIZED_OK)


class ODPSNormalizerV4_1MarketplaceTest(TestCase):
    """Test enhanced marketplace features for ODPS 4.1"""

    def setUp(self):
        """Set up test fixtures"""
        self.normalizer = ODPSNormalizerV4_1()

    def test_normalize_marketplace_payment_gateways(self):
        """Test normalization of marketplace.paymentGateways (ODPS 4.1 feature)"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                },
                "marketplace": {
                    "paymentGateways": {
                        "stripe": {
                            "enabled": True,
                            "publicKey": "pk_test_123"
                        },
                        "paypal": {
                            "enabled": False
                        }
                    }
                },
                "dataSchema": {
                    "fields": [
                        {
                            "name": "test_field",
                            "type": "string"
                        }
                    ]
                }
            }
        }

        result = self.normalizer.normalize(contract_data)
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("marketplace", result.hub_contract)
        self.assertIn("x_odps", result.hub_contract["marketplace"])
        self.assertIn("payment_gateways", result.hub_contract["marketplace"]["x_odps"])
        payment_gateways = result.hub_contract["marketplace"]["x_odps"]["payment_gateways"]
        self.assertIn("stripe", payment_gateways)
        self.assertIn("paypal", payment_gateways)
        self.assertTrue(payment_gateways["stripe"]["enabled"])

    def test_normalize_marketplace_complete_4_1(self):
        """Test normalization of complete marketplace with all 4.1 features"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                },
                "marketplace": {
                    "pricingPlans": [
                        {
                            "planID": "free",
                            "name": "Free Plan",
                            "price": 0
                        }
                    ],
                    "accessMethods": {
                        "api": {
                            "type": "REST API"
                        }
                    },
                    "paymentGateways": {
                        "stripe": {
                            "enabled": True
                        }
                    }
                },
                "dataSchema": {
                    "fields": [
                        {
                            "name": "test_field",
                            "type": "string"
                        }
                    ]
                }
            }
        }

        result = self.normalizer.normalize(contract_data)
        self.assertIsNotNone(result.hub_contract)
        marketplace = result.hub_contract["marketplace"]
        x_odps = marketplace["x_odps"]
        self.assertIn("pricing_plans", x_odps)
        self.assertIn("access_methods", x_odps)
        self.assertIn("payment_gateways", x_odps)


class ODPSNormalizerV4_1IntegrationTest(TestCase):
    """Integration tests for ODPSNormalizerV4_1"""

    def setUp(self):
        """Set up test fixtures"""
        self.normalizer = ODPSNormalizerV4_1()

    def test_normalize_complete_4_1_contract(self):
        """Test normalization of complete ODPS 4.1 contract with all features"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product",
                        "description": "A comprehensive test product"
                    }
                },
                "marketplace": {
                    "pricingPlans": [
                        {
                            "planID": "free",
                            "name": "Free Plan"
                        }
                    ],
                    "accessMethods": {
                        "api": {"type": "REST API"}
                    },
                    "paymentGateways": {
                        "stripe": {"enabled": True}
                    }
                },
                "dataSchema": {
                    "fields": [
                        {
                            "name": "test_field",
                            "type": "string"
                        }
                    ]
                }
            },
            "license": {
                "en": {
                    "definition": "MIT License"
                }
            },
            "productStrategy": {
                "objectives": ["Increase accessibility"],
                "strategicAlignment": [{"goal": "Digital transformation"}],
                "productKPIs": [{"name": "User adoption", "target": 1000}]
            }
        }

        result = self.normalizer.normalize(contract_data)
        self.assertIsNotNone(result.hub_contract)
        # Status can be NORMALIZED_OK or NORMALIZED_WITH_WARNINGS (warnings are acceptable)
        self.assertIn(
            result.status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS]
        )
        self.assertEqual(result.spec_version, "4.1")

        # Verify all sections are normalized
        self.assertIn("info", result.hub_contract)
        self.assertIn("marketplace", result.hub_contract)
        self.assertIn("schema", result.hub_contract)
        self.assertIn("extensions", result.hub_contract)
        self.assertIn("x_odps", result.hub_contract["extensions"])
        self.assertIn("product_strategy", result.hub_contract["extensions"]["x_odps"])

    def test_normalize_version_detection(self):
        """Test that version is auto-detected from schema URL"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                },
                "dataSchema": {
                    "fields": [
                        {
                            "name": "test_field",
                            "type": "string"
                        }
                    ]
                }
            }
        }

        result = self.normalizer.normalize(contract_data)
        self.assertIsNotNone(result.hub_contract)
        self.assertEqual(result.spec_version, "4.1")

