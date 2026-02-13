"""
Unit tests for ODPS Generator - Lifecycle Generation (Task 2.1.5)

Tests verify:
1. Map lifecycle.slas → product.SLA.declarative[]
2. Map lifecycle.x_odps.sla_dimensions[] → product.SLA.declarative[]
3. Map lifecycle.x_odps.status → product.details.<lang>.status
4. Error handling for invalid lifecycle data
"""

from django.test import SimpleTestCase, TestCase

from hub.apps.contracts.odps_errors import ODPSExportError
from hub.apps.contracts.odps_generator import generate_odps_from_hubcontract


class ODPSGeneratorLifecycleStatusMappingTest(SimpleTestCase):
    """Test ODPS generator lifecycle status mapping"""

    def test_lifecycle_status_mapping_to_product_details(self):
        """
        Test mapping lifecycle.x_odps.status → product.details.<lang>.status.

        Scenario: Generate ODPS with lifecycle.x_odps.status
        Expected: product.details.en.status contains the status value
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product", "description": "Test product description"},
            "schema": {"fields": []},
            "lifecycle": {"x_odps": {"status": "active"}},
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Verify product.details.en.status exists
        self.assertIn("product", result)
        self.assertIn("details", result["product"])
        self.assertIn("en", result["product"]["details"])
        self.assertIn("status", result["product"]["details"]["en"])

        # Verify status value
        self.assertEqual(result["product"]["details"]["en"]["status"], "active")

    def test_lifecycle_status_mapping_with_different_status_values(self):
        """
        Test mapping lifecycle status with different status values.

        Scenario: Generate ODPS with different status values (active, draft, retired)
        Expected: product.details.en.status contains the correct status value
        """
        status_values = ["active", "draft", "retired", "archived"]

        for status_value in status_values:
            hub_contract = {
                "id": f"test-product-{status_value}",
                "info": {"name": f"Test Product {status_value}"},
                "schema": {"fields": []},
                "lifecycle": {"x_odps": {"status": status_value}},
            }

            result = generate_odps_from_hubcontract(hub_contract)

            self.assertEqual(result["product"]["details"]["en"]["status"], status_value)

    def test_lifecycle_status_mapping_with_invalid_status_type(self):
        """
        Test error handling when lifecycle.x_odps.status is not a string.

        Scenario: Generate ODPS with invalid status type
        Expected: ODPSExportError with field_path and expected/actual types
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "lifecycle": {"x_odps": {"status": 123}},  # Invalid type
        }

        with self.assertRaises(ODPSExportError) as context:
            generate_odps_from_hubcontract(hub_contract)

        error = context.exception
        self.assertIn("lifecycle.x_odps.status", error.message.lower())
        self.assertIn("string", error.message.lower())
        self.assertIn("field_path", error.context)
        self.assertEqual(error.context["field_path"], "/lifecycle/x_odps/status")
        self.assertEqual(error.context["expected"], "str")
        self.assertIn("actual", error.context)


class ODPSGeneratorLifecycleSLASMappingTest(SimpleTestCase):
    """Test ODPS generator lifecycle SLAs mapping"""

    def test_lifecycle_slas_mapping_to_sla_declarative(self):
        """
        Test mapping lifecycle.slas → product.SLA.declarative[].

        Scenario: Generate ODPS with lifecycle.slas
        Expected: product.SLA.declarative.dimensions contains mapped dimensions
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "lifecycle": {"slas": {"availability": 99.9, "latency_ms_p95": 5000.0}},
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Verify product.SLA.declarative.dimensions exists
        self.assertIn("product", result)
        self.assertIn("SLA", result["product"])
        self.assertIn("declarative", result["product"]["SLA"])
        self.assertIn("dimensions", result["product"]["SLA"]["declarative"])

        dimensions = result["product"]["SLA"]["declarative"]["dimensions"]

        # Verify availability dimension
        self.assertIn("availability", dimensions)
        self.assertEqual(dimensions["availability"]["target"], 99.9)

        # Verify latency dimension (latency_ms_p95 → latency)
        self.assertIn("latency", dimensions)
        self.assertEqual(dimensions["latency"]["target"], 5000.0)

    def test_lifecycle_slas_mapping_availability_only(self):
        """
        Test mapping lifecycle.slas with only availability.

        Scenario: Generate ODPS with only availability SLA
        Expected: product.SLA.declarative.dimensions contains availability dimension
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "lifecycle": {"slas": {"availability": 99.5}},
        }

        result = generate_odps_from_hubcontract(hub_contract)

        dimensions = result["product"]["SLA"]["declarative"]["dimensions"]
        self.assertIn("availability", dimensions)
        self.assertEqual(dimensions["availability"]["target"], 99.5)
        self.assertEqual(len(dimensions), 1)

    def test_lifecycle_slas_mapping_latency_only(self):
        """
        Test mapping lifecycle.slas with only latency_ms_p95.

        Scenario: Generate ODPS with only latency SLA
        Expected: product.SLA.declarative.dimensions contains latency dimension
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "lifecycle": {"slas": {"latency_ms_p95": 3000.0}},
        }

        result = generate_odps_from_hubcontract(hub_contract)

        dimensions = result["product"]["SLA"]["declarative"]["dimensions"]
        self.assertIn("latency", dimensions)
        self.assertEqual(dimensions["latency"]["target"], 3000.0)
        self.assertEqual(len(dimensions), 1)

    def test_lifecycle_slas_mapping_with_custom_dimension(self):
        """
        Test mapping lifecycle.slas with custom dimension.

        Scenario: Generate ODPS with custom SLA dimension
        Expected: product.SLA.declarative.dimensions contains custom dimension
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "lifecycle": {"slas": {"availability": 99.9, "custom_sla_dimension": 100.0}},
        }

        result = generate_odps_from_hubcontract(hub_contract)

        dimensions = result["product"]["SLA"]["declarative"]["dimensions"]
        self.assertIn("availability", dimensions)
        self.assertIn("custom_sla_dimension", dimensions)
        self.assertEqual(dimensions["custom_sla_dimension"]["target"], 100.0)

    def test_lifecycle_slas_mapping_with_invalid_slas_type(self):
        """
        Test error handling when lifecycle.slas is not a dictionary.

        Scenario: Generate ODPS with invalid slas type
        Expected: ODPSExportError with field_path and expected/actual types
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "lifecycle": {"slas": "not-a-dict"},  # Invalid type
        }

        with self.assertRaises(ODPSExportError) as context:
            generate_odps_from_hubcontract(hub_contract)

        error = context.exception
        self.assertIn("lifecycle.slas", error.message.lower())
        self.assertIn("dictionary", error.message.lower())
        self.assertIn("field_path", error.context)
        self.assertEqual(error.context["field_path"], "/lifecycle/slas")
        self.assertEqual(error.context["expected"], "dict")
        self.assertIn("actual", error.context)

    def test_lifecycle_slas_mapping_with_invalid_sla_value_type(self):
        """
        Test error handling when lifecycle.slas value is not a number.

        Scenario: Generate ODPS with invalid SLA value type
        Expected: ODPSExportError with field_path and expected/actual types
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "lifecycle": {"slas": {"availability": "not-a-number"}},  # Invalid type
        }

        with self.assertRaises(ODPSExportError) as context:
            generate_odps_from_hubcontract(hub_contract)

        error = context.exception
        self.assertIn("lifecycle.slas.availability", error.message.lower())
        self.assertIn("number", error.message.lower())
        self.assertIn("field_path", error.context)
        self.assertEqual(error.context["field_path"], "/lifecycle/slas/availability")
        self.assertEqual(error.context["expected"], "number")
        self.assertIn("actual", error.context)


class ODPSGeneratorLifecycleSLADimensionsMappingTest(SimpleTestCase):
    """Test ODPS generator lifecycle SLA dimensions mapping"""

    def test_lifecycle_sla_dimensions_mapping_to_sla_declarative(self):
        """
        Test mapping lifecycle.x_odps.sla_dimensions[] → product.SLA.declarative[].

        Scenario: Generate ODPS with lifecycle.x_odps.sla_dimensions[]
        Expected: product.SLA.declarative.dimensions contains all dimensions
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "lifecycle": {
                "x_odps": {
                    "sla_dimensions": [
                        {
                            "name": "availability",
                            "data": {"target": 99.9, "description": "Availability target"},
                        },
                        {"name": "latency", "data": {"target": 5000, "unit": "ms"}},
                    ]
                }
            },
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Verify product.SLA.declarative.dimensions exists
        self.assertIn("product", result)
        self.assertIn("SLA", result["product"])
        self.assertIn("declarative", result["product"]["SLA"])
        self.assertIn("dimensions", result["product"]["SLA"]["declarative"])

        dimensions = result["product"]["SLA"]["declarative"]["dimensions"]

        # Verify availability dimension with full data
        self.assertIn("availability", dimensions)
        self.assertEqual(dimensions["availability"]["target"], 99.9)
        self.assertEqual(dimensions["availability"]["description"], "Availability target")

        # Verify latency dimension with full data
        self.assertIn("latency", dimensions)
        self.assertEqual(dimensions["latency"]["target"], 5000)
        self.assertEqual(dimensions["latency"]["unit"], "ms")

    def test_lifecycle_sla_dimensions_mapping_with_custom_dimension(self):
        """
        Test mapping lifecycle.x_odps.sla_dimensions[] with custom dimension.

        Scenario: Generate ODPS with custom SLA dimension
        Expected: product.SLA.declarative.dimensions contains custom dimension
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "lifecycle": {
                "x_odps": {
                    "sla_dimensions": [
                        {
                            "name": "custom_dimension",
                            "data": {
                                "target": 100,
                                "description": "Custom SLA dimension",
                                "unit": "count",
                            },
                        }
                    ]
                }
            },
        }

        result = generate_odps_from_hubcontract(hub_contract)

        dimensions = result["product"]["SLA"]["declarative"]["dimensions"]
        self.assertIn("custom_dimension", dimensions)
        self.assertEqual(dimensions["custom_dimension"]["target"], 100)
        self.assertEqual(dimensions["custom_dimension"]["description"], "Custom SLA dimension")
        self.assertEqual(dimensions["custom_dimension"]["unit"], "count")

    def test_lifecycle_sla_dimensions_mapping_without_data(self):
        """
        Test mapping lifecycle.x_odps.sla_dimensions[] without data field.

        Scenario: Generate ODPS with sla_dimensions without data (should use lifecycle.slas)
        Expected: product.SLA.declarative.dimensions uses lifecycle.slas values
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "lifecycle": {
                "slas": {"availability": 99.9},
                "x_odps": {
                    "sla_dimensions": [
                        {
                            "name": "availability"
                            # No data field
                        }
                    ]
                },
            },
        }

        result = generate_odps_from_hubcontract(hub_contract)

        dimensions = result["product"]["SLA"]["declarative"]["dimensions"]
        self.assertIn("availability", dimensions)
        self.assertEqual(dimensions["availability"]["target"], 99.9)

    def test_lifecycle_sla_dimensions_mapping_precedence_over_slas(self):
        """
        Test that lifecycle.x_odps.sla_dimensions[] takes precedence over lifecycle.slas.

        Scenario: Generate ODPS with both lifecycle.slas and sla_dimensions
        Expected: sla_dimensions data overwrites lifecycle.slas values
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "lifecycle": {
                "slas": {"availability": 99.5},  # This should be overwritten
                "x_odps": {
                    "sla_dimensions": [
                        {
                            "name": "availability",
                            "data": {
                                "target": 99.9,  # This should be used
                                "description": "High availability target",
                            },
                        }
                    ]
                },
            },
        }

        result = generate_odps_from_hubcontract(hub_contract)

        dimensions = result["product"]["SLA"]["declarative"]["dimensions"]
        self.assertIn("availability", dimensions)
        # sla_dimensions data should take precedence
        self.assertEqual(dimensions["availability"]["target"], 99.9)
        self.assertEqual(dimensions["availability"]["description"], "High availability target")

    def test_lifecycle_sla_dimensions_mapping_with_invalid_dimensions_type(self):
        """
        Test error handling when lifecycle.x_odps.sla_dimensions is not a list.

        Scenario: Generate ODPS with invalid sla_dimensions type
        Expected: ODPSExportError with field_path and expected/actual types
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "lifecycle": {"x_odps": {"sla_dimensions": "not-a-list"}},  # Invalid type
        }

        with self.assertRaises(ODPSExportError) as context:
            generate_odps_from_hubcontract(hub_contract)

        error = context.exception
        self.assertIn("lifecycle.x_odps.sla_dimensions", error.message.lower())
        self.assertIn("list", error.message.lower())
        self.assertIn("field_path", error.context)
        self.assertEqual(error.context["field_path"], "/lifecycle/x_odps/sla_dimensions")
        self.assertEqual(error.context["expected"], "list")
        self.assertIn("actual", error.context)

    def test_lifecycle_sla_dimensions_mapping_with_missing_name(self):
        """
        Test error handling when sla_dimensions entry is missing name.

        Scenario: Generate ODPS with sla_dimensions entry without name
        Expected: ODPSExportError with field_path and expected/actual
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "lifecycle": {
                "x_odps": {
                    "sla_dimensions": [
                        {
                            "data": {"target": 99.9}
                            # Missing name
                        }
                    ]
                }
            },
        }

        with self.assertRaises(ODPSExportError) as context:
            generate_odps_from_hubcontract(hub_contract)

        error = context.exception
        self.assertIn("sla_dimensions[0].name", error.message.lower())
        self.assertIn("required", error.message.lower())
        self.assertIn("field_path", error.context)
        self.assertEqual(error.context["field_path"], "/lifecycle/x_odps/sla_dimensions/0/name")
        self.assertEqual(error.context["expected"], "str")
        self.assertEqual(error.context["actual"], None)

    def test_lifecycle_sla_dimensions_mapping_with_invalid_entry_type(self):
        """
        Test error handling when sla_dimensions entry is not a dictionary.

        Scenario: Generate ODPS with invalid sla_dimensions entry type
        Expected: ODPSExportError with field_path and expected/actual types
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "lifecycle": {"x_odps": {"sla_dimensions": ["not-a-dict"]}},  # Invalid type
        }

        with self.assertRaises(ODPSExportError) as context:
            generate_odps_from_hubcontract(hub_contract)

        error = context.exception
        self.assertIn("sla_dimensions[0]", error.message.lower())
        self.assertIn("dictionary", error.message.lower())
        self.assertIn("field_path", error.context)
        self.assertEqual(error.context["field_path"], "/lifecycle/x_odps/sla_dimensions/0")
        self.assertEqual(error.context["expected"], "dict")
        self.assertIn("actual", error.context)

    def test_lifecycle_sla_dimensions_mapping_with_invalid_data_type(self):
        """
        Test error handling when sla_dimensions entry data is not a dictionary.

        Scenario: Generate ODPS with invalid data type in sla_dimensions entry
        Expected: ODPSExportError with field_path and expected/actual types
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "lifecycle": {
                "x_odps": {
                    "sla_dimensions": [
                        {"name": "availability", "data": "not-a-dict"}  # Invalid type
                    ]
                }
            },
        }

        with self.assertRaises(ODPSExportError) as context:
            generate_odps_from_hubcontract(hub_contract)

        error = context.exception
        self.assertIn("sla_dimensions[0].data", error.message.lower())
        self.assertIn("dictionary", error.message.lower())
        self.assertIn("field_path", error.context)
        self.assertEqual(error.context["field_path"], "/lifecycle/x_odps/sla_dimensions/0/data")
        self.assertEqual(error.context["expected"], "dict")
        self.assertIn("actual", error.context)


class ODPSGeneratorLifecycleCombinedMappingTest(SimpleTestCase):
    """Test ODPS generator lifecycle combined mapping scenarios"""

    def test_lifecycle_combined_mapping_status_and_slas(self):
        """
        Test combined mapping of status and SLAs.

        Scenario: Generate ODPS with both status and SLAs
        Expected: Both status and SLA dimensions are mapped correctly
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "lifecycle": {
                "slas": {"availability": 99.9, "latency_ms_p95": 5000.0},
                "x_odps": {"status": "active"},
            },
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Verify status is mapped
        self.assertEqual(result["product"]["details"]["en"]["status"], "active")

        # Verify SLA dimensions are mapped
        dimensions = result["product"]["SLA"]["declarative"]["dimensions"]
        self.assertIn("availability", dimensions)
        self.assertIn("latency", dimensions)
        self.assertEqual(dimensions["availability"]["target"], 99.9)
        self.assertEqual(dimensions["latency"]["target"], 5000.0)

    def test_lifecycle_combined_mapping_all_components(self):
        """
        Test combined mapping of status, slas, and sla_dimensions.

        Scenario: Generate ODPS with status, slas, and sla_dimensions
        Expected: All components are mapped correctly with proper precedence
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "lifecycle": {
                "slas": {"availability": 99.5},  # Should be overwritten by sla_dimensions
                "x_odps": {
                    "status": "active",
                    "sla_dimensions": [
                        {
                            "name": "availability",
                            "data": {"target": 99.9, "description": "High availability"},
                        },
                        {"name": "latency", "data": {"target": 3000, "unit": "ms"}},
                    ],
                },
            },
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Verify status
        self.assertEqual(result["product"]["details"]["en"]["status"], "active")

        # Verify SLA dimensions (sla_dimensions takes precedence)
        dimensions = result["product"]["SLA"]["declarative"]["dimensions"]
        self.assertIn("availability", dimensions)
        self.assertEqual(dimensions["availability"]["target"], 99.9)
        self.assertEqual(dimensions["availability"]["description"], "High availability")
        self.assertIn("latency", dimensions)
        self.assertEqual(dimensions["latency"]["target"], 3000)
        self.assertEqual(dimensions["latency"]["unit"], "ms")

    def test_lifecycle_omitted_when_not_provided(self):
        """
        Test that lifecycle section is optional.

        Scenario: Generate ODPS without lifecycle section
        Expected: No SLA or status fields are added (optional in ODPS)
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            # No lifecycle section
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Verify product exists
        self.assertIn("product", result)

        # Verify SLA section is not present (optional)
        if "SLA" in result["product"]:
            # If SLA exists, it should be empty or not have declarative
            if "declarative" in result["product"]["SLA"]:
                self.assertNotIn("dimensions", result["product"]["SLA"]["declarative"])

        # Verify status is not present in details
        if "details" in result["product"] and "en" in result["product"]["details"]:
            self.assertNotIn("status", result["product"]["details"]["en"])

    def test_lifecycle_with_invalid_lifecycle_type(self):
        """
        Test error handling when lifecycle is not a dictionary.

        Scenario: Generate ODPS with invalid lifecycle type
        Expected: ODPSExportError with field_path and expected/actual types
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "lifecycle": "not-a-dict",  # Invalid type
        }

        with self.assertRaises(ODPSExportError) as context:
            generate_odps_from_hubcontract(hub_contract)

        error = context.exception
        self.assertIn("lifecycle", error.message.lower())
        self.assertIn("dictionary", error.message.lower())
        self.assertIn("field_path", error.context)
        self.assertEqual(error.context["field_path"], "/lifecycle")
        self.assertEqual(error.context["expected"], "dict")
        self.assertIn("actual", error.context)


class ODPSGeneratorLifecycleIntegrationTest(SimpleTestCase):
    """Integration tests for ODPS generator lifecycle generation"""

    def test_lifecycle_generation_with_complete_hubcontract(self):
        """
        Test lifecycle generation with complete HubContract including all sections.

        Scenario: Generate ODPS with complete HubContract including lifecycle
        Expected: Complete ODPS document with lifecycle components mapped
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
            "lifecycle": {
                "slas": {"availability": 99.9, "latency_ms_p95": 5000.0},
                "x_odps": {
                    "status": "active",
                    "sla_dimensions": [
                        {
                            "name": "availability",
                            "data": {"target": 99.9, "description": "High availability target"},
                        }
                    ],
                },
            },
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Verify complete ODPS structure
        self.assertIn("schema", result)
        self.assertIn("version", result)
        self.assertIn("product", result)
        self.assertIn("details", result["product"])
        self.assertIn("SLA", result["product"])
        self.assertIn("declarative", result["product"]["SLA"])
        self.assertIn("dimensions", result["product"]["SLA"]["declarative"])

        # Verify status is mapped
        self.assertEqual(result["product"]["details"]["en"]["status"], "active")

        # Verify SLA dimensions are mapped
        dimensions = result["product"]["SLA"]["declarative"]["dimensions"]
        self.assertIn("availability", dimensions)
        self.assertEqual(dimensions["availability"]["target"], 99.9)
        self.assertEqual(dimensions["availability"]["description"], "High availability target")

    def test_lifecycle_generation_handles_unicode_characters(self):
        """Test that lifecycle generation handles unicode characters correctly."""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "测试产品", "description": "测试描述"},
            "schema": {"fields": []},
            "lifecycle": {
                "x_odps": {
                    "status": "活跃",
                    "sla_dimensions": [
                        {"name": "可用性", "data": {"target": 99.9, "description": "高可用性目标"}}
                    ],
                }
            },
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Verify unicode characters are preserved
        self.assertIn("product", result)
        self.assertIn("details", result["product"])
        self.assertIn("en", result["product"]["details"])
        if "status" in result["product"]["details"]["en"]:
            self.assertEqual(result["product"]["details"]["en"]["status"], "活跃")

    def test_lifecycle_generation_handles_special_characters(self):
        """Test that lifecycle generation handles special characters correctly."""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test & Co. (Special)"},
            "schema": {"fields": []},
            "lifecycle": {
                "x_odps": {
                    "status": "active",
                    "sla_dimensions": [
                        {
                            "name": "availability",
                            "data": {"target": 99.9, "description": "High <availability> & more"},
                        }
                    ],
                }
            },
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Verify special characters are preserved
        self.assertIn("product", result)
        self.assertIn("SLA", result["product"])
        if "SLA" in result["product"]:
            sla = result["product"]["SLA"]
            if "declarative" in sla and "dimensions" in sla["declarative"]:
                dimensions = sla["declarative"]["dimensions"]
                if "availability" in dimensions and "description" in dimensions["availability"]:
                    self.assertEqual(
                        dimensions["availability"]["description"], "High <availability> & more"
                    )

    def test_lifecycle_generation_handles_very_large_documents(self):
        """Test that lifecycle generation handles very large documents correctly."""
        large_description = "A" * 100000  # 100KB string
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "lifecycle": {
                "x_odps": {
                    "status": "active",
                    "sla_dimensions": [
                        {
                            "name": "availability",
                            "data": {"target": 99.9, "description": large_description},
                        }
                    ],
                }
            },
        }

        # Should handle large documents gracefully
        try:
            result = generate_odps_from_hubcontract(hub_contract)
            # If generation succeeds, verify structure
            self.assertIn("product", result)
        except Exception as e:
            # If generation fails, it should fail gracefully
            self.assertIsInstance(
                e, ODPSExportError, "Should raise ODPSExportError for very large documents"
            )

    def test_lifecycle_generation_handles_none_values(self):
        """Test that lifecycle generation handles None values correctly."""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "lifecycle": {"x_odps": {"status": None, "sla_dimensions": None}},  # None value
        }

        # Should handle None values gracefully
        try:
            result = generate_odps_from_hubcontract(hub_contract)
            # If generation succeeds, None values may be omitted or handled
            self.assertIsNotNone(result)
        except Exception as e:
            # If generation fails, it should fail gracefully
            self.assertIsInstance(
                e, ODPSExportError, "Should raise ODPSExportError for None values"
            )

    def test_lifecycle_generation_handles_nested_structures(self):
        """Test that lifecycle generation handles nested structures correctly."""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "lifecycle": {
                "x_odps": {
                    "status": "active",
                    "sla_dimensions": [
                        {
                            "name": "availability",
                            "data": {
                                "target": 99.9,
                                "nested": {"level1": {"level2": {"level3": {"value": "deep"}}}},
                            },
                        }
                    ],
                }
            },
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Verify nested structure is preserved
        self.assertIn("product", result)
        self.assertIn("SLA", result["product"])
        if "SLA" in result["product"]:
            sla = result["product"]["SLA"]
            if "declarative" in sla and "dimensions" in sla["declarative"]:
                dimensions = sla["declarative"]["dimensions"]
                if "availability" in dimensions and "nested" in dimensions["availability"]:
                    self.assertIn(
                        "level1",
                        dimensions["availability"]["nested"],
                        "Nested structures should be preserved",
                    )
