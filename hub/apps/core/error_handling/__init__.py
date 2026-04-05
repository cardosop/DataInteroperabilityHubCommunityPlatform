"""
Error Handling Module

Provides comprehensive error handling including:
- Standardized error responses
- Enhanced error logging
- Sentry integration
- Error recovery mechanisms
"""
from hub.apps.core.error_handling.error_responses import (
    ErrorResponse,
    ErrorResponseBuilder,
    format_error_response,
)
from hub.apps.core.error_handling.error_logging import (
    ErrorLogger,
    log_error,
    log_exception,
)
from hub.apps.core.error_handling.error_tracking import (
    ErrorTracker,
    track_error,
    track_exception,
)
from hub.apps.core.error_handling.error_recovery import (
    ErrorRecovery,
    RetryStrategy,
    CircuitBreaker,
    with_retry,
    with_circuit_breaker,
)

__all__ = [
    "ErrorResponse",
    "ErrorResponseBuilder",
    "format_error_response",
    "ErrorLogger",
    "log_error",
    "log_exception",
    "ErrorTracker",
    "track_error",
    "track_exception",
    "ErrorRecovery",
    "RetryStrategy",
    "CircuitBreaker",
    "with_retry",
    "with_circuit_breaker",
]

