"""
OpenTelemetry Span Middleware for Django Views

Middleware that automatically creates spans for each Django request/response.
Adds request attributes (method, path, user_id, tenant_id) and response
attributes (status_code, duration).
"""
import time
import logging
from typing import Optional
from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings

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
    return getattr(settings, 'OPENTELEMETRY_ENABLED', False)


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
            route = getattr(request.resolver_match, 'route', None) if hasattr(request, 'resolver_match') else None
            span_name = route or request.path

            # Start span
            span = tracer.start_as_current_span(
                f"HTTP {request.method} {span_name}",
                kind=trace.SpanKind.SERVER
            )

            # Add request attributes
            attributes = {
                "http.method": request.method,
                "http.url": request.build_absolute_uri(),
                "http.route": request.path,
                "http.scheme": request.scheme,
                "http.host": request.get_host(),
            }

            # Add user agent if available
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            if user_agent:
                attributes["http.user_agent"] = user_agent

            # Add user and tenant info if available
            if hasattr(request, 'user') and request.user.is_authenticated:
                attributes["user.id"] = str(request.user.id)
                if hasattr(request.user, 'tenant_id'):
                    attributes["tenant.id"] = str(request.user.tenant_id)
                if hasattr(request.user, 'email'):
                    attributes["user.email"] = request.user.email

            # Add trace ID if available
            if hasattr(request, 'trace_id'):
                attributes["trace.id"] = request.trace_id

            # Set attributes on span
            for key, value in attributes.items():
                try:
                    if value is not None:
                        span.set_attribute(key, str(value))
                except Exception:
                    pass

            # Store start time and span in request
            request._span_start_time = time.time()
            request._span = span

        except Exception as e:
            logger.debug(f"Failed to create span for request: {e}")
            request._span = None
            request._span_start_time = None

        return None

    def process_response(
        self,
        request: HttpRequest,
        response: HttpResponse
    ) -> HttpResponse:
        """Add response attributes to span."""
        if not is_opentelemetry_enabled():
            return response

        span = getattr(request, '_span', None)
        if not span:
            return response

        try:
            # Calculate duration
            start_time = getattr(request, '_span_start_time', None)
            if start_time:
                duration_ms = (time.time() - start_time) * 1000
                span.set_attribute("http.response.duration_ms", duration_ms)

            # Add response attributes
            span.set_attribute("http.status_code", response.status_code)

            # Set span status based on HTTP status code
            is_error = False
            if response.status_code >= 500:
                span.set_status(Status(StatusCode.ERROR, f"HTTP {response.status_code}"))
                is_error = True
            elif response.status_code >= 400:
                span.set_status(Status(StatusCode.ERROR, f"HTTP {response.status_code}"))
                is_error = True
            else:
                span.set_status(Status(StatusCode.OK))

            # Ensure error spans are sampled (100% sampling for errors)
            # Note: We can't change sampling decision after span creation,
            # but we can mark error spans and ensure they're exported
            if is_error:
                span_context = span.get_span_context()
                # Check if span was sampled
                is_sampled = bool(span_context.trace_flags & trace.TraceFlags.SAMPLED)

                # Mark error span with attributes for filtering/analysis
                span.set_attribute("error.sampled", is_sampled)
                span.set_attribute("sampling.priority", "high")

                if not is_sampled:
                    # Create a new sampled span for the error to ensure it's traced
                    # Use the same trace context but with sampled flag
                    tracer = trace.get_tracer(__name__)

                    # Create a new span in the same trace
                    with tracer.start_as_current_span(
                        f"HTTP {request.method} {request.path} [ERROR]",
                        context=trace.set_span_in_context(span),
                        kind=trace.SpanKind.SERVER
                    ) as error_span:
                        # Copy key attributes
                        error_span.set_attribute("http.method", request.method)
                        error_span.set_attribute("http.url", request.build_absolute_uri())
                        error_span.set_attribute("http.route", request.path)
                        error_span.set_attribute("http.status_code", response.status_code)
                        error_span.set_attribute("sampling.forced", True)
                        error_span.set_attribute("sampling.reason", "http_error")
                        error_span.set_status(Status(StatusCode.ERROR, f"HTTP {response.status_code}"))

                        # Add user/tenant info if available
                        if hasattr(request, 'user') and request.user.is_authenticated:
                            error_span.set_attribute("user.id", str(request.user.id))
                            if hasattr(request.user, 'tenant_id'):
                                error_span.set_attribute("tenant.id", str(request.user.tenant_id))

                        logger.debug(
                            "trace_sampling_error_span_created",
                            trace_id=format(span_context.trace_id, '032x'),
                            status_code=response.status_code,
                            path=request.path
                        )

            # End span
            span.end()

        except Exception as e:
            logger.debug(f"Failed to update span with response: {e}")

        return response

    def process_exception(
        self,
        request: HttpRequest,
        exception: Exception
    ) -> Optional[HttpResponse]:
        """Record exception in span."""
        if not is_opentelemetry_enabled():
            return None

        span = getattr(request, '_span', None)
        if not span:
            return None

        try:
            # Record exception
            span.record_exception(exception)
            span.set_status(Status(StatusCode.ERROR, str(exception)))

            # Add error attributes
            span.set_attribute("error", True)
            span.set_attribute("error.type", type(exception).__name__)
            span.set_attribute("error.message", str(exception))

            # End span
            span.end()

        except Exception:
            pass

        return None

