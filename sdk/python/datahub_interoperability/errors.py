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


# ODPS-specific error classes
class ODPSError(DataHubError):
    """
    Base exception class for all ODPS-related errors in the SDK.

    Maps to backend ODPSError hierarchy with structured error information.
    """

    def __init__(
        self,
        message: str,
        error_code: str = "ODPS_ERROR",
        http_status: int = 400,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        recoverable: bool = False,
        recovery_strategy: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize ODPS error.

        Args:
            message: Error message
            error_code: Machine-readable error code
            http_status: HTTP status code
            request_id: Request ID from API
            details: Additional error details
            recoverable: Whether the error can be recovered from
            recovery_strategy: Suggested recovery strategy
            context: Additional context information
        """
        super().__init__(message, error_code, http_status, request_id, None, details)
        self.recoverable = recoverable
        self.recovery_strategy = recovery_strategy
        self.context = context or {}
        # Extract context from details if available
        if details and isinstance(details, dict):
            if "context" in details:
                self.context.update(details["context"])
            if "recoverable" in details:
                self.recoverable = details["recoverable"]
            if "recovery_strategy" in details:
                self.recovery_strategy = details["recovery_strategy"]


class ODPSValidationError(ODPSError):
    """
    Exception raised when ODPS document validation fails.

    Used for schema validation, required field validation, and data type validation.
    """

    def __init__(
        self,
        message: str,
        error_code: str = "ODPS_VALIDATION_ERROR",
        http_status: int = 400,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        field_path: Optional[str] = None,
        expected: Optional[Any] = None,
        actual: Optional[Any] = None,
    ):
        """
        Initialize ODPS validation error.

        Args:
            message: Error message
            error_code: Machine-readable error code
            http_status: HTTP status code
            request_id: Request ID from API
            details: Additional error details
            field_path: JSON Pointer path to the field that failed validation
            expected: Expected value or type
            actual: Actual value that failed validation
        """
        context = {}
        if field_path:
            context["field_path"] = field_path
        if expected is not None:
            context["expected"] = expected
        if actual is not None:
            context["actual"] = actual
        if details and isinstance(details, dict) and "context" in details:
            context.update(details["context"])

        super().__init__(
            message,
            error_code,
            http_status,
            request_id,
            details,
            recoverable=False,
            recovery_strategy="fail",
            context=context,
        )
        self.field_path = field_path
        self.expected = expected
        self.actual = actual


class ODPSRefResolutionError(ODPSError):
    """
    Exception raised when ODPS $ref resolution fails.

    Used for internal, local, and external reference resolution errors.
    """

    def __init__(
        self,
        message: str,
        error_code: str = "ODPS_REF_RESOLUTION_ERROR",
        http_status: int = 400,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ref_path: Optional[str] = None,
        ref_type: Optional[str] = None,
    ):
        """
        Initialize ODPS ref resolution error.

        Args:
            message: Error message
            error_code: Machine-readable error code
            http_status: HTTP status code
            request_id: Request ID from API
            details: Additional error details
            ref_path: The $ref path that failed to resolve
            ref_type: Type of reference (internal, local, external)
        """
        context = {}
        if ref_path:
            context["ref_path"] = ref_path
        if ref_type:
            context["ref_type"] = ref_type
        if details and isinstance(details, dict) and "context" in details:
            context.update(details["context"])

        # Determine recoverability based on error code
        recoverable = error_code in {
            "ODPS_REF_RATE_LIMIT_EXCEEDED",
            "ODPS_REF_TIMEOUT",
            "ODPS_REF_RESOLUTION_FAILED",
        }
        recovery_strategy = "retry" if recoverable else "fail"

        super().__init__(
            message,
            error_code,
            http_status,
            request_id,
            details,
            recoverable=recoverable,
            recovery_strategy=recovery_strategy,
            context=context,
        )
        self.ref_path = ref_path
        self.ref_type = ref_type


class ODPSExportError(ODPSError):
    """
    Exception raised when ODPS export/generation fails.
    """

    def __init__(
        self,
        message: str,
        error_code: str = "ODPS_EXPORT_ERROR",
        http_status: int = 500,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        field_path: Optional[str] = None,
    ):
        """
        Initialize ODPS export error.

        Args:
            message: Error message
            error_code: Machine-readable error code
            http_status: HTTP status code
            request_id: Request ID from API
            details: Additional error details
            field_path: JSON Pointer path to the field that caused the error
        """
        context = {}
        if field_path:
            context["field_path"] = field_path
        if details and isinstance(details, dict) and "context" in details:
            context.update(details["context"])

        super().__init__(
            message,
            error_code,
            http_status,
            request_id,
            details,
            recoverable=True,  # Export errors are typically recoverable
            recovery_strategy="retry",
            context=context,
        )
        self.field_path = field_path


class ODPSLinkingError(ODPSError):
    """
    Exception raised when ODPS/ODCS linking operations fail.
    """

    def __init__(
        self,
        message: str,
        error_code: str = "ODPS_LINKING_ERROR",
        http_status: int = 400,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize ODPS linking error.

        Args:
            message: Error message
            error_code: Machine-readable error code
            http_status: HTTP status code
            request_id: Request ID from API
            details: Additional error details
        """
        super().__init__(
            message,
            error_code,
            http_status,
            request_id,
            details,
            recoverable=False,
            recovery_strategy="fail",
        )


# ODCS-specific error classes
class ODCSError(DataHubError):
    """
    Base exception class for all ODCS-related errors in the SDK.

    Maps to backend ODCSError hierarchy with structured error information.
    """

    def __init__(
        self,
        message: str,
        error_code: str = "ODCS_ERROR",
        http_status: int = 400,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        recoverable: bool = False,
        recovery_strategy: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize ODCS error.

        Args:
            message: Error message
            error_code: Machine-readable error code
            http_status: HTTP status code
            request_id: Request ID from API
            details: Additional error details
            recoverable: Whether the error can be recovered from
            recovery_strategy: Suggested recovery strategy
            context: Additional context information
        """
        super().__init__(message, error_code, http_status, request_id, None, details)
        self.recoverable = recoverable
        self.recovery_strategy = recovery_strategy
        self.context = context or {}
        # Extract context from details if available
        if details and isinstance(details, dict):
            if "context" in details:
                self.context.update(details["context"])
            if "recoverable" in details:
                self.recoverable = details["recoverable"]
            if "recovery_strategy" in details:
                self.recovery_strategy = details["recovery_strategy"]


class ODCSValidationError(ODCSError):
    """
    Exception raised when ODCS document validation fails.

    Used for schema validation, required field validation, and data type validation.
    """

    def __init__(
        self,
        message: str,
        error_code: str = "ODCS_VALIDATION_ERROR",
        http_status: int = 400,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        field_path: Optional[str] = None,
        expected: Optional[Any] = None,
        actual: Optional[Any] = None,
    ):
        """
        Initialize ODCS validation error.

        Args:
            message: Error message
            error_code: Machine-readable error code
            http_status: HTTP status code
            request_id: Request ID from API
            details: Additional error details
            field_path: JSON Pointer path to the field that failed validation
            expected: Expected value or type
            actual: Actual value that failed validation
        """
        context = {}
        if field_path:
            context["field_path"] = field_path
        if expected is not None:
            context["expected"] = expected
        if actual is not None:
            context["actual"] = actual
        if details and isinstance(details, dict) and "context" in details:
            context.update(details["context"])

        super().__init__(
            message,
            error_code,
            http_status,
            request_id,
            details,
            recoverable=False,
            recovery_strategy="fail",
            context=context,
        )
        self.field_path = field_path
        self.expected = expected
        self.actual = actual


class ODCSExportError(ODCSError):
    """
    Exception raised when ODCS export/generation fails.
    """

    def __init__(
        self,
        message: str,
        error_code: str = "ODCS_EXPORT_ERROR",
        http_status: int = 500,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        field_path: Optional[str] = None,
    ):
        """
        Initialize ODCS export error.

        Args:
            message: Error message
            error_code: Machine-readable error code
            http_status: HTTP status code
            request_id: Request ID from API
            details: Additional error details
            field_path: JSON Pointer path to the field that caused the error
        """
        context = {}
        if field_path:
            context["field_path"] = field_path
        if details and isinstance(details, dict) and "context" in details:
            context.update(details["context"])

        super().__init__(
            message,
            error_code,
            http_status,
            request_id,
            details,
            recoverable=True,  # Export errors are typically recoverable
            recovery_strategy="retry",
            context=context,
        )
        self.field_path = field_path


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

    # Handle FastAPI/DRF style {"detail": "..."} format
    if "detail" in response_data and "error" not in response_data:
        detail = response_data["detail"]
        http_status = response_data.get("http_status", 500)
        # Convert detail to error format for consistent handling
        if isinstance(detail, str):
            response_data = {
                "error": {
                    "message": detail,
                    "code": "ERROR",
                    "http_status": http_status,
                }
            }
        elif isinstance(detail, dict):
            response_data = {"error": detail}
        else:
            response_data = {
                "error": {
                    "message": str(detail),
                    "code": "ERROR",
                    "http_status": http_status,
                }
            }

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
        # Check details dict first
        if isinstance(details, dict):
            retry_after = details.get("retry_after")
        # Also check top-level error dict (DRF format)
        if retry_after is None and isinstance(error, dict):
            retry_after = error.get("retry_after")
        # Also check top-level response_data (some API formats)
        if retry_after is None and isinstance(response_data, dict):
            retry_after = response_data.get("retry_after")

        # Convert to int if it's a string or ErrorDetail-like object
        if retry_after is not None:
            try:
                if isinstance(retry_after, str):
                    retry_after = int(retry_after.strip())
                elif hasattr(retry_after, '__str__'):
                    # Handle ErrorDetail objects
                    retry_after = int(str(retry_after).strip())
                else:
                    retry_after = int(retry_after)
            except (ValueError, TypeError):
                retry_after = None

        return RateLimitError(message, request_id, retry_after)
    elif http_status >= 500:
        return ServerError(message, code, http_status, request_id)
    else:
        return DataHubError(message, code, http_status, request_id, timestamp, details)


def parse_odcs_error(response_data: Any) -> ODCSError:
    """
    Parse ODCS-specific error response and return appropriate ODCS error class.

    Maps backend ODCS error codes to SDK ODCS error classes.

    Args:
        response_data: Error response from API (dict, str, or other)

    Returns:
        Appropriate ODCSError subclass
    """
    # First parse as standard error
    base_error = parse_error(response_data)

    # If not a dict or doesn't have error structure, return base error wrapped as ODCS error
    if not isinstance(response_data, dict) or "error" not in response_data:
        return ODCSError(
            base_error.message,
            base_error.code,
            base_error.http_status,
            base_error.request_id,
            base_error.details,
        )

    error = response_data["error"]
    if not isinstance(error, dict):
        return ODCSError(
            base_error.message,
            base_error.code,
            base_error.http_status,
            base_error.request_id,
            base_error.details,
        )

    code = error.get("code", base_error.code)
    http_status = error.get("http_status", base_error.http_status)
    message = error.get("message", base_error.message)
    request_id = error.get("request_id", base_error.request_id)
    details = error.get("details", base_error.details or {})
    context = error.get("context", {})

    # Map ODCS error codes to specific error classes
    code_upper = code.upper()

    # ODCS Validation Errors
    if "VALIDATION" in code_upper or "SCHEMA" in code_upper or "REQUIRED_FIELD" in code_upper:
        field_path = context.get("field_path") if isinstance(context, dict) else None
        expected = context.get("expected") if isinstance(context, dict) else None
        actual = context.get("actual") if isinstance(context, dict) else None
        return ODCSValidationError(
            message,
            code,
            http_status,
            request_id,
            details,
            field_path=field_path,
            expected=expected,
            actual=actual,
        )

    # ODCS Export Errors
    if "EXPORT" in code_upper or "SERIALIZATION" in code_upper or "FORMAT" in code_upper:
        field_path = context.get("field_path") if isinstance(context, dict) else None
        return ODCSExportError(
            message,
            code,
            http_status,
            request_id,
            details,
            field_path=field_path,
        )

    # Default to base ODCSError
    recoverable = error.get("recoverable", False) if isinstance(error, dict) else False
    recovery_strategy = error.get("recovery_strategy") if isinstance(error, dict) else None
    return ODCSError(
        message,
        code,
        http_status,
        request_id,
        details,
        recoverable=recoverable,
        recovery_strategy=recovery_strategy,
        context=context if isinstance(context, dict) else {},
    )


def parse_odps_error(response_data: Any) -> ODPSError:
    """
    Parse ODPS-specific error response and return appropriate ODPS error class.

    Maps backend ODPS error codes to SDK ODPS error classes.

    Args:
        response_data: Error response from API (dict, str, or other)

    Returns:
        Appropriate ODPSError subclass
    """
    # First parse as standard error
    base_error = parse_error(response_data)

    # If not a dict or doesn't have error structure, return base error wrapped as ODPS error
    if not isinstance(response_data, dict) or "error" not in response_data:
        return ODPSError(
            base_error.message,
            base_error.code,
            base_error.http_status,
            base_error.request_id,
            base_error.details,
        )

    error = response_data["error"]
    if not isinstance(error, dict):
        return ODPSError(
            base_error.message,
            base_error.code,
            base_error.http_status,
            base_error.request_id,
            base_error.details,
        )

    code = error.get("code", base_error.code)
    http_status = error.get("http_status", base_error.http_status)
    message = error.get("message", base_error.message)
    request_id = error.get("request_id", base_error.request_id)
    details = error.get("details", base_error.details or {})
    context = error.get("context", {})

    # Map ODPS error codes to specific error classes
    code_upper = code.upper()

    # ODPS Validation Errors
    if "VALIDATION" in code_upper or "SCHEMA" in code_upper or "REQUIRED_FIELD" in code_upper:
        field_path = context.get("field_path") if isinstance(context, dict) else None
        expected = context.get("expected") if isinstance(context, dict) else None
        actual = context.get("actual") if isinstance(context, dict) else None
        return ODPSValidationError(
            message,
            code,
            http_status,
            request_id,
            details,
            field_path=field_path,
            expected=expected,
            actual=actual,
        )

    # ODPS Ref Resolution Errors
    if "REF" in code_upper or "RESOLUTION" in code_upper:
        ref_path = context.get("ref_path") if isinstance(context, dict) else None
        ref_type = context.get("ref_type") if isinstance(context, dict) else None
        return ODPSRefResolutionError(
            message,
            code,
            http_status,
            request_id,
            details,
            ref_path=ref_path,
            ref_type=ref_type,
        )

    # ODPS Export Errors
    if "EXPORT" in code_upper or "SERIALIZATION" in code_upper or "FORMAT" in code_upper:
        field_path = context.get("field_path") if isinstance(context, dict) else None
        return ODPSExportError(
            message,
            code,
            http_status,
            request_id,
            details,
            field_path=field_path,
        )

    # ODPS Linking Errors
    if "LINK" in code_upper or "LINKING" in code_upper:
        return ODPSLinkingError(
            message,
            code,
            http_status,
            request_id,
            details,
        )

    # Default to base ODPSError
    recoverable = error.get("recoverable", False) if isinstance(error, dict) else False
    recovery_strategy = error.get("recovery_strategy") if isinstance(error, dict) else None
    return ODPSError(
        message,
        code,
        http_status,
        request_id,
        details,
        recoverable=recoverable,
        recovery_strategy=recovery_strategy,
        context=context if isinstance(context, dict) else {},
    )


# Marketplace-specific error classes
class MarketplaceError(DataHubError):
    """
    Base exception class for all marketplace-related errors in the SDK.
    """

    def __init__(
        self,
        message: str,
        error_code: str = "MARKETPLACE_ERROR",
        http_status: int = 400,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize marketplace error.

        Args:
            message: Error message
            error_code: Machine-readable error code
            http_status: HTTP status code
            request_id: Request ID from API
            details: Additional error details
        """
        super().__init__(message, error_code, http_status, request_id, None, details)


class MarketplaceValidationError(MarketplaceError):
    """
    Exception raised when marketplace operation validation fails.
    """

    def __init__(
        self,
        message: str,
        error_code: str = "MARKETPLACE_VALIDATION_ERROR",
        http_status: int = 400,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        field_path: Optional[str] = None,
        expected: Optional[Any] = None,
        actual: Optional[Any] = None,
    ):
        """
        Initialize marketplace validation error.

        Args:
            message: Error message
            error_code: Machine-readable error code
            http_status: HTTP status code
            request_id: Request ID from API
            details: Additional error details
            field_path: JSON Pointer path to the field that failed validation
            expected: Expected value or type
            actual: Actual value that failed validation
        """
        context = {}
        if field_path:
            context["field_path"] = field_path
        if expected is not None:
            context["expected"] = expected
        if actual is not None:
            context["actual"] = actual
        if details and isinstance(details, dict) and "context" in details:
            context.update(details["context"])

        if details is None:
            details = {}
        if "context" not in details:
            details["context"] = context
        else:
            details["context"].update(context)

        super().__init__(
            message,
            error_code,
            http_status,
            request_id,
            details,
        )
        self.field_path = field_path
        self.expected = expected
        self.actual = actual


class MarketplaceConnectionError(MarketplaceError):
    """
    Exception raised when marketplace connection operations fail.
    """

    def __init__(
        self,
        message: str,
        error_code: str = "MARKETPLACE_CONNECTION_ERROR",
        http_status: int = 400,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize marketplace connection error.

        Args:
            message: Error message
            error_code: Machine-readable error code
            http_status: HTTP status code
            request_id: Request ID from API
            details: Additional error details
        """
        super().__init__(
            message,
            error_code,
            http_status,
            request_id,
            details,
        )


# BaaS-specific error classes
class BaaSError(DataHubError):
    """
    Base exception class for all BaaS-related errors in the SDK.
    """

    def __init__(
        self,
        message: str,
        error_code: str = "BAAS_ERROR",
        http_status: int = 400,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize BaaS error.

        Args:
            message: Error message
            error_code: Machine-readable error code
            http_status: HTTP status code
            request_id: Request ID from API
            details: Additional error details
        """
        super().__init__(message, error_code, http_status, request_id, None, details)


class BaaSValidationError(BaaSError):
    """
    Exception raised when BaaS operation validation fails.
    """

    def __init__(
        self,
        message: str,
        error_code: str = "BAAS_VALIDATION_ERROR",
        http_status: int = 400,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        field_path: Optional[str] = None,
        expected: Optional[Any] = None,
        actual: Optional[Any] = None,
    ):
        """
        Initialize BaaS validation error.

        Args:
            message: Error message
            error_code: Machine-readable error code
            http_status: HTTP status code
            request_id: Request ID from API
            details: Additional error details
            field_path: JSON Pointer path to the field that failed validation
            expected: Expected value or type
            actual: Actual value that failed validation
        """
        context = {}
        if field_path:
            context["field_path"] = field_path
        if expected is not None:
            context["expected"] = expected
        if actual is not None:
            context["actual"] = actual
        if details and isinstance(details, dict) and "context" in details:
            context.update(details["context"])

        if details is None:
            details = {}
        if "context" not in details:
            details["context"] = context
        else:
            details["context"].update(context)

        super().__init__(
            message,
            error_code,
            http_status,
            request_id,
            details,
        )
        self.field_path = field_path
        self.expected = expected
        self.actual = actual


# ODH ML-specific error classes
class ODHMLError(DataHubError):
    """
    Base exception class for all ODH ML-related errors in the SDK.
    """

    def __init__(
        self,
        message: str,
        error_code: str = "ODH_ML_ERROR",
        http_status: int = 400,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize ODH ML error.

        Args:
            message: Error message
            error_code: Machine-readable error code
            http_status: HTTP status code
            request_id: Request ID from API
            details: Additional error details
        """
        super().__init__(message, error_code, http_status, request_id, None, details)


class ODHMLValidationError(ODHMLError):
    """
    Exception raised when ODH ML operation validation fails.
    """

    def __init__(
        self,
        message: str,
        error_code: str = "ODH_ML_VALIDATION_ERROR",
        http_status: int = 400,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        field_path: Optional[str] = None,
        expected: Optional[Any] = None,
        actual: Optional[Any] = None,
    ):
        """
        Initialize ODH ML validation error.

        Args:
            message: Error message
            error_code: Machine-readable error code
            http_status: HTTP status code
            request_id: Request ID from API
            details: Additional error details
            field_path: JSON Pointer path to the field that failed validation
            expected: Expected value or type
            actual: Actual value that failed validation
        """
        context = {}
        if field_path:
            context["field_path"] = field_path
        if expected is not None:
            context["expected"] = expected
        if actual is not None:
            context["actual"] = actual
        if details and isinstance(details, dict) and "context" in details:
            context.update(details["context"])

        if details is None:
            details = {}
        if "context" not in details:
            details["context"] = context
        else:
            details["context"].update(context)

        super().__init__(message, error_code, http_status, request_id, details)
        self.field_path = field_path
        self.expected = expected
        self.actual = actual


class ODHMLNotFoundError(ODHMLError):
    """
    Exception raised when ODH ML resource is not found.
    """

    def __init__(
        self,
        message: str = "ODH ML resource not found",
        error_code: str = "ODH_ML_NOT_FOUND",
        http_status: int = 404,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize ODH ML not found error.

        Args:
            message: Error message
            error_code: Machine-readable error code
            http_status: HTTP status code
            request_id: Request ID from API
            details: Additional error details
        """
        super().__init__(message, error_code, http_status, request_id, details)


class ODHMLConflictError(ODHMLError):
    """
    Exception raised when ODH ML operation conflicts with existing state.
    """

    def __init__(
        self,
        message: str,
        error_code: str = "ODH_ML_CONFLICT",
        http_status: int = 409,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize ODH ML conflict error.

        Args:
            message: Error message
            error_code: Machine-readable error code
            http_status: HTTP status code
            request_id: Request ID from API
            details: Additional error details
        """
        super().__init__(message, error_code, http_status, request_id, details)


# Model Serving-specific error classes
class ModelServingError(DataHubError):
    """
    Base exception class for all model serving-related errors in the SDK.
    """

    def __init__(
        self,
        message: str,
        error_code: str = "MODEL_SERVING_ERROR",
        http_status: int = 400,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize model serving error.

        Args:
            message: Error message
            error_code: Machine-readable error code
            http_status: HTTP status code
            request_id: Request ID from API
            details: Additional error details
        """
        super().__init__(message, error_code, http_status, request_id, None, details)


class ModelServingValidationError(ModelServingError):
    """
    Exception raised when model serving operation validation fails.
    """

    def __init__(
        self,
        message: str,
        error_code: str = "MODEL_SERVING_VALIDATION_ERROR",
        http_status: int = 400,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        field_path: Optional[str] = None,
        expected: Optional[Any] = None,
        actual: Optional[Any] = None,
    ):
        """
        Initialize model serving validation error.

        Args:
            message: Error message
            error_code: Machine-readable error code
            http_status: HTTP status code
            request_id: Request ID from API
            details: Additional error details
            field_path: JSON Pointer path to the field that failed validation
            expected: Expected value or type
            actual: Actual value that failed validation
        """
        context = {}
        if field_path:
            context["field_path"] = field_path
        if expected is not None:
            context["expected"] = expected
        if actual is not None:
            context["actual"] = actual
        if details and isinstance(details, dict) and "context" in details:
            context.update(details["context"])

        if details is None:
            details = {}
        if "context" not in details:
            details["context"] = context
        else:
            details["context"].update(context)

        super().__init__(message, error_code, http_status, request_id, details)
        self.field_path = field_path
        self.expected = expected
        self.actual = actual


class ModelServingNotFoundError(ModelServingError):
    """
    Exception raised when model serving resource is not found.
    """

    def __init__(
        self,
        message: str = "Model serving resource not found",
        error_code: str = "MODEL_SERVING_NOT_FOUND",
        http_status: int = 404,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize model serving not found error.

        Args:
            message: Error message
            error_code: Machine-readable error code
            http_status: HTTP status code
            request_id: Request ID from API
            details: Additional error details
        """
        super().__init__(message, error_code, http_status, request_id, details)


class ModelServingDeploymentError(ModelServingError):
    """
    Exception raised when model deployment operation fails.
    """

    def __init__(
        self,
        message: str,
        error_code: str = "MODEL_SERVING_DEPLOYMENT_ERROR",
        http_status: int = 500,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize model serving deployment error.

        Args:
            message: Error message
            error_code: Machine-readable error code
            http_status: HTTP status code
            request_id: Request ID from API
            details: Additional error details
        """
        super().__init__(message, error_code, http_status, request_id, details)


class ABTestError(ModelServingError):
    """
    Exception raised when A/B testing operation fails.
    """

    def __init__(
        self,
        message: str,
        error_code: str = "AB_TEST_ERROR",
        http_status: int = 400,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize A/B test error.

        Args:
            message: Error message
            error_code: Machine-readable error code
            http_status: HTTP status code
            request_id: Request ID from API
            details: Additional error details
        """
        super().__init__(message, error_code, http_status, request_id, details)


# ── Phase 118F.20: New error classes ─────────────────────


class BillingError(DataHubError):
    def __init__(self, msg, code="BILLING_ERROR", status=400, rid=None, details=None):
        super().__init__(msg, code, status, rid, details=details)

class BillingValidationError(BillingError):
    def __init__(self, msg, rid=None, details=None):
        super().__init__(msg, "BILLING_VALIDATION_ERROR", 400, rid, details)

class DowngradeLimitExceededError(BillingError):
    def __init__(self, msg, rid=None, details=None):
        super().__init__(msg, "DOWNGRADE_LIMIT_EXCEEDED", 400, rid, details)

class TransformationError(DataHubError):
    def __init__(self, msg, code="TRANSFORMATION_ERROR", status=400, rid=None, details=None):
        super().__init__(msg, code, status, rid, details=details)

class TransformationValidationError(TransformationError):
    def __init__(self, msg, rid=None, details=None):
        super().__init__(msg, "TRANSFORMATION_VALIDATION_ERROR", 400, rid, details)

class ComplianceError(DataHubError):
    def __init__(self, msg, code="COMPLIANCE_ERROR", status=400, rid=None, details=None):
        super().__init__(msg, code, status, rid, details=details)

class ComplianceValidationError(ComplianceError):
    def __init__(self, msg, rid=None, details=None):
        super().__init__(msg, "COMPLIANCE_VALIDATION_ERROR", 400, rid, details)

class SemanticError(DataHubError):
    def __init__(self, msg, code="SEMANTIC_ERROR", status=400, rid=None, details=None):
        super().__init__(msg, code, status, rid, details=details)

class SPARQLError(SemanticError):
    def __init__(self, msg, rid=None, details=None):
        super().__init__(msg, "SPARQL_ERROR", 400, rid, details)

class SHACLValidationError(SemanticError):
    def __init__(self, msg, rid=None, details=None):
        super().__init__(msg, "SHACL_VALIDATION_ERROR", 400, rid, details)

class WorkflowError(DataHubError):
    def __init__(self, msg, code="WORKFLOW_ERROR", status=400, rid=None, details=None):
        super().__init__(msg, code, status, rid, details=details)

class DLQError(DataHubError):
    def __init__(self, msg, code="DLQ_ERROR", status=500, rid=None, details=None):
        super().__init__(msg, code, status, rid, details=details)

class EntitlementRequiredError(ForbiddenError):
    def __init__(self, msg="Entitlement required", rid=None):
        super().__init__(msg, rid)
        self.code = "ENTITLEMENT_REQUIRED"

class CircuitBreakerOpenError(ServerError):
    def __init__(self, msg="Circuit breaker open", rid=None):
        super().__init__(msg, "CIRCUIT_BREAKER_OPEN", 503, rid)

class ModelDeploymentError(DataHubError):
    def __init__(self, msg, code="MODEL_DEPLOYMENT_ERROR", status=400, rid=None, details=None):
        super().__init__(msg, code, status, rid, details=details)
