"""
SDK Error Classes

Typed exceptions for API errors matching the standard error envelope.
"""

from datetime import datetime
from typing import Any, Dict, Optional


class DataHubError(Exception):
    """
    Base error class for all SDK errors
    """

    def __init__(
        self,
        message: str,
        code: str,
        http_status: int,
        request_id: Optional[str] = None,
        timestamp: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.http_status = http_status
        self.request_id = request_id
        self.timestamp = timestamp
        self.details = details

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert error to dictionary for serialization
        """
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "http_status": self.http_status,
                "request_id": self.request_id,
                "timestamp": self.timestamp,
                "details": self.details,
            }
        }

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(code={self.code!r}, "
            f"http_status={self.http_status}, message={self.message!r})"
        )


class ValidationError(DataHubError):
    """Validation error (400)"""

    def __init__(
        self,
        message: str,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, "VALIDATION_ERROR", 400, request_id, None, details)


class UnauthorizedError(DataHubError):
    """Authentication error (401)"""

    def __init__(self, message: str = "Authentication required", request_id: Optional[str] = None):
        super().__init__(message, "AUTH_UNAUTHORIZED", 401, request_id)


class ForbiddenError(DataHubError):
    """Authorization error (403)"""

    def __init__(self, message: str = "Permission denied", request_id: Optional[str] = None):
        super().__init__(message, "AUTH_FORBIDDEN", 403, request_id)


class NotFoundError(DataHubError):
    """Not found error (404)"""

    def __init__(self, message: str = "Resource not found", request_id: Optional[str] = None):
        super().__init__(message, "NOT_FOUND", 404, request_id)


class ConflictError(DataHubError):
    """Conflict error (409)"""

    def __init__(
        self,
        message: str,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, "CONFLICT_ERROR", 409, request_id, None, details)


class RateLimitError(DataHubError):
    """Rate limit error (429)"""

    def __init__(
        self,
        message: str,
        request_id: Optional[str] = None,
        retry_after: Optional[int] = None,
    ):
        super().__init__(message, "RATE_LIMIT_EXCEEDED", 429, request_id)
        self.retry_after = retry_after


class ServerError(DataHubError):
    """Server error (5xx)"""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        http_status: int = 500,
        request_id: Optional[str] = None,
    ):
        super().__init__(message, code, http_status, request_id)


class NetworkError(DataHubError):
    """Network/timeout error"""

    def __init__(self, message: str = "Network error occurred"):
        super().__init__(message, "NETWORK_ERROR", 0)


def parse_error(response_data: Any) -> DataHubError:
    """
    Parse API error response and return appropriate error class

    Args:
        response_data: Error response from API (dict, str, or other)

    Returns:
        Appropriate DataHubError subclass
    """
    # Handle case where response_data is a string
    if isinstance(response_data, str):
        return ServerError(f"Unexpected error: {response_data}", "UNEXPECTED_ERROR", 500)

    # Handle case where response_data is not a dict
    if not isinstance(response_data, dict):
        return ServerError(f"Unexpected error: {response_data}", "UNEXPECTED_ERROR", 500)

    if "error" not in response_data:
        return ServerError("Unexpected error format", "UNKNOWN_ERROR", 500)

    error = response_data["error"]

    # Handle case where error is a string instead of dict
    # This happens when API returns {"error": "message"} format
    if isinstance(error, str):
        # Try to get http_status from response_data if available
        http_status = response_data.get("http_status", 500)
        # Default to 400 for string errors (common for validation errors)
        if http_status == 500:
            http_status = 400
        return (
            ValidationError(error)
            if http_status == 400
            else ServerError(error, "UNKNOWN_ERROR", http_status)
        )

    if not isinstance(error, dict):
        return ServerError(f"Unexpected error format: {error}", "UNKNOWN_ERROR", 500)

    code = error.get("code", "UNKNOWN_ERROR")
    http_status = error.get("http_status", 500)
    message = error.get("message", "An error occurred")
    request_id = error.get("request_id")
    timestamp = error.get("timestamp")
    details = error.get("details")

    # Map error codes to specific error classes
    if http_status == 400:
        return ValidationError(message, request_id, details)
    elif http_status == 401:
        return UnauthorizedError(message, request_id)
    elif http_status == 403:
        return ForbiddenError(message, request_id)
    elif http_status == 404:
        return NotFoundError(message, request_id)
    elif http_status == 409:
        return ConflictError(message, request_id, details)
    elif http_status == 429:
        retry_after = None
        if isinstance(details, dict):
            retry_after = details.get("retry_after")
        return RateLimitError(message, request_id, retry_after)
    elif http_status >= 500:
        return ServerError(message, code, http_status, request_id)
    else:
        return DataHubError(message, code, http_status, request_id, timestamp, details)
