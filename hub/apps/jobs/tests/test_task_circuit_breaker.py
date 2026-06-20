"""
Phase 277.B.072 — RQ task circuit breaker tests.
"""

import contextlib
from unittest.mock import patch

import pytest

from hub.apps.core.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerState,
)
from hub.apps.jobs.task_circuit_breaker import circuit_breaker_guard


class TestCircuitBreakerGuard:
    """Test the circuit_breaker_guard decorator behaviour."""

    def test_guard_allows_execution_when_closed(self):
        """Function runs normally when circuit is closed."""
        call_count = 0

        @circuit_breaker_guard("test_service", failure_threshold=3, timeout_seconds=10)
        def my_task():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = my_task()
        assert result == "ok"
        assert call_count == 1

    def test_guard_skips_when_circuit_open(self):
        """Function returns None without executing when circuit is open."""
        breaker = CircuitBreaker("test_open_service", failure_threshold=1, timeout_seconds=999)
        # Manually open the circuit via internal state mutation
        breaker._set_state(CircuitBreakerState.OPEN)

        with patch(
            "hub.apps.jobs.task_circuit_breaker._get_breaker",
            return_value=breaker,
        ):
            call_count = 0

            @circuit_breaker_guard("test_open_service")
            def my_task():
                nonlocal call_count
                call_count += 1

            result = my_task()
            assert result is None
            assert call_count == 0  # Never executed

    def test_guard_reports_failure_and_re_raises(self):
        """Exception in task → breaker records failure → exception re-raised."""
        breaker = CircuitBreaker("test_fail_service", failure_threshold=3, timeout_seconds=10)

        with patch(
            "hub.apps.jobs.task_circuit_breaker._get_breaker",
            return_value=breaker,
        ):

            @circuit_breaker_guard("test_fail_service")
            def failing_task():
                raise ValueError("downstream error")

            with pytest.raises(ValueError, match="downstream error"):
                failing_task()

            assert breaker._get_failure_count() == 1

    def test_guard_reports_success(self):
        """Successful execution → breaker stays CLOSED with zero failures."""
        breaker = CircuitBreaker("test_success_service", failure_threshold=3, timeout_seconds=10)

        with patch(
            "hub.apps.jobs.task_circuit_breaker._get_breaker",
            return_value=breaker,
        ):

            @circuit_breaker_guard("test_success_service")
            def ok_task():
                return "fine"

            ok_task()
            # In CLOSED state, success resets failure count (stays 0).
            # Success count is only tracked in HALF_OPEN state.
            assert breaker._get_failure_count() == 0
            assert breaker.get_state() == CircuitBreakerState.CLOSED

    def test_guard_opens_after_threshold_failures(self):
        """Repeated failures trip the circuit open."""
        breaker = CircuitBreaker("test_threshold_service", failure_threshold=2, timeout_seconds=999)

        with patch(
            "hub.apps.jobs.task_circuit_breaker._get_breaker",
            return_value=breaker,
        ):

            @circuit_breaker_guard("test_threshold_service", failure_threshold=2)
            def flaky_task():
                raise RuntimeError("boom")

            for _ in range(2):
                with contextlib.suppress(RuntimeError):
                    flaky_task()

            assert breaker.get_state() == CircuitBreakerState.OPEN

            # Third call should skip
            result = flaky_task()
            assert result is None

    def test_guard_half_open_closes_after_successes(self):
        """Half-open circuit closes after success_threshold successes."""
        breaker = CircuitBreaker(
            "test_half_open_service",
            failure_threshold=1,
            timeout_seconds=1,
            success_threshold=2,
        )

        with patch(
            "hub.apps.jobs.task_circuit_breaker._get_breaker",
            return_value=breaker,
        ):

            @circuit_breaker_guard(
                "test_half_open_service",
                failure_threshold=1,
                timeout_seconds=1,
                success_threshold=2,
            )
            def task():
                return "recovered"

            # Trip the breaker by calling with a failing function
            with pytest.raises(ValueError):
                breaker.call(lambda: (_ for _ in ()).throw(ValueError("trip")))

            assert breaker.get_state() == CircuitBreakerState.OPEN

            # Manually set to half-open (simulates timeout expiry)
            breaker._set_state(CircuitBreakerState.HALF_OPEN)
            breaker._reset_success_count()

            # First success after timeout: still half-open (need 2)
            task()
            assert breaker.get_state() == CircuitBreakerState.HALF_OPEN

            # Second success: back to closed
            task()
            assert breaker.get_state() == CircuitBreakerState.CLOSED

    def test_guard_preserves_function_metadata(self):
        """Decorator preserves __name__, __doc__, __module__."""

        @circuit_breaker_guard("test_metadata_service")
        def documented_task(x: int) -> str:
            """Does important work."""
            return str(x)

        assert documented_task.__name__ == "documented_task"
        assert documented_task.__doc__ == "Does important work."

    def test_guard_passes_args_and_kwargs(self):
        """Decorator passes through positional and keyword arguments."""
        captured = {}

        @circuit_breaker_guard("test_args_service")
        def arg_task(a, b, c=3):
            captured["a"] = a
            captured["b"] = b
            captured["c"] = c
            return a + b + c

        result = arg_task(1, 2, c=4)
        assert result == 7
        assert captured == {"a": 1, "b": 2, "c": 4}

    def test_guard_returns_result_unchanged(self):
        """Return value passes through the guard unchanged."""

        @circuit_breaker_guard("test_return_service")
        def data_task():
            return {"status": "processed", "count": 42}

        result = data_task()
        assert result == {"status": "processed", "count": 42}
