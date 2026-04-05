"""
Standardized Error Response Helper

Provides a consistent error response format across all API endpoints.
Maps service layer exceptions (ValidationError, NotFoundError, ConflictError, PermissionError)
to standardized HTTP responses with consistent structure.

All error responses follow this format (per perfect1 API contract):
{
    "detail": "Human-readable error message",
    "code": "ERROR_CODE",
    "details": {}
}
"""

import logging

from rest_framework import status
from rest_framework.response import Response

from hub.apps.core.services.base import (
    ConflictError,
    NotFoundError,
    PermissionError,
)
from hub.apps.core.services.base import (
    ValidationError as ServiceValidationError,
)

logger = logging.getLogger(__name__)


def api_error_response(
    message: str,
    status_code: int,
    code: str = None,
    details: dict = None,
) -> Response:
    """
    Create a standardized API error response (per perfect1 API contract).

    Standard schema: { "detail": "...", "code": "...", "details": {...} }

    Args:
        message: Human-readable error message
        status_code: HTTP status code
        code: Machine-readable error code (e.g., "VALIDATION_ERROR", "NOT_FOUND")
               If not provided, inferred from status_code
        details: Optional dictionary with additional error details

    Returns:
        DRF Response with standardized error format
    """
    if details is None:
        details = {}

    # Infer error code from status if not provided
    if code is None:
        status_to_code = {
            status.HTTP_400_BAD_REQUEST: "VALIDATION_ERROR",
            status.HTTP_401_UNAUTHORIZED: "AUTH_UNAUTHORIZED",
            status.HTTP_403_FORBIDDEN: "PERMISSION_DENIED",
            status.HTTP_404_NOT_FOUND: "NOT_FOUND",
            status.HTTP_409_CONFLICT: "CONFLICT_ERROR",
            status.HTTP_429_TOO_MANY_REQUESTS: "RATE_LIMIT_EXCEEDED",
            status.HTTP_500_INTERNAL_SERVER_ERROR: "INTERNAL_ERROR",
            status.HTTP_502_BAD_GATEWAY: "SERVICE_UNAVAILABLE",
            status.HTTP_503_SERVICE_UNAVAILABLE: "SERVICE_UNAVAILABLE",
        }
        code = status_to_code.get(status_code, "UNKNOWN_ERROR")

    return Response(
        {
            "detail": message,
            "code": code,
            "details": details,
        },
        status=status_code,
    )


def error_response(
    error: str,
    code: str,
    details: dict = None,
    http_status: int = None,
) -> Response:
    """
    Create a standardized error response (legacy format for backward compatibility).

    DEPRECATED: Use api_error_response() instead for new code.

    Args:
        error: Human-readable error message
        code: Machine-readable error code (e.g., "VALIDATION_ERROR", "NOT_FOUND")
        details: Optional dictionary with additional error details
        http_status: HTTP status code (defaults based on code if not provided)

    Returns:
        DRF Response with standardized error format
    """
    if details is None:
        details = {}

    # Map error codes to HTTP status if not provided
    if http_status is None:
        code_to_status = {
            "VALIDATION_ERROR": status.HTTP_400_BAD_REQUEST,
            "VALIDATION_FAILED": status.HTTP_400_BAD_REQUEST,
            "NOT_FOUND": status.HTTP_404_NOT_FOUND,
            "CONFLICT": status.HTTP_409_CONFLICT,
            "CONFLICT_ERROR": status.HTTP_409_CONFLICT,
            "PERMISSION_DENIED": status.HTTP_403_FORBIDDEN,
            "AUTH_FORBIDDEN": status.HTTP_403_FORBIDDEN,
        }
        http_status = code_to_status.get(code, status.HTTP_400_BAD_REQUEST)

    return Response(
        {
            "error": error,
            "code": code,
            "details": details,
        },
        status=http_status,
    )


def handle_service_exception(exception: Exception) -> Response:
    """
    Handle service layer exceptions and return standardized error response.

    Maps:
    - ValidationError (hub.apps.core.services.base) → 400 Bad Request
    - NotFoundError → 404 Not Found
    - ConflictError → 409 Conflict
    - PermissionError → 403 Forbidden

    Args:
        exception: Service exception instance

    Returns:
        DRF Response with standardized error format (uses api_error_response)
    """
    if isinstance(exception, ServiceValidationError):
        return api_error_response(
            message=exception.message,
            status_code=getattr(exception, "http_status", status.HTTP_400_BAD_REQUEST),
            code=getattr(exception, "code", "VALIDATION_ERROR"),
            details=getattr(exception, "details", {}),
        )
    elif isinstance(exception, NotFoundError):
        return api_error_response(
            message=exception.message,
            status_code=getattr(exception, "http_status", status.HTTP_404_NOT_FOUND),
            code=getattr(exception, "code", "NOT_FOUND"),
            details=getattr(exception, "details", {}),
        )
    elif isinstance(exception, ConflictError):
        return api_error_response(
            message=exception.message,
            status_code=getattr(exception, "http_status", status.HTTP_409_CONFLICT),
            code=getattr(exception, "code", "CONFLICT_ERROR"),
            details=getattr(exception, "details", {}),
        )
    elif isinstance(exception, PermissionError):
        return api_error_response(
            message=str(exception),
            status_code=status.HTTP_403_FORBIDDEN,
            code="PERMISSION_DENIED",
            details={},
        )
    else:
        # Unknown exception - log and return generic error
        logger.exception(
            "Unexpected exception in handle_service_exception",
            extra={"exception_type": type(exception).__name__, "exception_message": str(exception)},
        )
        return api_error_response(
            message="An unexpected error occurred",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="INTERNAL_ERROR",
            details={},
        )
