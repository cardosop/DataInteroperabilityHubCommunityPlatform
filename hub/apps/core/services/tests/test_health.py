"""
Tests for service health check utilities.
"""

from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase

from hub.apps.core.services.health import (
    ServiceHealthCheck,
    ServiceHealthMonitor,
    check_all_services_health,
    check_service_health,
    is_service_healthy,
)


def _make_httpx_client_mock(mock_client_class, status_code=200, json_data=None, side_effect=None):
    """Helper: configure an httpx.Client mock and return the inner client mock."""
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=None)

    if side_effect is not None:
        mock_client.get.side_effect = side_effect
    else:
        mock_response = MagicMock()
        mock_response.status_code = status_code
        mock_response.json.return_value = json_data or {}
        mock_client.get.return_value = mock_response

    mock_client_class.return_value = mock_client
    return mock_client


class ServiceHealthCheckTest(TestCase):
    """Test service health check functionality."""

    def setUp(self):
        """Set up test fixtures."""
        cache.clear()

    @patch("httpx.Client")
    def test_check_health_healthy(self, mock_client_class):
        """Test health check for healthy service."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "healthy"}

        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        health_check = ServiceHealthCheck("api-service", timeout=5.0)
        result = health_check.check_health(use_cache=False)

        self.assertEqual(result["status"], "healthy")
        self.assertIsNotNone(result["latency_ms"])
        self.assertIsNone(result["error"])

    @patch("httpx.Client")
    def test_check_health_unhealthy(self, mock_client_class):
        """Test health check for unhealthy service."""
        mock_response = MagicMock()
        mock_response.status_code = 503

        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        health_check = ServiceHealthCheck("api-service", timeout=5.0)
        result = health_check.check_health(use_cache=False)

        self.assertEqual(result["status"], "unhealthy")
        self.assertIsNotNone(result["error"])

    @patch("httpx.Client")
    def test_check_health_timeout(self, mock_client_class):
        """Test health check timeout handling."""
        import httpx

        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client.get.side_effect = httpx.TimeoutException("Timeout")
        mock_client_class.return_value = mock_client

        health_check = ServiceHealthCheck("api-service", timeout=5.0)
        result = health_check.check_health(use_cache=False)

        self.assertEqual(result["status"], "unhealthy")
        self.assertEqual(result["error"], "Timeout")

    @patch("httpx.Client")
    def test_check_health_cache(self, mock_client_class):
        """Test health check caching."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "healthy"}

        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        health_check = ServiceHealthCheck("api-service", timeout=5.0, cache_ttl=60)

        # First call - should make HTTP request
        result1 = health_check.check_health(use_cache=True)
        self.assertEqual(mock_client.get.call_count, 1)

        # Second call - should use cache
        result2 = health_check.check_health(use_cache=True)
        self.assertEqual(mock_client.get.call_count, 1)  # Still 1, not 2
        self.assertEqual(result1["status"], result2["status"])

    @patch("httpx.Client")
    def test_is_healthy(self, mock_client_class):
        """Test is_healthy convenience method."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        health_check = ServiceHealthCheck("api-service", timeout=5.0)
        is_healthy = health_check.is_healthy(use_cache=False)

        self.assertTrue(is_healthy)


class ServiceHealthMonitorTest(TestCase):
    """Test service health monitor functionality."""

    def setUp(self):
        """Set up test fixtures."""
        cache.clear()

    @patch("httpx.Client")
    def test_check_all_services(self, mock_client_class):
        """Test checking health of all services — real monitor with HTTP mocked."""
        _make_httpx_client_mock(mock_client_class, status_code=200, json_data={"status": "healthy"})

        monitor = ServiceHealthMonitor()
        results = monitor.check_all_services(service_names=["api-service"], use_cache=False)

        self.assertIn("api-service", results)
        self.assertEqual(results["api-service"]["status"], "healthy")
        self.assertIsNotNone(results["api-service"]["latency_ms"])

    @patch("httpx.Client")
    def test_get_healthy_services(self, mock_client_class):
        """Test getting list of healthy services — real monitor with HTTP mocked."""
        call_count = {"n": 0}
        healthy_response = MagicMock()
        healthy_response.status_code = 200
        healthy_response.json.return_value = {"status": "healthy"}

        unhealthy_response = MagicMock()
        unhealthy_response.status_code = 503

        def get_side_effect(url, **kwargs):
            call_count["n"] += 1
            if "api-service" in url:
                return healthy_response
            return unhealthy_response

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=None)
        mock_client.get.side_effect = get_side_effect
        mock_client_class.return_value = mock_client

        monitor = ServiceHealthMonitor()
        healthy_services = monitor.get_healthy_services(
            service_names=["api-service", "unhealthy-service"], use_cache=False
        )

        self.assertIn("api-service", healthy_services)
        self.assertNotIn("unhealthy-service", healthy_services)
        # Verify actual HTTP calls were made (not just mock plumbing)
        self.assertEqual(call_count["n"], 2)

    @patch("httpx.Client")
    def test_get_unhealthy_services(self, mock_client_class):
        """Test getting list of unhealthy services — real monitor with HTTP mocked."""
        healthy_response = MagicMock()
        healthy_response.status_code = 200
        healthy_response.json.return_value = {"status": "healthy"}

        unhealthy_response = MagicMock()
        unhealthy_response.status_code = 503

        def get_side_effect(url, **kwargs):
            if "api-service" in url:
                return healthy_response
            return unhealthy_response

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=None)
        mock_client.get.side_effect = get_side_effect
        mock_client_class.return_value = mock_client

        monitor = ServiceHealthMonitor()
        unhealthy_services = monitor.get_unhealthy_services(
            service_names=["api-service", "unhealthy-service"], use_cache=False
        )

        self.assertNotIn("api-service", unhealthy_services)
        self.assertIn("unhealthy-service", unhealthy_services)


class ServiceHealthConvenienceFunctionsTest(TestCase):
    """Test convenience functions for service health checks."""

    def setUp(self):
        """Set up test fixtures."""
        cache.clear()

    @patch("httpx.Client")
    def test_check_service_health(self, mock_client_class):
        """Test check_service_health convenience function exercises real ServiceHealthCheck."""
        _make_httpx_client_mock(mock_client_class, status_code=200, json_data={"status": "healthy"})

        result = check_service_health("api-service", use_cache=False)

        self.assertEqual(result["status"], "healthy")
        self.assertEqual(result["service"], "api-service")
        self.assertIsNotNone(result["latency_ms"])
        self.assertIsNone(result["error"])

    @patch("httpx.Client")
    def test_check_service_health_unhealthy(self, mock_client_class):
        """Test check_service_health reports unhealthy on HTTP 503."""
        _make_httpx_client_mock(mock_client_class, status_code=503)

        result = check_service_health("api-service", use_cache=False)

        self.assertEqual(result["status"], "unhealthy")
        self.assertIn("503", result["error"])

    @patch("httpx.Client")
    def test_is_service_healthy(self, mock_client_class):
        """Test is_service_healthy exercises real ServiceHealthCheck and returns True on 200."""
        _make_httpx_client_mock(mock_client_class, status_code=200)

        is_healthy = is_service_healthy("api-service", use_cache=False)

        self.assertTrue(is_healthy)

    @patch("httpx.Client")
    def test_is_service_healthy_false(self, mock_client_class):
        """Test is_service_healthy returns False on non-200 response."""
        _make_httpx_client_mock(mock_client_class, status_code=500)

        is_healthy = is_service_healthy("api-service", use_cache=False)

        self.assertFalse(is_healthy)

    @patch("httpx.Client")
    def test_check_all_services_health(self, mock_client_class):
        """Test check_all_services_health exercises real ServiceHealthMonitor."""
        _make_httpx_client_mock(mock_client_class, status_code=200, json_data={"status": "healthy"})

        results = check_all_services_health(service_names=["api-service"], use_cache=False)

        self.assertIn("api-service", results)
        self.assertEqual(results["api-service"]["status"], "healthy")
        self.assertIsNotNone(results["api-service"]["latency_ms"])
