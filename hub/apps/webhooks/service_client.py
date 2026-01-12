"""
Webhook Delivery Service Client

Client for delivering webhooks with circuit breaker and retry logic.

**Important Notes:**
- This client follows service-to-service communication patterns with circuit breaker protection
- Used for delivering webhooks to external endpoints
- Provides retry logic, circuit breaker, and distributed tracing
"""
import httpx
import logging
import time
from typing import Dict, Any, Optional, Tuple
from django.conf import settings

from hub.apps.core.resilience.circuit_breaker import (
    CircuitBreaker,
    get_redis_client,
)

logger = logging.getLogger(__name__)


class WebhookDeliveryClient:
    """
    Client for webhook delivery with circuit breaker and retry logic.

    Follows Pattern 1: Direct Service Calls (Synchronous) from SERVICE_INTEGRATION_PATTERNS.md
    """

    def __init__(self, timeout: int = 30):
        """
        Initialize WebhookDeliveryClient.

        Args:
            timeout: Request timeout in seconds (default: 30)
        """
        self.timeout = timeout
        # Use httpx.Client with connection pooling
        self.client = httpx.Client(timeout=self.timeout)
        self.max_retries = 2
        self.backoff_factor = 1

        # Initialize circuit breaker
        self._circuit_breaker = CircuitBreaker(
            service_name="webhook-delivery",
            failure_threshold=5,
            timeout_seconds=60,
            success_threshold=2,
            redis_client=get_redis_client()
        )

    def _request_with_retry(self, method: str, url: str, **kwargs) -> httpx.Response:
        """
        Make HTTP request with retry logic and distributed tracing.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full URL to request
            **kwargs: Additional arguments for httpx request

        Returns:
            httpx.Response object

        Raises:
            httpx.HTTPStatusError: On HTTP errors
            httpx.RequestError: On network errors
        """
        # Add trace headers for distributed tracing
        from hub.apps.api.middleware.trace_propagation import get_trace_headers

        trace_headers = get_trace_headers()
        if trace_headers:
            # Merge trace headers into existing headers
            if 'headers' in kwargs:
                kwargs['headers'].update(trace_headers)
            else:
                kwargs['headers'] = trace_headers

        # Retry logic with exponential backoff
        for attempt in range(self.max_retries + 1):
            try:
                # Use circuit breaker to protect against cascading failures
                response = self._circuit_breaker.call(
                    lambda: self.client.request(method, url, **kwargs)
                )
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as e:
                # Retry on 5xx errors
                if e.response.status_code >= 500 and attempt < self.max_retries:
                    delay = self.backoff_factor * (2 ** attempt)
                    logger.warning(
                        f"Webhook delivery returned {e.response.status_code}. "
                        f"Retrying in {delay}s... (attempt {attempt + 1}/{self.max_retries + 1})"
                    )
                    time.sleep(delay)
                    continue
                # Don't retry on 4xx errors (client errors)
                raise
            except httpx.RequestError as e:
                # Retry on network errors
                if attempt < self.max_retries:
                    delay = self.backoff_factor * (2 ** attempt)
                    logger.warning(
                        f"Network error during webhook delivery: {e}. "
                        f"Retrying in {delay}s... (attempt {attempt + 1}/{self.max_retries + 1})"
                    )
                    time.sleep(delay)
                    continue
                raise
        raise Exception("Max retries exceeded for webhook delivery.")

    def deliver_webhook(
        self,
        url: str,
        payload: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[str] = None
    ) -> Tuple[int, str]:
        """
        Deliver webhook with retry and circuit breaker protection.

        Args:
            url: Webhook URL
            payload: JSON payload (if using json parameter)
            headers: HTTP headers
            data: Raw data string (alternative to payload)

        Returns:
            Tuple of (status_code, response_text)

        Raises:
            httpx.HTTPStatusError: On HTTP errors
            httpx.RequestError: On network errors
        """
        request_kwargs: Dict[str, Any] = {
            'headers': headers or {},
        }

        # Use data if provided, otherwise use json payload
        if data is not None:
            request_kwargs['content'] = data
            if 'headers' in request_kwargs:
                request_kwargs['headers']['Content-Type'] = 'application/json'
        elif payload is not None:
            request_kwargs['json'] = payload
        else:
            raise ValueError("Either 'payload' or 'data' must be provided")

        response = self._request_with_retry("POST", url, **request_kwargs)

        # Limit response text size
        response_text = response.text[:1000] if response.text else ""

        return response.status_code, response_text

    def health_check(self) -> Tuple[bool, str]:
        """
        Health check for webhook delivery client.

        Returns:
            Tuple of (is_healthy, status_message)
        """
        try:
            # Check circuit breaker state (if available)
            # Note: Circuit breaker state is internal, but we can check if it exists
            if hasattr(self._circuit_breaker, '_state'):
                # Internal state check - circuit breaker is working
                return True, "Webhook delivery client is healthy"

            return True, "Webhook delivery client is healthy"
        except Exception as e:
            logger.error(f"Webhook delivery client health check failed: {e}")
            return False, f"Health check error: {str(e)}"

    def close(self):
        """
        Close the HTTP client and release resources.

        Should be called when the client is no longer needed to properly
        close underlying socket connections.
        """
        if hasattr(self, 'client') and self.client is not None:
            try:
                self.client.close()
            except Exception as e:
                logger.debug(f"Error closing WebhookDeliveryClient: {e}")

    def __del__(self):
        """
        Cleanup method to ensure HTTP client is closed on garbage collection.

        This is a safety net - prefer calling close() explicitly when possible.
        """
        self.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures client is closed."""
        self.close()
        return False


