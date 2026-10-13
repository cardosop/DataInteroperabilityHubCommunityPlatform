"""
Integration tests for `databricks uc ls` against the real API (openspec
add-databricks-control-plane task 1.9).

Real HTTP, real database rows, real RLS — no mocks. The API service
under test is the configured Meshant backend (``MESHANT_API_URL``,
default http://localhost:8000/api/v1); a Docker Compose or staging stack
must be up, per the W16 environment policy (CI raises when unreachable,
local runs skip gracefully).

Requires public DNS — the workspace host must be a genuine
``*.cloud.databricks.com`` hostname to pass the backend SSRF guard's
save-time DNS checks (the same REAL_HOST contract as the workspace
real-API suite).
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

from click.testing import CliRunner
from datahub_cli.config import config
from datahub_cli.main import cli

REAL_HOST = "dbc-6710eb95-8fe1.cloud.databricks.com"


def _require_dns():
    """W16: raise in CI / skip locally when public DNS is unavailable."""
    try:
        socket.getaddrinfo(REAL_HOST, None)
    except OSError:
        from envpolicy import environment_guard

        environment_guard("public DNS unavailable — Databricks host resolution required")
        pytest.skip("public DNS unavailable — Databricks host resolution required")


def _docker_exec(script: str) -> str:
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
def uc_env():
    """Provision a real tenant + admin + API key + a workspace with a
    seeded UC mirror (catalog → schema → table) via Django shell in the
    API container. Returns (api_key, workspace_id, catalog_id, schema_id,
    table_id, second_key)."""
    _require_dns()
    unique = uuid.uuid4().hex[:10]
    tenant_slug = f"dbx-uc-cli-{unique}"
    email = f"dbx-uc-cli-{unique}@example.com"
    other_email = f"dbx-uc-cli-other-{unique}@example.com"
    script = f"""
import uuid as _uuid
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus, Role, UserRole
from hub.apps.auth.models import APIKey as AuthAPIKey
from hub.apps.databricks_admin.models import (
    DatabricksWorkspace, DatabricksWorkspaceStatus, DatabricksCloud,
    UCCatalog, UCSchema, UCTable,
)

tenant, _ = Tenant.objects.get_or_create(
    slug='{tenant_slug}',
    defaults={{'name': 'DBX UC CLI {unique}'}}
)
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

key, _ = AuthAPIKey.objects.get_or_create(
    user=user,
    name='dbx-uc-cli-{unique}',
)
if not key.is_active:
    key.is_active = True
    key.save()

workspace = DatabricksWorkspace.objects.create(
    tenant=tenant,
    name='ws-uc-{unique}',
    host='{REAL_HOST}',
    cloud=DatabricksCloud.AWS,
    region='us-east-1',
    status=DatabricksWorkspaceStatus.ACTIVE,
)
catalog = UCCatalog.objects.create(
    workspace=workspace, name='main', comment='cli seed catalog'
)
schema = UCSchema.objects.create(
    catalog=catalog, name='sales', comment='cli seed schema'
)
table = UCTable.objects.create(
    schema=schema,
    name='orders',
    table_type='MANAGED',
    columns=[{{'name': 'id'}}],
    full_name='main.sales.orders',
)

# A SECOND tenant (no workspace) — its admin must NOT see tenant A's
# mirror (RLS + the 1.3 cross-tenant 404 contract).
other_tenant, _ = Tenant.objects.get_or_create(
    slug='dbx-uc-cli-other-{unique}',
    defaults={{'name': 'DBX UC CLI Other {unique}'}}
)
other_user, _ = User.objects.get_or_create(
    email='{other_email}',
    defaults={{'tenant': other_tenant, 'status': UserStatus.ACTIVE}}
)
other_role, _ = Role.objects.get_or_create(
    tenant=other_tenant,
    name='TENANT_ADMIN',
    defaults={{'description': 'Tenant Administrator'}}
)
UserRole.objects.get_or_create(user=other_user, role=other_role)
other_key, _ = AuthAPIKey.objects.get_or_create(
    user=other_user,
    name='dbx-uc-cli-other-{unique}',
)

print(f"OK {{key.id}} {{workspace.id}} {{catalog.id}} {{schema.id}} {{table.id}} {{other_key.id}}")
"""
    out = _docker_exec(script).strip().splitlines()[-1]
    parts = out.split()
    assert parts[0] == "OK", out
    (
        _,
        api_key_id,
        workspace_id,
        catalog_id,
        schema_id,
        table_id,
        other_key_id,
    ) = parts

    # The API-key secret is generated server-side; fetch it from the DB.
    fetch = _docker_exec(
        f"""
from hub.apps.auth.models import APIKey
k = APIKey.objects.get(id='{api_key_id}')
o = APIKey.objects.get(id='{other_key_id}')
print(k.key + ' ' + o.key)
"""
    ).strip()
    key_secret, other_secret = fetch.split()

    return {
        "api_key": key_secret,
        "other_api_key": other_secret,
        "workspace_id": workspace_id,
        "catalog_id": catalog_id,
        "schema_id": schema_id,
        "table_id": table_id,
        "slug": tenant_slug,
    }


def _run(env, *args):
    """Invoke the CLI as the provisioned tenant admin (the 0.15
    convention — config.set_api_key, no --api-key option)."""
    config.set_api_key(env["api_key"])
    try:
        return CliRunner().invoke(cli, list(args))
    finally:
        config.set_api_key(None)


class TestUcLsRealApi:
    """The `uc ls` wire contract against the real backend."""

    def test_uc_ls_lists_catalogs_table_format(self, api_available_flag, uc_env):
        if not api_available_flag:
            pytest.skip("API unavailable — W16 environment policy")
        result = _run(uc_env, "databricks", "uc", "ls", "--workspace", uc_env["workspace_id"])
        assert result.exit_code == 0, result.output
        assert "main" in result.output

    def test_uc_ls_catalog_lists_schemas_json(self, api_available_flag, uc_env):
        if not api_available_flag:
            pytest.skip("API unavailable — W16 environment policy")
        result = _run(
            uc_env,
            "databricks",
            "uc",
            "ls",
            "--workspace",
            uc_env["workspace_id"],
            "--catalog",
            uc_env["catalog_id"],
            "--format",
            "json",
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        names = [row["name"] for row in payload.get("results", [])]
        assert names == ["sales"]

    def test_uc_ls_schema_lists_tables(self, api_available_flag, uc_env):
        if not api_available_flag:
            pytest.skip("API unavailable — W16 environment policy")
        result = _run(
            uc_env,
            "databricks",
            "uc",
            "ls",
            "--workspace",
            uc_env["workspace_id"],
            "--schema",
            uc_env["schema_id"],
        )
        assert result.exit_code == 0, result.output
        assert "main.sales.orders" in result.output

    def test_uc_ls_schema_unknown_kind_rejected_locally(self, api_available_flag, uc_env):
        if not api_available_flag:
            pytest.skip("API unavailable — W16 environment policy")
        result = _run(
            uc_env,
            "databricks",
            "uc",
            "ls",
            "--workspace",
            uc_env["workspace_id"],
            "--schema",
            uc_env["schema_id"],
            "--kind",
            "bogus",
        )
        assert result.exit_code == 2

    def test_uc_ls_foreign_workspace_is_404(self, api_available_flag, uc_env):
        """The RLS/tenant-scoping contract: tenant B's admin cannot read
        tenant A's workspace mirror (1.3 cross-tenant 404)."""
        if not api_available_flag:
            pytest.skip("API unavailable — W16 environment policy")
        config.set_api_key(uc_env["other_api_key"])
        try:
            result = CliRunner().invoke(
                cli,
                ["databricks", "uc", "ls", "--workspace", uc_env["workspace_id"]],
            )
        finally:
            config.set_api_key(None)
        assert result.exit_code != 0
        assert "404" in result.output or "Not Found" in result.output
