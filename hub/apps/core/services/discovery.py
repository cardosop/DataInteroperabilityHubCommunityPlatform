"""
Service Discovery Module

Provides centralized service discovery for the service layer.
Supports Docker Compose (DNS-based) and Kubernetes (DNS-based) environments.
"""

import os
from functools import lru_cache

import structlog
from django.conf import settings

logger = structlog.get_logger(__name__)


class ServiceRegistry:
    """
    Service registry for service discovery.

    Provides a centralized way to discover and configure service URLs
    across different deployment environments (Docker Compose, Kubernetes).
    """

    # Service registry - maps service names to their configuration
    _services: dict[str, dict[str, any]] = {
        # Core Services
        "api-service": {"port": 8000, "health_path": "/health", "env_var": "API_SERVICE_URL"},
        "contract-service": {
            "port": 8001,
            "health_path": "/health",
            "env_var": "CONTRACT_SERVICE_URL",
        },
        "asset-service": {"port": 8002, "health_path": "/health", "env_var": "ASSET_SERVICE_URL"},
        "dataset-service": {
            "port": 8003,
            "health_path": "/health",
            "env_var": "DATASET_SERVICE_URL",
        },
        "lineage-service": {
            "port": 8004,
            "health_path": "/health",
            "env_var": "LINEAGE_SERVICE_URL",
        },
        "governance-service": {
            "port": 8005,
            "health_path": "/health",
            "env_var": "GOVERNANCE_SERVICE_URL",
        },
        "ingestion-service": {
            "port": 8006,
            "health_path": "/health",
            "env_var": "INGESTION_SERVICE_URL",
        },
        "versioning-service": {
            "port": 8007,
            "health_path": "/health",
            "env_var": "VERSIONING_SERVICE_URL",
        },
        "normalization-service": {
            "port": 8008,
            "health_path": "/health",
            "env_var": "NORMALIZATION_SERVICE_URL",
        },
        # Supporting Services (Phase 59: removed dead search/observability/webhook services)
        "semantic-service": {
            "port": 8081,
            "health_path": "/health",
            "env_var": "SEMANTIC_SERVICE_URL",
        },
        "dq-service": {"port": 8083, "health_path": "/health", "env_var": "DQ_SERVICE_URL"},
        "compliance-service": {
            "port": 8082,
            "health_path": "/health",
            "env_var": "COMPLIANCE_SERVICE_URL",
        },
        "datacontract-service": {
            "port": 8080,
            "health_path": "/health",
            "env_var": "DATACONTRACT_SERVICE_URL",
        },
        "prefect-integration-service": {
            "port": 8084,
            "health_path": "/health",
            "env_var": "PREFECT_INTEGRATION_SERVICE_URL",
        },
        # Infrastructure Services (Phase 59: removed dead workflow-engine/registry/event-bus/schema-registry)
    }

    @classmethod
    def register_service(
        cls, service_name: str, port: int, health_path: str = "/health", env_var: str | None = None
    ):
        """
        Register a new service in the registry.

        Args:
            service_name: Service name (e.g., 'my-service')
            port: Service port
            health_path: Health check path
            env_var: Environment variable name for service URL (optional)
        """
        cls._services[service_name] = {
            "port": port,
            "health_path": health_path,
            "env_var": env_var or f"{service_name.upper().replace('-', '_')}_SERVICE_URL",
        }

    @classmethod
    def get_service_config(cls, service_name: str) -> dict[str, any] | None:
        """
        Get service configuration.

        Args:
            service_name: Service name

        Returns:
            Service configuration dictionary or None if not found
        """
        return cls._services.get(service_name)

    @classmethod
    def list_services(cls) -> list[str]:
        """
        List all registered services.

        Returns:
            List of service names
        """
        return list(cls._services.keys())

    @classmethod
    @lru_cache(maxsize=128)
    def get_service_url(cls, service_name: str, namespace: str | None = None) -> str:
        """
        Get service URL for a given service name.

        Supports multiple environments:
        - Docker Compose: Uses service name directly
        - Kubernetes: Uses service name with namespace
        - Environment variable override: Checks env var first

        Args:
            service_name: Service name (e.g., 'contract-service')
            namespace: Kubernetes namespace (optional)

        Returns:
            Service URL (e.g., 'http://contract-service:8001')
        """
        # Check environment variable first
        config = cls.get_service_config(service_name)
        env_var = None
        if config:
            env_var = config.get("env_var")
            if env_var:
                env_url = os.getenv(env_var)
                if env_url:
                    logger.debug(
                        "service_url_from_env", service=service_name, env_var=env_var, url=env_url
                    )
                    return env_url

        # Check Django settings (only if env_var was found in config)
        if env_var and hasattr(settings, env_var):
            settings_url = getattr(settings, env_var)
            if settings_url:
                logger.debug(
                    "service_url_from_settings",
                    service=service_name,
                    setting=env_var,
                    url=settings_url,
                )
                return settings_url

        # Determine environment
        environment = cls._detect_environment()

        if environment == "kubernetes":
            # Kubernetes DNS format
            if namespace:
                url = f"http://{service_name}.{namespace}.svc.cluster.local"
            else:
                # Try to get namespace from environment
                k8s_namespace = os.getenv("KUBERNETES_NAMESPACE", "default")
                url = f"http://{service_name}.{k8s_namespace}.svc.cluster.local"

            # Add port if configured
            if config and config.get("port"):
                url = f"{url}:{config['port']}"
        else:
            # Docker Compose - use service name directly
            url = f"http://{service_name}"

            # Add port if configured
            if config and config.get("port"):
                url = f"{url}:{config['port']}"

        logger.debug(
            "service_url_discovered", service=service_name, environment=environment, url=url
        )

        return url

    @classmethod
    def get_health_check_url(cls, service_name: str, namespace: str | None = None) -> str:
        """
        Get health check URL for a service.

        Args:
            service_name: Service name
            namespace: Kubernetes namespace (optional)

        Returns:
            Health check URL
        """
        base_url = cls.get_service_url(service_name, namespace)
        config = cls.get_service_config(service_name)
        health_path = config.get("health_path", "/health") if config else "/health"

        # Remove trailing slash from base_url if present
        base_url = base_url.rstrip("/")

        return f"{base_url}{health_path}"

    @classmethod
    def _detect_environment(cls) -> str:
        """
        Detect deployment environment.

        Returns:
            Environment name ('kubernetes', 'docker-compose', or 'local')
        """
        # Check for Kubernetes environment variables
        if os.getenv("KUBERNETES_SERVICE_HOST"):
            return "kubernetes"

        # Check for Docker Compose environment
        if os.getenv("COMPOSE_PROJECT_NAME"):
            return "docker-compose"

        # Default to local
        return "local"


# Convenience functions
def get_service_url(service_name: str, namespace: str | None = None) -> str:
    """Get service URL for a service."""
    return ServiceRegistry.get_service_url(service_name, namespace)


def get_health_check_url(service_name: str, namespace: str | None = None) -> str:
    """Get health check URL for a service."""
    return ServiceRegistry.get_health_check_url(service_name, namespace)


def list_services() -> list[str]:
    """List all registered services."""
    return ServiceRegistry.list_services()


def register_service(
    service_name: str, port: int, health_path: str = "/health", env_var: str | None = None
):
    """Register a new service."""
    ServiceRegistry.register_service(service_name, port, health_path, env_var)
