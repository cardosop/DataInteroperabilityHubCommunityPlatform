"""W1.18 (oss-release-remediation) — docker-compose.production.yml Redis contract.

Pins the production-compose Redis hardening (host-side, real YAML — the
``test_staging_env_contract.py`` convention):

  1. Every Redis ``--requirepass`` uses the ``${VAR:?}`` fail-fast form —
     a missing password aborts ``docker compose config`` instead of
     starting redis with ``--requirepass ""`` (empty password = no auth).
  2. The redis healthchecks use the same fail-fast form.
  3. No application service carries a passwordless
     ``redis://<host>:6379/`` URL (environment, command or healthcheck) —
     the W0.7/W0.8 class where a requirepass'd instance is reached
     without credentials.
  4. The compliance scanner + RQ worker (the only services that hardcoded
     URLs) carry authenticated fail-fast URLs.
  5. The Django booters (api-service, worker-heavy, worker-light) either
     carry authenticated URL envs or rely on ``env_file: .env.production``
     (whose template documents the authenticated forms) — no passwordless
     literals.

Run host-side (no Django/DB required):
    venv/bin/python -m pytest scripts/tests/test_production_compose_contract.py -q
"""

import re
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
COMPOSE_PRODUCTION = PROJECT_ROOT / "docker-compose.production.yml"

# The fail-fast secret set for production Redis. Adding a new
# ``${VAR:?}`` redis secret without registering it here fails the suite.
REGISTERED_REDIS_FAILFAST_VARS = {
    "REDIS_CACHE_PASSWORD",
    "REDIS_QUEUE_PASSWORD",
    "REDIS_EVENTS_PASSWORD",
    "REDIS_CHANNELS_PASSWORD",
}

# Passwordless redis:// URL literal anywhere in app-service config.
_PASSWORDLESS_REDIS_URL = re.compile(r"redis://(?!:)")
# The four redis servers.
_REDIS_SERVICES = (
    "redis-cache",
    "redis-queue",
    "redis-events",
    "redis-channels",
)
# Application services that reach Redis (Django booters + compliance).
_REDIS_CONSUMER_SERVICES = (
    "api-service",
    "worker-heavy",
    "worker-light",
    "compliance-service",
    "compliance-rq-worker",
)


@pytest.fixture(scope="module")
def production_compose():
    assert COMPOSE_PRODUCTION.exists(), (
        "docker-compose.production.yml not found"
    )
    with open(COMPOSE_PRODUCTION) as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def production_compose_text():
    return COMPOSE_PRODUCTION.read_text()


def _service_text(compose_text: str, service_name: str) -> str:
    """The raw YAML slice for one top-level service (by ``^  name:``)."""
    lines = compose_text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.match(rf"^  {re.escape(service_name)}:$", line):
            start = i
            break
    assert start is not None, f"service {service_name} not found"
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if re.match(r"^  [a-z0-9_-]+:$", lines[i]):
            end = i
            break
    return "\n".join(lines[start:end])


def _failfast(var: str) -> str:
    """The compose fail-fast literal for a var: ${VAR:?}."""
    return "${" + var + ":?}"


class TestRedisRequirepassFailFast:
    """Every production redis server + healthcheck uses ${VAR:?}."""

    def test_requirepass_uses_failfast_form(self, production_compose_text):
        for name in _REDIS_SERVICES:
            svc = _service_text(production_compose_text, name)
            match = re.search(r"--requirepass\s+\$\{([A-Z_]+)(?::\?)?\}", svc)
            assert match, (
                f"{name}: --requirepass must reference ${{VAR:?}} (fail-fast)."
            )
            var = match.group(1)
            assert _failfast(var) in svc, (
                f"{name}: --requirepass must use the fail-fast "
                f"{_failfast(var)} form — a plain ${{{var}}} starts redis "
                "with an empty password (no auth) when unset."
            )
            assert var in REGISTERED_REDIS_FAILFAST_VARS, (
                f"{name}: unregistered fail-fast redis var {var}"
            )

    def test_healthchecks_use_failfast_form(self, production_compose_text):
        for name in _REDIS_SERVICES:
            svc = _service_text(production_compose_text, name)
            for match in re.finditer(
                r"redis-cli[^\n]*-a\s+\$\{([A-Z_]+)(?::\?)?\}", svc
            ):
                var = match.group(1)
                assert _failfast(var) in svc, (
                    f"{name}: healthcheck must use {_failfast(var)} "
                    "(fail-fast) so the probe never authenticates with an "
                    "empty password."
                )

    def test_no_plain_requirepass_interpolation(self, production_compose_text):
        # No ${REDIS_*_PASSWORD} without the :? qualifier anywhere.
        for var in REGISTERED_REDIS_FAILFAST_VARS:
            plain = re.findall(rf"\${{{var}}}(?!:)", production_compose_text)
            assert not plain, (
                f"{var} must always use the {_failfast(var)} fail-fast form; "
                f"found {len(plain)} plain occurrence(s)."
            )


class TestRedisConsumerUrls:
    """No passwordless redis:// URLs in app-service config; compliance
    workers carry authenticated fail-fast URLs."""

    def test_no_passwordless_redis_urls_in_app_services(
        self, production_compose_text
    ):
        for name in _REDIS_CONSUMER_SERVICES:
            svc_text = _service_text(production_compose_text, name)
            assert not _PASSWORDLESS_REDIS_URL.search(svc_text), (
                f"{name}: passwordless redis:// URL found — a requirepass'd "
                "production redis would refuse the connection."
            )

    def test_compliance_services_use_authenticated_failfast_url(
        self, production_compose_text
    ):
        for name in ("compliance-service", "compliance-rq-worker"):
            svc = _service_text(production_compose_text, name)
            assert (
                "redis://:${REDIS_QUEUE_PASSWORD:?}@redis-queue:6379/0" in svc
            ), (
                f"{name}: must carry the authenticated fail-fast "
                "REDIS_QUEUE_URL (redis://:${REDIS_QUEUE_PASSWORD:?}@…)."
            )
            assert "redis://redis-queue:6379/0" not in svc, (
                f"{name}: the pre-W1.18 passwordless literal is gone."
            )

    def test_django_booters_have_no_passwordless_redis_env(
        self, production_compose_text
    ):
        for name in ("api-service", "worker-heavy", "worker-light"):
            svc = _service_text(production_compose_text, name)
            assert not re.search(r"REDIS_[A-Z_]*URL=redis://(?!:)", svc), (
                f"{name}: passwordless REDIS_*_URL environment literal."
            )
            assert "env_file" in svc, (
                f"{name}: relies on env_file (.env.production) for its "
                "authenticated REDIS_*_URL values — the boot guard in "
                "hub/settings.py enforces them at startup."
            )

    def test_compose_parses_with_failfast_placeholders(
        self, production_compose
    ):
        # Structure sanity only — docker compose config itself FAILS without
        # the env values (that is the point of :?); YAML must stay valid.
        assert "services" in production_compose
