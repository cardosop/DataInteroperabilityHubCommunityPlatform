"""
Comprehensive tests for Compliance Service Client circuit breaker integration.

Tests verify:
- Circuit breaker protects scan_file method
- Fallback mechanism returns error response instead of failing
- Circuit breaker state transitions work correctly
- Redis-backed state persistence
"""
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from django.test import TestCase, override_settings
from django.conf import settings

import httpx
import redis

from hub.apps.compliance.service_client import ComplianceServiceClient
from hub.apps.core.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerState,
    CircuitBreakerError,
)


def get_real_redis_client_or_none():
    """Get real Redis client or return None if unavailable."""
    try:
        redis_url = getattr(settings, 'REDIS_URL', 'redis://redis:6379/0')
        client = redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2
        )
        client.ping()
        return client
    except Exception:
        return None


class TestComplianceServiceClientCircuitBreaker(TestCase):
    """Test circuit breaker integration with Compliance Service Client."""

    @override_settings(REDIS_URL='redis://redis:6379/0')
    def setUp(self):
        """Set up test fixtures."""
        self.redis_client = get_real_redis_client_or_none()
        if self.redis_client is None:
            self.skipTest("Redis not available for integration tests")

        self.service_client = ComplianceServiceClient()
        self.service_name = "compliance-service"

        # Clean up any existing circuit breaker state and reset
        try:
            pattern = f"circuit_breaker:{self.service_name}:*"
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
            # Explicitly reset circuit breaker to ensure clean state
            self.service_client._circuit_breaker.reset()
        except Exception:
            pass

    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up circuit breaker state and reset
        try:
            # Explicitly reset circuit breaker first
            self.service_client._circuit_breaker.reset()
            # Then clean up Redis keys
            pattern = f"circuit_breaker:{self.service_name}:*"
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
        except Exception:
            pass

    def test_circuit_breaker_initialized(self):
        """Test circuit breaker is initialized for Compliance service client."""
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

    def test_scan_file_successful_with_circuit_closed(self):
        """Test scan_file succeeds when circuit is closed."""
        file_content = b"test,data\n1,2"

        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {
            "overall_status": "PASS",
            "risk_level": "LOW",
            "allowed_to_store": True,
            "detected_categories": {}
        }
        mock_response.raise_for_status = Mock()

        with patch.object(self.service_client.client, 'request', return_value=mock_response):
            result = self.service_client.scan_file(
                file_content=file_content,
                file_format="csv"
            )

            self.assertEqual(result["overall_status"], "PASS")
            self.assertEqual(self.service_client._circuit_breaker.get_state(), CircuitBreakerState.CLOSED)

    def test_scan_file_fallback_on_circuit_open(self):
        """Test scan_file uses fallback when circuit is open."""
        file_content = b"test,data\n1,2"

        # Open circuit by triggering failures
        def failing_request(*args, **kwargs):
            raise httpx.RequestError("Service unavailable")

        with patch.object(self.service_client.client, 'request', side_effect=failing_request):
            # Trigger failures to open circuit
            for i in range(5):
                try:
                    self.service_client.scan_file(
                        file_content=file_content,
                        file_format="csv"
                    )
                except Exception:
                    pass

        # Circuit should be open now
        self.assertEqual(self.service_client._circuit_breaker.get_state(), CircuitBreakerState.OPEN)

        # Next call should use fallback
        result = self.service_client.scan_file(
            file_content=file_content,
            file_format="csv"
        )

        # Should return error response, not raise exception
        self.assertEqual(result["overall_status"], "UNKNOWN")
        self.assertEqual(result["risk_level"], "UNKNOWN")
        self.assertIn("error", result)

    def test_scan_file_failure_counting(self):
        """Test failures are counted correctly."""
        file_content = b"test,data\n1,2"

        def failing_request(*args, **kwargs):
            raise httpx.RequestError("Service unavailable")

        with patch.object(self.service_client.client, 'request', side_effect=failing_request):
            # Trigger 3 failures
            for i in range(3):
                try:
                    self.service_client.scan_file(
                        file_content=file_content,
                        file_format="csv"
                    )
                except Exception:
                    pass

            # Circuit should still be closed (threshold is 5)
            self.assertEqual(self.service_client._circuit_breaker.get_state(), CircuitBreakerState.CLOSED)

            # Trigger 2 more failures
            for i in range(2):
                try:
                    self.service_client.scan_file(
                        file_content=file_content,
                        file_format="csv"
                    )
                except Exception:
                    pass

            # Circuit should now be open
            self.assertEqual(self.service_client._circuit_breaker.get_state(), CircuitBreakerState.OPEN)

    def test_scan_file_fallback_response_structure(self):
        """Test fallback response has correct structure."""
        file_content = b"test,data\n1,2"

        # Open circuit
        def failing_request(*args, **kwargs):
            raise httpx.RequestError("Service unavailable")

        with patch.object(self.service_client.client, 'request', side_effect=failing_request):
            for i in range(5):
                try:
                    self.service_client.scan_file(
                        file_content=file_content,
                        file_format="csv"
                    )
                except Exception:
                    pass

        # Get fallback response
        result = self.service_client.scan_file(
            file_content=file_content,
            file_format="csv"
        )

        # Verify structure
        self.assertIn("overall_status", result)
        self.assertIn("risk_level", result)
        self.assertIn("allowed_to_store", result)
        self.assertIn("detected_categories", result)
        self.assertIn("column_findings", result)
        self.assertIn("regulation_mapping", result)
        self.assertEqual(result["overall_status"], "UNKNOWN")
        self.assertEqual(result["risk_level"], "UNKNOWN")

