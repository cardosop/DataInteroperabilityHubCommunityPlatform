"""
Traefik rate-limiting boundary guard (was 280.A.6.4 — retired).

Rate limiting moved OUT of Traefik into the application layer
(``hub.apps.core.rate_limiting`` + DRF throttle classes, Phase 273;
``RATE_LIMIT_ENABLED`` setting). Traefik is now the edge only: TLS
termination, load balancing, CORS and tracing — see the comment block
in infrastructure/traefik/dynamic/routes.yml.

These tests guard the boundary: a ``rateLimit`` middleware (or a router
referencing one) in any Traefik config is an architectural regression
and must fail.

Validates across all Traefik config files:
- infrastructure/traefik/dynamic/routes.yml.tmpl (production template)
- infrastructure/traefik/dynamic/routes.yml (static/development)
- k8s/api-gateway/traefik/configmap.yaml (Kubernetes deployment)

Does NOT mock — validates real configuration files.
"""

import os
import re

import pytest
import yaml

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

ROUTES_TMPL = os.path.join(PROJECT_ROOT, "infrastructure", "traefik", "dynamic", "routes.yml.tmpl")
ROUTES_YML = os.path.join(PROJECT_ROOT, "infrastructure", "traefik", "dynamic", "routes.yml")
K8S_CONFIGMAP = os.path.join(PROJECT_ROOT, "k8s", "api-gateway", "traefik", "configmap.yaml")

# Where the capability actually lives now.
APP_RATE_LIMITING_DIR = os.path.join(PROJECT_ROOT, "hub", "apps", "core", "rate_limiting")


def _load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f.read())


def _load_yaml_from_embedded(path):
    """Load YAML embedded inside a Kubernetes ConfigMap data key."""
    with open(path) as f:
        content = f.read()
    # Extract the routes.yml embedded YAML from the ConfigMap
    match = re.search(r"routes\.yml:\s*\|\n(.*?)(?=^\S|\Z)", content, re.DOTALL)
    if match:
        return yaml.safe_load(match.group(1))
    return None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def routes_tmpl():
    """Parsed routes.yml.tmpl (production template)."""
    assert os.path.exists(ROUTES_TMPL), f"Missing {ROUTES_TMPL}"
    return _load_yaml(ROUTES_TMPL)


@pytest.fixture(scope="module")
def routes_yml():
    """Parsed routes.yml (static/development)."""
    assert os.path.exists(ROUTES_YML), f"Missing {ROUTES_YML}"
    return _load_yaml(ROUTES_YML)


@pytest.fixture(scope="module")
def k8s_routes():
    """Parsed routes from K8s ConfigMap."""
    assert os.path.exists(K8S_CONFIGMAP), f"Missing {K8S_CONFIGMAP}"
    routes = _load_yaml_from_embedded(K8S_CONFIGMAP)
    assert routes is not None, "Failed to extract routes.yml from ConfigMap"
    return routes


# ---------------------------------------------------------------------------
# Boundary: no rate-limit middleware in Traefik
# ---------------------------------------------------------------------------


class TestNoRateLimitMiddlewareInTraefik:
    """Rate limiting is app-layer — Traefik must not define it."""

    def _get_middlewares(self, routes_data):
        """Extract middlewares dict from routes data."""
        return routes_data.get("http", {}).get("middlewares", {})

    @pytest.mark.parametrize(
        ("config_name", "loader"),
        [
            ("routes.yml.tmpl", "routes_tmpl"),
            ("routes.yml", "routes_yml"),
            ("K8s ConfigMap", "k8s_routes"),
        ],
    )
    def test_no_rate_limit_middleware(self, request, config_name, loader):
        """No middleware named 'rate-limit' and no rateLimit block allowed."""
        routes = request.getfixturevalue(loader)
        middlewares = self._get_middlewares(routes)

        assert "rate-limit" not in middlewares, (
            f"[{config_name}] 'rate-limit' middleware in Traefik — rate limiting "
            "is owned by the application layer (hub.apps.core.rate_limiting)."
        )
        for middleware_name, middleware_config in middlewares.items():
            assert "rateLimit" not in middleware_config, (
                f"[{config_name}] Middleware {middleware_name} defines rateLimit — "
                "rate limiting is owned by the application layer."
            )

    @pytest.mark.parametrize(
        ("config_name", "loader"),
        [
            ("routes.yml.tmpl", "routes_tmpl"),
            ("routes.yml", "routes_yml"),
            ("K8s ConfigMap", "k8s_routes"),
        ],
    )
    def test_no_router_references_rate_limit(self, request, config_name, loader):
        """No router may reference a rate-limit middleware."""
        routes = request.getfixturevalue(loader)
        routers = routes.get("http", {}).get("routers", {})

        for router_name, router_config in routers.items():
            middlewares = router_config.get("middlewares", []) or []
            assert "rate-limit" not in middlewares, (
                f"[{config_name}] Router '{router_name}' references rate-limit "
                f"middleware. Current middlewares: {middlewares}"
            )

    def test_app_layer_owns_rate_limiting(self):
        """The rate-limiting implementation lives in the app layer."""
        assert os.path.isdir(APP_RATE_LIMITING_DIR), (
            "hub/apps/core/rate_limiting missing — the app-layer rate-limiting "
            "module (Phase 273) should exist where the Traefik middleware was "
            "retired."
        )


# ---------------------------------------------------------------------------
# Cross-file consistency (all three configs consistently rate-limit-free)
# ---------------------------------------------------------------------------


class TestRateLimitCrossFileConsistency:
    """All Traefik config files must consistently carry NO rate limiting."""

    def test_absent_consistently_across_all_files(self, routes_tmpl, routes_yml, k8s_routes):
        for name, routes in [("tmpl", routes_tmpl), ("yml", routes_yml), ("k8s", k8s_routes)]:
            middlewares = routes.get("http", {}).get("middlewares", {})
            assert "rate-limit" not in middlewares, (
                f"[{name}] has a rate-limit middleware while others do not — "
                "rate limiting must stay in the application layer everywhere."
            )


# ---------------------------------------------------------------------------
# Raw file content checks (YAML parse-independent)
# ---------------------------------------------------------------------------


class TestRateLimitRawFileChecks:
    """Raw content checks catch commented-out or stale middleware remnants."""

    @pytest.mark.parametrize(
        ("config_name", "path"),
        [
            ("routes.yml.tmpl", ROUTES_TMPL),
            ("routes.yml", ROUTES_YML),
            ("K8s ConfigMap", K8S_CONFIGMAP),
        ],
    )
    def test_rate_limit_token_absent(self, config_name, path):
        """The literal 'rate-limit:' middleware header must not appear."""
        with open(path) as f:
            content = f.read()
        assert not re.search(r"^\s+rate-limit:\s*$", content, re.MULTILINE), (
            f"rate-limit middleware (active or commented) found in {config_name} — "
            "rate limiting is owned by the application layer."
        )

    def test_no_rate_limit_reference_in_router_middleware_lists(self):
        """Raw-text check: no router middleware list mentions rate-limit."""
        with open(ROUTES_TMPL) as f:
            content = f.read()
        for name in ["api-gateway", "api-gateway-host", "frontend"]:
            pattern = rf"^\s{{4}}{re.escape(name)}:\s*$"
            match = re.search(pattern, content, re.MULTILINE)
            if match:
                start = match.start()
                block = content[start : start + 800]
                assert "rate-limit" not in block, (
                    f"Router {name} block references rate-limit in routes.yml.tmpl"
                )
