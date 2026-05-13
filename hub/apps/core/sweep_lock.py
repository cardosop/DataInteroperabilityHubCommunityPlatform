"""
Phase 277.B.074 — distributed lock consistency for Prefect/django_rq sweeps.

Provides a standardised lock-key registry and a ``@sweep_lock`` decorator
that ensures only one instance of a named sweep operation executes at a
time — regardless of whether it was dispatched by Prefect, django_rq, or
a management command.

Lock keys follow the convention ``sweep:<sweep_name>`` so operators can
inspect them in Redis with ``KEYS sweep:*``.

Usage::

    from hub.apps.core.sweep_lock import sweep_lock

    @sweep_lock("cleanup_orphan_drafts", ttl_seconds=1800)
    def my_management_command():
        ...

The decorator uses ``distributed_lock`` from ``hub.apps.core.distributed_lock``
under the hood.  When the lock cannot be acquired (another instance is
already running), ``SweepLockHeldError`` is raised.
"""
from __future__ import annotations

import functools
from typing import Any, Callable

from hub.apps.core.distributed_lock import (
    distributed_lock_acquire,
    distributed_lock_release,
)

SWEEP_LOCK_KEY_PREFIX = "sweep"

# ── Registry ────────────────────────────────────────────────────────


# Known sweep lock keys — add new sweeps here so operators can grep
# the codebase for all scheduled mutex operations.
_KNOWN_SWEEPS: dict[str, str] = {}


def register_sweep(sweep_name: str, description: str) -> str:
    """Register a named sweep operation and return its lock key.

    Args:
        sweep_name: Short kebab-case identifier, e.g. ``cleanup-orphan-drafts``.
        description: Human-readable description for operators.

    Returns:
        The fully-qualified Redis lock key, e.g. ``sweep:cleanup-orphan-drafts``.
    """
    lock_key = f"{SWEEP_LOCK_KEY_PREFIX}:{sweep_name}"
    _KNOWN_SWEEPS[lock_key] = description
    return lock_key


def list_known_sweeps() -> dict[str, str]:
    """Return a copy of the registry for introspection / health checks."""
    return dict(_KNOWN_SWEEPS)


# ── Exception ───────────────────────────────────────────────────────


class SweepLockHeldError(RuntimeError):
    """Raised when a sweep lock cannot be acquired (another instance is active)."""

    def __init__(self, lock_key: str):
        super().__init__(
            f"Sweep lock held for '{lock_key}'. "
            "Another instance of this sweep is already running."
        )
        self.lock_key = lock_key


# ── Decorator ───────────────────────────────────────────────────────


def sweep_lock(
    sweep_name: str,
    ttl_seconds: int = 1800,
    wait_seconds: float = 0.0,
    description: str = "",
):
    """Decorator: wrap a callable with a distributed Redis lock.

    The lock key is ``sweep:<sweep_name>``.  The TTL ensures the lock
    auto-expires if the process crashes (no permanent deadlock).

    Args:
        sweep_name: Kebab-case sweep identifier (e.g. ``cleanup-orphan-drafts``).
        ttl_seconds: Lock expiry in seconds (default 30 min).
        wait_seconds: Seconds to poll for acquisition before giving up.
        description: Human-readable description for the sweep registry.

    Raises:
        SweepLockHeldError: If the lock cannot be acquired.
    """
    lock_key = register_sweep(sweep_name, description or sweep_name)

    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            from hub.apps.core.redis_pools import get_redis_cache_client

            redis_client = get_redis_cache_client()
            acquired, token = distributed_lock_acquire(
                redis_client,
                key=lock_key,
                ttl_seconds=ttl_seconds,
                wait_seconds=wait_seconds,
            )
            if not acquired:
                raise SweepLockHeldError(lock_key)

            try:
                return func(*args, **kwargs)
            finally:
                try:
                    distributed_lock_release(
                        redis_client,
                        key=lock_key,
                        token=token,
                    )
                except Exception:
                    # Lock will expire via TTL — best-effort release
                    pass

        # Attach metadata so introspection tools can discover sweep locks
        wrapper._sweep_lock_key = lock_key  # type: ignore[attr-defined]
        wrapper._sweep_lock_ttl = ttl_seconds  # type: ignore[attr-defined]

        return wrapper

    return decorator
