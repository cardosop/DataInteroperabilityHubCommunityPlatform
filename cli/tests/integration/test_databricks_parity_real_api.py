"""Shared DoD gate (openspec add-databricks-control-plane — "CLI parity
commands shipped") — the parity command families against the REAL API.

Real HTTP, real database rows, real validation — no mocks (the
test_databricks_workspaces_real_api convention). The API service under
test is the configured Meshant backend (``MESHANT_API_URL``, default
http://localhost:8000/api/v1); a Docker Compose or staging stack must
be up, per the W16 environment policy (CI raises when unreachable,
local runs skip gracefully).

Read surfaces are verified end-to-end (real tenant, real workspace
row, real RLS); the UC change DRAFT lifecycle (create → show →
comment → timeline) runs against the real 2.4 guards; unknown
resources pin the classified-error surface the CLI relays. Write
paths that mutate real Databricks state (submit → execution) stay in
the backend suite — the CLI issues the same endpoint shapes the
backend tests already own.

Requires public DNS — workspace hosts must be real
``*.cloud.databricks.com`` hosts to pass the backend SSRF guard's
save-time DNS checks (the same REAL_HOST contract as
test_databricks_workspaces_real_api.py).

To run against the test stack:

    MESHANT_API_URL=http://localhost:8001/api/v1 \
    pytest cli/tests/integration/test_databricks_parity_real_api.py -v
"""

import json
import os
import socket
import subprocess
import uuid

import pytest
import requests
from click.testing import CliRunner
from datahub_cli.config import config
from datahub_cli.main import cli
from tests.pytest_mvp_skip import skip_if_mvp_mode

from envpolicy import api_available

pytestmark = skip_if_mvp_mode

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
        pytest.skip(
            "public DNS unavailable — Databricks host resolution required "
            "TICKET=PREPRO01-DBX-DNS EXPIRES=2026-12-31"
        )


def _docker_exec(script: str) -> str:
    """Run a Django shell script inside the running API container (the
    test_databricks_workspaces_real_api helper)."""
    container = os.environ.get("MESHANT_API_CONTAINER", "hub-test-api")
    manage_py = os.environ.get("MESHANT_API_MANAGE_PY", "hub/manage.py")
    result = subprocess.run(
        ["docker", "exec", "-i", container, "python", manage_py, "shell", "-c", script],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"docker exec failed: {result.stderr or result.stdout}")
    return result.stdout


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
    databricks control-plane AND ML-asset flags ON (the parity surfaces
    gate on both)."""
    unique = uuid.uuid4().hex[:10]
    tenant_slug = f"dbx-parity-test-{unique}"
    email = f"dbx-parity-test-{unique}@example.com"
    script = f"""
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus, Role, UserRole
from hub.apps.auth.models import APIKey as AuthAPIKey

tenant, _ = Tenant.objects.get_or_create(
    slug='{tenant_slug}',
    defaults={{'name': 'DBX Parity Test {unique}'}}
)
# Task 0.12: the control-plane flag defaults OFF for new tenants —
# enable it (plus the 12.x ML-asset surface flag and the 8.x SSO flag;
# the 0b.10 gate raises DATABRICKS_SSO_DISABLED without it).
tenant.databricks_control_plane_enabled = True
tenant.databricks_ml_assets_enabled = True
tenant.databricks_sso_enabled = True
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
    name='DBX Parity Test Key {unique}',
    key_hash=AuthAPIKey.hash_key(key)
)
print(f"TENANT_ID:{{tenant.id}}")
print(key)
"""
    output = _docker_exec(script).strip().splitlines()
    tenant_id = next(line for line in output if line.startswith("TENANT_ID:")).split(":", 1)[1]
    key = output[-1].strip()
    return {
        "api_key": key,
        "tenant_id": tenant_id,
        "tenant_slug": tenant_slug,
        "email": email,
    }


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
    """Raw HTTP client using the same key — for seeding workspace rows."""
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
class TestDatabricksParityRealAPI:
    """The parity command families against the real API (reads + the
    DRAFT lifecycle + the classified-error surface)."""

    @pytest.fixture(autouse=True)
    def _dns_guard(self):
        _require_dns()

    def test_tenant_level_reads(self, configured_cli, databricks_env):
        """budgets/sso/inbox return real (empty-tenant) payloads through
        the CLI (sso is AllowAny — the tenant id rides the query string)."""
        for argv in (
            ["databricks", "budgets", "list"],
            ["databricks", "sso", "workspaces", "--tenant", databricks_env["tenant_id"]],
            ["databricks", "uc", "changes", "inbox"],
        ):
            result = configured_cli.invoke(cli, argv)
            assert result.exit_code == 0, (argv, result.output)

    def test_account_plane_is_platform_admin_only(self, configured_cli):
        """The account plane (accounts + estate-summary) is
        PLATFORM_ADMIN-only by design (the 8.x RBAC contract) — the CLI
        relays the backend's classified 403 for a tenant admin."""
        for argv in (
            ["databricks", "accounts", "list"],
            ["databricks", "accounts", "estate"],
        ):
            result = configured_cli.invoke(cli, argv)
            assert result.exit_code != 0, (argv, result.output)
            assert "PERMISSION_DENIED" in result.output, (argv, result.output)

    def test_workspace_scoped_reads(self, configured_cli, http_client):
        """The mirror-first reads return real payloads for a seeded
        workspace (empty mirrors are legitimate results)."""
        workspace = _seed_workspace(http_client, f"CLI Parity {uuid.uuid4().hex[:8]}")
        for argv in (
            ["databricks", "jobs", "list", "--workspace", workspace],
            ["databricks", "uc", "changes", "list", "--workspace", workspace],
            ["databricks", "uc", "external-locations", "--workspace", workspace],
            ["databricks", "uc", "storage-credentials", "--workspace", workspace],
            ["databricks", "ml", "models", "--workspace", workspace],
            ["databricks", "ml", "feature-tables", "--workspace", workspace],
            ["databricks", "ml", "serving-endpoints", "ls", "--workspace", workspace],
            ["databricks", "ml", "vector-endpoints", "ls", "--workspace", workspace],
            ["databricks", "workspaces", "credentials", "ls", workspace],
        ):
            result = configured_cli.invoke(cli, argv)
            assert result.exit_code == 0, (argv, result.output)

    def test_uc_change_draft_lifecycle(self, configured_cli, http_client, tmp_path):
        """create → show → comment → timeline against the real 2.4
        guards (a DRAFT never reaches the Databricks network)."""
        workspace = _seed_workspace(http_client, f"CLI Parity Draft {uuid.uuid4().hex[:8]}")
        payload = {
            "change_type": "CREATE",
            "securable_type": "TABLE",
            "definition": {
                "identifiers": ["catalog_one", "schema_one", "table_one"],
                "options": {},
            },
        }
        payload_file = tmp_path / "change.json"
        payload_file.write_text(json.dumps(payload))

        result = configured_cli.invoke(
            cli,
            [
                "databricks",
                "uc",
                "changes",
                "create",
                "--workspace",
                workspace,
                "--file",
                str(payload_file),
            ],
        )
        assert result.exit_code == 0, result.output
        created = json.loads(result.output)
        change_id = created["id"]
        assert created["status"] == "DRAFT"

        result = configured_cli.invoke(
            cli,
            [
                "databricks",
                "uc",
                "changes",
                "show",
                "--workspace",
                workspace,
                "--change",
                change_id,
            ],
        )
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)["id"] == change_id

        result = configured_cli.invoke(
            cli,
            [
                "databricks",
                "uc",
                "changes",
                "comment",
                "--workspace",
                workspace,
                "--change",
                change_id,
                "--text",
                "CLI parity comment",
            ],
        )
        assert result.exit_code == 0, result.output

        result = configured_cli.invoke(
            cli,
            [
                "databricks",
                "uc",
                "changes",
                "timeline",
                "--workspace",
                workspace,
                "--change",
                change_id,
            ],
        )
        assert result.exit_code == 0, result.output

        result = configured_cli.invoke(
            cli,
            ["databricks", "uc", "changes", "list", "--workspace", workspace, "--format", "json"],
        )
        assert result.exit_code == 0, result.output
        assert change_id in result.output

    def test_unknown_resources_surface_classified_errors(self, configured_cli, http_client):
        """The CLI relays the backend's classified envelopes — a
        non-zero exit with the machine-readable code, never a traceback."""
        workspace = _seed_workspace(http_client, f"CLI Parity Err {uuid.uuid4().hex[:8]}")
        unknown = str(uuid.uuid4())

        result = configured_cli.invoke(
            cli, ["databricks", "uc", "table", "--workspace", workspace, "--table", unknown]
        )
        assert result.exit_code != 0, result.output
        assert "NOT_FOUND" in result.output or "not found" in result.output.lower()

        result = configured_cli.invoke(
            cli, ["databricks", "jobs", "runs", "--workspace", workspace, "--job", unknown]
        )
        assert result.exit_code != 0, result.output

        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            junk_file = Path(tmpdir) / "account.json"
            junk_file.write_text(json.dumps({"account_id": "not-a-real-account"}))
            result = configured_cli.invoke(
                cli, ["databricks", "accounts", "create", "--file", str(junk_file)]
            )
        assert result.exit_code != 0, result.output
