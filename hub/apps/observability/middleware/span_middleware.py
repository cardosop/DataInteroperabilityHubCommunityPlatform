"""
OpenTelemetry Span Middleware for Django Views

Middleware that automatically creates spans for each Django request/response.
Adds request attributes (method, path, user_id, tenant_id) and response
attributes (status_code, duration).
"""

import time

import structlog
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin

logger = structlog.get_logger(__name__)

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


class SpanMiddleware(MiddlewareMixin):
    """
    Middleware for creating OpenTelemetry spans for Django requests.

    Creates a span for each request with:
    - Request attributes: method, path, user_id, tenant_id
    - Response attributes: status_code, duration
    """

    def process_request(self, request: HttpRequest) -> None:
        """Create span for incoming request."""
        if not is_opentelemetry_enabled():
            return None

        try:
            tracer = trace.get_tracer(__name__)

            # Get route name or path
            route = (
                getattr(request.resolver_match, "route", None)
                if hasattr(request, "resolver_match")
                else None
            )
            span_name = route or request.path

            # Start span: start_as_current_span returns a context manager; __enter__ yields the span
            span_cm = tracer.start_as_current_span(
                f"HTTP {request.method} {span_name}", kind=trace.SpanKind.SERVER
            )
            span = span_cm.__enter__()

            # Add request attributes (guard: no-op tracer may return object without set_attribute)
            if hasattr(span, "set_attribute"):
                attributes = {
                    "http.method": request.method,
                    "http.url": request.build_absolute_uri(),
                    "http.route": request.path,
                    "http.scheme": request.scheme,
                    "http.host": request.get_host(),
                }

                # Add user agent if available
                user_agent = request.META.get("HTTP_USER_AGENT", "")
                if user_agent:
                    attributes["http.user_agent"] = user_agent

                # Add user and tenant info if available
                if hasattr(request, "user") and request.user.is_authenticated:
                    attributes["user.id"] = str(request.user.id)
                    if hasattr(request.user, "tenant_id"):
                        attributes["tenant.id"] = str(request.user.tenant_id)
                    if hasattr(request.user, "email"):
                        attributes["user.email"] = request.user.email

                # Add trace ID if available
                if hasattr(request, "trace_id"):
                    attributes["trace.id"] = request.trace_id

                for key, value in attributes.items():
                    try:
                        if value is not None:
                            span.set_attribute(key, str(value))
                    except Exception:
                        pass

            # Store start time, span, and context manager (for __exit__ in process_response)
            request._span_start_time = time.time()
            request._span = span
            request._span_cm = span_cm

        except Exception as e:
            logger.debug(f"Failed to create span for request: {e}")
            request._span = None
            request._span_start_time = None

        return None

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Add response attributes to span."""
        if not is_opentelemetry_enabled():
            return response

        span = getattr(request, "_span", None)
        span_cm = getattr(request, "_span_cm", None)
        if not span:
            return response

        try:
            # Add response attributes (guard: no-op span may lack set_attribute)
            if hasattr(span, "set_attribute"):
                # Calculate duration
                start_time = getattr(request, "_span_start_time", None)
                if start_time:
                    duration_ms = (time.time() - start_time) * 1000
                    span.set_attribute("http.response.duration_ms", duration_ms)

                span.set_attribute("http.status_code", response.status_code)

                # Set span status based on HTTP status code
                is_error = False
                if response.status_code >= 500 or response.status_code >= 400:
                    span.set_status(Status(StatusCode.ERROR, f"HTTP {response.status_code}"))
                    is_error = True
                else:
                    span.set_status(Status(StatusCode.OK))

                # Ensure error spans are sampled (100% sampling for errors)
                if is_error and hasattr(span, "get_span_context"):
                    span_context = span.get_span_context()
                    is_sampled = bool(span_context.trace_flags & trace.TraceFlags.SAMPLED)

                    span.set_attribute("error.sampled", is_sampled)
                    span.set_attribute("sampling.priority", "high")

                    if not is_sampled:
                        tracer = trace.get_tracer(__name__)
                        with tracer.start_as_current_span(
                            f"HTTP {request.method} {request.path} [ERROR]",
                            context=trace.set_span_in_context(span),
                            kind=trace.SpanKind.SERVER,
                        ) as error_span:
                            if hasattr(error_span, "set_attribute"):
                                error_span.set_attribute("http.method", request.method)
                                error_span.set_attribute("http.url", request.build_absolute_uri())
                                error_span.set_attribute("http.route", request.path)
                                error_span.set_attribute("http.status_code", response.status_code)
                                error_span.set_attribute("sampling.forced", True)
                                error_span.set_attribute("sampling.reason", "http_error")
                                error_span.set_status(
                                    Status(StatusCode.ERROR, f"HTTP {response.status_code}")
                                )
                                if hasattr(request, "user") and request.user.is_authenticated:
                                    error_span.set_attribute("user.id", str(request.user.id))
                                    if hasattr(request.user, "tenant_id"):
                                        error_span.set_attribute(
                                            "tenant.id", str(request.user.tenant_id)
                                        )

                            logger.debug(
                                "trace_sampling_error_span_created",
                                trace_id=format(span_context.trace_id, "032x"),
                                status_code=response.status_code,
                                path=request.path,
                            )

            # End span: use context manager __exit__ if available, else span.end()
            if span_cm is not None:
                try:
                    span_cm.__exit__(None, None, None)
                except Exception:
                    if hasattr(span, "end"):
                        span.end()
            elif hasattr(span, "end"):
                span.end()

        except Exception as e:
            logger.debug(f"Failed to update span with response: {e}")
            # Ensure span is closed even on error
            try:
                if span_cm is not None:
                    span_cm.__exit__(None, None, None)
                elif hasattr(span, "end"):
                    span.end()
            except Exception:
                pass

        return response

    def process_exception(self, request: HttpRequest, exception: Exception) -> HttpResponse | None:
        """Record exception in span."""
        if not is_opentelemetry_enabled():
            return None

        span = getattr(request, "_span", None)
        span_cm = getattr(request, "_span_cm", None)
        if not span:
            return None

        try:
            if hasattr(span, "record_exception"):
                span.record_exception(exception)
            if hasattr(span, "set_status"):
                span.set_status(Status(StatusCode.ERROR, str(exception)))
            if hasattr(span, "set_attribute"):
                span.set_attribute("error", True)
                span.set_attribute("error.type", type(exception).__name__)
                span.set_attribute("error.message", str(exception))

            # End span
            if span_cm is not None:
                try:
                    span_cm.__exit__(type(exception), exception, exception.__traceback__)
                except Exception:
                    if hasattr(span, "end"):
                        span.end()
            elif hasattr(span, "end"):
                span.end()

        except Exception:
            pass

        return None
