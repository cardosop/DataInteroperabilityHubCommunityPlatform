"""
Observability: Structured Logging

Enhanced structlog configuration with required fields and PII redaction.
"""
import re
import structlog
from typing import Any, Dict
from django.conf import settings


# PII patterns for redaction
PII_PATTERNS = [
    (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL_REDACTED]'),  # Email
    (r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', '[CARD_REDACTED]'),  # Credit card
    (r'\b\d{3}-\d{2}-\d{4}\b', '[SSN_REDACTED]'),  # SSN
    (r'\b\d{10,}\b', '[PHONE_REDACTED]'),  # Phone numbers (10+ digits)
    (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL_REDACTED]'),  # Email (duplicate for safety)
]


def redact_pii(message: str) -> str:
    """
    Redact PII from log messages.
    
    Args:
        message: Log message string
        
    Returns:
        Message with PII redacted
    """
    if not isinstance(message, str):
        return message
    
    redacted = message
    for pattern, replacement in PII_PATTERNS:
        redacted = re.sub(pattern, replacement, redacted, flags=re.IGNORECASE)
    
    return redacted


def redact_pii_processor(logger, method_name, event_dict):
    """
    Structlog processor to redact PII from log entries.
    
    Args:
        logger: Logger instance
        method_name: Log method name
        event_dict: Event dictionary
        
    Returns:
        Event dictionary with PII redacted
    """
    # Redact PII from message
    if 'event' in event_dict:
        event_dict['event'] = redact_pii(str(event_dict['event']))
    
    # Redact PII from additional fields
    pii_fields = ['email', 'phone', 'ssn', 'credit_card', 'password', 'token', 'api_key']
    for field in pii_fields:
        if field in event_dict:
            event_dict[field] = '[REDACTED]'
    
    # Redact PII from nested dictionaries
    for key, value in event_dict.items():
        if isinstance(value, dict):
            for nested_key in pii_fields:
                if nested_key in value:
                    value[nested_key] = '[REDACTED]'
        elif isinstance(value, str) and key not in ['level', 'timestamp', 'service', 'request_id']:
            # Check if value looks like PII
            if '@' in value and '.' in value:  # Email-like
                event_dict[key] = '[REDACTED]'
    
    return event_dict


def add_service_name(logger, method_name, event_dict):
    """
    Add service name to log entries.
    
    Args:
        logger: Logger instance
        method_name: Log method name
        event_dict: Event dictionary
        
    Returns:
        Event dictionary with service name
    """
    if 'service' not in event_dict:
        event_dict['service'] = 'hub-api'
    return event_dict


def add_request_context(logger, method_name, event_dict):
    """
    Add request context (request_id, tenant_id, user_id) to log entries.
    
    Args:
        logger: Logger instance
        method_name: Log method name
        event_dict: Event dictionary
        
    Returns:
        Event dictionary with request context
    """
    # Request ID is already added by RequestIDMiddleware via contextvars
    # Tenant ID and user ID should be added by middleware or views
    
    return event_dict


def add_trace_context(logger, method_name, event_dict):
    """
    Add trace context (trace_id, span_id) to log entries for correlation.
    
    Args:
        logger: Logger instance
        method_name: Log method name
        event_dict: Event dictionary
        
    Returns:
        Event dictionary with trace context
    """
    try:
        from opentelemetry import trace
        
        span = trace.get_current_span()
        if span and span.get_span_context().is_valid:
            span_context = span.get_span_context()
            # Convert trace_id and span_id to hex strings
            trace_id = format(span_context.trace_id, '032x')
            span_id = format(span_context.span_id, '016x')
            event_dict['trace_id'] = trace_id
            event_dict['span_id'] = span_id
    except Exception:
        # If OpenTelemetry is not available, skip trace context
        pass
    
    return event_dict


def configure_structlog():
    """
    Configure structlog with required processors and JSON output.
    """
    import os
    from django.conf import settings
    
    # Determine log format
    log_format = os.getenv('LOG_FORMAT', 'json')
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    
    # Build processors list
    processors = [
        structlog.contextvars.merge_contextvars,  # Merge context variables (request_id, etc.)
        structlog.stdlib.filter_by_level,  # Filter by log level
        structlog.stdlib.add_logger_name,  # Add logger name
        structlog.stdlib.add_log_level,  # Add log level
        structlog.stdlib.PositionalArgumentsFormatter(),  # Format positional arguments
        structlog.processors.TimeStamper(fmt="iso"),  # ISO 8601 timestamp
        structlog.processors.StackInfoRenderer(),  # Stack traces
        structlog.processors.format_exc_info,  # Exception formatting
        add_service_name,  # Add service name
        add_request_context,  # Add request context
        add_trace_context,  # Add trace context (trace_id, span_id)
        redact_pii_processor,  # Redact PII
    ]
    
    # Add renderer based on format
    if log_format == 'json':
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

