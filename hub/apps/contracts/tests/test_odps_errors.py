"""
Unit tests for ODPS Error Hierarchy

Tests verify:
1. Error hierarchy structure and inheritance
2. Error code constants
3. Error context and metadata
4. Error serialization (to_dict)
5. Error recovery strategies
6. Recovery handlers (retry, fallback, compensation)
"""

import time

from django.test import TestCase

from hub.apps.contracts.odps_errors import (
    CompensationRecoveryHandler,
    ErrorRecoveryHandler,
    FallbackRecoveryHandler,
    ODPSError,
    ODPSExportError,
    ODPSLinkingError,
    ODPSNormalizationError,
    ODPSRefResolutionError,
    ODPSValidationError,
    RecoveryStrategy,
    RetryRecoveryHandler,
    recover_from_error,
)


class ODPSErrorTest(TestCase):
    """Test base ODPSError class"""

    def test_odps_error_basic(self):
        """Test basic ODPSError creation"""
        error = ODPSError("Test error message")
        self.assertEqual(str(error), "ODPSError(UNKNOWN_ERROR): Test error message")
        self.assertEqual(error.message, "Test error message")
        self.assertEqual(error.error_code, ODPSError.ERROR_CODE_UNKNOWN)
        self.assertEqual(error.user_message, "Test error message")
        self.assertFalse(error.recoverable)
        self.assertIsNone(error.recovery_strategy)

    def test_odps_error_with_error_code(self):
        """Test ODPSError with custom error code"""
        error = ODPSError("Test error", error_code=ODPSError.ERROR_CODE_VALIDATION_FAILED)
        self.assertEqual(error.error_code, ODPSError.ERROR_CODE_VALIDATION_FAILED)

    def test_odps_error_with_user_message(self):
        """Test ODPSError with custom user message"""
        error = ODPSError("Technical error", user_message="User-friendly error message")
        self.assertEqual(error.message, "Technical error")
        self.assertEqual(error.user_message, "User-friendly error message")

    def test_odps_error_with_context(self):
        """Test ODPSError with context"""
        context = {"field": "test_field", "value": 123}
        error = ODPSError("Test error", context=context)
        self.assertEqual(error.context, context)

    def test_odps_error_recoverable(self):
        """Test ODPSError with recoverable flag"""
        error = ODPSError("Test error", recoverable=True, recovery_strategy=RecoveryStrategy.RETRY)
        self.assertTrue(error.recoverable)
        self.assertEqual(error.recovery_strategy, RecoveryStrategy.RETRY)

    def test_odps_error_with_tenant_user(self):
        """Test ODPSError with tenant and user IDs"""
        error = ODPSError("Test error", tenant_id="tenant-123", user_id="user-456")
        self.assertEqual(error.tenant_id, "tenant-123")
        self.assertEqual(error.user_id, "user-456")

    def test_odps_error_with_cause(self):
        """Test ODPSError with cause exception"""
        cause = ValueError("Original error")
        error = ODPSError("Test error", cause=cause)
        self.assertEqual(error.cause, cause)
        self.assertEqual(error.context["cause_type"], "ValueError")
        self.assertEqual(error.context["cause_message"], "Original error")

    def test_odps_error_to_dict(self):
        """Test ODPSError serialization to dict"""
        error = ODPSError(
            "Test error",
            error_code="TEST_ERROR",
            user_message="User message",
            context={"key": "value"},
            recoverable=True,
            recovery_strategy=RecoveryStrategy.RETRY,
            tenant_id="tenant-123",
            user_id="user-456",
        )
        result = error.to_dict()

        self.assertEqual(result["error"], "TEST_ERROR")
        self.assertEqual(result["message"], "User message")
        self.assertEqual(result["technical_message"], "Test error")
        self.assertTrue(result["recoverable"])
        self.assertEqual(result["recovery_strategy"], "retry")
        self.assertEqual(result["tenant_id"], "tenant-123")
        self.assertEqual(result["user_id"], "user-456")
        self.assertEqual(result["context"]["key"], "value")
        self.assertIn("timestamp", result)

    def test_odps_error_repr(self):
        """Test ODPSError representation"""
        error = ODPSError("Test error", error_code="TEST_ERROR")
        repr_str = repr(error)
        self.assertIn("ODPSError", repr_str)
        self.assertIn("TEST_ERROR", repr_str)
        self.assertIn("Test error", repr_str)


class ODPSValidationErrorTest(TestCase):
    """Test ODPSValidationError class"""

    def test_validation_error_basic(self):
        """Test basic ODPSValidationError creation"""
        error = ODPSValidationError("Validation failed")
        self.assertEqual(error.error_code, ODPSValidationError.ERROR_CODE_VALIDATION_FAILED)
        self.assertFalse(error.recoverable)
        self.assertEqual(error.recovery_strategy, RecoveryStrategy.FAIL)

    def test_validation_error_with_field_path(self):
        """Test ODPSValidationError with field path"""
        error = ODPSValidationError("Validation failed", field_path="/product/name")
        self.assertEqual(error.context["field_path"], "/product/name")

    def test_validation_error_with_expected_actual(self):
        """Test ODPSValidationError with expected and actual values"""
        error = ODPSValidationError("Type mismatch", expected="string", actual=123)
        self.assertEqual(error.context["expected"], "string")
        self.assertEqual(error.context["actual"], 123)

    def test_validation_error_error_codes(self):
        """Test ODPSValidationError error code constants"""
        error = ODPSValidationError(
            "Schema validation failed",
            error_code=ODPSValidationError.ERROR_CODE_SCHEMA_VALIDATION_FAILED,
        )
        self.assertEqual(error.error_code, ODPSValidationError.ERROR_CODE_SCHEMA_VALIDATION_FAILED)

        error = ODPSValidationError(
            "Required field missing",
            error_code=ODPSValidationError.ERROR_CODE_REQUIRED_FIELD_MISSING,
        )
        self.assertEqual(error.error_code, ODPSValidationError.ERROR_CODE_REQUIRED_FIELD_MISSING)


class ODPSRefResolutionErrorTest(TestCase):
    """Test ODPSRefResolutionError class"""

    def test_ref_resolution_error_basic(self):
        """Test basic ODPSRefResolutionError creation"""
        error = ODPSRefResolutionError("Ref resolution failed")
        self.assertEqual(error.error_code, ODPSRefResolutionError.ERROR_CODE_RESOLUTION_FAILED)
        self.assertTrue(error.recoverable)
        self.assertEqual(error.recovery_strategy, RecoveryStrategy.FALLBACK)

    def test_ref_resolution_error_with_retry_after(self):
        """Test ODPSRefResolutionError with retry_after"""
        retry_after = int(time.time()) + 3600
        error = ODPSRefResolutionError(
            "Rate limit exceeded",
            error_code=ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED,
            retry_after=retry_after,
        )
        self.assertEqual(error.retry_after, retry_after)
        self.assertIn("retry_after", error.context)
        self.assertIn("retry_after_seconds", error.context)

    def test_ref_resolution_error_get_retry_after_header(self):
        """Test ODPSRefResolutionError retry_after header"""
        retry_after = int(time.time()) + 300  # 5 minutes from now
        error = ODPSRefResolutionError("Rate limit exceeded", retry_after=retry_after)
        header_value = error.get_retry_after_header()
        self.assertIsNotNone(header_value)
        self.assertIsInstance(header_value, str)
        # Should be approximately 300 seconds
        self.assertGreater(int(header_value), 290)
        self.assertLess(int(header_value), 310)

    def test_ref_resolution_error_no_retry_after(self):
        """Test ODPSRefResolutionError without retry_after"""
        error = ODPSRefResolutionError("Ref resolution failed")
        self.assertIsNone(error.get_retry_after_header())

    def test_ref_resolution_error_with_ref_path(self):
        """Test ODPSRefResolutionError with ref_path"""
        error = ODPSRefResolutionError("Ref resolution failed", ref_path="#/definitions/Email")
        self.assertEqual(error.context["ref_path"], "#/definitions/Email")

    def test_ref_resolution_error_with_ref_type(self):
        """Test ODPSRefResolutionError with ref_type"""
        error = ODPSRefResolutionError("Ref resolution failed", ref_type="internal")
        self.assertEqual(error.context["ref_type"], "internal")

    def test_ref_resolution_error_error_codes(self):
        """Test ODPSRefResolutionError error code constants"""
        error = ODPSRefResolutionError(
            "Rate limit exceeded", error_code=ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED
        )
        self.assertEqual(error.error_code, ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED)
        self.assertEqual(error.recovery_strategy, RecoveryStrategy.RETRY)

        error = ODPSRefResolutionError(
            "Security violation", error_code=ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION
        )
        self.assertEqual(error.error_code, ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION)
        self.assertEqual(error.recovery_strategy, RecoveryStrategy.FAIL)

    def test_ref_resolution_error_to_dict_with_retry_after(self):
        """Test ODPSRefResolutionError to_dict with retry_after"""
        retry_after = int(time.time()) + 600
        error = ODPSRefResolutionError("Rate limit exceeded", retry_after=retry_after)
        result = error.to_dict()
        self.assertIn("retry_after", result)
        self.assertIn("retry_after_timestamp", result)


class ODPSNormalizationErrorTest(TestCase):
    """Test ODPSNormalizationError class"""

    def test_normalization_error_basic(self):
        """Test basic ODPSNormalizationError creation"""
        error = ODPSNormalizationError("Normalization failed")
        self.assertEqual(error.error_code, ODPSNormalizationError.ERROR_CODE_NORMALIZATION_FAILED)
        self.assertTrue(error.recoverable)
        self.assertEqual(error.recovery_strategy, RecoveryStrategy.FALLBACK)

    def test_normalization_error_with_paths(self):
        """Test ODPSNormalizationError with field paths"""
        error = ODPSNormalizationError(
            "Normalization failed",
            field_path="/product/name",
            source_path="/info/name",
            target_path="/name",
        )
        self.assertEqual(error.context["field_path"], "/product/name")
        self.assertEqual(error.context["source_path"], "/info/name")
        self.assertEqual(error.context["target_path"], "/name")


class ODPSExportErrorTest(TestCase):
    """Test ODPSExportError class"""

    def test_export_error_basic(self):
        """Test basic ODPSExportError creation"""
        error = ODPSExportError("Export failed")
        self.assertEqual(error.error_code, ODPSExportError.ERROR_CODE_EXPORT_FAILED)
        self.assertTrue(error.recoverable)
        self.assertEqual(error.recovery_strategy, RecoveryStrategy.FALLBACK)

    def test_export_error_with_format(self):
        """Test ODPSExportError with export format"""
        error = ODPSExportError("Export failed", export_format="yaml")
        self.assertEqual(error.context["export_format"], "yaml")

    def test_export_error_with_file_path(self):
        """Test ODPSExportError with file path"""
        error = ODPSExportError("Export failed", file_path="/tmp/export.json")
        self.assertEqual(error.context["file_path"], "/tmp/export.json")


class ODPSLinkingErrorTest(TestCase):
    """Test ODPSLinkingError class"""

    def test_linking_error_basic(self):
        """Test basic ODPSLinkingError creation"""
        error = ODPSLinkingError("Linking failed")
        self.assertEqual(error.error_code, ODPSLinkingError.ERROR_CODE_LINKING_FAILED)
        self.assertTrue(error.recoverable)
        self.assertEqual(error.recovery_strategy, RecoveryStrategy.SKIP)

    def test_linking_error_with_link_info(self):
        """Test ODPSLinkingError with link information"""
        error = ODPSLinkingError(
            "Linking failed",
            link_path="/links/0",
            link_type="contract",
            source_id="source-123",
            target_id="target-456",
        )
        self.assertEqual(error.context["link_path"], "/links/0")
        self.assertEqual(error.context["link_type"], "contract")
        self.assertEqual(error.context["source_id"], "source-123")
        self.assertEqual(error.context["target_id"], "target-456")


class ErrorRecoveryHandlerTest(TestCase):
    """Test error recovery handlers"""

    def test_retry_recovery_handler_can_handle(self):
        """Test RetryRecoveryHandler can_handle"""
        handler = RetryRecoveryHandler()
        error = ODPSRefResolutionError(
            "Rate limit exceeded", error_code=ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED
        )
        self.assertTrue(handler.can_handle(error))

        error = ODPSRefResolutionError(
            "Security violation", error_code=ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION
        )
        self.assertFalse(handler.can_handle(error))

    def test_retry_recovery_handler_success(self):
        """Test RetryRecoveryHandler successful retry"""
        handler = RetryRecoveryHandler(max_retries=3, initial_delay=0.01)
        error = ODPSRefResolutionError(
            "Temporary error", error_code=ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED
        )

        call_count = [0]

        def operation():
            call_count[0] += 1
            if call_count[0] < 2:
                raise ODPSRefResolutionError(
                    "Temporary error",
                    error_code=ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED,
                )
            return "success"

        result = handler.recover(error, {}, operation=operation)
        self.assertEqual(result, "success")
        self.assertEqual(call_count[0], 2)

    def test_retry_recovery_handler_max_retries(self):
        """Test RetryRecoveryHandler with max retries exceeded"""
        handler = RetryRecoveryHandler(max_retries=2, initial_delay=0.01)
        error = ODPSRefResolutionError(
            "Temporary error", error_code=ODPSRefResolutionError.ERROR_CODE_RESOLUTION_FAILED
        )

        def operation():
            raise ODPSRefResolutionError(
                "Temporary error", error_code=ODPSRefResolutionError.ERROR_CODE_RESOLUTION_FAILED
            )

        with self.assertRaises(ODPSRefResolutionError):
            handler.recover(error, {}, operation=operation)

    def test_fallback_recovery_handler_can_handle(self):
        """Test FallbackRecoveryHandler can_handle"""
        handler = FallbackRecoveryHandler()
        error = ODPSNormalizationError("Normalization failed")
        self.assertTrue(handler.can_handle(error))

        error = ODPSRefResolutionError(
            "Security violation", error_code=ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION
        )
        self.assertFalse(handler.can_handle(error))

    def test_fallback_recovery_handler_success(self):
        """Test FallbackRecoveryHandler successful fallback"""
        handler = FallbackRecoveryHandler()
        error = ODPSNormalizationError("Normalization failed")

        def fallback_operation():
            return "fallback_result"

        result = handler.recover(error, {}, fallback_operation=fallback_operation)
        self.assertEqual(result, "fallback_result")

    def test_compensation_recovery_handler_can_handle(self):
        """Test CompensationRecoveryHandler can_handle"""
        handler = CompensationRecoveryHandler()
        error = ODPSError(
            "Operation failed", recoverable=True, recovery_strategy=RecoveryStrategy.COMPENSATION
        )
        self.assertTrue(handler.can_handle(error))

    def test_compensation_recovery_handler_success(self):
        """Test CompensationRecoveryHandler successful compensation"""
        handler = CompensationRecoveryHandler()
        error = ODPSError(
            "Operation failed", recoverable=True, recovery_strategy=RecoveryStrategy.COMPENSATION
        )

        def compensation_operation():
            return "compensation_result"

        result = handler.recover(error, {}, compensation_operation=compensation_operation)
        self.assertEqual(result, "compensation_result")


class RecoverFromErrorTest(TestCase):
    """Test recover_from_error function"""

    def test_recover_from_error_not_recoverable(self):
        """Test recover_from_error with non-recoverable error"""
        error = ODPSValidationError("Validation failed")
        with self.assertRaises(ODPSValidationError):
            recover_from_error(error, {})

    def test_recover_from_error_retry_success(self):
        """Test recover_from_error with successful retry"""
        error = ODPSRefResolutionError(
            "Temporary error", error_code=ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED
        )

        call_count = [0]

        def operation():
            call_count[0] += 1
            if call_count[0] < 2:
                raise ODPSRefResolutionError(
                    "Temporary error",
                    error_code=ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED,
                )
            return "success"

        result = recover_from_error(error, {"operation": operation})
        self.assertEqual(result, "success")

    def test_recover_from_error_fallback_success(self):
        """Test recover_from_error with successful fallback"""
        error = ODPSNormalizationError("Normalization failed")

        def fallback_operation():
            return "fallback_result"

        result = recover_from_error(error, {"fallback_operation": fallback_operation})
        self.assertEqual(result, "fallback_result")

    def test_recover_from_error_no_handler(self):
        """Test recover_from_error with no matching handler"""
        error = ODPSError(
            "Unknown error", recoverable=True, recovery_strategy=RecoveryStrategy.SKIP
        )

        with self.assertRaises(ODPSError):
            recover_from_error(error, {})

    def test_recover_from_error_custom_handlers(self):
        """Test recover_from_error with custom handlers"""
        error = ODPSError("Custom error", recoverable=True, recovery_strategy=RecoveryStrategy.SKIP)

        class SkipHandler(ErrorRecoveryHandler):
            def can_handle(self, error):
                return error.recovery_strategy == RecoveryStrategy.SKIP

            def recover(self, error, context):
                return "skipped"

        handlers = [SkipHandler()]
        result = recover_from_error(error, {}, handlers=handlers)
        self.assertEqual(result, "skipped")


class ErrorHierarchyInheritanceTest(TestCase):
    """Test error hierarchy inheritance"""

    def test_error_inheritance(self):
        """Test that all error classes inherit from ODPSError"""
        self.assertTrue(issubclass(ODPSValidationError, ODPSError))
        self.assertTrue(issubclass(ODPSRefResolutionError, ODPSError))
        self.assertTrue(issubclass(ODPSNormalizationError, ODPSError))
        self.assertTrue(issubclass(ODPSExportError, ODPSError))
        self.assertTrue(issubclass(ODPSLinkingError, ODPSError))

    def test_error_isinstance(self):
        """Test isinstance checks for error hierarchy"""
        validation_error = ODPSValidationError("Validation failed")
        self.assertIsInstance(validation_error, ODPSError)
        self.assertIsInstance(validation_error, ODPSValidationError)

        ref_error = ODPSRefResolutionError("Ref resolution failed")
        self.assertIsInstance(ref_error, ODPSError)
        self.assertIsInstance(ref_error, ODPSRefResolutionError)

    def test_error_polymorphism(self):
        """Test error polymorphism in error handling"""
        errors = [
            ODPSValidationError("Validation failed"),
            ODPSRefResolutionError("Ref resolution failed"),
            ODPSNormalizationError("Normalization failed"),
        ]

        for error in errors:
            self.assertIsInstance(error, ODPSError)
            self.assertIn("error", error.to_dict())
            self.assertIn("message", error.to_dict())

    # Edge cases and error handling tests (using real implementations)
    def test_odps_error_with_empty_message(self):
        """Test ODPSError with empty message."""
        error = ODPSError("")
        self.assertEqual(error.message, "")
        error_dict = error.to_dict()
        self.assertIn("error", error_dict)
        self.assertIn("message", error_dict)

    def test_odps_error_with_very_long_message(self):
        """Test ODPSError with very long message."""
        long_message = "A" * 100000
        error = ODPSError(long_message)
        self.assertEqual(error.message, long_message)
        error_dict = error.to_dict()
        self.assertIn("error", error_dict)
        self.assertEqual(error_dict["technical_message"], long_message)

    def test_odps_error_with_special_characters_in_message(self):
        """Test ODPSError with special characters in message."""
        special_message = "Error <>&\"'"
        error = ODPSError(special_message)
        self.assertEqual(error.message, special_message)
        error_dict = error.to_dict()
        self.assertIn("error", error_dict)
        self.assertEqual(error_dict["message"], special_message)

    def test_odps_error_with_unicode_in_message(self):
        """Test ODPSError with unicode characters in message."""
        unicode_message = "错误消息"
        error = ODPSError(unicode_message)
        self.assertEqual(error.message, unicode_message)
        error_dict = error.to_dict()
        self.assertIn("error", error_dict)
        self.assertEqual(error_dict["message"], unicode_message)

    def test_odps_error_with_none_context(self):
        """Test ODPSError with None context."""
        error = ODPSError("Test error", context=None)
        error_dict = error.to_dict()
        self.assertIn("error", error_dict)
        self.assertIn("message", error_dict)

    def test_odps_error_with_empty_context(self):
        """Test ODPSError with empty context."""
        error = ODPSError("Test error", context={})
        self.assertEqual(error.context, {})
        error_dict = error.to_dict()
        self.assertIn("error", error_dict)
        self.assertIn("message", error_dict)
        # Empty context should not appear in to_dict output
        self.assertNotIn("context", error_dict)

    def test_odps_error_with_very_large_context(self):
        """Test ODPSError with very large context."""
        large_context = {f"key_{i}": "value" * 1000 for i in range(1000)}
        error = ODPSError("Test error", context=large_context)
        self.assertEqual(len(error.context), 1000)
        error_dict = error.to_dict()
        self.assertIn("error", error_dict)
        self.assertIn("context", error_dict)
        self.assertEqual(len(error_dict["context"]), 1000)

    def test_odps_error_with_nested_context(self):
        """Test ODPSError with nested context."""
        nested_context = {"level1": {"level2": {"level3": {"value": "deep"}}}}
        error = ODPSError("Test error", context=nested_context)
        self.assertEqual(error.context, nested_context)
        error_dict = error.to_dict()
        self.assertIn("context", error_dict)
        self.assertEqual(error_dict["context"]["level1"]["level2"]["level3"]["value"], "deep")

    def test_odps_error_to_dict_preserves_all_fields(self):
        """Test that to_dict preserves all error fields."""
        error = ODPSError(
            "Test error",
            error_code="TEST_ERROR",
            user_message="User message",
            recoverable=True,
            recovery_strategy=RecoveryStrategy.RETRY,
            tenant_id="tenant-123",
            user_id="user-456",
            context={"field": "value"},
        )
        error_dict = error.to_dict()

        # Verify all fields are present (to_dict uses "error" for error_code)
        self.assertIn("error", error_dict)
        self.assertIn("message", error_dict)
        self.assertEqual(error_dict["error"], "TEST_ERROR")
        self.assertIn("recoverable", error_dict)
        self.assertIn("recovery_strategy", error_dict)
        self.assertIn("tenant_id", error_dict)
        self.assertIn("user_id", error_dict)
        self.assertIn("context", error_dict)

    def test_error_hierarchy_to_dict_consistency(self):
        """Test that all error types have consistent to_dict structure."""
        errors = [
            ODPSValidationError("Validation failed"),
            ODPSRefResolutionError("Ref resolution failed"),
            ODPSNormalizationError("Normalization failed"),
            ODPSExportError("Export failed"),
            ODPSLinkingError("Linking failed"),
        ]

        for error in errors:
            error_dict = error.to_dict()
            # All should have at least these fields
            self.assertIn("error", error_dict)
            self.assertIn("message", error_dict)
            self.assertIsInstance(error_dict["error"], str)
            self.assertIsInstance(error_dict["message"], str)

    def test_error_with_cause_exception_chain(self):
        """Test error with exception chain."""
        inner_error = ValueError("Inner error")
        TypeError("Middle error")
        outer_error = ODPSError("Outer error", cause=inner_error)

        # Should preserve cause information
        self.assertEqual(outer_error.cause, inner_error)
        self.assertIn("cause_type", outer_error.context)
        self.assertIn("cause_message", outer_error.context)

    def test_error_recovery_strategy_enum_values(self):
        """Test that all recovery strategy enum values are valid."""
        strategies = [
            RecoveryStrategy.RETRY,
            RecoveryStrategy.FALLBACK,
            RecoveryStrategy.COMPENSATION,
            RecoveryStrategy.SKIP,
        ]

        for strategy in strategies:
            error = ODPSError("Test error", recoverable=True, recovery_strategy=strategy)
            self.assertEqual(error.recovery_strategy, strategy)

    def test_error_with_invalid_recovery_strategy(self):
        """Test error with invalid recovery strategy raises on serialization."""
        # ODPSError constructor accepts arbitrary recovery_strategy values
        error = ODPSError("Test error", recoverable=True, recovery_strategy="INVALID_STRATEGY")
        self.assertEqual(error.recovery_strategy, "INVALID_STRATEGY")
        self.assertTrue(error.recoverable)
        # But to_dict() calls .value on it, which fails for non-enum strings
        with self.assertRaises(AttributeError):
            error.to_dict()

    def test_error_serialization_with_circular_reference(self):
        """Test error construction accepts circular reference context."""
        context = {"self": None}
        context["self"] = context  # Create circular reference

        # Construction should succeed - context is stored as-is
        error = ODPSError("Test error", context=context)
        self.assertIs(error.context["self"], context)
        # to_dict stores context by reference, so it also succeeds
        error_dict = error.to_dict()
        self.assertIn("error", error_dict)
        self.assertIn("message", error_dict)
        self.assertIn("context", error_dict)

    def test_odps_errors_handle_unicode_characters(self):
        """Test that ODPS errors handle unicode characters correctly."""
        error = ODPSError("测试错误消息")
        error_dict = error.to_dict()
        self.assertIn("error", error_dict)
        self.assertIn("message", error_dict)
        self.assertEqual(error_dict["message"], "测试错误消息")

    def test_odps_errors_handle_special_characters(self):
        """Test that ODPS errors handle special characters correctly."""
        error = ODPSError("Test & Co. (Special) <error> & more")
        error_dict = error.to_dict()
        self.assertIn("error", error_dict)
        self.assertIn("message", error_dict)
        self.assertEqual(error_dict["message"], "Test & Co. (Special) <error> & more")

    def test_odps_errors_handle_very_large_messages(self):
        """Test that ODPS errors handle very large messages correctly."""
        large_message = "A" * 100000  # 100KB string
        error = ODPSError(large_message)
        error_dict = error.to_dict()
        self.assertIn("error", error_dict)
        self.assertIn("message", error_dict)
        self.assertEqual(error_dict["technical_message"], large_message)

    def test_odps_errors_handle_none_values(self):
        """Test that ODPS errors handle None values correctly."""
        error = ODPSError(None)  # type: ignore[misc]  # test: edge-case type exercise
        error_dict = error.to_dict()
        self.assertIn("error", error_dict)
        self.assertIn("message", error_dict)

    def test_odps_errors_handle_nested_structures(self):
        """Test that ODPS errors handle nested structures correctly."""
        nested_context = {"level1": {"level2": {"level3": {"value": "deep"}}}}
        error = ODPSError("Test error", context=nested_context)
        error_dict = error.to_dict()
        self.assertIn("error", error_dict)
        self.assertIn("message", error_dict)
        self.assertIn("context", error_dict)
        self.assertEqual(error_dict["context"], nested_context)
