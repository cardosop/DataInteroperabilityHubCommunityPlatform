"""Phase 109.4 — Nginx configuration validation.

Validates security headers, CSP, and configuration structure.
Does NOT require nginx to be running — parses config files directly.
"""
import os
import re
import pytest

NGINX_CONF = os.path.join(
    os.path.dirname(__file__), "..", "..", "frontend", "nginx.conf"
)
NGINX_TEST_CONF = os.path.join(
    os.path.dirname(__file__), "..", "..", "frontend", "nginx.test.conf"
)


@pytest.fixture
def nginx_config():
    """Load nginx.conf content."""
    assert os.path.exists(NGINX_CONF), f"nginx.conf not found at {NGINX_CONF}"
    with open(NGINX_CONF) as f:
        return f.read()


@pytest.fixture
def nginx_test_config():
    """Load nginx.test.conf content."""
    if not os.path.exists(NGINX_TEST_CONF):
        pytest.skip("nginx.test.conf not found")
    with open(NGINX_TEST_CONF) as f:
        return f.read()


class TestNginxSecurityHeaders:
    """Validate security headers in nginx.conf."""

    def test_x_frame_options_deny(self, nginx_config):
        assert "X-Frame-Options" in nginx_config
        assert "DENY" in nginx_config

    def test_x_content_type_options(self, nginx_config):
        assert "X-Content-Type-Options" in nginx_config
        assert "nosniff" in nginx_config

    def test_hsts_header(self, nginx_config):
        assert "Strict-Transport-Security" in nginx_config
        assert "max-age=31536000" in nginx_config
        assert "includeSubDomains" in nginx_config

    def test_referrer_policy(self, nginx_config):
        assert "Referrer-Policy" in nginx_config

    def test_permissions_policy(self, nginx_config):
        assert "Permissions-Policy" in nginx_config
        # Camera and microphone should be disabled
        assert "camera=()" in nginx_config
        assert "microphone=()" in nginx_config

    def test_server_tokens_off(self, nginx_config):
        assert "server_tokens off" in nginx_config

    def test_csp_header_present(self, nginx_config):
        assert "Content-Security-Policy" in nginx_config
        assert "default-src" in nginx_config
        assert "script-src" in nginx_config


class TestNginxConfiguration:
    """Validate nginx.conf structure."""

    def test_gzip_enabled(self, nginx_config):
        assert "gzip on" in nginx_config

    def test_health_proxy(self, nginx_config):
        assert "location /health" in nginx_config

    def test_api_proxy(self, nginx_config):
        assert "location /api" in nginx_config

    def test_websocket_upgrade(self, nginx_config):
        assert "Upgrade" in nginx_config
        assert "Connection" in nginx_config

    def test_index_html_no_cache(self, nginx_config):
        assert "no-cache" in nginx_config or "no-store" in nginx_config

    def test_static_assets_cached(self, nginx_config):
        assert "immutable" in nginx_config or "max-age" in nginx_config


class TestNginxTestConfig:
    """Validate nginx.test.conf differences."""

    def test_test_config_uses_test_service(self, nginx_test_config):
        assert "api-service-test" in nginx_test_config

    def test_test_config_csp_report_only(self, nginx_test_config):
        assert "Report-Only" in nginx_test_config or "report-only" in nginx_test_config.lower()
