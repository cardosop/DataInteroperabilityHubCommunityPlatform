"""
Cross-Service Data Access Patterns

Provides patterns for accessing data across service boundaries in a microservices architecture.
"""

import time
from enum import Enum
from typing import Any

import httpx
import structlog
from django.conf import settings
from django.core.cache import cache

from hub.apps.core.services.base import NotFoundError, ServiceError
from hub.apps.observability.otel_metrics import (
    service_call_duration_seconds,
    service_call_errors_total,
    service_call_retries_total,
    service_call_timeouts_total,
    service_calls_total,
)

# OpenTelemetry tracing
try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode

    from hub.apps.observability.tracing import get_tracer

    _tracer = get_tracer(__name__)
    _trace_available = True
except ImportError:
    _tracer = None
    trace = None
    Status = None
    StatusCode = None
    _trace_available = False

logger = structlog.get_logger(__name__)


class RetryStrategy(Enum):
    """Retry strategy types."""

    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"


class ServiceCommunicationConfig:
    """
    Configuration for service-to-service communication.

    Provides centralized configuration for timeouts, retries, and other
    communication settings.
    """

    # Default timeout values (in seconds)
    DEFAULT_TIMEOUT = 30
    DEFAULT_CONNECT_TIMEOUT = 5
    DEFAULT_READ_TIMEOUT = 30

    # Default retry configuration
    DEFAULT_RETRY_COUNT = 3
    DEFAULT_RETRY_DELAY = 1.0
    DEFAULT_RETRY_MAX_DELAY = 60.0
    DEFAULT_RETRY_STRATEGY = RetryStrategy.EXPONENTIAL_BACKOFF

    # Retryable status codes
    RETRYABLE_STATUS_CODES = {500, 502, 503, 504}

    # Non-retryable status codes (don't retry on these)
    NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404, 409}

    @classmethod
    def get_timeout(cls, service_name: str | None = None) -> float:
        """
        Get timeout for a service.

        Args:
            service_name: Service name (optional)

        Returns:
            Timeout in seconds
        """
        if service_name:
            # Check for service-specific timeout setting
            setting_name = f"{service_name.upper().replace('-', '_')}_TIMEOUT"
            timeout = getattr(settings, setting_name, None)
            if timeout:
                return float(timeout)

        # Check for global timeout setting
        global_timeout = getattr(settings, "SERVICE_COMMUNICATION_TIMEOUT", None)
        if global_timeout:
            return float(global_timeout)

        return cls.DEFAULT_TIMEOUT

    @classmethod
    def get_retry_count(cls, service_name: str | None = None) -> int:
        """
        Get retry count for a service.

        Args:
            service_name: Service name (optional)

        Returns:
            Retry count
        """
        if service_name:
            # Check for service-specific retry setting
            setting_name = f"{service_name.upper().replace('-', '_')}_RETRY_COUNT"
            retry_count = getattr(settings, setting_name, None)
            if retry_count:
                return int(retry_count)

        # Check for global retry setting
        global_retry = getattr(settings, "SERVICE_COMMUNICATION_RETRY_COUNT", None)
        if global_retry:
            return int(global_retry)

        return cls.DEFAULT_RETRY_COUNT

    @classmethod
    def get_retry_delay(cls, service_name: str | None = None) -> float:
        """
        Get retry delay for a service.

        Args:
            service_name: Service name (optional)

        Returns:
            Retry delay in seconds
        """
        if service_name:
            # Check for service-specific retry delay setting
            setting_name = f"{service_name.upper().replace('-', '_')}_RETRY_DELAY"
            retry_delay = getattr(settings, setting_name, None)
            if retry_delay:
                return float(retry_delay)

        # Check for global retry delay setting
        global_delay = getattr(settings, "SERVICE_COMMUNICATION_RETRY_DELAY", None)
        if global_delay:
            return float(global_delay)

        return cls.DEFAULT_RETRY_DELAY

    @classmethod
    def get_retry_strategy(cls, service_name: str | None = None) -> RetryStrategy:
        """
        Get retry strategy for a service.

        Args:
            service_name: Service name (optional)

        Returns:
            Retry strategy
        """
        if service_name:
            # Check for service-specific retry strategy setting
            setting_name = f"{service_name.upper().replace('-', '_')}_RETRY_STRATEGY"
            strategy_str = getattr(settings, setting_name, None)
            if strategy_str:
                try:
                    return RetryStrategy(strategy_str)
                except ValueError:
                    pass

        # Check for global retry strategy setting
        global_strategy = getattr(settings, "SERVICE_COMMUNICATION_RETRY_STRATEGY", None)
        if global_strategy:
            try:
                return RetryStrategy(global_strategy)
            except ValueError:
                pass

        return cls.DEFAULT_RETRY_STRATEGY

    @classmethod
    def should_retry(cls, status_code: int) -> bool:
        """
        Determine if a status code should be retried.

        Args:
            status_code: HTTP status code

        Returns:
            True if should retry, False otherwise
        """
        if status_code in cls.NON_RETRYABLE_STATUS_CODES:
            return False
        if status_code in cls.RETRYABLE_STATUS_CODES:
            return True
        # Don't retry on 2xx or other status codes
        return False

    @classmethod
    def calculate_retry_delay(
        cls,
        attempt: int,
        base_delay: float,
        strategy: RetryStrategy,
        max_delay: float | None = None,
    ) -> float:
        """
        Calculate retry delay for an attempt.

        Args:
            attempt: Attempt number (0-indexed)
            base_delay: Base delay in seconds
            strategy: Retry strategy
            max_delay: Maximum delay in seconds (optional)

        Returns:
            Delay in seconds
        """
        max_delay = max_delay or cls.DEFAULT_RETRY_MAX_DELAY

        if strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = base_delay * (2**attempt)
        elif strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = base_delay * (attempt + 1)
        else:  # FIXED_DELAY
            delay = base_delay

        return min(delay, max_delay)


class ServiceClient:
    """
    Client for cross-service API calls.

    Provides a standardized way to call other services via HTTP APIs with
    configurable timeouts, retries, and error handling.
    """

    def __init__(
        self,
        service_name: str,
        service_url: str | None = None,
        timeout: float | None = None,
        connect_timeout: float | None = None,
        read_timeout: float | None = None,
        retry_count: int | None = None,
        retry_delay: float | None = None,
        retry_strategy: RetryStrategy | None = None,
        retry_max_delay: float | None = None,
    ):
        """
        Initialize service client.

        Args:
            service_name: Name of the target service (e.g., 'contract-service')
            service_url: Base URL of the service (default: from service discovery)
            timeout: Request timeout in seconds (default: from config)
            connect_timeout: Connection timeout in seconds (default: 5)
            read_timeout: Read timeout in seconds (default: same as timeout)
            retry_count: Number of retries on failure (default: from config)
            retry_delay: Base delay between retries in seconds (default: from config)
            retry_strategy: Retry strategy (default: exponential backoff)
            retry_max_delay: Maximum retry delay in seconds (default: 60)
        """
        self.service_name = service_name
        self.service_url = service_url or self._get_service_url(service_name)

        # Get configuration values
        config = ServiceCommunicationConfig
        self.timeout = timeout or config.get_timeout(service_name)
        self.connect_timeout = connect_timeout or config.DEFAULT_CONNECT_TIMEOUT
        self.read_timeout = read_timeout or self.timeout
        self.retry_count = retry_count or config.get_retry_count(service_name)
        self.retry_delay = retry_delay or config.get_retry_delay(service_name)
        self.retry_strategy = retry_strategy or config.get_retry_strategy(service_name)
        self.retry_max_delay = retry_max_delay or config.DEFAULT_RETRY_MAX_DELAY

        # Create HTTP client with timeout configuration
        timeout_config = httpx.Timeout(
            connect=self.connect_timeout,
            read=self.read_timeout,
            write=self.read_timeout,
            pool=self.connect_timeout,
        )

        self.client = httpx.Client(
            base_url=self.service_url,
            timeout=timeout_config,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

    def _get_service_url(self, service_name: str) -> str:
        """Get service URL using service discovery."""
        from hub.apps.core.services.discovery import get_service_url

        return get_service_url(service_name)

    def _get_status_class(self, status_code: int) -> str:
        """Get status class from HTTP status code."""
        if 200 <= status_code < 300:
            return "2xx"
        elif 300 <= status_code < 400:
            return "3xx"
        elif 400 <= status_code < 500:
            return "4xx"
        elif 500 <= status_code < 600:
            return "5xx"
        else:
            return "unknown"

    def _get_error_type(self, status_code: int) -> str:
        """Get error type from HTTP status code."""
        if status_code == 400:
            return "BAD_REQUEST"
        elif status_code == 401:
            return "UNAUTHORIZED"
        elif status_code == 403:
            return "FORBIDDEN"
        elif status_code == 404:
            return "NOT_FOUND"
        elif status_code == 409:
            return "CONFLICT"
        elif status_code == 429:
            return "RATE_LIMIT"
        elif status_code >= 500:
            return "SERVER_ERROR"
        else:
            return "CLIENT_ERROR"

    def _request_with_retry(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        tenant_id: str | None = None,
        user_id: str | None = None,
        source_service: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Make HTTP request with retry logic, metrics, and tracing.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            path: API path
            params: Query parameters (for GET)
            data: Request body data (for POST/PUT)
            headers: Additional headers
            tenant_id: Tenant ID for tenant isolation
            user_id: User ID for user context
            source_service: Source service name for metrics (optional)

        Returns:
            Response data as dictionary (None for DELETE)

        Raises:
            NotFoundError: If resource not found (404)
            ServiceError: If service error occurs
        """
        start_time = time.time()
        request_headers = self._build_headers(headers, tenant_id, user_id)
        last_exception = None
        retry_count = 0
        effective_source_service = source_service or "unknown"

        # Create tracing span
        span = None
        if _tracer and _trace_available:
            span = _tracer.start_span(
                name=f"{effective_source_service}.call.{self.service_name}",
                kind=trace.SpanKind.CLIENT,
                attributes={
                    "service.source": effective_source_service,
                    "service.target": self.service_name,
                    "http.method": method,
                    "http.url": f"{self.service_url}{path}",
                    "service.tenant_id": tenant_id or "unknown",
                },
            )

        try:
            for attempt in range(self.retry_count):
                try:
                    # Make request based on method
                    if method == "GET":
                        response = self.client.get(path, params=params, headers=request_headers)
                    elif method == "POST":
                        response = self.client.post(path, json=data, headers=request_headers)
                    elif method == "PUT":
                        response = self.client.put(path, json=data, headers=request_headers)
                    elif method == "DELETE":
                        response = self.client.delete(path, headers=request_headers)
                    else:
                        raise ValueError(f"Unsupported HTTP method: {method}")

                    duration_seconds = time.time() - start_time
                    status_class = self._get_status_class(response.status_code)

                    # Record metrics
                    service_calls_total.labels(
                        source_service=effective_source_service,
                        target_service=self.service_name,
                        method=method,
                        status=status_class,
                        tenant_id=tenant_id or "unknown",
                    ).inc()

                    service_call_duration_seconds.labels(
                        source_service=effective_source_service,
                        target_service=self.service_name,
                        method=method,
                        status=status_class,
                        tenant_id=tenant_id or "unknown",
                    ).observe(duration_seconds)

                    # Record retries if any
                    if retry_count > 0:
                        service_call_retries_total.labels(
                            source_service=effective_source_service,
                            target_service=self.service_name,
                            method=method,
                            retry_count=str(retry_count),
                            tenant_id=tenant_id or "unknown",
                        ).inc()

                    # Update tracing span
                    if span and _trace_available:
                        span.set_attribute("http.status_code", response.status_code)
                        span.set_attribute("service.duration_seconds", duration_seconds)
                        if retry_count > 0:
                            span.set_attribute("service.retry_count", retry_count)

                    if response.status_code == 404:
                        if span and _trace_available:
                            span.set_status(Status(StatusCode.ERROR, "Not Found"))
                            span.end()
                        raise NotFoundError(self.service_name, path)

                    # Check if status code is retryable
                    if attempt < self.retry_count - 1 and ServiceCommunicationConfig.should_retry(
                        response.status_code
                    ):
                        retry_count += 1
                        delay = ServiceCommunicationConfig.calculate_retry_delay(
                            attempt=attempt,
                            base_delay=self.retry_delay,
                            strategy=self.retry_strategy,
                            max_delay=self.retry_max_delay,
                        )
                        logger.warning(
                            "service_request_retry",
                            service=self.service_name,
                            method=method,
                            path=path,
                            status_code=response.status_code,
                            attempt=attempt + 1,
                            max_attempts=self.retry_count,
                            delay=delay,
                        )
                        time.sleep(delay)
                        continue

                    response.raise_for_status()

                    # End tracing span successfully
                    if span and _trace_available:
                        span.set_status(Status(StatusCode.OK))
                        span.end()

                    # Return JSON for methods that return data
                    if method == "DELETE":
                        return None
                    return response.json()

                except httpx.HTTPStatusError as e:
                    duration_seconds = time.time() - start_time

                    if e.response.status_code == 404:
                        if span and _trace_available:
                            span.set_status(Status(StatusCode.ERROR, "Not Found"))
                            span.end()
                        raise NotFoundError(self.service_name, path)

                    # Check if should retry
                    if attempt < self.retry_count - 1 and ServiceCommunicationConfig.should_retry(
                        e.response.status_code
                    ):
                        retry_count += 1
                        delay = ServiceCommunicationConfig.calculate_retry_delay(
                            attempt=attempt,
                            base_delay=self.retry_delay,
                            strategy=self.retry_strategy,
                            max_delay=self.retry_max_delay,
                        )
                        logger.warning(
                            "service_request_retry",
                            service=self.service_name,
                            method=method,
                            path=path,
                            status_code=e.response.status_code,
                            attempt=attempt + 1,
                            max_attempts=self.retry_count,
                            delay=delay,
                        )
                        time.sleep(delay)
                        last_exception = e
                        continue

                    # Record error metrics
                    error_type = self._get_error_type(e.response.status_code)
                    service_call_errors_total.labels(
                        source_service=effective_source_service,
                        target_service=self.service_name,
                        method=method,
                        error_type=error_type,
                        tenant_id=tenant_id or "unknown",
                    ).inc()

                    # End tracing span with error
                    if span and _trace_available:
                        span.set_attribute("http.status_code", e.response.status_code)
                        span.set_attribute("service.error_type", error_type)
                        span.set_status(Status(StatusCode.ERROR, f"HTTP {e.response.status_code}"))
                        span.record_exception(e)
                        span.end()

                    raise ServiceError(
                        f"Service {self.service_name} returned error: {e.response.status_code}",
                        http_status=e.response.status_code,
                        details={
                            "path": path,
                            "method": method,
                            "status_code": e.response.status_code,
                        },
                    )
                except httpx.TimeoutException as e:
                    duration_seconds = time.time() - start_time

                    # Record timeout metric
                    service_call_timeouts_total.labels(
                        source_service=effective_source_service,
                        target_service=self.service_name,
                        method=method,
                        tenant_id=tenant_id or "unknown",
                    ).inc()

                    # Network errors are always retryable
                    if attempt < self.retry_count - 1:
                        retry_count += 1
                        delay = ServiceCommunicationConfig.calculate_retry_delay(
                            attempt=attempt,
                            base_delay=self.retry_delay,
                            strategy=self.retry_strategy,
                            max_delay=self.retry_max_delay,
                        )
                        logger.warning(
                            "service_request_retry",
                            service=self.service_name,
                            method=method,
                            path=path,
                            error=str(e),
                            attempt=attempt + 1,
                            max_attempts=self.retry_count,
                            delay=delay,
                        )
                        time.sleep(delay)
                        last_exception = e
                        continue

                    # End tracing span with timeout error
                    if span and _trace_available:
                        span.set_attribute("service.error_type", "TIMEOUT")
                        span.set_status(Status(StatusCode.ERROR, "Timeout"))
                        span.record_exception(e)
                        span.end()

                    raise ServiceError(
                        f"Failed to connect to {self.service_name}: {e}",
                        http_status=503,
                        details={"path": path, "method": method, "error": str(e)},
                    )
                except httpx.RequestError as e:
                    # Network errors are always retryable
                    duration_seconds = time.time() - start_time

                    if attempt < self.retry_count - 1:
                        retry_count += 1
                        delay = ServiceCommunicationConfig.calculate_retry_delay(
                            attempt=attempt,
                            base_delay=self.retry_delay,
                            strategy=self.retry_strategy,
                            max_delay=self.retry_max_delay,
                        )
                        logger.warning(
                            "service_request_retry",
                            service=self.service_name,
                            method=method,
                            path=path,
                            error=str(e),
                            attempt=attempt + 1,
                            max_attempts=self.retry_count,
                            delay=delay,
                        )
                        time.sleep(delay)
                        last_exception = e
                        continue

                    # End tracing span with network error
                    if span and _trace_available:
                        span.set_attribute("service.error_type", "NETWORK_ERROR")
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.record_exception(e)
                        span.end()

                    raise ServiceError(
                        f"Failed to connect to {self.service_name}: {e}",
                        http_status=503,
                        details={"path": path, "method": method, "error": str(e)},
                    )
        except Exception as e:
            # End tracing span with unexpected error
            if span and _trace_available:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                span.end()
            raise
        # If we exhausted retries, raise the last exception
        if last_exception:
            # End tracing span with retry exhaustion
            if span and _trace_available:
                span.set_attribute("service.retry_exhausted", True)
                span.set_status(Status(StatusCode.ERROR, "Retries exhausted"))
                span.end()

            if isinstance(last_exception, httpx.HTTPStatusError):
                raise ServiceError(
                    f"Service {self.service_name} failed after {self.retry_count} attempts: {last_exception.response.status_code}",
                    http_status=last_exception.response.status_code,
                    details={"path": path, "method": method, "attempts": self.retry_count},
                )
            else:
                raise ServiceError(
                    f"Failed to connect to {self.service_name} after {self.retry_count} attempts: {last_exception}",
                    http_status=503,
                    details={"path": path, "method": method, "attempts": self.retry_count},
                )

    def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        tenant_id: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Make GET request to service.

        Args:
            path: API path (e.g., '/api/v1/contracts/{id}')
            params: Query parameters
            headers: Additional headers
            tenant_id: Tenant ID for tenant isolation
            user_id: User ID for user context

        Returns:
            Response data as dictionary

        Raises:
            NotFoundError: If resource not found (404)
            ServiceError: If service error occurs
        """
        result = self._request_with_retry(
            method="GET",
            path=path,
            params=params,
            headers=headers,
            tenant_id=tenant_id,
            user_id=user_id,
            source_service=getattr(self, "source_service", None),
        )
        return result

    def post(
        self,
        path: str,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        tenant_id: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Make POST request to service.

        Args:
            path: API path
            data: Request body data
            headers: Additional headers
            tenant_id: Tenant ID for tenant isolation
            user_id: User ID for user context

        Returns:
            Response data as dictionary

        Raises:
            ServiceError: If service error occurs
        """
        return self._request_with_retry(
            method="POST",
            path=path,
            data=data,
            headers=headers,
            tenant_id=tenant_id,
            user_id=user_id,
            source_service=getattr(self, "source_service", None),
        )

    def put(
        self,
        path: str,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        tenant_id: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Make PUT request to service.

        Args:
            path: API path
            data: Request body data
            headers: Additional headers
            tenant_id: Tenant ID for tenant isolation
            user_id: User ID for user context

        Returns:
            Response data as dictionary

        Raises:
            ServiceError: If service error occurs
        """
        return self._request_with_retry(
            method="PUT",
            path=path,
            data=data,
            headers=headers,
            tenant_id=tenant_id,
            user_id=user_id,
            source_service=getattr(self, "source_service", None),
        )

    def delete(
        self,
        path: str,
        headers: dict[str, str] | None = None,
        tenant_id: str | None = None,
        user_id: str | None = None,
    ) -> None:
        """
        Make DELETE request to service.

        Args:
            path: API path
            headers: Additional headers
            tenant_id: Tenant ID for tenant isolation
            user_id: User ID for user context

        Raises:
            ServiceError: If service error occurs
        """
        self._request_with_retry(
            method="DELETE",
            path=path,
            headers=headers,
            tenant_id=tenant_id,
            user_id=user_id,
            source_service=getattr(self, "source_service", None),
        )

    def _build_headers(
        self, headers: dict[str, str] | None, tenant_id: str | None, user_id: str | None
    ) -> dict[str, str]:
        """Build request headers with tenant and user context."""
        request_headers = {}

        if tenant_id:
            request_headers["X-Tenant-Id"] = tenant_id
        if user_id:
            request_headers["X-User-Id"] = user_id

        # Add trace context if available
        from opentelemetry import trace

        span = trace.get_current_span()
        if span:
            span_context = span.get_span_context()
            if span_context.is_valid:
                request_headers["traceparent"] = (
                    f"00-{span_context.trace_id:032x}-{span_context.span_id:016x}-01"
                )

        if headers:
            request_headers.update(headers)

        return request_headers

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.client.close()


class CachedServiceClient(ServiceClient):
    """
    Service client with caching support.

    Caches responses for GET requests to reduce API calls.
    """

    def __init__(
        self, service_name: str, cache_ttl: int = 3600, cache_prefix: str | None = None, **kwargs
    ):
        """
        Initialize cached service client.

        Args:
            service_name: Name of the target service
            cache_ttl: Cache TTL in seconds (default: 1 hour)
            cache_prefix: Cache key prefix (default: service_name)
            **kwargs: Additional arguments for ServiceClient
        """
        super().__init__(service_name, **kwargs)
        self.cache_ttl = cache_ttl
        self.cache_prefix = cache_prefix or service_name

    def get(
        self, path: str, params: dict[str, Any] | None = None, use_cache: bool = True, **kwargs
    ) -> dict[str, Any]:
        """
        Make GET request with caching.

        Args:
            path: API path
            params: Query parameters
            use_cache: Whether to use cache (default: True)
            **kwargs: Additional arguments
        """
        if not use_cache:
            return super().get(path, params=params, **kwargs)

        # Build cache key
        cache_key = self._build_cache_key(path, params)

        # Try cache first
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            logger.debug("Cache hit", service=self.service_name, path=path)
            return cached_data

        # Cache miss, call service
        logger.debug("Cache miss", service=self.service_name, path=path)
        data = super().get(path, params=params, **kwargs)

        # Store in cache
        cache.set(cache_key, data, timeout=self.cache_ttl)

        return data

    def _build_cache_key(self, path: str, params: dict[str, Any] | None) -> str:
        """Build cache key from path and params."""
        key_parts = [self.cache_prefix, path]
        if params:
            # Sort params for consistent key
            sorted_params = sorted(params.items())
            key_parts.append(str(sorted_params))
        return ":".join(key_parts)


class EventualConsistencyClient:
    """
    Client for eventual consistency patterns.

    Provides methods for maintaining read models via events.
    """

    def __init__(self, event_bus):
        """
        Initialize eventual consistency client.

        Args:
            event_bus: Event bus instance
        """
        self.event_bus = event_bus

    def subscribe_to_updates(self, event_type: str, handler: callable, service_name: str):
        """
        Subscribe to events for read model updates.

        Args:
            event_type: Event type to subscribe to (e.g., 'asset.created')
            handler: Handler function to call on event
            service_name: Name of the service maintaining read model
        """

        @self.event_bus.subscribe(event_type)
        def event_handler(event):
            try:
                handler(event)
            except Exception as e:
                logger.error(
                    "Event handler failed",
                    service=service_name,
                    event_type=event_type,
                    error=str(e),
                )


# Factory functions for common patterns


def get_contract_client(tenant_id: str | None = None) -> ServiceClient:
    """Get contract service client."""
    client = ServiceClient("contract-service")
    if tenant_id:
        client.tenant_id = tenant_id
    return client


def get_asset_client(tenant_id: str | None = None, use_cache: bool = True) -> ServiceClient:
    """Get asset service client with optional caching."""
    if use_cache:
        return CachedServiceClient("asset-service", cache_ttl=3600)
    return ServiceClient("asset-service")


def get_dataset_client(tenant_id: str | None = None) -> ServiceClient:
    """Get dataset service client."""
    return ServiceClient("dataset-service")
