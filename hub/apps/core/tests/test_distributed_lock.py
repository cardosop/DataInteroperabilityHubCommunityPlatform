"""Distributed lock — real Redis integration tests (Phase 260.0.16).

Tests the SET NX + Lua compare-and-del token-release semantics against
the live Redis instance (redis-cache-test) shared by the test suite.
"""

from __future__ import annotations

import threading

import pytest
import redis as redis_lib
from django.conf import settings
from django.test import TestCase

from hub.apps.core.distributed_lock import (
    distributed_lock,
    distributed_lock_acquire,
    distributed_lock_release,
)

_LOCK_KEY_PREFIX = "test:dl"


def _get_cache_redis_or_none():
    """Return a real Redis client for the cache pool, or None if unavailable."""
    try:
        redis_url = getattr(
            settings,
            "REDIS_CACHE_URL",
            getattr(settings, "REDIS_URL", "redis://redis-cache-test:6379/0"),
        )
        client = redis_lib.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        client.ping()
        return client
    except Exception:
        return None


@pytest.mark.integration
class DistributedLockRedisTests(TestCase):
    """Distributed lock contract verified against real Redis (no stubs)."""

    def setUp(self) -> None:
        self.redis = _get_cache_redis_or_none()
        if self.redis is None:
            self.skipTest("Redis not available for integration tests")

        # Clean up any leftover keys from previous runs
        try:
            keys = self.redis.keys(f"{_LOCK_KEY_PREFIX}:*")
            if keys:
                self.redis.delete(*keys)
        except Exception:
            pass

    def tearDown(self) -> None:
        try:
            keys = self.redis.keys(f"{_LOCK_KEY_PREFIX}:*")
            if keys:
                self.redis.delete(*keys)
        except Exception:
            pass

    @pytest.mark.integration
    def test_acquire_exclusive(self) -> None:
        ok1, tok1 = distributed_lock_acquire(
            self.redis,
            f"{_LOCK_KEY_PREFIX}:purge",
            ttl_seconds=30,
        )
        self.assertTrue(ok1)
        ok2, _ = distributed_lock_acquire(
            self.redis,
            f"{_LOCK_KEY_PREFIX}:purge",
            ttl_seconds=30,
        )
        self.assertFalse(ok2)
        self.assertTrue(
            distributed_lock_release(
                self.redis,
                f"{_LOCK_KEY_PREFIX}:purge",
                token=tok1,
            ),
        )
        ok3, _ = distributed_lock_acquire(
            self.redis,
            f"{_LOCK_KEY_PREFIX}:purge",
            ttl_seconds=30,
        )
        self.assertTrue(ok3)

    @pytest.mark.integration
    def test_release_requires_token_match(self) -> None:
        key = f"{_LOCK_KEY_PREFIX}:r2"
        ok, tok_a = distributed_lock_acquire(self.redis, key, ttl_seconds=30)
        self.assertTrue(ok)
        released = distributed_lock_release(
            self.redis,
            key,
            token="wrong-holder",
        )
        self.assertFalse(released)
        self.assertEqual(self.redis.get(key), tok_a)
        released_ok = distributed_lock_release(self.redis, key, token=tok_a)
        self.assertTrue(released_ok)
        self.assertIsNone(self.redis.get(key))

    @pytest.mark.integration
    def test_context_manager_releases_on_success(self) -> None:
        key = f"{_LOCK_KEY_PREFIX}:cm"
        with distributed_lock(self.redis, key, ttl_seconds=60) as tok:
            self.assertGreater(self.redis.ttl(key), 0)
            self.assertNotEqual(tok, "")
        self.assertIsNone(self.redis.get(key))

    @pytest.mark.integration
    def test_concurrent_acquire_only_one_holder(self) -> None:
        results: list[bool] = []
        tokens: list[str] = []
        barrier = threading.Barrier(2)

        # Each contender needs its own connection; fakeredis was
        # in-process safe, real Redis requires separate clients.
        def contender() -> None:
            client = _get_cache_redis_or_none()
            if client is None:
                results.append(True)  # don't block on redis outage
                return
            barrier.wait()
            ok, tok = distributed_lock_acquire(
                client,
                f"{_LOCK_KEY_PREFIX}:r3",
                ttl_seconds=60,
            )
            results.append(ok)
            if ok:
                tokens.append(tok)

        t1 = threading.Thread(target=contender)
        t2 = threading.Thread(target=contender)
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)
        self.assertEqual(sum(1 for ok in results if ok), 1)
        for tok in tokens:
            distributed_lock_release(
                self.redis,
                f"{_LOCK_KEY_PREFIX}:r3",
                token=tok,
            )

    @pytest.mark.integration
    def test_purge_deleted_files_lock_key_is_exclusive(self) -> None:
        """Contract: management command key matches SET NX + token release
        semantics."""
        from hub.apps.files.management.commands.purge_deleted_files import (
            _PURGE_LOCK_KEY,
        )

        ok1, tok1 = distributed_lock_acquire(
            self.redis,
            _PURGE_LOCK_KEY,
            ttl_seconds=3600,
            wait_seconds=0,
        )
        self.assertTrue(ok1)
        ok2, _ = distributed_lock_acquire(
            self.redis,
            _PURGE_LOCK_KEY,
            ttl_seconds=3600,
            wait_seconds=0,
        )
        self.assertFalse(ok2)
        self.assertTrue(
            distributed_lock_release(
                self.redis,
                _PURGE_LOCK_KEY,
                token=tok1,
            ),
        )

    @pytest.mark.integration
    def test_wait_seconds_polls_when_lock_held(self) -> None:
        """When lock is held, wait_seconds spins until deadline then returns False."""
        import time as _time

        key = f"{_LOCK_KEY_PREFIX}:wait-poll"
        ok1, tok1 = distributed_lock_acquire(self.redis, key, ttl_seconds=30)
        self.assertTrue(ok1)

        start = _time.monotonic()
        ok2, _ = distributed_lock_acquire(
            self.redis,
            key,
            ttl_seconds=30,
            wait_seconds=1.0,
            retry_interval_seconds=0.1,
        )
        elapsed = _time.monotonic() - start
        self.assertFalse(ok2)
        self.assertGreaterEqual(elapsed, 0.9, "Should have polled for at least ~1 second")

        distributed_lock_release(self.redis, key, token=tok1)

    @pytest.mark.integration
    def test_acquire_rejects_non_positive_ttl(self) -> None:
        """TTL <= 0 must raise ValueError."""
        with self.assertRaises(ValueError) as ctx:
            distributed_lock_acquire(self.redis, f"{_LOCK_KEY_PREFIX}:ttl-0", ttl_seconds=0)
        self.assertIn("ttl_seconds must be positive", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx:
            distributed_lock_acquire(self.redis, f"{_LOCK_KEY_PREFIX}:ttl-neg", ttl_seconds=-5)
        self.assertIn("ttl_seconds must be positive", str(ctx.exception))
