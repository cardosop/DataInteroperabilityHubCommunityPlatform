"""
Shared CircuitBreaker instances per external service (Phase 205).

Ensures health checks, run/submit paths, and activation degradation logic observe the
same OPEN/CLOSED state for a given service name.
"""
from __future__ import annotations

import threading
from typing import Dict, Tuple

from hub.apps.core.resilience.circuit_breaker import CircuitBreaker, CircuitBreakerState, get_redis_client

_LOCK = threading.Lock()
_STORE: Dict[Tuple[str, int, int, int], CircuitBreaker] = {}


def get_shared_circuit_breaker(
    service_name: str,
    failure_threshold: int = 5,
    timeout_seconds: int = 60,
    success_threshold: int = 2,
) -> CircuitBreaker:
    """
    Return a process-wide shared CircuitBreaker for *service_name* and parameters.

    The first call constructs the breaker (with Redis when available); later calls
    return the same instance so dq-service / compliance-service state is consistent.

    When a service is registered in
    :mod:`circuit_breaker_thresholds.PRODUCTION_THRESHOLDS`, the thresholds from
    that registry take precedence over the caller-supplied defaults.  This
    prevents a caller that forgets to pass explicit thresholds (e.g.
    ``ComplianceServiceClient``) from silently creating a breaker with the wrong
    ``timeout_seconds``.
    """
    # Resolve from the production-thresholds registry when available, falling
    # back to the caller-supplied values for services not yet registered there.
    try:
        from hub.apps.core.resilience.circuit_breaker_thresholds import (
            PRODUCTION_THRESHOLDS,
        )
        threshold = PRODUCTION_THRESHOLDS.get(service_name)
        if threshold is not None:
            failure_threshold = threshold.failure_threshold
            timeout_seconds = threshold.timeout_seconds
            success_threshold = threshold.success_threshold
    except ImportError:
        pass

    key = (service_name, failure_threshold, timeout_seconds, success_threshold)
    with _LOCK:
        existing = _STORE.get(key)
        if existing is not None:
            return existing
        br = CircuitBreaker(
            service_name=service_name,
            failure_threshold=failure_threshold,
            timeout_seconds=timeout_seconds,
            success_threshold=success_threshold,
            redis_client=get_redis_client(),
        )
        _STORE[key] = br
        return br


def reset_shared_circuit_breakers_for_service(service_name: str) -> None:
    """Reset all shared breakers registered for *service_name* (test isolation)."""
    with _LOCK:
        to_reset = [b for k, b in _STORE.items() if k[0] == service_name]
    for br in to_reset:
        br.reset()


def is_circuit_open(channel: str) -> bool:
    """
    Return True if the circuit breaker for *channel* is currently OPEN.

    Used by warehouse connectors to short-circuit queries when the
    breaker has tripped.  When no shared breaker has been registered
    for *channel* yet, the circuit is treated as CLOSED (safe to
    proceed).
    """
    try:
        with _LOCK:
            for (service_name, _ft, _to, _st), breaker in _STORE.items():
                if service_name == channel:
                    return breaker.get_state() == CircuitBreakerState.OPEN
    except Exception:
        # If Redis is unavailable or any other error occurs, fail open
        # (allow the query) rather than blocking legitimate traffic.
        return False
    return False
