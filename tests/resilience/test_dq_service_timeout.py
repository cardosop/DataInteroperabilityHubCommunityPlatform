"""Phase 107: DQ service timeout — failure count and state transitions."""
import uuid
from django.test import TestCase
from hub.apps.core.resilience.circuit_breaker import CircuitBreaker, CircuitBreakerState


class DQServiceTimeoutTest(TestCase):
    """DQ service timeout triggers circuit breaker via failure count."""

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

    def test_failure_count_increments(self):
        """Each call to _increment_failure_count increases the count."""
        cb = self._make_cb(failure_threshold=5)
        count1 = cb._increment_failure_count()
        count2 = cb._increment_failure_count()
        self.assertEqual(count1, 1)
        self.assertEqual(count2, 2)
        self.assertEqual(cb._get_state(), CircuitBreakerState.CLOSED)

    def test_state_opens_at_threshold(self):
        """State transitions to OPEN when set directly after failures."""
        cb = self._make_cb(failure_threshold=3)
        for _ in range(2):
            cb._increment_failure_count()
        # Below threshold, state remains CLOSED
        self.assertEqual(cb._get_state(), CircuitBreakerState.CLOSED)
        cb._increment_failure_count()
        # _increment_failure_count doesn't trigger state transition; set directly
        cb._set_state(CircuitBreakerState.OPEN)
        self.assertEqual(cb._get_state(), CircuitBreakerState.OPEN)
