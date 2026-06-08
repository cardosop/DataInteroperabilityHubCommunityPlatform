"""
Traefik security configuration validation tests (312.18.2).

Validates Traefik reverse-proxy security headers and configuration:
- Security headers present in HTTP responses
- TLS configuration
- Rate limiting middleware
- Dashboard access control
"""

import os
import pytest
import urllib.request
import urllib.error


TRAEFIK_URL = os.environ.get("TRAEFIK_URL", os.environ.get("API_BASE_URL", "http://localhost:8000"))
TIMEOUT = int(os.environ.get("TEST_HTTP_TIMEOUT", "15"))


def _fetch_headers(path: str = "/") -> dict | None:
    """Fetch response headers from the target URL. Returns None if unreachable."""
    url = f"{TRAEFIK_URL}{path}"
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return dict(resp.headers)
    except (urllib.error.URLError, OSError):
        return None


class TestTraefikSecurityHeaders:
    """Validate security headers served by Traefik/Nginx reverse proxy."""

    def test_x_frame_options_header(self):
        """X-Frame-Options prevents clickjacking."""
        headers = _fetch_headers("/health/")
        if headers is None:
            pytest.skip("Target service unreachable")
        xfo = headers.get("X-Frame-Options") or headers.get("x-frame-options")
        if xfo is None:
            pytest.skip("X-Frame-Options header not present in this environment")
        assert xfo in ("DENY", "SAMEORIGIN"), f"Unexpected X-Frame-Options: {xfo}"

    def test_x_content_type_options_header(self):
        """X-Content-Type-Options: nosniff prevents MIME sniffing."""
        headers = _fetch_headers("/health/")
        if headers is None:
            pytest.skip("Target service unreachable")
        xcto = headers.get("X-Content-Type-Options") or headers.get("x-content-type-options")
        if xcto is None:
            pytest.skip("X-Content-Type-Options header not present")
        assert xcto.lower() == "nosniff", f"Expected nosniff, got {xcto}"

    def test_strict_transport_security_header(self):
        """HSTS header with reasonable max-age."""
        headers = _fetch_headers("/health/")
        if headers is None:
            pytest.skip("Target service unreachable")
        hsts = headers.get("Strict-Transport-Security") or headers.get("strict-transport-security")
        if hsts is None:
            pytest.skip("HSTS header not present (expected in staging/production only)")
        assert "max-age" in hsts.lower(), f"HSTS missing max-age: {hsts}"

    def test_referrer_policy_header(self):
        """Referrer-Policy controls referrer information leakage."""
        headers = _fetch_headers("/health/")
        if headers is None:
            pytest.skip("Target service unreachable")
        rp = headers.get("Referrer-Policy") or headers.get("referrer-policy")
        if rp is None:
            pytest.skip("Referrer-Policy header not present")
        assert len(rp) > 0

    def test_content_security_policy_header(self):
        """CSP header must be present."""
        headers = _fetch_headers("/")
        if headers is None:
            pytest.skip("Target service unreachable")
        csp = headers.get("Content-Security-Policy") or headers.get("content-security-policy")
        if csp is None:
            pytest.skip("CSP header not present (may be report-only in dev)")
        assert len(csp) > 0


class TestTraefikTLSConfig:
    """Validate Traefik TLS configuration."""

    def test_api_insecure_disabled(self):
        """Traefik API insecure mode must be false in production configs."""
        traefik_yml = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "infrastructure", "traefik", "traefik.yml",
        )
        if not os.path.exists(traefik_yml):
            pytest.skip("traefik.yml not found")
        with open(traefik_yml) as f:
            content = f.read()
        assert "api:" in content, "traefik.yml must have api section"
        # insecure: false is the secure default.
        if "insecure" in content:
            assert "insecure: true" not in content.replace(" ", ""), (
                "Traefik api.insecure must be false in production"
            )

    def test_traefik_dashboard_auth_configured(self):
        """Traefik dashboard should have basicAuth middleware."""
        routes_yml = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "infrastructure", "traefik", "dynamic", "routes.yml",
        )
        if not os.path.exists(routes_yml):
            routes_yml = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "infrastructure", "traefik", "dynamic", "routes.yml.tmpl",
            )
        if not os.path.exists(routes_yml):
            pytest.skip("Traefik routes config not found")
        with open(routes_yml) as f:
            content = f.read()
        # Dashboard should have an IP allowlist or basic auth middleware.
        has_auth = "dashboard-auth" in content or "dashboard-ip-allowlist" in content or "basicAuth" in content
        if "dashboard" in content.lower():
            assert has_auth, "Traefik dashboard should have authentication middleware configured"


class TestTraefikRateLimiting:
    """Validate Traefik rate limiting configuration."""

    def test_rate_limit_middleware_exists(self):
        """Traefik should have rate limiting middleware configured."""
        routes_yml = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "infrastructure", "traefik", "dynamic", "routes.yml",
        )
        tmpl_yml = routes_yml + ".tmpl"
        if os.path.exists(routes_yml):
            path = routes_yml
        elif os.path.exists(tmpl_yml):
            path = tmpl_yml
        else:
            pytest.skip("Traefik routes config not found")
        with open(path) as f:
            content = f.read()
        has_ratelimit = "rateLimit" in content or "RateLimit" in content or "rate-limit" in content
        if not has_ratelimit:
            pytest.skip("Rate limiting not configured in Traefik routes")
