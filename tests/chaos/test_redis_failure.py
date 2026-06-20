"""Phase 111.6 — Redis failure → fail-open behaviour."""

import pytest
from django.core.cache import cache
from django.test import TestCase

from hub.apps.core.resilience.circuit_breaker import CircuitBreaker, CircuitBreakerState

pytestmark = pytest.mark.django_db(transaction=True)


class RedisFailureTest(TestCase):
    """When Redis is unavailable, app fails open."""

    def test_circuit_breaker_works_without_redis(self):
        """Circuit breaker falls back to in-memory state."""
        cb = CircuitBreaker(
            service_name="no-redis-chaos",
            failure_threshold=3,
            timeout_seconds=10,
            success_threshold=1,
            redis_client=None,
        )
        self.assertEqual(cb._get_state(), CircuitBreakerState.CLOSED)
        cb._set_state(CircuitBreakerState.OPEN)
        self.assertEqual(cb._get_state(), CircuitBreakerState.OPEN)

    def test_cache_miss_returns_none(self):
        """Cache miss returns None, not exception."""
        result = cache.get("chaos-test-nonexistent-key")
        self.assertIsNone(result)

    def test_cache_operations_dont_crash(self):
        """Set/get/delete cycle works without crashing."""
        cache.set("chaos-test-key", "value", timeout=5)
        val = cache.get("chaos-test-key")
        self.assertEqual(val, "value")
        cache.delete("chaos-test-key")
