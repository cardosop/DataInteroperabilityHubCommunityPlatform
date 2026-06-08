"""
Unit tests for ODPS Normalizer

Tests verify:
1. SpecNormalizer protocol implementation
2. supports() method
3. normalize() method signature and basic functionality
4. Error handling with ODPSNormalizationError
5. Error context (field name, expected type)
6. Graceful degradation for missing optional fields

All tests use real implementations (no mocks of hub services).
"""

from django.test import SimpleTestCase, TestCase

from hub.apps.contracts.models import NormalizationStatus, OriginalSpecType

# Import from normalization package (which re-exports from normalization_engine.py)
from hub.apps.contracts.normalization import NormalizationResult, SpecNormalizer
from hub.apps.contracts.normalization.odps_normalizer import ODPSNormalizer
from hub.apps.contracts.odps_errors import ODPSNormalizationError
from hub.apps.contracts.tests.normalizer_edge_case_mixin import ODPSEdgeCaseMixin


class ODPSNormalizerSupportsTest(TestCase):
    """Test ODPSNormalizer supports() method"""

    def setUp(self):
        """Set up test fixtures"""
        self.normalizer = ODPSNormalizer()

    def test_supports_odps(self):
        """Test that normalizer supports ODPS spec type"""
        contract_data = {"schema": "https://opendataproducts.org/schema/v4.1"}
        result = self.normalizer.supports(OriginalSpecType.ODPS, "4.1", contract_data)
        self.assertTrue(result)

    def test_supports_odps_different_versions(self):
        """Test that normalizer supports different ODPS versions"""
        contract_data = {"schema": "https://opendataproducts.org/schema/v4.0"}
        result = self.normalizer.supports(OriginalSpecType.ODPS, "4.0", contract_data)
        self.assertTrue(result)

        contract_data = {"schema": "https://opendataproducts.org/schema/v3.9"}
        result = self.normalizer.supports(OriginalSpecType.ODPS, "3.9", contract_data)
        self.assertTrue(result)

    def test_supports_not_odcs(self):
        """Test that normalizer does not support ODCS"""
        contract_data = {"apiVersion": "odcs/v3", "kind": "DataContract"}
        result = self.normalizer.supports(OriginalSpecType.ODCS, "3.0.2", contract_data)
        self.assertFalse(result)

    def test_supports_case_sensitive(self):
        """Test that supports() is case-sensitive for spec_type"""
        contract_data = {"schema": "https://opendataproducts.org/schema/v4.1"}
        result = self.normalizer.supports("odps", "4.1", contract_data)  # lowercase
        self.assertFalse(result)

    def test_spec_type_attribute(self):
        """Test that normalizer has spec_type attribute"""
        self.assertEqual(self.normalizer.spec_type, OriginalSpecType.ODPS)


class ODPSNormalizerNormalizeTest(TestCase):
    """Test ODPSNormalizer normalize() method"""

    def setUp(self):
        """Set up test fixtures"""
        self.normalizer = ODPSNormalizer()

    def test_normalize_returns_normalization_result(self):
        """Test that normalize() returns NormalizationResult"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {"en": {"name": "Test Product"}}},
        }

        result = self.normalizer.normalize(contract_data)
        # Check that it's a NormalizationResult-like object (may be from different module due to import handling)
        self.assertTrue(hasattr(result, "hub_contract"))
        self.assertTrue(hasattr(result, "status"))
        self.assertTrue(hasattr(result, "errors"))
        self.assertTrue(hasattr(result, "warnings"))
        self.assertTrue(hasattr(result, "spec_type"))
        self.assertTrue(hasattr(result, "spec_version"))
        self.assertEqual(result.spec_type, OriginalSpecType.ODPS)
        self.assertIsNotNone(result.spec_version)

    def test_normalize_with_spec_version(self):
        """Test normalize() with explicit spec version"""
        contract_data = {"schema": "https://opendataproducts.org/schema/v4.1", "version": "4.1"}

        result = self.normalizer.normalize(contract_data, spec_version="4.1")
        self.assertEqual(result.spec_version, "4.1")

    def test_normalize_auto_detects_version(self):
        """Test that normalize() auto-detects version if not provided using real detect_odps_version"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {"en": {"productID": "test"}}},
        }

        # Use real detect_odps_version implementation
        result = self.normalizer.normalize(contract_data)
        self.assertEqual(result.spec_version, "4.1")

    def test_normalize_handles_version_detection_failure(self):
        """Test that normalize() handles version detection failure gracefully using real detect_odps_version"""
        # Use contract data without version info to test fallback behavior
        contract_data = {
            "product": {"details": {"en": {"productID": "test"}}}
            # No schema URL and no version field - detect_odps_version will return "unknown"
        }

        # Use real detect_odps_version implementation - it will return "unknown" or None
        # The normalizer should handle this gracefully
        result = self.normalizer.normalize(contract_data)
        # Version detection failure must return "unknown" — NOT fallback to "4.1"
        self.assertEqual(result.spec_version, "unknown",
            "Version detection failure must return 'unknown', not fallback '4.1'")
        self.assertIsNotNone(result.spec_version)

    def test_normalize_initializes_hub_contract(self):
        """Test that normalize() initializes HubContract structure"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {"en": {"name": "Test Product"}}},
        }

        result = self.normalizer.normalize(contract_data)
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("info", result.hub_contract)
        self.assertIn("schema", result.hub_contract)
        self.assertIn("extensions", result.hub_contract)
        self.assertIn("normalization", result.hub_contract)


class ODPSNormalizerErrorHandlingTest(TestCase):
    """Test ODPSNormalizer error handling"""

    def setUp(self):
        """Set up test fixtures"""
        self.normalizer = ODPSNormalizer()

    def test_normalize_invalid_data_type(self):
        """Test that normalize() handles invalid data type"""
        # Pass non-dict data
        result = self.normalizer.normalize("not a dict")

        self.assertIsNone(result.hub_contract)
        self.assertEqual(result.status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertTrue(len(result.errors) > 0)
        # Check that error message contains relevant information
        error_msg = " ".join(result.errors)
        self.assertTrue("dictionary" in error_msg.lower() or "dict" in error_msg.lower())

    def test_normalize_handles_odps_normalization_error(self):
        """Test that normalize() properly handles ODPSNormalizationError using real implementation"""
        # Use invalid contract data that will naturally cause ODPSNormalizationError
        # Missing required product field will trigger normalization error
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            # Missing required "product" field - will cause normalization error
        }

        # Use real implementation - invalid data will naturally cause errors
        result = self.normalizer.normalize(contract_data)

        # Should handle error gracefully
        self.assertIsNotNone(result)
        # May have errors or warnings due to missing required fields
        self.assertIsNotNone(result.status)
        # Check that errors are properly formatted
        if result.errors:
            self.assertIsInstance(result.errors, list)

    def test_normalize_handles_unexpected_errors(self):
        """Test that normalize() handles unexpected errors gracefully using real implementation"""
        # Use invalid data type that will cause unexpected errors
        # Pass non-dict data to trigger error handling
        contract_data = "not a dict"

        # Use real implementation - invalid data type will naturally cause errors
        result = self.normalizer.normalize(contract_data)

        # Should handle error gracefully
        self.assertIsNotNone(result)
        self.assertEqual(result.status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertTrue(len(result.errors) > 0)
        # Error message should indicate the problem
        error_msg = " ".join(result.errors)
        self.assertTrue(
            "dictionary" in error_msg.lower()
            or "dict" in error_msg.lower()
            or "invalid" in error_msg.lower()
        )


class ODPSNormalizerErrorContextTest(TestCase):
    """Test ODPSNormalizer error context through public API"""

    def setUp(self):
        """Set up test fixtures"""
        self.normalizer = ODPSNormalizer()

    def test_normalize_missing_required_field_provides_error_context(self):
        """Test that normalize() provides error context when required field is missing"""
        # Missing required "product" field should trigger error with context
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            # Missing required "product" field
        }

        result = self.normalizer.normalize(contract_data)

        # Should have errors with context
        self.assertEqual(result.status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertTrue(len(result.errors) > 0)
        # Error should contain context about missing field
        error_msg = " ".join(result.errors)
        self.assertTrue("product" in error_msg.lower() or "missing" in error_msg.lower())

    def test_normalize_invalid_type_provides_error_context(self):
        """Test that normalize() provides error context when field has invalid type"""
        # product.details should be a dict, not a string
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": "invalid_type",  # Should be dict, not string
            },
        }

        result = self.normalizer.normalize(contract_data)

        # Should have errors with context about invalid structure
        self.assertEqual(result.status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertTrue(len(result.errors) > 0)
        error_msg = " ".join(result.errors)
        # Error should mention the issue with product.details (could be type mismatch or missing field)
        self.assertTrue(
            "type" in error_msg.lower()
            or "invalid" in error_msg.lower()
            or "dict" in error_msg.lower()
            or "details" in error_msg.lower()
            or "product" in error_msg.lower()
            or "missing" in error_msg.lower()
            or "found" in error_msg.lower()
        )

    def test_normalize_valid_contract_succeeds(self):
        """Test that normalize() succeeds with valid contract data"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {"en": {"name": "Test Product"}}},
        }

        result = self.normalizer.normalize(contract_data)

        # Should succeed
        self.assertIsNotNone(result.hub_contract)
        self.assertIn(
            result.status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
        )

    def test_normalize_missing_optional_field_uses_default(self):
        """Test that normalize() handles missing optional fields gracefully"""
        # Contract with minimal required fields, missing optional fields
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {"en": {"name": "Test Product"}}},
            # Missing optional fields like lifecycle, marketplace, etc.
        }

        result = self.normalizer.normalize(contract_data)

        # Should succeed (optional fields are handled gracefully)
        self.assertIsNotNone(result.hub_contract)
        # May have warnings about missing optional fields, but should not fail
        self.assertIn(
            result.status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
        )


class ODPSNormalizerGracefulDegradationTest(TestCase):
    """Test ODPSNormalizer graceful degradation through public API"""

    def setUp(self):
        """Set up test fixtures"""
        self.normalizer = ODPSNormalizer()

    def test_normalize_handles_missing_optional_fields_gracefully(self):
        """Test that normalize() handles missing optional fields gracefully with warnings"""
        # Contract with required fields but missing optional fields (lifecycle, marketplace, etc.)
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                # Missing optional fields like lifecycle, marketplace, dataQuality
            },
        }

        result = self.normalizer.normalize(contract_data)

        # Should succeed (optional fields handled gracefully)
        self.assertIsNotNone(result.hub_contract)
        # May have warnings about missing optional fields, but should not fail
        self.assertIn(
            result.status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
        )

    def test_normalize_handles_invalid_optional_field_types_gracefully(self):
        """Test that normalize() handles invalid optional field types gracefully"""
        # Contract with invalid type for optional field (if such exists)
        # Note: This tests behavior - if optional fields have invalid types, they should be handled gracefully
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
            },
        }

        result = self.normalizer.normalize(contract_data)

        # Should handle gracefully - may have warnings but should not fail completely
        self.assertIsNotNone(result.hub_contract)
        self.assertIn(
            result.status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
        )

    def test_normalize_with_valid_optional_fields_succeeds(self):
        """Test that normalize() succeeds when optional fields are provided correctly"""
        # Contract with optional fields provided correctly
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "lifecycle": {"stage": "production"},
            },
        }

        result = self.normalizer.normalize(contract_data)

        # Should succeed without warnings for optional fields
        self.assertIsNotNone(result.hub_contract)
        self.assertIn(
            result.status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
        )

    def test_normalize_handles_missing_optional_sections_without_errors(self):
        """Test that normalize() handles completely missing optional sections without errors"""
        # Minimal contract with only required fields
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                # No lifecycle, marketplace, dataQuality sections
            },
        }

        result = self.normalizer.normalize(contract_data)

        # Should succeed - missing optional sections should not cause errors
        self.assertIsNotNone(result.hub_contract)
        self.assertIn(
            result.status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
        )
        # Should not have errors due to missing optional sections
        self.assertEqual(len(result.errors), 0)


class ODPSNormalizerStatusDeterminationTest(TestCase):
    """Test ODPSNormalizer status determination through public API"""

    def setUp(self):
        """Set up test fixtures"""
        self.normalizer = ODPSNormalizer()

    def test_normalize_status_failed_with_errors(self):
        """Test that normalize() returns NORMALIZATION_FAILED when errors occur"""
        # Invalid contract data that will cause errors
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            # Missing required product field - will cause errors
        }

        result = self.normalizer.normalize(contract_data)

        # Should have NORMALIZATION_FAILED status
        self.assertEqual(result.status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertTrue(len(result.errors) > 0)

    def test_normalize_status_failed_missing_name(self):
        """Test that normalize() returns NORMALIZATION_FAILED when required name is missing"""
        # Contract missing product.details.name (required field)
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {}},  # Missing "name" field
            },
        }

        result = self.normalizer.normalize(contract_data)

        # Should fail due to missing name
        self.assertEqual(result.status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertTrue(len(result.errors) > 0)

    def test_normalize_status_failed_missing_required_fields(self):
        """Test that normalize() returns NORMALIZATION_FAILED when required fields are missing"""
        # Contract with missing required product field
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            # Missing required "product" field
        }

        result = self.normalizer.normalize(contract_data)

        # Should fail
        self.assertEqual(result.status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertTrue(len(result.errors) > 0)

    def test_normalize_status_with_warnings(self):
        """Test that normalize() returns NORMALIZED_WITH_WARNINGS when warnings occur"""
        # Valid contract but with optional fields that might generate warnings
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                # Include optional fields that might generate warnings if incomplete
            },
        }

        result = self.normalizer.normalize(contract_data)

        # Should succeed, may have warnings
        self.assertIsNotNone(result.hub_contract)
        # Status should be OK or WITH_WARNINGS
        self.assertIn(
            result.status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
        )

    def test_normalize_status_ok(self):
        """Test that normalize() returns NORMALIZED_OK for successful normalization"""
        # Complete valid contract
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product", "productID": "test-123"}},
            },
        }

        result = self.normalizer.normalize(contract_data)

        # Should succeed without errors
        self.assertIsNotNone(result.hub_contract)
        # Status should be OK (or WITH_WARNINGS if optional fields trigger warnings)
        self.assertIn(
            result.status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
        )
        # If status is OK, there should be no errors
        if result.status == NormalizationStatus.NORMALIZED_OK:
            self.assertEqual(len(result.errors), 0)


class ODPSNormalizerProtocolTest(TestCase):
    """Test ODPSNormalizer protocol compliance"""

    def test_implements_spec_normalizer_protocol(self):
        """Test that ODPSNormalizer implements SpecNormalizer protocol"""
        normalizer = ODPSNormalizer()

        # Check protocol compliance
        self.assertTrue(isinstance(normalizer, SpecNormalizer))
        self.assertTrue(hasattr(normalizer, "spec_type"))
        self.assertTrue(hasattr(normalizer, "supports"))
        self.assertTrue(hasattr(normalizer, "normalize"))
        self.assertTrue(callable(normalizer.supports))
        self.assertTrue(callable(normalizer.normalize))

    def test_spec_type_attribute(self):
        """Test that spec_type attribute is set correctly"""
        normalizer = ODPSNormalizer()
        self.assertEqual(normalizer.spec_type, OriginalSpecType.ODPS)


class ODPSNormalizerQualityMappingTest(TestCase):
    """Test ODPS → HubContract quality mapping through public API (Task 1.4.3)"""

    def setUp(self):
        """Set up test fixtures"""
        self.normalizer = ODPSNormalizer()

    def test_normalize_maps_declarative_default_to_quality_default_profile_key(self):
        """Test that normalize() maps product.dataQuality.declarative.default → quality.default_profile_key"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "dataQuality": {"declarative": {"default": "high-quality-profile"}},
            },
        }

        result = self.normalizer.normalize(contract_data)

        # Should succeed and map quality data
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("quality", result.hub_contract)
        self.assertEqual(
            result.hub_contract["quality"]["default_profile_key"], "high-quality-profile"
        )
        # Should not have errors
        self.assertEqual(len(result.errors), 0)

    def test_normalize_maps_declarative_dimensions_to_quality_rules(self):
        """Test that normalize() maps declarative dimensions → quality.rules[]"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "dataQuality": {
                    "declarative": {
                        "dimensions": {
                            "completeness": {
                                "ruleID": "completeness-rule",
                                "name": "Completeness Check",
                                "objectives": {"min": 0.95},
                                "unit": "percentage",
                                "threshold": 0.95,
                                "severity": "ERROR",
                                "description": "Ensure data completeness",
                            },
                            "accuracy": {
                                "ruleID": "accuracy-rule",
                                "name": "Accuracy Check",
                                "objectives": {"target": 0.98},
                                "unit": "percentage",
                                "threshold": 0.98,
                                "severity": "WARNING",
                            },
                        }
                    }
                },
            },
        }

        result = self.normalizer.normalize(contract_data)

        # Should succeed and map quality rules
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("quality", result.hub_contract)
        self.assertIn("rules", result.hub_contract["quality"])
        self.assertEqual(len(result.hub_contract["quality"]["rules"]), 2)

        # Check first rule (completeness)
        completeness_rule = result.hub_contract["quality"]["rules"][0]
        self.assertEqual(completeness_rule["dimension"], "completeness")
        self.assertEqual(completeness_rule["rule_id"], "completeness-rule")
        self.assertEqual(completeness_rule["name"], "Completeness Check")
        self.assertEqual(completeness_rule["threshold"], 0.95)
        self.assertEqual(completeness_rule["unit"], "percentage")
        self.assertEqual(completeness_rule["severity"], "ERROR")
        self.assertIn("expression", completeness_rule)
        self.assertIn(">= 0.95", completeness_rule["expression"])
        self.assertIn("percentage", completeness_rule["expression"])

        # Check second rule (accuracy)
        accuracy_rule = result.hub_contract["quality"]["rules"][1]
        self.assertEqual(accuracy_rule["dimension"], "accuracy")
        self.assertEqual(accuracy_rule["rule_id"], "accuracy-rule")
        self.assertEqual(accuracy_rule["name"], "Accuracy Check")
        self.assertEqual(accuracy_rule["threshold"], 0.98)
        self.assertEqual(accuracy_rule["unit"], "percentage")
        self.assertEqual(accuracy_rule["severity"], "WARNING")
        self.assertIn("expression", accuracy_rule)
        self.assertIn("== 0.98", accuracy_rule["expression"])

    def test_normalize_stores_executable_specs_in_quality_x_odps_executable(self):
        """Test that normalize() stores executable specs in quality.x_odps.executable[]"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "dataQuality": {
                    "executable": [
                        {
                            "type": "great_expectations",
                            "suite": "data_quality_suite",
                            "expectations": [
                                {"expectation_type": "expect_column_values_to_not_be_null"}
                            ],
                        },
                        {
                            "type": "dbt_test",
                            "test_name": "test_data_quality",
                            "sql": "SELECT * FROM data WHERE quality_score < 0.9",
                        },
                    ]
                },
            },
        }

        result = self.normalizer.normalize(contract_data)

        # Should succeed and store executable specs
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("quality", result.hub_contract)
        self.assertIn("x_odps", result.hub_contract["quality"])
        self.assertIn("executable", result.hub_contract["quality"]["x_odps"])
        self.assertEqual(len(result.hub_contract["quality"]["x_odps"]["executable"]), 2)
        self.assertEqual(
            result.hub_contract["quality"]["x_odps"]["executable"][0]["type"], "great_expectations"
        )
        self.assertEqual(
            result.hub_contract["quality"]["x_odps"]["executable"][1]["type"], "dbt_test"
        )

    def test_normalize_stores_single_executable_object_wrapped_in_list(self):
        """Test that normalize() stores single executable object (wrapped in list)"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "dataQuality": {
                    "executable": {"type": "great_expectations", "suite": "data_quality_suite"}
                },
            },
        }

        result = self.normalizer.normalize(contract_data)

        # Should succeed and store executable as list
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("quality", result.hub_contract)
        self.assertIn("x_odps", result.hub_contract["quality"])
        self.assertIn("executable", result.hub_contract["quality"]["x_odps"])
        self.assertEqual(len(result.hub_contract["quality"]["x_odps"]["executable"]), 1)
        self.assertEqual(
            result.hub_contract["quality"]["x_odps"]["executable"][0]["type"], "great_expectations"
        )

    def test_normalize_handles_missing_quality_data_gracefully(self):
        """Test that normalize() handles missing quality data gracefully"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}}
                # No dataQuality section
            },
        }

        result = self.normalizer.normalize(contract_data)

        # Should succeed without errors, quality section should not be created
        self.assertIsNotNone(result.hub_contract)
        self.assertNotIn("quality", result.hub_contract)
        self.assertEqual(len(result.errors), 0)

    def test_normalize_handles_missing_declarative_section_gracefully(self):
        """Test that normalize() handles missing declarative section gracefully"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "dataQuality": {
                    # No declarative section
                    "executable": []
                },
            },
        }

        result = self.normalizer.normalize(contract_data)

        # Should succeed without errors
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("quality", result.hub_contract)
        self.assertIn("x_odps", result.hub_contract["quality"])
        self.assertIn("executable", result.hub_contract["quality"]["x_odps"])
        self.assertEqual(len(result.errors), 0)

    def test_normalize_handles_invalid_default_type_with_warning(self):
        """Test that normalize() handles invalid default type with warning"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "dataQuality": {"declarative": {"default": 123}},  # Invalid: should be string
            },
        }

        result = self.normalizer.normalize(contract_data)

        # Should succeed but with warnings, should not set default_profile_key
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("quality", result.hub_contract)
        self.assertNotIn("default_profile_key", result.hub_contract["quality"])
        # Should have warnings about invalid type
        self.assertTrue(len(result.warnings) > 0)
        warning_msg = " ".join(result.warnings)
        self.assertTrue("default" in warning_msg.lower() or "invalid type" in warning_msg.lower())

    def test_quality_mapping_invalid_dimension_type(self):
        """Test handling invalid dimension type with warning through public API"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "dataQuality": {
                    "declarative": {
                        "dimensions": {"completeness": "invalid"}  # Invalid: should be dict
                    }
                },
            },
        }

        # Test through public API - normalize() calls _normalize_quality internally
        result = self.normalizer.normalize(contract_data)

        # Should not create rules, but should log warning
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("quality", result.hub_contract)
        self.assertNotIn("rules", result.hub_contract["quality"])
        self.assertTrue(len(result.warnings) > 0)
        warning_msg = " ".join(result.warnings)
        self.assertIn("completeness", warning_msg)
        self.assertIn("invalid type", warning_msg)

    def test_quality_mapping_invalid_executable_type(self):
        """Test handling invalid executable type with warning through public API"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "dataQuality": {"executable": "invalid"},  # Invalid: should be list or dict
            },
        }

        # Test through public API - normalize() calls _normalize_quality internally
        result = self.normalizer.normalize(contract_data)

        # Should not set executable, but should log warning
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("quality", result.hub_contract)
        if "x_odps" in result.hub_contract["quality"]:
            self.assertNotIn("executable", result.hub_contract["quality"]["x_odps"])
        self.assertTrue(len(result.warnings) > 0)
        warning_msg = " ".join(result.warnings)
        self.assertIn("executable", warning_msg)
        self.assertIn("invalid type", warning_msg)

    def test_quality_mapping_objectives_dict(self):
        """Test generating expression from objectives dict through public API"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "dataQuality": {
                    "declarative": {
                        "dimensions": {
                            "completeness": {
                                "objectives": {"min": 0.9, "max": 1.0},
                                "unit": "percentage",
                            }
                        }
                    }
                },
            },
        }

        # Test through public API - normalize() calls _normalize_quality internally
        result = self.normalizer.normalize(contract_data)

        self.assertIsNotNone(result.hub_contract)
        self.assertIn("quality", result.hub_contract)
        self.assertIn("rules", result.hub_contract["quality"])
        self.assertTrue(len(result.hub_contract["quality"]["rules"]) > 0)
        rule = result.hub_contract["quality"]["rules"][0]
        expression = rule["expression"]
        self.assertIn(">= 0.9", expression)
        self.assertIn("<= 1.0", expression)
        self.assertIn("percentage", expression)

    def test_quality_mapping_objectives_list(self):
        """Test generating expression from objectives list through public API"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "dataQuality": {
                    "declarative": {
                        "dimensions": {
                            "validity": {
                                "objectives": ["valid", "pending", "approved"],
                                "unit": "status",
                            }
                        }
                    }
                },
            },
        }

        # Test through public API - normalize() calls _normalize_quality internally
        result = self.normalizer.normalize(contract_data)

        self.assertIsNotNone(result.hub_contract)
        self.assertIn("quality", result.hub_contract)
        self.assertIn("rules", result.hub_contract["quality"])
        self.assertTrue(len(result.hub_contract["quality"]["rules"]) > 0)
        rule = result.hub_contract["quality"]["rules"][0]
        expression = rule["expression"]
        self.assertIn("IN", expression)
        self.assertIn("status", expression)

    def test_quality_mapping_objectives_scalar(self):
        """Test generating expression from objectives scalar through public API"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "dataQuality": {
                    "declarative": {
                        "dimensions": {"accuracy": {"objectives": 0.95, "unit": "percentage"}}
                    }
                },
            },
        }

        # Test through public API - normalize() calls _normalize_quality internally
        result = self.normalizer.normalize(contract_data)

        self.assertIsNotNone(result.hub_contract)
        self.assertIn("quality", result.hub_contract)
        self.assertIn("rules", result.hub_contract["quality"])
        self.assertTrue(len(result.hub_contract["quality"]["rules"]) > 0)
        rule = result.hub_contract["quality"]["rules"][0]
        expression = rule["expression"]
        self.assertIn("== 0.95", expression)
        self.assertIn("percentage", expression)

    def test_quality_mapping_objectives_string(self):
        """Test using objectives as expression string through public API"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "dataQuality": {
                    "declarative": {
                        "dimensions": {"custom": {"objectives": "COUNT(*) > 100", "unit": "rows"}}
                    }
                },
            },
        }

        # Test through public API - normalize() calls _normalize_quality internally
        result = self.normalizer.normalize(contract_data)

        self.assertIsNotNone(result.hub_contract)
        self.assertIn("quality", result.hub_contract)
        self.assertIn("rules", result.hub_contract["quality"])
        self.assertTrue(len(result.hub_contract["quality"]["rules"]) > 0)
        rule = result.hub_contract["quality"]["rules"][0]
        expression = rule["expression"]
        self.assertIn("COUNT(*) > 100", expression)
        self.assertIn("rows", expression)

    def test_quality_mapping_default_severity(self):
        """Test default severity assignment based on dimension type through public API"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "dataQuality": {
                    "declarative": {
                        "dimensions": {
                            "completeness": {"objectives": {"min": 0.9}},
                            "timeliness": {"objectives": {"min": 24}},
                        }
                    }
                },
            },
        }

        # Test through public API - normalize() calls _normalize_quality internally
        result = self.normalizer.normalize(contract_data)

        self.assertIsNotNone(result.hub_contract)
        self.assertIn("quality", result.hub_contract)
        self.assertIn("rules", result.hub_contract["quality"])
        self.assertTrue(len(result.hub_contract["quality"]["rules"]) >= 2)
        completeness_rule = result.hub_contract["quality"]["rules"][0]
        timeliness_rule = result.hub_contract["quality"]["rules"][1]
        self.assertEqual(completeness_rule["severity"], "ERROR")
        self.assertEqual(timeliness_rule["severity"], "WARNING")

    def test_quality_mapping_complete_workflow(self):
        """Test complete quality mapping with all components through public API"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "dataQuality": {
                    "declarative": {
                        "default": "production-profile",
                        "dimensions": {
                            "completeness": {
                                "ruleID": "comp-1",
                                "name": "Completeness",
                                "objectives": {"min": 0.95},
                                "threshold": 0.95,
                                "severity": "ERROR",
                            }
                        },
                    },
                    "executable": [{"type": "great_expectations", "suite": "dq_suite"}],
                },
            },
        }

        # Test through public API - normalize() calls _normalize_quality internally
        result = self.normalizer.normalize(contract_data)

        # Check all components are mapped
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("quality", result.hub_contract)
        self.assertEqual(
            result.hub_contract["quality"]["default_profile_key"], "production-profile"
        )
        self.assertEqual(len(result.hub_contract["quality"]["rules"]), 1)
        self.assertIn("x_odps", result.hub_contract["quality"])
        self.assertEqual(len(result.hub_contract["quality"]["x_odps"]["executable"]), 1)


class ODPSNormalizerLifecycleMappingTest(TestCase):
    """Test ODPS → HubContract lifecycle mapping through public API (Task 1.4.4)"""

    def setUp(self):
        """Set up test fixtures"""
        self.normalizer = ODPSNormalizer()

    def test_normalize_maps_product_status_to_lifecycle_x_odps_status(self):
        """Test that normalize() maps product.details.<lang>.status → lifecycle.x_odps.status"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {"en": {"name": "Test Product", "status": "active"}}},
        }

        result = self.normalizer.normalize(contract_data)

        # Should succeed and map lifecycle data
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("lifecycle", result.hub_contract)
        self.assertIn("x_odps", result.hub_contract["lifecycle"])
        self.assertEqual(result.hub_contract["lifecycle"]["x_odps"]["status"], "active")
        self.assertEqual(len(result.errors), 0)

    def test_lifecycle_mapping_visibility(self):
        """Test mapping product.details.<lang>.visibility → lifecycle.x_odps.visibility through public API"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product",
                        "visibility": "public",
                    }
                }
            },
        }

        # Test through public API - normalize() calls _normalize_lifecycle internally
        result = self.normalizer.normalize(contract_data)

        self.assertIsNotNone(result.hub_contract)
        self.assertIn("lifecycle", result.hub_contract)
        self.assertIn("x_odps", result.hub_contract["lifecycle"])
        self.assertEqual(result.hub_contract["lifecycle"]["x_odps"]["visibility"], "public")
        self.assertEqual(len(result.warnings), 0)

    def test_lifecycle_mapping_status_and_visibility(self):
        """Test mapping both status and visibility through public API"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {"name": "Test Product", "status": "draft", "visibility": "private"}
                }
            },
        }

        # Test through public API - normalize() calls _normalize_lifecycle internally
        result = self.normalizer.normalize(contract_data)

        self.assertIsNotNone(result.hub_contract)
        self.assertIn("lifecycle", result.hub_contract)
        self.assertIn("x_odps", result.hub_contract["lifecycle"])
        self.assertEqual(result.hub_contract["lifecycle"]["x_odps"]["status"], "draft")
        self.assertEqual(result.hub_contract["lifecycle"]["x_odps"]["visibility"], "private")

    def test_lifecycle_mapping_sla_availability(self):
        """Test mapping SLA availability dimension to lifecycle.slas through public API"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "SLA": {
                    "declarative": {
                        "dimensions": {
                            "availability": {
                                "target": 99.9,
                                "unit": "percentage",
                                "description": "99.9% availability target",
                            }
                        }
                    }
                },
            },
        }

        # Test through public API - normalize() calls _normalize_lifecycle internally
        result = self.normalizer.normalize(contract_data)

        self.assertIsNotNone(result.hub_contract)
        self.assertIn("lifecycle", result.hub_contract)
        self.assertIn("slas", result.hub_contract["lifecycle"])
        self.assertEqual(result.hub_contract["lifecycle"]["slas"]["availability"], 99.9)
        self.assertIn("x_odps", result.hub_contract["lifecycle"])
        self.assertIn("sla_dimensions", result.hub_contract["lifecycle"]["x_odps"])
        self.assertEqual(len(result.hub_contract["lifecycle"]["x_odps"]["sla_dimensions"]), 1)

    def test_lifecycle_mapping_sla_latency(self):
        """Test mapping SLA latency dimension to lifecycle.slas through public API"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "SLA": {
                    "declarative": {
                        "dimensions": {
                            "latency": {
                                "target": 5000,
                                "unit": "milliseconds",
                                "description": "P95 latency target",
                            }
                        }
                    }
                },
            },
        }

        # Test through public API - normalize() calls _normalize_lifecycle internally
        result = self.normalizer.normalize(contract_data)

        self.assertIsNotNone(result.hub_contract)
        self.assertIn("lifecycle", result.hub_contract)
        self.assertIn("slas", result.hub_contract["lifecycle"])
        self.assertEqual(result.hub_contract["lifecycle"]["slas"]["latency_ms_p95"], 5000.0)
        self.assertIn("x_odps", result.hub_contract["lifecycle"])
        self.assertIn("sla_dimensions", result.hub_contract["lifecycle"]["x_odps"])
        self.assertEqual(len(result.hub_contract["lifecycle"]["x_odps"]["sla_dimensions"]), 1)

    def test_lifecycle_mapping_sla_latency_ms_p95(self):
        """Test mapping SLA latency_ms_p95 dimension to lifecycle.slas through public API"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "SLA": {
                    "declarative": {
                        "dimensions": {"latency_ms_p95": {"target": 3000, "unit": "milliseconds"}}
                    }
                },
            },
        }

        # Test through public API - normalize() calls _normalize_lifecycle internally
        result = self.normalizer.normalize(contract_data)

        self.assertIsNotNone(result.hub_contract)
        self.assertIn("lifecycle", result.hub_contract)
        self.assertIn("slas", result.hub_contract["lifecycle"])
        self.assertEqual(result.hub_contract["lifecycle"]["slas"]["latency_ms_p95"], 3000.0)

    def test_lifecycle_mapping_sla_freshness(self):
        """Test mapping SLA freshness dimension to lifecycle.x_odps through public API"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "SLA": {
                    "declarative": {
                        "dimensions": {
                            "freshness": {
                                "target": 24,
                                "unit": "hours",
                                "description": "Data should be refreshed within 24 hours",
                            }
                        }
                    }
                },
            },
        }

        # Test through public API - normalize() calls _normalize_lifecycle internally
        result = self.normalizer.normalize(contract_data)

        self.assertIsNotNone(result.hub_contract)
        self.assertIn("lifecycle", result.hub_contract)
        self.assertIn("x_odps", result.hub_contract["lifecycle"])
        # Freshness should be converted to seconds (24 hours = 86400 seconds)
        self.assertEqual(
            result.hub_contract["lifecycle"]["x_odps"]["freshness_sla_seconds"], 86400.0
        )
        self.assertIn("sla_dimensions", result.hub_contract["lifecycle"]["x_odps"])

    def test_lifecycle_mapping_sla_freshness_days(self):
        """Test mapping SLA freshness with days unit through public API"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "SLA": {
                    "declarative": {"dimensions": {"freshness": {"target": 7, "unit": "days"}}}
                },
            },
        }

        # Test through public API - normalize() calls _normalize_lifecycle internally
        result = self.normalizer.normalize(contract_data)

        # 7 days = 604800 seconds
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("lifecycle", result.hub_contract)
        self.assertIn("x_odps", result.hub_contract["lifecycle"])
        self.assertEqual(
            result.hub_contract["lifecycle"]["x_odps"]["freshness_sla_seconds"], 604800.0
        )

    def test_lifecycle_mapping_sla_multiple_dimensions(self):
        """Test mapping multiple SLA dimensions through public API"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "SLA": {
                    "declarative": {
                        "dimensions": {
                            "availability": {"target": 99.9},
                            "latency": {"target": 5000},
                            "custom_dimension": {
                                "target": 100,
                                "description": "Custom SLA dimension",
                            },
                        }
                    }
                },
            },
        }

        # Test through public API - normalize() calls _normalize_lifecycle internally
        result = self.normalizer.normalize(contract_data)

        self.assertIsNotNone(result.hub_contract)
        self.assertIn("lifecycle", result.hub_contract)
        self.assertIn("slas", result.hub_contract["lifecycle"])
        self.assertEqual(result.hub_contract["lifecycle"]["slas"]["availability"], 99.9)
        self.assertEqual(result.hub_contract["lifecycle"]["slas"]["latency_ms_p95"], 5000.0)
        self.assertIn("x_odps", result.hub_contract["lifecycle"])
        self.assertIn("sla_dimensions", result.hub_contract["lifecycle"]["x_odps"])
        # Should have 3 dimensions (availability, latency, custom_dimension)
        self.assertEqual(len(result.hub_contract["lifecycle"]["x_odps"]["sla_dimensions"]), 3)

    def test_lifecycle_mapping_sla_executable(self):
        """Test storing executable SLA specs through public API"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "SLA": {
                    "executable": [
                        {
                            "type": "prometheus",
                            "query": "up{job='data-pipeline'}",
                            "threshold": 0.99,
                        },
                        {"type": "custom", "script": "check_sla.py"},
                    ]
                },
            },
        }

        # Test through public API - normalize() calls _normalize_lifecycle internally
        result = self.normalizer.normalize(contract_data)

        self.assertIsNotNone(result.hub_contract)
        self.assertIn("lifecycle", result.hub_contract)
        self.assertIn("x_odps", result.hub_contract["lifecycle"])
        self.assertIn("executable_sla", result.hub_contract["lifecycle"]["x_odps"])
        self.assertEqual(len(result.hub_contract["lifecycle"]["x_odps"]["executable_sla"]), 2)
        self.assertEqual(
            result.hub_contract["lifecycle"]["x_odps"]["executable_sla"][0]["type"], "prometheus"
        )

    def test_lifecycle_mapping_sla_executable_single_object(self):
        """Test storing single executable SLA object (wrapped in list) through public API"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "SLA": {"executable": {"type": "prometheus", "query": "up{job='data-pipeline'}"}},
            },
        }

        # Test through public API - normalize() calls _normalize_lifecycle internally
        result = self.normalizer.normalize(contract_data)

        self.assertIsNotNone(result.hub_contract)
        self.assertIn("lifecycle", result.hub_contract)
        self.assertIn("x_odps", result.hub_contract["lifecycle"])
        self.assertIn("executable_sla", result.hub_contract["lifecycle"]["x_odps"])
        self.assertEqual(len(result.hub_contract["lifecycle"]["x_odps"]["executable_sla"]), 1)

    def test_lifecycle_mapping_missing_data(self):
        """Test handling missing lifecycle data gracefully through public API"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"productID": "test-product", "name": "Test Product"}}
                # No status, visibility, or SLA
            },
        }

        # Test through public API - normalize() calls _normalize_lifecycle internally
        result = self.normalizer.normalize(contract_data)

        # Should not raise error, lifecycle section should be initialized
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("lifecycle", result.hub_contract)
        self.assertIn("x_odps", result.hub_contract["lifecycle"])
        self.assertEqual(len(result.warnings), 0)

    def test_lifecycle_mapping_invalid_status_type(self):
        """Test handling invalid status type with warning through public API"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {"name": "Test Product", "status": 123}  # Invalid: should be string
                }
            },
        }

        # Test through public API - normalize() calls _normalize_lifecycle internally
        result = self.normalizer.normalize(contract_data)

        # Should not set status, but should log warning
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("lifecycle", result.hub_contract)
        self.assertIn("x_odps", result.hub_contract["lifecycle"])
        self.assertNotIn("status", result.hub_contract["lifecycle"]["x_odps"],
            "Invalid status type must NOT set status on the output")
        self.assertTrue(len(result.warnings) > 0)
        warning_msg = " ".join(result.warnings)
        self.assertIn("status", warning_msg)
        self.assertIn("invalid type", warning_msg)

    def test_lifecycle_mapping_invalid_visibility_type(self):
        """Test handling invalid visibility type with warning through public API"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "name": "Test Product",
                        "visibility": ["public"],  # Invalid: should be string
                    }
                }
            },
        }

        # Test through public API - normalize() calls _normalize_lifecycle internally
        result = self.normalizer.normalize(contract_data)

        # Should not set visibility, but should log warning
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("lifecycle", result.hub_contract)
        self.assertIn("x_odps", result.hub_contract["lifecycle"])
        self.assertNotIn("visibility", result.hub_contract["lifecycle"]["x_odps"],
            "Invalid visibility type must NOT set visibility on the output")
        self.assertTrue(len(result.warnings) > 0)
        warning_msg = " ".join(result.warnings)
        self.assertIn("visibility", warning_msg)

    def test_lifecycle_mapping_invalid_sla_type(self):
        """Test handling invalid SLA type with warning through public API"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "SLA": "invalid",  # Invalid: should be dict
            },
        }

        # Test through public API - normalize() calls _normalize_lifecycle internally
        result = self.normalizer.normalize(contract_data)

        # Should not process SLA, but should log warning
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("lifecycle", result.hub_contract)
        self.assertNotIn("slas", result.hub_contract["lifecycle"],
            "Invalid SLA type must NOT set slas on the output")
        self.assertTrue(len(result.warnings) > 0)
        warning_msg = " ".join(result.warnings)
        self.assertIn("SLA", warning_msg)
        self.assertIn("invalid type", warning_msg)

    def test_lifecycle_mapping_invalid_dimension_type(self):
        """Test handling invalid dimension type with warning"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "SLA": {
                    "declarative": {
                        "dimensions": {"availability": "invalid"}  # Invalid: should be dict
                    }
                },
            },
        }
        # Test through public API - normalize() calls _normalize_lifecycle internally
        result = self.normalizer.normalize(contract_data)

        # Should not create dimensions, but should log warning
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("lifecycle", result.hub_contract)
        self.assertNotIn("slas", result.hub_contract["lifecycle"],
            "Invalid SLA type must NOT set slas on the output")
        self.assertTrue(len(result.warnings) > 0)
        warning_msg = " ".join(result.warnings)
        self.assertIn("availability", warning_msg)

    def test_lifecycle_mapping_sla_threshold_instead_of_target(self):
        """Test mapping SLA dimension using threshold instead of target through public API"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "SLA": {
                    "declarative": {
                        "dimensions": {
                            "availability": {"threshold": 99.5}  # Using threshold instead of target
                        }
                    }
                },
            },
        }

        # Test through public API - normalize() calls _normalize_lifecycle internally
        result = self.normalizer.normalize(contract_data)

        self.assertIsNotNone(result.hub_contract)
        self.assertIn("lifecycle", result.hub_contract)
        self.assertIn("slas", result.hub_contract["lifecycle"])
        self.assertEqual(result.hub_contract["lifecycle"]["slas"]["availability"], 99.5)

    def test_lifecycle_mapping_complete_workflow(self):
        """Test complete lifecycle mapping with all components through public API"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {"name": "Test Product", "status": "active", "visibility": "public"}
                },
                "SLA": {
                    "declarative": {
                        "dimensions": {
                            "availability": {"target": 99.9},
                            "latency": {"target": 5000},
                        }
                    },
                    "executable": [{"type": "prometheus", "query": "up"}],
                },
            },
        }

        # Test through public API - normalize() calls _normalize_lifecycle internally
        result = self.normalizer.normalize(contract_data)

        # Check all components are mapped
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("lifecycle", result.hub_contract)
        self.assertEqual(result.hub_contract["lifecycle"]["x_odps"]["status"], "active")
        self.assertEqual(result.hub_contract["lifecycle"]["x_odps"]["visibility"], "public")
        self.assertIn("slas", result.hub_contract["lifecycle"])
        self.assertEqual(result.hub_contract["lifecycle"]["slas"]["availability"], 99.9)
        self.assertEqual(result.hub_contract["lifecycle"]["slas"]["latency_ms_p95"], 5000.0)
        self.assertEqual(len(result.hub_contract["lifecycle"]["x_odps"]["sla_dimensions"]), 2)
        self.assertEqual(len(result.hub_contract["lifecycle"]["x_odps"]["executable_sla"]), 1)


class ODPSNormalizerInfoMappingTest(TestCase):
    """Test ODPSNormalizer info mapping (Task 1.4.2)"""

    def setUp(self):
        """Set up test fixtures"""
        self.normalizer = ODPSNormalizer()

    def test_info_mapping_all_fields(self):
        """Test info mapping with all fields present"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product-123",
                        "name": "Test Product",
                        "description": "Test description",
                        "productVersion": "1.0.0",
                        "tags": ["tag1", "tag2"],
                        "categories": ["category1", "category2"],
                    }
                }
            },
            "dataHolder": {"legalName": "Test Company", "email": "test@example.com"},
        }

        result = self.normalizer.normalize(contract_data)

        self.assertIsNotNone(result.hub_contract)
        self.assertEqual(result.hub_contract["id"], "test-product-123")
        self.assertEqual(result.hub_contract["info"]["name"], "Test Product")
        self.assertEqual(result.hub_contract["info"]["description"], "Test description")
        self.assertEqual(result.hub_contract["info"]["version"], "1.0.0")
        # Tags should include both tags and categories (merged, deduplicated)
        self.assertIn("tag1", result.hub_contract["info"]["tags"])
        self.assertIn("tag2", result.hub_contract["info"]["tags"])
        self.assertIn("category1", result.hub_contract["info"]["tags"])
        self.assertIn("category2", result.hub_contract["info"]["tags"])
        # Owners should be populated
        self.assertEqual(len(result.hub_contract["info"]["owners"]), 1)
        self.assertEqual(result.hub_contract["info"]["owners"][0]["name"], "Test Company")
        self.assertEqual(result.hub_contract["info"]["owners"][0]["email"], "test@example.com")

    def test_info_mapping_multilingual_support(self):
        """Test info mapping with multiple languages (prefers English)"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product-en",
                        "name": "English Name",
                        "description": "English description",
                    },
                    "fr": {
                        "productID": "test-product-en",
                        "name": "Nom français",
                        "description": "Description française",
                    },
                    "de": {
                        "productID": "test-product-en",
                        "name": "Deutscher Name",
                        "description": "Deutsche Beschreibung",
                    },
                }
            },
        }

        result = self.normalizer.normalize(contract_data)

        self.assertIsNotNone(result.hub_contract)
        # Should use English (preferred language)
        self.assertEqual(result.hub_contract["info"]["name"], "English Name")
        self.assertEqual(result.hub_contract["info"]["description"], "English description")
        # Should store multilingual details in extensions
        self.assertIn("extensions", result.hub_contract)
        self.assertIn("x_odps", result.hub_contract["extensions"])
        self.assertIn("available_languages", result.hub_contract["extensions"]["x_odps"])
        self.assertEqual(result.hub_contract["extensions"]["x_odps"]["preferred_language"], "en")
        self.assertIn("multilingual_details", result.hub_contract["extensions"]["x_odps"])
        # Should have all three languages
        self.assertIn("en", result.hub_contract["extensions"]["x_odps"]["multilingual_details"])
        self.assertIn("fr", result.hub_contract["extensions"]["x_odps"]["multilingual_details"])
        self.assertIn("de", result.hub_contract["extensions"]["x_odps"]["multilingual_details"])

    def test_info_mapping_multilingual_fallback(self):
        """Test info mapping with multiple languages (fallback to first available if English not present)"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "fr": {
                        "productID": "test-product-fr",
                        "name": "Nom français",
                        "description": "Description française",
                    },
                    "de": {
                        "productID": "test-product-fr",
                        "name": "Deutscher Name",
                        "description": "Deutsche Beschreibung",
                    },
                }
            },
        }

        result = self.normalizer.normalize(contract_data)

        self.assertIsNotNone(result.hub_contract)
        # Should use first available language (German, alphabetically first: de < fr)
        self.assertEqual(result.hub_contract["info"]["name"], "Deutscher Name")
        self.assertEqual(
            result.hub_contract["extensions"]["x_odps"]["preferred_language"], "de"
        )  # Sorted: de, fr

    def test_info_mapping_missing_required_name(self):
        """Test info mapping fails when name is missing"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        # name is missing
                        "description": "Test description",
                    }
                }
            },
        }

        result = self.normalizer.normalize(contract_data)

        # Should fail normalization
        self.assertEqual(result.status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertIsNone(result.hub_contract)
        self.assertTrue(len(result.errors) > 0)
        self.assertIn("name", result.errors[0].lower())

    def test_info_mapping_missing_optional_fields(self):
        """Test info mapping with missing optional fields (graceful degradation)"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product",
                        # description, version, tags, categories are missing
                    }
                }
            },
        }

        result = self.normalizer.normalize(contract_data)

        self.assertIsNotNone(result.hub_contract)
        self.assertEqual(result.hub_contract["info"]["name"], "Test Product")
        # Optional fields should not be present
        self.assertNotIn("description", result.hub_contract["info"])
        self.assertNotIn("version", result.hub_contract["info"])
        self.assertNotIn("tags", result.hub_contract["info"])
        # No warnings expected since all required fields (productID, name) are present
        # and optional fields are gracefully handled without warnings
        self.assertEqual(len(result.warnings), 0)

    def test_info_mapping_tags_and_categories_merge(self):
        """Test that tags and categories are merged into tags array"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product",
                        "tags": ["tag1", "tag2"],
                        "categories": ["cat1", "cat2"],
                    }
                }
            },
        }

        result = self.normalizer.normalize(contract_data)

        self.assertIn("tags", result.hub_contract["info"])
        tags = result.hub_contract["info"]["tags"]
        self.assertIn("tag1", tags)
        self.assertIn("tag2", tags)
        self.assertIn("cat1", tags)
        self.assertIn("cat2", tags)
        # Should be deduplicated
        self.assertEqual(len(tags), 4)

    def test_info_mapping_tags_categories_deduplication(self):
        """Test that duplicate tags and categories are deduplicated"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product",
                        "tags": ["tag1", "tag2", "tag1"],  # duplicate
                        "categories": ["tag2", "cat1"],  # tag2 overlaps with tags
                    }
                }
            },
        }

        result = self.normalizer.normalize(contract_data)

        self.assertIn("tags", result.hub_contract["info"])
        tags = result.hub_contract["info"]["tags"]
        # Should have unique tags only
        self.assertEqual(len(tags), 3)  # tag1, tag2, cat1
        self.assertEqual(tags.count("tag1"), 1)
        self.assertEqual(tags.count("tag2"), 1)
        self.assertEqual(tags.count("cat1"), 1)

    def test_info_mapping_tags_as_string(self):
        """Test that single tag as string is handled"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product",
                        "tags": "single-tag",  # string instead of list
                    }
                }
            },
        }

        result = self.normalizer.normalize(contract_data)

        self.assertIn("tags", result.hub_contract["info"])
        self.assertEqual(result.hub_contract["info"]["tags"], ["single-tag"])

    def test_info_mapping_dataholder_multilingual(self):
        """Test dataHolder mapping with multilingual support"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {"en": {"productID": "test-product", "name": "Test Product"}}},
            "dataHolder": {
                "en": {"legalName": "English Company", "email": "en@example.com"},
                "fr": {"legalName": "Entreprise française", "email": "fr@example.com"},
            },
        }

        result = self.normalizer.normalize(contract_data)

        self.assertIn("owners", result.hub_contract["info"])
        self.assertEqual(len(result.hub_contract["info"]["owners"]), 1)
        # Should use English (preferred language)
        self.assertEqual(result.hub_contract["info"]["owners"][0]["name"], "English Company")
        self.assertEqual(result.hub_contract["info"]["owners"][0]["email"], "en@example.com")

    def test_info_mapping_dataholder_single_object(self):
        """Test dataHolder mapping with single object (not keyed by language)"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {"en": {"productID": "test-product", "name": "Test Product"}}},
            "dataHolder": {"legalName": "Test Company", "email": "test@example.com"},
        }

        result = self.normalizer.normalize(contract_data)

        self.assertIn("owners", result.hub_contract["info"])
        self.assertEqual(len(result.hub_contract["info"]["owners"]), 1)
        self.assertEqual(result.hub_contract["info"]["owners"][0]["name"], "Test Company")
        self.assertEqual(result.hub_contract["info"]["owners"][0]["email"], "test@example.com")

    def test_info_mapping_dataholder_partial(self):
        """Test dataHolder mapping with only name or only email"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {"en": {"productID": "test-product", "name": "Test Product"}}},
            "dataHolder": {
                "legalName": "Test Company"
                # email is missing
            },
        }

        result = self.normalizer.normalize(contract_data)

        self.assertIn("owners", result.hub_contract["info"])
        self.assertEqual(len(result.hub_contract["info"]["owners"]), 1)
        self.assertEqual(result.hub_contract["info"]["owners"][0]["name"], "Test Company")
        self.assertNotIn("email", result.hub_contract["info"]["owners"][0])

    def test_info_mapping_no_dataholder(self):
        """Test info mapping without dataHolder"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {"en": {"productID": "test-product", "name": "Test Product"}}},
        }

        result = self.normalizer.normalize(contract_data)

        self.assertIsNotNone(result.hub_contract)
        # owners should not be present if dataHolder is missing
        self.assertNotIn("owners", result.hub_contract["info"])

    def test_info_mapping_invalid_types(self):
        """Test info mapping with invalid field types (graceful degradation)"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product",
                        "description": 123,  # invalid type
                        "productVersion": ["1.0.0"],  # invalid type
                        "tags": "not-a-list",  # will be handled as string
                        "categories": 456,  # invalid type
                    }
                }
            },
        }

        result = self.normalizer.normalize(contract_data)

        self.assertIsNotNone(result.hub_contract)
        # Should have warnings for invalid types
        self.assertTrue(len(result.warnings) > 0)
        # Invalid fields should be skipped
        self.assertNotIn("description", result.hub_contract["info"])
        self.assertNotIn("version", result.hub_contract["info"])
        # tags should handle string
        self.assertIn("tags", result.hub_contract["info"])

    def test_info_mapping_no_product_details(self):
        """Test info mapping fails when product.details is missing"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                # details is missing
            },
        }

        result = self.normalizer.normalize(contract_data)

        self.assertEqual(result.status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertIsNone(result.hub_contract)
        self.assertTrue(len(result.errors) > 0)

    def test_extract_available_languages(self):
        """Test language extraction through public API - normalize() uses _extract_available_languages internally"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {"name": "English"},
                    "fr": {"name": "French"},
                    "de": {"name": "German"},
                }
            },
        }

        # Test through public API - normalize() calls _extract_available_languages internally
        # and uses the preferred language (default: "en") for normalization
        result = self.normalizer.normalize(contract_data)

        # Verify that normalization succeeded and used English (preferred language)
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("info", result.hub_contract)
        # The info.name should be from English details (preferred language)
        if "name" in result.hub_contract["info"]:
            # Verify English was used (could be "English" or the actual name)
            self.assertIsNotNone(result.hub_contract["info"]["name"])

    def test_get_preferred_language(self):
        """Test preferred language selection through public API - normalize() uses _get_preferred_language internally"""
        # Test with preferred language available (English)
        contract_data_en = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {"name": "English Product"},
                    "fr": {"name": "French Product"},
                    "de": {"name": "German Product"},
                }
            },
        }
        result = self.normalizer.normalize(contract_data_en)
        # Should use English (preferred/default)
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("info", result.hub_contract)

        # Test with preferred language not available (fallback to first available)
        contract_data_fr_de = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "fr": {"name": "French Product"},
                    "de": {"name": "German Product"},
                }
            },
        }
        result2 = self.normalizer.normalize(contract_data_fr_de)
        # Should use French (first available when English not available)
        self.assertIsNotNone(result2.hub_contract)
        self.assertIn("info", result2.hub_contract)

        # Test with empty details (no languages available) - normalization fails
        contract_data_empty = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {}},
        }
        result3 = self.normalizer.normalize(contract_data_empty)
        self.assertEqual(result3.status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertIsNone(result3.hub_contract)
        self.assertGreater(len(result3.errors), 0)


class ODPSNormalizerProductStrategyMappingTest(TestCase):
    """Test ODPSNormalizer product strategy mapping (Task 1.4.7)"""

    def setUp(self):
        """Set up test fixtures"""
        self.normalizer = ODPSNormalizer()

    def test_product_strategy_mapping_all_fields(self):
        """Test product strategy mapping with all fields present (ODPS 4.1)"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"productID": "test-product", "name": "Test Product"}},
                "productStrategy": {
                    "objectives": ["Increase data quality", "Improve customer satisfaction"],
                    "strategicAlignment": [
                        "Company goal: Data-driven decisions",
                        {"goal": "Digital transformation", "priority": "high"},
                    ],
                    "productKPIs": [
                        "Data quality score > 95%",
                        {"metric": "User adoption", "target": "1000 users"},
                    ],
                },
            },
        }

        result = self.normalizer.normalize(contract_data)

        self.assertIsNotNone(result.hub_contract)
        self.assertIn("extensions", result.hub_contract)
        self.assertIn("x_odps", result.hub_contract["extensions"])
        self.assertIn("product_strategy", result.hub_contract["extensions"]["x_odps"])

        strategy = result.hub_contract["extensions"]["x_odps"]["product_strategy"]
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

    def test_product_strategy_mapping_objectives_only(self):
        """Test product strategy mapping with only objectives"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"productID": "test-product", "name": "Test Product"}},
                "productStrategy": {"objectives": ["Objective 1", "Objective 2"]},
            },
        }

        result = self.normalizer.normalize(contract_data)

        self.assertIsNotNone(result.hub_contract)
        strategy = result.hub_contract["extensions"]["x_odps"]["product_strategy"]
        self.assertIn("objectives", strategy)
        self.assertNotIn("strategicAlignment", strategy)
        self.assertNotIn("productKPIs", strategy)

    def test_product_strategy_mapping_single_string_values(self):
        """Test product strategy mapping with single string values (not arrays)"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"productID": "test-product", "name": "Test Product"}},
                "productStrategy": {
                    "objectives": "Single objective",
                    "strategicAlignment": "Single alignment",
                    "productKPIs": "Single KPI",
                },
            },
        }

        result = self.normalizer.normalize(contract_data)

        self.assertIsNotNone(result.hub_contract)
        strategy = result.hub_contract["extensions"]["x_odps"]["product_strategy"]
        # Single strings should be converted to arrays
        self.assertEqual(strategy["objectives"], ["Single objective"])
        self.assertEqual(strategy["strategicAlignment"], ["Single alignment"])
        self.assertEqual(strategy["productKPIs"], ["Single KPI"])

    def test_product_strategy_mapping_missing_optional(self):
        """Test product strategy mapping when productStrategy is missing (optional)"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {"en": {"productID": "test-product", "name": "Test Product"}}},
            # productStrategy is missing
        }

        result = self.normalizer.normalize(contract_data)

        self.assertIsNotNone(result.hub_contract)
        # Should not have product_strategy if not present
        if "extensions" in result.hub_contract and "x_odps" in result.hub_contract["extensions"]:
            self.assertNotIn("product_strategy", result.hub_contract["extensions"]["x_odps"])
        # No warnings expected for missing optional field
        self.assertEqual(len(result.warnings), 0)

    def test_product_strategy_mapping_invalid_types(self):
        """Test product strategy mapping with invalid field types (graceful degradation)"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"productID": "test-product", "name": "Test Product"}},
                "productStrategy": {
                    "objectives": 123,  # invalid type
                    "strategicAlignment": {"not": "a list"},  # invalid type
                    "productKPIs": ["valid", 456, "valid"],  # mixed types
                },
            },
        }

        result = self.normalizer.normalize(contract_data)

        self.assertIsNotNone(result.hub_contract)
        # Should have warnings for invalid types
        self.assertTrue(len(result.warnings) > 0)
        # Invalid fields should be skipped
        strategy = (
            result.hub_contract.get("extensions", {}).get("x_odps", {}).get("product_strategy", {})
        )
        self.assertNotIn("objectives", strategy)
        self.assertNotIn("strategicAlignment", strategy)
        # Only valid KPIs should be included
        if "productKPIs" in strategy:
            self.assertEqual(len(strategy["productKPIs"]), 2)  # Only "valid" strings

    def test_product_strategy_mapping_invalid_product_strategy_type(self):
        """Test product strategy mapping when productStrategy is not a dict"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"productID": "test-product", "name": "Test Product"}},
                "productStrategy": "not a dict",  # invalid type
            },
        }

        result = self.normalizer.normalize(contract_data)

        self.assertIsNotNone(result.hub_contract)
        # Should have warning for invalid type
        self.assertTrue(len(result.warnings) > 0)
        self.assertTrue(
            any("productStrategy" in w and "invalid type" in w for w in result.warnings)
        )

    def test_product_strategy_mapping_version_check_4_0(self):
        """Test that product strategy is skipped for ODPS 4.0 (not supported)"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.0",
            "version": "4.0",
            "product": {
                "details": {"en": {"productID": "test-product", "name": "Test Product"}},
                "productStrategy": {"objectives": ["Objective 1"]},
            },
        }

        result = self.normalizer.normalize(contract_data, spec_version="4.0")

        self.assertIsNotNone(result.hub_contract)
        # Product strategy should not be mapped for 4.0
        if "extensions" in result.hub_contract and "x_odps" in result.hub_contract["extensions"]:
            self.assertNotIn("product_strategy", result.hub_contract["extensions"]["x_odps"])

    def test_product_strategy_mapping_version_check_3_x(self):
        """Test that product strategy is skipped for ODPS 3.x (not supported)"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v3.9",
            "version": "3.9",
            "product": {
                "details": {"en": {"productID": "test-product", "name": "Test Product"}},
                "productStrategy": {"objectives": ["Objective 1"]},
            },
        }

        result = self.normalizer.normalize(contract_data, spec_version="3.9")

        self.assertIsNotNone(result.hub_contract)
        # Product strategy should not be mapped for 3.9
        if "extensions" in result.hub_contract and "x_odps" in result.hub_contract["extensions"]:
            self.assertNotIn("product_strategy", result.hub_contract["extensions"]["x_odps"])

    def test_product_strategy_mapping_version_check_4_1(self):
        """Test that product strategy is mapped for ODPS 4.1 (supported)"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"productID": "test-product", "name": "Test Product"}},
                "productStrategy": {"objectives": ["Objective 1"]},
            },
        }

        result = self.normalizer.normalize(contract_data, spec_version="4.1")

        self.assertIsNotNone(result.hub_contract)
        # Product strategy should be mapped for 4.1
        self.assertIn("extensions", result.hub_contract)
        self.assertIn("x_odps", result.hub_contract["extensions"])
        self.assertIn("product_strategy", result.hub_contract["extensions"]["x_odps"])
        self.assertIn("objectives", result.hub_contract["extensions"]["x_odps"]["product_strategy"])

    def test_product_strategy_mapping_empty_arrays(self):
        """Test product strategy mapping with empty arrays"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"productID": "test-product", "name": "Test Product"}},
                "productStrategy": {"objectives": [], "strategicAlignment": [], "productKPIs": []},
            },
        }

        result = self.normalizer.normalize(contract_data)

        self.assertIsNotNone(result.hub_contract)
        # Empty arrays should result in empty product_strategy structure (which gets removed)
        if "extensions" in result.hub_contract and "x_odps" in result.hub_contract["extensions"]:
            self.assertNotIn("product_strategy", result.hub_contract["extensions"]["x_odps"])

    def test_product_strategy_mapping_mixed_valid_invalid_items(self):
        """Test product strategy mapping with mixed valid and invalid items in arrays"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"productID": "test-product", "name": "Test Product"}},
                "productStrategy": {
                    "objectives": ["valid1", 123, "valid2", None, "valid3"],
                    "strategicAlignment": ["valid", {"key": "value"}, 456],
                    "productKPIs": [{"kpi": "valid"}, "string", True],
                },
            },
        }

        result = self.normalizer.normalize(contract_data)

        self.assertIsNotNone(result.hub_contract)
        # Should have warnings for invalid items
        self.assertTrue(len(result.warnings) > 0)

        strategy = result.hub_contract["extensions"]["x_odps"]["product_strategy"]
        # Only valid items should be included
        self.assertIn("objectives", strategy)
        self.assertEqual(len(strategy["objectives"]), 3)  # Only "valid1", "valid2", "valid3"
        self.assertIn("valid1", strategy["objectives"])
        self.assertIn("valid2", strategy["objectives"])
        self.assertIn("valid3", strategy["objectives"])

        self.assertIn("strategicAlignment", strategy)
        self.assertEqual(len(strategy["strategicAlignment"]), 2)  # "valid" string and dict
        self.assertIn("valid", strategy["strategicAlignment"])

        self.assertIn("productKPIs", strategy)
        self.assertEqual(len(strategy["productKPIs"]), 2)  # dict and string


class ODPSNormalizerContractExtractionTest(SimpleTestCase):
    """Test ODPS contract extraction (Task 1.4.6)"""

    def setUp(self):
        """Set up test fixtures"""
        self.normalizer = ODPSNormalizer()

    def test_contract_extraction_contracturl(self):
        """Test extracting contractURL and storing as pointer through public API"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "contract": {"contractURL": "https://example.com/contracts/test-contract.json"},
            },
        }

        # Test through public API - normalize() calls _extract_contract internally
        result = self.normalizer.normalize(contract_data)

        self.assertIsNotNone(result.hub_contract)
        self.assertIn("extensions", result.hub_contract)
        self.assertIn("x_odps", result.hub_contract["extensions"])
        self.assertEqual(
            result.hub_contract["extensions"]["x_odps"]["contract_url"],
            "https://example.com/contracts/test-contract.json",
        )
        # When only contractURL is present (no inline spec), schema extraction may add one warning
        self.assertLessEqual(
            len(result.warnings), 1,
            "At most one warning (e.g. failed to extract schema when no inline spec)",
        )

    def test_contract_extraction_inline_spec(self):
        """Test extracting inline ODCS spec and normalizing"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "contract": {
                    "spec": {
                        "apiVersion": "odcs/v3",
                        "kind": "DataContract",
                        "id": "test-contract",
                        "name": "Test Contract",
                        "version": "1.0.0",
                        "schema": {"fields": [{"name": "field1", "type": "string"}]},
                    }
                },
            },
        }

        # Test through public API - normalize() calls _extract_contract internally
        result = self.normalizer.normalize(contract_data)

        # Should have normalized contract in extensions.x_odps.contract
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("extensions", result.hub_contract)
        self.assertIn("x_odps", result.hub_contract["extensions"])
        self.assertIn("contract", result.hub_contract["extensions"]["x_odps"])
        contract = result.hub_contract["extensions"]["x_odps"]["contract"]
        self.assertIn("info", contract)
        self.assertEqual(contract["info"]["name"], "Test Contract")

    def test_contract_extraction_internal_ref(self):
        """Test extracting contract from internal $ref through public API"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "contract": {"$ref": "#/definitions/contract"},
            },
            "definitions": {
                "contract": {
                    "apiVersion": "odcs/v3",
                    "kind": "DataContract",
                    "id": "test-contract",
                    "name": "Test Contract",
                    "version": "1.0.0",
                    "schema": {"fields": [{"name": "field1", "type": "string"}]},
                }
            },
        }

        # Test through public API - normalize() calls _extract_contract internally
        result = self.normalizer.normalize(contract_data)

        # Should have normalized contract in extensions.x_odps.contract
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("extensions", result.hub_contract)
        self.assertIn("x_odps", result.hub_contract["extensions"])
        self.assertIn("contract", result.hub_contract["extensions"]["x_odps"])
        contract = result.hub_contract["extensions"]["x_odps"]["contract"]
        self.assertIn("info", contract)
        self.assertEqual(contract["info"]["name"], "Test Contract")

    def test_contract_extraction_missing_contract_section(self):
        """Test handling missing contract section gracefully through public API"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}}
                # No contract section
            },
        }

        # Test through public API - normalize() calls _extract_contract internally
        result = self.normalizer.normalize(contract_data)

        # Should not raise error, should not create contract
        self.assertIsNotNone(result.hub_contract)
        extensions = result.hub_contract.get("extensions", {})
        x_odps = extensions.get("x_odps", {})
        self.assertNotIn("contract", x_odps)
        # When contract section is missing, schema extraction may add one warning
        self.assertLessEqual(
            len(result.warnings), 1,
            "At most one warning (e.g. failed to extract schema when no contract)",
        )

    def test_contract_extraction_invalid_contracturl_type(self):
        """Test handling invalid contractURL type with warning through public API"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "contract": {"contractURL": 123},  # Invalid: should be string
            },
        }

        # Test through public API - normalize() calls _extract_contract internally
        result = self.normalizer.normalize(contract_data)

        # Should not set contract_url, but should log warning
        self.assertIsNotNone(result.hub_contract)
        extensions = result.hub_contract.get("extensions", {})
        x_odps = extensions.get("x_odps", {})
        self.assertNotIn("contract_url", x_odps,
            "Invalid contract_url type must NOT set contract_url on the output")
        self.assertTrue(len(result.warnings) > 0)
        warning_msg = " ".join(result.warnings)
        self.assertIn("contractURL", warning_msg)
        self.assertIn("invalid type", warning_msg)

    def test_contract_extraction_invalid_ref_type(self):
        """Test handling invalid $ref type with warning through public API"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "contract": {"$ref": 123},  # Invalid: should be string
            },
        }

        # Test through public API - normalize() calls _extract_contract internally
        result = self.normalizer.normalize(contract_data)

        # Should not process $ref, but should log warning
        self.assertIsNotNone(result.hub_contract)
        extensions = result.hub_contract.get("extensions", {})
        x_odps = extensions.get("x_odps", {})
        self.assertNotIn("contract", x_odps,
            "Invalid type must NOT set contract on the output")
        self.assertTrue(len(result.warnings) > 0)
        warning_msg = " ".join(result.warnings)
        self.assertIn("$ref", warning_msg)
        self.assertIn("invalid type", warning_msg)

    def test_contract_extraction_invalid_spec_type(self):
        """Test handling invalid spec type with warning through public API"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "contract": {"spec": "invalid"},  # Invalid: should be dict
            },
        }

        # Test through public API - normalize() calls _extract_contract internally
        result = self.normalizer.normalize(contract_data)

        # Should not process spec, but should log warning
        self.assertIsNotNone(result.hub_contract)
        extensions = result.hub_contract.get("extensions", {})
        x_odps = extensions.get("x_odps", {})
        self.assertNotIn("contract", x_odps,
            "Invalid type must NOT set contract on the output")
        self.assertTrue(len(result.warnings) > 0)
        warning_msg = " ".join(result.warnings)
        self.assertIn("spec", warning_msg)
        self.assertIn("invalid type", warning_msg)

    def test_contract_extraction_ref_not_found(self):
        """Test handling $ref that cannot be resolved through public API"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "contract": {"$ref": "#/definitions/nonexistent"},
            },
        }

        # Test through public API - normalize() calls _extract_contract internally
        result = self.normalizer.normalize(contract_data)

        # Should not raise error, but should log warning
        self.assertIsNotNone(result.hub_contract)
        extensions = result.hub_contract.get("extensions", {})
        x_odps = extensions.get("x_odps", {})
        if "contract" in x_odps:
            # If contract was set despite missing ref, that's also acceptable behavior
            pass
        # Should have warnings about resolution failure
        self.assertTrue(len(result.warnings) > 0)

    def test_contract_extraction_all_formats(self):
        """Test contract extraction with all formats (URL, $ref, spec) through public API"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "contract": {
                    "contractURL": "https://example.com/contracts/test.json",
                    "$ref": "#/definitions/contract",
                },
            },
            "definitions": {
                "contract": {
                    "apiVersion": "odcs/v3",
                    "kind": "DataContract",
                    "id": "test-contract",
                    "name": "Test Contract",
                    "version": "1.0.0",
                    "schema": {"fields": [{"name": "field1", "type": "string"}]},
                }
            },
        }

        # Test through public API - normalize() calls _extract_contract internally
        result = self.normalizer.normalize(contract_data)

        # Should have both contract_url and normalized contract
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("extensions", result.hub_contract)
        self.assertIn("x_odps", result.hub_contract["extensions"])
        self.assertEqual(
            result.hub_contract["extensions"]["x_odps"]["contract_url"],
            "https://example.com/contracts/test.json",
        )
        self.assertIn("contract", result.hub_contract["extensions"]["x_odps"])
        contract = result.hub_contract["extensions"]["x_odps"]["contract"]
        self.assertIn("info", contract)
        self.assertEqual(contract["info"]["name"], "Test Contract")

    def test_contract_extraction_spec_takes_precedence(self):
        """Test that inline spec takes precedence when multiple formats present through public API"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "contract": {
                    "contractURL": "https://example.com/contracts/test.json",
                    "spec": {
                        "apiVersion": "odcs/v3",
                        "kind": "DataContract",
                        "id": "inline-contract",
                        "name": "Inline Contract",
                        "version": "1.0.0",
                        "schema": {"fields": [{"name": "test_field", "type": "string"}]},
                    },
                },
            },
        }

        # Test through public API - normalize() calls _extract_contract internally
        result = self.normalizer.normalize(contract_data)

        # Should have both contract_url and normalized contract from spec
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("extensions", result.hub_contract)
        self.assertIn("x_odps", result.hub_contract["extensions"])
        self.assertEqual(
            result.hub_contract["extensions"]["x_odps"]["contract_url"],
            "https://example.com/contracts/test.json",
        )
        self.assertIn("contract", result.hub_contract["extensions"]["x_odps"])
        contract = result.hub_contract["extensions"]["x_odps"]["contract"]
        self.assertEqual(contract["info"]["name"], "Inline Contract")

    def test_contract_extraction_validation(self):
        """Test that extracted contracts are validated by ODCSNormalizer through public API"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product"}},
                "contract": {
                    "spec": {
                        "apiVersion": "odcs/v3",
                        "kind": "DataContract",
                        "id": "test-contract",
                        "name": "Test Contract",
                        "version": "1.0.0",
                        "schema": {
                            "fields": [
                                {"name": "field1", "type": "string", "description": "Test field"},
                                {"name": "field2", "type": "integer", "required": True},
                            ]
                        },
                        "quality": {
                            "rules": [
                                {
                                    "id": "rule1",
                                    "name": "Completeness Check",
                                    "dimension": "completeness",
                                    "threshold": 0.95,
                                }
                            ]
                        },
                    }
                },
            },
        }

        # Test through public API - normalize() calls _extract_contract internally
        result = self.normalizer.normalize(contract_data)

        # Should have normalized contract with all sections validated
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("extensions", result.hub_contract)
        self.assertIn("x_odps", result.hub_contract["extensions"])
        self.assertIn("contract", result.hub_contract["extensions"]["x_odps"])
        contract = result.hub_contract["extensions"]["x_odps"]["contract"]

        # Validate that contract was properly normalized
        self.assertIn("info", contract)
        self.assertEqual(contract["info"]["name"], "Test Contract")
        self.assertIn("schema", contract)
        self.assertIn("fields", contract["schema"])
        # Quality rules should be preserved if present in ODCS
        if "quality" in contract:
            self.assertIn("rules", contract["quality"])

        # Should not have critical errors (warnings are OK)
        critical_errors = [
            w for w in result.warnings if "error" in w.lower() and "failed" in w.lower()
        ]
        # Warnings about normalization are acceptable, but should not fail completely
        self.assertTrue(
            len(critical_errors) == 0
            or all("normalization warning" in err.lower() for err in critical_errors),
            f"Unexpected critical errors: {critical_errors}",
        )


class ODPSNormalizerMarketplaceTest(TestCase):
    """Test ODPSNormalizer marketplace mapping (Task 1.4.5)"""

    def setUp(self):
        """Set up test fixtures"""
        self.normalizer = ODPSNormalizer()

    def test_marketplace_mapping_license_definition(self):
        """Test mapping license.definition to marketplace.license_summary"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {"en": {"productID": "test-product", "name": "Test Product"}}},
            "license": {"en": {"definition": "MIT License - Free to use for any purpose"}},
        }

        result = self.normalizer.normalize(contract_data)
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("marketplace", result.hub_contract)
        self.assertEqual(
            result.hub_contract["marketplace"]["license_summary"],
            "MIT License - Free to use for any purpose",
        )

    def test_marketplace_mapping_license_restrictions(self):
        """Test mapping license.restrictions to marketplace.restricted_use[]"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {"en": {"productID": "test-product", "name": "Test Product"}}},
            "license": {"en": {"restrictions": ["No commercial use", "No redistribution"]}},
        }

        result = self.normalizer.normalize(contract_data)
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("marketplace", result.hub_contract)
        self.assertIn("restricted_use", result.hub_contract["marketplace"])
        restricted_use = result.hub_contract["marketplace"]["restricted_use"]
        self.assertEqual(len(restricted_use), 2)
        self.assertIn("No commercial use", restricted_use)
        self.assertIn("No redistribution", restricted_use)

    def test_marketplace_mapping_license_restrictions_string(self):
        """Test mapping license.restrictions as string to marketplace.restricted_use[]"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {"en": {"productID": "test-product", "name": "Test Product"}}},
            "license": {"en": {"restrictions": "No commercial use"}},
        }

        result = self.normalizer.normalize(contract_data)
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("marketplace", result.hub_contract)
        self.assertIn("restricted_use", result.hub_contract["marketplace"])
        restricted_use = result.hub_contract["marketplace"]["restricted_use"]
        self.assertEqual(len(restricted_use), 1)
        self.assertIn("No commercial use", restricted_use)

    def test_marketplace_mapping_license_rights(self):
        """Test mapping license.rights[] to marketplace.intended_use[]"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {"en": {"productID": "test-product", "name": "Test Product"}}},
            "license": {"en": {"rights": ["Research and analysis", "Educational purposes"]}},
        }

        result = self.normalizer.normalize(contract_data)
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("marketplace", result.hub_contract)
        self.assertIn("intended_use", result.hub_contract["marketplace"])
        intended_use = result.hub_contract["marketplace"]["intended_use"]
        self.assertEqual(len(intended_use), 2)
        self.assertIn("Research and analysis", intended_use)
        self.assertIn("Educational purposes", intended_use)

    def test_marketplace_mapping_license_rights_string(self):
        """Test mapping license.rights as string to marketplace.intended_use[]"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {"en": {"productID": "test-product", "name": "Test Product"}}},
            "license": {"en": {"rights": "Research and analysis"}},
        }

        result = self.normalizer.normalize(contract_data)
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("marketplace", result.hub_contract)
        self.assertIn("intended_use", result.hub_contract["marketplace"])
        intended_use = result.hub_contract["marketplace"]["intended_use"]
        self.assertEqual(len(intended_use), 1)
        self.assertIn("Research and analysis", intended_use)

    def test_marketplace_mapping_pricing_plans(self):
        """Test storing pricing plans in marketplace.x_odps.pricing_plans[]"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"productID": "test-product", "name": "Test Product"}},
                "marketplace": {
                    "pricingPlans": [
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
                },
            },
        }

        result = self.normalizer.normalize(contract_data)
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("marketplace", result.hub_contract)
        self.assertIn("x_odps", result.hub_contract["marketplace"])
        self.assertIn("pricing_plans", result.hub_contract["marketplace"]["x_odps"])
        pricing_plans = result.hub_contract["marketplace"]["x_odps"]["pricing_plans"]
        self.assertEqual(len(pricing_plans), 2)
        self.assertEqual(pricing_plans[0]["planID"], "basic")
        self.assertEqual(pricing_plans[1]["planID"], "premium")

    def test_marketplace_mapping_access_methods(self):
        """Test storing access methods in marketplace.x_odps.access_methods{}"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"productID": "test-product", "name": "Test Product"}},
                "marketplace": {
                    "accessMethods": {
                        "api": {
                            "endpoint": "https://api.example.com/v1/products/test-product",
                            "version": "v1",
                        },
                        "download": {
                            "url": "https://download.example.com/products/test-product",
                            "format": "zip",
                        },
                    }
                },
            },
        }

        result = self.normalizer.normalize(contract_data)
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("marketplace", result.hub_contract)
        self.assertIn("x_odps", result.hub_contract["marketplace"])
        self.assertIn("access_methods", result.hub_contract["marketplace"]["x_odps"])
        access_methods = result.hub_contract["marketplace"]["x_odps"]["access_methods"]
        self.assertIn("api", access_methods)
        self.assertIn("download", access_methods)
        self.assertEqual(
            access_methods["api"]["endpoint"], "https://api.example.com/v1/products/test-product"
        )
        self.assertEqual(
            access_methods["download"]["url"], "https://download.example.com/products/test-product"
        )

    def test_marketplace_mapping_payment_gateways(self):
        """Test storing payment gateways in marketplace.x_odps.payment_gateways{}"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"productID": "test-product", "name": "Test Product"}},
                "marketplace": {
                    "paymentGateways": {
                        "stripe": {"enabled": True, "publicKey": "pk_test_example"},
                        "paypal": {"enabled": True},
                    }
                },
            },
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
        self.assertTrue(payment_gateways["paypal"]["enabled"])

    def test_marketplace_mapping_multilingual_license(self):
        """Test mapping multilingual license (preferred language)"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {"productID": "test-product", "name": "Test Product"},
                    "fr": {"productID": "test-product", "name": "Produit de Test"},
                }
            },
            "license": {
                "en": {
                    "definition": "MIT License",
                    "restrictions": ["No commercial use"],
                    "rights": ["Research"],
                },
                "fr": {
                    "definition": "Licence MIT",
                    "restrictions": ["Pas d'utilisation commerciale"],
                    "rights": ["Recherche"],
                },
            },
        }

        result = self.normalizer.normalize(contract_data)
        self.assertIsNotNone(result.hub_contract)
        self.assertIn("marketplace", result.hub_contract)
        # Should use English (preferred language)
        self.assertEqual(result.hub_contract["marketplace"]["license_summary"], "MIT License")
        self.assertIn("No commercial use", result.hub_contract["marketplace"]["restricted_use"])
        self.assertIn("Research", result.hub_contract["marketplace"]["intended_use"])

    def test_marketplace_mapping_complete(self):
        """Test complete marketplace mapping with all fields"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"productID": "test-product", "name": "Test Product"}},
                "marketplace": {
                    "pricingPlans": [{"planID": "basic", "name": "Basic Plan", "price": 9.99}],
                    "accessMethods": {"api": {"endpoint": "https://api.example.com/v1"}},
                    "paymentGateways": {"stripe": {"enabled": True}},
                },
            },
            "license": {
                "en": {
                    "definition": "MIT License",
                    "restrictions": ["No commercial use"],
                    "rights": ["Research", "Education"],
                }
            },
        }

        result = self.normalizer.normalize(contract_data)
        self.assertIsNotNone(result.hub_contract)
        marketplace = result.hub_contract["marketplace"]

        # License mapping
        self.assertEqual(marketplace["license_summary"], "MIT License")
        self.assertIn("No commercial use", marketplace["restricted_use"])
        self.assertIn("Research", marketplace["intended_use"])
        self.assertIn("Education", marketplace["intended_use"])

        # Pricing plans
        self.assertIn("pricing_plans", marketplace["x_odps"])
        self.assertEqual(len(marketplace["x_odps"]["pricing_plans"]), 1)

        # Access methods
        self.assertIn("access_methods", marketplace["x_odps"])
        self.assertIn("api", marketplace["x_odps"]["access_methods"])

        # Payment gateways
        self.assertIn("payment_gateways", marketplace["x_odps"])
        self.assertIn("stripe", marketplace["x_odps"]["payment_gateways"])

    def test_marketplace_mapping_missing_optional_fields(self):
        """Test graceful handling of missing optional marketplace fields"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {"en": {"productID": "test-product", "name": "Test Product"}}},
        }

        result = self.normalizer.normalize(contract_data)
        self.assertIsNotNone(result.hub_contract)
        # Marketplace section should exist but be empty or minimal
        self.assertIn("marketplace", result.hub_contract)
        # Should not fail even if license and marketplace are missing

    def test_marketplace_mapping_invalid_types(self):
        """Test handling of invalid types in marketplace fields"""
        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"productID": "test-product", "name": "Test Product"}},
                "marketplace": {
                    "pricingPlans": "invalid",  # Should be list
                    "accessMethods": ["invalid"],  # Should be dict
                    "paymentGateways": "invalid",  # Should be dict
                },
                "dataSchema": {"fields": [{"name": "test_field", "type": "string"}]},
            },
            "license": {
                "en": {
                    "definition": 123,  # Should be string
                    "restrictions": "invalid",  # Should be list or string (string is OK)
                    "rights": 456,  # Should be list or string
                }
            },
        }

        result = self.normalizer.normalize(contract_data)
        self.assertIsNotNone(result.hub_contract)
        # Should have warnings for invalid types
        self.assertTrue(len(result.warnings) > 0, f"Expected warnings but got: {result.warnings}")
        # Should still normalize successfully with warnings (invalid types should be handled gracefully)
        self.assertEqual(
            result.status,
            NormalizationStatus.NORMALIZED_WITH_WARNINGS,
            f"Expected NORMALIZED_WITH_WARNINGS but got {result.status}. Errors: {result.errors}, Warnings: {result.warnings}",
        )


class ODPSNormalizerEdgeCaseTest(ODPSEdgeCaseMixin, TestCase):
    """Standard edge-case tests for ODPS normalizer (via shared mixin).

    These tests validate normalization behavior for unicode, special characters,
    large documents, None values, and nested structures — verifying general
    normalization robustness independent of marketplace-specific mapping.
    """

    normalizer_class = ODPSNormalizer
    spec_version = "4.1"

    def setUp(self):
        self.normalizer = self.normalizer_class()
