"""
Tests for Error Logging
"""
import structlog
from django.test import TestCase

from hub.apps.core.error_handling.error_logging import (
    ErrorLogger,
    log_error,
    log_exception,
)


class ErrorLoggerTest(TestCase):
    """Test ErrorLogger class."""

    def test_log_error(self):
        """Test logging an error."""
        logger = ErrorLogger()

        with structlog.testing.capture_logs() as captured:
            try:
                raise ValueError("Test error")
            except ValueError as e:
                logger.log_error(
                    error=e,
                    error_code="TEST_ERROR",
                    message="Test error occurred",
                    http_status=400,
                    request_id="test-request-id",
                    tenant_id="test-tenant-id",
                )

        self.assertEqual(len(captured), 1)
        log_entry = captured[0]
        self.assertEqual(log_entry["event"], "error_occurred")
        self.assertEqual(log_entry["error_code"], "TEST_ERROR")
        self.assertEqual(log_entry["error_type"], "ValueError")
        self.assertEqual(log_entry["error_message"], "Test error")
        self.assertEqual(log_entry["message"], "Test error occurred")
        self.assertEqual(log_entry["http_status"], 400)
        self.assertEqual(log_entry["request_id"], "test-request-id")
        self.assertEqual(log_entry["tenant_id"], "test-tenant-id")
        self.assertEqual(log_entry["log_level"], "error")

    def test_log_exception(self):
        """Test logging an exception."""
        logger = ErrorLogger()

        with structlog.testing.capture_logs() as captured:
            try:
                raise RuntimeError("Test exception")
            except RuntimeError as e:
                logger.log_exception(e, context={"additional": "context"})

        self.assertEqual(len(captured), 1)
        log_entry = captured[0]
        self.assertEqual(log_entry["event"], "error_occurred")
        self.assertEqual(log_entry["error_type"], "RuntimeError")
        self.assertEqual(log_entry["error_message"], "Test exception")
        self.assertEqual(log_entry["additional"], "context")
        self.assertEqual(log_entry["log_level"], "error")

    def test_log_validation_error(self):
        """Test logging a validation error."""
        logger = ErrorLogger()

        with structlog.testing.capture_logs() as captured:
            logger.log_validation_error(
                field="email",
                message="Invalid email format",
                value="invalid-email",
                request_id="test-request-id",
                tenant_id="test-tenant-id",
            )

        self.assertEqual(len(captured), 1)
        log_entry = captured[0]
        self.assertEqual(log_entry["event"], "validation_error")
        self.assertEqual(log_entry["field"], "email")
        self.assertEqual(log_entry["message"], "Invalid email format")
        self.assertEqual(log_entry["error_type"], "ValidationError")
        self.assertEqual(log_entry["error_code"], "VALIDATION_ERROR")
        self.assertEqual(log_entry["request_id"], "test-request-id")
        self.assertEqual(log_entry["tenant_id"], "test-tenant-id")
        self.assertEqual(log_entry["log_level"], "warning")

    def test_log_permission_error(self):
        """Test logging a permission error."""
        logger = ErrorLogger()

        with structlog.testing.capture_logs() as captured:
            logger.log_permission_error(
                resource="asset",
                action="delete",
                user_id="test-user-id",
                tenant_id="test-tenant-id",
                request_id="test-request-id",
            )

        self.assertEqual(len(captured), 1)
        log_entry = captured[0]
        self.assertEqual(log_entry["event"], "permission_denied")
        self.assertEqual(log_entry["resource"], "asset")
        self.assertEqual(log_entry["action"], "delete")
        self.assertEqual(log_entry["error_type"], "PermissionError")
        self.assertEqual(log_entry["error_code"], "PERMISSION_DENIED")
        self.assertEqual(log_entry["user_id"], "test-user-id")
        self.assertEqual(log_entry["log_level"], "warning")

    def test_log_not_found_error(self):
        """Test logging a not found error."""
        logger = ErrorLogger()

        with structlog.testing.capture_logs() as captured:
            logger.log_not_found_error(
                resource_type="asset",
                resource_id="test-asset-id",
                request_id="test-request-id",
                tenant_id="test-tenant-id",
            )

        self.assertEqual(len(captured), 1)
        log_entry = captured[0]
        self.assertEqual(log_entry["event"], "resource_not_found")
        self.assertEqual(log_entry["resource_type"], "asset")
        self.assertEqual(log_entry["resource_id"], "test-asset-id")
        self.assertEqual(log_entry["error_type"], "NotFoundError")
        self.assertEqual(log_entry["error_code"], "NOT_FOUND")
        self.assertEqual(log_entry["log_level"], "warning")

    def test_logger_with_context(self):
        """Test logger with initial context."""
        logger = ErrorLogger(context={"service": "test-service"})

        with structlog.testing.capture_logs() as captured:
            try:
                raise ValueError("Test")
            except ValueError as e:
                logger.log_error(e, error_code="TEST_ERROR")

        self.assertEqual(len(captured), 1)
        log_entry = captured[0]
        self.assertEqual(log_entry["event"], "error_occurred")
        self.assertEqual(log_entry["error_code"], "TEST_ERROR")
        self.assertEqual(log_entry["service"], "test-service")

    def test_log_error_warning_level(self):
        """Test logging error with warning level."""
        logger = ErrorLogger()

        with structlog.testing.capture_logs() as captured:
            try:
                raise ValueError("Test warning")
            except ValueError as e:
                logger.log_error(
                    error=e,
                    error_code="TEST_WARNING",
                    level="warning",
                )

        self.assertEqual(len(captured), 1)
        log_entry = captured[0]
        self.assertEqual(log_entry["event"], "error_occurred")
        self.assertEqual(log_entry["log_level"], "warning")
        self.assertEqual(log_entry["error_code"], "TEST_WARNING")

    def test_log_error_critical_level(self):
        """Test logging error with critical level."""
        logger = ErrorLogger()

        with structlog.testing.capture_logs() as captured:
            try:
                raise ValueError("Test critical")
            except ValueError as e:
                logger.log_error(
                    error=e,
                    error_code="TEST_CRITICAL",
                    level="critical",
                )

        self.assertEqual(len(captured), 1)
        log_entry = captured[0]
        self.assertEqual(log_entry["event"], "error_occurred")
        self.assertEqual(log_entry["log_level"], "critical")
        self.assertEqual(log_entry["error_code"], "TEST_CRITICAL")

    def test_log_validation_error_with_value(self):
        """Test logging validation error with dict value includes value_type."""
        logger = ErrorLogger()

        with structlog.testing.capture_logs() as captured:
            logger.log_validation_error(
                field="email",
                message="Invalid email format",
                value={"email": "invalid"},
                request_id="test-request-id",
                tenant_id="test-tenant-id",
            )

        self.assertEqual(len(captured), 1)
        log_entry = captured[0]
        self.assertEqual(log_entry["event"], "validation_error")
        self.assertEqual(log_entry["field"], "email")
        self.assertEqual(log_entry["value_type"], "dict")

    def test_log_validation_error_with_string_value(self):
        """Test logging validation error with string value omits value_type."""
        logger = ErrorLogger()

        with structlog.testing.capture_logs() as captured:
            logger.log_validation_error(
                field="email",
                message="Invalid email format",
                value="invalid-email",
                request_id="test-request-id",
                tenant_id="test-tenant-id",
            )

        self.assertEqual(len(captured), 1)
        log_entry = captured[0]
        self.assertEqual(log_entry["event"], "validation_error")
        self.assertEqual(log_entry["field"], "email")
        self.assertNotIn("value_type", log_entry)


class LogErrorFunctionTest(TestCase):
    """Test log_error convenience function."""

    def test_log_error_function(self):
        """Test log_error convenience function."""
        with structlog.testing.capture_logs() as captured:
            try:
                raise ValueError("Test error")
            except ValueError as e:
                log_error(
                    error=e,
                    error_code="TEST_ERROR",
                    message="Test error",
                    http_status=400,
                )

        self.assertEqual(len(captured), 1)
        log_entry = captured[0]
        self.assertEqual(log_entry["event"], "error_occurred")
        self.assertEqual(log_entry["error_code"], "TEST_ERROR")
        self.assertEqual(log_entry["error_type"], "ValueError")
        self.assertEqual(log_entry["log_level"], "error")


class LogExceptionFunctionTest(TestCase):
    """Test log_exception convenience function."""

    def test_log_exception_function(self):
        """Test log_exception convenience function."""
        with structlog.testing.capture_logs() as captured:
            try:
                raise RuntimeError("Test exception")
            except RuntimeError as e:
                log_exception(e, context={"test": "context"})

        self.assertEqual(len(captured), 1)
        log_entry = captured[0]
        self.assertEqual(log_entry["event"], "error_occurred")
        self.assertEqual(log_entry["error_type"], "RuntimeError")
        self.assertEqual(log_entry["test"], "context")
        self.assertEqual(log_entry["log_level"], "error")
