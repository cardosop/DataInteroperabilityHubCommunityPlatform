"""
Service Health Client

Client for checking service health with circuit breaker and retry logic.

**Important Notes:**
- This client follows service-to-service communication patterns with circuit breaker protection
- Used for health checks of external services
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


class ServiceHealthClient:
    """
    Client for service health checks with circuit breaker and retry logic.

    Follows Pattern 1: Direct Service Calls (Synchronous) from SERVICE_INTEGRATION_PATTERNS.md
    """

    def __init__(self, timeout: int = 5):
        """
        Initialize ServiceHealthClient.

        Args:
            timeout: Request timeout in seconds (default: 5)
        """
        self.timeout = timeout
        # Use httpx.Client with connection pooling
        self.client = httpx.Client(timeout=self.timeout, follow_redirects=True)
        self.max_retries = 2
        self.backoff_factor = 1

        # Initialize circuit breaker
        self._circuit_breaker = CircuitBreaker(
            service_name="service-health-check",
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
                        f"Health check returned {e.response.status_code}. "
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
                        f"Network error during health check: {e}. "
                        f"Retrying in {delay}s... (attempt {attempt + 1}/{self.max_retries + 1})"
                    )
                    time.sleep(delay)
                    continue
                raise
        raise Exception("Max retries exceeded for health check.")

    def check_health(
        self,
        service_url: str,
        health_path: str = "/health",
        timeout: Optional[int] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Check service health.

        Args:
            service_url: Base URL of the service
            health_path: Health check endpoint path (default: /health)
            timeout: Request timeout in seconds (overrides default)

        Returns:
            Tuple of (is_healthy, status_message)
        """
        health_url = f"{service_url.rstrip('/')}{health_path}"
        effective_timeout = timeout or self.timeout

        try:
            # Use a temporary client with custom timeout if needed
            if timeout and timeout != self.timeout:
                with httpx.Client(timeout=effective_timeout, follow_redirects=True) as temp_client:
                    response = temp_client.get(health_url)
                    response.raise_for_status()
            else:
                response = self._request_with_retry("GET", health_url)

            if response.status_code == 200:
                try:
                    data = response.json()
                    is_healthy = data.get('status') in ['healthy', 'ok', 'up']
                    status_message = data.get('service', 'unknown')
                    return is_healthy, status_message
                except (ValueError, KeyError):
                    # If response is not JSON or doesn't have status, consider 200 as healthy
                    return True, "healthy"
            else:
                return False, f"HTTP {response.status_code}"

        except httpx.TimeoutException:
            logger.debug(f"Health check timeout for {service_url}")
            return False, "timeout"
        except httpx.ConnectError:
            logger.debug(f"Health check connection error for {service_url}")
            return False, "unreachable"
        except httpx.HTTPStatusError as e:
            logger.debug(f"Health check HTTP error for {service_url}: {e.response.status_code}")
            return False, f"HTTP {e.response.status_code}"
        except Exception as e:
            logger.debug(f"Health check error for {service_url}: {e}")
            return False, f"error: {str(e)[:50]}"

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
                logger.debug(f"Error closing ServiceHealthClient: {e}")

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


