"""
Error Handling Module

Provides comprehensive error handling including:
- Standardized error responses
- Enhanced error logging
- Sentry integration
- Error recovery mechanisms
"""

from hub.apps.core.error_handling.error_logging import (
    ErrorLogger,
    log_error,
    log_exception,
)
from hub.apps.core.error_handling.error_recovery import (
    CircuitBreaker,
    ErrorRecovery,
    RetryStrategy,
    with_circuit_breaker,
    with_retry,
)
from hub.apps.core.error_handling.error_responses import (
    ErrorResponse,
    ErrorResponseBuilder,
    format_error_response,
)
from hub.apps.core.error_handling.error_tracking import (
    ErrorTracker,
    track_error,
    track_exception,
)

__all__ = [
    "CircuitBreaker",
    "ErrorLogger",
    "ErrorRecovery",
    "ErrorResponse",
    "ErrorResponseBuilder",
    "ErrorTracker",
    "RetryStrategy",
    "format_error_response",
    "log_error",
    "log_exception",
    "track_error",
    "track_exception",
    "with_circuit_breaker",
    "with_retry",
]
