"""
Standardized Error Codes

Provides consistent error code definitions and mappings.
"""

from typing import Dict, Optional

from rest_framework import status


class StandardErrorCodes:
    """
    Standard error codes for API responses.

    All error codes follow the pattern: CATEGORY_SPECIFIC_ERROR
    """

    # Validation errors (400)
    VALIDATION_ERROR = "VALIDATION_ERROR"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    INVALID_INPUT = "INVALID_INPUT"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    INVALID_FORMAT = "INVALID_FORMAT"

    # Authentication errors (401)
    AUTH_UNAUTHORIZED = "AUTH_UNAUTHORIZED"
    AUTH_TOKEN_EXPIRED = "AUTH_TOKEN_EXPIRED"
    AUTH_TOKEN_INVALID = "AUTH_TOKEN_INVALID"
    AUTH_CREDENTIALS_INVALID = "AUTH_CREDENTIALS_INVALID"

    # Authorization errors (403)
    AUTH_FORBIDDEN = "AUTH_FORBIDDEN"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"
    TENANT_ACCESS_DENIED = "TENANT_ACCESS_DENIED"

    # Not found errors (404)
    NOT_FOUND = "NOT_FOUND"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    ENDPOINT_NOT_FOUND = "ENDPOINT_NOT_FOUND"

    # Conflict errors (409)
    CONFLICT_ERROR = "CONFLICT_ERROR"
    RESOURCE_CONFLICT = "RESOURCE_CONFLICT"
    DUPLICATE_RESOURCE = "DUPLICATE_RESOURCE"

    # Rate limiting (429)
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    TOO_MANY_REQUESTS = "TOO_MANY_REQUESTS"

    # Server errors (500)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVER_ERROR = "SERVER_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"

    # Service unavailable (502/503)
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    BAD_GATEWAY = "BAD_GATEWAY"
    SERVICE_TIMEOUT = "SERVICE_TIMEOUT"

    # Contract-specific errors
    CONTRACT_VALIDATION_FAILED = "CONTRACT_VALIDATION_FAILED"
    CONTRACT_NORMALIZATION_FAILED = "CONTRACT_NORMALIZATION_FAILED"
    CONTRACT_CLI_ERROR = "CONTRACT_CLI_ERROR"

    # Phase 32 — Semantic-specific errors
    MISSING_TENANT_ID = "MISSING_TENANT_ID"
    INVALID_SPARQL = "INVALID_SPARQL"
    QUERY_TIMEOUT = "QUERY_TIMEOUT"
    SHACL_VIOLATION = "SHACL_VIOLATION"
    TENANT_MISMATCH = "TENANT_MISMATCH"
    UNSUPPORTED_RDF_MEDIA_TYPE = "UNSUPPORTED_RDF_MEDIA_TYPE"

    # Mapping from HTTP status to default error code
    STATUS_TO_CODE: Dict[int, str] = {
        status.HTTP_400_BAD_REQUEST: VALIDATION_ERROR,
        status.HTTP_401_UNAUTHORIZED: AUTH_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: AUTH_FORBIDDEN,
        status.HTTP_404_NOT_FOUND: NOT_FOUND,
        status.HTTP_409_CONFLICT: CONFLICT_ERROR,
        status.HTTP_429_TOO_MANY_REQUESTS: RATE_LIMIT_EXCEEDED,
        status.HTTP_500_INTERNAL_SERVER_ERROR: INTERNAL_ERROR,
        status.HTTP_502_BAD_GATEWAY: SERVICE_UNAVAILABLE,
        status.HTTP_503_SERVICE_UNAVAILABLE: SERVICE_UNAVAILABLE,
    }


def get_error_code(
    exception: Optional[Exception] = None,
    http_status: int = status.HTTP_400_BAD_REQUEST,
) -> str:
    """
    Get error code from exception or HTTP status.

    Args:
        exception: Exception instance (optional)
        http_status: HTTP status code

    Returns:
        Error code string
    """
    # Check if exception has a code attribute
    if exception and hasattr(exception, "code") and exception.code:
        return exception.code

    # Map HTTP status to error code
    return StandardErrorCodes.STATUS_TO_CODE.get(
        http_status,
        StandardErrorCodes.INTERNAL_ERROR,
    )


def get_error_message(
    exception: Optional[Exception] = None,
    http_status: int = status.HTTP_400_BAD_REQUEST,
    default_message: Optional[str] = None,
) -> str:
    """
    Get user-friendly error message.

    Args:
        exception: Exception instance (optional)
        http_status: HTTP status code
        default_message: Default message if none found

    Returns:
        Error message string
    """
    # Check if exception has a message attribute
    if exception and hasattr(exception, "message") and exception.message:
        return exception.message

    # Use exception string representation
    if exception:
        message = str(exception)
        # Remove stack traces and internal details
        if "Traceback" in message:
            message = message.split("Traceback")[0].strip()
        if message and message != "None":
            return message

    # Use default message if provided
    if default_message:
        return default_message

    # Default messages for common status codes
    default_messages = {
        status.HTTP_400_BAD_REQUEST: "Invalid request",
        status.HTTP_401_UNAUTHORIZED: "Authentication required",
        status.HTTP_403_FORBIDDEN: "Permission denied",
        status.HTTP_404_NOT_FOUND: "Resource not found",
        status.HTTP_409_CONFLICT: "Resource conflict",
        status.HTTP_429_TOO_MANY_REQUESTS: "Rate limit exceeded",
        status.HTTP_500_INTERNAL_SERVER_ERROR: "Internal server error",
    }

    return default_messages.get(http_status, "An error occurred")
