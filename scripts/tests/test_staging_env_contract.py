"""U.6 — staging bring-up contract tests (TDD).

Pins the compose-path staging bring-up contract so the WS-6 acceptance
criteria are enforced by a gate, not by memory:

  1. The set of ``${VAR:?}`` fail-fast secrets in docker-compose.staging.yml
     matches the registered set — adding a new required secret without a
     registry entry (and without this test) fails.
  2. Every host-port binding is unique AFTER ``${VAR:-default}`` expansion
     (the pgbouncer/prefect-db 5433 collision class).
  3. Service-to-service URLs and ``*_HOST`` env vars reference services that
     actually exist in the compose file (the ``REDIS_URL=redis://redis`` class
     — ``redis`` is not a service).
  4. When the stack is configured to send email (EMAIL_BACKEND=smtp), a real
     SMTP relay service exists in the compose file (``SMTP_HOST=localhost``
     inside a container points at the container itself — mail never leaves).
  5. ``make staging-up`` wires ``--env-file .env.staging`` — compose only
     auto-loads ``.env``, so the bring-up entrypoint must pass it explicitly
     (the "config parse fails without --env-file" class).
  6. The real ``.env.staging`` (gitignored secret material — assertions skip
     where the file is absent, i.e. in CI) carries no placeholder secrets,
     no role-pair secret reuse (MinIO root vs app credentials), a minimum
     secret length, and a unique internal port map.
  7. Every fail-fast secret is covered by an owner + rotation entry in
     docs/operations/staging-secrets-registry.md.

Run host-side (no Django/DB required):
    venv/bin/python -m pytest scripts/tests/test_staging_env_contract.py -q
"""

import re
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
COMPOSE_STAGING = PROJECT_ROOT / "docker-compose.staging.yml"
ENV_STAGING = PROJECT_ROOT / ".env.staging"
MAKEFILE = PROJECT_ROOT / "Makefile"
SECRETS_REGISTRY = PROJECT_ROOT / "docs" / "operations" / "staging-secrets-registry.md"

# The registered fail-fast secrets. Adding a `${NEW_VAR:?}` to the compose
# file without updating this set (and the secrets registry doc) fails.
REGISTERED_FAILFAST_VARS = {
    "POSTGRES_PASSWORD",
    "PGBOUNCER_AUTH_PASSWORD",
    "PGBOUNCER_ADMIN_PASSWORD",
    "MINIO_ROOT_USER",
    "MINIO_ROOT_PASSWORD",
    "FUSEKI_ADMIN_PASSWORD",
    "STRIPE_SECRET_KEY",
    "STRIPE_WEBHOOK_SECRET",
    "STRIPE_MARKETPLACE_WEBHOOK_SECRET",
    # minio-init bootstrap (Phase U.6) — the app-scoped S3 credentials and
    # the bucket name are required for the bootstrap to succeed.
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_STORAGE_BUCKET_NAME",
    # Phase U.6: services/shared/auth.py refuses to boot the microservices
    # without it — the first bring-up crashed dq/datacontract/semantic/
    # prefect-integration on the missing env var.
    "INTERNAL_API_KEY",
    # Phase U.6: the B-RLS-0.5 admin alias (meshant_admin) — without it the
    # admin connection fails SASL via pgbouncer and login 500s.
    "POSTGRES_ADMIN_PASSWORD",
    # Phase U.6: RS256 signing keypair — empty defaults make login 500 with
    # "Could not parse the provided public key".
    "JWT_PRIVATE_KEY",
    "JWT_PUBLIC_KEY",
    # W0.7 (oss-release-remediation): requirepass x4 — the staging redis
    # instances refuse to boot without their passwords (the production
    # compose precedent).
    "REDIS_CACHE_PASSWORD",
    "REDIS_QUEUE_PASSWORD",
    "REDIS_EVENTS_PASSWORD",
    "REDIS_CHANNELS_PASSWORD",
    # W0.7: the scheduled-ingestion internal-auth key (fail-fast like
    # INTERNAL_API_KEY).
    "HUB_WORKER_API_KEY",
    # W0.7: grafana's admin password lost its ``:-admin`` default.
    "GRAFANA_ADMIN_PASSWORD",
    # W0.7: the compliance rq CLI resolves it fail-fast (a non-secret
    # config literal — JSON serializer path, not a credential).
    "RQ_SERIALIZER",
    # W0.7: the prefect DB password lost its ``:-prefect`` default (the
    # evidence boot found the default-credential class).
    "PREFECT_DB_PASSWORD",
}

# Env-file secrets that MUST be covered by the owner + rotation registry.
# RQ_SERIALIZER is fail-fast but a NON-secret config literal (the JSON
# serializer path) — it needs no registry row.
REGISTRY_COVERAGE = (REGISTERED_FAILFAST_VARS - {"RQ_SERIALIZER"}) | {
    "SECRET_KEY",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "GRAFANA_ADMIN_PASSWORD",
    "INTERNAL_API_KEY",
    "POSTGRES_USER",
    # Phase U.6: embeds the postgres password — its rotation rides the
    # POSTGRES_PASSWORD event; the registry row cross-references it.
    "BAAS_DATABASE_URL",
    "POSTGRES_ADMIN_PASSWORD",
    "JWT_PRIVATE_KEY",
    "JWT_PUBLIC_KEY",
    # W0.7: the redis passwords + the worker key + the BAAS redis URL
    # (embeds the cache password — rides the REDIS_CACHE_PASSWORD event).
    "REDIS_CACHE_PASSWORD",
    "REDIS_QUEUE_PASSWORD",
    "REDIS_EVENTS_PASSWORD",
    "REDIS_CHANNELS_PASSWORD",
    "HUB_WORKER_API_KEY",
    "BAAS_REDIS_URL",
}

# Service-to-service environment values whose host is INTENTIONALLY not a
# compose service name (self-references or external DNS), with the reason.
HOST_ALLOWLIST = {
    "PREFECT_API_URL": "prefect-server reaches itself on its own published port",
    "GF_SERVER_ROOT_URL": "grafana's own published URL (self-reference)",
    "EMAIL_BASE_URL": "external tenant-facing URL (staging.hub.example.com)",
    "HUB_DOMAIN": "external tenant-facing URL",
}

PLACEHOLDER_MARKERS = (
    "placeholder",
    "changeme",
    "change-me",
    "rotate-me",
    "dev-staging",
    "your-",
    "example.com-secret",
    "sk_test_local",
)


# ── helpers ────────────────────────────────────────────────────────────────


def read_compose() -> dict:
    with open(COMPOSE_STAGING) as f:
        return yaml.safe_load(f)


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse a dotenv file (KEY=value, # comments, no quoting surprises)."""
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


VAR_REF = re.compile(r"\$\{([A-Z0-9_]+)(:[-?][^}]*)?\}")


def expand(value: str, env: dict[str, str]) -> str:
    """Expand ${VAR} / ${VAR:-default} references using the env map."""

    def _sub(m: re.Match) -> str:
        name = m.group(1)
        if env.get(name):
            return env[name]
        default = m.group(2) or ""
        if default.startswith(":-"):
            return default[2:]
        return ""

    prev, out = None, value
    while out != prev:
        prev = out
        out = VAR_REF.sub(_sub, out)
    return out


def env_map_of(service: dict) -> dict[str, str]:
    """Compose env: dict form → {key: value}; list form → joined."""
    env = service.get("environment") or {}
    if isinstance(env, dict):
        return env
    if isinstance(env, list):
        result: dict[str, str] = {}
        for item in env:
            if isinstance(item, str) and "=" in item:
                k, _, v = item.partition("=")
                result[k] = v
        return result
    return {}


URL_HOST = re.compile(r"(?:redis|postgres|postgresql|amqp|http|https)://(?:[^@/]*@)?([^:/]+)")


def service_url_hosts(compose: dict, env_file: dict[str, str]) -> dict[str, set[str]]:
    """Map env KEY → set of hosts appearing in its value across all services."""
    hosts: dict[str, set[str]] = {}
    for svc in compose["services"].values():
        for key, value in env_map_of(svc).items():
            expanded = expand(value, env_file)
            for h in URL_HOST.findall(expanded):
                hosts.setdefault(key, set()).add(h)
        for key, value in env_map_of(svc).items():
            if key.endswith("_HOST"):
                hosts.setdefault(key, set()).add(expand(value, env_file))
    return hosts


# Full port entry: "<host>:<digits>[/proto]" — the CONTAINER port is the last
# colon-digits group, so the host part may itself contain colons
# (${VAR:-default}). A naive split(":")[0] truncates at the default's colon.
PORT_ENTRY = re.compile(r"^(.+):(\d+)(?:/(udp|tcp))?$")


def host_port_bindings(compose: dict, env_file: dict[str, str]) -> dict[str, list[str]]:
    """Map expanded host port → services binding it (short syntax only)."""
    bindings: dict[str, list[str]] = {}
    for name, svc in compose["services"].items():
        for entry in svc.get("ports") or []:
            if not isinstance(entry, str) or not entry.strip():
                continue
            match = PORT_ENTRY.match(entry)
            if not match:
                continue  # long syntax ({target: ..., published: ...}) — rare here
            expanded = expand(match.group(1), env_file)
            bindings.setdefault(expanded, []).append(name)
    return bindings


def makefile_target_recipe(target: str) -> str:
    """Extract the recipe of a Makefile target (contiguous tab-indented lines)."""
    text = MAKEFILE.read_text()
    lines = text.splitlines()
    out: list[str] = []
    for i, line in enumerate(lines):
        if line.startswith(f"{target}:"):
            j = i + 1
            while j < len(lines) and lines[j].startswith("\t"):
                out.append(lines[j])
                j += 1
            return "\n".join(out)
    return ""


# ── static compose contracts (CI-safe: no .env.staging required) ────────────


class TestStagingComposeStaticContracts:
    def test_failfast_vars_are_the_registered_set(self):
        raw = COMPOSE_STAGING.read_text()
        found = set(re.findall(r"\$\{([A-Z0-9_]+):\?", raw))
        assert found == REGISTERED_FAILFAST_VARS, (
            "docker-compose.staging.yml ${VAR:?} set drifted from the "
            f"registered fail-fast secrets. Found: {sorted(found)}; "
            f"registered: {sorted(REGISTERED_FAILFAST_VARS)}. Update the "
            "registry + docs/operations/staging-secrets-registry.md together "
            "with the compose change."
        )

    def test_host_ports_unique_after_default_expansion(self):
        compose = read_compose()
        bindings = host_port_bindings(compose, {})
        dupes = {p: svcs for p, svcs in bindings.items() if len(svcs) > 1}
        assert not dupes, (
            "Host-port collision after ${VAR:-default} expansion: "
            f"{dupes}. Pin distinct ports (e.g. PGBOUNCER_PORT and "
            "PREFECT_DB_PORT both default to 5433)."
        )

    def test_service_urls_reference_defined_services(self):
        compose = read_compose()
        service_names = set(compose["services"])
        hosts = service_url_hosts(compose, {})
        offenders = {}
        for key, host_set in hosts.items():
            if key in HOST_ALLOWLIST:
                continue
            bad = {
                h
                for h in host_set
                if h not in service_names and h not in ("localhost", "127.0.0.1")
            }
            if bad:
                offenders[key] = sorted(bad)
        assert not offenders, (
            f"Service-to-service env references resolve to hosts that are not "
            f"compose services: {offenders}. (REDIS_URL=redis://redis is the "
            "canonical bug — the service is named redis-cache.)"
        )

    def test_smtp_relay_exists_when_email_is_smtp(self):
        compose = read_compose()
        api_env = env_map_of(compose["services"]["api-service"])
        worker_env = env_map_of(compose["services"]["worker-service"])
        email_backend = expand(
            api_env.get("EMAIL_BACKEND", worker_env.get("EMAIL_BACKEND", "smtp")),
            {},
        )
        if email_backend != "smtp":
            pytest.skip("EMAIL_BACKEND is not smtp — relay not required")
        relay_images = ("mailhog", "mailpit", "smtp4dev")
        has_relay = any(
            any(marker in str(svc.get("image", "")).lower() for marker in relay_images)
            for svc in compose["services"].values()
        )
        assert has_relay, (
            "EMAIL_BACKEND=smtp but the staging compose has no SMTP relay "
            "service. SMTP_HOST=localhost inside a container points at the "
            "container itself — beta cohort invite emails would never leave "
            "the stack. Add a MailHog relay service and point SMTP_HOST at it."
        )

    def test_make_staging_up_passes_env_file(self):
        recipe = makefile_target_recipe("staging-up")
        assert recipe, "Makefile has no `staging-up` target"
        assert "-f docker-compose.staging.yml" in recipe, (
            "staging-up must select docker-compose.staging.yml"
        )
        assert "--env-file .env.staging" in recipe, (
            "staging-up must pass --env-file .env.staging — compose only "
            "auto-loads `.env`, so `docker compose -f docker-compose.staging.yml "
            "config` fails on the ${VAR:?} secrets without it."
        )

    def test_staging_volumes_are_named(self):
        compose = read_compose()
        volumes = compose.get("volumes", {})
        for name, svc in compose["services"].items():
            for mount in svc.get("volumes") or []:
                if not isinstance(mount, str):
                    continue
                source = mount.split(":")[0]
                if source in (".", "..") or source.startswith(("./", "../", "/", "$")):
                    continue  # bind mounts / host paths are expected
                assert source in volumes, (
                    f"{name} mounts anonymous/undeclared volume {source!r} — "
                    "staging data volumes must be named for backup/restore."
                )


# ── real .env.staging contracts (secret material — absent in CI) ────────────


pytestmark_env_only = pytest.mark.skipif(
    not ENV_STAGING.exists(),
    reason=".env.staging is gitignored secret material — only checked where it exists",
)


@pytestmark_env_only
class TestStagingEnvFileContracts:
    def test_all_failfast_vars_present(self):
        env = parse_env_file(ENV_STAGING)
        missing = {v for v in REGISTERED_FAILFAST_VARS if not env.get(v)}
        assert not missing, f".env.staging is missing fail-fast secrets: {sorted(missing)}"

    def test_no_placeholder_secrets(self):
        env = parse_env_file(ENV_STAGING)
        offenders = {}
        for key, value in env.items():
            lowered = value.lower()
            if any(m in lowered for m in PLACEHOLDER_MARKERS) and value:
                offenders[key] = value
        assert not offenders, (
            f".env.staging carries placeholder secret values: {offenders}. "
            "Generate real random secrets (see docs/operations/"
            "staging-secrets-registry.md) — placeholder keys are the reason "
            "smoke/invite flows fail mysteriously in staging."
        )

    def test_role_pair_secrets_differ(self):
        env = parse_env_file(ENV_STAGING)
        pairs = [
            (
                "MinIO root user vs app user",
                env.get("MINIO_ROOT_USER"),
                env.get("AWS_ACCESS_KEY_ID"),
            ),
            (
                "MinIO root password vs app secret",
                env.get("MINIO_ROOT_PASSWORD"),
                env.get("AWS_SECRET_ACCESS_KEY"),
            ),
            (
                "PgBouncer admin vs auth",
                env.get("PGBOUNCER_ADMIN_PASSWORD"),
                env.get("PGBOUNCER_AUTH_PASSWORD"),
            ),
            (
                "Postgres vs PgBouncer auth",
                env.get("POSTGRES_PASSWORD"),
                env.get("PGBOUNCER_AUTH_PASSWORD"),
            ),
        ]
        offenders = {}
        for label, a, b in pairs:
            if a is None or b is None:
                continue
            if a == b:
                offenders[label] = a
        assert not offenders, (
            f"Role-pair secrets are reused: {list(offenders)}. Each role gets "
            "its own credential so one compromise/rotation never cascades."
        )

    def test_secret_minimum_length(self):
        env = parse_env_file(ENV_STAGING)
        secret_keys = {k for k in env if any(s in k for s in ("PASSWORD", "SECRET_KEY", "_KEY"))}
        secret_keys.discard("STRIPE_PUBLISHABLE_KEY")  # public by design
        short = {k: len(env[k]) for k in secret_keys if env[k] and len(env[k]) < 16}
        assert not short, f"Secrets shorter than 16 chars: {short}"

    def test_env_file_host_ports_are_unique(self):
        env = parse_env_file(ENV_STAGING)
        port_keys = [k for k in env if k.endswith("_PORT")]
        seen: dict[str, str] = {}
        dupes = {}
        for key in port_keys:
            value = env[key]
            if not value.isdigit():
                continue
            if value in seen:
                dupes[value] = [seen[value], key]
            else:
                seen[value] = key
        assert not dupes, f"Duplicate host ports inside .env.staging: {dupes}"

    def test_no_duplicate_keys(self):
        """dotenv consumers (docker compose --env-file) keep the LAST value
        for a duplicated key — the earlier declaration silently dies. The
        canonical staging bug: POSTGRES_PORT declared twice (in-network 5432
        under Database Configuration AND host-map 5437), so edits to the
        first line change nothing and edits to the second change the app
        connection. One key, one purpose: the host-map value must live under
        its own key (POSTGRES_HOST_PORT)."""
        seen: dict[str, list[int]] = {}
        for line_no, raw_line in enumerate(ENV_STAGING.read_text().splitlines(), start=1):
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key = line.partition("=")[0].strip()
            seen.setdefault(key, []).append(line_no)
        dupes = {k: lines for k, lines in seen.items() if len(lines) > 1}
        assert not dupes, (
            f".env.staging declares the same key multiple times: {dupes}. "
            "docker compose --env-file resolves to the LAST occurrence — the "
            "earlier value is dead and edits to it silently do nothing."
        )

    def test_secrets_registry_covers_every_secret(self):
        assert SECRETS_REGISTRY.exists(), (
            "docs/operations/staging-secrets-registry.md does not exist — "
            "every staging secret needs an owner + rotation entry."
        )
        registry = SECRETS_REGISTRY.read_text()
        uncovered = {v for v in REGISTRY_COVERAGE if v not in registry}
        assert not uncovered, (
            f"Secrets missing from the owner + rotation registry: {sorted(uncovered)}"
        )
