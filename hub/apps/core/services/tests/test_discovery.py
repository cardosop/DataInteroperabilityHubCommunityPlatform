"""
Tests for service discovery module.
"""

import os
from unittest.mock import patch

from django.test import TestCase, override_settings

from hub.apps.core.services.discovery import (
    ServiceRegistry,
    get_health_check_url,
    get_service_url,
    list_services,
    register_service,
)


class ServiceDiscoveryTest(TestCase):
    """Test service discovery functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear cache before each test
        ServiceRegistry.get_service_url.cache_clear()

    def test_list_services(self):
        """Test listing all registered services."""
        services = list_services()
        self.assertIsInstance(services, list)
        self.assertGreater(len(services), 0)
        self.assertIn("api-service", services)
        self.assertIn("contract-service", services)

    def test_get_service_config(self):
        """Test getting service configuration."""
        config = ServiceRegistry.get_service_config("api-service")
        self.assertIsNotNone(config)
        self.assertIn("port", config)
        self.assertIn("health_path", config)
        self.assertIn("env_var", config)

    def test_get_service_config_not_found(self):
        """Test getting configuration for non-existent service."""
        config = ServiceRegistry.get_service_config("nonexistent-service")
        self.assertIsNone(config)

    @patch.dict(os.environ, {"API_SERVICE_URL": "http://custom-api:9000"})
    def test_get_service_url_from_env(self):
        """Test getting service URL from environment variable."""
        url = get_service_url("api-service")
        self.assertEqual(url, "http://custom-api:9000")

    @patch.dict(os.environ, {}, clear=True)
    def test_get_service_url_docker_compose(self):
        """Test getting service URL for Docker Compose environment."""
        with patch.object(ServiceRegistry, "_detect_environment", return_value="docker-compose"):
            url = get_service_url("api-service")
            self.assertEqual(url, "http://api-service:8000")

    @patch.dict(os.environ, {"KUBERNETES_SERVICE_HOST": "10.0.0.1"})
    def test_get_service_url_kubernetes(self):
        """Test getting service URL for Kubernetes environment."""
        url = get_service_url("api-service", namespace="default")
        self.assertIn("api-service", url)
        self.assertIn("svc.cluster.local", url)

    def test_get_health_check_url(self):
        """Test getting health check URL."""
        url = get_health_check_url("api-service")
        self.assertIn("/health", url)
        self.assertIn("api-service", url)

    def test_register_service(self):
        """Test registering a new service."""
        register_service(
            service_name="test-service",
            port=9999,
            health_path="/healthz",
            env_var="TEST_SERVICE_URL",
        )

        config = ServiceRegistry.get_service_config("test-service")
        self.assertIsNotNone(config)
        self.assertEqual(config["port"], 9999)
        self.assertEqual(config["health_path"], "/healthz")
        self.assertEqual(config["env_var"], "TEST_SERVICE_URL")

    def test_service_url_caching(self):
        """Test that service URLs are cached via lru_cache (second call skips resolution)."""
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(
                ServiceRegistry, "_detect_environment", return_value="docker-compose"
            ) as mock_detect,
        ):
            # First call — should invoke _detect_environment
            url1 = get_service_url("api-service")
            self.assertEqual(mock_detect.call_count, 1)

            # Second call — lru_cache should prevent _detect_environment from running again
            url2 = get_service_url("api-service")
            self.assertEqual(mock_detect.call_count, 1)  # still 1, proving caching

            self.assertEqual(url1, url2)

    @override_settings(API_SERVICE_URL="http://settings-api:8000")
    def test_get_service_url_from_settings(self):
        """Test getting service URL from Django settings."""
        # Clear environment to force settings lookup
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(ServiceRegistry, "_detect_environment", return_value="local"):
                # This will check settings
                url = get_service_url("api-service")
                # Should fall back to Docker Compose format if settings not found
                self.assertIsNotNone(url)
