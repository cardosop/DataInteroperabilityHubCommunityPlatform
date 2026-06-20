"""
Comprehensive tests for circuit breaker implementation.

Tests cover:
- Circuit breaker states (CLOSED, OPEN, HALF_OPEN)
- State transitions
- Failure threshold and timeout configuration
- Redis-backed state storage
- Thread-safe state management
- Decorator functionality
- Exception handling
- Fallback mechanism integration
"""

import contextlib
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta

import redis
from django.conf import settings
from django.test import TestCase, override_settings

from hub.apps.core.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitBreakerState,
    circuit_breaker,
)


def get_real_redis_client_or_none():
    """Get real Redis client or return None if unavailable."""
    try:
        redis_url = getattr(settings, "REDIS_URL", "redis://redis-cache-test:6379/0")
        client = redis.from_url(
            redis_url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2
        )
        client.ping()
        return client
    except Exception:
        return None


def redis_available():
    """Check if Redis is available."""
    return get_real_redis_client_or_none() is not None


# ============================================================================
# Circuit Breaker State Tests
# ============================================================================


class TestCircuitBreakerState(TestCase):
    """Test circuit breaker state enumeration."""

    def test_state_values(self):
        """Test state enum values."""
        self.assertEqual(CircuitBreakerState.CLOSED.value, "CLOSED")
        self.assertEqual(CircuitBreakerState.OPEN.value, "OPEN")
        self.assertEqual(CircuitBreakerState.HALF_OPEN.value, "HALF_OPEN")

    def test_state_string_representation(self):
        """Test state string representation."""
        self.assertEqual(CircuitBreakerState.CLOSED.value, "CLOSED")
        self.assertEqual(CircuitBreakerState.OPEN.value, "OPEN")
        self.assertEqual(CircuitBreakerState.HALF_OPEN.value, "HALF_OPEN")


# ============================================================================
# Circuit Breaker Base Class Tests
# ============================================================================


class TestCircuitBreakerBase(TestCase):
    """Test circuit breaker base class functionality."""

    @override_settings(REDIS_URL="redis://redis-cache-test:6379/0")
    def setUp(self):
        """Set up test fixtures."""
        self.redis_client = get_real_redis_client_or_none()
        if self.redis_client is None:
            self.skipTest("Redis not available for integration tests")
        self.service_name = f"test_service_{uuid.uuid4().hex[:12]}"
        self.circuit_breaker = CircuitBreaker(
            service_name=self.service_name,
            failure_threshold=5,
            timeout_seconds=60,
            success_threshold=2,
            redis_client=self.redis_client,
        )

    def tearDown(self):
        """Clean up test fixtures."""
        if hasattr(self, "circuit_breaker"):
            with contextlib.suppress(Exception):
                self.circuit_breaker.reset()

    def test_initial_state_is_closed(self):
        """Test circuit breaker starts in CLOSED state."""
        self.assertEqual(self.circuit_breaker.get_state(), CircuitBreakerState.CLOSED)

    def test_default_configuration(self):
        """Test default configuration values."""
        cb = CircuitBreaker(service_name="test")
        self.assertEqual(cb.failure_threshold, 5)
        self.assertEqual(cb.timeout_seconds, 60)
        self.assertEqual(cb.success_threshold, 2)

    def test_custom_configuration(self):
        """Test custom configuration values."""
        cb = CircuitBreaker(
            service_name="test", failure_threshold=10, timeout_seconds=120, success_threshold=3
        )
        self.assertEqual(cb.failure_threshold, 10)
        self.assertEqual(cb.timeout_seconds, 120)
        self.assertEqual(cb.success_threshold, 3)

    def test_call_successful_operation(self):
        """Test calling successful operation."""

        def successful_func():
            return "success"

        result = self.circuit_breaker.call(successful_func)
        self.assertEqual(result, "success")
        self.assertEqual(self.circuit_breaker.get_state(), CircuitBreakerState.CLOSED)

    def test_call_failing_operation(self):
        """Test calling failing operation."""

        def failing_func():
            raise Exception("Service error")

        with self.assertRaises(Exception) as context:
            self.circuit_breaker.call(failing_func)

        self.assertEqual(str(context.exception), "Service error")
        self.assertEqual(self.circuit_breaker.get_state(), CircuitBreakerState.CLOSED)

    def test_state_transition_closed_to_open(self):
        """Test state transition from CLOSED to OPEN after threshold failures."""

        def failing_func():
            raise Exception("Service error")

        # Trigger failures up to threshold
        for _i in range(5):
            with contextlib.suppress(Exception):
                self.circuit_breaker.call(failing_func)

        # Next failure should open circuit
        with self.assertRaises(CircuitBreakerError) as context:
            self.circuit_breaker.call(failing_func)

        self.assertIn("Circuit breaker is OPEN", str(context.exception))
        self.assertEqual(self.circuit_breaker.get_state(), CircuitBreakerState.OPEN)

    def test_state_transition_open_to_half_open_after_timeout(self):
        """Test state transition from OPEN to HALF_OPEN after timeout."""

        def failing_func():
            raise Exception("Service error")

        # Open the circuit
        for _i in range(5):
            with contextlib.suppress(Exception):
                self.circuit_breaker.call(failing_func)

        # Manually set state to OPEN and update timestamp
        self.circuit_breaker._set_state(CircuitBreakerState.OPEN)
        # Set opened_at to past (timeout seconds ago)
        self.circuit_breaker._set_opened_at(datetime.now(UTC) - timedelta(seconds=61))

        # Next call should transition to HALF_OPEN
        def successful_func():
            return "success"

        result = self.circuit_breaker.call(successful_func)
        self.assertEqual(result, "success")
        self.assertEqual(self.circuit_breaker.get_state(), CircuitBreakerState.HALF_OPEN)

    def test_state_transition_half_open_to_closed_on_success(self):
        """Test state transition from HALF_OPEN to CLOSED after success threshold."""

        def successful_func():
            return "success"

        # Set to HALF_OPEN state
        self.circuit_breaker._set_state(CircuitBreakerState.HALF_OPEN)

        # Trigger successes up to threshold
        for _i in range(2):
            result = self.circuit_breaker.call(successful_func)
            self.assertEqual(result, "success")

        # Should transition to CLOSED
        self.assertEqual(self.circuit_breaker.get_state(), CircuitBreakerState.CLOSED)

    def test_state_transition_half_open_to_open_on_failure(self):
        """Test state transition from HALF_OPEN to OPEN on failure."""

        def failing_func():
            raise Exception("Service error")

        # Set to HALF_OPEN state
        self.circuit_breaker._set_state(CircuitBreakerState.HALF_OPEN)

        # Failure should immediately open circuit
        with self.assertRaises(CircuitBreakerError) as context:
            self.circuit_breaker.call(failing_func)

        self.assertIn("Circuit breaker is OPEN", str(context.exception))
        self.assertEqual(self.circuit_breaker.get_state(), CircuitBreakerState.OPEN)

    def test_reset_circuit_breaker(self):
        """Test resetting circuit breaker."""

        # Open the circuit
        def failing_func():
            raise Exception("Service error")

        for _i in range(5):
            with contextlib.suppress(Exception):
                self.circuit_breaker.call(failing_func)

        self.assertEqual(self.circuit_breaker.get_state(), CircuitBreakerState.OPEN)

        # Reset
        self.circuit_breaker.reset()

        # Should be CLOSED
        self.assertEqual(self.circuit_breaker.get_state(), CircuitBreakerState.CLOSED)

        # Should be able to call successfully
        def successful_func():
            return "success"

        result = self.circuit_breaker.call(successful_func)
        self.assertEqual(result, "success")


# ============================================================================
# Redis-Backed State Storage Tests
# ============================================================================


class TestRedisBackedState(TestCase):
    """Test Redis-backed state storage."""

    @override_settings(REDIS_URL="redis://redis-cache-test:6379/0")
    def setUp(self):
        """Set up test fixtures."""
        self.redis_client = get_real_redis_client_or_none()
        if self.redis_client is None:
            self.skipTest("Redis not available for integration tests")
        self.service_name = f"test_service_{uuid.uuid4().hex[:12]}"

    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up Redis keys
        try:
            pattern = f"circuit_breaker:{self.service_name}:*"
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
        except Exception:
            pass

    def test_state_persistence_across_instances(self):
        """Test state persists across different circuit breaker instances."""
        cb1 = CircuitBreaker(service_name=self.service_name, redis_client=self.redis_client)

        # Open circuit with first instance
        def failing_func():
            raise Exception("Service error")

        for _i in range(5):
            with contextlib.suppress(Exception):
                cb1.call(failing_func)

        self.assertEqual(cb1.get_state(), CircuitBreakerState.OPEN)

        # Create second instance - should see same state
        cb2 = CircuitBreaker(service_name=self.service_name, redis_client=self.redis_client)

        self.assertEqual(cb2.get_state(), CircuitBreakerState.OPEN)

        # Reset with second instance
        cb2.reset()

        # First instance should see reset state
        self.assertEqual(cb1.get_state(), CircuitBreakerState.CLOSED)

    def test_failure_count_persistence(self):
        """Test failure count persists across instances."""
        cb1 = CircuitBreaker(
            service_name=self.service_name, failure_threshold=5, redis_client=self.redis_client
        )

        def failing_func():
            raise Exception("Service error")

        # Trigger 3 failures
        for _i in range(3):
            with contextlib.suppress(Exception):
                cb1.call(failing_func)

        # Create second instance
        cb2 = CircuitBreaker(
            service_name=self.service_name, failure_threshold=5, redis_client=self.redis_client
        )

        # Trigger 2 more failures with second instance
        for _i in range(2):
            with contextlib.suppress(Exception):
                cb2.call(failing_func)

        # Next failure should open circuit
        with self.assertRaises(CircuitBreakerError):
            cb2.call(failing_func)

        self.assertEqual(cb2.get_state(), CircuitBreakerState.OPEN)


# ============================================================================
# Thread Safety Tests
# ============================================================================


class TestThreadSafety(TestCase):
    """Test thread-safe state management."""

    @override_settings(REDIS_URL="redis://redis-cache-test:6379/0")
    def setUp(self):
        """Set up test fixtures."""
        self.redis_client = get_real_redis_client_or_none()
        if self.redis_client is None:
            self.skipTest("Redis not available for integration tests")
        self.service_name = f"test_service_{uuid.uuid4().hex[:12]}"
        self.circuit_breaker = CircuitBreaker(
            service_name=self.service_name,
            failure_threshold=10,  # Higher threshold for concurrent tests
            redis_client=self.redis_client,
        )
        self.results = []
        self.lock = threading.Lock()

    def tearDown(self):
        """Clean up test fixtures."""
        if hasattr(self, "circuit_breaker"):
            with contextlib.suppress(Exception):
                self.circuit_breaker.reset()

    def test_concurrent_calls(self):
        """Test concurrent calls to circuit breaker."""

        def successful_func():
            return "success"

        def call_circuit_breaker():
            try:
                result = self.circuit_breaker.call(successful_func)
                with self.lock:
                    self.results.append(result)
            except Exception as e:
                with self.lock:
                    self.results.append(str(e))

        # Create multiple threads
        threads = []
        for _i in range(10):
            thread = threading.Thread(target=call_circuit_breaker)
            threads.append(thread)
            thread.start()

        # Wait for all threads (timeout prevents test from hanging forever)
        for thread in threads:
            thread.join(timeout=30)

        # All should succeed
        self.assertEqual(len(self.results), 10)
        self.assertTrue(all(r == "success" for r in self.results))

    def test_concurrent_failures(self):
        """Test concurrent failures are properly counted."""

        def failing_func():
            raise Exception("Service error")

        def call_circuit_breaker():
            with contextlib.suppress(Exception):
                self.circuit_breaker.call(failing_func)

        # Create multiple threads
        threads = []
        for _i in range(10):
            thread = threading.Thread(target=call_circuit_breaker)
            threads.append(thread)
            thread.start()

        # Wait for all threads (timeout prevents test from hanging forever)
        for thread in threads:
            thread.join(timeout=30)

        # Circuit should be open (10 failures > threshold of 10, so it opens)
        self.assertEqual(self.circuit_breaker.get_state(), CircuitBreakerState.OPEN)


# ============================================================================
# Circuit Breaker Decorator Tests
# ============================================================================


class TestCircuitBreakerDecorator(TestCase):
    """Test circuit breaker decorator."""

    @override_settings(REDIS_URL="redis://redis-cache-test:6379/0")
    def setUp(self):
        """Set up test fixtures."""
        self.redis_client = get_real_redis_client_or_none()
        if self.redis_client is None:
            self.skipTest("Redis not available for integration tests")
        # Use UUID-based suffix for unique service names across tests
        # within the same second, preventing shared-breaker state leakage
        # (the @circuit_breaker decorator now uses get_shared_circuit_breaker
        # which maintains a process-wide _STORE cache).
        self.service_name = f"test_service_{uuid.uuid4().hex[:12]}"

    def tearDown(self):
        """Clean up test fixtures."""
        # Reset shared circuit breaker state so subsequent tests
        # start with a clean slate (process-wide _STORE cache).
        from hub.apps.core.resilience.service_breakers import (
            reset_shared_circuit_breakers_for_service,
        )

        with contextlib.suppress(Exception):
            reset_shared_circuit_breakers_for_service(self.service_name)
        # Clean up Redis keys
        try:
            pattern = f"circuit_breaker:{self.service_name}:*"
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
        except Exception:
            pass

    def test_decorator_successful_call(self):
        """Test decorator with successful call."""

        @circuit_breaker(service_name=self.service_name, redis_client=self.redis_client)
        def test_function():
            return "success"

        result = test_function()
        self.assertEqual(result, "success")

    def test_decorator_failing_call(self):
        """Test decorator with failing call."""

        @circuit_breaker(service_name=self.service_name, redis_client=self.redis_client)
        def test_function():
            raise Exception("Service error")

        with self.assertRaises(Exception) as context:
            test_function()

        self.assertEqual(str(context.exception), "Service error")

    def test_decorator_with_parameters(self):
        """Test decorator with function parameters."""

        @circuit_breaker(service_name=self.service_name, redis_client=self.redis_client)
        def test_function(param1, param2=None):
            return f"{param1}-{param2}"

        result = test_function("value1", param2="value2")
        self.assertEqual(result, "value1-value2")

    def test_decorator_with_kwargs(self):
        """Test decorator with keyword arguments."""

        @circuit_breaker(service_name=self.service_name, redis_client=self.redis_client)
        def test_function(**kwargs):
            return kwargs

        result = test_function(key1="value1", key2="value2")
        self.assertEqual(result, {"key1": "value1", "key2": "value2"})

    def test_decorator_circuit_opens_after_threshold(self):
        """Test decorator opens circuit after threshold failures."""

        @circuit_breaker(
            service_name=self.service_name, failure_threshold=5, redis_client=self.redis_client
        )
        def test_function():
            raise Exception("Service error")

        # Trigger failures
        for _i in range(5):
            with contextlib.suppress(Exception):
                test_function()

        # Next call should raise CircuitBreakerError
        with self.assertRaises(CircuitBreakerError) as context:
            test_function()

        self.assertIn("Circuit breaker is OPEN", str(context.exception))


# ============================================================================
# Fallback Mechanism Tests
# ============================================================================


class TestFallbackMechanism(TestCase):
    """Test fallback mechanism integration."""

    @override_settings(REDIS_URL="redis://redis-cache-test:6379/0")
    def setUp(self):
        """Set up test fixtures."""
        self.redis_client = get_real_redis_client_or_none()
        if self.redis_client is None:
            self.skipTest("Redis not available for integration tests")
        self.service_name = f"test_service_{uuid.uuid4().hex[:12]}"
        self.circuit_breaker = CircuitBreaker(
            service_name=self.service_name, failure_threshold=5, redis_client=self.redis_client
        )

    def tearDown(self):
        """Clean up test fixtures."""
        if hasattr(self, "circuit_breaker"):
            with contextlib.suppress(Exception):
                self.circuit_breaker.reset()

    def test_fallback_on_circuit_open(self):
        """Test fallback is called when circuit is open."""

        def primary_func():
            raise Exception("Service error")

        def fallback_func():
            return "fallback_result"

        # Open circuit
        for _i in range(5):
            with contextlib.suppress(Exception):
                self.circuit_breaker.call(primary_func)

        # Call with fallback
        result = self.circuit_breaker.call(primary_func, fallback=fallback_func)
        self.assertEqual(result, "fallback_result")

    def test_fallback_not_called_on_success(self):
        """Test fallback is not called when primary succeeds."""
        call_count = {"primary": 0, "fallback": 0}

        def primary_func():
            call_count["primary"] += 1
            return "success"

        def fallback_func():
            call_count["fallback"] += 1
            return "fallback"

        result = self.circuit_breaker.call(primary_func, fallback=fallback_func)

        self.assertEqual(result, "success")
        self.assertEqual(call_count["primary"], 1)
        self.assertEqual(call_count["fallback"], 0)

    def test_fallback_on_exception(self):
        """Test fallback is called when failures reach threshold and circuit opens."""

        def primary_func():
            raise Exception("Service error")

        def fallback_func():
            return "fallback_result"

        # Below-threshold failures propagate the real error (by design) so
        # callers can distinguish HTTP 400 from 503, etc.  Drive the breaker
        # to the failure_threshold so the circuit opens and the fallback fires.
        for _ in range(self.circuit_breaker.failure_threshold):
            with self.assertRaises(Exception):
                self.circuit_breaker.call(primary_func)

        # Circuit is now OPEN — next call should use the fallback
        result = self.circuit_breaker.call(primary_func, fallback=fallback_func)
        self.assertEqual(result, "fallback_result")


# ============================================================================
# Integration Tests
# ============================================================================


class TestCircuitBreakerIntegration(TestCase):
    """Integration tests for circuit breaker."""

    @override_settings(REDIS_URL="redis://redis-cache-test:6379/0")
    def setUp(self):
        """Set up test fixtures."""
        self.redis_client = get_real_redis_client_or_none()
        if self.redis_client is None:
            self.skipTest("Redis not available for integration tests")
        self.service_name = f"test_service_{uuid.uuid4().hex[:12]}"

    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up Redis keys
        try:
            pattern = f"circuit_breaker:{self.service_name}:*"
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
        except Exception:
            pass

    def test_complete_cycle_closed_open_half_open_closed(self):
        """Test complete circuit breaker cycle."""
        cb = CircuitBreaker(
            service_name=self.service_name,
            failure_threshold=3,
            timeout_seconds=1,  # Short timeout for testing
            success_threshold=2,
            redis_client=self.redis_client,
        )

        def failing_func():
            raise Exception("Service error")

        def successful_func():
            return "success"

        # Start CLOSED
        self.assertEqual(cb.get_state(), CircuitBreakerState.CLOSED)

        # Trigger failures to OPEN
        for _i in range(3):
            with contextlib.suppress(Exception):
                cb.call(failing_func)

        self.assertEqual(cb.get_state(), CircuitBreakerState.OPEN)

        # Wait for timeout
        time.sleep(1.1)  # noqa: sleep-needed  # INTENTIONAL: test-specific timing requirement

        # Next call should transition to HALF_OPEN
        result = cb.call(successful_func)
        self.assertEqual(result, "success")
        self.assertEqual(cb.get_state(), CircuitBreakerState.HALF_OPEN)

        # Another success should close circuit
        result = cb.call(successful_func)
        self.assertEqual(result, "success")
        self.assertEqual(cb.get_state(), CircuitBreakerState.CLOSED)
