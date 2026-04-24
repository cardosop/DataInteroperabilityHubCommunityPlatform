"""Phase 109.4 — Nginx configuration validation.

Validates security headers, CSP, and configuration structure.
Does NOT require nginx to be running — parses config files directly.
"""
import base64
import hashlib
import os
import re
import pytest

NGINX_CONF = os.path.join(
    os.path.dirname(__file__), "..", "..", "frontend", "nginx.conf"
)
NGINX_TEST_CONF = os.path.join(
    os.path.dirname(__file__), "..", "..", "frontend", "nginx.test.conf"
)
INDEX_HTML = os.path.join(
    os.path.dirname(__file__), "..", "..", "frontend", "index.html"
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

    def test_csp_connect_src_has_no_double_wildcard_hosts(self, nginx_config):
        """CSP source-expressions allow exactly ONE wildcard at the leftmost
        position. Browsers silently drop entries with two wildcards (e.g.
        ``*.s3.*.amazonaws.com``), which is worse than a missing rule — the
        CSP string looks permissive but regional virtual-hosted S3 URLs are
        BLOCKED at runtime. This test asserts no such entries are present.
        """
        # Find the CSP value (between the first pair of " after Content-Security-Policy)
        m = re.search(
            r'Content-Security-Policy\s+"([^"]+)"', nginx_config
        )
        assert m, "Could not locate Content-Security-Policy value in nginx.conf"
        csp = m.group(1)
        # Look for host tokens with two `*.` segments — that's the invalid form.
        offenders = [
            tok for tok in csp.split()
            if tok.count("*.") >= 2
        ]
        assert not offenders, (
            f"CSP contains hosts with >1 wildcard segment (silently dropped by browsers): "
            f"{offenders}. Use one wildcard at the leftmost position, or enumerate regions."
        )

    def test_csp_script_src_hash_matches_inline_pre_hydration_script(
        self, nginx_config
    ):
        """The synchronous pre-hydration theme script in frontend/index.html
        MUST stay inline (so the theme is applied BEFORE CSS parses — otherwise
        dark-mode users see a light flash on every navigation). CSP covers it
        via a sha256-hash source in script-src. This test recomputes the hash
        from index.html and asserts nginx.conf carries the matching entry, so
        any edit to the inline script without a CSP update fails CI here
        rather than in production via CSP report.
        """
        assert os.path.exists(INDEX_HTML), f"index.html not found at {INDEX_HTML}"
        with open(INDEX_HTML) as f:
            html = f.read()

        # The pre-hydration script is the only <script>...</script> block
        # without a src= or type=module attribute. If more such blocks are
        # added in the future, each needs its own hash; we surface that by
        # matching all inline scripts and computing a hash for each.
        inline_blocks = re.findall(
            r"<script>(.*?)</script>", html, flags=re.DOTALL
        )
        assert inline_blocks, (
            "No inline <script>...</script> blocks found in index.html — "
            "if the pre-hydration theme script was moved, delete the sha256 "
            "hash from nginx.conf:script-src and delete this test."
        )

        for block in inline_blocks:
            digest = hashlib.sha256(block.encode("utf-8")).digest()
            expected_hash = "sha256-" + base64.b64encode(digest).decode("ascii")
            assert f"'{expected_hash}'" in nginx_config, (
                f"Inline <script> in frontend/index.html has hash {expected_hash} "
                f"but nginx.conf script-src does not list it. Update the "
                f"Content-Security-Policy header at frontend/nginx.conf (or "
                f"move the script to a separate file and drop the hash)."
            )


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
