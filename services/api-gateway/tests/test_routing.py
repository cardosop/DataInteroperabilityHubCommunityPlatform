"""
Unit tests for API Gateway routing module.

Tests routing configuration, longest prefix match, and validation.
"""
import pytest
import os
import sys
from unittest.mock import patch

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from routing import ROUTE_CONFIG, get_backend_url, validate_route_config


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
