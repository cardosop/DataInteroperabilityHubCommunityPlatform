"""Phase 111.5 — Random service failure → platform continues serving."""

import pytest
from django.test import TestCase

from hub.apps.core.resilience.circuit_breaker import CircuitBreaker, CircuitBreakerState

pytestmark = pytest.mark.django_db(transaction=True)


class RandomServiceFailureTest(TestCase):
    """Platform continues serving when individual services fail."""

    def test_compliance_down_does_not_affect_dq(self):
        """Compliance circuit open does not affect DQ circuit."""
        compliance_cb = CircuitBreaker(
            service_name="compliance-chaos-1",
            failure_threshold=3,
            timeout_seconds=10,
            success_threshold=1,
            redis_client=None,
        )
        dq_cb = CircuitBreaker(
            service_name="dq-chaos-1",
            failure_threshold=3,
            timeout_seconds=10,
            success_threshold=1,
            redis_client=None,
        )
        compliance_cb._set_state(CircuitBreakerState.OPEN)
        self.assertEqual(compliance_cb._get_state(), CircuitBreakerState.OPEN)
        self.assertEqual(dq_cb._get_state(), CircuitBreakerState.CLOSED)

    def test_dq_down_does_not_affect_semantic(self):
        """DQ circuit open does not affect semantic circuit."""
        dq_cb = CircuitBreaker(
            service_name="dq-chaos-2",
            failure_threshold=3,
            timeout_seconds=10,
            success_threshold=1,
            redis_client=None,
        )
        semantic_cb = CircuitBreaker(
            service_name="semantic-chaos-1",
            failure_threshold=3,
            timeout_seconds=10,
            success_threshold=1,
            redis_client=None,
        )
        dq_cb._set_state(CircuitBreakerState.OPEN)
        self.assertEqual(dq_cb._get_state(), CircuitBreakerState.OPEN)
        self.assertEqual(semantic_cb._get_state(), CircuitBreakerState.CLOSED)

    def test_circuit_breaker_reset_recovers(self):
        """Circuit breaker reset returns to CLOSED state."""
        cb = CircuitBreaker(
            service_name="reset-chaos",
            failure_threshold=2,
            timeout_seconds=0,
            success_threshold=1,
            redis_client=None,
        )
        cb._set_state(CircuitBreakerState.OPEN)
        self.assertEqual(cb._get_state(), CircuitBreakerState.OPEN)
        cb.reset()
        self.assertEqual(cb._get_state(), CircuitBreakerState.CLOSED)
