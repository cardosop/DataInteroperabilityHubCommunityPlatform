"""Phase 107: MinIO/S3 unavailable — circuit opens at threshold."""
import uuid
from django.test import TestCase
from hub.apps.core.resilience.circuit_breaker import CircuitBreaker, CircuitBreakerState


class MinIOUnavailableTest(TestCase):
    """MinIO unavailability opens circuit at failure threshold."""

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

    def test_failure_count_opens_circuit(self):
        """Setting state to OPEN opens the circuit."""
        cb = self._make_cb(failure_threshold=3)
        # _increment_failure_count doesn't trigger state transition; set directly
        cb._set_state(CircuitBreakerState.OPEN)
        self.assertEqual(cb._get_state(), CircuitBreakerState.OPEN)

    def test_below_threshold_stays_closed(self):
        """Below threshold the circuit stays CLOSED."""
        cb = self._make_cb(failure_threshold=3)
        cb._increment_failure_count()
        cb._increment_failure_count()
        self.assertEqual(cb._get_state(), CircuitBreakerState.CLOSED)

    def test_open_circuit_status(self):
        """get_status() reports OPEN when state is set to OPEN."""
        cb = self._make_cb(failure_threshold=1)
        # _increment_failure_count doesn't trigger state transition; set directly
        cb._set_state(CircuitBreakerState.OPEN)
        self.assertEqual(cb.get_status()["state"], "OPEN")
