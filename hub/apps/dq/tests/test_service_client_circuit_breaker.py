"""
Comprehensive tests for DQ Service Client circuit breaker integration.

Tests verify:
- Circuit breaker protects run_dq method
- Fallback mechanism returns error response instead of failing
- Circuit breaker state transitions work correctly
- Redis-backed state persistence

Uses a unique service_name per test to isolate Redis state when tests run
in parallel (xdist); otherwise workers share circuit_breaker:dq-service keys
and interfere with each other.
"""
import uuid
from unittest.mock import Mock, patch
from django.conf import settings
from django.test import TestCase

import httpx
import redis

from hub.apps.dq.service_client import DQServiceClient
from hub.apps.core.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerState,
    CircuitBreakerError,
    get_redis_client,
)


def get_real_redis_client_or_none():
    """Get real Redis client or return None if unavailable.
    Uses settings.REDIS_URL so Docker (e.g. redis-cache-test) and local (localhost) work.
    """
    try:
        redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
        client = redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        client.ping()
        return client
    except Exception:
        return None


class TestDQServiceClientCircuitBreaker(TestCase):
    """Test circuit breaker integration with DQ Service Client."""

    def setUp(self):
        """Set up test fixtures."""
        self.redis_client = get_real_redis_client_or_none()
        if self.redis_client is None:
            self.skipTest("Redis not available for integration tests")

        self.service_client = DQServiceClient()
        # Unique service_name per test for parallel isolation (xdist)
        self.service_name = f"dq-service-test-{uuid.uuid4().hex[:12]}"
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
        """Clean up test fixtures (no-op if setUp skipped due to missing Redis)."""
        if getattr(self, "redis_client", None) is None or getattr(
            self, "service_client", None
        ) is None:
            return
        try:
            self.service_client._circuit_breaker.reset()
            pattern = f"circuit_breaker:{self.service_name}:*"
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
        except Exception:
            pass

    def test_circuit_breaker_initialized(self):
        """Test circuit breaker is initialized for DQ service client."""
        # Verify circuit breaker exists
        self.assertTrue(hasattr(self.service_client, '_circuit_breaker'))
        self.assertIsInstance(self.service_client._circuit_breaker, CircuitBreaker)
        self.assertEqual(self.service_client._circuit_breaker.service_name, self.service_name)

    def test_circuit_breaker_configuration(self):
        """Test circuit breaker has correct configuration."""
        cb = self.service_client._circuit_breaker
        self.assertEqual(cb.failure_threshold, 5)
        self.assertEqual(cb.timeout_seconds, 60)
        self.assertEqual(cb.success_threshold, 2)

    def test_run_dq_successful_with_circuit_closed(self):
        """Test run_dq succeeds when circuit is closed."""
        file_content = b"test,data\n1,2"

        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {
            "overall_status": "PASS",
            "quality_score": 0.95,
            "checks": []
        }
        mock_response.raise_for_status = Mock()

        # _request_with_retry uses self.client.send(prepared_request),
        # NOT self.client.request(...).  Patch the actual call path.
        with patch.object(self.service_client.client, 'send', return_value=mock_response):
            result = self.service_client.run_dq(
                file_content=file_content,
                file_format="csv",
                use_cache=False
            )

            self.assertEqual(result["overall_status"], "PASS")
            self.assertEqual(self.service_client._circuit_breaker.get_state(), CircuitBreakerState.CLOSED)

    def test_run_dq_fallback_on_circuit_open(self):
        """Test run_dq uses fallback when circuit is open."""
        file_content = b"test,data\n1,2"

        # Open circuit by triggering failures
        def failing_request(*args, **kwargs):
            raise httpx.RequestError("Service unavailable")

        with patch.object(self.service_client.client, 'send', side_effect=failing_request):
            # Trigger failures to open circuit
            for i in range(5):
                try:
                    self.service_client.run_dq(
                        file_content=file_content,
                        file_format="csv",
                        use_cache=False
                    )
                except (httpx.RequestError, httpx.HTTPStatusError, CircuitBreakerError, ConnectionError):
                    pass  # Expected: service is unavailable, triggering circuit breaker

        # Circuit should be open now
        self.assertEqual(self.service_client._circuit_breaker.get_state(), CircuitBreakerState.OPEN)

        # Next call should use fallback
        result = self.service_client.run_dq(
            file_content=file_content,
            file_format="csv",
            use_cache=False
        )

        # Should return error response, not raise exception
        self.assertEqual(result["overall_status"], "UNKNOWN")
        self.assertEqual(result["quality_score"], 0.0)
        self.assertIn("error", result.get("metadata", {}))

    def test_run_dq_failure_counting(self):
        """Test failures are counted correctly."""
        file_content = b"test,data\n1,2"

        def failing_request(*args, **kwargs):
            raise httpx.RequestError("Service unavailable")

        with patch.object(self.service_client.client, 'send', side_effect=failing_request):
            # Trigger 3 failures
            for i in range(3):
                try:
                    self.service_client.run_dq(
                        file_content=file_content,
                        file_format="csv",
                        use_cache=False
                    )
                except (httpx.RequestError, httpx.HTTPStatusError, CircuitBreakerError, ConnectionError):
                    pass  # Expected: service is unavailable, triggering circuit breaker

            # Circuit should still be closed (threshold is 5)
            self.assertEqual(self.service_client._circuit_breaker.get_state(), CircuitBreakerState.CLOSED)

            # Trigger 2 more failures
            for i in range(2):
                try:
                    self.service_client.run_dq(
                        file_content=file_content,
                        file_format="csv",
                        use_cache=False
                    )
                except (httpx.RequestError, httpx.HTTPStatusError, CircuitBreakerError, ConnectionError):
                    pass  # Expected: service is unavailable, triggering circuit breaker

            # Circuit should now be open
            self.assertEqual(self.service_client._circuit_breaker.get_state(), CircuitBreakerState.OPEN)

    def test_run_dq_circuit_recovery(self):
        """Test circuit breaker recovers after timeout."""
        file_content = b"test,data\n1,2"

        # Open circuit
        def failing_request(*args, **kwargs):
            raise httpx.RequestError("Service unavailable")

        with patch.object(self.service_client.client, 'send', side_effect=failing_request):
            for i in range(5):
                try:
                    self.service_client.run_dq(
                        file_content=file_content,
                        file_format="csv",
                        use_cache=False
                    )
                except (httpx.RequestError, httpx.HTTPStatusError, CircuitBreakerError, ConnectionError):
                    pass  # Expected: service is unavailable, triggering circuit breaker

        self.assertEqual(self.service_client._circuit_breaker.get_state(), CircuitBreakerState.OPEN)

        # Simulate time passage (60s timeout + 1s) so the breaker
        # transitions to HALF_OPEN on the next call.  The circuit
        # breaker uses datetime.now(timezone.utc) internally, not
        # django.utils.timezone.now, so patching the latter would
        # be ineffective.  _set_opened_at is the supported test hook.
        from datetime import datetime, timedelta, timezone

        self.service_client._circuit_breaker._set_opened_at(
            datetime.now(timezone.utc) - timedelta(seconds=61)
        )

        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {
            "overall_status": "PASS",
            "quality_score": 0.95,
            "checks": [],
        }
        mock_response.raise_for_status = Mock()

        with patch.object(self.service_client.client, "send", return_value=mock_response):
            # Should transition to HALF_OPEN
            result = self.service_client.run_dq(
                file_content=file_content,
                file_format="csv",
                use_cache=False,
            )

            self.assertEqual(result["overall_status"], "PASS")
            self.assertEqual(
                self.service_client._circuit_breaker.get_state(),
                CircuitBreakerState.HALF_OPEN,
            )

            # Another success should close circuit
            result = self.service_client.run_dq(
                file_content=file_content,
                file_format="csv",
                use_cache=False,
            )

            self.assertEqual(
                self.service_client._circuit_breaker.get_state(),
                CircuitBreakerState.CLOSED,
            )

    def test_run_dq_fallback_response_structure(self):
        """Test fallback response has correct structure."""
        file_content = b"test,data\n1,2"

        # Open circuit
        def failing_request(*args, **kwargs):
            raise httpx.RequestError("Service unavailable")

        with patch.object(self.service_client.client, 'send', side_effect=failing_request):
            for i in range(5):
                try:
                    self.service_client.run_dq(
                        file_content=file_content,
                        file_format="csv",
                        use_cache=False
                    )
                except (httpx.RequestError, httpx.HTTPStatusError, CircuitBreakerError, ConnectionError):
                    pass  # Expected: service is unavailable, triggering circuit breaker

        # Get fallback response
        result = self.service_client.run_dq(
            file_content=file_content,
            file_format="csv",
            use_cache=False
        )

        # Verify structure
        self.assertIn("overall_status", result)
        self.assertIn("quality_score", result)
        self.assertIn("checks", result)
        self.assertIn("engine_type", result)
        self.assertIn("engine_version", result)
        self.assertIn("profile_key", result)
        self.assertIn("metadata", result)
        self.assertEqual(result["overall_status"], "UNKNOWN")
        self.assertEqual(result["quality_score"], 0.0)
        self.assertEqual(result["checks"], [])

