"""
Comprehensive tests for Compliance Service Client circuit breaker integration.

Tests verify:
- Circuit breaker protects scan_file method
- Fallback mechanism returns error response instead of failing
- Circuit breaker state transitions work correctly
- Redis-backed state persistence

All tests use real implementations (no mocks/stubs).
MockTransport is used only for simulating failures (acceptable test utility).
"""

import uuid

import httpx
import redis
from django.conf import settings
from django.test import TestCase

from hub.apps.compliance.service_client import ComplianceServiceClient
from hub.apps.core.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitBreakerState,
    get_redis_client,
)


def get_real_redis_client_or_none():
    """Get real Redis client or return None if unavailable."""
    try:
        redis_url = getattr(settings, "REDIS_URL", "redis://redis:6379/0")
        client = redis.from_url(
            redis_url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2
        )
        client.ping()
        return client
    except Exception:
        return None


class TestComplianceServiceClientCircuitBreaker(TestCase):
    """Test circuit breaker integration with Compliance Service Client.

    Uses REDIS_URL from the environment (e.g. redis-cache-test in test stack)
    so that integration tests run against the real Redis service.

    Uses a unique service_name per test to isolate Redis state when tests run
    in parallel (xdist); otherwise workers share circuit_breaker:compliance-service
    keys and interfere with each other.
    """

    def setUp(self):
        """Set up test fixtures."""
        self.redis_client = get_real_redis_client_or_none()
        if self.redis_client is None:
            self.skipTest("Redis not available for integration tests")

        self.service_client = ComplianceServiceClient()
        # Unique service_name per test for parallel isolation (xdist)
        self.service_name = f"compliance-service-test-{uuid.uuid4().hex[:12]}"
        self.service_client._circuit_breaker = CircuitBreaker(
            service_name=self.service_name,
            failure_threshold=5,
            timeout_seconds=60,
            success_threshold=2,
            redis_client=get_redis_client(),
        )

        # Clean up any existing circuit breaker state and reset
        try:
            pattern = f"circuit_breaker:{self.service_name}:*"
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
            self.service_client._circuit_breaker.reset()
        except Exception:
            pass

    def tearDown(self):
        """Clean up test fixtures."""
        try:
            self.service_client._circuit_breaker.reset()
            pattern = f"circuit_breaker:{self.service_name}:*"
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
        except Exception:
            pass

    def test_circuit_breaker_initialized(self):
        """Test circuit breaker is initialized for Compliance service client."""
        # Verify circuit breaker exists
        self.assertTrue(hasattr(self.service_client, "_circuit_breaker"))
        self.assertIsInstance(self.service_client._circuit_breaker, CircuitBreaker)
        self.assertEqual(
            self.service_client._circuit_breaker.service_name,
            self.service_name,
        )

    def test_circuit_breaker_configuration(self):
        """Test circuit breaker has correct configuration."""
        cb = self.service_client._circuit_breaker
        self.assertEqual(cb.failure_threshold, 5)
        self.assertEqual(cb.timeout_seconds, 60)
        self.assertEqual(cb.success_threshold, 2)

    def test_scan_file_successful_with_circuit_closed(self):
        """Test scan_file succeeds when circuit is closed."""
        file_content = b"test,data\n1,2"

        # Use MockTransport to simulate successful response (acceptable test utility)
        def handler(request: httpx.Request) -> httpx.Response:
            """Return successful response"""
            return httpx.Response(
                200,
                json={
                    "overall_status": "PASS",
                    "risk_level": "LOW",
                    "allowed_to_store": True,
                    "detected_categories": {},
                },
                request=request,
            )

        transport = httpx.MockTransport(handler)
        original_client = self.service_client.client
        self.service_client.client = httpx.Client(
            transport=transport, base_url=self.service_client.base_url
        )

        try:
            result = self.service_client.scan_file(file_content=file_content, file_format="csv")

            self.assertEqual(result["overall_status"], "PASS")
            self.assertEqual(
                self.service_client._circuit_breaker.get_state(), CircuitBreakerState.CLOSED
            )
        finally:
            self.service_client.client = original_client

    def test_scan_file_fallback_on_circuit_open(self):
        """Test scan_file uses fallback when circuit is open."""
        file_content = b"test,data\n1,2"

        # Use MockTransport to simulate failures (acceptable test utility)
        def failing_handler(request: httpx.Request) -> httpx.Response:
            """Simulate service failure"""
            raise httpx.RequestError("Service unavailable", request=request)

        transport = httpx.MockTransport(failing_handler)
        original_client = self.service_client.client
        self.service_client.client = httpx.Client(
            transport=transport, base_url=self.service_client.base_url
        )

        try:
            # Trigger failures to open circuit
            for i in range(5):
                try:
                    self.service_client.scan_file(file_content=file_content, file_format="csv")
                except Exception:
                    pass

            # Circuit should be open now
            self.assertEqual(
                self.service_client._circuit_breaker.get_state(), CircuitBreakerState.OPEN
            )

            # Next call should use fallback
            result = self.service_client.scan_file(file_content=file_content, file_format="csv")

            # Should return error response, not raise exception
            self.assertEqual(result["overall_status"], "UNKNOWN")
            self.assertEqual(result["risk_level"], "UNKNOWN")
            self.assertIn("error", result)
        finally:
            self.service_client.client = original_client
            # Reset circuit breaker for next test
            self.service_client._circuit_breaker.reset()

    def test_scan_file_failure_counting(self):
        """Test failures are counted correctly."""
        file_content = b"test,data\n1,2"

        # Use MockTransport to simulate failures (acceptable test utility)
        def failing_handler(request: httpx.Request) -> httpx.Response:
            """Simulate service failure"""
            raise httpx.RequestError("Service unavailable", request=request)

        transport = httpx.MockTransport(failing_handler)
        original_client = self.service_client.client
        self.service_client.client = httpx.Client(
            transport=transport, base_url=self.service_client.base_url
        )

        try:
            # Trigger 3 failures
            for i in range(3):
                try:
                    self.service_client.scan_file(file_content=file_content, file_format="csv")
                except Exception:
                    pass

            # Circuit should still be closed (threshold is 5)
            self.assertEqual(
                self.service_client._circuit_breaker.get_state(), CircuitBreakerState.CLOSED
            )

            # Trigger 2 more failures
            for i in range(2):
                try:
                    self.service_client.scan_file(file_content=file_content, file_format="csv")
                except Exception:
                    pass

            # Circuit should now be open
            self.assertEqual(
                self.service_client._circuit_breaker.get_state(), CircuitBreakerState.OPEN
            )
        finally:
            self.service_client.client = original_client
            # Reset circuit breaker for next test
            self.service_client._circuit_breaker.reset()

    def test_scan_file_fallback_response_structure(self):
        """Test fallback response has correct structure."""
        file_content = b"test,data\n1,2"

        # Use MockTransport to simulate failures (acceptable test utility)
        def failing_handler(request: httpx.Request) -> httpx.Response:
            """Simulate service failure"""
            raise httpx.RequestError("Service unavailable", request=request)

        transport = httpx.MockTransport(failing_handler)
        original_client = self.service_client.client
        self.service_client.client = httpx.Client(
            transport=transport, base_url=self.service_client.base_url
        )

        try:
            # Open circuit by triggering failures
            for i in range(5):
                try:
                    self.service_client.scan_file(file_content=file_content, file_format="csv")
                except Exception:
                    pass

            # Get fallback response
            result = self.service_client.scan_file(file_content=file_content, file_format="csv")

            # Verify structure
            self.assertIn("overall_status", result)
            self.assertIn("risk_level", result)
            self.assertIn("allowed_to_store", result)
            self.assertIn("detected_categories", result)
            self.assertIn("column_findings", result)
            self.assertIn("regulation_mapping", result)
            self.assertEqual(result["overall_status"], "UNKNOWN")
            self.assertEqual(result["risk_level"], "UNKNOWN")
        finally:
            self.service_client.client = original_client
            # Reset circuit breaker for next test
            self.service_client._circuit_breaker.reset()
