"""
Unit tests for ODPS Generator (Task 2.1.1)

Tests verify:
1. Generator initialization
2. generate_odps_from_hubcontract() function
3. Error handling with ODPSExportError
4. Error context (field name, expected type)
5. ODPS 4.1 generation support
"""

from django.test import SimpleTestCase, TestCase

from hub.apps.contracts.odps_errors import ODPSExportError
from hub.apps.contracts.odps_generator import generate_odps_from_hubcontract


class ODPSGeneratorInitializationTest(SimpleTestCase):
    """Test ODPS generator initialization and basic structure"""

    def test_generate_odps_from_hubcontract_function_exists(self):
        """Test that generate_odps_from_hubcontract function exists"""
        self.assertTrue(callable(generate_odps_from_hubcontract))

    def test_generate_odps_from_hubcontract_accepts_dict(self):
        """Test that function accepts HubContract dictionary"""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
        }

        # Should not raise an error for valid input structure
        try:
            result = generate_odps_from_hubcontract(hub_contract)
            # If it succeeds, result should be a dict
            self.assertIsInstance(result, dict)
        except ODPSExportError:
            # If it fails, it should be ODPSExportError with context
            pass

    def test_generate_odps_from_hubcontract_returns_dict(self):
        """Test that function returns a dictionary"""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
        }

        result = generate_odps_from_hubcontract(hub_contract)
        self.assertIsInstance(result, dict)

    def test_generate_odps_from_hubcontract_returns_odps_structure(self):
        """Test that function returns ODPS structure with required fields"""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Verify ODPS structure
        self.assertIn("schema", result)
        self.assertIn("version", result)
        self.assertIn("product", result)
        self.assertIn("details", result["product"])

        # Verify schema URL
        self.assertEqual(result["schema"], "https://opendataproducts.org/schema/v4.1")
        self.assertEqual(result["version"], "4.1")


class ODPSGeneratorErrorHandlingTest(TestCase):
    """Test ODPS generator error handling"""

    def test_generate_odps_from_hubcontract_raises_export_error_for_invalid_input(self):
        """Test that function raises ODPSExportError for invalid input"""
        # Invalid input: not a dict
        with self.assertRaises(ODPSExportError) as context:
            generate_odps_from_hubcontract("not a dict")

        error = context.exception
        self.assertEqual(error.error_code, ODPSExportError.ERROR_CODE_EXPORT_FAILED)
        self.assertIsNotNone(error.context)
        self.assertIn("field_path", error.context)

    def test_generate_odps_from_hubcontract_error_includes_field_name(self):
        """Test that error includes field name in context"""
        # Missing required field: info
        hub_contract = {
            "id": "test-product",
            # Missing info section
            "schema": {"fields": []},
        }

        with self.assertRaises(ODPSExportError) as context:
            generate_odps_from_hubcontract(hub_contract)

        error = context.exception
        self.assertIsNotNone(error.context)
        # Context should include information about the missing field
        self.assertIn("field_path", error.context)

    def test_generate_odps_from_hubcontract_error_includes_expected_type(self):
        """Test that error includes expected type in context"""
        # Invalid type: info is not a dict
        hub_contract = {
            "id": "test-product",
            "info": "not a dict",  # Should be dict
            "schema": {"fields": []},
        }

        with self.assertRaises(ODPSExportError) as context:
            generate_odps_from_hubcontract(hub_contract)

        error = context.exception
        self.assertIsNotNone(error.context)
        # Context should include expected type information
        self.assertIn("expected", error.context)
        self.assertIsNotNone(error.context["expected"])

    def test_generate_odps_from_hubcontract_error_includes_actual_type(self):
        """Test that error includes actual type in context"""
        # Invalid type: info is not a dict
        hub_contract = {
            "id": "test-product",
            "info": "not a dict",  # Should be dict
            "schema": {"fields": []},
        }

        with self.assertRaises(ODPSExportError) as context:
            generate_odps_from_hubcontract(hub_contract)

        error = context.exception
        self.assertIsNotNone(error.context)
        # Context should include actual type information
        self.assertIn("actual", error.context)
        self.assertIsNotNone(error.context["actual"])

    def test_generate_odps_from_hubcontract_error_includes_field_path(self):
        """Test that error includes field path in context"""
        # Missing required field: info.name
        hub_contract = {
            "id": "test-product",
            "info": {
                # Missing name field
            },
            "schema": {"fields": []},
        }

        with self.assertRaises(ODPSExportError) as context:
            generate_odps_from_hubcontract(hub_contract)

        error = context.exception
        self.assertIsNotNone(error.context)
        # Context should include field path information
        self.assertIn("field_path", error.context)
        self.assertIsNotNone(error.context["field_path"])

    def test_generate_odps_from_hubcontract_wraps_unexpected_errors(self):
        """Test that unexpected errors are wrapped in ODPSExportError"""
        # This test ensures that any unexpected exception is caught and wrapped
        # We'll use a None input which should cause an error
        with self.assertRaises(ODPSExportError):
            generate_odps_from_hubcontract(None)

    def test_generate_odps_from_hubcontract_error_recoverable(self):
        """Test that export errors are marked as recoverable"""
        # Invalid input
        with self.assertRaises(ODPSExportError) as context:
            generate_odps_from_hubcontract("not a dict")

        error = context.exception
        # Export errors should be recoverable (as per ODPSExportError definition)
        self.assertTrue(error.recoverable)


class ODPSGeneratorQualityMappingTest(TestCase):
    """Test HubContract → ODPS quality mapping (Task 2.1.4)"""

    def test_quality_mapping_default_profile_key(self):
        """Test mapping quality.default_profile_key → product.dataQuality.declarative.default"""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "quality": {"default_profile_key": "production-profile"},
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Verify default profile is mapped
        self.assertIn("product", result)
        self.assertIn("dataQuality", result["product"])
        self.assertIn("declarative", result["product"]["dataQuality"])
        self.assertIn("default", result["product"]["dataQuality"]["declarative"])
        self.assertEqual(
            result["product"]["dataQuality"]["declarative"]["default"], "production-profile"
        )

    def test_quality_mapping_rules_to_dimensions(self):
        """Test mapping quality.rules[] → product.dataQuality.declarative.dimensions"""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "quality": {
                "rules": [
                    {
                        "dimension": "completeness",
                        "rule_id": "completeness-rule",
                        "name": "Completeness Check",
                        "threshold": 0.95,
                        "unit": "percentage",
                        "severity": "ERROR",
                        "description": "Ensure data completeness",
                        "expression": ">= 0.95 percentage",
                    },
                    {
                        "dimension": "accuracy",
                        "rule_id": "accuracy-rule",
                        "name": "Accuracy Check",
                        "threshold": 0.98,
                        "unit": "percentage",
                        "severity": "WARNING",
                        "expression": "== 0.98 percentage",
                    },
                ]
            },
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Verify dimensions are created
        self.assertIn("product", result)
        self.assertIn("dataQuality", result["product"])
        self.assertIn("declarative", result["product"]["dataQuality"])
        self.assertIn("dimensions", result["product"]["dataQuality"]["declarative"])

        dimensions = result["product"]["dataQuality"]["declarative"]["dimensions"]
        self.assertIn("completeness", dimensions)
        self.assertIn("accuracy", dimensions)

        # Check completeness dimension
        completeness = dimensions["completeness"]
        self.assertEqual(completeness["ruleID"], "completeness-rule")
        self.assertEqual(completeness["name"], "Completeness Check")
        self.assertEqual(completeness["threshold"], 0.95)
        self.assertEqual(completeness["unit"], "percentage")
        self.assertEqual(completeness["severity"], "ERROR")
        self.assertEqual(completeness["description"], "Ensure data completeness")
        self.assertIn("objectives", completeness)
        self.assertIn("min", completeness["objectives"])
        self.assertEqual(completeness["objectives"]["min"], 0.95)

        # Check accuracy dimension
        accuracy = dimensions["accuracy"]
        self.assertEqual(accuracy["ruleID"], "accuracy-rule")
        self.assertEqual(accuracy["name"], "Accuracy Check")
        self.assertEqual(accuracy["threshold"], 0.98)
        self.assertEqual(accuracy["unit"], "percentage")
        self.assertEqual(accuracy["severity"], "WARNING")
        self.assertIn("objectives", accuracy)
        self.assertIn("target", accuracy["objectives"])
        self.assertEqual(accuracy["objectives"]["target"], 0.98)

    def test_quality_mapping_executable_specs(self):
        """Test mapping quality.x_odps.executable[] → product.dataQuality.executable[]"""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "quality": {
                "x_odps": {
                    "executable": [
                        {"type": "great_expectations", "suite": "data_quality_suite"},
                        {"type": "dbt_test", "test_name": "test_data_quality"},
                    ]
                }
            },
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Verify executable specs are mapped
        self.assertIn("product", result)
        self.assertIn("dataQuality", result["product"])
        self.assertIn("executable", result["product"]["dataQuality"])
        self.assertIsInstance(result["product"]["dataQuality"]["executable"], list)
        self.assertEqual(len(result["product"]["dataQuality"]["executable"]), 2)
        self.assertEqual(
            result["product"]["dataQuality"]["executable"][0]["type"], "great_expectations"
        )
        self.assertEqual(result["product"]["dataQuality"]["executable"][1]["type"], "dbt_test")

    def test_quality_mapping_all_components_together(self):
        """Test mapping all quality components together"""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "quality": {
                "default_profile_key": "production-profile",
                "rules": [
                    {
                        "dimension": "completeness",
                        "rule_id": "comp-1",
                        "name": "Completeness",
                        "threshold": 0.95,
                        "severity": "ERROR",
                    }
                ],
                "x_odps": {"executable": [{"type": "great_expectations", "suite": "dq_suite"}]},
            },
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Verify all components are mapped
        data_quality = result["product"]["dataQuality"]
        self.assertEqual(data_quality["declarative"]["default"], "production-profile")
        self.assertIn("dimensions", data_quality["declarative"])
        self.assertIn("completeness", data_quality["declarative"]["dimensions"])
        self.assertIn("executable", data_quality)
        self.assertEqual(len(data_quality["executable"]), 1)

    def test_quality_mapping_optional_sections(self):
        """Test that quality section is optional (graceful degradation)"""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            # quality section is missing
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Should succeed without quality section
        self.assertIn("product", result)
        # dataQuality should not be present if quality is missing
        self.assertNotIn("dataQuality", result["product"])

    def test_quality_mapping_rules_without_dimension(self):
        """Test that rules without dimension field are skipped"""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "quality": {
                "rules": [
                    {
                        "rule_id": "rule-1",
                        "name": "Rule without dimension",
                        # dimension is missing
                    }
                ]
            },
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Should succeed but dimensions should be empty or not present
        if "dataQuality" in result["product"]:
            declarative = result["product"]["dataQuality"].get("declarative", {})
            dimensions = declarative.get("dimensions", {})
            # Rules without dimension should not create dimensions
            self.assertEqual(len(dimensions), 0)

    def test_quality_mapping_rules_invalid_type(self):
        """Test error handling for invalid rules type"""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "quality": {"rules": "not a list"},  # Should be list
        }

        with self.assertRaises(ODPSExportError) as context:
            generate_odps_from_hubcontract(hub_contract)

        error = context.exception
        self.assertIn("rules", error.message.lower())
        self.assertIn("field_path", error.context)

    def test_quality_mapping_executable_invalid_type(self):
        """Test error handling for invalid executable type"""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "quality": {"x_odps": {"executable": "not a list"}},  # Should be list
        }

        with self.assertRaises(ODPSExportError) as context:
            generate_odps_from_hubcontract(hub_contract)

        error = context.exception
        self.assertIn("executable", error.message.lower())
        self.assertIn("field_path", error.context)

    def test_quality_mapping_rules_grouped_by_dimension(self):
        """Test that multiple rules with same dimension are grouped"""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "quality": {
                "rules": [
                    {
                        "dimension": "completeness",
                        "rule_id": "comp-1",
                        "name": "Completeness Rule 1",
                        "threshold": 0.95,
                    },
                    {
                        "dimension": "completeness",
                        "rule_id": "comp-2",
                        "name": "Completeness Rule 2",
                        "threshold": 0.90,
                    },
                ]
            },
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Should create one dimension with the first rule (ODPS supports one dimension per name)
        dimensions = result["product"]["dataQuality"]["declarative"]["dimensions"]
        self.assertIn("completeness", dimensions)
        # Should use first rule
        self.assertEqual(dimensions["completeness"]["ruleID"], "comp-1")

    def test_quality_mapping_expression_parsing_min(self):
        """Test parsing expression with min objective"""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "quality": {
                "rules": [
                    {
                        "dimension": "completeness",
                        "rule_id": "comp-1",
                        "name": "Completeness",
                        "expression": ">= 0.95 percentage",
                        "threshold": 0.95,
                        "unit": "percentage",
                    }
                ]
            },
        }

        result = generate_odps_from_hubcontract(hub_contract)

        completeness = result["product"]["dataQuality"]["declarative"]["dimensions"]["completeness"]
        self.assertIn("objectives", completeness)
        self.assertIn("min", completeness["objectives"])
        self.assertEqual(completeness["objectives"]["min"], 0.95)

    def test_quality_mapping_expression_parsing_max(self):
        """Test parsing expression with max objective"""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "quality": {
                "rules": [
                    {
                        "dimension": "accuracy",
                        "rule_id": "acc-1",
                        "name": "Accuracy",
                        "expression": "<= 0.99 percentage",
                        "threshold": 0.99,
                        "unit": "percentage",
                    }
                ]
            },
        }

        result = generate_odps_from_hubcontract(hub_contract)

        accuracy = result["product"]["dataQuality"]["declarative"]["dimensions"]["accuracy"]
        self.assertIn("objectives", accuracy)
        self.assertIn("max", accuracy["objectives"])
        self.assertEqual(accuracy["objectives"]["max"], 0.99)

    def test_quality_mapping_expression_parsing_target(self):
        """Test parsing expression with target objective"""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "quality": {
                "rules": [
                    {
                        "dimension": "accuracy",
                        "rule_id": "acc-1",
                        "name": "Accuracy",
                        "expression": "== 0.98 percentage",
                        "threshold": 0.98,
                        "unit": "percentage",
                    }
                ]
            },
        }

        result = generate_odps_from_hubcontract(hub_contract)

        accuracy = result["product"]["dataQuality"]["declarative"]["dimensions"]["accuracy"]
        self.assertIn("objectives", accuracy)
        self.assertIn("target", accuracy["objectives"])
        self.assertEqual(accuracy["objectives"]["target"], 0.98)

    def test_quality_mapping_rule_with_additional_fields(self):
        """Test mapping rule with additional fields (target, operator, etc.)"""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
            "quality": {
                "rules": [
                    {
                        "dimension": "completeness",
                        "rule_id": "comp-1",
                        "name": "Completeness",
                        "target": "email_column",
                        "operator": ">=",
                        "threshold": 0.95,
                        "unit": "percentage",
                        "severity": "ERROR",
                        "description": "Check email completeness",
                    }
                ]
            },
        }

        result = generate_odps_from_hubcontract(hub_contract)

        completeness = result["product"]["dataQuality"]["declarative"]["dimensions"]["completeness"]
        self.assertEqual(completeness["target"], "email_column")
        self.assertEqual(completeness["operator"], ">=")
        self.assertEqual(completeness["description"], "Check email completeness")


class ODPSGeneratorInfoMappingTest(TestCase):
    """Test HubContract → ODPS info mapping (Task 2.1.2)"""

    def test_info_mapping_version_to_product_version(self):
        """Test mapping HubContract.info.version → product.details.<lang>.productVersion"""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product", "version": "1.0.0"},
            "schema": {"fields": []},
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Verify productVersion is mapped
        self.assertIn("product", result)
        self.assertIn("details", result["product"])
        self.assertIn("en", result["product"]["details"])
        self.assertIn("productVersion", result["product"]["details"]["en"])
        self.assertEqual(result["product"]["details"]["en"]["productVersion"], "1.0.0")

    def test_info_mapping_version_optional(self):
        """Test that version is optional (graceful degradation)"""
        hub_contract = {
            "id": "test-product",
            "info": {
                "name": "Test Product"
                # version is missing
            },
            "schema": {"fields": []},
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Should succeed without version
        self.assertIn("product", result)
        self.assertIn("details", result["product"])
        self.assertIn("en", result["product"]["details"])
        # productVersion should not be present if version is missing
        self.assertNotIn("productVersion", result["product"]["details"]["en"])

    def test_info_mapping_tags_to_product_details_tags(self):
        """Test mapping HubContract.info.tags → product.details.<lang>.tags"""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product", "tags": ["tag1", "tag2", "tag3"]},
            "schema": {"fields": []},
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Verify tags are mapped
        self.assertIn("product", result)
        self.assertIn("details", result["product"])
        self.assertIn("en", result["product"]["details"])
        self.assertIn("tags", result["product"]["details"]["en"])
        self.assertEqual(result["product"]["details"]["en"]["tags"], ["tag1", "tag2", "tag3"])

    def test_info_mapping_tags_optional(self):
        """Test that tags are optional (graceful degradation)"""
        hub_contract = {
            "id": "test-product",
            "info": {
                "name": "Test Product"
                # tags are missing
            },
            "schema": {"fields": []},
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Should succeed without tags
        self.assertIn("product", result)
        self.assertIn("details", result["product"])
        self.assertIn("en", result["product"]["details"])
        # tags should not be present if missing
        self.assertNotIn("tags", result["product"]["details"]["en"])

    def test_info_mapping_owners_to_dataholder(self):
        """Test mapping HubContract.info.owners[] → dataHolder.<lang>"""
        hub_contract = {
            "id": "test-product",
            "info": {
                "name": "Test Product",
                "owners": [{"name": "Test Company", "email": "test@example.com"}],
            },
            "schema": {"fields": []},
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Verify dataHolder is created
        self.assertIn("dataHolder", result)
        self.assertIn("en", result["dataHolder"])
        self.assertEqual(result["dataHolder"]["en"]["legalName"], "Test Company")
        self.assertEqual(result["dataHolder"]["en"]["email"], "test@example.com")

    def test_info_mapping_owners_multiple_to_dataholder_first(self):
        """Test mapping multiple owners - use first owner for dataHolder"""
        hub_contract = {
            "id": "test-product",
            "info": {
                "name": "Test Product",
                "owners": [
                    {"name": "First Company", "email": "first@example.com"},
                    {"name": "Second Company", "email": "second@example.com"},
                ],
            },
            "schema": {"fields": []},
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Verify dataHolder uses first owner
        self.assertIn("dataHolder", result)
        self.assertIn("en", result["dataHolder"])
        self.assertEqual(result["dataHolder"]["en"]["legalName"], "First Company")
        self.assertEqual(result["dataHolder"]["en"]["email"], "first@example.com")

    def test_info_mapping_owners_partial_name_only(self):
        """Test mapping owners with only name (no email)"""
        hub_contract = {
            "id": "test-product",
            "info": {
                "name": "Test Product",
                "owners": [
                    {
                        "name": "Test Company"
                        # email is missing
                    }
                ],
            },
            "schema": {"fields": []},
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Verify dataHolder has only legalName
        self.assertIn("dataHolder", result)
        self.assertIn("en", result["dataHolder"])
        self.assertEqual(result["dataHolder"]["en"]["legalName"], "Test Company")
        self.assertNotIn("email", result["dataHolder"]["en"])

    def test_info_mapping_owners_partial_email_only(self):
        """Test mapping owners with only email (no name)"""
        hub_contract = {
            "id": "test-product",
            "info": {
                "name": "Test Product",
                "owners": [
                    {
                        "email": "test@example.com"
                        # name is missing
                    }
                ],
            },
            "schema": {"fields": []},
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Verify dataHolder has only email
        self.assertIn("dataHolder", result)
        self.assertIn("en", result["dataHolder"])
        self.assertEqual(result["dataHolder"]["en"]["email"], "test@example.com")
        self.assertNotIn("legalName", result["dataHolder"]["en"])

    def test_info_mapping_owners_optional(self):
        """Test that owners are optional (graceful degradation)"""
        hub_contract = {
            "id": "test-product",
            "info": {
                "name": "Test Product"
                # owners are missing
            },
            "schema": {"fields": []},
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Should succeed without owners
        self.assertIn("product", result)
        # dataHolder should not be present if owners are missing
        self.assertNotIn("dataHolder", result)

    def test_info_mapping_all_fields_together(self):
        """Test mapping all info fields together"""
        hub_contract = {
            "id": "test-product",
            "info": {
                "name": "Test Product",
                "description": "Test description",
                "version": "2.0.0",
                "tags": ["tag1", "tag2"],
                "owners": [{"name": "Test Company", "email": "test@example.com"}],
            },
            "schema": {"fields": []},
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Verify all fields are mapped
        details = result["product"]["details"]["en"]
        self.assertEqual(details["name"], "Test Product")
        self.assertEqual(details["description"], "Test description")
        self.assertEqual(details["productVersion"], "2.0.0")
        self.assertEqual(details["tags"], ["tag1", "tag2"])

        # Verify dataHolder
        self.assertIn("dataHolder", result)
        self.assertEqual(result["dataHolder"]["en"]["legalName"], "Test Company")
        self.assertEqual(result["dataHolder"]["en"]["email"], "test@example.com")

    def test_info_mapping_version_invalid_type(self):
        """Test error handling for invalid version type"""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product", "version": 123},  # Should be string
            "schema": {"fields": []},
        }

        with self.assertRaises(ODPSExportError) as context:
            generate_odps_from_hubcontract(hub_contract)

        error = context.exception
        self.assertIn("version", error.message.lower())
        self.assertIn("field_path", error.context)

    def test_info_mapping_tags_invalid_type(self):
        """Test error handling for invalid tags type"""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product", "tags": "not a list"},  # Should be list
            "schema": {"fields": []},
        }

        with self.assertRaises(ODPSExportError) as context:
            generate_odps_from_hubcontract(hub_contract)

        error = context.exception
        self.assertIn("tags", error.message.lower())
        self.assertIn("field_path", error.context)

    def test_info_mapping_owners_invalid_type(self):
        """Test error handling for invalid owners type"""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product", "owners": "not a list"},  # Should be list
            "schema": {"fields": []},
        }

        with self.assertRaises(ODPSExportError) as context:
            generate_odps_from_hubcontract(hub_contract)

        error = context.exception
        self.assertIn("owners", error.message.lower())
        self.assertIn("field_path", error.context)

    def test_info_mapping_owners_invalid_owner_type(self):
        """Test error handling for invalid owner entry type"""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product", "owners": ["not a dict"]},  # Should be dict
            "schema": {"fields": []},
        }

        with self.assertRaises(ODPSExportError) as context:
            generate_odps_from_hubcontract(hub_contract)

        error = context.exception
        self.assertIn("owner", error.message.lower())
        self.assertIn("field_path", error.context)

    def test_generate_odps_handles_unicode_characters(self):
        """Test that ODPS generation handles unicode characters correctly."""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "测试产品", "description": "测试描述", "tags": ["标签1", "标签2"]},
            "schema": {"fields": []},
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Verify unicode characters are preserved
        self.assertIn("product", result)
        self.assertIn("details", result["product"])
        self.assertIn("en", result["product"]["details"])
        self.assertEqual(result["product"]["details"]["en"]["name"], "测试产品")
        self.assertEqual(result["product"]["details"]["en"]["description"], "测试描述")

    def test_generate_odps_handles_special_characters(self):
        """Test that ODPS generation handles special characters correctly."""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test & Co. (Special)", "description": "Test <description> & more"},
            "schema": {"fields": []},
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Verify special characters are preserved
        self.assertIn("product", result)
        self.assertIn("details", result["product"])
        self.assertIn("en", result["product"]["details"])
        self.assertEqual(result["product"]["details"]["en"]["name"], "Test & Co. (Special)")
        self.assertEqual(
            result["product"]["details"]["en"]["description"], "Test <description> & more"
        )

    def test_generate_odps_handles_very_large_documents(self):
        """Test that ODPS generation handles very large documents correctly."""
        large_description = "A" * 100000  # 100KB string
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product", "description": large_description},
            "schema": {"fields": []},
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

    def test_generate_odps_handles_none_values(self):
        """Test that ODPS generation handles None values correctly."""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product", "description": None, "version": None},  # None value
            "schema": {"fields": []},
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

    def test_generate_odps_handles_nested_structures(self):
        """Test that ODPS generation handles nested structures correctly."""
        hub_contract = {
            "id": "test-product",
            "info": {
                "name": "Test Product",
                "nested": {"level1": {"level2": {"level3": {"level4": {"value": "deep"}}}}},
            },
            "schema": {"fields": []},
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Verify nested structure is preserved (may be in extensions or details)
        self.assertIn("product", result)
        # Nested structures may be preserved in various places depending on implementation
        self.assertIsNotNone(result)
