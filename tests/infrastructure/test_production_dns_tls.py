"""
280.A.6.3 — DNS + TLS Verification for Production Domains.

Validates:
- Traefik HTTP→HTTPS redirect configuration
- TLS certificate resolver (Let's Encrypt) configuration
- Production domain references in router rules
- DNS automation in Terraform (Route53 for staging)
- Security headers and TLS best practices

Does NOT perform live DNS lookups — validates configuration correctness.
"""
import os
import re
import pytest
import yaml

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)

TRAEFIK_MAIN = os.path.join(PROJECT_ROOT, "infrastructure", "traefik", "traefik.yml")
ROUTES_TMPL = os.path.join(
    PROJECT_ROOT, "infrastructure", "traefik", "dynamic", "routes.yml.tmpl"
)
ROUTES_YML = os.path.join(
    PROJECT_ROOT, "infrastructure", "traefik", "dynamic", "routes.yml"
)

PRODUCTION_DOMAINS = [
    "meshant.com",
    "meshant-internal.example.com",
    "stagingmeshant-internal.example.com",
    "api.stagingmeshant-internal.example.com",
]

# Domains that must appear in the Route53 Terraform DNS zone configuration.
# meshant.com is the apex; staging subdomains are CNAME'd via CI deploy workflow.
ROUTE53_EXPECTED_DOMAINS = {"meshant.com"}


def _load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f.read())


# ---------------------------------------------------------------------------
# 280.A.6.3.1 — HTTP → HTTPS redirect
# ---------------------------------------------------------------------------

class TestHttpToHttpsRedirect:
    """Validate that all HTTP traffic is redirected to HTTPS."""

    @pytest.fixture(scope="class")
    def traefik_config(self):
        assert os.path.exists(TRAEFIK_MAIN), f"Missing {TRAEFIK_MAIN}"
        return _load_yaml(TRAEFIK_MAIN)

    def test_web_entrypoint_has_https_redirect(self, traefik_config):
        """The web (:80) entrypoint must redirect to websecure (:443)."""
        entrypoints = traefik_config.get("entryPoints", {})
        web = entrypoints.get("web", {})
        assert web is not None, "Missing 'web' entrypoint"

        http_config = web.get("http", {})
        redirections = http_config.get("redirections", {})
        assert redirections, "web entrypoint must have HTTP redirections"

        entrypoint_redirect = redirections.get("entryPoint", {})
        assert entrypoint_redirect.get("to") == "websecure", (
            "web must redirect to websecure entrypoint"
        )
        assert entrypoint_redirect.get("scheme") == "https", (
            "redirect scheme must be https"
        )

    def test_websecure_entrypoint_exists(self, traefik_config):
        """The websecure (:443) entrypoint must exist."""
        entrypoints = traefik_config.get("entryPoints", {})
        websecure = entrypoints.get("websecure", {})
        assert websecure is not None, "Missing 'websecure' entrypoint"
        assert websecure.get("address") == ":443", (
            "websecure must listen on :443"
        )

    def test_websecure_has_tls_enabled(self, traefik_config):
        """websecure must have TLS configuration."""
        entrypoints = traefik_config.get("entryPoints", {})
        websecure = entrypoints.get("websecure", {})
        tls_config = websecure.get("http", {}).get("tls", {})
        # TLS can be {} (default settings) or have explicit options
        assert "tls" in websecure.get("http", {}), (
            "websecure entrypoint must have TLS section"
        )


# ---------------------------------------------------------------------------
# 280.A.6.3.2 — TLS certificate resolver
# ---------------------------------------------------------------------------

class TestTlsCertificateResolver:
    """Validate Let's Encrypt ACME configuration."""

    @pytest.fixture(scope="class")
    def traefik_config(self):
        return _load_yaml(TRAEFIK_MAIN)

    def test_letsencrypt_resolver_exists(self, traefik_config):
        """A Let's Encrypt certificate resolver must be configured."""
        resolvers = traefik_config.get("certificatesResolvers", {})
        assert "letsencrypt" in resolvers, (
            "Missing 'letsencrypt' certificate resolver"
        )

    def test_acme_configuration(self, traefik_config):
        """ACME config must be present with httpChallenge."""
        letsencrypt = traefik_config["certificatesResolvers"]["letsencrypt"]
        acme = letsencrypt.get("acme", {})
        assert acme, "letsencrypt resolver must have acme config"

        # Email is required by Let's Encrypt
        email = acme.get("email", "")
        assert email, "ACME email must be set (uses TRAEFIK_ACME_EMAIL env var)"

        # Storage for certs
        assert acme.get("storage"), "ACME storage path must be set"

        # Challenge type
        http_challenge = acme.get("httpChallenge", {})
        assert http_challenge is not None, (
            "ACME must use httpChallenge (DNS challenge is also valid but "
            "httpChallenge is the configured choice)"
        )
        assert http_challenge.get("entryPoint") == "web", (
            "httpChallenge must use the 'web' entrypoint (port 80)"
        )

    def test_all_routers_use_cert_resolver(self):
        """Every router in routes.yml.tmpl must reference the TLS cert resolver."""
        routes = _load_yaml(ROUTES_TMPL)
        routers = routes.get("http", {}).get("routers", {})

        EXEMPT_ROUTERS = set()  # none are exempt in production

        for name, router in routers.items():
            if name in EXEMPT_ROUTERS:
                continue
            tls = router.get("tls", {})
            assert tls, f"Router '{name}' must have TLS config"
            cert_resolver = tls.get("certResolver")
            assert cert_resolver == "letsencrypt", (
                f"Router '{name}' certResolver must be 'letsencrypt', "
                f"got {cert_resolver!r}"
            )

    def test_routers_only_use_websecure_entrypoint(self):
        """Production routers must only bind to websecure (not plain web)."""
        routes = _load_yaml(ROUTES_TMPL)
        routers = routes.get("http", {}).get("routers", {})

        for name, router in routers.items():
            entrypoints = router.get("entryPoints", [])
            assert "websecure" in entrypoints, (
                f"Router '{name}' must bind to websecure"
            )
            if "web" in entrypoints:
                # The dashboard router may use web for non-TLS access
                assert "dashboard" in name.lower(), (
                    f"Router '{name}' uses 'web' entrypoint but is not the "
                    f"dashboard. All routers must use websecure only."
                )


# ---------------------------------------------------------------------------
# 280.A.6.3.3 — Production domain references
# ---------------------------------------------------------------------------

class TestProductionDomainReferences:
    """Validate production domain names are correctly referenced."""

    def test_traefik_dashboard_uses_env_var_for_host(self):
        """Dashboard host must be configured via env var, not hardcoded."""
        routes = _load_yaml(ROUTES_TMPL)
        dashboard = routes.get("http", {}).get("routers", {}).get("traefik-dashboard", {})
        assert dashboard, "traefik-dashboard router must exist in template"
        rule = dashboard.get("rule", "")
        assert "${TRAEFIK_DASHBOARD_HOST}" in rule, (
            "Dashboard host must use TRAEFIK_DASHBOARD_HOST env var"
        )

    def test_cors_allowed_origins_uses_env_var(self):
        """CORS allowed origins must use env var, not wildcard."""
        routes = _load_yaml(ROUTES_TMPL)
        cors = routes.get("http", {}).get("middlewares", {}).get("cors-middleware", {})
        assert cors, "cors-middleware must exist"
        headers = cors.get("headers", {})
        # In production template, uses regex env var
        origin_list = headers.get("accessControlAllowOriginList", [])
        origin_regex = headers.get("accessControlAllowOriginListRegex", [])
        if origin_regex:
            assert "${ALLOWED_ORIGINS_REGEX}" in str(origin_regex), (
                "CORS origin regex must use ALLOWED_ORIGINS_REGEX env var"
            )
        if origin_list:
            assert "*" not in origin_list, (
                "CORS must NOT use wildcard origin in production"
            )

    def test_no_hardcoded_internal_domains_in_production_routes(self):
        """Routes template must not hardcode internal dev domains."""
        routes = _load_yaml(ROUTES_TMPL)
        routers = routes.get("http", {}).get("routers", {})
        DANGEROUS_DOMAINS = {
            "localhost", "127.0.0.1", "hub.local", "hub.example.com",
            "hub.test", "hub.dev",
        }
        for name, router in routers.items():
            rule = router.get("rule", "")
            for domain in DANGEROUS_DOMAINS:
                if domain in rule:
                    # hub.local and hub.example.com are in the api-gateway-host
                    # router for backward compat — that's intentional
                    if name == "api-gateway-host" and domain in (
                        "hub.local", "hub.example.com"
                    ):
                        continue
                    pytest.fail(
                        f"Router '{name}' rule contains '{domain}'. "
                        f"Production routes must not reference dev domains."
                    )


# ---------------------------------------------------------------------------
# 280.A.6.3.4 — DNS automation (Terraform Route53)
# ---------------------------------------------------------------------------

class TestRoute53DnsAutomation:
    """Validate Route53 DNS configuration in Terraform."""

    STAGING_MAIN = os.path.join(
        PROJECT_ROOT, "infrastructure", "terraform",
        "environments", "staging", "main.tf"
    )

    def _read_staging_main(self):
        """Read staging main.tf, skip if missing."""
        if not os.path.exists(self.STAGING_MAIN):
            pytest.skip("Staging main.tf not found")
        with open(self.STAGING_MAIN) as f:
            return f.read()

    def test_staging_has_route53_zone_data_source(self):
        """Staging terraform must reference the meshant.com hosted zone."""
        content = self._read_staging_main()
        assert 'aws_route53_zone' in content, (
            "Staging TF must have Route53 zone data source"
        )
        assert 'meshant.com' in content, (
            "Route53 zone name must be meshant.com"
        )

    def test_staging_route53_iam_policy_is_minimal(self):
        """Route53 IAM policy must be scoped to the specific hosted zone."""
        content = self._read_staging_main()
        assert 'data.aws_route53_zone.meshant.arn' in content, (
            "Route53 ChangeResourceRecordSets must be scoped to meshant zone ARN, "
            "not wildcard"
        )

    def test_expected_production_domains_in_route53_zone(self):
        """All ROUTE53_EXPECTED_DOMAINS must be referenced in the TF zone config.

        This validates that the apex domain meshant.com is in the Route53
        hosted zone data source, confirming DNS automation targets the
        correct zone. Subdomains (meshant-internal.example.com, stagingmeshant-internal.example.com)
        are CNAME records created by the CI deploy workflow and don't appear
        in the Terraform zone data source.
        """
        content = self._read_staging_main()
        for domain in ROUTE53_EXPECTED_DOMAINS:
            assert domain in content, (
                f"Expected domain '{domain}' not found in staging TF Route53 config"
            )


# ---------------------------------------------------------------------------
# 280.A.6.3.5 — TLS best practices
# ---------------------------------------------------------------------------

class TestTlsBestPractices:
    """Validate TLS configuration follows security best practices."""

    @pytest.fixture(scope="class")
    def traefik_config(self):
        return _load_yaml(TRAEFIK_MAIN)

    def test_traefik_api_not_insecure(self, traefik_config):
        """Traefik dashboard/API must NOT be exposed on insecure port."""
        api = traefik_config.get("api", {})
        # insecure: false means the API is NOT on :8080 without auth
        assert api.get("insecure") is not True, (
            "Traefik API insecure mode must be false in production. "
            "Dashboard access must go through the secure router with auth."
        )

    def test_dashboard_has_auth_middleware(self):
        """Dashboard router must have both IP allowlist AND basic auth."""
        routes = _load_yaml(ROUTES_TMPL)
        dashboard = (
            routes.get("http", {})
            .get("routers", {})
            .get("traefik-dashboard", {})
        )
        assert dashboard, "traefik-dashboard router must exist"
        middlewares = dashboard.get("middlewares", [])
        assert "dashboard-ip-allowlist" in middlewares, (
            "Dashboard must have IP allowlist middleware"
        )
        assert "dashboard-auth" in middlewares, (
            "Dashboard must have basic auth middleware"
        )

    def test_access_log_drops_sensitive_headers(self, traefik_config):
        """Access logs must drop Authorization and Cookie headers."""
        access_log = traefik_config.get("accessLog", {})
        fields = access_log.get("fields", {})
        headers = fields.get("headers", {})
        dropped = headers.get("names", {})
        assert dropped.get("Authorization") == "drop", (
            "Authorization header must be dropped from access logs"
        )
        assert dropped.get("Cookie") == "drop", (
            "Cookie header must be dropped from access logs"
        )

    def test_send_anonymous_usage_disabled(self, traefik_config):
        """Anonymous usage reporting must be disabled."""
        assert traefik_config.get("global", {}).get("sendAnonymousUsage") is False, (
            "sendAnonymousUsage must be false"
        )
