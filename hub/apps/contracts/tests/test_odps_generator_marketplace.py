"""
Unit tests for ODPS Generator - Marketplace Generation (Task 2.1.6)

Tests verify:
1. Map marketplace.license_summary → license.<lang>.definition
2. Map marketplace.restricted_use[] → license.<lang>.restrictions
3. Map marketplace.intended_use[] → license.<lang>.rights[]
4. Map marketplace.x_odps.pricing_plans[] → product.marketplace.pricingPlans[]
5. Map marketplace.x_odps.access_methods{} → product.marketplace.accessMethods{}
6. Map marketplace.x_odps.payment_gateways{} → product.marketplace.paymentGateways{}
7. Error handling for invalid marketplace data
"""

from django.test import SimpleTestCase

from hub.apps.contracts.odps_errors import ODPSExportError
from hub.apps.contracts.odps_generator import generate_odps_from_hubcontract


class ODPSGeneratorMarketplaceLicenseMappingTest(SimpleTestCase):
    """Test ODPS generator marketplace license mapping"""

    def test_marketplace_license_summary_mapping_to_license_definition(self):
        """
        Test mapping marketplace.license_summary → license.<lang>.definition.

        Scenario: Generate ODPS with marketplace.license_summary
        Expected: license.en.definition contains the license summary
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product", "description": "Test product description"},
            "schema": {"fields": []},
            "marketplace": {"license_summary": "MIT License"},
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Verify license.en.definition exists
        self.assertIn("license", result)
        self.assertIn("en", result["license"])
        self.assertIn("definition", result["license"]["en"])

        # Verify definition value
        self.assertEqual(result["license"]["en"]["definition"], "MIT License")

    def test_marketplace_license_summary_with_different_licenses(self):
        """
        Test mapping license_summary with different license types.

        Scenario: Generate ODPS with different license summaries
        Expected: license.en.definition contains the correct license summary
        """
        license_summaries = [
            "MIT License",
            "Apache License 2.0",
            "GPL v3",
            "Proprietary License",
            "Creative Commons Attribution 4.0",
        ]

        for license_summary in license_summaries:
            hub_contract = {
                "id": f"test-product-{license_summary[:10]}",
                "info": {"name": f"Test Product {license_summary[:10]}"},
                "schema": {"fields": []},
                "marketplace": {"license_summary": license_summary},
            }

            result = generate_odps_from_hubcontract(hub_contract)

            self.assertEqual(result["license"]["en"]["definition"], license_summary)

    def test_marketplace_license_summary_with_invalid_type(self):
        """
        Test error handling when license_summary is not a string.

        Scenario: Generate ODPS with invalid license_summary type
        Expected: ODPSExportError with field_path and expected/actual types
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "marketplace": {"license_summary": 12345},  # Invalid type
        }

        with self.assertRaises(ODPSExportError) as context:
            generate_odps_from_hubcontract(hub_contract)

        error = context.exception
        self.assertIn("marketplace.license_summary", error.message.lower())
        self.assertIn("string", error.message.lower())
        self.assertIn("field_path", error.context)
        self.assertEqual(error.context["field_path"], "/marketplace/license_summary")
        self.assertEqual(error.context["expected"], "str")
        self.assertIn("actual", error.context)

    def test_marketplace_restricted_use_mapping_to_license_restrictions(self):
        """
        Test mapping marketplace.restricted_use[] → license.<lang>.restrictions.

        Scenario: Generate ODPS with marketplace.restricted_use[]
        Expected: license.en.restrictions contains the restricted use list
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "marketplace": {"restricted_use": ["COMMERCIAL", "RESALE"]},
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Verify license.en.restrictions exists
        self.assertIn("license", result)
        self.assertIn("en", result["license"])
        self.assertIn("restrictions", result["license"]["en"])

        # Verify restrictions value
        self.assertEqual(result["license"]["en"]["restrictions"], ["COMMERCIAL", "RESALE"])

    def test_marketplace_restricted_use_with_empty_list(self):
        """
        Test mapping restricted_use with empty list.

        Scenario: Generate ODPS with empty restricted_use list
        Expected: license.en.restrictions contains empty list
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "marketplace": {"restricted_use": []},
        }

        result = generate_odps_from_hubcontract(hub_contract)

        self.assertEqual(result["license"]["en"]["restrictions"], [])

    def test_marketplace_restricted_use_with_invalid_type(self):
        """
        Test error handling when restricted_use is not a list.

        Scenario: Generate ODPS with invalid restricted_use type
        Expected: ODPSExportError with field_path and expected/actual types
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "marketplace": {"restricted_use": "not-a-list"},  # Invalid type
        }

        with self.assertRaises(ODPSExportError) as context:
            generate_odps_from_hubcontract(hub_contract)

        error = context.exception
        self.assertIn("marketplace.restricted_use", error.message.lower())
        self.assertIn("list", error.message.lower())
        self.assertIn("field_path", error.context)
        self.assertEqual(error.context["field_path"], "/marketplace/restricted_use")
        self.assertEqual(error.context["expected"], "list")
        self.assertIn("actual", error.context)

    def test_marketplace_intended_use_mapping_to_license_rights(self):
        """
        Test mapping marketplace.intended_use[] → license.<lang>.rights[].

        Scenario: Generate ODPS with marketplace.intended_use[]
        Expected: license.en.rights contains the intended use list
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "marketplace": {"intended_use": ["ANALYTICS", "RESEARCH"]},
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Verify license.en.rights exists
        self.assertIn("license", result)
        self.assertIn("en", result["license"])
        self.assertIn("rights", result["license"]["en"])

        # Verify rights value
        self.assertEqual(result["license"]["en"]["rights"], ["ANALYTICS", "RESEARCH"])

    def test_marketplace_intended_use_with_multiple_values(self):
        """
        Test mapping intended_use with multiple values.

        Scenario: Generate ODPS with multiple intended use values
        Expected: license.en.rights contains all values
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "marketplace": {"intended_use": ["ANALYTICS", "RESEARCH", "DEVELOPMENT", "TESTING"]},
        }

        result = generate_odps_from_hubcontract(hub_contract)

        self.assertEqual(
            result["license"]["en"]["rights"], ["ANALYTICS", "RESEARCH", "DEVELOPMENT", "TESTING"]
        )

    def test_marketplace_intended_use_with_invalid_type(self):
        """
        Test error handling when intended_use is not a list.

        Scenario: Generate ODPS with invalid intended_use type
        Expected: ODPSExportError with field_path and expected/actual types
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "marketplace": {"intended_use": "not-a-list"},  # Invalid type
        }

        with self.assertRaises(ODPSExportError) as context:
            generate_odps_from_hubcontract(hub_contract)

        error = context.exception
        self.assertIn("marketplace.intended_use", error.message.lower())
        self.assertIn("list", error.message.lower())
        self.assertIn("field_path", error.context)
        self.assertEqual(error.context["field_path"], "/marketplace/intended_use")
        self.assertEqual(error.context["expected"], "list")
        self.assertIn("actual", error.context)

    def test_marketplace_license_combined_mapping(self):
        """
        Test combined mapping of license_summary, restricted_use, and intended_use.

        Scenario: Generate ODPS with all license fields
        Expected: license.en contains all fields
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "marketplace": {
                "license_summary": "MIT License",
                "restricted_use": ["COMMERCIAL"],
                "intended_use": ["ANALYTICS", "RESEARCH"],
            },
        }

        result = generate_odps_from_hubcontract(hub_contract)

        license_obj = result["license"]["en"]
        self.assertEqual(license_obj["definition"], "MIT License")
        self.assertEqual(license_obj["restrictions"], ["COMMERCIAL"])
        self.assertEqual(license_obj["rights"], ["ANALYTICS", "RESEARCH"])


class ODPSGeneratorMarketplacePricingPlansMappingTest(SimpleTestCase):
    """Test ODPS generator marketplace pricing plans mapping"""

    def test_marketplace_pricing_plans_mapping_to_product_marketplace(self):
        """
        Test mapping marketplace.x_odps.pricing_plans[] → product.marketplace.pricingPlans[].

        Scenario: Generate ODPS with marketplace.x_odps.pricing_plans[]
        Expected: product.marketplace.pricingPlans contains the pricing plans array
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "marketplace": {
                "x_odps": {
                    "pricing_plans": [
                        {
                            "planID": "basic",
                            "name": "Basic Plan",
                            "price": 9.99,
                            "currency": "USD",
                            "billingPeriod": "monthly",
                        },
                        {
                            "planID": "premium",
                            "name": "Premium Plan",
                            "price": 29.99,
                            "currency": "USD",
                            "billingPeriod": "monthly",
                        },
                    ]
                }
            },
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Verify product.marketplace.pricingPlans exists
        self.assertIn("product", result)
        self.assertIn("marketplace", result["product"])
        self.assertIn("pricingPlans", result["product"]["marketplace"])

        # Verify pricingPlans value
        pricing_plans = result["product"]["marketplace"]["pricingPlans"]
        self.assertEqual(len(pricing_plans), 2)
        self.assertEqual(pricing_plans[0]["planID"], "basic")
        self.assertEqual(pricing_plans[0]["price"], 9.99)
        self.assertEqual(pricing_plans[1]["planID"], "premium")
        self.assertEqual(pricing_plans[1]["price"], 29.99)

    def test_marketplace_pricing_plans_with_single_plan(self):
        """
        Test mapping pricing_plans with single plan.

        Scenario: Generate ODPS with single pricing plan
        Expected: product.marketplace.pricingPlans contains single plan
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "marketplace": {
                "x_odps": {
                    "pricing_plans": [
                        {"planID": "free", "name": "Free Plan", "price": 0, "currency": "USD"}
                    ]
                }
            },
        }

        result = generate_odps_from_hubcontract(hub_contract)

        pricing_plans = result["product"]["marketplace"]["pricingPlans"]
        self.assertEqual(len(pricing_plans), 1)
        self.assertEqual(pricing_plans[0]["planID"], "free")
        self.assertEqual(pricing_plans[0]["price"], 0)

    def test_marketplace_pricing_plans_with_empty_list(self):
        """
        Test mapping pricing_plans with empty list.

        Scenario: Generate ODPS with empty pricing_plans list
        Expected: product.marketplace.pricingPlans contains empty list
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "marketplace": {"x_odps": {"pricing_plans": []}},
        }

        result = generate_odps_from_hubcontract(hub_contract)

        pricing_plans = result["product"]["marketplace"]["pricingPlans"]
        self.assertEqual(pricing_plans, [])

    def test_marketplace_pricing_plans_with_invalid_type(self):
        """
        Test error handling when pricing_plans is not a list.

        Scenario: Generate ODPS with invalid pricing_plans type
        Expected: ODPSExportError with field_path and expected/actual types
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "marketplace": {"x_odps": {"pricing_plans": "not-a-list"}},  # Invalid type
        }

        with self.assertRaises(ODPSExportError) as context:
            generate_odps_from_hubcontract(hub_contract)

        error = context.exception
        self.assertIn("marketplace.x_odps.pricing_plans", error.message.lower())
        self.assertIn("list", error.message.lower())
        self.assertIn("field_path", error.context)
        self.assertEqual(error.context["field_path"], "/marketplace/x_odps/pricing_plans")
        self.assertEqual(error.context["expected"], "list")
        self.assertIn("actual", error.context)


class ODPSGeneratorMarketplaceAccessMethodsMappingTest(SimpleTestCase):
    """Test ODPS generator marketplace access methods mapping"""

    def test_marketplace_access_methods_mapping_to_product_marketplace(self):
        """
        Test mapping marketplace.x_odps.access_methods{} → product.marketplace.accessMethods{}.

        Scenario: Generate ODPS with marketplace.x_odps.access_methods{}
        Expected: product.marketplace.accessMethods contains the access methods dictionary
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "marketplace": {
                "x_odps": {
                    "access_methods": {
                        "api": {
                            "endpoint": "https://api.example.com/v1/products/test-product",
                            "version": "v1",
                        },
                        "download": {
                            "url": "https://download.example.com/products/test-product",
                            "format": "zip",
                        },
                    }
                }
            },
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Verify product.marketplace.accessMethods exists
        self.assertIn("product", result)
        self.assertIn("marketplace", result["product"])
        self.assertIn("accessMethods", result["product"]["marketplace"])

        # Verify accessMethods value
        access_methods = result["product"]["marketplace"]["accessMethods"]
        self.assertIn("api", access_methods)
        self.assertIn("download", access_methods)
        self.assertEqual(
            access_methods["api"]["endpoint"], "https://api.example.com/v1/products/test-product"
        )
        self.assertEqual(access_methods["download"]["format"], "zip")

    def test_marketplace_access_methods_with_single_method(self):
        """
        Test mapping access_methods with single method.

        Scenario: Generate ODPS with single access method
        Expected: product.marketplace.accessMethods contains single method
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "marketplace": {
                "x_odps": {
                    "access_methods": {
                        "api": {"endpoint": "https://api.example.com/v1/products/test-product"}
                    }
                }
            },
        }

        result = generate_odps_from_hubcontract(hub_contract)

        access_methods = result["product"]["marketplace"]["accessMethods"]
        self.assertIn("api", access_methods)
        self.assertEqual(len(access_methods), 1)

    def test_marketplace_access_methods_with_empty_dict(self):
        """
        Test mapping access_methods with empty dictionary.

        Scenario: Generate ODPS with empty access_methods dict
        Expected: product.marketplace.accessMethods contains empty dict
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "marketplace": {"x_odps": {"access_methods": {}}},
        }

        result = generate_odps_from_hubcontract(hub_contract)

        access_methods = result["product"]["marketplace"]["accessMethods"]
        self.assertEqual(access_methods, {})

    def test_marketplace_access_methods_with_invalid_type(self):
        """
        Test error handling when access_methods is not a dictionary.

        Scenario: Generate ODPS with invalid access_methods type
        Expected: ODPSExportError with field_path and expected/actual types
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "marketplace": {"x_odps": {"access_methods": "not-a-dict"}},  # Invalid type
        }

        with self.assertRaises(ODPSExportError) as context:
            generate_odps_from_hubcontract(hub_contract)

        error = context.exception
        self.assertIn("marketplace.x_odps.access_methods", error.message.lower())
        self.assertIn("dictionary", error.message.lower())
        self.assertIn("field_path", error.context)
        self.assertEqual(error.context["field_path"], "/marketplace/x_odps/access_methods")
        self.assertEqual(error.context["expected"], "dict")
        self.assertIn("actual", error.context)


class ODPSGeneratorMarketplacePaymentGatewaysMappingTest(SimpleTestCase):
    """Test ODPS generator marketplace payment gateways mapping"""

    def test_marketplace_payment_gateways_mapping_to_product_marketplace_4_1(self):
        """
        Test mapping marketplace.x_odps.payment_gateways{} → product.marketplace.paymentGateways{} (ODPS 4.1).

        Scenario: Generate ODPS 4.1 with marketplace.x_odps.payment_gateways{}
        Expected: product.marketplace.paymentGateways contains the payment gateways dictionary
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "marketplace": {
                "x_odps": {
                    "payment_gateways": {
                        "stripe": {"enabled": True, "publicKey": "pk_test_example"},
                        "paypal": {"enabled": True},
                    }
                }
            },
        }

        result = generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        # Verify product.marketplace.paymentGateways exists (ODPS 4.1+)
        self.assertIn("product", result)
        self.assertIn("marketplace", result["product"])
        self.assertIn("paymentGateways", result["product"]["marketplace"])

        # Verify paymentGateways value
        payment_gateways = result["product"]["marketplace"]["paymentGateways"]
        self.assertIn("stripe", payment_gateways)
        self.assertIn("paypal", payment_gateways)
        self.assertEqual(payment_gateways["stripe"]["enabled"], True)
        self.assertEqual(payment_gateways["stripe"]["publicKey"], "pk_test_example")

    def test_marketplace_payment_gateways_not_included_in_older_versions(self):
        """
        Test that payment_gateways are not included in ODPS versions < 4.1.

        Scenario: Generate ODPS 4.0 with payment_gateways
        Expected: product.marketplace.paymentGateways is not present
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "marketplace": {"x_odps": {"payment_gateways": {"stripe": {"enabled": True}}}},
        }

        result = generate_odps_from_hubcontract(hub_contract, target_version="4.0")

        # Verify paymentGateways is not present in ODPS 4.0
        if "marketplace" in result["product"]:
            self.assertNotIn("paymentGateways", result["product"]["marketplace"])

    def test_marketplace_payment_gateways_with_single_gateway(self):
        """
        Test mapping payment_gateways with single gateway.

        Scenario: Generate ODPS 4.1 with single payment gateway
        Expected: product.marketplace.paymentGateways contains single gateway
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "marketplace": {
                "x_odps": {
                    "payment_gateways": {
                        "stripe": {"enabled": True, "publicKey": "pk_live_example"}
                    }
                }
            },
        }

        result = generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        payment_gateways = result["product"]["marketplace"]["paymentGateways"]
        self.assertIn("stripe", payment_gateways)
        self.assertEqual(len(payment_gateways), 1)

    def test_marketplace_payment_gateways_with_invalid_type(self):
        """
        Test error handling when payment_gateways is not a dictionary.

        Scenario: Generate ODPS 4.1 with invalid payment_gateways type
        Expected: ODPSExportError with field_path and expected/actual types
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "marketplace": {"x_odps": {"payment_gateways": "not-a-dict"}},  # Invalid type
        }

        with self.assertRaises(ODPSExportError) as context:
            generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        error = context.exception
        self.assertIn("marketplace.x_odps.payment_gateways", error.message.lower())
        self.assertIn("dictionary", error.message.lower())
        self.assertIn("field_path", error.context)
        self.assertEqual(error.context["field_path"], "/marketplace/x_odps/payment_gateways")
        self.assertEqual(error.context["expected"], "dict")
        self.assertIn("actual", error.context)


class ODPSGeneratorMarketplaceCombinedMappingTest(SimpleTestCase):
    """Test ODPS generator marketplace combined mapping scenarios"""

    def test_marketplace_combined_mapping_all_components(self):
        """
        Test combined mapping of all marketplace components.

        Scenario: Generate ODPS with all marketplace components
        Expected: All components are mapped correctly
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "marketplace": {
                "license_summary": "MIT License",
                "restricted_use": ["COMMERCIAL"],
                "intended_use": ["ANALYTICS", "RESEARCH"],
                "x_odps": {
                    "pricing_plans": [
                        {"planID": "basic", "name": "Basic Plan", "price": 9.99, "currency": "USD"}
                    ],
                    "access_methods": {
                        "api": {"endpoint": "https://api.example.com/v1/products/test-product"}
                    },
                    "payment_gateways": {"stripe": {"enabled": True}},
                },
            },
        }

        result = generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        # Verify license mapping
        self.assertIn("license", result)
        self.assertEqual(result["license"]["en"]["definition"], "MIT License")
        self.assertEqual(result["license"]["en"]["restrictions"], ["COMMERCIAL"])
        self.assertEqual(result["license"]["en"]["rights"], ["ANALYTICS", "RESEARCH"])

        # Verify marketplace mapping
        marketplace = result["product"]["marketplace"]
        self.assertIn("pricingPlans", marketplace)
        self.assertIn("accessMethods", marketplace)
        self.assertIn("paymentGateways", marketplace)

        self.assertEqual(len(marketplace["pricingPlans"]), 1)
        self.assertIn("api", marketplace["accessMethods"])
        self.assertIn("stripe", marketplace["paymentGateways"])

    def test_marketplace_omitted_when_not_provided(self):
        """
        Test that marketplace section is optional.

        Scenario: Generate ODPS without marketplace section
        Expected: No marketplace or license fields are added (optional in ODPS)
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            # No marketplace section
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Verify product exists
        self.assertIn("product", result)

        # Verify marketplace section is not present when not provided.
        self.assertNotIn(
            "marketplace",
            result["product"],
            "Marketplace section must be absent when no marketplace data is provided",
        )

        # Verify license is not present (optional)
        self.assertNotIn("license", result)

    def test_marketplace_with_invalid_marketplace_type(self):
        """
        Test error handling when marketplace is not a dictionary.

        Scenario: Generate ODPS with invalid marketplace type
        Expected: ODPSExportError with field_path and expected/actual types
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "marketplace": "not-a-dict",  # Invalid type
        }

        with self.assertRaises(ODPSExportError) as context:
            generate_odps_from_hubcontract(hub_contract)

        error = context.exception
        self.assertIn("marketplace", error.message.lower())
        self.assertIn("dictionary", error.message.lower())
        self.assertIn("field_path", error.context)
        self.assertEqual(error.context["field_path"], "/marketplace")
        self.assertEqual(error.context["expected"], "dict")
        self.assertIn("actual", error.context)


class ODPSGeneratorMarketplaceIntegrationTest(SimpleTestCase):
    """Integration tests for ODPS generator marketplace generation"""

    def test_marketplace_generation_with_complete_hubcontract(self):
        """
        Test marketplace generation with complete HubContract including all sections.

        Scenario: Generate ODPS with complete HubContract including marketplace
        Expected: Complete ODPS document with all marketplace components mapped
        """
        hub_contract = {
            "id": "complete-product",
            "info": {
                "name": "Complete Product",
                "description": "Complete product description",
                "version": "1.0.0",
                "tags": ["data", "analytics"],
                "owners": [{"name": "Data Team", "email": "data@example.com"}],
            },
            "schema": {
                "fields": [
                    {"name": "id", "data_type": "string"},
                    {"name": "name", "data_type": "string"},
                ]
            },
            "marketplace": {
                "license_summary": "MIT License",
                "restricted_use": ["COMMERCIAL"],
                "intended_use": ["ANALYTICS", "RESEARCH"],
                "x_odps": {
                    "pricing_plans": [
                        {
                            "planID": "basic",
                            "name": "Basic Plan",
                            "price": 9.99,
                            "currency": "USD",
                            "billingPeriod": "monthly",
                        }
                    ],
                    "access_methods": {
                        "api": {
                            "endpoint": "https://api.example.com/v1/products/complete-product",
                            "version": "v1",
                        }
                    },
                    "payment_gateways": {
                        "stripe": {"enabled": True, "publicKey": "pk_test_example"}
                    },
                },
            },
        }

        result = generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        # Verify complete ODPS structure
        self.assertIn("schema", result)
        self.assertIn("version", result)
        self.assertIn("product", result)
        self.assertIn("marketplace", result["product"])
        self.assertIn("license", result)

        # Verify license mapping
        license_obj = result["license"]["en"]
        self.assertEqual(license_obj["definition"], "MIT License")
        self.assertEqual(license_obj["restrictions"], ["COMMERCIAL"])
        self.assertEqual(license_obj["rights"], ["ANALYTICS", "RESEARCH"])

        # Verify marketplace mapping
        marketplace = result["product"]["marketplace"]
        self.assertIn("pricingPlans", marketplace)
        self.assertIn("accessMethods", marketplace)
        self.assertIn("paymentGateways", marketplace)

        self.assertEqual(len(marketplace["pricingPlans"]), 1)
        self.assertEqual(marketplace["pricingPlans"][0]["planID"], "basic")
        self.assertIn("api", marketplace["accessMethods"])
        self.assertIn("stripe", marketplace["paymentGateways"])

    def test_marketplace_generation_handles_unicode_characters(self):
        """Test that marketplace generation handles unicode characters correctly."""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "测试产品", "description": "测试描述"},
            "schema": {"fields": []},
            "marketplace": {
                "license_summary": "MIT许可证",
                "restricted_use": ["商业用途"],
                "intended_use": ["分析", "研究"],
            },
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Verify unicode characters are preserved
        self.assertIn("license", result)
        self.assertIn("en", result["license"])
        self.assertEqual(result["license"]["en"]["definition"], "MIT许可证")
        self.assertEqual(result["license"]["en"]["restrictions"], ["商业用途"])
        self.assertEqual(result["license"]["en"]["rights"], ["分析", "研究"])

    def test_marketplace_generation_handles_special_characters(self):
        """Test that marketplace generation handles special characters correctly."""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test & Co. (Special)"},
            "schema": {"fields": []},
            "marketplace": {
                "license_summary": "License <>&\"'",
                "restricted_use": ["Use & Co."],
                "intended_use": ["Test <>&\"'"],
            },
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Verify special characters are preserved
        self.assertIn("license", result)
        self.assertIn("en", result["license"])
        self.assertEqual(result["license"]["en"]["definition"], "License <>&\"'")
        self.assertEqual(result["license"]["en"]["restrictions"], ["Use & Co."])
        self.assertEqual(result["license"]["en"]["rights"], ["Test <>&\"'"])

    def test_marketplace_generation_handles_very_large_documents(self):
        """Test that marketplace generation handles very large documents correctly."""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "marketplace": {
                "license_summary": "A" * 100000,  # 100KB string
                "restricted_use": ["A" * 10000] * 10,  # Large list
                "intended_use": ["B" * 10000] * 10,
            },
        }

        # Valid data (large license text) must succeed — must include license structure
        result = generate_odps_from_hubcontract(hub_contract)
        self.assertIn("license", result)
        self.assertIn("en", result["license"])

    def test_marketplace_generation_handles_none_values(self):
        """Test that marketplace generation handles None values correctly."""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "marketplace": {
                "license_summary": None,  # None value
                "restricted_use": None,
                "intended_use": None,
            },
        }

        # Should handle None values gracefully
        result = generate_odps_from_hubcontract(hub_contract)
        self.assertIsNotNone(result)
        self.assertIn("product", result)

    def test_marketplace_generation_handles_nested_structures(self):
        """Test that marketplace generation handles nested structures correctly."""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "marketplace": {
                "license_summary": "MIT License",
                "x_odps": {
                    "pricing_plans": [
                        {
                            "planID": "basic",
                            "nested": {"level1": {"level2": {"level3": {"value": "deep"}}}},
                        }
                    ]
                },
            },
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Verify nested structure is preserved
        self.assertIn("product", result)
        self.assertIn("marketplace", result["product"])
        self.assertIn("pricingPlans", result["product"]["marketplace"])
        self.assertGreater(
            len(result["product"]["marketplace"]["pricingPlans"]),
            0,
            "pricingPlans must not be empty for nested structure test",
        )
        plan = result["product"]["marketplace"]["pricingPlans"][0]
        self.assertIn("nested", plan, "Nested data must be preserved in pricing plan")
        self.assertIn("level1", plan["nested"], "Nested structures should be preserved")
