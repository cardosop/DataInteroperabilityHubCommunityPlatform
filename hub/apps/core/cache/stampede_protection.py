"""
311.19 (G26) — Cache stampede protection via Redis SETNX lock.

Prevents cache stampede (thundering herd) for hot keys by using
a Redis-based distributed lock. Only one worker recomputes the
value; other concurrent requests wait briefly and return stale
data or the fresh value once available.
"""

import time
from collections.abc import Callable
from functools import wraps
from typing import Any

from django.core.cache import cache as django_cache
from django_redis import get_redis_connection

LOCK_TTL = 5  # seconds — max time a recompute can hold the lock
WAIT_TIMEOUT = 2  # seconds — max time to poll for lock release
POLL_INTERVAL = 0.1  # seconds between lock polls


def _lock_key(cache_key: str) -> str:
    return f"lock:{cache_key}"


def with_stampede_protection(
    cache_key: str,
    timeout: int = 300,
    lock_ttl: int = LOCK_TTL,
):
    """Decorator that wraps a function with cache-stampede protection.

    Usage::

        @with_stampede_protection("dataset_list:{tenant_id}", timeout=60)
        def get_datasets(tenant_id):
            return Dataset.objects.filter(tenant_id=tenant_id)
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            # Format the cache key with args
            resolved_key = cache_key.format(*args, **kwargs) if args or kwargs else cache_key
            lock_key_val = _lock_key(resolved_key)

            # Fast path: cache hit
            cached = django_cache.get(resolved_key)
            if cached is not None:
                return cached

            # Try to acquire recompute lock
            redis = get_redis_connection("default")
            acquired = redis.set(lock_key_val, "1", nx=True, ex=lock_ttl)

            if acquired:
                try:
                    value = fn(*args, **kwargs)
                    django_cache.set(resolved_key, value, timeout=timeout)
                    return value
                finally:
                    redis.delete(lock_key_val)
            else:
                # Another worker is recomputing — poll for fresh value
                deadline = time.monotonic() + WAIT_TIMEOUT
                while time.monotonic() < deadline:
                    time.sleep(POLL_INTERVAL)
                    cached = django_cache.get(resolved_key)
                    if cached is not None:
                        return cached
                # Timeout — compute anyway (degraded mode)
                value = fn(*args, **kwargs)
                django_cache.set(resolved_key, value, timeout=timeout)
                return value

        return wrapper

    return decorator


# ── Pre-registered hot keys (311.19) ────────────────────────────────────

HOT_KEYS = {
    "dataset_list": "dataset_list:{tenant_id}",
    "contract_validation": "contract_validation:{sha256}",
    "search_index": "search_index:{tenant_id}:{query_hash}",
}
