"""
Resilience Patterns

Circuit breaker and fallback mechanisms for service resilience.
"""

from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerState,
    CircuitBreakerError,
    circuit_breaker,
)
from .fallback import (
    FallbackStrategy,
    FallbackError,
    fallback,
)
from .backoff import (
    backoff_with_jitter,
    sleep_with_jitter,
)

__all__ = [
    'CircuitBreaker',
    'CircuitBreakerState',
    'CircuitBreakerError',
    'circuit_breaker',
    'FallbackStrategy',
    'FallbackError',
    'fallback',
    'backoff_with_jitter',
    'sleep_with_jitter',
]

