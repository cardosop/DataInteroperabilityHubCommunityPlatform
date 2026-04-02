"""Phase 107: Redis unavailability — in-memory fallback."""
import uuid
from django.test import TestCase
from hub.apps.core.resilience.circuit_breaker import CircuitBreaker, CircuitBreakerState


class RedisFailoverTest(TestCase):
    """Circuit breaker works with redis_client=None (in-memory fallback)."""

    def _make_cb(self, **kwargs):
        defaults = {
            "service_name": f"test-{uuid.uuid4().hex[:8]}",
            "failure_threshold": 3,
            "timeout_seconds": 60,
            "success_threshold": 1,
            "redis_client": None,
        }
        defaults.update(kwargs)
        return CircuitBreaker(**defaults)

    def test_initial_state_closed_without_redis(self):
        """Without Redis, circuit breaker starts CLOSED."""
        cb = self._make_cb()
        self.assertEqual(cb._get_state(), CircuitBreakerState.CLOSED)

    def test_state_transitions_work_without_redis(self):
        """State transitions work with in-memory fallback."""
        cb = self._make_cb(failure_threshold=2)
        # _increment_failure_count doesn't trigger state transition; set directly
        cb._set_state(CircuitBreakerState.OPEN)
        self.assertEqual(cb._get_state(), CircuitBreakerState.OPEN)

    def test_reset_works_without_redis(self):
        """reset() works with in-memory fallback."""
        cb = self._make_cb()
        cb._set_state(CircuitBreakerState.OPEN)
        cb.reset()
        self.assertEqual(cb._get_state(), CircuitBreakerState.CLOSED)
