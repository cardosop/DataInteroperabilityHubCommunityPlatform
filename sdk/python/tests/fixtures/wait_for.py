"""
Phase 216.X.6 — deterministic ``wait_for`` polling helper.

Replaces fixed ``time.sleep(N)`` calls in tests that depend on eventual
consistency (search index rebuilds, audit log materialization, async
worker queues). The helper polls a predicate until it returns True or a
timeout elapses, then either returns the predicate's truthy value or
raises ``TimeoutError`` with diagnostic context.

Phase 216 has zero tolerance for flake (no ``pytest-rerunfailures``,
no auto-retry); the only acceptable way to handle eventual consistency
is to express it as a polling predicate via this helper.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Optional, TypeVar

T = TypeVar("T")


def wait_for(
    predicate: Callable[[], T],
    *,
    timeout: float = 30.0,
    interval: float = 0.1,
    description: Optional[str] = None,
) -> T:
    """Poll ``predicate`` until it returns truthy or ``timeout`` elapses.

    Args:
        predicate: A zero-arg callable. Truthy return value is the
            success signal. Exceptions raised by the predicate are
            **propagated immediately** — they are NOT swallowed and
            retried, because eventual consistency means "value is not
            yet there", not "the call crashed".
        timeout: Maximum total wait in seconds. Defaults to 30s, which
            matches the spec's reference budget for backend eventual
            consistency.
        interval: Sleep between polls. Defaults to 100ms — small enough
            to feel snappy, large enough not to hot-loop.
        description: Optional human-readable label included in the
            ``TimeoutError`` message. Defaults to the predicate's repr.

    Returns:
        The first truthy value returned by ``predicate``.

    Raises:
        TimeoutError: if ``timeout`` elapses without a truthy return.
        ValueError: if ``timeout`` or ``interval`` is non-positive.
    """
    if timeout <= 0:
        raise ValueError(f"timeout must be > 0, got {timeout}")
    if interval <= 0:
        raise ValueError(f"interval must be > 0, got {interval}")

    deadline = time.monotonic() + timeout
    last_value: Any = None
    iterations = 0
    while True:
        iterations += 1
        last_value = predicate()
        if last_value:
            return last_value
        if time.monotonic() >= deadline:
            label = description or f"predicate={predicate!r}"
            raise TimeoutError(
                f"wait_for timed out after {timeout}s "
                f"({iterations} iterations, last value={last_value!r}): {label}"
            )
        time.sleep(interval)
