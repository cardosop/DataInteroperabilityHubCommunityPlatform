"""
Comprehensive tests for DataContract CLI Client circuit breaker integration.

Tests verify:
- Circuit breaker protects validate method
- Fallback mechanism returns error response instead of failing
- Circuit breaker state transitions work correctly
- Redis-backed state persistence
- 30-second timeout configuration
"""
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from django.test import TestCase, override_settings
from django.conf import settings

import httpx
import redis

from hub.apps.contracts.cli_client import DataContractCLIClient
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


class TestDataContractCLIClientCircuitBreaker(TestCase):
    """Test circuit breaker integration with DataContract CLI Client."""

    @override_settings(REDIS_URL='redis://redis:6379/0')
    def setUp(self):
        """Set up test fixtures."""
        self.redis_client = get_real_redis_client_or_none()
        if self.redis_client is None:
            self.skipTest("Redis not available for integration tests")

        self.service_client = DataContractCLIClient()
        self.service_name = "datacontract-service"

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
        """Test circuit breaker is initialized for DataContract CLI client."""
        # Verify circuit breaker exists
        self.assertTrue(hasattr(self.service_client, '_circuit_breaker'))
        self.assertIsInstance(self.service_client._circuit_breaker, CircuitBreaker)
        self.assertEqual(self.service_client._circuit_breaker.service_name, self.service_name)

    def test_circuit_breaker_configuration(self):
        """Test circuit breaker has correct configuration (30-second timeout)."""
        cb = self.service_client._circuit_breaker
        self.assertEqual(cb.failure_threshold, 5)
        self.assertEqual(cb.timeout_seconds, 30)  # 30 seconds as specified
        self.assertEqual(cb.success_threshold, 2)

    def test_validate_successful_with_circuit_closed(self):
        """Test validate succeeds when circuit is closed."""
        raw_contract = '{"version": "1.0", "name": "test"}'

        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {
            "validation_status": "PASS",
            "issues": [],
            "cli_version": "1.0.0"
        }
        mock_response.raise_for_status = Mock()

        with patch('httpx.Client') as mock_client_class:
            mock_client = Mock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__enter__.return_value = mock_client

            result = self.service_client.validate(
                raw_contract=raw_contract,
                format="json",
                use_cache=False
            )

            self.assertEqual(result["validation_status"], "PASS")
            self.assertEqual(self.service_client._circuit_breaker.get_state(), CircuitBreakerState.CLOSED)

    def test_validate_fallback_on_circuit_open(self):
        """Test validate uses fallback when circuit is open."""
        raw_contract = '{"version": "1.0", "name": "test"}'

        # Open circuit by triggering failures
        def failing_request(*args, **kwargs):
            raise httpx.RequestError("Service unavailable")

        with patch('httpx.Client') as mock_client_class:
            mock_client = Mock()
            mock_client.post.side_effect = failing_request
            mock_client_class.return_value.__enter__.return_value = mock_client

            # Trigger failures to open circuit
            for i in range(5):
                try:
                    self.service_client.validate(
                        raw_contract=raw_contract,
                        format="json",
                        use_cache=False
                    )
                except Exception:
                    pass

        # Circuit should be open now
        self.assertEqual(self.service_client._circuit_breaker.get_state(), CircuitBreakerState.OPEN)

        # Next call should use fallback
        result = self.service_client.validate(
            raw_contract=raw_contract,
            format="json",
            use_cache=False
        )

        # Should return error response, not raise exception
        self.assertEqual(result["validation_status"], "ERROR")
        self.assertIn("error", result)

    def test_validate_fallback_response_structure(self):
        """Test fallback response has correct structure."""
        raw_contract = '{"version": "1.0", "name": "test"}'

        # Open circuit
        def failing_request(*args, **kwargs):
            raise httpx.RequestError("Service unavailable")

        with patch('httpx.Client') as mock_client_class:
            mock_client = Mock()
            mock_client.post.side_effect = failing_request
            mock_client_class.return_value.__enter__.return_value = mock_client

            for i in range(5):
                try:
                    self.service_client.validate(
                        raw_contract=raw_contract,
                        format="json",
                        use_cache=False
                    )
                except Exception:
                    pass

        # Get fallback response
        result = self.service_client.validate(
            raw_contract=raw_contract,
            format="json",
            use_cache=False
        )

        # Verify structure
        self.assertIn("validation_status", result)
        self.assertIn("issues", result)
        self.assertEqual(result["validation_status"], "ERROR")
        self.assertEqual(result["issues"], [])

