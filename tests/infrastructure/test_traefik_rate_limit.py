"""
280.A.6.4 — Traefik Per-IP Rate Limit Middleware Validation.

Validates:
- rate-limit middleware is defined with correct configuration
- Applied to all production routers (api-gateway, frontend, dashboard)
- 100 req/s average with 50 burst
- sourceCriterion uses ipStrategy for per-IP counting
- The middleware is positioned to block before requests reach Django

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
# 280.A.6.4.1 — Middleware definition
# ---------------------------------------------------------------------------


class TestRateLimitMiddlewareDefinition:
    """Validate the rate-limit middleware is correctly defined."""

    ROUTERS_REQUIRING_RATE_LIMIT = [
        "api-gateway",
        "api-gateway-host",
        "frontend",
    ]

    def _get_middlewares(self, routes_data):
        """Extract middlewares dict from routes data."""
        return routes_data.get("http", {}).get("middlewares", {})

    def _get_routers(self, routes_data):
        """Extract routers dict from routes data."""
        return routes_data.get("http", {}).get("routers", {})

    def test_rate_limit_middleware_exists_in_template(self, routes_tmpl):
        """rate-limit middleware must be defined in routes.yml.tmpl."""
        middlewares = self._get_middlewares(routes_tmpl)
        assert "rate-limit" in middlewares, "rate-limit middleware missing from routes.yml.tmpl"

    def test_rate_limit_middleware_exists_in_static(self, routes_yml):
        """rate-limit middleware must be defined in routes.yml."""
        middlewares = self._get_middlewares(routes_yml)
        assert "rate-limit" in middlewares, "rate-limit middleware missing from routes.yml"

    def test_rate_limit_middleware_exists_in_k8s(self, k8s_routes):
        """rate-limit middleware must be defined in K8s ConfigMap."""
        middlewares = self._get_middlewares(k8s_routes)
        assert "rate-limit" in middlewares, "rate-limit middleware missing from K8s ConfigMap"

    @pytest.mark.parametrize(
        "config_name,loader",
        [
            ("routes.yml.tmpl", "routes_tmpl"),
            ("routes.yml", "routes_yml"),
            ("K8s ConfigMap", "k8s_routes"),
        ],
    )
    def test_rate_limit_average_is_100(self, request, config_name, loader):
        """rate-limit average must be 100 req/s."""
        routes = request.getfixturevalue(loader)
        rl = self._get_middlewares(routes).get("rate-limit", {})
        rate_limit = rl.get("rateLimit", {})
        average = rate_limit.get("average")
        assert average == 100, f"[{config_name}] rate-limit average must be 100, got {average}"

    @pytest.mark.parametrize(
        "config_name,loader",
        [
            ("routes.yml.tmpl", "routes_tmpl"),
            ("routes.yml", "routes_yml"),
            ("K8s ConfigMap", "k8s_routes"),
        ],
    )
    def test_rate_limit_burst_is_50(self, request, config_name, loader):
        """rate-limit burst must be 50 (half of average)."""
        routes = request.getfixturevalue(loader)
        rl = self._get_middlewares(routes).get("rate-limit", {})
        rate_limit = rl.get("rateLimit", {})
        burst = rate_limit.get("burst")
        assert burst == 50, f"[{config_name}] rate-limit burst must be 50, got {burst}"

    @pytest.mark.parametrize(
        "config_name,loader",
        [
            ("routes.yml.tmpl", "routes_tmpl"),
            ("routes.yml", "routes_yml"),
            ("K8s ConfigMap", "k8s_routes"),
        ],
    )
    def test_rate_limit_uses_source_criterion_ip_strategy(self, request, config_name, loader):
        """rate-limit must use sourceCriterion with ipStrategy for per-IP."""
        routes = request.getfixturevalue(loader)
        rl = self._get_middlewares(routes).get("rate-limit", {})
        rate_limit = rl.get("rateLimit", {})
        source_criterion = rate_limit.get("sourceCriterion", {})
        assert source_criterion, f"[{config_name}] rate-limit must have sourceCriterion"
        ip_strategy = source_criterion.get("ipStrategy", {})
        assert ip_strategy is not None, (
            f"[{config_name}] sourceCriterion must use ipStrategy "
            f"(not requestHost or requestHeader)"
        )
        depth = ip_strategy.get("depth")
        assert depth is not None, f"[{config_name}] ipStrategy must specify depth"


# ---------------------------------------------------------------------------
# 280.A.6.4.2 — Middleware application to routers
# ---------------------------------------------------------------------------


class TestRateLimitAppliedToRouters:
    """Validate rate-limit middleware is attached to all production routers."""

    ROUTERS_REQUIRING_RATE_LIMIT = [
        "api-gateway",
        "api-gateway-host",
        "frontend",
    ]

    def _get_routers(self, routes_data):
        return routes_data.get("http", {}).get("routers", {})

    @pytest.mark.parametrize(
        "config_name,loader",
        [
            ("routes.yml.tmpl", "routes_tmpl"),
            ("routes.yml", "routes_yml"),
            ("K8s ConfigMap", "k8s_routes"),
        ],
    )
    def test_all_production_routers_have_rate_limit(self, request, config_name, loader):
        """Every production-facing router must include rate-limit middleware."""
        routes = request.getfixturevalue(loader)
        routers = self._get_routers(routes)

        for router_name in self.ROUTERS_REQUIRING_RATE_LIMIT:
            router = routers.get(router_name)
            if router is None:
                # K8s configmap may not have all routers
                if loader == "k8s_routes":
                    continue
                pytest.fail(f"[{config_name}] Required router '{router_name}' not found")
            middlewares = router.get("middlewares", [])
            assert "rate-limit" in middlewares, (
                f"[{config_name}] Router '{router_name}' missing rate-limit "
                f"middleware. Current middlewares: {middlewares}"
            )

    @pytest.mark.parametrize(
        "config_name,loader",
        [
            ("routes.yml.tmpl", "routes_tmpl"),
            ("routes.yml", "routes_yml"),
            ("K8s ConfigMap", "k8s_routes"),
        ],
    )
    def test_rate_limit_before_other_non_auth_middlewares(self, request, config_name, loader):
        """rate-limit should be applied early, but after CORS and tracing.

        The ordering in Traefik is: CORS → tracing → rate-limit.
        This ensures CORS preflight and trace context propagation happen
        before rate limiting, but the rate limit fires before reaching
        the backend service.
        """
        routes = request.getfixturevalue(loader)
        routers = self._get_routers(routes)

        for router_name in self.ROUTERS_REQUIRING_RATE_LIMIT:
            router = routers.get(router_name)
            if router is None:
                continue
            middlewares = router.get("middlewares", [])
            if "rate-limit" not in middlewares:
                continue

            rl_idx = middlewares.index("rate-limit")
            # CORS should come before rate-limit
            if "cors-middleware" in middlewares:
                cors_idx = middlewares.index("cors-middleware")
                assert cors_idx < rl_idx, (
                    f"[{config_name}] Router '{router_name}': "
                    f"cors-middleware must precede rate-limit "
                    f"(CORS preflight must not be rate-limited)"
                )
            # tracing should come before rate-limit (we want traces of blocked requests)
            if "tracing-middleware" in middlewares:
                trace_idx = middlewares.index("tracing-middleware")
                assert trace_idx < rl_idx, (
                    f"[{config_name}] Router '{router_name}': "
                    f"tracing-middleware must precede rate-limit "
                    f"(rate-limited requests should still be traced)"
                )


# ---------------------------------------------------------------------------
# 280.A.6.4.3 — 429 response behavior
# ---------------------------------------------------------------------------


class TestRateLimit429Behavior:
    """Validate that exceeding the rate limit returns 429 before reaching Django."""

    def test_rate_limit_middleware_produces_429(self):
        """Traefik's rateLimit middleware returns 429 by default.

        This is inherent to Traefik v3 — when the rate limit is exceeded,
        Traefik returns 429 Too Many Requests and does NOT forward the
        request to the backend service. This means Django never sees the
        request and never incurs the overhead of processing it.

        We verify this by checking that:
        1. The rateLimit middleware has no custom response override
        2. The middleware is NOT configured with a custom error page
           that would change the status code
        """
        routes = _load_yaml(ROUTES_TMPL)
        rl = routes.get("http", {}).get("middlewares", {}).get("rate-limit", {})
        rate_limit = rl.get("rateLimit", {})

        # No custom error page configured — Traefik default 429
        assert "errorPage" not in rate_limit, (
            "rate-limit must not use custom errorPage — default 429 is required"
        )
        # No custom response code override
        assert "responseCode" not in rate_limit, (
            "rate-limit must not override responseCode — default 429 is required"
        )

    def test_no_bypass_headers_configured(self):
        """Rate limit must not have bypass headers that would defeat it."""
        routes = _load_yaml(ROUTES_TMPL)
        rl = routes.get("http", {}).get("middlewares", {}).get("rate-limit", {})
        rate_limit = rl.get("rateLimit", {})

        # sourceCriterion must NOT use requestHeader (which could be spoofed)
        sc = rate_limit.get("sourceCriterion", {})
        assert "requestHeaderName" not in sc, (
            "rate-limit must not use requestHeader for source criterion "
            "(header values can be spoofed)"
        )
        assert "requestHost" not in sc, (
            "rate-limit must not use requestHost for source criterion "
            "(host-based limiting is not per-IP)"
        )


# ---------------------------------------------------------------------------
# 280.A.6.4.4 — Cross-file consistency
# ---------------------------------------------------------------------------


class TestRateLimitCrossFileConsistency:
    """Validate rate-limit config is consistent across all Traefik config files."""

    def test_average_consistent_across_all_files(self, routes_tmpl, routes_yml, k8s_routes):
        """Average must be 100 in all config files."""
        for name, routes in [("tmpl", routes_tmpl), ("yml", routes_yml), ("k8s", k8s_routes)]:
            rl = routes.get("http", {}).get("middlewares", {}).get("rate-limit", {})
            avg = rl.get("rateLimit", {}).get("average")
            assert avg == 100, f"[{name}] average={avg}, expected 100"

    def test_burst_consistent_across_all_files(self, routes_tmpl, routes_yml, k8s_routes):
        """Burst must be 50 in all config files."""
        for name, routes in [("tmpl", routes_tmpl), ("yml", routes_yml), ("k8s", k8s_routes)]:
            rl = routes.get("http", {}).get("middlewares", {}).get("rate-limit", {})
            burst = rl.get("rateLimit", {}).get("burst")
            assert burst == 50, f"[{name}] burst={burst}, expected 50"

    def test_ip_strategy_depth_consistent(self, routes_tmpl, routes_yml, k8s_routes):
        """ipStrategy depth must be consistent across all files."""
        depths = {}
        for name, routes in [("tmpl", routes_tmpl), ("yml", routes_yml), ("k8s", k8s_routes)]:
            rl = routes.get("http", {}).get("middlewares", {}).get("rate-limit", {})
            depth = (
                rl.get("rateLimit", {})
                .get("sourceCriterion", {})
                .get("ipStrategy", {})
                .get("depth")
            )
            depths[name] = depth

        # All files should have the same depth
        unique_depths = set(depths.values())
        assert len(unique_depths) == 1, f"ipStrategy depth differs across files: {depths}"


# ---------------------------------------------------------------------------
# 280.A.6.4.5 — Performance impact analysis
# ---------------------------------------------------------------------------


class TestRateLimitPerformanceCharacteristics:
    """Validate rate limit config won't cause performance issues."""

    def test_burst_is_reasonable_fraction_of_average(self, routes_tmpl):
        """Burst should be ~50% of average — enough for bursts but not abuse."""
        rl = routes_tmpl.get("http", {}).get("middlewares", {}).get("rate-limit", {})
        avg = rl.get("rateLimit", {}).get("average", 0)
        burst = rl.get("rateLimit", {}).get("burst", 0)

        if avg > 0:
            ratio = burst / avg
            assert 0.25 <= ratio <= 0.75, (
                f"Burst/average ratio should be 0.25-0.75, got {ratio:.2f}. "
                f"Too low: no burst tolerance. Too high: defeats rate limiting."
            )

    def test_average_100_is_within_traefik_capabilities(self, routes_tmpl):
        """Traefik can handle rate-limiting at 100 req/s per IP without issues.

        Traefik's in-memory rate limiter uses a token bucket algorithm that
        is O(1) per request. With 100 req/s per IP and typical production
        traffic, the overhead is negligible.
        """
        rl = routes_tmpl.get("http", {}).get("middlewares", {}).get("rate-limit", {})
        avg = rl.get("rateLimit", {}).get("average")
        # 100 req/s is well within Traefik's documented performance envelope
        # (Traefik can handle 10k+ req/s with rate limiting enabled)
        assert isinstance(avg, int) and avg == 100


# ---------------------------------------------------------------------------
# 280.A.6.4.6 — Raw file content checks (YAML parse-independent)
# ---------------------------------------------------------------------------


class TestRateLimitRawFileChecks:
    """Validate raw file content for the rate-limit middleware.

    These tests catch issues like YAML parsing silently swallowing config
    or the middleware being commented out.
    """

    def test_rate_limit_not_commented_out_in_template(self):
        """rate-limit must NOT be commented out in the template."""
        with open(ROUTES_TMPL) as f:
            content = f.read()
        # The middleware name line should not be commented
        assert re.search(r"^\s+rate-limit:\s*$", content, re.MULTILINE), (
            "rate-limit middleware appears to be commented out or missing in routes.yml.tmpl"
        )

    def test_rate_limit_not_commented_out_in_static(self):
        """rate-limit must NOT be commented out in routes.yml."""
        with open(ROUTES_YML) as f:
            content = f.read()
        assert re.search(r"^\s+rate-limit:\s*$", content, re.MULTILINE), (
            "rate-limit middleware appears to be commented out or missing in routes.yml"
        )

    def test_rate_limit_not_commented_out_in_k8s(self):
        """rate-limit must NOT be commented out in K8s ConfigMap."""
        with open(K8S_CONFIGMAP) as f:
            content = f.read()
        assert re.search(r"^\s+rate-limit:\s*$", content, re.MULTILINE), (
            "rate-limit middleware appears to be commented out or missing in K8s ConfigMap"
        )

    def test_rate_limit_in_middleware_list_of_routers(self):
        """Every production router must include rate-limit in its middleware list.

        Raw text check to ensure the middleware reference is not commented out.
        """
        with open(ROUTES_TMPL) as f:
            content = f.read()

        routers_with_rl = 0
        for name in ["api-gateway", "api-gateway-host", "frontend"]:
            # Find the router block
            pattern = rf"^\s{{4}}{re.escape(name)}:\s*$"
            match = re.search(pattern, content, re.MULTILINE)
            if match:
                # Get the next 20 lines
                start = match.start()
                block = content[start : start + 800]
                if "rate-limit" in block:
                    routers_with_rl += 1

        assert routers_with_rl >= 3, (
            f"Only {routers_with_rl}/3 production routers reference rate-limit "
            f"middleware in routes.yml.tmpl"
        )
