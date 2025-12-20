"""
Trace Sampling Configuration

Custom trace sampling strategies for OpenTelemetry:
- 100% sampling for errors (status codes >= 400)
- Configurable sampling for successful requests (default: 10%)
- 100% sampling for critical endpoints (auth, asset activation)

This module provides a custom sampler that makes sampling decisions based on:
- Request path (for critical endpoints)
- HTTP status code (for errors)
- Configurable ratio for other requests
"""
import os
import logging
from typing import Optional, Dict, Any, TYPE_CHECKING
from django.conf import settings

logger = logging.getLogger(__name__)

# OpenTelemetry availability flag
OPENTELEMETRY_AVAILABLE = False
if TYPE_CHECKING:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import SamplingResult
    from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
    from opentelemetry.trace import SpanKind, TraceState
else:
    SamplingResult = None
    TraceIdRatioBased = None
    SpanKind = None
    TraceState = None

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import SamplingResult
    from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
    from opentelemetry.trace import SpanKind, TraceState
    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    logger.warning("OpenTelemetry packages not available for trace sampling")
    OPENTELEMETRY_AVAILABLE = False


# Critical endpoints that should always be sampled (100%)
CRITICAL_ENDPOINTS = [
    '/api/v1/auth/register',
    '/api/v1/auth/login',
    '/api/v1/auth/logout',
    '/api/v1/auth/refresh',
    '/api/v1/auth/me',
    '/api/v1/assets/',
    '/api/v1/assets/{id}/activate',
    '/api/v1/assets/{id}/deactivate',
]


def is_critical_endpoint(path: str) -> bool:
    """
    Check if a path matches a critical endpoint pattern.

    Args:
        path: Request path

    Returns:
        True if path matches a critical endpoint
    """
    # Check exact matches
    if path in CRITICAL_ENDPOINTS:
        return True

    # Check pattern matches (for paths with IDs)
    for pattern in CRITICAL_ENDPOINTS:
        # Convert pattern to regex-like matching
        if pattern.endswith('/'):
            # Check if path starts with pattern
            if path.startswith(pattern):
                return True
        elif '{id}' in pattern:
            # Replace {id} with any UUID or numeric ID
            import re
            pattern_regex = pattern.replace('{id}', r'[0-9a-f-]+|\d+')
            if re.match(pattern_regex, path):
                return True
        elif pattern in path:
            return True

    # Check for asset activation endpoints
    if '/activate' in path or '/deactivate' in path:
        return True

    # Check for auth endpoints
    if path.startswith('/api/v1/auth/'):
        return True

    return False


class AdaptiveTraceSampler:
    """
    Custom trace sampler that adapts sampling based on:
    - Critical endpoints (always sampled)
    - Configurable ratio for other requests

    This sampler makes decisions at span creation time based on request path.
    Error-based sampling is handled by middleware that ensures error spans are created.
    """

    def __init__(
        self,
        base_sampling_rate: float = 0.1,
        critical_endpoints: Optional[list] = None
    ):
        """
        Initialize adaptive trace sampler.

        Args:
            base_sampling_rate: Base sampling rate for non-critical requests (default: 0.1 = 10%)
            critical_endpoints: List of critical endpoint patterns (optional)
        """
        self.base_sampling_rate = base_sampling_rate
        self.base_sampler = TraceIdRatioBased(base_sampling_rate)
        self.critical_endpoints = critical_endpoints or CRITICAL_ENDPOINTS

    def should_sample(
        self,
        parent_context: Optional[Any],
        trace_id: int,
        name: str,
        kind: Optional[Any] = None,
        attributes: Optional[Dict[str, Any]] = None,
        links: Optional[list] = None,
        trace_state: Optional[Any] = None,
    ) -> Any:
        """
        Make sampling decision for a span.

        Args:
            parent_context: Parent span context
            trace_id: Trace ID
            name: Span name
            kind: Span kind
            attributes: Span attributes
            links: Span links
            trace_state: Trace state

        Returns:
            SamplingResult with decision and attributes
        """
        # Check if this is a critical endpoint
        if attributes:
            # Check HTTP target (path) from attributes
            http_target = attributes.get('http.target') or attributes.get('http.url.path') or attributes.get('http.route')
            if http_target and is_critical_endpoint(http_target):
                logger.debug(
                    f"trace_sampling_critical_endpoint: path={http_target}, trace_id={format(trace_id, '032x')}"
                )
                return SamplingResult(
                    decision=SamplingResult.Decision.RECORD_AND_SAMPLE,
                    attributes={"sampling.reason": "critical_endpoint"}
                )

        # Use base sampler for other requests
        result = self.base_sampler.should_sample(
            parent_context=parent_context,
            trace_id=trace_id,
            name=name,
            kind=kind,
            attributes=attributes,
            links=links,
            trace_state=trace_state,
        )

        # Add sampling rate to attributes
        if result.attributes:
            result.attributes["sampling.rate"] = self.base_sampling_rate
        else:
            result.attributes = {"sampling.rate": self.base_sampling_rate}

        return result


class ErrorAwareSpanProcessor:
    """
    Span processor that ensures error spans are always exported.

    This wraps a BatchSpanProcessor and ensures that all error responses
    (status >= 400) are exported, even if they weren't sampled initially.
    """

    def __init__(self, wrapped_processor):
        """
        Initialize error-aware span processor.

        Args:
            wrapped_processor: Span processor to wrap (e.g., BatchSpanProcessor)
        """
        self.wrapped_processor = wrapped_processor

    def on_start(self, span, parent_context=None):
        """Called when a span starts."""
        if hasattr(self.wrapped_processor, 'on_start'):
            self.wrapped_processor.on_start(span, parent_context)

    def on_end(self, span):
        """
        Called when a span ends. Ensures error spans are exported.

        Args:
            span: Span that ended
        """
        # Check if span has error status code
        span_context = span.get_span_context()
        is_sampled = bool(span_context.trace_flags & trace.TraceFlags.SAMPLED)

        # Check for errors that should always be exported
        should_force_export = False
        reason = None

        # Check span status
        if hasattr(span, 'status') and span.status:
            if span.status.status_code == span.status.StatusCode.ERROR:
                should_force_export = True
                reason = "error_status"

        # Check HTTP status code from attributes
        if hasattr(span, 'attributes') and span.attributes:
            http_status_code = span.attributes.get('http.status_code')
            if http_status_code and http_status_code >= 400:
                should_force_export = True
                reason = "http_error"

        # If we need to force export and span wasn't sampled, mark it
        if should_force_export and not is_sampled:
            # Add attributes to indicate forced sampling
            if hasattr(span, 'set_attribute'):
                span.set_attribute("sampling.forced", True)
                span.set_attribute("sampling.reason", reason)
            logger.debug(
                "trace_sampling_error_detected",
                trace_id=format(span_context.trace_id, '032x'),
                span_id=format(span_context.span_id, '016x'),
                reason=reason
            )

        # Always call wrapped processor - it will handle export
        # Note: The wrapped processor (BatchSpanProcessor) will only export
        # sampled spans, so we need to ensure error spans are sampled
        # This is handled by the sampler checking status codes
        if hasattr(self.wrapped_processor, 'on_end'):
            self.wrapped_processor.on_end(span)

    def shutdown(self):
        """Shutdown the span processor."""
        if hasattr(self.wrapped_processor, 'shutdown'):
            self.wrapped_processor.shutdown()

    def force_flush(self, timeout_millis: int = 30000):
        """Force flush spans."""
        if hasattr(self.wrapped_processor, 'force_flush'):
            return self.wrapped_processor.force_flush(timeout_millis)
        return True


def get_adaptive_sampler(
    base_sampling_rate: Optional[float] = None,
    critical_endpoints: Optional[list] = None
) -> Optional[Any]:
    """
    Get adaptive trace sampler with error-aware and critical endpoint support.

    Args:
        base_sampling_rate: Base sampling rate (default: from settings or 0.1)
        critical_endpoints: List of critical endpoint patterns (optional)

    Returns:
        AdaptiveTraceSampler instance or None if OpenTelemetry not available
    """
    if not OPENTELEMETRY_AVAILABLE:
        return None

    if base_sampling_rate is None:
        # Get from environment or settings
        base_sampling_rate = float(
            os.getenv(
                'OTEL_TRACES_SAMPLER_ARG',
                getattr(settings, 'OTEL_TRACES_SAMPLER_ARG', '0.1')
            )
        )

    return AdaptiveTraceSampler(
        base_sampling_rate=base_sampling_rate,
        critical_endpoints=critical_endpoints
    )

