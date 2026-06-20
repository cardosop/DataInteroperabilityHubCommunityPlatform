"""
Error Handling Middleware

Middleware for comprehensive error handling, logging, and tracking.
"""

import uuid
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin

from hub.apps.core.error_handling.error_logging import ErrorLogger
from hub.apps.core.error_handling.error_tracking import get_error_tracker


class ErrorHandlingMiddleware(MiddlewareMixin):
    """
    Middleware for comprehensive error handling.

    Provides:
    - Request ID generation
    - Error logging
    - Error tracking (Sentry)
    - Context propagation
    """

    def __init__(self, get_response: Callable):
        """Initialize middleware."""
        super().__init__(get_response)
        self.get_response = get_response
        self.error_logger = ErrorLogger()
        self.error_tracker = get_error_tracker()

    def process_request(self, request: HttpRequest) -> None:
        """Process request - generate request ID."""
        # Generate request ID if not present
        if not hasattr(request, "id"):
            request.id = str(uuid.uuid4())

        # Set request ID in context for logging
        import structlog

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request.id)

    def process_exception(self, request: HttpRequest, exception: Exception) -> HttpResponse | None:
        """
        Process exception - log and track errors.

        Args:
            request: HTTP request
            exception: Exception instance

        Returns:
            None (let Django handle the exception)
        """
        # Get context
        request_id = getattr(request, "id", None)
        tenant_id = getattr(request, "tenant_id", None) if hasattr(request, "tenant_id") else None
        user_id = (
            getattr(request.user, "id", None)
            if hasattr(request, "user") and request.user.is_authenticated
            else None
        )

        # Classify severity: 4xx responses are expected client behaviour
        # (auth failures, not-found, rate-limiting, validation rejections).
        # Only 5xx responses indicate an actual server fault worth an
        # ERROR-level alert.  This keeps the log signal clean so real
        # faults aren't buried under routine HTTP error noise.
        #
        # DRF exceptions carry .status_code directly.  Django exceptions
        # (Http404, PermissionDenied, SuspiciousOperation) do not — map
        # them to their known HTTP status here.
        http_status = getattr(exception, "status_code", None)
        if http_status is None:
            from django.core.exceptions import (
                PermissionDenied as DjangoPermissionDenied,
            )
            from django.core.exceptions import (
                SuspiciousOperation,
            )
            from django.core.exceptions import (
                ValidationError as DjangoValidationError,
            )
            from django.http import Http404 as DjangoHttp404

            if isinstance(exception, DjangoHttp404):
                http_status = 404
            elif isinstance(exception, DjangoPermissionDenied):
                http_status = 403
            elif isinstance(exception, SuspiciousOperation) or isinstance(
                exception, DjangoValidationError
            ):
                http_status = 400
            else:
                http_status = 500
        if http_status < 500:
            log_level = "warning"
        else:
            log_level = "error"

        # Log error
        self.error_logger.log_error(
            error=exception,
            error_code=getattr(exception, "code", None),
            message=str(exception),
            http_status=http_status,
            request_id=request_id,
            tenant_id=str(tenant_id) if tenant_id else None,
            user_id=str(user_id) if user_id else None,
            additional_context={
                "path": request.path,
                "method": request.method,
            },
            level=log_level,
        )

        # Track error in Sentry
        self.error_tracker.track_error(
            error=exception,
            error_code=getattr(exception, "code", None),
            message=str(exception),
            http_status=http_status,
            request_id=request_id,
            tenant_id=str(tenant_id) if tenant_id else None,
            user_id=str(user_id) if user_id else None,
            context={
                "path": request.path,
                "method": request.method,
            },
            level=log_level,
        )

        # Set user context for Sentry
        if user_id:
            self.error_tracker.set_user(str(user_id))
        if tenant_id:
            self.error_tracker.set_tenant(str(tenant_id))

        # Return None to let Django handle the exception
        return None
