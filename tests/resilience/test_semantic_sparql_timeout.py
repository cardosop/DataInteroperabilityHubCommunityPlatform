"""Phase 107: Semantic/SPARQL service timeout — status reporting."""

import uuid

from django.test import TestCase

from hub.apps.core.resilience.circuit_breaker import CircuitBreaker, CircuitBreakerState


class SemanticSPARQLTimeoutTest(TestCase):
    """SPARQL circuit breaker reports correct status."""

    def _make_cb(self, **kwargs):
        defaults = {
            "service_name": f"test-{uuid.uuid4().hex[:8]}",
            "failure_threshold": 3,
            "timeout_seconds": 30,
            "success_threshold": 2,
            "redis_client": None,
        }
        defaults.update(kwargs)
        return CircuitBreaker(**defaults)

    def test_status_reports_closed(self):
        """get_status() reports CLOSED for a fresh circuit breaker."""
        name = f"semantic-{uuid.uuid4().hex[:8]}"
        cb = self._make_cb(service_name=name)
        status = cb.get_status()
        self.assertEqual(status["service_name"], name)
        self.assertEqual(status["state"], "CLOSED")
        self.assertEqual(status["failure_threshold"], 3)

    def test_status_reports_open_after_failures(self):
        """get_status() reports OPEN when state is set to OPEN."""
        cb = self._make_cb(failure_threshold=3)
        # _increment_failure_count doesn't trigger state transition
        cb._set_state(CircuitBreakerState.OPEN)
        status = cb.get_status()
        self.assertEqual(status["state"], "OPEN")
