"""
Trace ID Propagation Middleware

Middleware for extracting and propagating trace IDs across service boundaries.
Supports W3C Trace Context standard (traceparent header) and custom X-Trace-Id header.

Features:
- Extract trace ID from traceparent header (W3C Trace Context)
- Extract trace ID from X-Trace-Id header (fallback)
- Generate new trace ID if not present
- Add trace ID to response headers (X-Trace-Id) for frontend correlation
- Store trace ID in request for use by service clients
"""

import uuid

import structlog
from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin

logger = structlog.get_logger(__name__)

# W3C Trace Context version (currently 00)
TRACEPARENT_VERSION = "00"


def parse_traceparent_header(traceparent: str) -> dict | None:
    """
    Parse W3C Trace Context traceparent header.

    Format: version-trace_id-parent_id-trace_flags
    Example: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01

    Args:
        traceparent: traceparent header value

    Returns:
        Dictionary with trace_id, parent_id, flags, or None if invalid
    """
    if not traceparent:
        return None

    try:
        parts = traceparent.split("-")
        if len(parts) != 4:
            logger.debug("traceparent_invalid_format", traceparent=traceparent[:50])
            return None

        version, trace_id, parent_id, flags = parts

        # Validate version (must be 00 for now)
        if version != TRACEPARENT_VERSION:
            logger.debug("traceparent_unsupported_version", version=version)
            return None

        # Validate trace_id (32 hex characters)
        if len(trace_id) != 32 or not all(c in "0123456789abcdefABCDEF" for c in trace_id):
            logger.debug("traceparent_invalid_trace_id", trace_id=trace_id)
            return None

        # Validate parent_id (16 hex characters)
        if len(parent_id) != 16 or not all(c in "0123456789abcdefABCDEF" for c in parent_id):
            logger.debug("traceparent_invalid_parent_id", parent_id=parent_id)
            return None

        # Validate flags (2 hex characters)
        if len(flags) != 2 or not all(c in "0123456789abcdefABCDEF" for c in flags):
            logger.debug("traceparent_invalid_flags", flags=flags)
            return None

        return {
            "version": version,
            "trace_id": trace_id.lower(),  # Normalize to lowercase
            "parent_id": parent_id.lower(),
            "flags": flags.lower(),
        }
    except Exception as e:
        logger.warning("traceparent_parse_error", error=str(e), traceparent=traceparent[:50])
        return None


def generate_trace_id() -> str:
    """
    Generate a new trace ID (32 hex characters).

    Returns:
        Trace ID as hex string
    """
    # Generate UUID4 and convert to hex without dashes
    trace_uuid = uuid.uuid4()
    return trace_uuid.hex


def generate_span_id() -> str:
    """
    Generate a new span ID (16 hex characters).

    Returns:
        Span ID as hex string
    """
    # Generate UUID4 and take first 16 hex characters
    span_uuid = uuid.uuid4()
    return span_uuid.hex[:16]


def format_traceparent(trace_id: str, parent_id: str, flags: str = "01") -> str:
    """
    Format traceparent header value (W3C Trace Context).

    Args:
        trace_id: 32-character hex trace ID
        parent_id: 16-character hex parent/span ID
        flags: 2-character hex flags (default: 01 = sampled)

    Returns:
        Formatted traceparent header value
    """
    return f"{TRACEPARENT_VERSION}-{trace_id}-{parent_id}-{flags}"


def extract_trace_id_from_request(request: HttpRequest) -> tuple[str, str | None, str | None]:
    """
    Extract trace ID from incoming request headers.

    Checks in order:
    1. traceparent header (W3C Trace Context)
    2. X-Trace-Id header (fallback)

    Args:
        request: HTTP request object

    Returns:
        Tuple of (trace_id, parent_id, flags)
        - trace_id: Trace ID (always present, generated if not found)
        - parent_id: Parent/span ID from traceparent (None if not present)
        - flags: Trace flags from traceparent (None if not present)
    """
    # Try traceparent header first (W3C Trace Context)
    traceparent = request.META.get("HTTP_TRACEPARENT", "")
    if traceparent:
        parsed = parse_traceparent_header(traceparent)
        if parsed:
            logger.debug(
                "trace_id_extracted_from_traceparent",
                trace_id=parsed["trace_id"],
                parent_id=parsed["parent_id"],
            )
            return parsed["trace_id"], parsed["parent_id"], parsed["flags"]

    # Try X-Trace-Id header (fallback)
    trace_id_header = request.META.get("HTTP_X_TRACE_ID", "")
    if trace_id_header:
        # Validate format (should be 32 hex characters)
        trace_id_header = trace_id_header.strip()
        if len(trace_id_header) == 32 and all(
            c in "0123456789abcdefABCDEF" for c in trace_id_header
        ):
            logger.debug("trace_id_extracted_from_x_trace_id", trace_id=trace_id_header.lower())
            return trace_id_header.lower(), None, None

    # Generate new trace ID if not present
    trace_id = generate_trace_id()
    logger.debug("trace_id_generated", trace_id=trace_id)
    return trace_id, None, None


class TraceIDMiddleware(MiddlewareMixin):
    """
    Middleware for trace ID extraction and propagation.

    Extracts trace ID from incoming requests and adds it to response headers
    for frontend correlation. Stores trace ID in request for use by service clients.
    """

    def process_request(self, request: HttpRequest) -> None:
        """
        Extract trace ID from request headers and store in request.

        Args:
            request: HTTP request object
        """
        # Extract trace ID from request
        trace_id, parent_id, flags = extract_trace_id_from_request(request)

        # Store trace ID in request for use by service clients
        request.trace_id = trace_id
        request.trace_parent_id = parent_id
        request.trace_flags = flags

        # Generate new span ID for this request
        request.span_id = generate_span_id()

        # Format traceparent for outgoing requests
        request.traceparent = format_traceparent(trace_id, request.span_id, flags or "01")

        # Add trace context to structlog
        structlog.contextvars.bind_contextvars(trace_id=trace_id, span_id=request.span_id)

        # Store request in context for trace propagation to service clients
        from hub.apps.api.middleware.trace_propagation import set_current_request

        set_current_request(request)

        logger.debug(
            "trace_id_extracted",
            trace_id=trace_id,
            span_id=request.span_id,
            parent_id=parent_id,
            path=request.path,
        )

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """
        Add trace ID to response headers.

        Args:
            request: HTTP request object
            response: HTTP response object

        Returns:
            HTTP response with trace ID header
        """
        # Only add headers to API responses
        if not request.path.startswith("/api/"):
            return response

        # Add X-Trace-Id header for frontend correlation
        if hasattr(request, "trace_id"):
            response["X-Trace-Id"] = request.trace_id

            logger.debug(
                "trace_id_added_to_response",
                trace_id=request.trace_id,
                path=request.path,
                status_code=response.status_code,
            )

        return response
