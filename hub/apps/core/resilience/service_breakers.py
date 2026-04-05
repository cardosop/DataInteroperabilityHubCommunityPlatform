"""
Shared CircuitBreaker instances per external service (Phase 205).

Ensures health checks, run/submit paths, and activation degradation logic observe the
same OPEN/CLOSED state for a given service name.
"""
from __future__ import annotations

import threading
from typing import Dict, Tuple

from hub.apps.core.resilience.circuit_breaker import CircuitBreaker, get_redis_client

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
    """
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
