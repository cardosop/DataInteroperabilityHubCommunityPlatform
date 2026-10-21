"""
Integration tests for service-to-service communication.

Tests service client functionality including timeouts, retries, and error handling.
"""

from unittest.mock import MagicMock, patch

import httpx
from django.test import TestCase, override_settings

from hub.apps.core.services.base import NotFoundError, ServiceError
from hub.apps.core.services.cross_service_access import (
    CachedServiceClient,
    RetryStrategy,
    ServiceClient,
    ServiceCommunicationConfig,
)


class ServiceCommunicationConfigTest(TestCase):
    """Test service communication configuration."""

    def test_get_timeout_default(self):
        """Test getting default timeout."""
        timeout = ServiceCommunicationConfig.get_timeout()
        self.assertEqual(timeout, ServiceCommunicationConfig.DEFAULT_TIMEOUT)

    @override_settings(SERVICE_COMMUNICATION_TIMEOUT=60.0)
    def test_get_timeout_from_settings(self):
        """Test getting timeout from Django settings."""
        timeout = ServiceCommunicationConfig.get_timeout()
        self.assertEqual(timeout, 60.0)

    @override_settings(API_SERVICE_TIMEOUT=45.0)
    def test_get_timeout_service_specific(self):
        """Test getting service-specific timeout."""
        timeout = ServiceCommunicationConfig.get_timeout("api-service")
        self.assertEqual(timeout, 45.0)

    def test_get_retry_count_default(self):
        """Test getting default retry count."""
        retry_count = ServiceCommunicationConfig.get_retry_count()
        self.assertEqual(retry_count, ServiceCommunicationConfig.DEFAULT_RETRY_COUNT)

    @override_settings(SERVICE_COMMUNICATION_RETRY_COUNT=5)
    def test_get_retry_count_from_settings(self):
        """Test getting retry count from Django settings."""
        retry_count = ServiceCommunicationConfig.get_retry_count()
        self.assertEqual(retry_count, 5)

    def test_get_retry_strategy_default(self):
        """Test getting default retry strategy."""
        strategy = ServiceCommunicationConfig.get_retry_strategy()
        self.assertEqual(strategy, RetryStrategy.EXPONENTIAL_BACKOFF)

    @override_settings(SERVICE_COMMUNICATION_RETRY_STRATEGY="linear_backoff")
    def test_get_retry_strategy_from_settings(self):
        """Test getting retry strategy from Django settings."""
        strategy = ServiceCommunicationConfig.get_retry_strategy()
        self.assertEqual(strategy, RetryStrategy.LINEAR_BACKOFF)

    def test_should_retry_retryable_status(self):
        """Test should_retry for retryable status codes."""
        self.assertTrue(ServiceCommunicationConfig.should_retry(500))
        self.assertTrue(ServiceCommunicationConfig.should_retry(502))
        self.assertTrue(ServiceCommunicationConfig.should_retry(503))
        self.assertTrue(ServiceCommunicationConfig.should_retry(504))

    def test_should_retry_non_retryable_status(self):
        """Test should_retry for non-retryable status codes."""
        self.assertFalse(ServiceCommunicationConfig.should_retry(400))
        self.assertFalse(ServiceCommunicationConfig.should_retry(401))
        self.assertFalse(ServiceCommunicationConfig.should_retry(403))
        self.assertFalse(ServiceCommunicationConfig.should_retry(404))
        self.assertFalse(ServiceCommunicationConfig.should_retry(409))

    def test_calculate_retry_delay_exponential(self):
        """Test exponential backoff delay calculation."""
        delay1 = ServiceCommunicationConfig.calculate_retry_delay(
            attempt=0, base_delay=1.0, strategy=RetryStrategy.EXPONENTIAL_BACKOFF
        )
        self.assertEqual(delay1, 1.0)

        delay2 = ServiceCommunicationConfig.calculate_retry_delay(
            attempt=1, base_delay=1.0, strategy=RetryStrategy.EXPONENTIAL_BACKOFF
        )
        self.assertEqual(delay2, 2.0)

        delay3 = ServiceCommunicationConfig.calculate_retry_delay(
            attempt=2, base_delay=1.0, strategy=RetryStrategy.EXPONENTIAL_BACKOFF
        )
        self.assertEqual(delay3, 4.0)

    def test_calculate_retry_delay_linear(self):
        """Test linear backoff delay calculation."""
        delay1 = ServiceCommunicationConfig.calculate_retry_delay(
            attempt=0, base_delay=1.0, strategy=RetryStrategy.LINEAR_BACKOFF
        )
        self.assertEqual(delay1, 1.0)

        delay2 = ServiceCommunicationConfig.calculate_retry_delay(
            attempt=1, base_delay=1.0, strategy=RetryStrategy.LINEAR_BACKOFF
        )
        self.assertEqual(delay2, 2.0)

        delay3 = ServiceCommunicationConfig.calculate_retry_delay(
            attempt=2, base_delay=1.0, strategy=RetryStrategy.LINEAR_BACKOFF
        )
        self.assertEqual(delay3, 3.0)

    def test_calculate_retry_delay_fixed(self):
        """Test fixed delay calculation."""
        delay1 = ServiceCommunicationConfig.calculate_retry_delay(
            attempt=0, base_delay=1.0, strategy=RetryStrategy.FIXED_DELAY
        )
        self.assertEqual(delay1, 1.0)

        delay2 = ServiceCommunicationConfig.calculate_retry_delay(
            attempt=1, base_delay=1.0, strategy=RetryStrategy.FIXED_DELAY
        )
        self.assertEqual(delay2, 1.0)

    def test_calculate_retry_delay_max_delay(self):
        """Test retry delay respects max delay."""
        delay = ServiceCommunicationConfig.calculate_retry_delay(
            attempt=10, base_delay=10.0, strategy=RetryStrategy.EXPONENTIAL_BACKOFF, max_delay=60.0
        )
        self.assertLessEqual(delay, 60.0)


class ServiceClientTest(TestCase):
    """Test service client functionality."""

    @patch("hub.apps.core.services.discovery.get_service_url")
    def test_service_client_initialization(self, mock_get_url):
        """Test service client initialization."""
        mock_get_url.return_value = "http://test-service:8000"

        client = ServiceClient("test-service")

        self.assertEqual(client.service_name, "test-service")
        self.assertEqual(client.service_url, "http://test-service:8000")
        self.assertIsNotNone(client.client)

    @patch("hub.apps.core.services.discovery.get_service_url")
    def test_service_client_custom_timeout(self, mock_get_url):
        """Test service client with custom timeout."""
        mock_get_url.return_value = "http://test-service:8000"

        client = ServiceClient("test-service", timeout=60.0)

        self.assertEqual(client.timeout, 60.0)

    @patch("hub.apps.core.services.discovery.get_service_url")
    def test_service_client_custom_retry(self, mock_get_url):
        """Test service client with custom retry configuration."""
        mock_get_url.return_value = "http://test-service:8000"

        client = ServiceClient(
            "test-service",
            retry_count=5,
            retry_delay=2.0,
            retry_strategy=RetryStrategy.LINEAR_BACKOFF,
        )

        self.assertEqual(client.retry_count, 5)
        self.assertEqual(client.retry_delay, 2.0)
        self.assertEqual(client.retry_strategy, RetryStrategy.LINEAR_BACKOFF)

    @patch("hub.apps.core.services.discovery.get_service_url")
    @patch("httpx.Client")
    def test_service_client_get_success(self, mock_client_class, mock_get_url):
        """Test successful GET request."""
        mock_get_url.return_value = "http://test-service:8000"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "123", "name": "Test"}

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = ServiceClient("test-service")
        result = client.get("/api/v1/resource/123")

        self.assertEqual(result["id"], "123")
        self.assertEqual(result["name"], "Test")

    @patch("hub.apps.core.services.discovery.get_service_url")
    @patch("httpx.Client")
    def test_service_client_get_not_found(self, mock_client_class, mock_get_url):
        """Test GET request with 404 response."""
        mock_get_url.return_value = "http://test-service:8000"

        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = ServiceClient("test-service")

        with self.assertRaises(NotFoundError):
            client.get("/api/v1/resource/123")

    @patch("hub.apps.core.services.discovery.get_service_url")
    @patch("httpx.Client")
    @patch("time.sleep")
    def test_service_client_get_retry_success(self, mock_sleep, mock_client_class, mock_get_url):
        """Test GET request with retry on failure."""
        mock_get_url.return_value = "http://test-service:8000"

        # First attempt fails, second succeeds
        mock_response_fail = MagicMock()
        mock_response_fail.status_code = 503

        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"id": "123"}

        mock_client = MagicMock()
        mock_client.get.side_effect = [mock_response_fail, mock_response_success]
        mock_client_class.return_value = mock_client

        client = ServiceClient("test-service", retry_count=3, retry_delay=0.1)
        result = client.get("/api/v1/resource/123")

        self.assertEqual(result["id"], "123")
        self.assertEqual(mock_client.get.call_count, 2)
        mock_sleep.assert_called_once()

    @patch("hub.apps.core.services.discovery.get_service_url")
    @patch("httpx.Client")
    @patch("time.sleep")
    def test_service_client_get_retry_exhausted(self, mock_sleep, mock_client_class, mock_get_url):
        """Test GET request with exhausted retries."""
        mock_get_url.return_value = "http://test-service:8000"

        # Create mock response that raises HTTPStatusError when raise_for_status is called
        mock_response = MagicMock()
        mock_response.status_code = 503

        # Make raise_for_status raise HTTPStatusError
        def raise_status_error():
            error = httpx.HTTPStatusError(
                "Service Unavailable", request=MagicMock(), response=mock_response
            )
            raise error

        mock_response.raise_for_status.side_effect = raise_status_error

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = ServiceClient("test-service", retry_count=3, retry_delay=0.1)

        with self.assertRaises(ServiceError) as cm:
            client.get("/api/v1/resource/123")

        self.assertEqual(cm.exception.http_status, 503)
        self.assertEqual(mock_client.get.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)  # Retries: 2 sleeps

    @patch("hub.apps.core.services.discovery.get_service_url")
    @patch("httpx.Client")
    def test_service_client_post_success(self, mock_client_class, mock_get_url):
        """Test successful POST request."""
        mock_get_url.return_value = "http://test-service:8000"

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "123", "created": True}

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = ServiceClient("test-service")
        result = client.post("/api/v1/resource", data={"name": "Test"})

        self.assertEqual(result["id"], "123")
        self.assertTrue(result["created"])
        mock_client.post.assert_called_once()

    @patch("hub.apps.core.services.discovery.get_service_url")
    @patch("httpx.Client")
    def test_service_client_put_success(self, mock_client_class, mock_get_url):
        """Test successful PUT request."""
        mock_get_url.return_value = "http://test-service:8000"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "123", "updated": True}

        mock_client = MagicMock()
        mock_client.put.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = ServiceClient("test-service")
        result = client.put("/api/v1/resource/123", data={"name": "Updated"})

        self.assertEqual(result["id"], "123")
        self.assertTrue(result["updated"])

    @patch("hub.apps.core.services.discovery.get_service_url")
    @patch("httpx.Client")
    def test_service_client_delete_success(self, mock_client_class, mock_get_url):
        """Test successful DELETE request."""
        mock_get_url.return_value = "http://test-service:8000"

        mock_response = MagicMock()
        mock_response.status_code = 204

        mock_client = MagicMock()
        mock_client.delete.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = ServiceClient("test-service")
        client.delete("/api/v1/resource/123")

        mock_client.delete.assert_called_once()

    @patch("hub.apps.core.services.discovery.get_service_url")
    @patch("httpx.Client")
    def test_service_client_tenant_context(self, mock_client_class, mock_get_url):
        """Test service client includes tenant context in headers."""
        mock_get_url.return_value = "http://test-service:8000"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = ServiceClient("test-service")
        client.get("/api/v1/resource", tenant_id="tenant-123", user_id="user-456")

        # Verify headers were set
        call_args = mock_client.get.call_args
        headers = call_args[1]["headers"]
        self.assertEqual(headers.get("X-Tenant-Id"), "tenant-123")
        self.assertEqual(headers.get("X-User-Id"), "user-456")

    @patch("hub.apps.core.services.discovery.get_service_url")
    @patch("httpx.Client")
    def test_service_client_non_retryable_error(self, mock_client_class, mock_get_url):
        """Test that non-retryable errors are not retried."""
        mock_get_url.return_value = "http://test-service:8000"

        # Create mock response that raises HTTPStatusError when raise_for_status is called
        mock_response = MagicMock()
        mock_response.status_code = 400  # Bad request - not retryable

        # Make raise_for_status raise HTTPStatusError
        def raise_status_error():
            error = httpx.HTTPStatusError(
                "Bad Request", request=MagicMock(), response=mock_response
            )
            raise error

        mock_response.raise_for_status.side_effect = raise_status_error

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = ServiceClient("test-service", retry_count=3)

        with self.assertRaises(ServiceError):
            client.get("/api/v1/resource")

        # Should not retry on 400
        self.assertEqual(mock_client.get.call_count, 1)


class CachedServiceClientTest(TestCase):
    """Test cached service client functionality."""

    @patch("hub.apps.core.services.discovery.get_service_url")
    @patch("httpx.Client")
    def test_cached_service_client_cache_hit(self, mock_client_class, mock_get_url):
        """Test cached service client cache hit."""

        mock_get_url.return_value = "http://test-service:8000"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "123"}

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = CachedServiceClient("test-service", cache_ttl=60)

        # First call - cache miss
        result1 = client.get("/api/v1/resource/123", use_cache=True)
        self.assertEqual(mock_client.get.call_count, 1)

        # Second call - cache hit
        result2 = client.get("/api/v1/resource/123", use_cache=True)
        self.assertEqual(mock_client.get.call_count, 1)  # Still 1, not 2
        self.assertEqual(result1, result2)

    @patch("hub.apps.core.services.discovery.get_service_url")
    @patch("httpx.Client")
    def test_cached_service_client_cache_bypass(self, mock_client_class, mock_get_url):
        """Test cached service client cache bypass."""
        mock_get_url.return_value = "http://test-service:8000"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "123"}

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = CachedServiceClient("test-service", cache_ttl=60)

        # Call with cache disabled
        client.get("/api/v1/resource/123", use_cache=False)

        # Should still make request
        self.assertEqual(mock_client.get.call_count, 1)


class ServiceClientIntegrationTest(TestCase):
    """Integration tests for service client."""

    @patch("hub.apps.core.services.discovery.get_service_url")
    def test_service_client_context_manager(self, mock_get_url):
        """Test service client as context manager."""
        mock_get_url.return_value = "http://test-service:8000"

        with ServiceClient("test-service") as client:
            self.assertIsNotNone(client.client)

        # Client should be closed after context exit
        # (httpx.Client.close() is called in __exit__)

    @override_settings(
        SERVICE_COMMUNICATION_TIMEOUT=60.0,
        SERVICE_COMMUNICATION_RETRY_COUNT=5,
        SERVICE_COMMUNICATION_RETRY_DELAY=2.0,
    )
    @patch("hub.apps.core.services.discovery.get_service_url")
    def test_service_client_uses_settings(self, mock_get_url):
        """Test service client uses Django settings."""
        mock_get_url.return_value = "http://test-service:8000"

        client = ServiceClient("test-service")

        self.assertEqual(client.timeout, 60.0)
        self.assertEqual(client.retry_count, 5)
        self.assertEqual(client.retry_delay, 2.0)
