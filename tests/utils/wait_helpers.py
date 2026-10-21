"""
Higher-level polling helpers built on ``wait_until`` (Phase 84).

These replace fixed ``time.sleep()`` calls in tests with
condition-based polling that is both faster (returns as soon as
the condition is met) and more reliable (no under-sleep flakiness).

Usage::

    from tests.utils.wait_helpers import (
        wait_for_count,
        wait_for_status,
        wait_for_condition,
    )

    # Wait for exactly 3 deliveries to appear
    wait_for_count(
        lambda: WebhookDelivery.objects.filter(webhook=wh).count(),
        expected=3,
    )

    # Wait for a job to reach COMPLETED status
    wait_for_status(
        lambda: Job.objects.get(id=job_id).status,
        expected="COMPLETED",
    )
"""

import time
from collections.abc import Callable, Sequence
from typing import Any

from tests.utils.polling import wait_until


def wait_for_count(
    count_fn: Callable[[], int],
    expected: int,
    *,
    timeout: float = 5.0,
    interval: float = 0.1,
    message: str | None = None,
) -> int:
    """Poll until ``count_fn()`` returns ``expected``.

    Args:
        count_fn: Callable returning a current count (e.g.
            ``lambda: qs.count()``).
        expected: The target count.
        timeout: Maximum seconds to wait.
        interval: Seconds between polls.
        message: Custom assertion message.

    Returns:
        The final count (== ``expected``).

    Raises:
        AssertionError: If the count doesn't reach ``expected``
        within ``timeout``.
    """
    msg = message or (f"Count did not reach {expected} within {timeout}s")
    wait_until(
        lambda: count_fn() == expected,
        timeout=timeout,
        interval=interval,
        message=msg,
    )
    return count_fn()


def wait_for_min_count(
    count_fn: Callable[[], int],
    minimum: int,
    *,
    timeout: float = 5.0,
    interval: float = 0.1,
    message: str | None = None,
) -> int:
    """Poll until ``count_fn() >= minimum``.

    Useful when the exact count is non-deterministic but you
    need at least N items to exist.

    Returns:
        The final count (>= ``minimum``).
    """
    msg = message or (f"Count did not reach >= {minimum} within {timeout}s")
    wait_until(
        lambda: count_fn() >= minimum,
        timeout=timeout,
        interval=interval,
        message=msg,
    )
    return count_fn()


def wait_for_status(
    status_fn: Callable[[], Any],
    expected: Any | Sequence,
    *,
    timeout: float = 5.0,
    interval: float = 0.1,
    message: str | None = None,
) -> Any:
    """Poll until ``status_fn()`` returns one of ``expected``.

    Args:
        status_fn: Callable returning the current status (e.g.
            ``lambda: instance.refresh_from_db() or instance.status``).
        expected: A single value or sequence of acceptable values.
        timeout: Maximum seconds to wait.
        interval: Seconds between polls.

    Returns:
        The final status value.

    Raises:
        AssertionError: If the status doesn't match within
        ``timeout``.
    """
    if isinstance(expected, (list, tuple, set, frozenset)):
        acceptable = set(expected)
    else:
        acceptable = {expected}

    msg = message or (f"Status did not reach {acceptable} within {timeout}s")
    wait_until(
        lambda: status_fn() in acceptable,
        timeout=timeout,
        interval=interval,
        message=msg,
    )
    return status_fn()


def wait_for_condition(
    condition: Callable[[], bool],
    *,
    timeout: float = 5.0,
    interval: float = 0.1,
    message: str = "Condition not met within timeout",
) -> None:
    """Alias for ``wait_until`` with keyword-only params.

    Identical to ``wait_until`` but reads better in test code::

        wait_for_condition(
            lambda: cache.get(key) is None,
            timeout=3.0,
            message="Cache entry should have expired",
        )
    """
    wait_until(
        condition,
        timeout=timeout,
        interval=interval,
        message=message,
    )


def wait_for_event_persistence(
    *,
    timeout: float = 2.0,
    interval: float = 0.05,
) -> None:
    """Short poll replacement for ``time.sleep(0.1)`` after
    event/audit writes.

    The Django ORM writes are synchronous so in theory the row is
    visible immediately, but under heavy transaction load the test
    reader may run before the commit is flushed.  This helper
    returns instantly if the event loop has nothing pending, or
    after a tiny poll otherwise — replacing the common pattern::

        time.sleep(0.1)  # Allow event persistence

    In practice this is a no-op sleep(0.05) — but it's documented,
    discoverable, and can be replaced with a real condition later.
    """
    # Minimal yield — just enough for transaction commit visibility
    time.sleep(min(interval, 0.05))
