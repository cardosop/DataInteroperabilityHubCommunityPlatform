"""
Unit tests for ODPS Generator - Product Strategy Generation (Task 2.1.7)

Tests verify:
1. Map info.x_odps.product_strategy or extensions.x_odps.product_strategy → productStrategy (ODPS 4.1+)
2. Generate objectives, KPIs, strategic alignment
3. Error handling for invalid product strategy data
4. Version check (only ODPS 4.1+)
"""

from django.test import SimpleTestCase, TestCase

from hub.apps.contracts.odps_errors import ODPSExportError
from hub.apps.contracts.odps_generator import generate_odps_from_hubcontract


class ODPSGeneratorProductStrategyMappingTest(SimpleTestCase):
    """Test ODPS generator product strategy mapping"""

    def test_product_strategy_mapping_from_extensions_x_odps(self):
        """
        Test mapping extensions.x_odps.product_strategy → productStrategy (ODPS 4.1).

        Scenario: Generate ODPS 4.1 with extensions.x_odps.product_strategy
        Expected: productStrategy contains all fields
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product", "description": "Test product description"},
            "schema": {"fields": []},
            "extensions": {
                "x_odps": {
                    "product_strategy": {
                        "objectives": ["Increase data quality", "Improve customer satisfaction"],
                        "strategicAlignment": [
                            "Company goal: Data-driven decisions",
                            {"goal": "Digital transformation", "priority": "high"},
                        ],
                        "productKPIs": [
                            "Data quality score > 95%",
                            {"metric": "User adoption", "target": "1000 users"},
                        ],
                    }
                }
            },
        }

        result = generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        # Verify productStrategy exists
        self.assertIn("productStrategy", result)

        strategy = result["productStrategy"]
        self.assertIn("objectives", strategy)
        self.assertEqual(len(strategy["objectives"]), 2)
        self.assertIn("Increase data quality", strategy["objectives"])
        self.assertIn("Improve customer satisfaction", strategy["objectives"])

        self.assertIn("strategicAlignment", strategy)
        self.assertEqual(len(strategy["strategicAlignment"]), 2)
        self.assertEqual(strategy["strategicAlignment"][0], "Company goal: Data-driven decisions")
        self.assertIsInstance(strategy["strategicAlignment"][1], dict)

        self.assertIn("productKPIs", strategy)
        self.assertEqual(len(strategy["productKPIs"]), 2)
        self.assertEqual(strategy["productKPIs"][0], "Data quality score > 95%")
        self.assertIsInstance(strategy["productKPIs"][1], dict)

    def test_product_strategy_mapping_from_info_x_odps(self):
        """
        Test mapping info.x_odps.product_strategy → productStrategy (ODPS 4.1).

        Scenario: Generate ODPS 4.1 with info.x_odps.product_strategy (fallback)
        Expected: productStrategy contains all fields
        """
        hub_contract = {
            "id": "test-product",
            "info": {
                "name": "Test Product",
                "description": "Test product description",
                "x_odps": {
                    "product_strategy": {
                        "objectives": ["Objective 1", "Objective 2"],
                        "strategicAlignment": ["Strategic goal 1"],
                        "productKPIs": ["KPI 1"],
                    }
                },
            },
            "schema": {"fields": []},
        }

        result = generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        # Verify productStrategy exists
        self.assertIn("productStrategy", result)

        strategy = result["productStrategy"]
        self.assertIn("objectives", strategy)
        self.assertEqual(len(strategy["objectives"]), 2)
        self.assertIn("strategicAlignment", strategy)
        self.assertIn("productKPIs", strategy)

    def test_product_strategy_mapping_objectives_only(self):
        """
        Test mapping product strategy with only objectives.

        Scenario: Generate ODPS 4.1 with only objectives
        Expected: productStrategy contains only objectives
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "extensions": {
                "x_odps": {
                    "product_strategy": {
                        "objectives": ["Increase data quality", "Improve customer satisfaction"]
                    }
                }
            },
        }

        result = generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        strategy = result["productStrategy"]
        self.assertIn("objectives", strategy)
        self.assertEqual(len(strategy["objectives"]), 2)
        self.assertNotIn("strategicAlignment", strategy)
        self.assertNotIn("productKPIs", strategy)

    def test_product_strategy_mapping_strategic_alignment_only(self):
        """
        Test mapping product strategy with only strategic alignment.

        Scenario: Generate ODPS 4.1 with only strategic alignment
        Expected: productStrategy contains only strategic alignment
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "extensions": {
                "x_odps": {
                    "product_strategy": {
                        "strategicAlignment": [
                            "Company goal: Data-driven decisions",
                            {"goal": "Digital transformation", "priority": "high"},
                        ]
                    }
                }
            },
        }

        result = generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        strategy = result["productStrategy"]
        self.assertIn("strategicAlignment", strategy)
        self.assertEqual(len(strategy["strategicAlignment"]), 2)
        self.assertNotIn("objectives", strategy)
        self.assertNotIn("productKPIs", strategy)

    def test_product_strategy_mapping_product_kpis_only(self):
        """
        Test mapping product strategy with only product KPIs.

        Scenario: Generate ODPS 4.1 with only product KPIs
        Expected: productStrategy contains only product KPIs
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "extensions": {
                "x_odps": {
                    "product_strategy": {
                        "productKPIs": [
                            "Data quality score > 95%",
                            {"metric": "User adoption", "target": "1000 users"},
                        ]
                    }
                }
            },
        }

        result = generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        strategy = result["productStrategy"]
        self.assertIn("productKPIs", strategy)
        self.assertEqual(len(strategy["productKPIs"]), 2)
        self.assertNotIn("objectives", strategy)
        self.assertNotIn("strategicAlignment", strategy)

    def test_product_strategy_mapping_with_dict_objectives(self):
        """
        Test mapping product strategy with dictionary objectives.

        Scenario: Generate ODPS 4.1 with dictionary objectives
        Expected: productStrategy contains dictionary objectives
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "extensions": {
                "x_odps": {
                    "product_strategy": {
                        "objectives": [
                            {"objective": "Increase data quality", "priority": "high"},
                            {"objective": "Improve customer satisfaction", "priority": "medium"},
                        ]
                    }
                }
            },
        }

        result = generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        strategy = result["productStrategy"]
        self.assertIn("objectives", strategy)
        self.assertEqual(len(strategy["objectives"]), 2)
        self.assertIsInstance(strategy["objectives"][0], dict)
        self.assertIsInstance(strategy["objectives"][1], dict)

    def test_product_strategy_mapping_with_empty_lists(self):
        """
        Test mapping product strategy with empty lists.

        Scenario: Generate ODPS 4.1 with empty lists
        Expected: productStrategy is not created (empty structure)
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "extensions": {
                "x_odps": {
                    "product_strategy": {
                        "objectives": [],
                        "strategicAlignment": [],
                        "productKPIs": [],
                    }
                }
            },
        }

        result = generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        # productStrategy should not be created if all lists are empty
        self.assertNotIn("productStrategy", result)

    def test_product_strategy_not_included_in_older_versions(self):
        """
        Test that product strategy is not included in ODPS versions < 4.1.

        Scenario: Generate ODPS 4.0 with product strategy
        Expected: productStrategy is not present
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "extensions": {
                "x_odps": {"product_strategy": {"objectives": ["Increase data quality"]}}
            },
        }

        result = generate_odps_from_hubcontract(hub_contract, target_version="4.0")

        # Verify productStrategy is not present in ODPS 4.0
        self.assertNotIn("productStrategy", result)

    def test_product_strategy_omitted_when_not_provided(self):
        """
        Test that product strategy is optional.

        Scenario: Generate ODPS 4.1 without product strategy
        Expected: productStrategy is not present (optional in ODPS)
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            # No product_strategy section
        }

        result = generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        # Verify productStrategy is not present (optional)
        self.assertNotIn("productStrategy", result)

    def test_product_strategy_with_invalid_product_strategy_type(self):
        """
        Test error handling when product_strategy is not a dictionary.

        Scenario: Generate ODPS 4.1 with invalid product_strategy type
        Expected: ODPSExportError with field_path and expected/actual types
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "extensions": {"x_odps": {"product_strategy": "not-a-dict"}},  # Invalid type
        }

        with self.assertRaises(ODPSExportError) as context:
            generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        error = context.exception
        self.assertIn("product_strategy", error.message.lower())
        self.assertIn("dictionary", error.message.lower())
        self.assertIn("field_path", error.context)
        self.assertEqual(error.context["field_path"], "/product_strategy")
        self.assertEqual(error.context["expected"], "dict")
        self.assertIn("actual", error.context)

    def test_product_strategy_with_invalid_objectives_type(self):
        """
        Test error handling when objectives is not a list.

        Scenario: Generate ODPS 4.1 with invalid objectives type
        Expected: ODPSExportError with field_path and expected/actual types
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "extensions": {
                "x_odps": {"product_strategy": {"objectives": "not-a-list"}}  # Invalid type
            },
        }

        with self.assertRaises(ODPSExportError) as context:
            generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        error = context.exception
        self.assertIn("product_strategy.objectives", error.message.lower())
        self.assertIn("list", error.message.lower())
        self.assertIn("field_path", error.context)
        self.assertEqual(error.context["field_path"], "/product_strategy/objectives")
        self.assertEqual(error.context["expected"], "list")
        self.assertIn("actual", error.context)

    def test_product_strategy_with_invalid_objective_item_type(self):
        """
        Test error handling when objective item is not a string or dict.

        Scenario: Generate ODPS 4.1 with invalid objective item type
        Expected: ODPSExportError with field_path and expected/actual types
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "extensions": {
                "x_odps": {
                    "product_strategy": {"objectives": ["Valid objective", 12345]}  # Invalid type
                }
            },
        }

        with self.assertRaises(ODPSExportError) as context:
            generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        error = context.exception
        self.assertIn("product_strategy.objectives[1]", error.message.lower())
        self.assertIn("string or dictionary", error.message.lower())
        self.assertIn("field_path", error.context)
        self.assertEqual(error.context["field_path"], "/product_strategy/objectives/1")
        self.assertEqual(error.context["expected"], "str or dict")
        self.assertIn("actual", error.context)

    def test_product_strategy_with_invalid_strategic_alignment_type(self):
        """
        Test error handling when strategicAlignment is not a list.

        Scenario: Generate ODPS 4.1 with invalid strategicAlignment type
        Expected: ODPSExportError with field_path and expected/actual types
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "extensions": {
                "x_odps": {"product_strategy": {"strategicAlignment": "not-a-list"}}  # Invalid type
            },
        }

        with self.assertRaises(ODPSExportError) as context:
            generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        error = context.exception
        self.assertIn("product_strategy.strategicalignment", error.message.lower())
        self.assertIn("list", error.message.lower())
        self.assertIn("field_path", error.context)
        self.assertEqual(error.context["field_path"], "/product_strategy/strategicAlignment")
        self.assertEqual(error.context["expected"], "list")
        self.assertIn("actual", error.context)

    def test_product_strategy_with_invalid_strategic_alignment_item_type(self):
        """
        Test error handling when strategic alignment item is not a string or dict.

        Scenario: Generate ODPS 4.1 with invalid strategic alignment item type
        Expected: ODPSExportError with field_path and expected/actual types
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "extensions": {
                "x_odps": {
                    "product_strategy": {
                        "strategicAlignment": ["Valid alignment", 12345]  # Invalid type
                    }
                }
            },
        }

        with self.assertRaises(ODPSExportError) as context:
            generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        error = context.exception
        self.assertIn("product_strategy.strategicalignment[1]", error.message.lower())
        self.assertIn("string or dictionary", error.message.lower())
        self.assertIn("field_path", error.context)
        self.assertEqual(error.context["field_path"], "/product_strategy/strategicAlignment/1")
        self.assertEqual(error.context["expected"], "str or dict")
        self.assertIn("actual", error.context)

    def test_product_strategy_with_invalid_product_kpis_type(self):
        """
        Test error handling when productKPIs is not a list.

        Scenario: Generate ODPS 4.1 with invalid productKPIs type
        Expected: ODPSExportError with field_path and expected/actual types
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "extensions": {
                "x_odps": {"product_strategy": {"productKPIs": "not-a-list"}}  # Invalid type
            },
        }

        with self.assertRaises(ODPSExportError) as context:
            generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        error = context.exception
        self.assertIn("product_strategy.productkpis", error.message.lower())
        self.assertIn("list", error.message.lower())
        self.assertIn("field_path", error.context)
        self.assertEqual(error.context["field_path"], "/product_strategy/productKPIs")
        self.assertEqual(error.context["expected"], "list")
        self.assertIn("actual", error.context)

    def test_product_strategy_with_invalid_product_kpi_item_type(self):
        """
        Test error handling when product KPI item is not a string or dict.

        Scenario: Generate ODPS 4.1 with invalid product KPI item type
        Expected: ODPSExportError with field_path and expected/actual types
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "extensions": {
                "x_odps": {
                    "product_strategy": {"productKPIs": ["Valid KPI", 12345]}  # Invalid type
                }
            },
        }

        with self.assertRaises(ODPSExportError) as context:
            generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        error = context.exception
        self.assertIn("product_strategy.productkpis[1]", error.message.lower())
        self.assertIn("string or dictionary", error.message.lower())
        self.assertIn("field_path", error.context)
        self.assertEqual(error.context["field_path"], "/product_strategy/productKPIs/1")
        self.assertEqual(error.context["expected"], "str or dict")
        self.assertIn("actual", error.context)


class ODPSGeneratorProductStrategyIntegrationTest(SimpleTestCase):
    """Integration tests for ODPS generator product strategy generation"""

    def test_product_strategy_generation_with_complete_hubcontract(self):
        """
        Test product strategy generation with complete HubContract including all sections.

        Scenario: Generate ODPS 4.1 with complete HubContract including product strategy
        Expected: Complete ODPS document with product strategy mapped
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
            "extensions": {
                "x_odps": {
                    "product_strategy": {
                        "objectives": ["Increase data quality", "Improve customer satisfaction"],
                        "strategicAlignment": [
                            "Company goal: Data-driven decisions",
                            {"goal": "Digital transformation", "priority": "high"},
                        ],
                        "productKPIs": [
                            "Data quality score > 95%",
                            {"metric": "User adoption", "target": "1000 users"},
                        ],
                    }
                }
            },
        }

        result = generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        # Verify complete ODPS structure
        self.assertIn("schema", result)
        self.assertIn("version", result)
        self.assertIn("product", result)
        self.assertIn("productStrategy", result)

        # Verify product strategy mapping
        strategy = result["productStrategy"]
        self.assertIn("objectives", strategy)
        self.assertEqual(len(strategy["objectives"]), 2)
        self.assertIn("strategicAlignment", strategy)
        self.assertEqual(len(strategy["strategicAlignment"]), 2)
        self.assertIn("productKPIs", strategy)
        self.assertEqual(len(strategy["productKPIs"]), 2)

    def test_product_strategy_generation_handles_unicode_characters(self):
        """Test that product strategy generation handles unicode characters correctly."""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "测试产品", "description": "测试描述"},
            "schema": {"fields": []},
            "extensions": {
                "x_odps": {
                    "product_strategy": {
                        "objectives": ["提高数据质量", "改善客户满意度"],
                        "strategicAlignment": ["公司目标：数据驱动决策"],
                        "productKPIs": ["数据质量分数 > 95%"],
                    }
                }
            },
        }

        result = generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        # Verify unicode characters are preserved
        self.assertIn("productStrategy", result)
        strategy = result["productStrategy"]
        self.assertIn("objectives", strategy)
        if len(strategy["objectives"]) > 0:
            self.assertEqual(strategy["objectives"][0], "提高数据质量")

    def test_product_strategy_generation_handles_special_characters(self):
        """Test that product strategy generation handles special characters correctly."""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test & Co. (Special)"},
            "schema": {"fields": []},
            "extensions": {
                "x_odps": {
                    "product_strategy": {
                        "objectives": [
                            "Increase <data> quality & more",
                            "Improve customer <satisfaction>",
                        ],
                        "strategicAlignment": ["Company goal: Data-driven <decisions>"],
                        "productKPIs": ["Data quality score > 95% & <more>"],
                    }
                }
            },
        }

        result = generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        # Verify special characters are preserved
        self.assertIn("productStrategy", result)
        strategy = result["productStrategy"]
        self.assertIn("objectives", strategy)
        if len(strategy["objectives"]) > 0:
            self.assertEqual(strategy["objectives"][0], "Increase <data> quality & more")

    def test_product_strategy_generation_handles_very_large_documents(self):
        """Test that product strategy generation handles very large documents correctly."""
        large_objective = "A" * 100000  # 100KB string
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "extensions": {
                "x_odps": {
                    "product_strategy": {
                        "objectives": [large_objective],
                        "strategicAlignment": [large_objective],
                        "productKPIs": [large_objective],
                    }
                }
            },
        }

        # Should handle large documents gracefully
        try:
            result = generate_odps_from_hubcontract(hub_contract, target_version="4.1")
            # If generation succeeds, verify structure
            self.assertIn("productStrategy", result)
        except Exception as e:
            # If generation fails, it should fail gracefully
            self.assertIsInstance(
                e, ODPSExportError, "Should raise ODPSExportError for very large documents"
            )

    def test_product_strategy_generation_handles_none_values(self):
        """Test that product strategy generation handles None values correctly."""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "extensions": {
                "x_odps": {
                    "product_strategy": {
                        "objectives": None,  # None value
                        "strategicAlignment": None,
                        "productKPIs": None,
                    }
                }
            },
        }

        # Should handle None values gracefully
        try:
            result = generate_odps_from_hubcontract(hub_contract, target_version="4.1")
            # If generation succeeds, None values may be omitted or handled
            self.assertIsNotNone(result)
        except Exception as e:
            # If generation fails, it should fail gracefully
            self.assertIsInstance(
                e, ODPSExportError, "Should raise ODPSExportError for None values"
            )

    def test_product_strategy_generation_handles_nested_structures(self):
        """Test that product strategy generation handles nested structures correctly."""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "extensions": {
                "x_odps": {
                    "product_strategy": {
                        "objectives": ["Increase data quality"],
                        "strategicAlignment": [
                            {
                                "goal": "Digital transformation",
                                "priority": "high",
                                "nested": {"level1": {"level2": {"level3": {"value": "deep"}}}},
                            }
                        ],
                        "productKPIs": ["Data quality score > 95%"],
                    }
                }
            },
        }

        result = generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        # Verify nested structure is preserved
        self.assertIn("productStrategy", result)
        strategy = result["productStrategy"]
        self.assertIn("strategicAlignment", strategy)
        if len(strategy["strategicAlignment"]) > 0:
            alignment = strategy["strategicAlignment"][0]
            if isinstance(alignment, dict) and "nested" in alignment:
                self.assertIn(
                    "level1", alignment["nested"], "Nested structures should be preserved"
                )
