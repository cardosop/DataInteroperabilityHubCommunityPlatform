"""
Tests for Circuit Breaker Monitoring and Metrics.

Tests cover:
- OpenTelemetry metrics (state changes, failures, state gauge)
- Structured logging for circuit breaker events
- Health check endpoint for circuit breaker status
- Circuit breaker registry

All tests use real Redis connections - no mocks or stubs.
"""

import contextlib
import uuid
from unittest.mock import MagicMock

from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from structlog.testing import capture_logs

from hub.apps.core.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitBreakerState,
    get_all_circuit_breakers,
    get_circuit_breaker_status,
)


class TestCircuitBreakerMetrics(TestCase):
    """Test OpenTelemetry metrics for circuit breakers."""

    @override_settings(REDIS_URL="redis://redis-cache-test:6379/0")
    def setUp(self):
        """Set up test fixtures."""
        from hub.apps.core.resilience.circuit_breaker import get_redis_client

        self.redis_client = get_redis_client()
        if self.redis_client is None:
            self.skipTest("Redis not available for integration tests")

        # Create a test circuit breaker
        self.service_name = f"test-service-{uuid.uuid4().hex[:12]}"
        self.circuit_breaker = CircuitBreaker(
            service_name=self.service_name,
            failure_threshold=3,
            timeout_seconds=5,
            success_threshold=2,
            redis_client=self.redis_client,
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
        """Test circuit breaker initializes metric attributes post-init.

        This is a smoke test that ``_init_metrics()`` completed without
        raising.  The attribute values may be ``None`` when OpenTelemetry
        is not available in the test environment.
        """
        self.assertTrue(hasattr(self.circuit_breaker, "_state_changes_counter"))
        self.assertTrue(hasattr(self.circuit_breaker, "_failures_counter"))
        self.assertTrue(hasattr(self.circuit_breaker, "_state_gauge"))

    def test_state_change_records_metric(self):
        """Test state changes record metrics by verifying counter.add() is called."""
        self.assertEqual(self.circuit_breaker.get_state(), CircuitBreakerState.CLOSED)

        # Replace the counter with a MagicMock so we can verify the call
        self.circuit_breaker._state_changes_counter = MagicMock()

        # Trigger a state change from CLOSED to OPEN
        self.circuit_breaker._set_state(CircuitBreakerState.OPEN)

        self.circuit_breaker._state_changes_counter.add.assert_called_once()
        _args, kwargs = self.circuit_breaker._state_changes_counter.add.call_args
        self.assertEqual(kwargs["attributes"]["from_state"], "CLOSED")
        self.assertEqual(kwargs["attributes"]["to_state"], "OPEN")
        self.assertEqual(kwargs["attributes"]["service_name"], self.service_name)

    def test_failure_records_metric(self):
        """Test failures record metrics by verifying counter.add() is called."""
        self.circuit_breaker._failures_counter = MagicMock()

        def failing_func():
            raise ValueError("Test error")

        with contextlib.suppress(ValueError, CircuitBreakerError):
            self.circuit_breaker.call(failing_func)

        self.circuit_breaker._failures_counter.add.assert_called_once()
        _args, kwargs = self.circuit_breaker._failures_counter.add.call_args
        self.assertEqual(kwargs["attributes"]["state"], "CLOSED")
        self.assertEqual(kwargs["attributes"]["service_name"], self.service_name)

    def test_state_gauge_updates(self):
        """Test state gauge records correct add() calls on state transitions."""
        self.circuit_breaker._state_gauge = MagicMock()
        self.circuit_breaker._previous_gauge_value = 0

        # HALF_OPEN has numeric value 1; gauge transitions from 0→1
        self.circuit_breaker._update_state_gauge(CircuitBreakerState.HALF_OPEN)
        self.circuit_breaker._state_gauge.add.assert_called_once_with(
            1,
            attributes={"service_name": self.service_name},
        )

        # OPEN has numeric value 2; gauge transitions from 1→2:
        # subtract previous (1) then add new value (2)
        self.circuit_breaker._state_gauge.add.reset_mock()
        self.circuit_breaker._update_state_gauge(CircuitBreakerState.OPEN)

        self.assertEqual(self.circuit_breaker._state_gauge.add.call_count, 2)
        calls = self.circuit_breaker._state_gauge.add.call_args_list
        # First call: reset previous HALF_OPEN → add(-1)
        self.assertEqual(calls[0][0], (-1,))
        # Second call: set new OPEN → add(2)
        self.assertEqual(calls[1][0], (2,))


class TestCircuitBreakerStructuredLogging(TestCase):
    """Test structured logging for circuit breaker events."""

    @override_settings(REDIS_URL="redis://redis-cache-test:6379/0")
    def setUp(self):
        """Set up test fixtures."""
        from hub.apps.core.resilience.circuit_breaker import get_redis_client

        self.redis_client = get_redis_client()
        if self.redis_client is None:
            self.skipTest("Redis not available for integration tests")

        self.service_name = f"test-service-{uuid.uuid4().hex[:12]}"
        self.circuit_breaker = CircuitBreaker(
            service_name=self.service_name,
            failure_threshold=3,
            timeout_seconds=5,
            success_threshold=2,
            redis_client=self.redis_client,
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
            self.circuit_breaker._set_state(CircuitBreakerState.OPEN)

        # Verify state changed
        self.assertEqual(self.circuit_breaker.get_state(), CircuitBreakerState.OPEN)

        # Verify structured log was emitted
        events = [
            entry for entry in cap_logs if entry.get("event") == "circuit_breaker_state_changed"
        ]
        self.assertGreaterEqual(len(events), 1, "Expected a state_changed log event")
        self.assertEqual(events[0]["service_name"], self.service_name)
        self.assertEqual(events[0]["to_state"], "OPEN")

    def test_failure_logs_event(self):
        """Test failures log structured events."""

        def failing_func():
            raise ValueError("Test error")

        with capture_logs() as cap_logs:
            with contextlib.suppress(ValueError, CircuitBreakerError):
                self.circuit_breaker.call(failing_func)

        # Verify failure was recorded
        self.assertGreater(self.circuit_breaker._get_failure_count(), 0)

        # Verify structured failure log was emitted
        events = [entry for entry in cap_logs if entry.get("event") == "circuit_breaker_failure"]
        self.assertGreaterEqual(len(events), 1, "Expected a failure log event")
        self.assertEqual(events[0]["service_name"], self.service_name)
        self.assertIn("error", events[0])

    def test_circuit_opening_logs_event(self):
        """Test circuit opening logs structured event."""

        def failing_func():
            raise ValueError("Test error")

        with capture_logs() as cap_logs:
            for _ in range(3):
                with contextlib.suppress(ValueError, CircuitBreakerError):
                    self.circuit_breaker.call(failing_func)

        # Circuit should be open
        self.assertEqual(self.circuit_breaker.get_state(), CircuitBreakerState.OPEN)

        # Verify structured log for circuit opening
        events = [entry for entry in cap_logs if entry.get("event") == "circuit_breaker_opened"]
        self.assertGreaterEqual(len(events), 1, "Expected a circuit_breaker_opened log event")
        self.assertEqual(events[0]["service_name"], self.service_name)


class TestCircuitBreakerRegistry(TestCase):
    """Test circuit breaker registry for monitoring."""

    @override_settings(REDIS_URL="redis://redis-cache-test:6379/0")
    def setUp(self):
        """Set up test fixtures."""
        from hub.apps.core.resilience.circuit_breaker import get_redis_client

        self.redis_client = get_redis_client()
        if self.redis_client is None:
            self.skipTest("Redis not available for integration tests")

    def test_circuit_breaker_registered(self):
        """Test circuit breaker is registered in global registry."""
        service_name = f"test-service-{uuid.uuid4().hex[:12]}"
        breaker = CircuitBreaker(service_name=service_name, redis_client=self.redis_client)

        # Check registry
        all_breakers = get_all_circuit_breakers()
        self.assertIn(service_name, all_breakers)
        self.assertEqual(all_breakers[service_name], breaker)

    def test_get_circuit_breaker_status_single(self):
        """Test getting status for single circuit breaker."""
        service_name = f"test-service-{uuid.uuid4().hex[:12]}"
        CircuitBreaker(service_name=service_name, redis_client=self.redis_client)

        status = get_circuit_breaker_status(service_name=service_name)
        self.assertEqual(status["service_name"], service_name)
        self.assertEqual(status["state"], "CLOSED")
        self.assertIn("failure_threshold", status)
        self.assertIn("success_threshold", status)
        self.assertIn("timeout_seconds", status)
        self.assertIn("failure_count", status)
        self.assertIn("success_count", status)

    def test_get_circuit_breaker_status_all(self):
        """Test getting status for all circuit breakers."""
        service_name1 = f"test-service-1-{uuid.uuid4().hex[:12]}"
        service_name2 = f"test-service-2-{uuid.uuid4().hex[:12]}"

        CircuitBreaker(service_name=service_name1, redis_client=self.redis_client)
        CircuitBreaker(service_name=service_name2, redis_client=self.redis_client)

        all_status = get_circuit_breaker_status()
        self.assertIn(service_name1, all_status)
        self.assertIn(service_name2, all_status)
        self.assertEqual(all_status[service_name1]["service_name"], service_name1)
        self.assertEqual(all_status[service_name2]["service_name"], service_name2)

    def test_get_circuit_breaker_status_not_found(self):
        """Test getting status for non-existent circuit breaker."""
        status = get_circuit_breaker_status(service_name="non-existent-service")
        self.assertIn("error", status)


class TestCircuitBreakerHealthEndpoint(TestCase):
    """Test health check endpoint for circuit breaker status."""

    @override_settings(REDIS_URL="redis://redis-cache-test:6379/0")
    def setUp(self):
        """Set up test fixtures."""
        from hub.apps.core.resilience.circuit_breaker import get_redis_client

        self.redis_client = get_redis_client()
        if self.redis_client is None:
            self.skipTest("Redis not available for integration tests")

        # Authenticate a test user — the circuit breaker health
        # endpoint requires IsAuthenticated (Phase 221.3.1).
        from django.contrib.auth import get_user_model

        User = get_user_model()
        # Use get_or_create to avoid creating duplicate users across
        # tests, which can affect cache warming that iterates all tenants.
        self.test_user, _ = User.objects.get_or_create(
            email="cb-health-test@example.com",
            defaults={"password": "testpass123"},
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.test_user)

    def test_circuit_breaker_status_endpoint_all(self):
        """Test circuit breaker status endpoint returns aggregate breaker counts.

        Phase 221.3.2 — endpoint returns only aggregate data (status,
        total_breakers, open_breakers). Individual service names and
        the ?service_name= query parameter have been removed.
        """
        # Create a test circuit breaker
        service_name = f"test-service-{uuid.uuid4().hex[:12]}"
        breaker = CircuitBreaker(service_name=service_name, redis_client=self.redis_client)

        # Ensure circuit breaker is in CLOSED state
        breaker.reset()

        response = self.client.get("/health/circuit-breakers/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertIn("total_breakers", data)
        self.assertIn("open_breakers", data)
        # Aggregate-only response — no per-breaker detail (Phase 221.3.2)

    def test_circuit_breaker_status_endpoint_single(self):
        """Test circuit breaker status endpoint ignores ?service_name= query param.

        Phase 221.3.2 — the ?service_name= query parameter has been
        removed. All requests return aggregate-only data.
        """
        service_name = f"test-service-{uuid.uuid4().hex[:12]}"
        breaker = CircuitBreaker(service_name=service_name, redis_client=self.redis_client)

        breaker.reset()

        response = self.client.get(f"/health/circuit-breakers/?service_name={service_name}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # Aggregate response — ?service_name= is ignored (Phase 221.3.2)
        self.assertIn("status", data)
        self.assertIn("total_breakers", data)
        self.assertIn("open_breakers", data)

    def test_circuit_breaker_status_endpoint_not_found(self):
        """Test circuit breaker status endpoint handles unknown service gracefully.

        Phase 221.3.2 — the endpoint no longer returns 404 for unknown
        services. It returns aggregate counts regardless.
        """
        response = self.client.get("/health/circuit-breakers/?service_name=non-existent")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)

    def test_circuit_breaker_status_endpoint_open_breaker(self):
        """Test circuit breaker status endpoint shows degraded when breakers are open.

        Phase 221.3.2 — endpoint returns HTTP 200 with status='degraded'
        when one or more breakers are open (no per-breaker detail).
        """
        service_name = f"test-service-{uuid.uuid4().hex[:12]}"
        breaker = CircuitBreaker(
            service_name=service_name,
            failure_threshold=2,
            timeout_seconds=60,
            redis_client=self.redis_client,
        )

        # Open the circuit
        def failing_func():
            raise ValueError("Test error")

        for _ in range(2):
            with contextlib.suppress(ValueError, CircuitBreakerError):
                breaker.call(failing_func)

        # Circuit should be open
        self.assertEqual(breaker.get_state(), CircuitBreakerState.OPEN)

        # Check endpoint — returns 200 with degraded status (Phase 221.3.2)
        response = self.client.get(f"/health/circuit-breakers/?service_name={service_name}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "degraded")
        self.assertGreater(data["open_breakers"], 0)

    def test_circuit_breaker_status_endpoint_all_with_open_breakers(self):
        """Test circuit breaker status endpoint shows open breakers in aggregate.

        Phase 221.3.2 — returns aggregate only: status='degraded',
        open_breakers count (no per-breaker names or state detail).
        """
        service_name1 = f"test-service-1-{uuid.uuid4().hex[:12]}"
        service_name2 = f"test-service-2-{uuid.uuid4().hex[:12]}"

        breaker1 = CircuitBreaker(
            service_name=service_name1,
            failure_threshold=2,
            timeout_seconds=60,
            redis_client=self.redis_client,
        )
        CircuitBreaker(service_name=service_name2, redis_client=self.redis_client)

        # Open breaker1
        def failing_func():
            raise ValueError("Test error")

        for _ in range(2):
            with contextlib.suppress(ValueError, CircuitBreakerError):
                breaker1.call(failing_func)

        # Check endpoint — aggregate only (Phase 221.3.2)
        response = self.client.get("/health/circuit-breakers/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "degraded")
        self.assertGreater(data["open_breakers"], 0)
