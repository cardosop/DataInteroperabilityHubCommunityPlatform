"""
Phase 277.B.072 — circuit breaker integration for RQ task consumers.

Wires ``CircuitBreaker`` from ``hub.apps.core.resilience`` into RQ task
dispatch and execution so that when a downstream dependency (Stripe,
compliance-service, email provider, etc.) is unhealthy, the
circuit opens and subsequent enqueued tasks are deferred rather than
wasting worker slots on guaranteed failures.

Usage — decorate any ``@job`` function::

    from hub.apps.jobs.task_circuit_breaker import circuit_breaker_guard

    @job("job_default", timeout=360)
    @circuit_breaker_guard("stripe_api", failure_threshold=5, timeout_seconds=120)
    def sync_stripe_data(tenant_id: str) -> None:
        ...

Behaviour:
* Before the wrapped function runs, ``guard.check()`` is called.
  If the circuit is OPEN the function returns immediately (no-op)
  and logs a warning with ``task_skipped_circuit_open``.
* On success, ``guard.success()`` is called.
* On exception, ``guard.failure()`` is called and the original
  exception is re-raised (so RQ's retry machinery still operates).
"""
from __future__ import annotations

import functools
import logging
from typing import Callable

from hub.apps.core.resilience.circuit_breaker import CircuitBreakerError
from hub.apps.core.resilience.service_breakers import get_shared_circuit_breaker as _get_breaker

logger = logging.getLogger(__name__)


# ── Decorator ──────────────────────────────────────────────────────────


def circuit_breaker_guard(
    service_name: str,
    failure_threshold: int = 5,
    timeout_seconds: int = 120,
    success_threshold: int = 2,
):
    """Return a decorator that wraps an RQ task function with a circuit breaker.

    Args:
        service_name: Name of the downstream service to protect.
        failure_threshold: Consecutive failures before opening (default 5).
        timeout_seconds: Seconds before attempting HALF_OPEN (default 120).
        success_threshold: Successes in HALF_OPEN needed to close (default 2).
    """
    breaker = _get_breaker(
        service_name=service_name,
        failure_threshold=failure_threshold,
        timeout_seconds=timeout_seconds,
        success_threshold=success_threshold,
    )

    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                breaker.check()
            except CircuitBreakerError:
                logger.warning(
                    "task_skipped_circuit_open",
                    extra={
                        "task": func.__name__,
                        "service_name": service_name,
                    },
                )
                # Return None so RQ treats it as a no-op success rather than
                # consuming retries on a known-broken downstream.
                return None

            try:
                result = func(*args, **kwargs)
            except Exception:
                breaker.failure()
                raise

            breaker.success()
            return result

        return wrapper

    return decorator
