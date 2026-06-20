"""
Service Availability Checker

Provides utilities to check service availability, log service status,
and handle service unavailability gracefully in tests and production.
"""

import logging
import time

from django.conf import settings
from django.core.cache import cache

from .health_client import ServiceHealthClient

logger = logging.getLogger(__name__)


class ServiceAvailabilityChecker:
    """
    Service availability checker with logging and caching.
    """

    def __init__(self, cache_ttl: int = 60):
        """
        Initialize service availability checker.

        Args:
            cache_ttl: Cache TTL in seconds for availability checks
        """
        self.cache_ttl = cache_ttl
        self._availability_cache: dict[str, tuple[bool, float]] = {}

    def check_service_availability(
        self, service_name: str, service_url: str, health_path: str = "/health", timeout: int = 5
    ) -> tuple[bool, str | None]:
        """
        Check if a service is available and healthy.

        Args:
            service_name: Name of the service (for logging)
            service_url: Base URL of the service
            health_path: Health check endpoint path
            timeout: Timeout in seconds

        Returns:
            Tuple of (is_available: bool, error_message: Optional[str])
        """
        # Check cache first
        cache_key = f"service_availability:{service_name}:{service_url}"
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            is_available, cached_time = cached_result
            # Use cached result if less than cache_ttl seconds old
            if time.time() - cached_time < self.cache_ttl:
                logger.debug(
                    f"Service {service_name} availability (cached): {is_available}",
                    extra={
                        "service_name": service_name,
                        "service_url": service_url,
                        "is_available": is_available,
                        "cached": True,
                    },
                )
                return is_available, None if is_available else "Service unavailable (cached)"

        # Perform actual health check using ServiceHealthClient
        health_client = ServiceHealthClient(timeout=timeout)
        try:
            is_healthy, status_message = health_client.check_health(
                service_url=service_url, health_path=health_path, timeout=timeout
            )

            if is_healthy:
                # Cache successful result
                cache.set(cache_key, (True, time.time()), self.cache_ttl)
                logger.info(
                    f"Service {service_name} is available and healthy",
                    extra={
                        "service_name": service_name,
                        "service_url": service_url,
                        "health_path": health_path,
                        "status_message": status_message,
                        "is_available": True,
                    },
                )
                return True, None
            else:
                error_msg = f"Service {service_name} is unavailable: {status_message}"
                cache.set(cache_key, (False, time.time()), self.cache_ttl)
                logger.warning(
                    error_msg,
                    extra={
                        "service_name": service_name,
                        "service_url": service_url,
                        "health_path": health_path,
                        "status_message": status_message,
                        "is_available": False,
                    },
                )
                return False, error_msg

        except Exception as e:
            error_msg = f"Service {service_name} health check failed: {e}"
            cache.set(cache_key, (False, time.time()), self.cache_ttl)
            logger.warning(
                error_msg,
                extra={
                    "service_name": service_name,
                    "service_url": service_url,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "is_available": False,
                },
                exc_info=True,
            )
            return False, error_msg

    def check_all_services(
        self, service_configs: dict[str, dict[str, str]]
    ) -> dict[str, tuple[bool, str | None]]:
        """
        Check availability of multiple services.

        Args:
            service_configs: Dictionary mapping service names to config dicts
                           with 'url' and optionally 'health_path' keys

        Returns:
            Dictionary mapping service names to (is_available, error_message) tuples
        """
        results = {}
        for service_name, config in service_configs.items():
            service_url = config.get("url")
            health_path = config.get("health_path", "/health")
            timeout = config.get("timeout", 5)

            if not service_url:
                logger.warning(
                    f"Service {service_name} has no URL configured",
                    extra={"service_name": service_name},
                )
                results[service_name] = (False, "No URL configured")
                continue

            is_available, error_msg = self.check_service_availability(
                service_name=service_name,
                service_url=service_url,
                health_path=health_path,
                timeout=timeout,
            )
            results[service_name] = (is_available, error_msg)

        return results

    def log_service_status_summary(self, results: dict[str, tuple[bool, str | None]]) -> None:
        """
        Log a summary of service availability status.

        Args:
            results: Dictionary mapping service names to (is_available, error_message) tuples
        """
        available_count = sum(1 for is_avail, _ in results.values() if is_avail)
        total_count = len(results)

        logger.info(
            f"Service availability summary: {available_count}/{total_count} services available",
            extra={
                "available_count": available_count,
                "total_count": total_count,
                "services": {
                    name: {"available": is_avail, "error": error_msg}
                    for name, (is_avail, error_msg) in results.items()
                },
            },
        )

        # Log unavailable services
        unavailable = {
            name: error_msg for name, (is_avail, error_msg) in results.items() if not is_avail
        }
        if unavailable:
            logger.warning(
                f"Unavailable services: {', '.join(unavailable.keys())}",
                extra={"unavailable_services": unavailable, "unavailable_count": len(unavailable)},
            )


# Global instance
_service_checker = ServiceAvailabilityChecker()


def check_service_availability(
    service_name: str, service_url: str, health_path: str = "/health", timeout: int = 5
) -> tuple[bool, str | None]:
    """
    Convenience function to check service availability.

    Args:
        service_name: Name of the service
        service_url: Base URL of the service
        health_path: Health check endpoint path
        timeout: Timeout in seconds

    Returns:
        Tuple of (is_available: bool, error_message: Optional[str])
    """
    return _service_checker.check_service_availability(
        service_name=service_name, service_url=service_url, health_path=health_path, timeout=timeout
    )


def get_all_service_configs() -> dict[str, dict[str, str]]:
    """
    Get configuration for all services from settings.

    Returns:
        Dictionary mapping service names to config dicts
    """
    return {
        "dq-service": {
            "url": getattr(settings, "DQ_SERVICE_URL", "http://dq-service:8083"),
            "health_path": "/health",
            "timeout": getattr(settings, "DQ_SERVICE_TIMEOUT", 1800),
        },
        "compliance-service": {
            "url": getattr(settings, "COMPLIANCE_SERVICE_URL", "http://compliance-service:8082"),
            "health_path": "/health",
            "timeout": getattr(settings, "COMPLIANCE_SERVICE_TIMEOUT", 1800),
        },
        "datacontract-service": {
            "url": getattr(
                settings, "DATACONTRACT_CLI_SERVICE_URL", "http://datacontract-service:8080"
            ),
            "health_path": "/health",
            "timeout": getattr(settings, "DATACONTRACT_CLI_TIMEOUT", 60),
        },
        "semantic-service": {
            "url": getattr(settings, "SEMANTIC_SERVICE_URL", "http://semantic-service:8081"),
            "health_path": "/health",
            "timeout": getattr(settings, "SEMANTIC_SERVICE_TIMEOUT", 60),
        },
    }


def check_all_services() -> dict[str, tuple[bool, str | None]]:
    """
    Check availability of all configured services.

    Returns:
        Dictionary mapping service names to (is_available, error_message) tuples
    """
    configs = get_all_service_configs()
    return _service_checker.check_all_services(configs)
