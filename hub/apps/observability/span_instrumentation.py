"""
OpenTelemetry Span Instrumentation

Utilities for creating and managing OpenTelemetry spans for:
- Django views (request/response instrumentation)
- Service client calls (HTTP client instrumentation)
- Database queries (slow query instrumentation)

This module provides decorators and context managers for easy span creation.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from contextlib import contextmanager, suppress
from functools import wraps
from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse

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
    return getattr(settings, "OPENTELEMETRY_ENABLED", False)


def get_tracer(name: str | None = None):
    """
    Get OpenTelemetry tracer instance.

    Args:
        name: Tracer name (default: __name__)

    Returns:
        Tracer instance or None if not enabled
    """
    if not is_opentelemetry_enabled():
        return None

    try:
        return trace.get_tracer(name or __name__)
    except Exception:
        return None


def get_current_span():
    """
    Get current active span.

    Returns:
        Current span or None if not available
    """
    if not is_opentelemetry_enabled():
        return None

    try:
        span = trace.get_current_span()
        if span and span.get_span_context().is_valid:
            return span
        return None
    except Exception:
        return None


def add_span_attributes(attributes: dict[str, Any]):
    """
    Add attributes to the current span.

    Args:
        attributes: Dictionary of attribute key-value pairs
    """
    span = get_current_span()
    if span:
        for key, value in attributes.items():
            try:
                # Convert value to appropriate type
                if value is None:
                    continue
                elif (
                    isinstance(value, bool)
                    or isinstance(value, (int, float))
                    or isinstance(value, str)
                ):
                    span.set_attribute(key, value)
                else:
                    span.set_attribute(key, str(value))
            except Exception as e:
                logger.debug(f"Failed to add span attribute {key}: {e}")


def set_span_status(status_code: StatusCode, description: str | None = None):
    """
    Set status on the current span.

    Args:
        status_code: Status code (OK, ERROR, UNSET)
        description: Optional status description
    """
    span = get_current_span()
    if span:
        with suppress(Exception):
            span.set_status(Status(status_code, description))


def record_span_exception(exception: Exception):
    """
    Record an exception on the current span.

    Args:
        exception: Exception instance
    """
    span = get_current_span()
    if span:
        try:
            span.record_exception(exception)
            span.set_status(Status(StatusCode.ERROR, str(exception)))
        except Exception:
            pass


@contextmanager
def create_span(name: str, attributes: dict[str, Any] | None = None, kind: int | None = None):
    """
    Context manager for creating a span.

    Args:
        name: Span name
        attributes: Initial span attributes
        kind: Span kind (SERVER, CLIENT, etc.)

    Yields:
        Span instance
    """
    tracer = get_tracer()
    if not tracer:
        yield None
        return

    span = None
    try:
        if kind:
            span = tracer.start_as_current_span(name, kind=kind)
        else:
            span = tracer.start_as_current_span(name)

        if attributes:
            add_span_attributes(attributes)

        yield span
    except Exception as e:
        logger.debug(f"Failed to create span {name}: {e}")
        yield None
    finally:
        if span is not None:
            with suppress(Exception):
                span.end()


def instrument_view(view_func: Callable | None = None, span_name: str | None = None):
    """
    Decorator to instrument Django views with spans.

    Usage:
        @instrument_view
        def my_view(request):
            ...

        @instrument_view(span_name="custom_span_name")
        def my_view(request):
            ...

    Args:
        view_func: View function to instrument
        span_name: Custom span name (default: function name)

    Returns:
        Decorated view function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            if not is_opentelemetry_enabled():
                return func(request, *args, **kwargs)

            span_name_final = span_name or f"{func.__module__}.{func.__name__}"
            start_time = time.time()

            # Get user and tenant info
            user_id = None
            tenant_id = None
            if hasattr(request, "user") and request.user.is_authenticated:
                user_id = str(request.user.id)
                if hasattr(request.user, "tenant_id"):
                    tenant_id = str(request.user.tenant_id)

            # Create span with request attributes
            with create_span(
                span_name_final,
                attributes={
                    "http.method": request.method,
                    "http.url": request.build_absolute_uri(),
                    "http.route": request.path,
                    "http.user_agent": request.META.get("HTTP_USER_AGENT", ""),
                },
                kind=trace.SpanKind.SERVER,
            ):
                # Add user/tenant attributes if available
                if user_id:
                    add_span_attributes({"user.id": user_id})
                if tenant_id:
                    add_span_attributes({"tenant.id": tenant_id})

                try:
                    # Execute view
                    response = func(request, *args, **kwargs)

                    # Calculate duration
                    duration = time.time() - start_time

                    # Add response attributes
                    if isinstance(response, HttpResponse):
                        add_span_attributes(
                            {
                                "http.status_code": response.status_code,
                                "http.response.duration_ms": duration * 1000,
                            }
                        )

                        # Set span status based on HTTP status
                        if response.status_code >= 500 or response.status_code >= 400:
                            set_span_status(StatusCode.ERROR, f"HTTP {response.status_code}")
                        else:
                            set_span_status(StatusCode.OK)

                    return response
                except Exception as e:
                    # Record exception
                    record_span_exception(e)
                    raise

        return wrapper

    if view_func is None:
        return decorator
    else:
        return decorator(view_func)


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
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not is_opentelemetry_enabled():
                return func(*args, **kwargs)

            span_name = f"{service_name}.{endpoint}"
            start_time = time.time()

            with create_span(
                span_name,
                attributes={
                    "service.name": service_name,
                    "service.endpoint": endpoint,
                    "http.method": method,
                },
                kind=trace.SpanKind.CLIENT,
            ):
                try:
                    # Execute service call
                    result = func(*args, **kwargs)

                    # Calculate duration
                    duration = time.time() - start_time

                    # Add duration attribute
                    add_span_attributes(
                        {
                            "service.call.duration_ms": duration * 1000,
                        }
                    )

                    # Set success status
                    set_span_status(StatusCode.OK)

                    return result
                except Exception as e:
                    # Record exception and add error attributes
                    record_span_exception(e)
                    add_span_attributes(
                        {
                            "error": True,
                            "error.type": type(e).__name__,
                            "error.message": str(e),
                        }
                    )
                    raise

        return wrapper

    return decorator


@contextmanager
def instrument_database_query(
    operation: str, table: str | None = None, slow_query_threshold_ms: float = 100.0
):
    """
    Context manager for instrumenting database queries.

    Only creates spans for slow queries (>threshold).

    Usage:
        with instrument_database_query("SELECT", "assets"):
            Asset.objects.filter(...)

    Args:
        operation: Database operation (SELECT, INSERT, UPDATE, DELETE)
        table: Table name (optional)
        slow_query_threshold_ms: Threshold in milliseconds for slow queries

    Yields:
        Span instance (or None if query is fast)
    """
    if not is_opentelemetry_enabled():
        yield None
        return

    start_time = time.time()
    span = None

    try:
        yield span
    finally:
        duration_ms = (time.time() - start_time) * 1000

        # Only create span for slow queries
        if duration_ms >= slow_query_threshold_ms:
            tracer = get_tracer()
            if tracer:
                try:
                    span_name = f"db.{operation.lower()}"
                    if table:
                        span_name = f"db.{operation.lower()}.{table}"

                    span = tracer.start_as_current_span(span_name)

                    attributes = {
                        "db.operation": operation,
                        "db.query.duration_ms": duration_ms,
                    }

                    if table:
                        attributes["db.table"] = table

                    add_span_attributes(attributes)
                    set_span_status(StatusCode.OK)
                    span.end()
                except Exception:
                    pass
