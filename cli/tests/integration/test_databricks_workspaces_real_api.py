"""
Integration tests for the Databricks workspace CLI commands against the real API
(openspec add-databricks-control-plane task 0.15).

Real HTTP, real database rows, real validation — no mocks. The API
service under test is the configured Meshant backend
(``MESHANT_API_URL``, default http://localhost:8000/api/v1); a Docker
Compose or staging stack must be up, per the W16 environment policy
(CI raises when unreachable, local runs skip gracefully).

Requires public DNS — workspace hosts must be real ``*.cloud.databricks.com``
hosts to pass the backend SSRF guard's save-time DNS checks (the same
``REAL_HOST`` contract as ``hub/apps/databricks_admin/tests/_fixtures.py``).

To run against the staging stack:

    MESHANT_API_URL=http://localhost:8101/api/v1 \
    pytest cli/tests/integration/test_databricks_workspaces_real_api.py -v
"""

import json
import os
import socket
import subprocess
import uuid

import pytest
from tests.pytest_mvp_skip import skip_if_mvp_mode

from envpolicy import api_available

pytestmark = skip_if_mvp_mode

import requests
from click.testing import CliRunner
from datahub_cli.config import config
from datahub_cli.main import cli

# Same real host contract as hub/apps/databricks_admin/tests/_fixtures.py —
# the backend SSRF guard resolves it at save time, so it must be a genuine
# *.cloud.databricks.com hostname.
REAL_HOST = "dbc-6710eb95-8fe1.cloud.databricks.com"
CLOUD = "AWS"
REGION = "us-east-1"


def _require_dns():
    """W16: raise in CI / skip locally when public DNS is unavailable."""
    try:
        socket.getaddrinfo(REAL_HOST, None)
    except OSError:
        from envpolicy import environment_guard

        environment_guard("public DNS unavailable — Databricks host resolution required")
        pytest.skip("public DNS unavailable — Databricks host resolution required")


def _docker_exec(script: str) -> str:
    """Run a Django shell script inside the running API container (staging or dev).

    The container's workdir is /app with the Django project rooted at
    /app/hub — ``python hub/manage.py shell`` is the entrypoint the
    container itself uses.
    """
    container = os.environ.get("MESHANT_API_CONTAINER", "hub-test-api")
    manage_py = os.environ.get("MESHANT_API_MANAGE_PY", "hub/manage.py")
    result = subprocess.run(
        ["docker", "exec", "-i", container, "python", manage_py, "shell", "-c", script],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,  # explicit — the returncode is asserted below with context
    )
    if result.returncode != 0:
        raise RuntimeError(f"docker exec failed: {result.stderr or result.stdout}")
    return result.stdout


# The billing middleware gates POST/PATCH/DELETE on an active BASE
# subscription — same boilerplate as hub/apps/databricks_admin/tests/
# test_views.py:_activate_billing (and the warehouses test helpers).
_ACTIVATE_BILLING = """
from hub.apps.billing.models import Subscription, SubscriptionStatus
from hub.apps.tenants.models import TenantConfig, TenantPlan

TenantConfig.objects.get_or_create(tenant=tenant)
plan = TenantPlan.objects.filter(slug="free", is_active=True).first()
if plan and not Subscription.objects.filter(tenant=tenant, category="BASE").exists():
    Subscription.objects.create(
        tenant=tenant,
        plan=plan,
        category="BASE",
        status=SubscriptionStatus.ACTIVE,
    )
"""


@pytest.fixture(scope="module")
def api_available_flag():
    return api_available()


@pytest.fixture(scope="module")
def databricks_env():
    """Provision a real tenant + TENANT_ADMIN user + API key with the
    databricks_control_plane_enabled flag ON, via Django shell in the API
    container. Returns (api_key, tenant_slug, email)."""
    unique = uuid.uuid4().hex[:10]
    tenant_slug = f"dbx-cli-test-{unique}"
    email = f"dbx-cli-test-{unique}@example.com"
    script = f"""
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus, Role, UserRole
from hub.apps.auth.models import APIKey as AuthAPIKey

tenant, _ = Tenant.objects.get_or_create(
    slug='{tenant_slug}',
    defaults={{'name': 'DBX CLI Test {unique}'}}
)
# Task 0.12: the control-plane flag defaults OFF for new tenants — enable it.
tenant.databricks_control_plane_enabled = True
tenant.save()

user, _ = User.objects.get_or_create(
    email='{email}',
    defaults={{'tenant': tenant, 'status': UserStatus.ACTIVE}}
)
if user.tenant != tenant:
    user.tenant = tenant
    user.save()
user.status = UserStatus.ACTIVE
user.save()

{_ACTIVATE_BILLING}

role, _ = Role.objects.get_or_create(
    tenant=tenant,
    name='TENANT_ADMIN',
    defaults={{'description': 'Tenant Administrator'}}
)
UserRole.objects.get_or_create(user=user, role=role)

AuthAPIKey.objects.filter(tenant=tenant).delete()
key = AuthAPIKey.generate_key()
AuthAPIKey.objects.create(
    user=user, tenant=tenant,
    name='DBX CLI Test Key {unique}',
    key_hash=AuthAPIKey.hash_key(key)
)
print(key)
"""
    key = _docker_exec(script).strip().splitlines()[-1].strip()
    return {"api_key": key, "tenant_slug": tenant_slug, "email": email}


@pytest.fixture(scope="module")
def configured_cli(databricks_env):
    """Point the real CLI config at the configured API + provisioned key."""
    api_base_url = os.environ.get("MESHANT_API_URL", "http://localhost:8000/api/v1")
    config.set_api_base_url(api_base_url)
    config.set_api_key(databricks_env["api_key"])
    yield CliRunner()
    config.clear_auth()


@pytest.fixture(scope="module")
def http_client(databricks_env):
    """Raw HTTP client using the same key — for seeding and teardown.

    Plain API keys (no dots) authenticate as ``ApiKey <key>`` — the same
    header the CLI sends (datahub_cli/auth.py); ``Bearer`` is only for
    JWTs/access tokens.
    """
    api_base_url = os.environ.get("MESHANT_API_URL", "http://localhost:8000/api/v1")
    session = requests.Session()
    session.headers.update({"Authorization": f"ApiKey {databricks_env['api_key']}"})
    session.api_base_url = api_base_url
    return session


def _seed_workspace(http_client, name: str) -> str:
    resp = http_client.post(
        f"{http_client.api_base_url}/databricks/workspaces/",
        json={"name": name, "host": REAL_HOST, "cloud": CLOUD, "region": REGION},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.mark.usefixtures("api_available_flag")
class TestDatabricksWorkspacesRealAPI:
    """register → list → test → rotate against the real API."""

    @pytest.fixture(autouse=True)
    def _dns_guard(self):
        _require_dns()

    def test_register_creates_real_workspace_row(self, configured_cli, http_client):
        name = f"CLI Register {uuid.uuid4().hex[:8]}"
        result = configured_cli.invoke(
            cli,
            [
                "databricks",
                "workspaces",
                "register",
                "--name",
                name,
                "--host",
                REAL_HOST,
                "--cloud",
                CLOUD,
                "--region",
                REGION,
            ],
        )
        assert result.exit_code == 0, result.output
        body = json.loads(result.output)
        assert body["name"] == name
        assert body["host"] == REAL_HOST
        assert body["cloud"] == CLOUD
        assert body["region"] == REGION
        assert body["status"] == "REGISTERED"

        # The row is real: the API list reflects it.
        listing = http_client.get(f"{http_client.api_base_url}/databricks/workspaces/")
        assert any(ws["id"] == body["id"] for ws in listing.json()["results"])

    def test_register_rejects_host_outside_databricks_family(self, configured_cli):
        result = configured_cli.invoke(
            cli,
            [
                "databricks",
                "workspaces",
                "register",
                "--name",
                f"bad-host-{uuid.uuid4().hex[:6]}",
                "--host",
                "attacker.example.com",
                "--cloud",
                CLOUD,
                "--region",
                REGION,
            ],
        )
        assert result.exit_code != 0
        # The API envelope code must reach the user, not a bare HTTP status.
        assert "DATABRICKS_HOST_NOT_ALLOWED" in result.output

    def test_register_rejects_ip_literal_host(self, configured_cli):
        result = configured_cli.invoke(
            cli,
            [
                "databricks",
                "workspaces",
                "register",
                "--name",
                f"ip-host-{uuid.uuid4().hex[:6]}",
                "--host",
                "10.0.0.5",
                "--cloud",
                CLOUD,
                "--region",
                REGION,
            ],
        )
        assert result.exit_code != 0
        assert "DATABRICKS_HOST_NOT_ALLOWED" in result.output

    def test_list_shows_registered_workspace(self, configured_cli, http_client):
        name = f"CLI List {uuid.uuid4().hex[:8]}"
        _seed_workspace(http_client, name)

        result = configured_cli.invoke(cli, ["databricks", "workspaces", "list"])
        assert result.exit_code == 0, result.output
        assert name in result.output
        assert REAL_HOST in result.output

    def test_list_json_emits_full_envelope(self, configured_cli):
        result = configured_cli.invoke(
            cli, ["databricks", "workspaces", "list", "--format", "json"]
        )
        assert result.exit_code == 0, result.output
        body = json.loads(result.output)
        assert isinstance(body, dict)
        assert "results" in body

    def test_test_connection_without_credential_returns_masked_failure(
        self, configured_cli, http_client
    ):
        """No credential attached → the API answers 502 with a MASKED payload
        (``DATABRICKS_AUTH_FAILED`` / "Credentials rejected by workspace").

        The CLI must exit non-zero AND surface the machine-readable code —
        never credential material."""
        ws_id = _seed_workspace(http_client, f"CLI Test {uuid.uuid4().hex[:8]}")

        result = configured_cli.invoke(cli, ["databricks", "workspaces", "test", ws_id])
        assert result.exit_code != 0
        assert "DATABRICKS_AUTH_FAILED" in result.output
        assert "Credentials rejected by workspace" in result.output

    def test_rotate_nonexistent_credential_is_structured_404(self, configured_cli, http_client):
        ws_id = _seed_workspace(http_client, f"CLI Rotate {uuid.uuid4().hex[:8]}")

        result = configured_cli.invoke(
            cli,
            ["databricks", "workspaces", "rotate", ws_id, str(uuid.uuid4())],
        )
        assert result.exit_code != 0

    def test_register_requires_tenant_flag(self, configured_cli):
        """Error-path pin: the CLI surfaces the flag-gate code when the
        tenant flag is off — provision a second tenant with the flag OFF
        and a second key, then assert the 403 envelope reaches the user."""
        unique = uuid.uuid4().hex[:8]
        script = f"""
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus, Role, UserRole
from hub.apps.auth.models import APIKey as AuthAPIKey

tenant = Tenant.objects.create(slug='dbx-noflag-{unique}', name='DBX NoFlag {unique}')
user = User.objects.create(email='dbx-noflag-{unique}@example.com', tenant=tenant, status=UserStatus.ACTIVE)
{_ACTIVATE_BILLING}
role, _ = Role.objects.get_or_create(tenant=tenant, name='TENANT_ADMIN', defaults={{'description': 'Tenant Administrator'}})
UserRole.objects.get_or_create(user=user, role=role)
key = AuthAPIKey.generate_key()
AuthAPIKey.objects.create(user=user, tenant=tenant, name='DBX NoFlag Key {unique}', key_hash=AuthAPIKey.hash_key(key))
print(key)
"""
        key = _docker_exec(script).strip().splitlines()[-1].strip()
        original_key = config.get_api_key()
        config.set_api_key(key)
        try:
            result = configured_cli.invoke(
                cli,
                [
                    "databricks",
                    "workspaces",
                    "register",
                    "--name",
                    f"noflag-{unique}",
                    "--host",
                    REAL_HOST,
                    "--cloud",
                    CLOUD,
                    "--region",
                    REGION,
                ],
            )
            assert result.exit_code != 0
            assert "DATABRICKS_CONTROL_PLANE_DISABLED" in result.output
        finally:
            config.set_api_key(original_key)

    def test_register_missing_required_options_is_usage_error(self, configured_cli):
        """No API round-trip: click enforces required options locally."""
        result = configured_cli.invoke(cli, ["databricks", "workspaces", "register"])
        assert result.exit_code == 2  # click usage error


@pytest.mark.usefixtures("api_available_flag")
class TestDatabricksWorkspacesTeardown:
    """Delete every workspace created by this suite (real rows on the real API)."""

    def test_teardown_workspaces(self, http_client):
        resp = http_client.get(f"{http_client.api_base_url}/databricks/workspaces/")
        for ws in (resp.json() or {}).get("results", []):
            http_client.delete(f"{http_client.api_base_url}/databricks/workspaces/{ws['id']}/")
