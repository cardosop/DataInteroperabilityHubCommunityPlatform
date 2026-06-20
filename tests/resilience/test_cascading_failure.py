"""Phase 107: Cascading failure — independent circuit breakers."""

import uuid

from django.test import TestCase

from hub.apps.core.resilience.circuit_breaker import CircuitBreaker, CircuitBreakerState


class CascadingFailureTest(TestCase):
    """Multiple services have independent circuit breakers."""

    def _make_cb(self, **kwargs):
        defaults = {
            "service_name": f"test-{uuid.uuid4().hex[:8]}",
            "failure_threshold": 2,
            "timeout_seconds": 60,
            "success_threshold": 1,
            "redis_client": None,
        }
        defaults.update(kwargs)
        return CircuitBreaker(**defaults)

    def test_circuits_open_independently(self):
        """Opening one circuit does not affect another."""
        cb_a = self._make_cb(service_name=f"svc-a-{uuid.uuid4().hex[:8]}")
        cb_b = self._make_cb(service_name=f"svc-b-{uuid.uuid4().hex[:8]}")
        # _increment_failure_count doesn't trigger state transition; set directly
        cb_a._set_state(CircuitBreakerState.OPEN)
        self.assertEqual(cb_a._get_state(), CircuitBreakerState.OPEN)
        self.assertEqual(cb_b._get_state(), CircuitBreakerState.CLOSED)

    def test_status_reflects_per_service_state(self):
        """get_status() reflects each service independently."""
        cb_a = self._make_cb(service_name=f"down-{uuid.uuid4().hex[:8]}")
        cb_b = self._make_cb(service_name=f"up-{uuid.uuid4().hex[:8]}")
        cb_a._set_state(CircuitBreakerState.OPEN)
        self.assertEqual(cb_a.get_status()["state"], "OPEN")
        self.assertEqual(cb_b.get_status()["state"], "CLOSED")
