"""
Phase 260.0.16 — Redis-backed distributed locks (SET NX + token release).

Operators wrap destructive management commands with ``distributed_lock()`` so
only one Hub pod executes at a time. Release uses Lua compare-and-del so only
the lock holder clears the key.
"""

from __future__ import annotations
import secrets
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

_LUA_COMPARE_DEL = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('DEL', KEYS[1])
else
  return 0
end
"""


def distributed_lock_acquire(
    redis_client: Any,
    key: str,
    *,
    token: str | None = None,
    ttl_seconds: int = 900,
    wait_seconds: float = 0,
    retry_interval_seconds: float = 0.2,
) -> tuple[bool, str]:
    """
    Try to acquire a lock. Returns ``(True, token)`` if acquired, else ``(False, "")``.
    ``wait_seconds`` spins with ``retry_interval_seconds`` sleeps (polling SET NX).
    """
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be positive")

    holder = token or secrets.token_hex(16)
    deadline = time.monotonic() + max(0.0, wait_seconds)
    while True:
        acquired = bool(
            redis_client.set(key, holder, nx=True, ex=int(ttl_seconds)),
        )
        if acquired:
            return True, holder
        if time.monotonic() >= deadline:
            return False, ""
        time.sleep(max(0.01, retry_interval_seconds))


def distributed_lock_release(redis_client: Any, key: str, *, token: str) -> bool:
    """Release only if ``token`` matches; returns True if deleted.

    Uses Lua ``compare-and-del`` for atomicity when available (real Redis);
    falls back to ``GET`` + ``DELETE`` when the Redis-compatible backend
    does not support ``EVAL`` (e.g. fakeredis, constrained test environments).
    The fallback is NOT atomic but is sufficient for test isolation where
    concurrent contended lock release doesn't occur.
    """
    if not token:
        return False
    try:
        res = redis_client.eval(_LUA_COMPARE_DEL, 1, key, token)
        return bool(int(res))
    except Exception:
        # EVAL not available — fall back to non-atomic GET + compare + DELETE.
        # Safe for test / single-worker scenarios.
        current = redis_client.get(key)
        if current and (current.decode() if isinstance(current, bytes) else current) == token:
            return bool(redis_client.delete(key))
        return False


@contextmanager
def distributed_lock(
    redis_client: Any,
    key: str,
    *,
    ttl_seconds: int = 900,
    wait_seconds: float = 0,
    strict: bool = True,
) -> Iterator[str]:
    """
    Acquire on entry, release on exit.

    When ``strict`` is True and acquisition fails immediately, raises
    ``RuntimeError``. With ``strict`` False + no lock, yields ``""`` without
    mutating Redis.
    """
    ok, tok = distributed_lock_acquire(
        redis_client,
        key,
        ttl_seconds=ttl_seconds,
        wait_seconds=wait_seconds,
    )
    if not ok:
        if strict:
            raise RuntimeError(f"distributed_lock_unavailable:{key}")
        yield ""
        return
    try:
        yield tok
    finally:
        try:
            distributed_lock_release(redis_client, key, token=tok)
        except Exception as exc:
            if strict:
                raise RuntimeError(
                    f"distributed_lock_release_failed:{key}",
                ) from exc
