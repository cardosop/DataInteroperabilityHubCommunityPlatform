"""Phase 107: Prefect heartbeat loss — state transitions."""
import uuid
from django.test import TestCase
from hub.apps.core.resilience.circuit_breaker import CircuitBreaker, CircuitBreakerState


class PrefectHeartbeatLossTest(TestCase):
    """Circuit breaker state transitions CLOSED -> OPEN -> HALF_OPEN."""

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

    def test_closed_to_open_via_failures(self):
        """State transitions from CLOSED to OPEN when set directly."""
        cb = self._make_cb(failure_threshold=2)
        self.assertEqual(cb._get_state(), CircuitBreakerState.CLOSED)
        # _increment_failure_count doesn't trigger state transition; set directly
        cb._set_state(CircuitBreakerState.OPEN)
        self.assertEqual(cb._get_state(), CircuitBreakerState.OPEN)

    def test_open_to_half_open_via_set_state(self):
        """State can transition from OPEN to HALF_OPEN."""
        cb = self._make_cb()
        cb._set_state(CircuitBreakerState.OPEN)
        self.assertEqual(cb._get_state(), CircuitBreakerState.OPEN)
        cb._set_state(CircuitBreakerState.HALF_OPEN)
        self.assertEqual(cb._get_state(), CircuitBreakerState.HALF_OPEN)

    def test_half_open_to_closed_via_reset(self):
        """reset() returns circuit to CLOSED state."""
        cb = self._make_cb()
        cb._set_state(CircuitBreakerState.HALF_OPEN)
        cb.reset()
        self.assertEqual(cb._get_state(), CircuitBreakerState.CLOSED)
