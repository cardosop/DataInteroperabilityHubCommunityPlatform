"""
Tests for ``hub.apps.core.resilience.service_breakers``.

Tests the shared circuit breaker registry, singleton pattern, reset
isolation, and fail-open behaviour — without requiring a real Redis
connection.
"""

import contextlib
from unittest import mock

from django.test import SimpleTestCase

from hub.apps.core.resilience import service_breakers


class GetSharedCircuitBreakerTests(SimpleTestCase):
    """Tests for get_shared_circuit_breaker()."""

    def setUp(self):
        # Clear the shared store between tests
        with service_breakers._LOCK:
            service_breakers._STORE.clear()

    def test_same_params_returns_same_instance(self):
        """Same (service, thresholds) returns the same object."""
        br1 = service_breakers.get_shared_circuit_breaker(
            "test-svc", failure_threshold=3, timeout_seconds=30, success_threshold=1
        )
        br2 = service_breakers.get_shared_circuit_breaker(
            "test-svc", failure_threshold=3, timeout_seconds=30, success_threshold=1
        )
        assert br1 is br2

    def test_different_service_returns_different_instance(self):
        """Different service names produce different breakers."""
        br1 = service_breakers.get_shared_circuit_breaker("svc-a")
        br2 = service_breakers.get_shared_circuit_breaker("svc-b")
        assert br1 is not br2

    def test_different_thresholds_returns_different_instance(self):
        """Different threshold values produce different breakers."""
        br1 = service_breakers.get_shared_circuit_breaker("svc", failure_threshold=3)
        br2 = service_breakers.get_shared_circuit_breaker("svc", failure_threshold=5)
        assert br1 is not br2

    def test_returns_circuit_breaker_with_correct_service_name(self):
        """The created breaker stores the service name."""
        br = service_breakers.get_shared_circuit_breaker("my-service")
        assert br.service_name == "my-service"

    def test_production_threshold_overrides_caller_defaults(self):
        """When a service is registered in PRODUCTION_THRESHOLDS,
        those values take precedence over caller-supplied defaults."""
        # compliance-service is registered with failure_threshold=5,
        # timeout_seconds=120, success_threshold=2
        br = service_breakers.get_shared_circuit_breaker(
            "compliance-service",
            failure_threshold=3,  # caller wants 3
            timeout_seconds=30,  # caller wants 30
            success_threshold=1,  # caller wants 1
        )
        # Production thresholds override caller defaults
        assert br.failure_threshold == 5, (
            f"Expected production failure_threshold=5, got {br.failure_threshold}"
        )
        assert br.timeout_seconds == 120, (
            f"Expected production timeout_seconds=120, got {br.timeout_seconds}"
        )


class ResetSharedCircuitBreakersTests(SimpleTestCase):
    """Tests for reset_shared_circuit_breakers_for_service()."""

    def setUp(self):
        with service_breakers._LOCK:
            service_breakers._STORE.clear()

    def test_reset_only_matching_service(self):
        """Reset only clears breakers for the named service."""
        br_a = service_breakers.get_shared_circuit_breaker("svc-a")
        br_b = service_breakers.get_shared_circuit_breaker("svc-b")

        # Force both to OPEN state (bypass Redis)
        with (
            mock.patch.object(br_a, "reset") as reset_a,
            mock.patch.object(br_b, "reset") as reset_b,
        ):
            service_breakers.reset_shared_circuit_breakers_for_service("svc-a")
            reset_a.assert_called_once()
            reset_b.assert_not_called()

    def test_reset_handles_empty_store(self):
        """Resetting with no registered breakers does not crash."""
        service_breakers.reset_shared_circuit_breakers_for_service("unknown")
        # No exception → pass


class IsCircuitOpenTests(SimpleTestCase):
    """Tests for is_circuit_open()."""

    def setUp(self):
        with service_breakers._LOCK:
            service_breakers._STORE.clear()

    def test_no_breaker_registered_returns_false(self):
        """When no breaker exists for the channel, circuit is CLOSED."""
        assert service_breakers.is_circuit_open("unknown-channel") is False

    def test_closed_breaker_returns_false(self):
        """When breaker is CLOSED, is_circuit_open returns False."""
        service_breakers.get_shared_circuit_breaker("channel-x")
        # Default state is CLOSED
        assert service_breakers.is_circuit_open("channel-x") is False

    def test_fail_open_on_exception(self):
        """If state check raises (e.g. Redis down), returns False (fail-open)."""
        # Register a breaker then make get_state() raise
        br = service_breakers.get_shared_circuit_breaker("flaky-channel")
        with mock.patch.object(br, "get_state", side_effect=RuntimeError("redis down")):
            assert service_breakers.is_circuit_open("flaky-channel") is False

    def test_is_circuit_open_when_breaker_is_open(self):
        """is_circuit_open returns True when the breaker is in OPEN state."""
        import uuid

        channel = f"open-test-{uuid.uuid4().hex[:8]}"
        br = service_breakers.get_shared_circuit_breaker(
            channel,
            failure_threshold=2,
            testing=False,
        )
        # Drive the breaker to OPEN via failing calls.
        # The first N calls raise RuntimeError; the (N+1)th raises
        # CircuitBreakerError because the circuit opens at threshold.
        from hub.apps.core.resilience.circuit_breaker import CircuitBreakerError

        for _ in range(3):
            with contextlib.suppress(RuntimeError, CircuitBreakerError):
                br.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
        assert service_breakers.is_circuit_open(channel) is True
