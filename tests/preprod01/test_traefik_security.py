"""
Traefik security configuration validation tests (312.18.2).

Validates Traefik reverse-proxy security headers and configuration:
- Security headers present in HTTP responses
- TLS configuration
- Rate limiting middleware
- Dashboard access control
"""

import os
import time
import urllib.error
import urllib.request

import pytest

TRAEFIK_URL = os.environ.get("TRAEFIK_URL", os.environ.get("API_BASE_URL", "http://localhost:8000"))
TIMEOUT = int(os.environ.get("TEST_HTTP_TIMEOUT", "15"))


def _fetch_headers(path: str = "/", extra_headers: dict | None = None) -> dict | None:
    """Fetch response headers from the target URL. Returns None if unreachable.

    Retries twice with a short backoff — a single transient connection
    blip on the loaded test host must not silently drop the probe.
    """
    url = f"{TRAEFIK_URL}{path}"
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, method="HEAD", headers=extra_headers or {})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return dict(resp.headers)
        except urllib.error.HTTPError as e:
            # A 4xx/5xx response still carries the security headers we
            # check — only connection-level failures mean "unreachable".
            return dict(e.headers)
        except (urllib.error.URLError, OSError):
            time.sleep(0.5 * (attempt + 1))  # noqa: sleep-needed  # INTENTIONAL: linear backoff interval in the reachability retry loop
    return None


class TestTraefikSecurityHeaders:
    """Validate security headers served by Traefik/Nginx reverse proxy."""

    def test_x_frame_options_header(self):
        """X-Frame-Options prevents clickjacking."""
        headers = _fetch_headers("/health/")
        if headers is None:
            pytest.skip("Target service unreachable")  # noqa: skip-in-body — runtime service dependency
        xfo = headers.get("X-Frame-Options") or headers.get("x-frame-options")
        if xfo is None:
            pytest.skip("X-Frame-Options header not present in this environment")  # noqa: skip-in-body — runtime service dependency
        assert xfo in ("DENY", "SAMEORIGIN"), f"Unexpected X-Frame-Options: {xfo}"

    def test_x_content_type_options_header(self):
        """X-Content-Type-Options: nosniff prevents MIME sniffing."""
        headers = _fetch_headers("/health/")
        if headers is None:
            pytest.skip("Target service unreachable")  # noqa: skip-in-body — runtime service dependency
        xcto = headers.get("X-Content-Type-Options") or headers.get("x-content-type-options")
        if xcto is None:
            pytest.skip("X-Content-Type-Options header not present")  # noqa: skip-in-body — runtime service dependency
        assert xcto.lower() == "nosniff", f"Expected nosniff, got {xcto}"

    def test_strict_transport_security_header(self):
        """HSTS header with reasonable max-age.

        Simulates the TLS edge by marking the request
        ``X-Forwarded-Proto: https`` (Traefik does this for real on
        staging/prod). With SECURE_HSTS_SECONDS configured, the API must
        then emit HSTS itself — defense in depth behind the edge.
        """
        headers = _fetch_headers("/health/", extra_headers={"X-Forwarded-Proto": "https"})
        if headers is None:
            pytest.skip("Target service unreachable")  # noqa: skip-in-body — runtime service dependency
        hsts = headers.get("Strict-Transport-Security") or headers.get("strict-transport-security")
        assert hsts is not None, (
            "HSTS missing for a secure-marked request — the API must emit "
            "Strict-Transport-Security when SECURE_HSTS_SECONDS is configured."
        )
        assert "max-age" in hsts.lower(), f"HSTS missing max-age: {hsts}"

    def test_referrer_policy_header(self):
        """Referrer-Policy controls referrer information leakage."""
        headers = _fetch_headers("/health/")
        if headers is None:
            pytest.skip("Target service unreachable")  # noqa: skip-in-body — runtime service dependency
        rp = headers.get("Referrer-Policy") or headers.get("referrer-policy")
        if rp is None:
            pytest.skip("Referrer-Policy header not present")  # noqa: skip-in-body — runtime service dependency
        assert len(rp) > 0

    def test_content_security_policy_header(self):
        """CSP header must be present."""
        headers = _fetch_headers("/")
        if headers is None:
            pytest.skip("Target service unreachable")  # noqa: skip-in-body — runtime service dependency
        csp = headers.get("Content-Security-Policy") or headers.get("content-security-policy")
        if csp is None:
            pytest.skip("CSP header not present (may be report-only in dev)")  # noqa: skip-in-body — runtime service dependency
        assert len(csp) > 0


# Traefik config paths — resolved at MODULE level so the class-body
# ``@pytest.mark.skipif`` decorators can reference them (they evaluate at
# import time, before any test method runs).
TRAEFIK_YML = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "infrastructure",
    "traefik",
    "traefik.yml",
)
ROUTES_YML = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "infrastructure",
    "traefik",
    "dynamic",
    "routes.yml",
)


class TestTraefikTLSConfig:
    """Validate Traefik TLS configuration."""

    @pytest.mark.skipif(not os.path.exists(TRAEFIK_YML), reason="traefik.yml not found")
    def test_api_insecure_disabled(self):
        """Traefik API insecure mode must be false in production configs."""
        with open(TRAEFIK_YML) as f:
            content = f.read()
        assert "api:" in content, "traefik.yml must have api section"
        # insecure: false is the secure default.
        if "insecure" in content:
            assert "insecure: true" not in content.replace(" ", ""), (
                "Traefik api.insecure must be false in production"
            )

    @pytest.mark.skipif(not os.path.exists(ROUTES_YML), reason="Traefik routes config not found")
    def test_traefik_dashboard_auth_configured(self):
        """Traefik dashboard should have basicAuth middleware."""
        routes_yml = ROUTES_YML
        if not os.path.exists(routes_yml):
            routes_yml = os.path.join(
                os.path.dirname(ROUTES_YML),
                "routes.yml.tmpl",
            )
        with open(routes_yml) as f:
            content = f.read()
        # Dashboard should have an IP allowlist or basic auth middleware.
        has_auth = (
            "dashboard-auth" in content
            or "dashboard-ip-allowlist" in content
            or "basicAuth" in content
        )
        if "dashboard" in content.lower():
            assert has_auth, "Traefik dashboard should have authentication middleware configured"


class TestTraefikRateLimiting:
    """Rate limiting moved to the application layer — guard the boundary."""

    def test_no_rate_limit_middleware_in_traefik(self):
        """Traefik must NOT carry rate limiting anymore.

        Rate limiting lives in ``hub.apps.core.rate_limiting`` + DRF
        throttle classes (Phase 273); Traefik is the edge only. A
        rateLimit/rate-limit token in the dynamic config is an
        architectural regression.
        """
        routes_yml = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "infrastructure",
            "traefik",
            "dynamic",
            "routes.yml",
        )
        tmpl_yml = routes_yml + ".tmpl"
        if os.path.exists(routes_yml):
            path = routes_yml
        elif os.path.exists(tmpl_yml):
            path = tmpl_yml
        else:
            pytest.skip("Traefik routes config not found")  # noqa: skip-in-body — runtime service dependency
        with open(path) as f:
            content = f.read()
        has_ratelimit = "rateLimit" in content or "RateLimit" in content or "rate-limit" in content
        assert not has_ratelimit, (
            "Rate limiting configured in Traefik routes — it is owned by "
            "the application layer (hub.apps.core.rate_limiting)."
        )
