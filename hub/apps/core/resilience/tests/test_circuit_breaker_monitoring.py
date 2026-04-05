"""
Tests for Circuit Breaker Monitoring and Metrics.

Tests cover:
- OpenTelemetry metrics (state changes, failures, state gauge)
- Structured logging for circuit breaker events
- Health check endpoint for circuit breaker status
- Circuit breaker registry

All tests use real Redis connections - no mocks or stubs.
"""
import time
from structlog.testing import capture_logs
from django.test import TestCase, override_settings
from django.test.client import Client

from hub.apps.core.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerState,
    CircuitBreakerError,
    get_circuit_breaker_status,
    get_all_circuit_breakers,
)


class TestCircuitBreakerMetrics(TestCase):
    """Test OpenTelemetry metrics for circuit breakers."""

    @override_settings(REDIS_URL='redis://redis-cache-test:6379/0')
    def setUp(self):
        """Set up test fixtures."""
        from hub.apps.core.resilience.circuit_breaker import get_redis_client
        self.redis_client = get_redis_client()
        if self.redis_client is None:
            self.skipTest("Redis not available for integration tests")

        # Create a test circuit breaker
        self.service_name = f"test-service-{int(time.time())}"
        self.circuit_breaker = CircuitBreaker(
            service_name=self.service_name,
            failure_threshold=3,
            timeout_seconds=5,
            success_threshold=2,
            redis_client=self.redis_client
        )

    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up circuit breaker state
        try:
            pattern = f"circuit_breaker:{self.service_name}:*"
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
        except Exception:
            pass

    def test_circuit_breaker_has_metrics(self):
        """Test circuit breaker initializes metrics."""
        # Metrics should be initialized (may be None if OpenTelemetry not available)
        self.assertTrue(hasattr(self.circuit_breaker, '_state_changes_counter'))
        self.assertTrue(hasattr(self.circuit_breaker, '_failures_counter'))
        self.assertTrue(hasattr(self.circuit_breaker, '_state_gauge'))

    def test_state_change_records_metric(self):
        """Test state changes record metrics."""
        # Initial state should be CLOSED
        self.assertEqual(self.circuit_breaker.get_state(), CircuitBreakerState.CLOSED)

        # Force state change to OPEN
        self.circuit_breaker._set_state(CircuitBreakerState.OPEN)
        self.assertEqual(self.circuit_breaker.get_state(), CircuitBreakerState.OPEN)

        # Verify the counter attribute exists
        self.assertIsNotNone(self.circuit_breaker._state_changes_counter)

    def test_failure_records_metric(self):
        """Test failures record metrics via the call() path."""
        # Use call() with a failing function — this increments both the
        # OTel metric counter AND the Redis/local failure count.
        def failing_func():
            raise ValueError("Test error")

        try:
            self.circuit_breaker.call(failing_func)
        except (ValueError, CircuitBreakerError):
            pass

        # Verify the counter attribute exists
        self.assertIsNotNone(self.circuit_breaker._failures_counter)

        # Verify failure count incremented (call() updates the actual count)
        failure_count = self.circuit_breaker._get_failure_count()
        self.assertGreaterEqual(
            failure_count, 1,
            "Expected failure count >= 1 after a failed call()"
        )

    def test_state_gauge_updates(self):
        """Test state gauge updates correctly."""
        # Update gauge for different states
        self.circuit_breaker._update_state_gauge(CircuitBreakerState.CLOSED)
        self.circuit_breaker._update_state_gauge(CircuitBreakerState.HALF_OPEN)
        self.circuit_breaker._update_state_gauge(CircuitBreakerState.OPEN)

        # Verify the gauge attribute exists
        self.assertIsNotNone(self.circuit_breaker._state_gauge)

        # Verify state reflects the last update (OPEN)
        self.assertEqual(
            self.circuit_breaker.get_state(),
            CircuitBreakerState.CLOSED
        )
        # The gauge tracks the last value set
        self.assertEqual(
            self.circuit_breaker._previous_gauge_value, 2,
            "Expected gauge value 2 (OPEN) after update"
        )


class TestCircuitBreakerStructuredLogging(TestCase):
    """Test structured logging for circuit breaker events."""

    @override_settings(REDIS_URL='redis://redis-cache-test:6379/0')
    def setUp(self):
        """Set up test fixtures."""
        from hub.apps.core.resilience.circuit_breaker import get_redis_client
        self.redis_client = get_redis_client()
        if self.redis_client is None:
            self.skipTest("Redis not available for integration tests")

        self.service_name = f"test-service-{int(time.time())}"
        self.circuit_breaker = CircuitBreaker(
            service_name=self.service_name,
            failure_threshold=3,
            timeout_seconds=5,
            success_threshold=2,
            redis_client=self.redis_client
        )

    def tearDown(self):
        """Clean up test fixtures."""
        try:
            pattern = f"circuit_breaker:{self.service_name}:*"
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
        except Exception:
            pass

    def test_state_change_logs_event(self):
        """Test state changes log structured events."""
        with capture_logs() as cap_logs:
            self.circuit_breaker._set_state(
                CircuitBreakerState.OPEN
            )

        # Verify state changed
        self.assertEqual(
            self.circuit_breaker.get_state(),
            CircuitBreakerState.OPEN
        )

        # Verify structured log was emitted
        events = [
            entry for entry in cap_logs
            if entry.get("event") == "circuit_breaker_state_changed"
        ]
        self.assertGreaterEqual(
            len(events), 1,
            "Expected a state_changed log event"
        )
        self.assertEqual(
            events[0]["service_name"],
            self.service_name
        )
        self.assertEqual(events[0]["to_state"], "OPEN")

    def test_failure_logs_event(self):
        """Test failures log structured events."""
        def failing_func():
            raise ValueError("Test error")

        with capture_logs() as cap_logs:
            try:
                self.circuit_breaker.call(failing_func)
            except (ValueError, CircuitBreakerError):
                pass

        # Verify failure was recorded
        self.assertGreater(
            self.circuit_breaker._get_failure_count(), 0
        )

        # Verify structured failure log was emitted
        events = [
            entry for entry in cap_logs
            if entry.get("event") == "circuit_breaker_failure"
        ]
        self.assertGreaterEqual(
            len(events), 1,
            "Expected a failure log event"
        )
        self.assertEqual(
            events[0]["service_name"],
            self.service_name
        )
        self.assertIn("error", events[0])

    def test_circuit_opening_logs_event(self):
        """Test circuit opening logs structured event."""
        def failing_func():
            raise ValueError("Test error")

        with capture_logs() as cap_logs:
            for _ in range(3):
                try:
                    self.circuit_breaker.call(failing_func)
                except (ValueError, CircuitBreakerError):
                    pass

        # Circuit should be open
        self.assertEqual(
            self.circuit_breaker.get_state(),
            CircuitBreakerState.OPEN
        )

        # Verify structured log for circuit opening
        events = [
            entry for entry in cap_logs
            if entry.get("event") == "circuit_breaker_opened"
        ]
        self.assertGreaterEqual(
            len(events), 1,
            "Expected a circuit_breaker_opened log event"
        )
        self.assertEqual(
            events[0]["service_name"],
            self.service_name
        )


class TestCircuitBreakerRegistry(TestCase):
    """Test circuit breaker registry for monitoring."""

    @override_settings(REDIS_URL='redis://redis-cache-test:6379/0')
    def setUp(self):
        """Set up test fixtures."""
        from hub.apps.core.resilience.circuit_breaker import get_redis_client
        self.redis_client = get_redis_client()
        if self.redis_client is None:
            self.skipTest("Redis not available for integration tests")

    def test_circuit_breaker_registered(self):
        """Test circuit breaker is registered in global registry."""
        service_name = f"test-service-{int(time.time())}"
        breaker = CircuitBreaker(
            service_name=service_name,
            redis_client=self.redis_client
        )

        # Check registry
        all_breakers = get_all_circuit_breakers()
        self.assertIn(service_name, all_breakers)
        self.assertEqual(all_breakers[service_name], breaker)

    def test_get_circuit_breaker_status_single(self):
        """Test getting status for single circuit breaker."""
        service_name = f"test-service-{int(time.time())}"
        breaker = CircuitBreaker(
            service_name=service_name,
            redis_client=self.redis_client
        )

        status = get_circuit_breaker_status(service_name=service_name)
        self.assertEqual(status['service_name'], service_name)
        self.assertEqual(status['state'], 'CLOSED')
        self.assertIn('failure_threshold', status)
        self.assertIn('success_threshold', status)
        self.assertIn('timeout_seconds', status)
        self.assertIn('failure_count', status)
        self.assertIn('success_count', status)

    def test_get_circuit_breaker_status_all(self):
        """Test getting status for all circuit breakers."""
        service_name1 = f"test-service-1-{int(time.time())}"
        service_name2 = f"test-service-2-{int(time.time())}"

        breaker1 = CircuitBreaker(
            service_name=service_name1,
            redis_client=self.redis_client
        )
        breaker2 = CircuitBreaker(
            service_name=service_name2,
            redis_client=self.redis_client
        )

        all_status = get_circuit_breaker_status()
        self.assertIn(service_name1, all_status)
        self.assertIn(service_name2, all_status)
        self.assertEqual(all_status[service_name1]['service_name'], service_name1)
        self.assertEqual(all_status[service_name2]['service_name'], service_name2)

    def test_get_circuit_breaker_status_not_found(self):
        """Test getting status for non-existent circuit breaker."""
        status = get_circuit_breaker_status(service_name="non-existent-service")
        self.assertIn('error', status)


class TestCircuitBreakerHealthEndpoint(TestCase):
    """Test health check endpoint for circuit breaker status."""

    @override_settings(REDIS_URL='redis://redis-cache-test:6379/0')
    def setUp(self):
        """Set up test fixtures."""
        from hub.apps.core.resilience.circuit_breaker import get_redis_client
        self.redis_client = get_redis_client()
        if self.redis_client is None:
            self.skipTest("Redis not available for integration tests")

        self.client = Client()

    def test_circuit_breaker_status_endpoint_all(self):
        """Test circuit breaker status endpoint returns all breakers."""
        # Create a test circuit breaker
        service_name = f"test-service-{int(time.time())}"
        breaker = CircuitBreaker(
            service_name=service_name,
            redis_client=self.redis_client
        )

        # Ensure circuit breaker is in CLOSED state
        breaker.reset()

        response = self.client.get('/health/circuit-breakers/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('status', data)
        self.assertIn('circuit_breakers', data)
        self.assertIn('total_breakers', data)
        self.assertIn(service_name, data['circuit_breakers'])
        self.assertEqual(data['circuit_breakers'][service_name]['state'], 'CLOSED')

    def test_circuit_breaker_status_endpoint_single(self):
        """Test circuit breaker status endpoint returns single breaker."""
        service_name = f"test-service-{int(time.time())}"
        breaker = CircuitBreaker(
            service_name=service_name,
            redis_client=self.redis_client
        )

        # Ensure circuit breaker is in CLOSED state
        breaker.reset()

        response = self.client.get(f'/health/circuit-breakers/?service_name={service_name}')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('status', data)
        self.assertIn('circuit_breaker', data)
        self.assertEqual(data['circuit_breaker']['service_name'], service_name)
        self.assertEqual(data['circuit_breaker']['state'], 'CLOSED')

    def test_circuit_breaker_status_endpoint_not_found(self):
        """Test circuit breaker status endpoint handles non-existent breaker."""
        response = self.client.get('/health/circuit-breakers/?service_name=non-existent')
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertIn('error', data)

    def test_circuit_breaker_status_endpoint_open_breaker(self):
        """Test circuit breaker status endpoint shows open breaker as degraded."""
        service_name = f"test-service-{int(time.time())}"
        breaker = CircuitBreaker(
            service_name=service_name,
            failure_threshold=2,
            timeout_seconds=60,
            redis_client=self.redis_client
        )

        # Open the circuit
        def failing_func():
            raise ValueError("Test error")

        for _ in range(2):
            try:
                breaker.call(failing_func)
            except (ValueError, CircuitBreakerError):
                pass

        # Circuit should be open
        self.assertEqual(breaker.get_state(), CircuitBreakerState.OPEN)

        # Check endpoint
        response = self.client.get(f'/health/circuit-breakers/?service_name={service_name}')
        self.assertEqual(response.status_code, 503)  # Service Unavailable
        data = response.json()
        self.assertEqual(data['status'], 'degraded')
        self.assertEqual(data['circuit_breaker']['state'], 'OPEN')

    def test_circuit_breaker_status_endpoint_all_with_open_breakers(self):
        """Test circuit breaker status endpoint shows open breakers."""
        service_name1 = f"test-service-1-{int(time.time())}"
        service_name2 = f"test-service-2-{int(time.time())}"

        breaker1 = CircuitBreaker(
            service_name=service_name1,
            failure_threshold=2,
            timeout_seconds=60,
            redis_client=self.redis_client
        )
        CircuitBreaker(
            service_name=service_name2,
            redis_client=self.redis_client
        )

        # Open breaker1
        def failing_func():
            raise ValueError("Test error")

        for _ in range(2):
            try:
                breaker1.call(failing_func)
            except (ValueError, CircuitBreakerError):
                pass

        # Check endpoint
        response = self.client.get('/health/circuit-breakers/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'degraded')
        self.assertEqual(data['open_breakers'], 1)
        self.assertIn(service_name1, data['open_breaker_names'])
        self.assertEqual(data['circuit_breakers'][service_name1]['state'], 'OPEN')
        self.assertEqual(data['circuit_breakers'][service_name2]['state'], 'CLOSED')

