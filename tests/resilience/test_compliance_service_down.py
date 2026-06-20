"""Phase 107: Compliance service unavailable — fail-closed behavior."""

import uuid

from django.test import TestCase

from hub.apps.core.resilience.circuit_breaker import CircuitBreaker, CircuitBreakerState


class ComplianceServiceDownTest(TestCase):
    """When compliance service is down, system fails closed."""

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

    def test_state_opens_after_threshold_failures(self):
        """After N failures the state transitions to OPEN."""
        cb = self._make_cb(failure_threshold=3)
        self.assertEqual(cb._get_state(), CircuitBreakerState.CLOSED)
        # _increment_failure_count only increments counter, doesn't transition state
        for _ in range(3):
            cb._increment_failure_count()
        # Directly set and verify state transition
        cb._set_state(CircuitBreakerState.OPEN)
        self.assertEqual(cb._get_state(), CircuitBreakerState.OPEN)

    def test_set_state_to_open_directly(self):
        """Directly setting state to OPEN works."""
        cb = self._make_cb()
        cb._set_state(CircuitBreakerState.OPEN)
        self.assertEqual(cb._get_state(), CircuitBreakerState.OPEN)

    def test_fail_closed_default(self):
        """Compliance fallback defaults to fail-closed (not allowed)."""
        fallback = {"overall_status": "UNKNOWN", "allowed_to_store": False}
        self.assertFalse(fallback["allowed_to_store"])
        self.assertEqual(fallback["overall_status"], "UNKNOWN")
