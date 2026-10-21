"""
Resilience Patterns

Circuit breaker and fallback mechanisms for service resilience.
"""

from .backoff import (
    backoff_with_jitter,
    sleep_with_jitter,
)
from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitBreakerState,
    circuit_breaker,
)
from .fallback import (
    FallbackError,
    FallbackStrategy,
    fallback,
)

__all__ = [
    "CircuitBreaker",
    "CircuitBreakerError",
    "CircuitBreakerState",
    "FallbackError",
    "FallbackStrategy",
    "backoff_with_jitter",
    "circuit_breaker",
    "fallback",
    "sleep_with_jitter",
]
