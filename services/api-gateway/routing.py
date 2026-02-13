"""
API Gateway Routing Configuration

Provides routing configuration for mapping API paths to backend services.
Uses longest prefix match algorithm for route resolution.

Health check contract: backends behind the gateway MUST expose a health endpoint.
Default path is /health. Override per host via BACKEND_HEALTH_PATHS if a service
uses a different path (e.g. /healthz).
"""
import os
from typing import Optional, Dict, List, Tuple
from urllib.parse import urlparse
import structlog

logger = structlog.get_logger(__name__)

# Default health endpoint path for all backends. Backends MUST expose this path
# (or the override in BACKEND_HEALTH_PATHS). See API Gateway README for contract.
DEFAULT_HEALTH_PATH = "/health"

# Optional per-host override for health path (hostname -> path). Use when a
# backend exposes health at a different path (e.g. /healthz, /ready).
# Key is hostname only (e.g. "api-service"), value is path (e.g. "/health").
BACKEND_HEALTH_PATHS: Dict[str, str] = {}

# Default route configuration mapping path prefixes to backend service URLs.
# All backends must exist in the deployment (docker-compose). Lineage, governance,
# ingestion, versioning, and normalization are served by Django (api-service);
# no dedicated microservices for these paths in the current deployment.
_DEFAULT_ROUTE_CONFIG: Dict[str, str] = {
    '/api/v1/contracts': 'http://api-service:8000',
    '/api/v1/assets': 'http://api-service:8000',
    '/api/v1/datasets': 'http://api-service:8000',
    '/api/v1/marketplace': 'http://api-service:8000',
    '/api/v1/ai': 'http://api-service:8000',  # Will route to ODH later
    '/api/v1/dq': 'http://dq-service:8083',
    '/api/v1/compliance': 'http://compliance-service:8082',
    '/api/v1/semantic': 'http://semantic-service:8081',
    '/api/v1/search': 'http://search-service:8085',
    '/api/v1/observability': 'http://observability-service:8086',
    '/api/v1/webhooks': 'http://webhook-service:8087',
    '/api/v1/lineage': 'http://api-service:8000',
    '/api/v1/governance': 'http://api-service:8000',
    '/api/v1/ingestion': 'http://api-service:8000',
    '/api/v1/versioning': 'http://api-service:8000',
    '/api/v1/normalization': 'http://api-service:8000',
}

# Load route configuration from environment variables (optional override)
_ROUTE_CONFIG: Dict[str, str] = {}

# Initialize route configuration with environment variable overrides
for route_prefix, default_url in _DEFAULT_ROUTE_CONFIG.items():
    # Environment variable format: API_GATEWAY_ROUTE_<SERVICE_NAME>
    # e.g., API_GATEWAY_ROUTE_CONTRACTS for /api/v1/contracts
    env_key = f"API_GATEWAY_ROUTE_{route_prefix.replace('/api/v1/', '').upper().replace('-', '_')}"
    env_url = os.getenv(env_key)
    _ROUTE_CONFIG[route_prefix] = env_url if env_url else default_url

# Export route configuration
ROUTE_CONFIG = _ROUTE_CONFIG


def validate_route_config(route_config: Dict[str, str]) -> None:
    """
    Validate route configuration.

    Args:
        route_config: Route configuration dictionary mapping path prefixes to URLs

    Raises:
        ValueError: If route configuration is invalid
    """
    if not route_config:
        raise ValueError("Route configuration cannot be empty")

    for route_prefix, url in route_config.items():
        # Validate URL format
        try:
            parsed = urlparse(url)
        except Exception as e:
            raise ValueError(f"Invalid URL for route {route_prefix}: {url}") from e

        # Check protocol
        if parsed.scheme != 'http':
            raise ValueError(f"URL must use http:// protocol for route {route_prefix}: {url}")

        # Check that port is specified (hostname:port)
        if not parsed.port:
            raise ValueError(f"URL must include port for route {route_prefix}: {url}")

        # Check that path prefix starts with /
        if not route_prefix.startswith('/'):
            raise ValueError(f"Route prefix must start with / for route {route_prefix}")


def get_backend_url(path: str) -> Optional[str]:
    """
    Get backend service URL for a given path using longest prefix match.

    Args:
        path: Request path (e.g., '/api/v1/contracts/123')

    Returns:
        Backend service URL or None if no match found
    """
    # Remove query string if present
    path_without_query = path.split('?')[0]

    # Find matching route using longest prefix match
    # Sort routes by prefix length (descending) to match longest first
    matching_routes = [
        (prefix, url) for prefix, url in ROUTE_CONFIG.items()
        if path_without_query.startswith(prefix)
    ]

    if not matching_routes:
        return None

    # Sort by prefix length (descending) to get longest match
    matching_routes.sort(key=lambda x: len(x[0]), reverse=True)

    # Return URL for longest matching prefix
    return matching_routes[0][1]


def _backend_host_from_url(backend_url: str) -> str:
    """Extract hostname from backend URL (e.g. http://api-service:8000 -> api-service)."""
    parsed = urlparse(backend_url)
    return (parsed.hostname or "").strip() or backend_url.split("//")[-1].split(":")[0]


def get_backend_health_path(backend_base_url: str) -> str:
    """
    Return the health endpoint path for a backend. Uses BACKEND_HEALTH_PATHS
    if the host has an override, otherwise DEFAULT_HEALTH_PATH.
    """
    host = _backend_host_from_url(backend_base_url)
    return BACKEND_HEALTH_PATHS.get(host, DEFAULT_HEALTH_PATH)


def get_backend_health_url(backend_base_url: str) -> str:
    """
    Build the full health URL for a backend. Same construction used by
    aggregate health in main.py. No trailing slash on base; path starts with /.
    """
    base = backend_base_url.rstrip("/")
    path = get_backend_health_path(backend_base_url)
    if not path.startswith("/"):
        path = "/" + path
    return f"{base}{path}"


def get_unique_backends_with_health_urls(
    route_config: Optional[Dict[str, str]] = None,
) -> List[Tuple[str, str]]:
    """
    Return list of (service_name, health_url) for each unique backend in
    route_config (default ROUTE_CONFIG). Used by aggregate health endpoint.
    """
    config = route_config or ROUTE_CONFIG
    seen_urls: set = set()
    result: List[Tuple[str, str]] = []
    for backend_url in config.values():
        if backend_url in seen_urls:
            continue
        seen_urls.add(backend_url)
        service_name = _backend_host_from_url(backend_url)
        health_url = get_backend_health_url(backend_url)
        result.append((service_name, health_url))
    return result


# Validate route configuration on module load
try:
    validate_route_config(ROUTE_CONFIG)
    logger.info(
        "route_config_loaded",
        route_count=len(ROUTE_CONFIG),
        routes=list(ROUTE_CONFIG.keys())
    )
except ValueError as e:
    logger.error("route_config_validation_failed", error=str(e))
    raise
