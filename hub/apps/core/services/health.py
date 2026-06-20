"""
Service Health Check Utilities

Provides utilities for checking service health and availability.
"""

import time
from typing import Any

import httpx
import structlog
from django.core.cache import cache

from hub.apps.core.services.discovery import ServiceRegistry, get_health_check_url
from hub.apps.observability.otel_metrics import (
    service_health_check_duration_seconds,
    service_health_checks_total,
    service_health_status,
)

logger = structlog.get_logger(__name__)


class ServiceHealthCheck:
    """
    Service health check utility.

    Provides methods for checking service health and availability.
    """

    def __init__(self, service_name: str, timeout: float = 5.0, cache_ttl: int = 30):
        """
        Initialize service health check.

        Args:
            service_name: Service name to check
            timeout: Health check timeout in seconds
            cache_ttl: Cache TTL for health check results in seconds
        """
        self.service_name = service_name
        self.timeout = timeout
        self.cache_ttl = cache_ttl
        self.health_url = get_health_check_url(service_name)

    def check_health(self, use_cache: bool = True, namespace: str | None = None) -> dict[str, Any]:
        """
        Check service health.

        Args:
            use_cache: Whether to use cached results
            namespace: Kubernetes namespace (optional)

        Returns:
            Health check result dictionary with:
            - status: 'healthy', 'unhealthy', or 'unknown'
            - latency_ms: Response latency in milliseconds
            - timestamp: Check timestamp
            - error: Error message if unhealthy
        """
        # Check cache first
        if use_cache:
            cache_key = f"service_health:{self.service_name}"
            cached_result = cache.get(cache_key)
            if cached_result:
                logger.debug("service_health_cache_hit", service=self.service_name)
                return cached_result

        # Perform health check
        start_time = time.time()
        result = {
            "service": self.service_name,
            "timestamp": time.time(),
            "status": "unknown",
            "latency_ms": None,
            "error": None,
        }

        try:
            # Update health URL if namespace provided
            if namespace:
                self.health_url = get_health_check_url(self.service_name, namespace)

            # Make health check request
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(self.health_url)

                latency_ms = (time.time() - start_time) * 1000
                duration_seconds = latency_ms / 1000.0

                # Record metrics
                status_str = "healthy" if response.status_code == 200 else "unhealthy"
                service_health_checks_total.labels(
                    service=self.service_name, status=status_str, check_type="http"
                ).inc()

                service_health_check_duration_seconds.labels(
                    service=self.service_name, check_type="http"
                ).observe(duration_seconds)

                if response.status_code == 200:
                    result["status"] = "healthy"
                    result["latency_ms"] = round(latency_ms, 2)
                    # Set health status gauge
                    service_health_status.labels(service=self.service_name).set(1)

                    # Try to parse response JSON
                    try:
                        health_data = response.json()
                        result["details"] = health_data
                    except:
                        pass
                else:
                    result["status"] = "unhealthy"
                    result["latency_ms"] = round(latency_ms, 2)
                    result["error"] = f"HTTP {response.status_code}"

        except httpx.TimeoutException:
            result["status"] = "unhealthy"
            result["error"] = "Timeout"
            latency_ms = (time.time() - start_time) * 1000
            duration_seconds = latency_ms / 1000.0
            result["latency_ms"] = round(latency_ms, 2)

            # Record error metrics
            service_health_checks_total.labels(
                service=self.service_name, status="unhealthy", check_type="http"
            ).inc()

            service_health_check_duration_seconds.labels(
                service=self.service_name, check_type="http"
            ).observe(duration_seconds)

            # Set health status gauge to 0 (unhealthy)
            service_health_status.labels(service=self.service_name).set(0)

        except httpx.RequestError as e:
            result["status"] = "unhealthy"
            result["error"] = str(e)
            latency_ms = (time.time() - start_time) * 1000
            duration_seconds = latency_ms / 1000.0
            result["latency_ms"] = round(latency_ms, 2)

            # Record error metrics
            service_health_checks_total.labels(
                service=self.service_name, status="unhealthy", check_type="http"
            ).inc()

            service_health_check_duration_seconds.labels(
                service=self.service_name, check_type="http"
            ).observe(duration_seconds)

            # Set health status gauge to 0 (unhealthy)
            service_health_status.labels(service=self.service_name).set(0)

        except Exception as e:
            result["status"] = "unknown"
            result["error"] = str(e)
            latency_ms = (time.time() - start_time) * 1000
            duration_seconds = latency_ms / 1000.0
            result["latency_ms"] = round(latency_ms, 2)

            # Record error metrics
            service_health_checks_total.labels(
                service=self.service_name, status="unknown", check_type="http"
            ).inc()

            service_health_check_duration_seconds.labels(
                service=self.service_name, check_type="http"
            ).observe(duration_seconds)

            # Set health status gauge to 0 (unhealthy)
            service_health_status.labels(service=self.service_name).set(0)

        # Cache result
        if use_cache:
            cache_key = f"service_health:{self.service_name}"
            cache.set(cache_key, result, timeout=self.cache_ttl)

        logger.debug(
            "service_health_check",
            service=self.service_name,
            status=result["status"],
            latency_ms=result["latency_ms"],
        )

        return result

    def is_healthy(self, use_cache: bool = True, namespace: str | None = None) -> bool:
        """
        Check if service is healthy.

        Args:
            use_cache: Whether to use cached results
            namespace: Kubernetes namespace (optional)

        Returns:
            True if service is healthy, False otherwise
        """
        result = self.check_health(use_cache=use_cache, namespace=namespace)
        return result["status"] == "healthy"


class ServiceHealthMonitor:
    """
    Monitor health of multiple services.

    Provides batch health checking and monitoring capabilities.
    """

    def __init__(self, timeout: float = 5.0, cache_ttl: int = 30):
        """
        Initialize service health monitor.

        Args:
            timeout: Health check timeout in seconds
            cache_ttl: Cache TTL for health check results in seconds
        """
        self.timeout = timeout
        self.cache_ttl = cache_ttl

    def check_all_services(
        self,
        service_names: list[str] | None = None,
        use_cache: bool = True,
        namespace: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        """
        Check health of multiple services.

        Args:
            service_names: List of service names (default: all registered services)
            use_cache: Whether to use cached results
            namespace: Kubernetes namespace (optional)

        Returns:
            Dictionary mapping service names to health check results
        """
        if service_names is None:
            service_names = ServiceRegistry.list_services()

        results = {}

        for service_name in service_names:
            try:
                health_check = ServiceHealthCheck(
                    service_name=service_name, timeout=self.timeout, cache_ttl=self.cache_ttl
                )
                results[service_name] = health_check.check_health(
                    use_cache=use_cache, namespace=namespace
                )
            except Exception as e:
                logger.error(
                    "service_health_check_error", service=service_name, error=str(e), exc_info=True
                )
                results[service_name] = {
                    "service": service_name,
                    "status": "unknown",
                    "error": str(e),
                    "timestamp": time.time(),
                }

        return results

    def get_healthy_services(
        self,
        service_names: list[str] | None = None,
        use_cache: bool = True,
        namespace: str | None = None,
    ) -> list[str]:
        """
        Get list of healthy services.

        Args:
            service_names: List of service names (default: all registered services)
            use_cache: Whether to use cached results
            namespace: Kubernetes namespace (optional)

        Returns:
            List of healthy service names
        """
        results = self.check_all_services(
            service_names=service_names, use_cache=use_cache, namespace=namespace
        )

        return [
            service_name
            for service_name, result in results.items()
            if result.get("status") == "healthy"
        ]

    def get_unhealthy_services(
        self,
        service_names: list[str] | None = None,
        use_cache: bool = True,
        namespace: str | None = None,
    ) -> list[str]:
        """
        Get list of unhealthy services.

        Args:
            service_names: List of service names (default: all registered services)
            use_cache: Whether to use cached results
            namespace: Kubernetes namespace (optional)

        Returns:
            List of unhealthy service names
        """
        results = self.check_all_services(
            service_names=service_names, use_cache=use_cache, namespace=namespace
        )

        return [
            service_name
            for service_name, result in results.items()
            if result.get("status") != "healthy"
        ]


# Convenience functions
def check_service_health(
    service_name: str, timeout: float = 5.0, use_cache: bool = True, namespace: str | None = None
) -> dict[str, Any]:
    """Check health of a single service."""
    health_check = ServiceHealthCheck(service_name, timeout=timeout)
    return health_check.check_health(use_cache=use_cache, namespace=namespace)


def is_service_healthy(
    service_name: str, timeout: float = 5.0, use_cache: bool = True, namespace: str | None = None
) -> bool:
    """Check if a service is healthy."""
    health_check = ServiceHealthCheck(service_name, timeout=timeout)
    return health_check.is_healthy(use_cache=use_cache, namespace=namespace)


def check_all_services_health(
    service_names: list[str] | None = None,
    timeout: float = 5.0,
    use_cache: bool = True,
    namespace: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Check health of multiple services."""
    monitor = ServiceHealthMonitor(timeout=timeout)
    return monitor.check_all_services(
        service_names=service_names, use_cache=use_cache, namespace=namespace
    )
