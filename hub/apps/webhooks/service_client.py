"""
Webhook Delivery Service Client

Client for delivering webhooks with circuit breaker and retry logic.

**Important Notes:**
- This client follows service-to-service communication patterns with circuit breaker protection
- Used for delivering webhooks to external endpoints
- Provides retry logic, circuit breaker, and distributed tracing
"""

import time
from typing import Any

import httpx
import structlog
from django.conf import settings

from hub.apps.core.resilience.circuit_breaker import (
    CircuitBreaker,
    get_redis_client,
)

logger = structlog.get_logger(__name__)


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
        # Max retries is configurable so test suites can set 0 to avoid
        # expensive DNS-resolution retry loops against unresolvable hosts.
        self.max_retries = getattr(settings, "WEBHOOK_DELIVERY_MAX_RETRIES", 2)
        self.backoff_factor = 1

        # Initialize circuit breaker
        self._circuit_breaker = CircuitBreaker(
            service_name="webhook-delivery",
            failure_threshold=5,
            timeout_seconds=60,
            success_threshold=2,
            redis_client=get_redis_client(),
        )

    def _request_with_retry(
        self, method: str, url: str, *, follow_redirects: bool = True, **kwargs
    ) -> httpx.Response:
        """
        Make HTTP request with retry logic and distributed tracing.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full URL to request
            follow_redirects: Whether httpx should automatically follow
                redirects (301/302/307/308).  Set to False when the caller
                needs to inspect and SSRF-validate the redirect target before
                following.
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
            if "headers" in kwargs:
                kwargs["headers"].update(trace_headers)
            else:
                kwargs["headers"] = trace_headers

        # Retry logic with exponential backoff
        for attempt in range(self.max_retries + 1):
            try:
                # Use circuit breaker to protect against cascading failures
                response = self._circuit_breaker.call(
                    lambda m=method, u=url, fw=follow_redirects, kw=kwargs: self.client.request(
                        m, u, follow_redirects=fw, **kw
                    )
                )
                if response.status_code >= 500 and attempt < self.max_retries:
                    delay = self.backoff_factor * (2**attempt)
                    logger.warning(
                        "webhook_delivery_http_retry",
                        status_code=response.status_code,
                        delay=delay,
                        attempt=attempt + 1,
                        max_attempts=self.max_retries + 1,
                    )
                    time.sleep(delay)
                    continue
                # When redirect-following is disabled the caller wants to
                # inspect the (potentially 3xx) response themselves — only
                # raise for real errors (4xx/5xx).
                if follow_redirects or response.status_code >= 400:
                    response.raise_for_status()
                return response
            except httpx.HTTPStatusError:
                # 4xx (and 3xx when following redirects) — don't retry
                raise
            except httpx.RequestError as e:
                # Retry on network errors
                if attempt < self.max_retries:
                    delay = self.backoff_factor * (2**attempt)
                    logger.warning(
                        "webhook_delivery_network_retry",
                        error=str(e),
                        delay=delay,
                        attempt=attempt + 1,
                        max_attempts=self.max_retries + 1,
                    )
                    time.sleep(delay)
                    continue
                raise
        raise Exception("Max retries exceeded for webhook delivery.")

    def deliver_webhook(
        self,
        url: str,
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        data: str | None = None,
        *,
        follow_redirects: bool = True,
    ) -> tuple[int, str]:
        """
        Deliver webhook with retry and circuit breaker protection.

        Args:
            url: Webhook URL
            payload: JSON payload (if using json parameter)
            headers: HTTP headers
            data: Raw data string (alternative to payload)
            follow_redirects: Whether to automatically follow HTTP redirects.
                Set to False when the caller needs to inspect the redirect
                target for SSRF before following.

        Returns:
            Tuple of (status_code, response_text)

        Raises:
            httpx.HTTPStatusError: On HTTP errors
            httpx.RequestError: On network errors
        """
        request_kwargs: dict[str, Any] = {
            "headers": headers or {},
        }

        # Use data if provided, otherwise use json payload
        if data is not None:
            request_kwargs["content"] = data
            if "headers" in request_kwargs:
                request_kwargs["headers"]["Content-Type"] = "application/json"
        elif payload is not None:
            request_kwargs["json"] = payload
        else:
            raise ValueError("Either 'payload' or 'data' must be provided")

        response = self._request_with_retry(
            "POST", url, follow_redirects=follow_redirects, **request_kwargs
        )

        # Limit response text size
        response_text = response.text[:1000] if response.text else ""

        return response.status_code, response_text

    def deliver_webhook_with_response(
        self,
        url: str,
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        data: str | None = None,
        *,
        follow_redirects: bool = False,
    ) -> httpx.Response:
        """
        Deliver webhook and return the full httpx Response object.

        Unlike ``deliver_webhook`` which returns ``(status_code, text)``,
        this method returns the full ``httpx.Response`` so callers can
        inspect headers (e.g. the ``Location`` header on a 301/302
        redirect for SSRF validation).

        Args:
            url: Webhook URL
            payload: JSON payload
            headers: HTTP headers
            data: Raw data string (alternative to payload)
            follow_redirects: Whether to follow HTTP redirects (default False).

        Returns:
            Full httpx.Response object.

        Raises:
            httpx.HTTPStatusError: On HTTP errors (when follow_redirects=True)
            httpx.RequestError: On network errors
        """
        request_kwargs: dict[str, Any] = {
            "headers": headers or {},
        }

        if data is not None:
            request_kwargs["content"] = data
            if "headers" in request_kwargs:
                request_kwargs["headers"]["Content-Type"] = "application/json"
        elif payload is not None:
            request_kwargs["json"] = payload
        else:
            raise ValueError("Either 'payload' or 'data' must be provided")

        return self._request_with_retry(
            "POST", url, follow_redirects=follow_redirects, **request_kwargs
        )

    def health_check(self) -> tuple[bool, str]:
        """
        Health check for webhook delivery client.

        Returns:
            Tuple of (is_healthy, status_message)
        """
        try:
            # Check circuit breaker state (if available)
            # Note: Circuit breaker state is internal, but we can check if it exists
            if hasattr(self._circuit_breaker, "_state"):
                # Internal state check - circuit breaker is working
                return True, "Webhook delivery client is healthy"

            return True, "Webhook delivery client is healthy"
        except (AttributeError, RuntimeError) as e:
            logger.error("webhook_client_health_check_failed", error=str(e))
            return False, f"Health check error: {e!s}"

    def close(self):
        """
        Close the HTTP client and release resources.

        Should be called when the client is no longer needed to properly
        close underlying socket connections.
        """
        if hasattr(self, "client") and self.client is not None:
            try:
                self.client.close()
            except OSError as e:
                logger.debug("webhook_client_close_error", error=str(e))

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
