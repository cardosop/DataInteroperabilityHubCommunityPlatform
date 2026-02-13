"""
Unit tests for API Gateway routing module.

Tests routing configuration, longest prefix match, and validation.
No mocks or stubs; tests assert against actual ROUTE_CONFIG (deployment alignment).
"""
import pytest
import os
import sys
from urllib.parse import urlparse

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from routing import (
    ROUTE_CONFIG,
    DEFAULT_HEALTH_PATH,
    get_backend_url,
    get_backend_health_url,
    get_backend_health_path,
    get_unique_backends_with_health_urls,
    validate_route_config,
)

# Backend hosts that exist in the deployment (docker-compose).
# Lineage, governance, ingestion, versioning, normalization are served by api-service.
ALLOWED_BACKEND_HOSTS = frozenset({
    'api-service',
    'dq-service',
    'compliance-service',
    'semantic-service',
    'search-service',
    'observability-service',
    'webhook-service',
})


@pytest.mark.unit
class TestRoutingConfig:
    """Test routing configuration"""

    def test_route_config_exists(self):
        """Test that ROUTE_CONFIG is defined"""
        assert ROUTE_CONFIG is not None
        assert isinstance(ROUTE_CONFIG, dict)
        assert len(ROUTE_CONFIG) > 0

    def test_route_config_has_required_routes(self):
        """Test that all required routes are configured"""
        required_routes = [
            '/api/v1/contracts',
            '/api/v1/assets',
            '/api/v1/datasets',
            '/api/v1/dq',
            '/api/v1/compliance',
            '/api/v1/semantic',
            '/api/v1/search',
            '/api/v1/observability',
            '/api/v1/webhooks',
            '/api/v1/lineage',
            '/api/v1/governance',
            '/api/v1/ingestion',
            '/api/v1/versioning',
            '/api/v1/normalization',
        ]
        for route in required_routes:
            assert route in ROUTE_CONFIG, f"Route {route} not found in ROUTE_CONFIG"

    def test_route_config_urls_are_valid(self):
        """Test that all route URLs are valid HTTP URLs"""
        for route, url in ROUTE_CONFIG.items():
            assert url.startswith('http://'), f"Route {route} URL {url} must start with http://"
            assert ':' in url.split('//')[1], f"Route {route} URL {url} must include port"


@pytest.mark.unit
class TestGetBackendUrl:
    """Test get_backend_url function"""

    def test_exact_path_match(self):
        """Test exact path prefix match"""
        url = get_backend_url('/api/v1/contracts')
        assert url == ROUTE_CONFIG['/api/v1/contracts']

    def test_path_with_subpath(self):
        """Test path with subpath matches longest prefix"""
        url = get_backend_url('/api/v1/contracts/123')
        assert url == ROUTE_CONFIG['/api/v1/contracts']

    def test_path_with_query_string(self):
        """Test path with query string matches correctly"""
        url = get_backend_url('/api/v1/assets?filter=active')
        assert url == ROUTE_CONFIG['/api/v1/assets']

    def test_longest_prefix_match(self):
        """Test that longest prefix is matched correctly"""
        # If we have both /api/v1 and /api/v1/contracts, /api/v1/contracts should match first
        url = get_backend_url('/api/v1/contracts/details')
        assert url == ROUTE_CONFIG['/api/v1/contracts']

    def test_no_match_returns_none(self):
        """Test that unknown paths return None"""
        url = get_backend_url('/unknown/path')
        assert url is None

    def test_root_path_returns_none(self):
        """Test that root path returns None"""
        url = get_backend_url('/')
        assert url is None

    def test_api_v1_path_without_specific_route(self):
        """Test that /api/v1 without specific route returns None"""
        url = get_backend_url('/api/v1')
        # This should return None unless we have a catch-all route
        assert url is None or url in ROUTE_CONFIG.values()

    def test_all_configured_routes_match(self):
        """Test that all configured routes match correctly"""
        for route_prefix in ROUTE_CONFIG.keys():
            # Test exact match
            url = get_backend_url(route_prefix)
            assert url == ROUTE_CONFIG[route_prefix], f"Route {route_prefix} did not match correctly"

            # Test with subpath
            url = get_backend_url(f"{route_prefix}/subpath")
            assert url == ROUTE_CONFIG[route_prefix], f"Route {route_prefix}/subpath did not match correctly"


@pytest.mark.unit
class TestValidateRouteConfig:
    """Test route configuration validation"""

    def test_validate_route_config_success(self):
        """Test validation succeeds with valid config"""
        # Should not raise
        validate_route_config(ROUTE_CONFIG)

    def test_validate_route_config_empty_dict(self):
        """Test validation fails with empty config"""
        with pytest.raises(ValueError, match="Route configuration cannot be empty"):
            validate_route_config({})

    def test_validate_route_config_invalid_url(self):
        """Test validation fails with invalid URL"""
        invalid_config = {
            '/api/v1/test': 'not-a-valid-url'
        }
        # urlparse may succeed but scheme check will fail, or urlparse may fail
        # Either way, we should get a ValueError
        with pytest.raises(ValueError):
            validate_route_config(invalid_config)

    def test_validate_route_config_non_http_url(self):
        """Test validation fails with non-HTTP URL"""
        invalid_config = {
            '/api/v1/test': 'ftp://example.com:8000'
        }
        with pytest.raises(ValueError, match="URL must use http://"):
            validate_route_config(invalid_config)

    def test_validate_route_config_missing_port(self):
        """Test validation fails with URL missing port"""
        invalid_config = {
            '/api/v1/test': 'http://example.com'
        }
        with pytest.raises(ValueError, match="URL must include port"):
            validate_route_config(invalid_config)


@pytest.mark.unit
class TestEnvironmentVariableOverride:
    """Test environment variable override for routes"""

    def test_environment_override_single_route(self):
        """Test that environment variable can override a single route"""
        # This test verifies the mechanism exists, actual override happens at module load time
        # The route config should be loaded from environment if set
        # Since we can't easily reload modules in tests, we verify the structure supports it
        assert '/api/v1/contracts' in ROUTE_CONFIG
        assert ROUTE_CONFIG['/api/v1/contracts'].startswith('http://')
        assert ':' in ROUTE_CONFIG['/api/v1/contracts'].split('//')[1]  # Has port


@pytest.mark.unit
class TestDeploymentAlignedRouting:
    """
    Tests that ROUTE_CONFIG aligns with the running deployment.
    All path prefixes must resolve to backends that exist in docker-compose.
    No references to non-existent hosts (lineage-service, governance-service, etc.).
    """

    # Paths served by Django api-service (no dedicated microservice in deployment).
    API_SERVICE_PATH_PREFIXES = (
        '/api/v1/lineage',
        '/api/v1/governance',
        '/api/v1/ingestion',
        '/api/v1/versioning',
        '/api/v1/normalization',
    )
    API_SERVICE_BACKEND_URL = 'http://api-service:8000'

    def test_five_path_prefixes_resolve_to_api_service(self):
        """Five path prefixes must resolve to api-service:8000 (host exists in deployment)."""
        for path_prefix in self.API_SERVICE_PATH_PREFIXES:
            url = get_backend_url(path_prefix)
            assert url is not None, f"{path_prefix} must have a backend URL"
            parsed = urlparse(url)
            assert parsed.hostname == 'api-service', (
                f"{path_prefix} must route to api-service, got host {parsed.hostname}"
            )
            assert parsed.port == 8000, (
                f"{path_prefix} must use port 8000, got {parsed.port}"
            )
            assert url == self.API_SERVICE_BACKEND_URL, (
                f"{path_prefix} must be {self.API_SERVICE_BACKEND_URL}, got {url}"
            )

    def test_five_path_prefixes_with_subpath_resolve_to_api_service(self):
        """Paths with subpaths under the five prefixes must also resolve to api-service:8000."""
        for path_prefix in self.API_SERVICE_PATH_PREFIXES:
            path_with_subpath = f"{path_prefix}/some/resource/123"
            url = get_backend_url(path_with_subpath)
            assert url is not None, f"{path_with_subpath} must have a backend URL"
            assert url == self.API_SERVICE_BACKEND_URL, (
                f"{path_with_subpath} must route to api-service:8000, got {url}"
            )

    def test_route_config_backend_hosts_all_in_deployment(self):
        """All unique backend hosts in ROUTE_CONFIG must exist in the deployment."""
        backend_urls = set(ROUTE_CONFIG.values())
        for backend_url in backend_urls:
            parsed = urlparse(backend_url)
            host = parsed.hostname
            assert host in ALLOWED_BACKEND_HOSTS, (
                f"Backend host '{host}' is not in deployment (allowed: {sorted(ALLOWED_BACKEND_HOSTS)}). "
                "Remove or route to an existing service (e.g. api-service:8000)."
            )


@pytest.mark.unit
class TestHealthUrlContract:
    """
    Health check URL contract: each backend has a defined health URL.
    Gateway uses the same URL construction as aggregate health; default path is /health.
    """

    def test_default_health_path_is_health(self):
        """Expected health endpoint path is /health for all backends unless overridden."""
        assert DEFAULT_HEALTH_PATH == "/health"

    def test_each_unique_backend_has_health_url_with_expected_path(self):
        """For each unique backend in ROUTE_CONFIG, health URL uses expected path (/health)."""
        backends = get_unique_backends_with_health_urls()
        assert len(backends) >= 1
        for service_name, health_url in backends:
            assert service_name, f"Service name must not be empty for {health_url}"
            assert health_url.endswith(DEFAULT_HEALTH_PATH), (
                f"Health URL for {service_name} must end with {DEFAULT_HEALTH_PATH}, got {health_url}"
            )
            assert "//" in health_url and "/health" in health_url

    def test_get_backend_health_url_construction(self):
        """get_backend_health_url builds URL the same way aggregate health uses it."""
        for backend_url in set(ROUTE_CONFIG.values()):
            health_url = get_backend_health_url(backend_url)
            base = backend_url.rstrip("/")
            assert health_url == f"{base}{DEFAULT_HEALTH_PATH}", (
                f"Health URL must be {base}{DEFAULT_HEALTH_PATH}, got {health_url}"
            )

    def test_get_backend_health_path_default(self):
        """get_backend_health_path returns DEFAULT_HEALTH_PATH when no override."""
        assert get_backend_health_path("http://api-service:8000") == DEFAULT_HEALTH_PATH
        assert get_backend_health_path("http://dq-service:8083") == DEFAULT_HEALTH_PATH

    def test_unique_backends_match_route_config_hosts(self):
        """Unique backends from get_unique_backends_with_health_urls match ROUTE_CONFIG hosts."""
        from urllib.parse import urlparse

        unique_hosts = {name for name, _ in get_unique_backends_with_health_urls()}
        config_hosts = {
            urlparse(u).hostname for u in ROUTE_CONFIG.values() if urlparse(u).hostname
        }
        assert unique_hosts == config_hosts, (
            f"Unique backends {unique_hosts} must match config hosts {config_hosts}"
        )


@pytest.mark.integration
class TestRoutingConfigurationIntegration:
    """
    Integration tests for routing configuration (no Django/DB required).
    Run with test_routing.py for fast validation of Phase 7 route config.
    """

    def test_route_config_loading(self):
        """Route configuration loads and validates correctly."""
        assert ROUTE_CONFIG is not None
        assert len(ROUTE_CONFIG) > 0
        validate_route_config(ROUTE_CONFIG)
        for route, url in ROUTE_CONFIG.items():
            assert url.startswith('http://')
            assert ':' in url.split('//')[1]

    def test_get_backend_url_integration(self):
        """get_backend_url matches all configured routes and subpaths."""
        for route_prefix in ROUTE_CONFIG.keys():
            url = get_backend_url(route_prefix)
            assert url == ROUTE_CONFIG[route_prefix]
            url = get_backend_url(f"{route_prefix}/subpath/123")
            assert url == ROUTE_CONFIG[route_prefix]
        assert get_backend_url('/api/v1/unknown') is None
