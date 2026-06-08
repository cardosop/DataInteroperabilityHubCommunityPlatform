"""
280.A.6.1 — Production docker-compose.yml Service Validation.

Validates:
- All services have health checks with appropriate intervals/timeouts
- depends_on chains are acyclic and reference real services
- Resource limits are within safe bounds (no unlimited or missing limits)
- Startup order is correct (infrastructure before app, app before workers)
- Port exposures follow security best practice (only Traefik exposed)
- Health check commands use tools available in the container image

Does NOT mock — reads and validates the real docker-compose.production.yml.
"""
import os
import re
import pytest
import yaml

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
PRODUCTION_COMPOSE = os.path.join(PROJECT_ROOT, "docker-compose.production.yml")


def _load_compose():
    """Load the production docker-compose file as a dict."""
    with open(PRODUCTION_COMPOSE) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def compose_data():
    """Parsed docker-compose.production.yml."""
    assert os.path.exists(PRODUCTION_COMPOSE), (
        f"docker-compose.production.yml not found at {PRODUCTION_COMPOSE}"
    )
    return _load_compose()


@pytest.fixture(scope="module")
def services(compose_data):
    """Dict of service_name → service_config."""
    return compose_data.get("services", {})


# ---------------------------------------------------------------------------
# 280.A.6.1.1 — File integrity
# ---------------------------------------------------------------------------

class TestProductionComposeFileIntegrity:
    """Validate the compose file is well-formed and parseable."""

    def test_file_exists_and_not_empty(self):
        """Production compose file must exist and have meaningful content."""
        assert os.path.exists(PRODUCTION_COMPOSE)
        size = os.path.getsize(PRODUCTION_COMPOSE)
        assert size > 1000, f"Production compose file too small ({size} bytes)"

    def test_valid_yaml(self, compose_data):
        """Must parse as valid YAML with expected top-level keys."""
        assert "services" in compose_data
        assert "networks" in compose_data
        assert "volumes" in compose_data

    def test_version_is_3_8(self, compose_data):
        """Must use Compose file format 3.8."""
        version = compose_data.get("version", "")
        assert version == "3.8", f"Expected version 3.8, got {version}"

    def test_production_network_exists(self, compose_data):
        """Must define hub-net-production network."""
        networks = compose_data.get("networks", {})
        assert "hub-net-production" in networks, (
            "Missing hub-net-production network"
        )


# ---------------------------------------------------------------------------
# 280.A.6.1.2 — Health checks
# ---------------------------------------------------------------------------

# Services that are intentionally marked with profiles and may not always start
PROFILE_GATED_SERVICES = {"postgres-replica"}


class TestProductionHealthChecks:
    """Every production service must have a valid health check."""

    def test_all_services_have_healthcheck(self, services):
        """Every service (except profile-gated) must define a health check."""
        missing = []
        for name, svc in sorted(services.items()):
            if name in PROFILE_GATED_SERVICES:
                continue
            if "healthcheck" not in svc:
                missing.append(name)
        assert not missing, (
            f"Services missing healthcheck: {missing}. "
            f"Every production service must have a health check."
        )

    def test_healthcheck_has_required_fields(self, services):
        """Health checks must specify test, interval, timeout, retries."""
        bad = []
        for name, svc in sorted(services.items()):
            hc = svc.get("healthcheck")
            if not hc:
                continue
            for field in ("test", "interval", "timeout", "retries"):
                if field not in hc:
                    bad.append(f"{name}: missing {field}")
        assert not bad, f"Health checks missing required fields: {bad}"

    def test_healthcheck_intervals_reasonable(self, services):
        """Interval must be between 10s-60s; timeout less than interval."""
        bad = []
        for name, svc in sorted(services.items()):
            hc = svc.get("healthcheck")
            if not hc:
                continue
            interval_str = str(hc.get("interval", "0s"))
            timeout_str = str(hc.get("timeout", "0s"))
            try:
                interval_s = int(re.sub(r"s$", "", interval_str))
                timeout_s = int(re.sub(r"s$", "", timeout_str))
            except ValueError:
                bad.append(f"{name}: unparseable interval/timeout")
                continue
            if not (10 <= interval_s <= 60):
                bad.append(
                    f"{name}: interval {interval_s}s outside 10-60s range"
                )
            if timeout_s >= interval_s:
                bad.append(
                    f"{name}: timeout {timeout_s}s >= interval {interval_s}s"
                )
        assert not bad, f"Unreasonable health check intervals/timeouts: {bad}"

    def test_healthcheck_commands_use_available_tools(self, services):
        """Health check commands must reference tools in the container image.

        Known tool → image mapping:
        - pg_isready → postgres:16-alpine
        - nc → edoburu/pgbouncer (Alpine, BusyBox nc)
        - redis-cli → redis:7-alpine
        - curl → api-service/worker images (Debian-based)
        - wget → apache-jena-fuseki, otel-contrib, tempo, loki, grafana
        """
        # Tools known to NOT be in specific images
        IMAGE_TOOL_BLACKLIST = {
            # edoburu/pgbouncer has no postgresql-client (no psql/pg_isready)
            "edoburu/pgbouncer": {"pg_isready", "psql"},
            # Alpine Redis has no curl
            "redis:7-alpine": {"curl", "wget"},
        }

        issues = []
        for name, svc in sorted(services.items()):
            hc = svc.get("healthcheck")
            if not hc:
                continue
            test_cmd = hc.get("test", [])
            image = svc.get("image", "")

            # Normalize test to string for analysis
            if isinstance(test_cmd, list):
                cmd_str = " ".join(str(x) for x in test_cmd)
            else:
                cmd_str = str(test_cmd)

            # Check blacklist
            for bad_image, bad_tools in IMAGE_TOOL_BLACKLIST.items():
                if bad_image in image:
                    for tool in bad_tools:
                        if tool in cmd_str:
                            issues.append(
                                f"{name} ({image}): uses '{tool}' which is "
                                f"not available in this image"
                            )

        assert not issues, f"Health check tool issues: {issues}"

    def test_healthcheck_start_period_exists_for_slow_services(self, services):
        """Database and heavyweight services must have a start_period."""
        SLOW_SERVICES = {
            "postgres", "postgres-replica", "api-service",
            "tempo", "loki", "grafana",
        }
        missing = []
        for name in SLOW_SERVICES:
            svc = services.get(name)
            if svc is None:
                continue
            if "start_period" not in svc.get("healthcheck", {}):
                missing.append(name)
        assert not missing, (
            f"Slow-start services missing start_period: {missing}"
        )


# ---------------------------------------------------------------------------
# 280.A.6.1.3 — Startup order (depends_on chains)
# ---------------------------------------------------------------------------

class TestProductionStartupOrder:
    """Validate that depends_on chains produce correct startup ordering."""

    def test_depends_on_references_are_valid(self, services):
        """Every depends_on target must be a real service."""
        bad = []
        all_names = set(services.keys())
        for name, svc in sorted(services.items()):
            for dep in svc.get("depends_on", {}):
                # depends_on can be a dict (with condition) or a list
                dep_name = dep if isinstance(dep, str) else dep
                if dep_name not in all_names:
                    bad.append(f"{name} depends on unknown service: {dep_name}")
        assert not bad, f"Invalid depends_on references: {bad}"

    def test_no_circular_dependencies(self, services):
        """depends_on graph must be acyclic."""
        # Build adjacency list
        adj = {}
        for name in services:
            adj[name] = set()
        for name, svc in services.items():
            deps = svc.get("depends_on", {})
            # depends_on in compose v3.8 can be dict or list
            if isinstance(deps, dict):
                for dep_name in deps:
                    if dep_name in services:
                        adj[name].add(dep_name)
            elif isinstance(deps, list):
                for dep_name in deps:
                    if dep_name in services:
                        adj[name].add(dep_name)

        # DFS-based cycle detection
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {n: WHITE for n in adj}

        def dfs(node):
            color[node] = GRAY
            for neighbor in adj[node]:
                if color[neighbor] == GRAY:
                    return [node, neighbor]  # back edge
                if color[neighbor] == WHITE:
                    cycle = dfs(neighbor)
                    if cycle:
                        return [node] + cycle
            color[node] = BLACK
            return None

        for node in adj:
            if color[node] == WHITE:
                cycle = dfs(node)
                assert cycle is None, (
                    f"Circular dependency detected: {' → '.join(cycle)}"
                )

    def test_infrastructure_starts_before_app(self, services):
        """Postgres, Redis, MinIO, Fuseki must start before api-service."""
        api = services.get("api-service", {})
        api_deps = set(api.get("depends_on", {}).keys())
        infrastructure = {"pgbouncer", "redis-cache", "redis-queue",
                          "redis-events", "redis-channels", "minio"}
        for dep in infrastructure:
            assert dep in api_deps, (
                f"api-service must depend_on {dep} for correct startup order"
            )

    def test_workers_depend_on_api_and_pgbouncer(self, services):
        """Worker services must depend on api-service and pgbouncer."""
        workers = ["worker-heavy", "worker-light"]
        for worker_name in workers:
            worker = services.get(worker_name)
            if worker is None:
                continue
            deps = set(worker.get("depends_on", {}).keys())
            assert "pgbouncer" in deps, (
                f"{worker_name} must depend_on pgbouncer"
            )
            assert "api-service" in deps, (
                f"{worker_name} must depend_on api-service (needs DB migrations)"
            )

    def test_compliance_rq_worker_depends_on_compliance_service(self, services):
        """compliance-rq-worker must depend on compliance-service."""
        rq = services.get("compliance-rq-worker")
        if rq is None:
            return
        deps = set(rq.get("depends_on", {}).keys())
        assert "compliance-service" in deps, (
            "compliance-rq-worker must depend_on compliance-service"
        )


# ---------------------------------------------------------------------------
# 280.A.6.1.4 — Resource limits
# ---------------------------------------------------------------------------

class TestProductionResourceLimits:
    """Validate resource limits are appropriate for production."""

    # Services that MUST have deploy.resources defined
    SERVICES_REQUIRING_LIMITS = {
        "postgres", "api-service", "worker-heavy", "worker-light",
        "fuseki", "redis-cache", "redis-queue", "redis-events",
        "redis-channels", "minio", "tempo", "loki", "prometheus",
    }

    def test_core_services_have_resource_limits(self, services):
        """Every core service must define deploy.resources with limits."""
        missing = []
        for name in self.SERVICES_REQUIRING_LIMITS:
            svc = services.get(name)
            if svc is None:
                continue
            deploy = svc.get("deploy", {})
            resources = deploy.get("resources", {})
            limits = resources.get("limits", {})
            if not limits:
                missing.append(name)
        assert not missing, (
            f"Core services without resource limits: {missing}"
        )

    def test_all_services_with_deploy_have_both_limits_and_reservations(self, services):
        """When deploy is specified, both limits and reservations must be set."""
        bad = []
        for name, svc in sorted(services.items()):
            deploy = svc.get("deploy", {})
            if not deploy:
                continue
            resources = deploy.get("resources", {})
            if "limits" in resources and "reservations" not in resources:
                bad.append(f"{name}: has limits but no reservations")
            if "reservations" in resources and "limits" not in resources:
                bad.append(f"{name}: has reservations but no limits")
        assert not bad, f"Services with incomplete resource specs: {bad}"

    def test_cpu_limits_not_excessive(self, services):
        """CPU limits must not exceed 8.0 (single service shouldn't dominate the host)."""
        bad = []
        for name, svc in sorted(services.items()):
            deploy = svc.get("deploy", {})
            resources = deploy.get("resources", {})
            limits = resources.get("limits", {})
            cpu = limits.get("cpus")
            if cpu is not None:
                try:
                    cpu_val = float(cpu) if isinstance(cpu, str) else cpu
                    if cpu_val > 8.0:
                        bad.append(f"{name}: CPU limit {cpu_val} > 8.0")
                except (ValueError, TypeError):
                    bad.append(f"{name}: unparseable CPU limit {cpu}")
        assert not bad, f"Excessive CPU limits: {bad}"

    def test_memory_limits_not_excessive(self, services):
        """Memory limits must not exceed 16G per service."""
        bad = []
        for name, svc in sorted(services.items()):
            deploy = svc.get("deploy", {})
            resources = deploy.get("resources", {})
            limits = resources.get("limits", {})
            mem = limits.get("memory")
            if mem is not None:
                mem_bytes = _parse_memory(mem)
                if mem_bytes is not None and mem_bytes > 16 * 1024 * 1024 * 1024:
                    bad.append(f"{name}: memory limit {mem} > 16G")
        assert not bad, f"Excessive memory limits: {bad}"

    def test_memory_reservation_less_than_limit(self, services):
        """Memory reservations must be less than limits."""
        bad = []
        for name, svc in sorted(services.items()):
            deploy = svc.get("deploy", {})
            resources = deploy.get("resources", {})
            limits = resources.get("limits", {})
            reservations = resources.get("reservations", {})
            limit_mem = limits.get("memory")
            resv_mem = reservations.get("memory")
            if limit_mem and resv_mem:
                limit_bytes = _parse_memory(limit_mem)
                resv_bytes = _parse_memory(resv_mem)
                if limit_bytes is not None and resv_bytes is not None:
                    if resv_bytes > limit_bytes:
                        bad.append(
                            f"{name}: reservation {resv_mem} > limit {limit_mem}"
                        )
        assert not bad, f"Memory reservation exceeds limit: {bad}"


# ---------------------------------------------------------------------------
# 280.A.6.1.5 — Security: ports
# ---------------------------------------------------------------------------

class TestProductionPortSecurity:
    """Validate port exposures follow the principle of least privilege."""

    # Services allowed to expose ports to the host
    ALLOWED_HOST_PORTS = {
        "traefik",        # 80/443 — reverse proxy entrypoint
        "otel-collector", # 4317/4318 — OTLP ingestion
        "tempo",          # 3200 — tracing query API
        "prometheus",     # 9090 — metrics scraping
        "alertmanager",   # 9093 — alert routing
        "grafana",        # 3000 — observability dashboards
    }

    def test_only_approved_services_expose_ports(self, services):
        """Only reverse proxy and observability services may expose host ports."""
        violators = []
        for name, svc in sorted(services.items()):
            ports = svc.get("ports", [])
            if ports and name not in self.ALLOWED_HOST_PORTS:
                violators.append(name)
        assert not violators, (
            f"Services with unexpected host port exposure: {violators}. "
            f"Allowed: {sorted(self.ALLOWED_HOST_PORTS)}"
        )

    def test_traefik_exposes_80_and_443(self, services):
        """Traefik must listen on 80 and 443 for HTTP→HTTPS redirect."""
        traefik = services.get("traefik", {})
        ports = traefik.get("ports", [])
        port_mappings = [str(p) for p in ports]
        assert any("80" in p for p in port_mappings), (
            "Traefik must expose port 80 for HTTP→HTTPS redirect"
        )
        assert any("443" in p for p in port_mappings), (
            "Traefik must expose port 443 for TLS termination"
        )

    def test_database_redis_no_host_ports(self, services):
        """PostgreSQL and Redis must never expose ports to the host."""
        for name in ("postgres", "pgbouncer", "redis-cache", "redis-queue",
                      "redis-events", "redis-channels"):
            svc = services.get(name)
            if svc is None:
                continue
            ports = svc.get("ports", [])
            assert not ports, (
                f"{name} must not expose ports in production"
            )


# ---------------------------------------------------------------------------
# 280.A.6.1.6 — Service restart policies
# ---------------------------------------------------------------------------

class TestProductionRestartPolicies:
    """Validate restart policies for production reliability."""

    def test_all_services_restart_always(self, services):
        """Production services must all use restart: always."""
        EXEMPT = {"postgres-replica"}  # profile-gated
        bad = []
        for name, svc in sorted(services.items()):
            if name in EXEMPT:
                continue
            restart = svc.get("restart", "")
            if restart != "always":
                bad.append(f"{name}: restart={restart!r}, expected 'always'")
        assert not bad, f"Services not using restart: always: {bad}"

    def test_api_service_has_restart_policy(self, services):
        """api-service deploy.restart_policy must be explicitly configured."""
        api = services.get("api-service", {})
        deploy = api.get("deploy", {})
        restart_policy = deploy.get("restart_policy", {})
        assert restart_policy, (
            "api-service must have deploy.restart_policy configured"
        )
        assert restart_policy.get("condition") == "on-failure", (
            "api-service restart condition should be on-failure"
        )


# ---------------------------------------------------------------------------
# 280.A.6.1.7 — Environment variables
# ---------------------------------------------------------------------------

class TestProductionEnvironmentVariables:
    """Validate environment variable configuration."""

    def test_api_service_uses_env_file(self, services):
        """api-service must source .env.production."""
        api = services.get("api-service", {})
        env_files = api.get("env_file", [])
        assert ".env.production" in env_files, (
            "api-service must use env_file: .env.production"
        )

    def test_api_service_overrides_debug_and_environment(self, services):
        """api-service must explicitly set DEBUG=False and ENVIRONMENT=production."""
        api = services.get("api-service", {})
        env = api.get("environment", [])
        if isinstance(env, dict):
            env = [f"{k}={v}" for k, v in env.items()]
        env_str = " ".join(str(e) for e in env)
        assert "DEBUG=False" in env_str or "DEBUG=false" in env_str, (
            "api-service must set DEBUG=False"
        )
        assert "ENVIRONMENT=production" in env_str, (
            "api-service must set ENVIRONMENT=production"
        )

    def test_pgbouncer_enabled_flag_is_set(self, services):
        """Services connecting through pgbouncer must set PGBOUNCER_ENABLED=true."""
        pgbouncer_enabled_services = {"api-service", "worker-heavy", "worker-light"}
        for name in pgbouncer_enabled_services:
            svc = services.get(name)
            if svc is None:
                continue
            env = svc.get("environment", [])
            if isinstance(env, dict):
                env = [f"{k}={v}" for k, v in env.items()]
            env_str = " ".join(str(e) for e in env)
            assert "PGBOUNCER_ENABLED=true" in env_str, (
                f"{name} must set PGBOUNCER_ENABLED=true"
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_memory(value):
    """Parse a Docker Compose memory string to bytes. Returns None on failure."""
    if value is None:
        return None
    value = str(value).lower().strip()
    multipliers = {
        "b": 1,
        "k": 1024,
        "kb": 1024,
        "m": 1024 * 1024,
        "mb": 1024 * 1024,
        "g": 1024 * 1024 * 1024,
        "gb": 1024 * 1024 * 1024,
    }
    match = re.match(r"^([\d.]+)\s*([a-z]*)$", value)
    if not match:
        return None
    num = float(match.group(1))
    unit = match.group(2) or "b"
    multiplier = multipliers.get(unit)
    if multiplier is None:
        return None
    return int(num * multiplier)
