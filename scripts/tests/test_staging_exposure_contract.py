"""
Contract tests for the W0.7 staging-exposure hardening
(oss-release-remediation).

The compose-path staging stack must boot with NO default credentials and
NO unauthenticated surfaces (design.md fix 7, R2-S8 + H9 subset). These
pins parse the REAL docker-compose.staging.yml and fail the contract on:

- a redis instance without ``--requirepass`` (per-instance passwords,
  the docker-compose.production.yml precedent) or a passwordless
  ``redis://`` URL anywhere in the compose;
- a Grafana admin-password default (``:-admin`` is the leak class) or a
  GF_SERVER_ROOT_URL default that disagrees with the port default;
- observability ports (prometheus/grafana/alertmanager/jaeger) published
  on 0.0.0.0 instead of loopback;
- any repo-source bind-mount (``./`` paths) — only the staged
  ``./infrastructure/staging/config-artifacts/`` copies may be mounted
  (the ``.:/app`` RW repo mounts are the exposure itself);
- an INTERNAL_API_KEY / HUB_WORKER_API_KEY reference without ``:?``
  (fail-fast, no silent empty default);
- a queue-touching service without ``RQ_SERIALIZER=rq.serializers.
  JSONSerializer`` — including the bare-rq compliance CLI's own
  ``--serializer`` flag (both ends of the compliance queue must flip
  together);
- a ``make staging-up`` recipe that does not stage the config artifacts
  BEFORE the compose boot.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import ClassVar

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
COMPOSE = REPO_ROOT / "docker-compose.staging.yml"
MAKEFILE = REPO_ROOT / "Makefile"

REDIS_SERVICES = {
    "redis-cache": "REDIS_CACHE_PASSWORD",
    "redis-queue": "REDIS_QUEUE_PASSWORD",
    "redis-events": "REDIS_EVENTS_PASSWORD",
    "redis-channels": "REDIS_CHANNELS_PASSWORD",
}
OBSERVABILITY_SERVICES = ("prometheus", "grafana", "alertmanager", "jaeger")
QUEUE_SERVICES = (
    "api-service",
    "worker-service",
    "compliance-service",
    "compliance-rq-worker",
    "dq-service",
    "datacontract-service",
)


@pytest.fixture(scope="module")
def doc():
    with COMPOSE.open() as handle:
        return yaml.safe_load(handle)


def _env_of(service: dict) -> dict[str, str]:
    environment = service.get("environment") or {}
    if isinstance(environment, dict):
        return {str(k): str(v) for k, v in environment.items()}
    env: dict[str, str] = {}
    for item in environment:
        if isinstance(item, dict):
            env.update({str(k): str(v) for k, v in item.items()})
        elif isinstance(item, str) and "=" in item:
            key, value = item.split("=", 1)
            env[key] = value
    return env


def _port_lines(service: dict) -> list[str]:
    return [str(p) for p in service.get("ports", []) or []]


class TestRedisRequirepass:
    def test_every_redis_instance_requires_a_password(self, doc):
        services = doc["services"]
        for name, password_var in REDIS_SERVICES.items():
            assert name in services, f"{name} missing from the staging compose"
            command = services[name].get("command")
            joined = " ".join(command) if isinstance(command, list) else str(command)
            assert "--requirepass" in joined, f"{name} runs without requirepass"
            assert (
                f"${{{password_var}:?" in joined
            ), f"{name} does not require {password_var} fail-fast"

    def test_no_passwordless_redis_url_anywhere(self, doc):
        raw = COMPOSE.read_text()
        urls = re.findall(r"redis://[^\s'\"]+", raw)
        assert urls, "no redis URLs found — the pin is vacuous"
        for url in urls:
            assert ":${REDIS_" in url, f"passwordless redis URL: {url[:40]}..."
            assert ":?" in url, f"redis URL without fail-fast: {url[:40]}..."


class TestGrafanaHardening:
    def test_admin_password_is_failfast_with_no_default(self, doc):
        grafana = doc["services"]["grafana"]
        env = _env_of(grafana)
        password = env["GF_SECURITY_ADMIN_PASSWORD"]
        assert ":?" in password, "GF_SECURITY_ADMIN_PASSWORD is not fail-fast"
        assert (
            ":-admin" not in password
        ), "GF_SECURITY_ADMIN_PASSWORD still defaults to admin — the default-credential leak class"

    def test_server_root_url_default_matches_the_port_default(self, doc):
        grafana = doc["services"]["grafana"]
        env = _env_of(grafana)
        root_url = env["GF_SERVER_ROOT_URL"]
        assert (
            "${GRAFANA_PORT:-3001}" in root_url
        ), "GF_SERVER_ROOT_URL default disagrees with the port-map default"


class TestObservabilityLoopback:
    def test_observability_ports_bind_loopback_only(self, doc):
        for name in OBSERVABILITY_SERVICES:
            for line in _port_lines(doc["services"][name]):
                assert line.startswith(
                    ('"127.0.0.1:', "127.0.0.1:")
                ), f"{name} publishes a port off-loopback: {line}"


class TestNoRepoBindMounts:
    def test_no_full_repo_mounts(self, doc):
        raw = COMPOSE.read_text()
        assert ".:/app" not in raw, "a service still mounts the repo at /app"

    def test_every_source_mount_is_a_staged_artifact(self, doc):
        raw = COMPOSE.read_text()
        mounts = re.findall(r"-\s+(\./[^\s:\"]+):", raw)
        assert mounts, "no ./ mounts found — the pin is vacuous"
        for mount in mounts:
            assert mount.startswith(
                "./infrastructure/staging/config-artifacts/"
            ), f"repo-source mount outside the staged artifacts dir: {mount}"


class TestDatabasePasswordDefaults:
    def test_no_defaulted_db_passwords_anywhere(self):
        raw = COMPOSE.read_text()
        for forbidden in ("POSTGRES_PASSWORD:-hub", "PREFECT_DB_PASSWORD:-prefect"):
            assert forbidden not in raw, f"defaulted credential remains: {forbidden}"

    def test_prefect_db_healthcheck_has_a_start_period(self):
        prefect_db = yaml.safe_load(COMPOSE.read_text())["services"]["prefect-db"]
        healthcheck = prefect_db["healthcheck"]
        assert "start_period" in healthcheck, (
            "prefect-db lacks the init-window grace — the W0.7 evidence "
            "boot's slow-first-init failure would recur"
        )


class TestKeyFailFast:
    def test_internal_api_key_is_failfast_everywhere(self, doc):
        raw = COMPOSE.read_text()
        occurrences = re.findall(r"INTERNAL_API_KEY:\s*[^,\n}]+", raw)
        assert occurrences, "INTERNAL_API_KEY not found — the pin is vacuous"
        for occurrence in occurrences:
            assert (
                ":?" in occurrence
            ), f"non-fail-fast INTERNAL_API_KEY: {occurrence.strip()}"

    def test_worker_api_key_is_failfast_on_the_internal_callers(self, doc):
        for name in ("worker-service", "prefect-worker"):
            env = _env_of(doc["services"][name])
            assert "HUB_WORKER_API_KEY" in env, f"{name} lacks HUB_WORKER_API_KEY"
            assert (
                ":?" in env["HUB_WORKER_API_KEY"]
            ), f"{name} carries a defaulted HUB_WORKER_API_KEY"


class TestRqSerializerJson:
    def test_queue_services_carry_the_json_serializer(self, doc):
        for name in QUEUE_SERVICES:
            env = _env_of(doc["services"][name])
            assert "rq.serializers.JSONSerializer" in env.get(
                "RQ_SERIALIZER", ""
            ), f"{name} does not set RQ_SERIALIZER=rq.serializers.JSONSerializer"

    def test_compliance_cli_carries_the_serializer_flag(self, doc):
        command = doc["services"]["compliance-rq-worker"]["command"]
        joined = " ".join(command)
        assert "--serializer" in joined, (
            "the bare-rq compliance CLI lacks its own --serializer flag — "
            "the two ends of the compliance queue would disagree"
        )


class TestStagingRoleUrlWiring:
    """W0.8 — the W0.7 requirepass hardening's runtime casualties.

    settings.py falls back to PASSWORDLESS role URLs
    (``redis://redis-queue:6379/0``) when the env var is absent, so any
    Django-settings service whose compose env lacks the role URLs fails at
    first connect — the live staging worker-service died with
    ``Authentication required.`` on the rq queue connect while the api
    stayed "healthy" because its queue/cache/events connects are lazy.
    Every Django-settings service must carry the role URLs with the
    per-instance passwords, fail-fast (the compliance-service precedent),
    and the settings URL-auth guard must cover staging — it is the only
    thing that catches this class at boot.
    """

    # Every staging service that boots hub/settings.py — api, the rq
    # worker, and prefect-integration-service (which imports the Django
    # settings module for its config validation contract). The settings
    # guard now covers staging, so an unwired service fails AT BOOT with
    # a named URL instead of crashing at first connect.
    DJANGO_SERVICES: ClassVar[tuple[str, ...]] = (
        "api-service",
        "worker-service",
        "prefect-integration-service",
    )
    ROLE_URLS: ClassVar[dict[str, str]] = {
        "REDIS_CACHE_URL": "REDIS_CACHE_PASSWORD",
        "REDIS_QUEUE_URL": "REDIS_QUEUE_PASSWORD",
        "REDIS_EVENTS_URL": "REDIS_EVENTS_PASSWORD",
        "REDIS_CHANNELS_URL": "REDIS_CHANNELS_PASSWORD",
    }

    def test_django_services_carry_every_role_url_failfast(self, doc):
        for name in self.DJANGO_SERVICES:
            env = _env_of(doc["services"][name])
            for var, password_var in self.ROLE_URLS.items():
                assert var in env, (
                    f"{name} lacks {var} — the settings fallback URL is "
                    "passwordless and fails at first connect"
                )
                value = env[var]
                assert (
                    f":${{{password_var}:?" in value
                ), f"{name} {var} does not require {password_var} fail-fast"
                assert "@redis-" in value, f"{name} {var} carries no auth segment"

    def test_django_services_carry_an_authenticated_redis_url(self, doc):
        for name in self.DJANGO_SERVICES:
            env = _env_of(doc["services"][name])
            assert "REDIS_URL" in env, (
                f"{name} lacks REDIS_URL — the settings default is "
                "passwordless and the staging guard now rejects it at boot"
            )
            assert (
                ":${REDIS_CACHE_PASSWORD:?" in env["REDIS_URL"]
            ), f"{name} REDIS_URL does not require the cache password fail-fast"
            assert (
                "@redis-cache" in env["REDIS_URL"]
            ), f"{name} REDIS_URL carries no auth segment"

    def test_settings_guard_covers_staging(self):
        settings_text = (REPO_ROOT / "hub" / "settings.py").read_text()
        assert 'if ENVIRONMENT in ("production", "staging"):' in settings_text, (
            "the redis-URL authentication guard is production-only — staging "
            "silently falls back to passwordless role URLs (the live worker "
            "'Authentication required.' crash class)"
        )


class TestPrefectIntegrationAuthMode:
    """W0.8 — the staging prefect-server runs unauthenticated (bare
    ``prefect server start``); prefect-integration-service's fail-closed
    gate demands PREFECT_API_KEY for every non-dev env, so it crash-loops
    with no key. The compose must declare the server's actual auth mode and
    the gate must honor it (fail-closed default preserved)."""

    def test_compose_declares_the_unauth_server_mode(self, doc):
        env = _env_of(doc["services"]["prefect-integration-service"])
        assert env.get("PREFECT_API_AUTH_DISABLED") == "true", (
            "the staging prefect-server runs without API auth; the "
            "integration service must declare PREFECT_API_AUTH_DISABLED=true "
            "or it crash-loops demanding a key the server never enforces"
        )

    def test_gate_honors_the_optout(self):
        main_text = (
            REPO_ROOT / "services" / "prefect-integration" / "main.py"
        ).read_text()
        assert (
            "PREFECT_API_AUTH_DISABLED" in main_text
        ), "prefect-integration main.py gate ignores the auth-mode opt-out"


class TestSerializerWiring:
    def test_settings_wire_the_rq_serializer_env(self):
        settings_text = (REPO_ROOT / "hub" / "settings.py").read_text()
        assert 'RQ_SERIALIZER = env("RQ_SERIALIZER", default=None)' in settings_text
        assert (
            '_q["SERIALIZER"] = RQ_SERIALIZER' in settings_text
        ), "settings does not apply RQ_SERIALIZER to every RQ_QUEUES entry"

    def test_compliance_producer_resolves_the_env_serializer(self):
        scanner_text = (
            REPO_ROOT / "services" / "compliance-service" / "async_scanner.py"
        ).read_text()
        assert 'serializer=os.environ.get("RQ_SERIALIZER")' in scanner_text, (
            "the compliance Queue build ignores the env serializer — the "
            "two ends of the compliance queue would disagree"
        )


class TestMakefileStagerWiring:
    def test_staging_up_stages_artifacts_before_the_boot(self):
        text = MAKEFILE.read_text()
        match = re.search(
            r"^staging-up:.*\n((?:\t.*\n|\t.*\\\n\t.*\n)+)", text, re.MULTILINE
        )
        assert match, "staging-up target not found in Makefile"
        recipe = "\n".join(match.group(1).splitlines())
        assert (
            "stage_config_artifacts.sh" in recipe
        ), "staging-up does not stage the config artifacts before the boot"
        stage_idx = recipe.index("stage_config_artifacts.sh")
        up_idx = recipe.index("compose")
        assert stage_idx < up_idx, "the stager must run BEFORE the compose up"
