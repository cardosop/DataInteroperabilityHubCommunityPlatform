"""
API Gateway Routing Configuration

Provides routing configuration for mapping API paths to backend services.
Uses longest prefix match algorithm for route resolution.
"""
import os
from typing import Optional, Dict
from urllib.parse import urlparse
import structlog

logger = structlog.get_logger(__name__)

# Default route configuration mapping path prefixes to backend service URLs
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
    '/api/v1/lineage': 'http://lineage-service:8004',
    '/api/v1/governance': 'http://governance-service:8005',
    '/api/v1/ingestion': 'http://ingestion-service:8006',
    '/api/v1/versioning': 'http://versioning-service:8007',
    '/api/v1/normalization': 'http://normalization-service:8008',
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
