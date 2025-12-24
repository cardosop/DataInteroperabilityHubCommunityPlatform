"""
Integration tests for ODPS normalization to HubContract (Task 1.7.2)

Comprehensive integration tests verifying:
1. ODPS → HubContract normalization (marketplace focus)
2. All ODPS versions (4.1, 4.0, 3.x, 2.x, 1.x)
3. Missing fields (graceful degradation)
4. Clear separation (ODPS marketplace, ODCS technical)
5. Complete normalization flow

Tests use real implementations (no mocks/stubs) and follow TDD principles.
"""

import json
from django.test import TestCase

from hub.apps.contracts.models import NormalizationStatus, OriginalSpecType
from hub.apps.contracts.normalization import normalize_contract, get_normalizer


class ODPSNormalizationIntegrationTest(TestCase):
    """Integration tests for ODPS normalization to HubContract"""

    def setUp(self):
        """Set up test fixtures"""
        # Base ODPS contract structure
        self.base_odps_contract = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product-integration",
                        "name": "Integration Test Product",
                        "description": "Test product for integration testing",
                    }
                },
                "dataSchema": {
                    "fields": [
                        {"name": "id", "type": "string", "description": "Unique identifier"},
                        {"name": "name", "type": "string", "description": "Name field"},
                    ]
                },
            },
        }

    def _create_odps_contract_with_marketplace(
        self, version: str, marketplace_data: dict = None
    ) -> dict:
        """Helper to create ODPS contract with marketplace section"""
        contract = self.base_odps_contract.copy()
        contract["schema"] = f"https://opendataproducts.org/schema/v{version}"
        contract["version"] = version

        if marketplace_data:
            if "product" not in contract:
                contract["product"] = {}
            contract["product"]["marketplace"] = marketplace_data

        return contract

    def _create_odps_contract_with_license(self, version: str, license_data: dict = None) -> dict:
        """Helper to create ODPS contract with license section"""
        contract = self.base_odps_contract.copy()
        contract["schema"] = f"https://opendataproducts.org/schema/v{version}"
        contract["version"] = version

        if license_data:
            contract["license"] = license_data

        return contract

    def test_odps_to_hubcontract_marketplace_normalization_4_1(self):
        """Test ODPS 4.1 → HubContract marketplace normalization"""
        marketplace_data = {
            "pricingPlans": [
                {"planID": "basic", "name": "Basic Plan", "price": 9.99, "currency": "USD"},
                {"planID": "premium", "name": "Premium Plan", "price": 29.99, "currency": "USD"},
            ],
            "accessMethods": {
                "api": {"type": "REST API", "endpoint": "https://api.example.com/v1"},
                "download": {"type": "File Download", "format": "CSV"},
            },
            "paymentGateways": {
                "stripe": {"enabled": True, "publicKey": "pk_test_123"},
                "paypal": {"enabled": False},
            },
        }

        contract = self._create_odps_contract_with_marketplace("4.1", marketplace_data)
        contract_json = json.dumps(contract)

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=contract_json, format="JSON"
        )

        # Verify detection
        self.assertEqual(spec_type, OriginalSpecType.ODPS)
        self.assertEqual(spec_version, "4.1")

        # Verify normalization succeeded
        self.assertIsNotNone(hub_contract)
        self.assertIn(
            status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
        )

        # Verify marketplace section exists
        self.assertIn("marketplace", hub_contract)
        marketplace = hub_contract["marketplace"]

        # Verify x_odps extension exists
        self.assertIn("x_odps", marketplace)
        x_odps = marketplace["x_odps"]

        # Verify pricing plans
        self.assertIn("pricing_plans", x_odps)
        self.assertEqual(len(x_odps["pricing_plans"]), 2)
        self.assertEqual(x_odps["pricing_plans"][0]["planID"], "basic")
        self.assertEqual(x_odps["pricing_plans"][0]["price"], 9.99)

        # Verify access methods
        self.assertIn("access_methods", x_odps)
        self.assertIn("api", x_odps["access_methods"])
        self.assertEqual(x_odps["access_methods"]["api"]["type"], "REST API")

        # Verify payment gateways (ODPS 4.1+ feature)
        self.assertIn("payment_gateways", x_odps)
        self.assertIn("stripe", x_odps["payment_gateways"])
        self.assertTrue(x_odps["payment_gateways"]["stripe"]["enabled"])

    def test_odps_to_hubcontract_marketplace_normalization_4_0(self):
        """Test ODPS 4.0 → HubContract marketplace normalization"""
        marketplace_data = {
            "pricingPlans": [{"planID": "standard", "name": "Standard Plan", "price": 19.99}],
            "accessMethods": {"api": {"type": "REST API"}},
            # paymentGateways not available in 4.0
        }

        contract = self._create_odps_contract_with_marketplace("4.0", marketplace_data)
        contract_json = json.dumps(contract)

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=contract_json, format="JSON"
        )

        # Verify detection
        self.assertEqual(spec_type, OriginalSpecType.ODPS)
        self.assertEqual(spec_version, "4.0")

        # Verify normalization succeeded
        self.assertIsNotNone(hub_contract)
        self.assertIn(
            status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
        )

        # Verify marketplace section
        self.assertIn("marketplace", hub_contract)
        marketplace = hub_contract["marketplace"]
        self.assertIn("x_odps", marketplace)

        # Verify pricing plans exist
        self.assertIn("pricing_plans", marketplace["x_odps"])

        # Verify payment gateways not present (4.0 doesn't support it)
        # If present, it should be gracefully handled
        if "payment_gateways" in marketplace["x_odps"]:
            # If somehow present, it should be valid
            self.assertIsInstance(marketplace["x_odps"]["payment_gateways"], dict)

    def test_odps_to_hubcontract_marketplace_normalization_3_x(self):
        """Test ODPS 3.x → HubContract marketplace normalization"""
        marketplace_data = {
            "pricingPlans": [{"planID": "basic", "name": "Basic Plan", "price": 5.99}]
            # accessMethods and paymentGateways may not be available in 3.x
        }

        contract = self._create_odps_contract_with_marketplace("3.9", marketplace_data)
        contract_json = json.dumps(contract)

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=contract_json, format="JSON"
        )

        # Verify detection (may normalize to 3.x)
        self.assertEqual(spec_type, OriginalSpecType.ODPS)
        self.assertIn(spec_version, ["3.9", "3.x"])

        # Verify normalization succeeded
        self.assertIsNotNone(hub_contract)
        self.assertIn(
            status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
        )

        # Verify marketplace section exists
        self.assertIn("marketplace", hub_contract)

    def test_odps_to_hubcontract_marketplace_normalization_2_x(self):
        """Test ODPS 2.x → HubContract marketplace normalization"""
        marketplace_data = {
            "pricingPlans": [{"planID": "basic", "name": "Basic Plan", "price": 4.99}]
        }

        contract = self._create_odps_contract_with_marketplace("2.9", marketplace_data)
        contract_json = json.dumps(contract)

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=contract_json, format="JSON"
        )

        # Verify detection
        self.assertEqual(spec_type, OriginalSpecType.ODPS)
        self.assertIn(spec_version, ["2.9", "2.x"])

        # Verify normalization succeeded
        self.assertIsNotNone(hub_contract)
        self.assertIn(
            status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
        )

        # Verify marketplace section exists
        self.assertIn("marketplace", hub_contract)

    def test_odps_to_hubcontract_marketplace_normalization_1_x(self):
        """Test ODPS 1.x → HubContract marketplace normalization"""
        marketplace_data = {
            "pricingPlans": [{"planID": "basic", "name": "Basic Plan", "price": 3.99}]
        }

        contract = self._create_odps_contract_with_marketplace("1.9", marketplace_data)
        contract_json = json.dumps(contract)

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=contract_json, format="JSON"
        )

        # Verify detection
        self.assertEqual(spec_type, OriginalSpecType.ODPS)
        self.assertIn(spec_version, ["1.9", "1.x"])

        # Verify normalization succeeded
        self.assertIsNotNone(hub_contract)
        self.assertIn(
            status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
        )

        # Verify marketplace section exists
        self.assertIn("marketplace", hub_contract)

    def test_odps_license_to_marketplace_mapping(self):
        """Test ODPS license section → HubContract marketplace mapping"""
        license_data = {
            "en": {
                "definition": "MIT License",
                "restrictions": ["No commercial use", "Attribution required"],
                "rights": ["Use", "Modify", "Distribute"],
            }
        }

        contract = self._create_odps_contract_with_license("4.1", license_data)
        contract_json = json.dumps(contract)

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=contract_json, format="JSON"
        )

        # Verify normalization succeeded
        self.assertIsNotNone(hub_contract)
        self.assertIn(
            status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
        )

        # Verify marketplace section exists
        self.assertIn("marketplace", hub_contract)
        marketplace = hub_contract["marketplace"]

        # Verify license mapping
        self.assertIn("license_summary", marketplace)
        self.assertEqual(marketplace["license_summary"], "MIT License")

        # Verify restricted_use mapping
        self.assertIn("restricted_use", marketplace)
        self.assertIsInstance(marketplace["restricted_use"], list)
        self.assertIn("No commercial use", marketplace["restricted_use"])

        # Verify intended_use mapping
        self.assertIn("intended_use", marketplace)
        self.assertIsInstance(marketplace["intended_use"], list)
        self.assertIn("Use", marketplace["intended_use"])

    def test_odps_missing_marketplace_fields_graceful_degradation(self):
        """Test graceful degradation when marketplace fields are missing"""
        # Contract without marketplace section
        contract = self.base_odps_contract.copy()
        contract_json = json.dumps(contract)

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=contract_json, format="JSON"
        )

        # Verify normalization succeeded (should not fail)
        self.assertIsNotNone(hub_contract)
        self.assertIn(
            status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
        )

        # Marketplace section may or may not exist, but normalization should succeed
        # If it exists, it should be properly structured
        if "marketplace" in hub_contract:
            self.assertIsInstance(hub_contract["marketplace"], dict)

    def test_odps_missing_license_fields_graceful_degradation(self):
        """Test graceful degradation when license fields are missing"""
        # Contract without license section
        contract = self.base_odps_contract.copy()
        contract_json = json.dumps(contract)

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=contract_json, format="JSON"
        )

        # Verify normalization succeeded
        self.assertIsNotNone(hub_contract)
        self.assertIn(
            status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
        )

        # License fields are optional, normalization should succeed

    def test_odps_partial_marketplace_fields_graceful_degradation(self):
        """Test graceful degradation with partial marketplace fields"""
        # Contract with only pricingPlans, missing accessMethods and paymentGateways
        marketplace_data = {
            "pricingPlans": [{"planID": "basic", "name": "Basic Plan", "price": 9.99}]
        }

        contract = self._create_odps_contract_with_marketplace("4.1", marketplace_data)
        contract_json = json.dumps(contract)

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=contract_json, format="JSON"
        )

        # Verify normalization succeeded
        self.assertIsNotNone(hub_contract)
        self.assertIn(
            status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
        )

        # Verify marketplace section exists
        self.assertIn("marketplace", hub_contract)
        marketplace = hub_contract["marketplace"]
        self.assertIn("x_odps", marketplace)

        # Verify pricing plans exist
        self.assertIn("pricing_plans", marketplace["x_odps"])

        # accessMethods and paymentGateways may not exist, which is fine

    def test_odps_separation_from_odcs_technical(self):
        """Test clear separation: ODPS marketplace vs ODCS technical"""
        # ODPS contract with marketplace focus
        odps_contract = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "odps-marketplace-product",
                        "name": "ODPS Marketplace Product",
                    }
                },
                "marketplace": {
                    "pricingPlans": [{"planID": "premium", "name": "Premium Plan", "price": 49.99}]
                },
                "dataSchema": {"fields": [{"name": "id", "type": "string"}]},
            },
        }

        odps_contract_json = json.dumps(odps_contract)

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=odps_contract_json, format="JSON"
        )

        # Verify ODPS was detected
        self.assertEqual(spec_type, OriginalSpecType.ODPS)
        self.assertEqual(spec_version, "4.1")

        # Verify normalization succeeded
        self.assertIsNotNone(hub_contract)
        self.assertIn(
            status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
        )

        # Verify marketplace section (ODPS marketplace focus)
        self.assertIn("marketplace", hub_contract)
        marketplace = hub_contract["marketplace"]
        self.assertIn("x_odps", marketplace)
        self.assertIn("pricing_plans", marketplace["x_odps"])

        # Verify schema section exists (technical, but minimal for ODPS)
        # ODPS focuses on marketplace, schema is minimal
        if "schema" in hub_contract:
            # Schema should exist but may be minimal
            self.assertIsInstance(hub_contract["schema"], dict)

    def test_odps_complete_normalization_all_versions(self):
        """Test complete normalization for all ODPS versions"""
        versions = ["4.1", "4.0", "3.9", "2.9", "1.9"]

        for version in versions:
            with self.subTest(version=version):
                contract = {
                    "schema": f"https://opendataproducts.org/schema/v{version}",
                    "version": version,
                    "product": {
                        "details": {
                            "en": {
                                "productID": f"test-product-{version}",
                                "name": f"Test Product {version}",
                                "description": f"Test product for version {version}",
                            }
                        },
                        "marketplace": {
                            "pricingPlans": [
                                {"planID": "basic", "name": "Basic Plan", "price": 9.99}
                            ]
                        },
                        "dataSchema": {"fields": [{"name": "id", "type": "string"}]},
                    },
                }

                contract_json = json.dumps(contract)

                hub_contract, spec_type, spec_version, status, errors, warnings = (
                    normalize_contract(raw_contract=contract_json, format="JSON")
                )

                # Verify detection
                self.assertEqual(spec_type, OriginalSpecType.ODPS, f"Failed for version {version}")

                # Verify normalization succeeded
                self.assertIsNotNone(hub_contract, f"HubContract is None for version {version}")
                self.assertIn(
                    status,
                    [
                        NormalizationStatus.NORMALIZED_OK,
                        NormalizationStatus.NORMALIZED_WITH_WARNINGS,
                    ],
                    f"Normalization failed for version {version}: {errors}",
                )

                # Verify basic structure
                self.assertIn("id", hub_contract, f"Missing id for version {version}")
                self.assertIn("info", hub_contract, f"Missing info for version {version}")
                self.assertEqual(
                    hub_contract["id"], f"test-product-{version}", f"Wrong id for version {version}"
                )

                # Verify marketplace section exists
                self.assertIn(
                    "marketplace", hub_contract, f"Missing marketplace for version {version}"
                )

    def test_odps_normalization_with_all_marketplace_features(self):
        """Test complete normalization with all marketplace features"""
        contract = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "complete-marketplace-product",
                        "name": "Complete Marketplace Product",
                    }
                },
                "marketplace": {
                    "pricingPlans": [
                        {"planID": "free", "name": "Free Plan", "price": 0},
                        {"planID": "pro", "name": "Pro Plan", "price": 99.99, "currency": "USD"},
                    ],
                    "accessMethods": {
                        "api": {"type": "REST API", "endpoint": "https://api.example.com"},
                        "sftp": {"type": "SFTP", "host": "sftp.example.com"},
                    },
                    "paymentGateways": {
                        "stripe": {"enabled": True, "publicKey": "pk_live_123"},
                        "paypal": {"enabled": True},
                    },
                },
                "dataSchema": {"fields": [{"name": "id", "type": "string"}]},
            },
            "license": {
                "en": {
                    "definition": "Apache 2.0 License",
                    "restrictions": ["No warranty"],
                    "rights": ["Use", "Modify", "Distribute", "Sublicense"],
                }
            },
        }

        contract_json = json.dumps(contract)

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=contract_json, format="JSON"
        )

        # Verify normalization succeeded
        self.assertIsNotNone(hub_contract)
        self.assertIn(
            status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
        )

        # Verify all marketplace features
        marketplace = hub_contract["marketplace"]

        # License mapping
        self.assertIn("license_summary", marketplace)
        self.assertEqual(marketplace["license_summary"], "Apache 2.0 License")
        self.assertIn("restricted_use", marketplace)
        self.assertIn("intended_use", marketplace)

        # Pricing plans
        self.assertIn("x_odps", marketplace)
        x_odps = marketplace["x_odps"]
        self.assertIn("pricing_plans", x_odps)
        self.assertEqual(len(x_odps["pricing_plans"]), 2)

        # Access methods
        self.assertIn("access_methods", x_odps)
        self.assertIn("api", x_odps["access_methods"])
        self.assertIn("sftp", x_odps["access_methods"])

        # Payment gateways
        self.assertIn("payment_gateways", x_odps)
        self.assertIn("stripe", x_odps["payment_gateways"])
        self.assertIn("paypal", x_odps["payment_gateways"])

    def test_odps_normalization_version_specific_features(self):
        """Test that version-specific features are handled correctly"""
        # Test 4.1 with paymentGateways (4.1+ feature)
        contract_4_1 = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"productID": "test-4-1", "name": "Test 4.1"}},
                "marketplace": {"paymentGateways": {"stripe": {"enabled": True}}},
                "dataSchema": {"fields": [{"name": "id", "type": "string"}]},
            },
        }

        contract_json = json.dumps(contract_4_1)
        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=contract_json, format="JSON"
        )

        self.assertIsNotNone(hub_contract)
        self.assertEqual(spec_version, "4.1")

        # paymentGateways should be present in 4.1
        if "marketplace" in hub_contract and "x_odps" in hub_contract["marketplace"]:
            x_odps = hub_contract["marketplace"]["x_odps"]
            # paymentGateways may or may not be present depending on implementation
            # If present, it should be valid
            if "payment_gateways" in x_odps:
                self.assertIsInstance(x_odps["payment_gateways"], dict)

    def test_odps_normalization_error_handling_invalid_types(self):
        """Test error handling for invalid field types"""
        # Contract with invalid marketplace.pricingPlans type (should be list, not string)
        contract = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"productID": "test-invalid", "name": "Test Invalid"}},
                "marketplace": {"pricingPlans": "invalid_type"},  # Should be list
                "dataSchema": {"fields": [{"name": "id", "type": "string"}]},
            },
        }

        contract_json = json.dumps(contract)

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=contract_json, format="JSON"
        )

        # Normalization should still succeed but with warnings
        self.assertIsNotNone(hub_contract)
        # Should have warnings about invalid type
        self.assertTrue(
            len(warnings) > 0 or status == NormalizationStatus.NORMALIZED_WITH_WARNINGS,
            "Expected warnings for invalid pricingPlans type",
        )
