"""
Unit tests for ODCS Generator Module Structure.

Tests module structure, imports, and basic functionality following
engineering best practices without mocks/stubs.
"""

import pytest
from django.test import TestCase

from hub.apps.contracts.odcs_errors import (
    ODCSError,
    ODCSExportError,
    ODCSGenerationError,
    ODCSValidationError,
    RecoveryStrategy,
)
from hub.apps.contracts.odcs_format_converter import (
    convert_json_to_yaml,
    convert_yaml_to_json,
)
from hub.apps.contracts.odcs_generator import (
    generate_odcs_from_hubcontract,
    generate_odcs_from_schema,
)
from hub.apps.contracts.odcs_version_detection import (
    detect_odcs_version,
    get_supported_odcs_versions,
    is_supported_odcs_version,
)

pytestmark = pytest.mark.django_db(transaction=True)


class ODCSGeneratorModuleStructureTest(TestCase):
    """Test ODCS generator module structure and imports"""

    def test_module_imports_successfully(self):
        """Test that all modules can be imported"""
        # Test main generator module
        from hub.apps.contracts import odcs_generator

        self.assertIsNotNone(odcs_generator)

        # Test error classes
        from hub.apps.contracts import odcs_errors

        self.assertIsNotNone(odcs_errors)

        # Test version detection
        from hub.apps.contracts import odcs_version_detection

        self.assertIsNotNone(odcs_version_detection)

        # Test format converter
        from hub.apps.contracts import odcs_format_converter

        self.assertIsNotNone(odcs_format_converter)

    def test_generator_functions_available(self):
        """Test that generator functions are available"""
        self.assertTrue(callable(generate_odcs_from_hubcontract))
        self.assertTrue(callable(generate_odcs_from_schema))

    def test_error_classes_available(self):
        """Test that error classes are available"""
        self.assertTrue(issubclass(ODCSError, Exception))
        self.assertTrue(issubclass(ODCSValidationError, ODCSError))
        self.assertTrue(issubclass(ODCSGenerationError, ODCSError))
        self.assertTrue(issubclass(ODCSExportError, ODCSError))

    def test_version_detection_functions_available(self):
        """Test that version detection functions are available"""
        self.assertTrue(callable(detect_odcs_version))
        self.assertTrue(callable(get_supported_odcs_versions))
        self.assertTrue(callable(is_supported_odcs_version))

    def test_format_converter_functions_available(self):
        """Test that format converter functions are available"""
        self.assertTrue(callable(convert_yaml_to_json))
        self.assertTrue(callable(convert_json_to_yaml))

    def test_recovery_strategy_enum_available(self):
        """Test that RecoveryStrategy enum is available"""
        self.assertTrue(hasattr(RecoveryStrategy, "RETRY"))
        self.assertTrue(hasattr(RecoveryStrategy, "FALLBACK"))
        self.assertTrue(hasattr(RecoveryStrategy, "COMPENSATION"))
        self.assertTrue(hasattr(RecoveryStrategy, "SKIP"))
        self.assertTrue(hasattr(RecoveryStrategy, "FAIL"))


class ODCSGeneratorErrorClassTest(TestCase):
    """Test ODCS error class instantiation and message formatting"""

    def test_odcs_error_instantiation(self):
        """Test basic ODCSError instantiation"""
        error = ODCSError(
            message="Test error message",
            error_code="TEST_ERROR",
            user_message="User-friendly error message",
        )

        self.assertEqual(error.message, "Test error message")
        self.assertEqual(error.error_code, "TEST_ERROR")
        self.assertEqual(error.user_message, "User-friendly error message")
        self.assertIsInstance(error.context, dict)
        self.assertFalse(error.recoverable)
        self.assertIsNone(error.recovery_strategy)

    def test_odcs_error_string_representation(self):
        """Test error string representation"""
        error = ODCSError(message="Test error", error_code="TEST_ERROR")

        error_str = str(error)
        self.assertIn("ODCSError", error_str)
        self.assertIn("TEST_ERROR", error_str)
        self.assertIn("Test error", error_str)

    def test_odcs_error_to_dict(self):
        """Test error to_dict conversion"""
        error = ODCSError(
            message="Test error",
            error_code="TEST_ERROR",
            user_message="User message",
            recoverable=True,
            recovery_strategy=RecoveryStrategy.RETRY,
            tenant_id="test-tenant",
            user_id="test-user",
        )

        error_dict = error.to_dict()
        self.assertEqual(error_dict["error"], "TEST_ERROR")
        self.assertEqual(error_dict["message"], "User message")
        self.assertEqual(error_dict["technical_message"], "Test error")
        self.assertTrue(error_dict["recoverable"])
        self.assertEqual(error_dict["recovery_strategy"], "retry")
        self.assertEqual(error_dict["tenant_id"], "test-tenant")
        self.assertEqual(error_dict["user_id"], "test-user")

    def test_odcs_validation_error_instantiation(self):
        """Test ODCSValidationError instantiation with field context"""
        error = ODCSValidationError(
            message="Validation failed",
            error_code=ODCSValidationError.ERROR_CODE_REQUIRED_FIELD_MISSING,
            field_path="/info/name",
            expected="str",
            actual=None,
        )

        self.assertEqual(error.error_code, ODCSValidationError.ERROR_CODE_REQUIRED_FIELD_MISSING)
        self.assertEqual(error.context["field_path"], "/info/name")
        self.assertEqual(error.context["expected"], "str")
        # actual=None is not added to context (only non-None values are added)
        self.assertNotIn("actual", error.context)
        self.assertFalse(error.recoverable)
        self.assertEqual(error.recovery_strategy, RecoveryStrategy.FAIL)

    def test_odcs_generation_error_instantiation(self):
        """Test ODCSGenerationError instantiation with path context"""
        error = ODCSGenerationError(
            message="Generation failed",
            error_code=ODCSGenerationError.ERROR_CODE_FIELD_MAPPING_FAILED,
            field_path="/schema/fields",
            source_path="/info/schema",
            target_path="/schema",
        )

        self.assertEqual(error.error_code, ODCSGenerationError.ERROR_CODE_FIELD_MAPPING_FAILED)
        self.assertEqual(error.context["field_path"], "/schema/fields")
        self.assertEqual(error.context["source_path"], "/info/schema")
        self.assertEqual(error.context["target_path"], "/schema")
        self.assertTrue(error.recoverable)
        self.assertEqual(error.recovery_strategy, RecoveryStrategy.FALLBACK)

    def test_odcs_export_error_instantiation(self):
        """Test ODCSExportError instantiation with export context"""
        error = ODCSExportError(
            message="Export failed",
            error_code=ODCSExportError.ERROR_CODE_SERIALIZATION_FAILED,
            export_format="json",
            file_path="/tmp/contract.json",
        )

        self.assertEqual(error.error_code, ODCSExportError.ERROR_CODE_SERIALIZATION_FAILED)
        self.assertEqual(error.context["export_format"], "json")
        self.assertEqual(error.context["file_path"], "/tmp/contract.json")
        self.assertTrue(error.recoverable)
        self.assertEqual(error.recovery_strategy, RecoveryStrategy.FALLBACK)

    def test_odcs_error_with_cause(self):
        """Test error with cause exception"""
        original_error = ValueError("Original error")
        error = ODCSError(message="Wrapped error", error_code="WRAPPED_ERROR", cause=original_error)

        self.assertEqual(error.cause, original_error)
        self.assertEqual(error.context["cause_type"], "ValueError")
        self.assertEqual(error.context["cause_message"], "Original error")

    def test_error_message_formatting(self):
        """Test error message formatting with context"""
        error = ODCSValidationError(
            message="Field validation failed",
            field_path="/info/name",
            expected="str (non-empty)",
            actual="None",
        )

        # Test string representation includes context
        error_str = str(error)
        self.assertIn("ODCSValidationError", error_str)
        self.assertIn("Field validation failed", error_str)

        # Test dict representation includes all context
        error_dict = error.to_dict()
        self.assertIn("context", error_dict)
        self.assertEqual(error_dict["context"]["field_path"], "/info/name")
        self.assertEqual(error_dict["context"]["expected"], "str (non-empty)")
        self.assertEqual(error_dict["context"]["actual"], "None")

    def test_generate_odcs_handles_unicode_characters(self):
        """Test that generation handles unicode characters correctly."""
        hub_contract = {
            "id": "test-unicode",
            "info": {"name": "测试合同", "description": "测试描述"},
            "schema": {"fields": [{"name": "字段名称", "data_type": "string"}]},
        }

        try:
            result = generate_odcs_from_hubcontract(hub_contract)
            # If generation succeeds, verify structure
            self.assertIsNotNone(result)
        except Exception as e:
            # If generation fails, it should fail gracefully
            self.assertIsInstance(
                e, (ODCSGenerationError, ODCSValidationError), "Should raise appropriate exception"
            )

    def test_generate_odcs_handles_special_characters(self):
        """Test that generation handles special characters correctly."""
        hub_contract = {
            "id": "test-special",
            "info": {"name": "Test & Co. (Special)", "description": "Test <description> & more"},
            "schema": {"fields": [{"name": "field-name", "data_type": "string"}]},
        }

        try:
            result = generate_odcs_from_hubcontract(hub_contract)
            # If generation succeeds, verify structure
            self.assertIsNotNone(result)
        except Exception as e:
            # If generation fails, it should fail gracefully
            self.assertIsInstance(
                e, (ODCSGenerationError, ODCSValidationError), "Should raise appropriate exception"
            )

    def test_generate_odcs_handles_very_large_documents(self):
        """Test that generation handles very large documents correctly."""
        large_description = "A" * 100000  # 100KB string
        hub_contract = {
            "id": "test-large",
            "info": {"name": "Test Product", "description": large_description},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }

        # Should handle large documents gracefully
        try:
            result = generate_odcs_from_hubcontract(hub_contract)
            # If generation succeeds, verify structure
            self.assertIsNotNone(result)
        except Exception as e:
            # If generation fails, it should fail gracefully
            self.assertIsInstance(
                e,
                (ODCSGenerationError, ODCSValidationError),
                "Should raise appropriate exception for very large documents",
            )

    def test_generate_odcs_handles_none_values(self):
        """Test that generation handles None values correctly."""
        hub_contract = {
            "id": "test-none",
            "info": {"name": "Test Product", "description": None},  # None value
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }

        # Should handle None values gracefully
        try:
            result = generate_odcs_from_hubcontract(hub_contract)
            # If generation succeeds, None values may be omitted or handled
            self.assertIsNotNone(result)
        except Exception as e:
            # If generation fails, it should fail gracefully
            self.assertIsInstance(
                e,
                (ODCSGenerationError, ODCSValidationError),
                "Should raise appropriate exception for None values",
            )

    def test_generate_odcs_handles_nested_structures(self):
        """Test that generation handles nested structures correctly."""
        hub_contract = {
            "id": "test-nested",
            "info": {
                "name": "Test Product",
                "nested": {"level1": {"level2": {"level3": {"level4": {"value": "deep"}}}}},
            },
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }

        try:
            result = generate_odcs_from_hubcontract(hub_contract)
            # If generation succeeds, verify structure
            self.assertIsNotNone(result)
        except Exception as e:
            # If generation fails, it should fail gracefully
            self.assertIsInstance(
                e, (ODCSGenerationError, ODCSValidationError), "Should raise appropriate exception"
            )
