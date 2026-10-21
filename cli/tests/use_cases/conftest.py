"""
Pytest fixtures for CLI use-cases tests.

Mirrors ``tests/integration/conftest.py``: auto-skips use-cases tests when
no live Meshant API is reachable. use-cases tests run a real CLI against a
real backend and have no business failing on dev boxes that don't run docker
compose. Set ``MESHANT_FORCE_INTEGRATION=1`` to bypass.

W16 (Phase T.4): the auto-skip is the shared ``tests._env_skip`` policy —
in CI an unreachable API RAISES instead of skipping (the environment failure
announces itself); local runs keep the graceful skip.
"""

# Django-backed modules in this directory import ``hub``/Django models at
# module scope, so settings must be configured before collection.  Kept
# here (not in the suite-root conftest) so unit batches never import
# ``hub.settings`` — that import opens a real PostgreSQL connection.
from tests._django_bootstrap import ensure_django

ensure_django()

import json
import os
import re

import pytest
from click.testing import CliRunner
from datahub_cli.config import Config
from tests._env_skip import auto_skip_unreachable_api

_api_test_port = os.environ.get("API_TEST_PORT", "8000")
_DEFAULT_API_BASE = f"http://localhost:{_api_test_port}"


def pytest_collection_modifyitems(config, items):
    auto_skip_unreachable_api(
        items,
        suite_label="CLI use-cases tests",
        path_scopes=("/tests/use_cases/",),
        # The batch runner exposes the API on API_TEST_PORT (8001) — the
        # helper's own default probes 8000, where nothing listens.
        default_port=int(_api_test_port),
    )


# ---------------------------------------------------------------------------
# Shared fixtures for CLI e2e tests
# ---------------------------------------------------------------------------


def extract_id(output: str) -> str:
    """Pull a resource id out of CLI output, JSON or table form.

    ``test_mid_journey_failure.py`` has imported this from this conftest
    since it was written, but the helper was never defined anywhere in the
    repository's history, so the module could never be collected.  Handles
    both ``--format json`` output and the table form the default
    ``assets create`` path prints (``ID: <uuid>``).
    """
    try:
        data = json.loads(output)
    except (json.JSONDecodeError, ValueError):
        data = None
    if isinstance(data, dict):
        return str(data.get("id") or "")
    match = re.search(r"^ID:\s*(\S+)\s*$", output, flags=re.MULTILINE)
    return match.group(1) if match else ""


def unique_key(prefix: str = "test") -> str:
    """Generate a unique asset/resource key for E2E tests.

    Uses a short UUID suffix to avoid 409 Conflict on staging
    when tests are re-run against persistent data.

    Key format: lowercase alphanumeric with single hyphens only
    (no underscores, no double hyphens, no trailing hyphens).
    """
    import uuid

    # Strip trailing hyphens from prefix to avoid double-hyphen
    clean = prefix.rstrip("-").lower()
    return f"{clean}-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def runner():
    """Click CLI runner."""
    return CliRunner()


@pytest.fixture
def api_base_url():
    """API base URL — reads from env for staging, falls back to localhost."""
    return os.environ.get(
        "MESHANT_API_URL",
        os.environ.get("ODH_BASE_URL", f"{_DEFAULT_API_BASE}/api/v1"),
    )


@pytest.fixture
def temp_config_dir(tmp_path, monkeypatch):
    """Create an isolated temporary config directory for the CLI."""
    config_dir = tmp_path / ".datahub"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"

    monkeypatch.setattr("datahub_cli.config.CONFIG_DIR", config_dir)
    monkeypatch.setattr("datahub_cli.config.CONFIG_FILE", config_file)

    return config_dir, config_file


@pytest.fixture
def temp_file(tmp_path):
    """Factory fixture: create a temporary file with given extension and content."""

    def _create_file(extension, content):
        file_path = tmp_path / f"test{extension}"
        file_path.write_text(content)
        return str(file_path), content

    return _create_file


def _setup_cli_auth(_api_base_url: str, config: Config) -> bool:
    """Set up authentication for CLI E2E tests.

    Tries, in order:
    1. ``TEST_API_KEY`` or ``DATAHUB_API_KEY`` env var
    2. Persona provisioning (``provision_persona("data_engineer")``)
       which handles rate-limit backoff, token caching, and self-heal.

    Returns True on success.

    NOTE: there is deliberately NO in-memory token cache here.  The old
    ``_cached_access_token`` short-circuit re-used the session's first
    persona JWT for every later test without validation — but destructive
    auth tests in ``test_auth_lifecycle.py`` (logout-all, role changes)
    bump the user's ``token_version`` mid-suite, so every subsequent test
    that reused the stale token failed with "Token has been invalidated"
    (measured 2026-08-28: ~45 tests in one run).  ``provision_persona``'s
    own disk cache validates tokens against ``/auth/me/`` and re-logins
    when they are evicted, so always going through it makes the suite
    self-healing at the cost of one cheap API call per test.
    """
    # --- Method 1: explicit API key from environment ---
    api_key = os.getenv("TEST_API_KEY") or os.getenv("DATAHUB_API_KEY")
    if api_key:
        config.set_api_key(api_key)
        return True

    # --- Method 2: persona provisioning (handles 429, cache, self-heal) ---
    try:
        from tests._persona_provisioning import provision_persona

        creds = provision_persona("data_engineer")
        if creds and creds.api_key:
            config.set_access_token(creds.api_key)
            return True
    except Exception:
        pass

    return False


_login_failure_reason: str = ""


@pytest.fixture
def authenticated_config(temp_config_dir, api_base_url):
    """Config instance with API base URL and authentication already set up.

    CLI commands go through ``datahub_cli.api_client.api_client``, which
    reads the GLOBAL ``datahub_cli.config.config`` singleton — a separate
    ``Config()`` instance here was invisible to the CLI, so every command
    ran unauthenticated and the suite failed with
    "Authentication failed. Please run 'datahub login' again."
    Authenticate the global singleton instead and return it.
    """
    from datahub_cli.config import config as global_config

    global_config.set_api_base_url(api_base_url)

    if not _setup_cli_auth(api_base_url, global_config):
        reason = _login_failure_reason or (
            "Set TEST_API_KEY or TEST_USER_EMAIL/TEST_USER_PASSWORD, "
            "or ensure pre-seeded E2E accounts exist."
        )
        pytest.skip(f"Could not set up CLI authentication for E2E test. {reason}")

    return global_config


def _register_api_delete_cleanup(
    cleanup_registry,
    path: str,
    label: str,
    *,
    headers: dict | None = None,
    base_url: str | None = None,
) -> None:
    """Register a live-API ``DELETE <path>`` callback at test teardown.

    The use_cases suite runs against the PERSISTENT full-mode backend on
    :8001.  Every resource a test creates counts toward the persona
    tenant's plan limits (``RESOURCE_COUNTERS`` counts DRAFT assets,
    users, contracts, files...), so tests that never delete their
    resources accumulate state across runs and the whole suite eventually
    403s with ``plan_limit_exceeded`` — measured 2026-08-28 at 100/100
    assets on the pro plan.  Registering cleanup here keeps the shared
    tenant under its limits without depending on the 24h
    ``purge_test_data`` sweep.

    Deletion goes through the live API (not the Django ORM) so it runs the
    same authorization and business-rule path a user would.

    Auth and base URL are snapshotted NOW: teardown runs after later tests
    may have re-pointed the global config (e.g. the marketplace tests call
    ``config.set_api_key(...)`` in setUp), and a callback that reads the
    live config deletes with the WRONG tenant's credentials — measured:
    deletes landed on ``cli-mapping-e2e-test-tenant`` with a mapping-test
    API key and 403'd with "No active subscription".  Tests that drive the
    API directly with persona credentials (not the global CLI config) pass
    explicit ``headers``/``base_url``.
    """
    from datahub_cli import api_client as _api
    from datahub_cli.config import config as _cfg

    if base_url is None:
        base_url = _cfg.get_api_base_url()
    base = base_url.rstrip("/")
    if headers is None:
        headers = _api.auth_manager.get_auth_headers()

    def _delete() -> None:
        import requests

        requests.delete(f"{base}{path}", headers=headers, timeout=15)

    cleanup_registry.add(_delete, label=label)


def register_asset_cleanup(
    cleanup_registry,
    asset_id: str | None,
    label: str = "",
    *,
    headers: dict | None = None,
    base_url: str | None = None,
) -> None:
    """Register an asset for API deletion at test teardown."""
    if not asset_id:
        return
    _register_api_delete_cleanup(
        cleanup_registry,
        f"/assets/{asset_id}/",
        label or f"asset:{asset_id}",
        headers=headers,
        base_url=base_url,
    )


def register_contract_cleanup(
    cleanup_registry,
    contract_id: str | None,
    label: str = "",
    *,
    headers: dict | None = None,
    base_url: str | None = None,
) -> None:
    """Register a contract for API deletion at test teardown.

    Contracts count toward the tenant's ``max_contracts`` plan limit, so
    every ``contracts create`` that never deletes inside the test must
    register here.  Deletion uses ``DELETE /contracts/{id}/``.
    """
    if not contract_id:
        return
    _register_api_delete_cleanup(
        cleanup_registry,
        f"/contracts/{contract_id}/",
        label or f"contract:{contract_id}",
        headers=headers,
        base_url=base_url,
    )


def register_connection_cleanup(
    cleanup_registry,
    connection_id: str | None,
    label: str = "",
    *,
    headers: dict | None = None,
    base_url: str | None = None,
) -> None:
    """Register a marketplace connection for API deletion at test teardown.

    Mirrors the CLI ``marketplace connections delete`` route:
    ``DELETE /integrations/marketplace/connections/{id}/``.
    """
    if not connection_id:
        return
    _register_api_delete_cleanup(
        cleanup_registry,
        f"/integrations/marketplace/connections/{connection_id}/",
        label or f"connection:{connection_id}",
        headers=headers,
        base_url=base_url,
    )


def register_file_cleanup(
    cleanup_registry,
    file_id: str | None,
    label: str = "",
    *,
    headers: dict | None = None,
    base_url: str | None = None,
) -> None:
    """Register an uploaded file for API deletion at test teardown.

    Uploaded files consume tenant storage; ``DELETE /files/{id}/`` keeps
    the suite re-runnable against the persistent backend.
    """
    if not file_id:
        return
    _register_api_delete_cleanup(
        cleanup_registry,
        f"/files/{file_id}/",
        label or f"file:{file_id}",
        headers=headers,
        base_url=base_url,
    )


def seed_marketplace_e2e_tenant_in_container(
    *,
    slug: str,
    name: str,
    email: str,
    key_name: str,
    scopes: tuple[str, ...] = ("integrations:read", "integrations:write"),
) -> dict[str, str]:
    """Seed the FULL LiveServer E2E fixture set inside the stack's container:
    tenant (marketplace flag ON) + ACTIVE BASE subscription + ACTIVE user +
    DATA_PROVIDER role + scoped API key.  Returns ``{"tenant_id", "api_key"}``.

    Root-cause rationale (measured 2026-09-20 on the marketplace
    mapping/sync suites): rows written by in-process ORM during a
    ``LiveServerTestCase`` setUp live inside the TransactionTestCase
    transaction, while the live server is a THREADED WSGI server whose
    request threads open their own DB connections and cannot see
    uncommitted rows — intermittent 401 / "No active subscription" 403
    flakes depending on which thread serves the request.  Committing the
    whole fixture set through the container shell (the pattern proven by
    ``test_baas_sdk_comprehensive``'s setup script) makes every row
    visible to every connection; the test process re-reads them
    afterwards (READ COMMITTED sees committed data on the next statement).

    W16: when the stack is unreachable the environment policy decides
    (graceful skip locally, loud raise in CI).
    """
    import subprocess
    from pathlib import Path

    from envpolicy import skip_or_fail

    script = (
        "from django.contrib.auth import get_user_model\n"
        "from hub.apps.tenants.models import Tenant, TenantPlan\n"
        "from hub.apps.billing.models import Subscription, SubscriptionStatus\n"
        "from hub.apps.users.models import Role, UserRole, UserStatus\n"
        "from hub.apps.auth.models import APIKey\n"
        "User = get_user_model()\n"
        "t = Tenant.objects.create(\n"
        f"    name={name!r}, slug={slug!r},\n"
        "    marketplace_integrations_enabled=True,\n"
        ")\n"
        "plan = TenantPlan.objects.first()\n"
        "if plan:\n"
        "    Subscription.objects.create(\n"
        "        tenant=t, category='BASE', plan=plan,\n"
        "        status=SubscriptionStatus.ACTIVE,\n"
        "    )\n"
        f"u = User.objects.create_user(email={email!r}, password='testpass123', tenant=t, status=UserStatus.ACTIVE)\n"
        "r, _ = Role.objects.get_or_create(tenant=t, name='DATA_PROVIDER', defaults={'description': 'Data Provider Role'})\n"
        "UserRole.objects.create(user=u, role=r)\n"
        "v = APIKey.generate_key()\n"
        f"APIKey.objects.create(user=u, tenant=t, name={key_name!r}, key_hash=APIKey.hash_key(v), scopes=list({list(scopes)!r}))\n"
        "print('SEEDED ' + str(t.id) + ' ' + v)\n"
    )
    repo_root = Path(__file__).resolve().parents[3]
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            "docker-compose.test.yml",
            "exec",
            "-T",
            "api-service-test",
            "python",
            "hub/manage.py",
            "shell",
        ],
        input=script,
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        skip_or_fail(
            "Container tenant seeding failed: " + (result.stderr or result.stdout or "")[:300]
        )
    for line in (result.stdout or "").splitlines():
        if line.startswith("SEEDED "):
            _, tenant_id, api_key = line.split(" ", 2)
            return {"tenant_id": tenant_id, "api_key": api_key}
    skip_or_fail("Container tenant seeding produced no SEEDED line: " + (result.stdout or "")[:200])
    return {}
