"""
Marketplace Integration Logging Utilities

Helper functions for structured logging with correlation IDs in marketplace integrations.
"""
import structlog
from typing import Optional, Dict, Any

logger = structlog.get_logger(__name__)


def get_correlation_context() -> Dict[str, Any]:
    """
    Get correlation IDs from current context for structured logging.

    Extracts trace_id, span_id, and request_id from:
    - OpenTelemetry trace context
    - Django request context (via trace_propagation)
    - structlog contextvars

    Returns:
        Dictionary with correlation IDs:
        - trace_id: OpenTelemetry trace ID (hex string)
        - span_id: OpenTelemetry span ID (hex string)
        - request_id: Request ID from middleware
    """
    context = {}

    # Try to get trace context from OpenTelemetry
    try:
        from opentelemetry import trace
        span = trace.get_current_span()
        if span and span.get_span_context().is_valid:
            span_context = span.get_span_context()
            context['trace_id'] = format(span_context.trace_id, '032x')
            context['span_id'] = format(span_context.span_id, '016x')
    except Exception:
        pass

    # Try to get request context from Django middleware
    try:
        from hub.apps.api.middleware.trace_propagation import get_current_request
        request = get_current_request()
        if request:
            if hasattr(request, 'trace_id') and request.trace_id:
                context['trace_id'] = request.trace_id
                context['request_id'] = request.trace_id
            if hasattr(request, 'span_id') and request.span_id:
                context['span_id'] = request.span_id
    except Exception:
        pass

    # Try to get from structlog contextvars
    try:
        import structlog.contextvars
        ctx = structlog.contextvars.get_contextvars()
        if 'trace_id' in ctx:
            context['trace_id'] = ctx['trace_id']
        if 'span_id' in ctx:
            context['span_id'] = ctx['span_id']
        if 'request_id' in ctx:
            context['request_id'] = ctx['request_id']
    except Exception:
        pass

    return context


def log_connector_operation(
    event: str,
    level: str = "info",
    operation_type: Optional[str] = None,
    marketplace_type: Optional[str] = None,
    tenant_id: Optional[str] = None,
    connection_id: Optional[str] = None,
    duration: Optional[float] = None,
    status: Optional[str] = None,
    error_type: Optional[str] = None,
    error_message: Optional[str] = None,
    **kwargs
):
    """
    Log connector operation with structured fields and correlation IDs.

    Args:
        event: Event name (e.g., "connector_operation_started", "connector_operation_completed")
        level: Log level ("info", "warning", "error", "debug")
        operation_type: Type of operation (e.g., "list_listings", "sync_pull")
        marketplace_type: Marketplace type
        tenant_id: Tenant ID
        connection_id: Connection ID
        duration: Operation duration in seconds
        status: Operation status ("success", "error")
        error_type: Error type if operation failed
        error_message: Error message if operation failed
        **kwargs: Additional structured fields
    """
    # Get correlation context
    correlation_context = get_correlation_context()

    # Build structured log fields
    log_fields = {
        "event": event,
        "component": "marketplace_connector",
    }

    # Add operation context
    if operation_type:
        log_fields["operation_type"] = operation_type
    if marketplace_type:
        log_fields["marketplace_type"] = marketplace_type
    if tenant_id:
        log_fields["tenant_id"] = tenant_id
    if connection_id:
        log_fields["connection_id"] = connection_id

    # Add operation metrics
    if duration is not None:
        log_fields["duration_seconds"] = duration
    if status:
        log_fields["status"] = status

    # Add error context
    if error_type:
        log_fields["error_type"] = error_type
    if error_message:
        log_fields["error_message"] = error_message

    # Add correlation IDs
    log_fields.update(correlation_context)

    # Add any additional fields
    log_fields.update(kwargs)

    # Get logger method
    log_method = getattr(logger, level, logger.info)

    # Extract event name (structlog expects it as first positional arg)
    event_name = log_fields.pop("event", "log_event")

    # Log with structured fields (event as first arg, rest as kwargs)
    log_method(event_name, **log_fields)


def log_sync_job(
    event: str,
    level: str = "info",
    sync_job_id: Optional[str] = None,
    connection_id: Optional[str] = None,
    marketplace_type: Optional[str] = None,
    direction: Optional[str] = None,
    tenant_id: Optional[str] = None,
    status: Optional[str] = None,
    duration: Optional[float] = None,
    total_items: Optional[int] = None,
    successful_items: Optional[int] = None,
    failed_items: Optional[int] = None,
    error_type: Optional[str] = None,
    error_message: Optional[str] = None,
    **kwargs
):
    """
    Log sync job operation with structured fields and correlation IDs.

    Args:
        event: Event name (e.g., "sync_job_started", "sync_job_completed")
        level: Log level ("info", "warning", "error", "debug")
        sync_job_id: Sync job ID
        connection_id: Connection ID
        marketplace_type: Marketplace type
        direction: Sync direction ("PUSH", "PULL", "BIDIRECTIONAL")
        tenant_id: Tenant ID
        status: Job status
        duration: Job duration in seconds
        total_items: Total items processed
        successful_items: Successful items count
        failed_items: Failed items count
        error_type: Error type if job failed
        error_message: Error message if job failed
        **kwargs: Additional structured fields
    """
    # Get correlation context
    correlation_context = get_correlation_context()

    # Build structured log fields
    log_fields = {
        "event": event,
        "component": "marketplace_sync_job",
    }

    # Add job context
    if sync_job_id:
        log_fields["sync_job_id"] = sync_job_id
    if connection_id:
        log_fields["connection_id"] = connection_id
    if marketplace_type:
        log_fields["marketplace_type"] = marketplace_type
    if direction:
        log_fields["direction"] = direction
    if tenant_id:
        log_fields["tenant_id"] = tenant_id

    # Add job status and metrics
    if status:
        log_fields["status"] = status
    if duration is not None:
        log_fields["duration_seconds"] = duration
    if total_items is not None:
        log_fields["total_items"] = total_items
    if successful_items is not None:
        log_fields["successful_items"] = successful_items
    if failed_items is not None:
        log_fields["failed_items"] = failed_items

    # Add error context
    if error_type:
        log_fields["error_type"] = error_type
    if error_message:
        log_fields["error_message"] = error_message

    # Add correlation IDs
    log_fields.update(correlation_context)

    # Add any additional fields
    log_fields.update(kwargs)

    # Get logger method
    log_method = getattr(logger, level, logger.info)

    # Extract event name (structlog expects it as first positional arg)
    event_name = log_fields.pop("event", "log_event")

    # Log with structured fields (event as first arg, rest as kwargs)
    log_method(event_name, **log_fields)


def log_api_call(
    event: str,
    level: str = "info",
    marketplace_type: Optional[str] = None,
    endpoint: Optional[str] = None,
    method: Optional[str] = None,
    status_code: Optional[str] = None,
    tenant_id: Optional[str] = None,
    duration: Optional[float] = None,
    error_type: Optional[str] = None,
    error_message: Optional[str] = None,
    **kwargs
):
    """
    Log API call with structured fields and correlation IDs.

    Args:
        event: Event name (e.g., "api_call_started", "api_call_completed")
        level: Log level ("info", "warning", "error", "debug")
        marketplace_type: Marketplace type
        endpoint: API endpoint path
        method: HTTP method
        status_code: HTTP status code
        tenant_id: Tenant ID
        duration: API call duration in seconds
        error_type: Error type if call failed
        error_message: Error message if call failed
        **kwargs: Additional structured fields
    """
    # Get correlation context
    correlation_context = get_correlation_context()

    # Build structured log fields
    log_fields = {
        "event": event,
        "component": "marketplace_api",
    }

    # Add API call context
    if marketplace_type:
        log_fields["marketplace_type"] = marketplace_type
    if endpoint:
        log_fields["endpoint"] = endpoint
    if method:
        log_fields["method"] = method
    if status_code:
        log_fields["status_code"] = status_code
    if tenant_id:
        log_fields["tenant_id"] = tenant_id

    # Add API call metrics
    if duration is not None:
        log_fields["duration_seconds"] = duration

    # Add error context
    if error_type:
        log_fields["error_type"] = error_type
    if error_message:
        log_fields["error_message"] = error_message

    # Add correlation IDs
    log_fields.update(correlation_context)

    # Add any additional fields
    log_fields.update(kwargs)

    # Get logger method
    log_method = getattr(logger, level, logger.info)

    # Extract event name (structlog expects it as first positional arg)
    event_name = log_fields.pop("event", "log_event")

    # Log with structured fields (event as first arg, rest as kwargs)
    log_method(event_name, **log_fields)


