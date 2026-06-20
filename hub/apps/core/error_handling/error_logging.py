"""
Enhanced Error Logging

Provides comprehensive error logging with context and structured data.
"""

import traceback
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class ErrorLogger:
    """Enhanced error logger with context and structured logging."""

    def __init__(
        self,
        logger_name: str | None = None,
        context: dict[str, Any] | None = None,
    ):
        """
        Initialize error logger.

        Args:
            logger_name: Logger name (defaults to module name)
            context: Additional context for all log entries
        """
        self._logger = structlog.get_logger(logger_name or __name__)
        self._context = context or {}

    def log_error(
        self,
        error: Exception,
        error_code: str | None = None,
        message: str | None = None,
        http_status: int | None = None,
        request_id: str | None = None,
        tenant_id: str | None = None,
        user_id: str | None = None,
        additional_context: dict[str, Any] | None = None,
        level: str = "error",
    ) -> None:
        """
        Log an error with full context.

        Args:
            error: Exception instance
            error_code: Error code
            message: Error message
            http_status: HTTP status code
            request_id: Request ID
            tenant_id: Tenant ID
            user_id: User ID
            additional_context: Additional context
            level: Log level (error, warning, critical)
        """
        log_data = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "error_code": error_code or getattr(error, "code", "UNKNOWN_ERROR"),
            **self._context,
        }

        if message:
            log_data["message"] = message
        if http_status:
            log_data["http_status"] = http_status
        if request_id:
            log_data["request_id"] = request_id
        if tenant_id:
            log_data["tenant_id"] = tenant_id
        if user_id:
            log_data["user_id"] = user_id
        if additional_context:
            log_data.update(additional_context)

        # Add stack trace only for server faults (5xx), not for expected
        # client errors (4xx) — routine 401/403/404 responses should not
        # produce full Python tracebacks in the structured log output.
        is_server_fault = level in ("error", "critical")
        if is_server_fault:
            log_data["traceback"] = traceback.format_exc()

        # Log with appropriate level.
        log_method = getattr(self._logger, level, self._logger.error)
        # Only include exception info (traceback) for server faults.
        # exc_info=True on every call produces full stack traces for
        # expected Http404/PermissionDenied responses, which buries
        # real faults under routine HTTP error noise.
        log_method(
            "error_occurred" if is_server_fault else "http_client_error",
            exc_info=is_server_fault,
            **log_data,
        )

    def log_exception(
        self,
        exception: Exception,
        context: dict[str, Any] | None = None,
        level: str = "error",
    ) -> None:
        """
        Log an exception with full context.

        Args:
            exception: Exception instance
            context: Additional context
            level: Log level
        """
        self.log_error(
            error=exception,
            error_code=getattr(exception, "code", None),
            message=str(exception),
            additional_context=context,
            level=level,
        )

    def log_validation_error(
        self,
        field: str,
        message: str,
        value: Any = None,
        request_id: str | None = None,
        tenant_id: str | None = None,
    ) -> None:
        """
        Log a validation error.

        Args:
            field: Field name
            message: Error message
            value: Invalid value (will be redacted if PII)
            request_id: Request ID
            tenant_id: Tenant ID
        """
        log_data = {
            "error_type": "ValidationError",
            "error_code": "VALIDATION_ERROR",
            "field": field,
            "message": message,
            **self._context,
        }

        if request_id:
            log_data["request_id"] = request_id
        if tenant_id:
            log_data["tenant_id"] = tenant_id

        # Don't log the value if it might be PII
        if value is not None and not isinstance(value, (str, int, float, bool)):
            log_data["value_type"] = type(value).__name__

        self._logger.warning("validation_error", **log_data)

    def log_permission_error(
        self,
        resource: str,
        action: str,
        user_id: str | None = None,
        tenant_id: str | None = None,
        request_id: str | None = None,
    ) -> None:
        """
        Log a permission error.

        Args:
            resource: Resource name
            action: Action attempted
            user_id: User ID
            tenant_id: Tenant ID
            request_id: Request ID
        """
        log_data = {
            "error_type": "PermissionError",
            "error_code": "PERMISSION_DENIED",
            "resource": resource,
            "action": action,
            **self._context,
        }

        if user_id:
            log_data["user_id"] = user_id
        if tenant_id:
            log_data["tenant_id"] = tenant_id
        if request_id:
            log_data["request_id"] = request_id

        self._logger.warning("permission_denied", **log_data)

    def log_not_found_error(
        self,
        resource_type: str,
        resource_id: str,
        request_id: str | None = None,
        tenant_id: str | None = None,
    ) -> None:
        """
        Log a not found error.

        Args:
            resource_type: Resource type
            resource_id: Resource ID
            request_id: Request ID
            tenant_id: Tenant ID
        """
        log_data = {
            "error_type": "NotFoundError",
            "error_code": "NOT_FOUND",
            "resource_type": resource_type,
            "resource_id": resource_id,
            **self._context,
        }

        if request_id:
            log_data["request_id"] = request_id
        if tenant_id:
            log_data["tenant_id"] = tenant_id

        self._logger.warning("resource_not_found", **log_data)


def log_error(
    error: Exception,
    error_code: str | None = None,
    message: str | None = None,
    http_status: int | None = None,
    request_id: str | None = None,
    tenant_id: str | None = None,
    user_id: str | None = None,
    context: dict[str, Any] | None = None,
    level: str = "error",
) -> None:
    """
    Log an error with full context (convenience function).

    Args:
        error: Exception instance
        error_code: Error code
        message: Error message
        http_status: HTTP status code
        request_id: Request ID
        tenant_id: Tenant ID
        user_id: User ID
        context: Additional context
        level: Log level
    """
    error_logger = ErrorLogger()
    error_logger.log_error(
        error=error,
        error_code=error_code,
        message=message,
        http_status=http_status,
        request_id=request_id,
        tenant_id=tenant_id,
        user_id=user_id,
        additional_context=context,
        level=level,
    )


def log_exception(
    exception: Exception,
    context: dict[str, Any] | None = None,
    level: str = "error",
) -> None:
    """
    Log an exception with full context (convenience function).

    Args:
        exception: Exception instance
        context: Additional context
        level: Log level
    """
    error_logger = ErrorLogger()
    error_logger.log_exception(exception, context, level)
