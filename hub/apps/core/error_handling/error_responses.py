"""
Standardized Error Responses

Provides comprehensive error response formatting and standardization.
"""

import uuid
from datetime import datetime
from typing import Any

from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from hub.apps.api.standards.error_codes import (
    StandardErrorCodes,
    get_error_code,
    get_error_message,
)


class ErrorResponse:
    """
    Standardized error response structure.

    All error responses follow this format:
    {
        "error": {
            "code": "ERROR_CODE",
            "message": "Human-readable message",
            "http_status": 400,
            "request_id": "uuid",
            "timestamp": "2025-01-15T10:30:00Z",
            "details": {}
        }
    }
    """

    def __init__(
        self,
        code: str,
        message: str,
        http_status: int = status.HTTP_400_BAD_REQUEST,
        details: dict[str, Any] | None = None,
        request_id: str | None = None,
        timestamp: datetime | None = None,
    ):
        """
        Initialize error response.

        Args:
            code: Machine-readable error code
            message: Human-readable error message
            http_status: HTTP status code
            details: Optional error details
            request_id: Optional request ID
            timestamp: Optional timestamp (defaults to now)
        """
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details or {}
        self.request_id = request_id or str(uuid.uuid4())
        self.timestamp = timestamp or timezone.now()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "http_status": self.http_status,
                "request_id": self.request_id,
                "timestamp": self.timestamp.isoformat(),
                **({"details": self.details} if self.details else {}),
            }
        }

    def to_response(self) -> Response:
        """Convert to DRF Response."""
        return Response(self.to_dict(), status=self.http_status)


class ErrorResponseBuilder:
    """Builder for creating standardized error responses."""

    def __init__(self):
        """Initialize builder."""
        self._code: str | None = None
        self._message: str | None = None
        self._http_status: int = status.HTTP_400_BAD_REQUEST
        self._details: dict[str, Any] = {}
        self._request_id: str | None = None
        self._timestamp: datetime | None = None

    def code(self, code: str) -> "ErrorResponseBuilder":
        """Set error code."""
        self._code = code
        return self

    def message(self, message: str) -> "ErrorResponseBuilder":
        """Set error message."""
        self._message = message
        return self

    def http_status(self, http_status: int) -> "ErrorResponseBuilder":
        """Set HTTP status code."""
        self._http_status = http_status
        return self

    def details(self, details: dict[str, Any]) -> "ErrorResponseBuilder":
        """Set error details."""
        self._details = details
        return self

    def add_detail(self, key: str, value: Any) -> "ErrorResponseBuilder":
        """Add a detail field."""
        self._details[key] = value
        return self

    def field_error(
        self, field: str, message: str, code: str = "VALIDATION_ERROR"
    ) -> "ErrorResponseBuilder":
        """Add a field-level error."""
        if "field_errors" not in self._details:
            self._details["field_errors"] = []
        self._details["field_errors"].append(
            {
                "field": field,
                "message": message,
                "code": code,
            }
        )
        return self

    def request_id(self, request_id: str) -> "ErrorResponseBuilder":
        """Set request ID."""
        self._request_id = request_id
        return self

    def timestamp(self, timestamp: datetime) -> "ErrorResponseBuilder":
        """Set timestamp."""
        self._timestamp = timestamp
        return self

    def build(self) -> ErrorResponse:
        """Build error response."""
        if not self._code:
            # Auto-determine code from HTTP status
            self._code = StandardErrorCodes.STATUS_TO_CODE.get(
                self._http_status, StandardErrorCodes.INTERNAL_ERROR
            )

        if not self._message:
            # Auto-determine message from HTTP status
            default_messages = {
                status.HTTP_400_BAD_REQUEST: "Invalid request",
                status.HTTP_401_UNAUTHORIZED: "Authentication required",
                status.HTTP_403_FORBIDDEN: "Permission denied",
                status.HTTP_404_NOT_FOUND: "Resource not found",
                status.HTTP_409_CONFLICT: "Resource conflict",
                status.HTTP_429_TOO_MANY_REQUESTS: "Rate limit exceeded",
                status.HTTP_500_INTERNAL_SERVER_ERROR: "Internal server error",
            }
            self._message = default_messages.get(self._http_status, "An error occurred")

        return ErrorResponse(
            code=self._code,
            message=self._message,
            http_status=self._http_status,
            details=self._details if self._details else None,
            request_id=self._request_id,
            timestamp=self._timestamp,
        )


def format_error_response(
    exception: Exception | None = None,
    code: str | None = None,
    message: str | None = None,
    http_status: int = status.HTTP_400_BAD_REQUEST,
    details: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> Response:
    """
    Format a standardized error response.

    Args:
        exception: Exception instance (optional)
        code: Error code (optional, auto-determined if not provided)
        message: Error message (optional, auto-determined if not provided)
        http_status: HTTP status code
        details: Error details (optional)
        request_id: Request ID (optional)

    Returns:
        Formatted error Response
    """
    # Auto-determine code and message from exception if not provided
    if exception:
        if not code:
            code = get_error_code(exception, http_status)
        if not message:
            message = get_error_message(exception, http_status)

    builder = ErrorResponseBuilder()
    if code:
        builder.code(code)
    if message:
        builder.message(message)
    builder.http_status(http_status)
    if details:
        builder.details(details)
    if request_id:
        builder.request_id(request_id)

    error_response = builder.build()
    return error_response.to_response()
