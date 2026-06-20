"""
Base Service Classes and Utilities

Provides base service classes and error types for the service layer.
Also includes OpenTelemetry instrumentation utilities for service clients.
"""

import logging
import sys
import time
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.paginator import InvalidPage as DjangoInvalidPage
from django.db import IntegrityError as DjangoIntegrityError
from django.db import models

logger = logging.getLogger(__name__)

# OpenTelemetry availability
OPENTELEMETRY_AVAILABLE = False
try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode

    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False


def is_opentelemetry_enabled() -> bool:
    """Check if OpenTelemetry is enabled."""
    if not OPENTELEMETRY_AVAILABLE:
        return False
    from django.conf import settings

    return getattr(settings, "OPENTELEMETRY_ENABLED", False)


# Service Error Classes
class ServiceError(Exception):
    """Base exception for service layer errors."""

    def __init__(
        self,
        message: str = "",
        code: str = "SERVICE_ERROR",
        details: dict[str, Any] | None = None,
        http_status: int = 500,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
        self.http_status = http_status


class ValidationError(ServiceError):
    """Exception raised for validation errors."""

    def __init__(
        self,
        message: str,
        code: str = "VALIDATION_ERROR",
        details: dict[str, Any] | None = None,
        http_status: int = 400,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
        self.http_status = http_status


class NotFoundError(ServiceError):
    """Exception raised when a resource is not found."""

    _SENTINEL = object()

    def __init__(
        self,
        message: str,
        code=_SENTINEL,
        details: dict[str, Any] | None = None,
        http_status: int = 404,
    ):
        # Support positional (resource_type, resource_id) shorthand:
        #   NotFoundError("Asset", "123") → message="Asset", details={"resource_type": "Asset", "resource_id": "123"}
        # But NOT when code= is explicitly an error code like "PLAN_NOT_FOUND".
        if code is self._SENTINEL:
            code = "NOT_FOUND"
        elif details is None and not code.startswith("NOT_FOUND") and not code.isupper():
            # Positional shorthand: code is actually a resource_id (e.g. a UUID string)
            details = {"resource_type": message, "resource_id": code}
            code = "NOT_FOUND"
        super().__init__(message, code=code, details=details, http_status=http_status)


class PermissionError(ServiceError):
    """Exception raised for permission errors."""

    def __init__(
        self,
        message: str = "",
        code: str = "PERMISSION_DENIED",
        details: dict[str, Any] | None = None,
        http_status: int = 403,
    ):
        super().__init__(message, code=code, details=details, http_status=http_status)


class ConflictError(ServiceError):
    """Exception raised for conflict errors (e.g., duplicate resources)."""

    def __init__(
        self,
        message: str = "",
        code: str = "CONFLICT_ERROR",
        details: dict[str, Any] | None = None,
        http_status: int = 409,
    ):
        super().__init__(message, code=code, details=details, http_status=http_status)


class ConnectionError(ServiceError):
    """Exception raised for connection errors (e.g., network failures, service unavailable)."""

    def __init__(
        self,
        message: str,
        code: str = "CONNECTION_ERROR",
        details: dict[str, Any] | None = None,
        http_status: int = 503,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
        self.http_status = http_status


try:
    from prometheus_client import Counter, Histogram

    service_operations_total = Counter(
        "service_operations_total",
        "Total service operations",
        ["service", "operation", "tenant_id"],
    )
    service_operation_duration_seconds = Histogram(
        "service_operation_duration_seconds",
        "Service operation duration",
        ["service", "operation", "tenant_id"],
    )
    service_operation_errors_total = Counter(
        "service_operation_errors_total",
        "Total service operation errors",
        ["service", "operation", "error_code", "tenant_id"],
    )
except ImportError:
    service_operations_total = None
    service_operation_duration_seconds = None
    service_operation_errors_total = None


class BaseService:
    """
    Base service class for business logic layer.

    Provides common functionality for services:
    - Resource retrieval with error handling
    - Metrics collection
    - Tenant scoping
    """

    service_name: str = "base_service"

    @property
    def _logger(self):
        """Lazy logger — works even if subclass skips super().__init__."""
        attr = "_logger_inst"
        if not hasattr(self, attr):
            object.__setattr__(
                self,
                attr,
                logging.getLogger(f"{__name__}.{self.service_name}"),
            )
        return getattr(self, attr)

    @_logger.setter
    def _logger(self, value):
        object.__setattr__(self, "_logger_inst", value)

    def __init__(
        self,
        tenant_id: str | None = None,
        user_id: str | None = None,
        request_id: str | None = None,
        **kwargs,
    ):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.request_id = request_id or str(uuid.uuid4())
        # Cooperative multiple inheritance: forward to next class in MRO
        # so that mixins (e.g. IngestionEventPublisher) get initialized.
        super().__init__(**kwargs)

    def _get_context(self) -> dict[str, Any]:
        return {
            "service": self.service_name,
            "tenant_id": getattr(self, "tenant_id", None),
            "user_id": getattr(self, "user_id", None),
            "request_id": getattr(self, "request_id", None),
        }

    def _log_operation_start(self, operation: str, **kwargs):
        self._logger.info(
            "Operation %s started",
            operation,
            extra={**self._get_context(), **kwargs},
        )

    def _log_operation_success(self, operation: str, duration_ms: float = 0, **kwargs):
        self._logger.info(
            "Operation %s succeeded in %.2fms",
            operation,
            duration_ms,
            extra={**self._get_context(), **kwargs},
        )

    def _log_operation_error(
        self, operation: str, error: Exception, duration_ms: float = 0, **kwargs
    ):
        # Business-rule rejections (plan limits, validation, not-found,
        # conflict/duplicate, permission denials) and client-input errors
        # (bad pagination, division-by-zero from page_size=0) are normal
        # operation, not system faults.  Log at WARNING so on-call pages
        # don't fire on expected throttling or routine business rejections.
        if isinstance(
            error,
            (
                ValidationError,
                ConflictError,
                NotFoundError,
                PermissionError,
                ValueError,
                ZeroDivisionError,
                DjangoInvalidPage,
                DjangoIntegrityError,
            ),
        ):
            log_level = logging.WARNING
        else:
            log_level = logging.ERROR
        self._logger.log(
            log_level,
            "Operation %s failed in %.2fms: %s",
            operation,
            duration_ms,
            str(error),
            extra={**self._get_context(), **kwargs},
        )

    def _record_metrics(
        self, operation: str, duration: float, success: bool = True, error_code: str | None = None
    ):
        tid = self.tenant_id or ""
        if service_operations_total:
            service_operations_total.labels(
                service=self.service_name,
                operation=operation,
                tenant_id=tid,
            ).inc()
        if service_operation_duration_seconds:
            service_operation_duration_seconds.labels(
                service=self.service_name,
                operation=operation,
                tenant_id=tid,
            ).observe(duration)
        if not success and error_code and service_operation_errors_total:
            service_operation_errors_total.labels(
                service=self.service_name,
                operation=operation,
                error_code=error_code,
                tenant_id=tid,
            ).inc()

    @staticmethod
    def validate_resource_tenant(
        model_class: type[models.Model],
        resource_id: str,
        expected_tenant_id: str,
        *,
        tenant_field: str = "tenant_id",
    ) -> models.Model:
        """Validate that a resource belongs to the expected tenant.

        Raises PermissionError if the resource belongs to a different
        tenant, NotFoundError if the resource does not exist.

        Args:
            model_class: Django model class to query.
            resource_id: Primary key of the resource.
            expected_tenant_id: Tenant ID that must own the resource.
            tenant_field: Name of the FK field to the tenant (default: 'tenant_id').

        Returns:
            The model instance if validation passes.
        """
        try:
            resource = model_class.objects.get(pk=resource_id)
        except model_class.DoesNotExist:
            raise NotFoundError(
                f"{model_class.__name__} with id '{resource_id}' not found",
                code="NOT_FOUND",
            )
        actual_tenant_id = str(getattr(resource, tenant_field, None))
        if actual_tenant_id != str(expected_tenant_id):
            raise PermissionError(
                f"Access denied: {model_class.__name__} '{resource_id}' "
                f"does not belong to tenant '{expected_tenant_id}'"
            )
        return resource

    def get_resource_or_raise(
        self,
        model_class: type[models.Model],
        resource_id: str,
        tenant_id: str | None = None,
        **filters,
    ) -> models.Model:
        """
        Get resource by ID or raise NotFoundError.

        Args:
            model_class: Django model class
            resource_id: Resource ID
            tenant_id: Tenant ID (uses service tenant_id if not provided)
            **filters: Additional filters

        Returns:
            Model instance

        Raises:
            NotFoundError: If resource not found
        """
        effective_tenant_id = tenant_id or self.tenant_id
        resource_type = filters.pop("resource_type", model_class.__name__)

        try:
            filters["id"] = resource_id
            if effective_tenant_id:
                # Try tenant_id field first
                if hasattr(model_class, "tenant_id") or hasattr(model_class, "tenant"):
                    filters["tenant_id"] = effective_tenant_id

            return model_class.objects.get(**filters)
        except ObjectDoesNotExist:
            raise NotFoundError(
                f"{resource_type} with id {resource_id} not found",
                details={"resource_type": resource_type, "resource_id": resource_id},
            )
        except DjangoValidationError as e:
            # Invalid UUID / bad field value — a client input error, not a
            # server fault.  Convert to our own ValidationError so callers
            # (and _log_operation_error) treat it as a routine rejection.
            raise ValidationError(
                str(e),
                code="VALIDATION_ERROR",
                details={"resource_type": resource_type, "resource_id": resource_id},
            )
        except Exception as e:
            logger.error(f"Error retrieving {resource_type}: {e}")
            raise

    def validate_tenant(self, tenant_id: str) -> None:
        """Validate that a tenant exists and is active.

        Raises:
            NotFoundError: If the tenant does not exist.
            PermissionError: If the tenant is not active.
        """
        from hub.apps.tenants.models import Tenant

        try:
            tenant = Tenant.objects.get(pk=tenant_id)
        except Tenant.DoesNotExist:
            raise NotFoundError(
                f"Tenant with id {tenant_id} not found",
                code="NOT_FOUND",
            )
        if not tenant.is_active():
            raise PermissionError(
                f"Tenant {tenant_id} is not active",
                code="PERMISSION_DENIED",
            )

    def get_tenant_or_raise(self, tenant_id: str):
        """Return the Tenant instance or raise NotFoundError."""
        from hub.apps.tenants.models import Tenant

        try:
            return Tenant.objects.get(pk=tenant_id)
        except Tenant.DoesNotExist:
            raise NotFoundError(
                f"Tenant with id {tenant_id} not found",
                code="NOT_FOUND",
            )

    @contextmanager
    def transaction_context(self):
        """Context manager that wraps the body in a DB transaction."""
        from django.db import transaction as db_transaction

        with db_transaction.atomic():
            yield

    def validate_required_fields(
        self,
        data: dict[str, Any],
        required_fields: list[str],
    ) -> None:
        """Validate that all required fields are present and non-None.

        Raises:
            ValidationError: If any required field is missing or None.
        """
        missing = [f for f in required_fields if f not in data or data[f] is None]
        if missing:
            raise ValidationError(
                f"Missing required fields: {', '.join(missing)}",
                code="VALIDATION_ERROR",
                details={"missing_fields": missing},
            )

    def execute_with_metrics(
        self, operation: str, tenant_id: str | None = None, func: Callable | None = None, **kwargs
    ) -> Any:
        """
        Execute function with metrics collection.

        Args:
            operation: Operation name for metrics
            tenant_id: Tenant ID
            func: Function to execute (or use as decorator)
            **kwargs: Additional arguments

        Returns:
            Function result
        """
        if func is None:
            # Used as decorator
            def decorator(f: Callable) -> Callable:
                return self.execute_with_metrics(operation, tenant_id, f, **kwargs)

            return decorator

        self._log_operation_start(operation, **kwargs)
        start = time.time()
        try:
            result = func()
            duration = time.time() - start
            self._log_operation_success(operation, duration * 1000, **kwargs)
            self._record_metrics(operation, duration, success=True)
            return result
        except ServiceError:
            duration = time.time() - start
            self._log_operation_error(operation, sys.exc_info()[1], duration * 1000, **kwargs)
            error_code = getattr(sys.exc_info()[1], "code", "SERVICE_ERROR")
            self._record_metrics(
                operation,
                duration,
                success=False,
                error_code=error_code,
            )
            raise
        except DjangoValidationError as e:
            duration = time.time() - start
            self._log_operation_error(operation, e, duration * 1000, **kwargs)
            self._record_metrics(
                operation,
                duration,
                success=False,
                error_code="VALIDATION_ERROR",
            )
            raise ValidationError(str(e)) from e
        except Exception as e:
            duration = time.time() - start
            self._log_operation_error(operation, e, duration * 1000, **kwargs)
            self._record_metrics(
                operation,
                duration,
                success=False,
                error_code="INTERNAL_ERROR",
            )
            raise ServiceError(
                str(e),
                code="INTERNAL_ERROR",
            ) from e

    def execute_with_transaction(
        self, operation: str, tenant_id: str | None = None, func: Callable | None = None, **kwargs
    ) -> Any:
        """
        Execute function within a database transaction with metrics collection.

        Args:
            operation: Operation name for metrics
            tenant_id: Tenant ID
            func: Function to execute
            **kwargs: Additional arguments

        Returns:
            Function result
        """
        from django.db import transaction

        if func is None:
            raise ValueError("func parameter is required for execute_with_transaction")

        # Execute function within transaction with metrics
        with transaction.atomic():
            return self.execute_with_metrics(
                operation=operation, tenant_id=tenant_id, func=func, **kwargs
            )


def instrument_service_call(service_name: str, endpoint: str, method: str = "GET"):
    """
    Decorator to instrument service client calls with spans.

    Usage:
        @instrument_service_call("dq-service", "/runs", "POST")
        def call_dq_service(self, data):
            ...

    Args:
        service_name: Name of the service being called
        endpoint: Endpoint path
        method: HTTP method

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        import time
        from functools import wraps

        @wraps(func)
        def wrapper(*args, **kwargs):
            if not is_opentelemetry_enabled():
                return func(*args, **kwargs)

            span_name = f"{service_name}.{endpoint}"
            start_time = time.time()

            try:
                tracer = trace.get_tracer(__name__)
                span = tracer.start_as_current_span(span_name, kind=trace.SpanKind.CLIENT)

                # Add service attributes
                span.set_attribute("service.name", service_name)
                span.set_attribute("service.endpoint", endpoint)
                span.set_attribute("http.method", method)

                try:
                    # Execute service call
                    result = func(*args, **kwargs)

                    # Calculate duration
                    duration_ms = (time.time() - start_time) * 1000

                    # Add duration attribute
                    span.set_attribute("service.call.duration_ms", duration_ms)

                    # Set success status
                    span.set_status(Status(StatusCode.OK))

                    return result
                except Exception as e:
                    # Record exception and add error attributes
                    span.record_exception(e)
                    span.set_attribute("error", True)
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", str(e))
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise
                finally:
                    span.end()
            except Exception as e:
                # If span creation fails, still execute the function
                logger.debug(f"Failed to create span for service call: {e}")
                return func(*args, **kwargs)

        return wrapper

    return decorator


class BaseServiceClient:
    """
    Base class for service clients with automatic instrumentation.

    Subclasses should implement service-specific methods and use
    @instrument_service_call decorator for HTTP calls.
    """

    def __init__(self, service_name: str, base_url: str):
        """
        Initialize service client.

        Args:
            service_name: Name of the service
            base_url: Base URL of the service
        """
        self.service_name = service_name
        self.base_url = base_url
