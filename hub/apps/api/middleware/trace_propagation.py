"""
Trace Propagation Utilities

Utilities for propagating trace IDs in outgoing HTTP requests.
Used by service clients to add trace headers to requests.
"""

from contextvars import ContextVar

from django.http import HttpRequest

# Context variable to store current request for trace propagation
_current_request: ContextVar[HttpRequest | None] = ContextVar("_current_request", default=None)


def set_current_request(request: HttpRequest) -> None:
    """
    Set current request in context for trace propagation.

    Called by TraceIDMiddleware to make request available to service clients.

    Args:
        request: Django HTTP request object
    """
    _current_request.set(request)


def get_current_request() -> HttpRequest | None:
    """
    Get current request from context.

    Returns:
        Current request object or None
    """
    return _current_request.get(None)


def get_trace_headers(request: HttpRequest | None = None) -> dict[str, str]:
    """
    Get trace headers for outgoing HTTP requests.

    Extracts trace ID from request object (set by TraceIDMiddleware) and formats
    headers for propagation to downstream services.

    Args:
        request: Django HTTP request object (optional, will use context if not provided)

    Returns:
        Dictionary of trace headers:
        - traceparent: W3C Trace Context header
        - X-Trace-Id: Custom trace ID header (for compatibility)
    """
    headers = {}

    # Use provided request or get from context
    if not request:
        request = get_current_request()

    if request and hasattr(request, "traceparent"):
        # Add W3C Trace Context header
        headers["traceparent"] = request.traceparent

    if request and hasattr(request, "trace_id"):
        # Add custom X-Trace-Id header for compatibility
        headers["X-Trace-Id"] = request.trace_id

    return headers
