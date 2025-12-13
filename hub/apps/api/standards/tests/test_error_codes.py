"""
Comprehensive tests for standardized error codes.
"""
from django.test import TestCase
from rest_framework import status

from hub.apps.api.standards.error_codes import (
    StandardErrorCodes,
    get_error_code,
    get_error_message,
)


class TestStandardErrorCodes(TestCase):
    """Test StandardErrorCodes class."""

    def test_validation_error_codes(self):
        """Test validation error codes."""
        self.assertEqual(StandardErrorCodes.VALIDATION_ERROR, "VALIDATION_ERROR")
        self.assertEqual(StandardErrorCodes.VALIDATION_FAILED, "VALIDATION_FAILED")
        self.assertEqual(StandardErrorCodes.INVALID_INPUT, "INVALID_INPUT")
        self.assertEqual(StandardErrorCodes.MISSING_REQUIRED_FIELD, "MISSING_REQUIRED_FIELD")
        self.assertEqual(StandardErrorCodes.INVALID_FORMAT, "INVALID_FORMAT")

    def test_auth_error_codes(self):
        """Test authentication error codes."""
        self.assertEqual(StandardErrorCodes.AUTH_UNAUTHORIZED, "AUTH_UNAUTHORIZED")
        self.assertEqual(StandardErrorCodes.AUTH_TOKEN_EXPIRED, "AUTH_TOKEN_EXPIRED")
        self.assertEqual(StandardErrorCodes.AUTH_TOKEN_INVALID, "AUTH_TOKEN_INVALID")
        self.assertEqual(
            StandardErrorCodes.AUTH_CREDENTIALS_INVALID, "AUTH_CREDENTIALS_INVALID"
        )

    def test_authorization_error_codes(self):
        """Test authorization error codes."""
        self.assertEqual(StandardErrorCodes.AUTH_FORBIDDEN, "AUTH_FORBIDDEN")
        self.assertEqual(StandardErrorCodes.PERMISSION_DENIED, "PERMISSION_DENIED")
        self.assertEqual(
            StandardErrorCodes.INSUFFICIENT_PERMISSIONS, "INSUFFICIENT_PERMISSIONS"
        )
        self.assertEqual(StandardErrorCodes.TENANT_ACCESS_DENIED, "TENANT_ACCESS_DENIED")

    def test_not_found_error_codes(self):
        """Test not found error codes."""
        self.assertEqual(StandardErrorCodes.NOT_FOUND, "NOT_FOUND")
        self.assertEqual(StandardErrorCodes.RESOURCE_NOT_FOUND, "RESOURCE_NOT_FOUND")
        self.assertEqual(StandardErrorCodes.ENDPOINT_NOT_FOUND, "ENDPOINT_NOT_FOUND")

    def test_conflict_error_codes(self):
        """Test conflict error codes."""
        self.assertEqual(StandardErrorCodes.CONFLICT_ERROR, "CONFLICT_ERROR")
        self.assertEqual(StandardErrorCodes.RESOURCE_CONFLICT, "RESOURCE_CONFLICT")
        self.assertEqual(StandardErrorCodes.DUPLICATE_RESOURCE, "DUPLICATE_RESOURCE")

    def test_rate_limiting_error_codes(self):
        """Test rate limiting error codes."""
        self.assertEqual(StandardErrorCodes.RATE_LIMIT_EXCEEDED, "RATE_LIMIT_EXCEEDED")
        self.assertEqual(StandardErrorCodes.TOO_MANY_REQUESTS, "TOO_MANY_REQUESTS")

    def test_server_error_codes(self):
        """Test server error codes."""
        self.assertEqual(StandardErrorCodes.INTERNAL_ERROR, "INTERNAL_ERROR")
        self.assertEqual(StandardErrorCodes.SERVER_ERROR, "SERVER_ERROR")
        self.assertEqual(StandardErrorCodes.DATABASE_ERROR, "DATABASE_ERROR")

    def test_service_unavailable_error_codes(self):
        """Test service unavailable error codes."""
        self.assertEqual(StandardErrorCodes.SERVICE_UNAVAILABLE, "SERVICE_UNAVAILABLE")
        self.assertEqual(StandardErrorCodes.BAD_GATEWAY, "BAD_GATEWAY")
        self.assertEqual(StandardErrorCodes.SERVICE_TIMEOUT, "SERVICE_TIMEOUT")

    def test_contract_error_codes(self):
        """Test contract-specific error codes."""
        self.assertEqual(
            StandardErrorCodes.CONTRACT_VALIDATION_FAILED, "CONTRACT_VALIDATION_FAILED"
        )
        self.assertEqual(
            StandardErrorCodes.CONTRACT_NORMALIZATION_FAILED,
            "CONTRACT_NORMALIZATION_FAILED",
        )
        self.assertEqual(StandardErrorCodes.CONTRACT_CLI_ERROR, "CONTRACT_CLI_ERROR")

    def test_status_to_code_mapping(self):
        """Test HTTP status to error code mapping."""
        self.assertEqual(
            StandardErrorCodes.STATUS_TO_CODE[status.HTTP_400_BAD_REQUEST],
            StandardErrorCodes.VALIDATION_ERROR,
        )
        self.assertEqual(
            StandardErrorCodes.STATUS_TO_CODE[status.HTTP_401_UNAUTHORIZED],
            StandardErrorCodes.AUTH_UNAUTHORIZED,
        )
        self.assertEqual(
            StandardErrorCodes.STATUS_TO_CODE[status.HTTP_403_FORBIDDEN],
            StandardErrorCodes.AUTH_FORBIDDEN,
        )
        self.assertEqual(
            StandardErrorCodes.STATUS_TO_CODE[status.HTTP_404_NOT_FOUND],
            StandardErrorCodes.NOT_FOUND,
        )
        self.assertEqual(
            StandardErrorCodes.STATUS_TO_CODE[status.HTTP_409_CONFLICT],
            StandardErrorCodes.CONFLICT_ERROR,
        )
        self.assertEqual(
            StandardErrorCodes.STATUS_TO_CODE[status.HTTP_429_TOO_MANY_REQUESTS],
            StandardErrorCodes.RATE_LIMIT_EXCEEDED,
        )
        self.assertEqual(
            StandardErrorCodes.STATUS_TO_CODE[status.HTTP_500_INTERNAL_SERVER_ERROR],
            StandardErrorCodes.INTERNAL_ERROR,
        )


class TestErrorCodeHelpers(TestCase):
    """Test error code helper functions."""

    def test_get_error_code_from_exception(self):
        """Test getting error code from exception with code attribute."""
        exception = Exception()
        exception.code = "CUSTOM_ERROR"

        error_code = get_error_code(exception, status.HTTP_400_BAD_REQUEST)

        self.assertEqual(error_code, "CUSTOM_ERROR")

    def test_get_error_code_from_status(self):
        """Test getting error code from HTTP status."""
        error_code = get_error_code(None, status.HTTP_400_BAD_REQUEST)

        self.assertEqual(error_code, StandardErrorCodes.VALIDATION_ERROR)

    def test_get_error_code_unknown_status(self):
        """Test getting error code for unknown status."""
        error_code = get_error_code(None, 999)

        self.assertEqual(error_code, StandardErrorCodes.INTERNAL_ERROR)

    def test_get_error_message_from_exception(self):
        """Test getting error message from exception."""
        exception = Exception("Custom error message")

        message = get_error_message(exception, status.HTTP_400_BAD_REQUEST)

        self.assertEqual(message, "Custom error message")

    def test_get_error_message_from_exception_with_message_attr(self):
        """Test getting error message from exception with message attribute."""
        exception = Exception()
        exception.message = "Custom message"

        message = get_error_message(exception, status.HTTP_400_BAD_REQUEST)

        self.assertEqual(message, "Custom message")

    def test_get_error_message_with_traceback(self):
        """Test getting error message removes traceback."""
        exception = Exception("Error\nTraceback (most recent call last):\n...")

        message = get_error_message(exception, status.HTTP_400_BAD_REQUEST)

        self.assertEqual(message, "Error")

    def test_get_error_message_with_default(self):
        """Test getting error message with default."""
        message = get_error_message(
            None, status.HTTP_400_BAD_REQUEST, default_message="Default message"
        )

        self.assertEqual(message, "Default message")

    def test_get_error_message_default_messages(self):
        """Test getting default error messages for common status codes."""
        self.assertEqual(
            get_error_message(None, status.HTTP_400_BAD_REQUEST), "Invalid request"
        )
        self.assertEqual(
            get_error_message(None, status.HTTP_401_UNAUTHORIZED),
            "Authentication required",
        )
        self.assertEqual(
            get_error_message(None, status.HTTP_403_FORBIDDEN), "Permission denied"
        )
        self.assertEqual(
            get_error_message(None, status.HTTP_404_NOT_FOUND), "Resource not found"
        )
        self.assertEqual(
            get_error_message(None, status.HTTP_409_CONFLICT), "Resource conflict"
        )
        self.assertEqual(
            get_error_message(None, status.HTTP_429_TOO_MANY_REQUESTS),
            "Rate limit exceeded",
        )
        self.assertEqual(
            get_error_message(None, status.HTTP_500_INTERNAL_SERVER_ERROR),
            "Internal server error",
        )
