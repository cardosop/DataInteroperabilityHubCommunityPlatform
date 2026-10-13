"""
Integration tests for the UC browse endpoints against the real API
(openspec add-databricks-control-plane task 1.12).

Real HTTP, real database rows, real RLS, real RBAC — no mocks. The API
service under test is the configured Meshant backend (``MESHANT_API_URL``,
default http://localhost:8000/api/v1); a Docker Compose or staging stack
must be up, per the W16 environment policy (CI raises when unreachable,
local runs skip gracefully).

The 1.12 acceptance — "catalog browse reflects a fixture workspace" —
is pinned over the wire: the suite provisions a tenant whose workspace
carries a seeded mirror (catalog → schema → table with columns) via the
API container's Django shell, then asserts the browse endpoints reflect
that seed, carry the pagination envelope, 404 for a foreign tenant
(RLS), 403 under the flag gate, and 401 unauthenticated.

Requires public DNS — the workspace host must be a genuine
``*.cloud.databricks.com`` hostname to pass the backend SSRF guard's
save-time DNS checks (the same REAL_HOST contract as the 1.9 suite).
"""

import os
import socket
import subprocess
import uuid

import pytest
import requests
from tests.pytest_mvp_skip import skip_if_mvp_mode

from envpolicy import api_available

pytestmark = skip_if_mvp_mode

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
def browse_env():
    """Provision a real tenant + admin API key + a workspace with a
    seeded UC mirror (catalog → schema → table with columns); a second
    tenant (flag ON, no workspace) for the 404 pin and a third (flag
    OFF) for the 403 pin. Returns ids + key secrets."""
    _require_dns()
    unique = uuid.uuid4().hex[:10]
    slug = f"dbx-browse-{unique}"
    other_slug = f"dbx-browse-other-{unique}"
    gated_slug = f"dbx-browse-gated-{unique}"
    email = f"dbx-browse-{unique}@example.com"
    other_email = f"dbx-browse-other-{unique}@example.com"
    gated_email = f"dbx-browse-gated-{unique}@example.com"
    script = f"""
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus, Role, UserRole
from hub.apps.auth.services import APIKeyService
from hub.apps.databricks_admin.models import (
    DatabricksWorkspace, DatabricksWorkspaceStatus, DatabricksCloud,
    UCCatalog, UCSchema, UCTable,
)


def make_tenant(slug_value, name_value, flag):
    tenant, _ = Tenant.objects.get_or_create(
        slug=slug_value,
        defaults={{'name': name_value}},
    )
    tenant.databricks_control_plane_enabled = flag
    tenant.save()
    return tenant


def make_admin(tenant, email_value):
    user, _ = User.objects.get_or_create(
        email=email_value,
        defaults={{'tenant': tenant, 'status': UserStatus.ACTIVE}},
    )
    if user.tenant != tenant:
        user.tenant = tenant
        user.save()
    user.status = UserStatus.ACTIVE
    user.save()
    role, _ = Role.objects.get_or_create(
        tenant=tenant,
        name='TENANT_ADMIN',
        defaults={{'description': 'Tenant Administrator'}},
    )
    UserRole.objects.get_or_create(user=user, role=role)
    # The CANONICAL creation path — APIKeyService generates the key
    # material + hash (a raw get_or_create leaves key_hash='' and the
    # second key collides on the unique constraint).
    _, key_secret = APIKeyService().create_api_key(
        tenant_id=str(tenant.id), user_id=str(user.id), name='dbx-browse-{unique}'
    )
    return key_secret


# The billing block is MODULE-LEVEL (it binds the ``tenant`` variable) —
# interpolating it inside make_admin would break the function block.
tenant = make_tenant('{slug}', 'DBX Browse {unique}', True)
{_ACTIVATE_BILLING}
key_secret = make_admin(tenant, '{email}')

workspace = DatabricksWorkspace.objects.create(
    tenant=tenant,
    name='ws-browse-{unique}',
    host='{REAL_HOST}',
    cloud=DatabricksCloud.AWS,
    region='us-east-1',
    status=DatabricksWorkspaceStatus.ACTIVE,
)
# NOTE: no ``comment=`` kwargs — the comment columns landed in migration
# 0012 and the shared API-container DB may predate them; the 1.12 wire
# contract (names + columns) does not depend on the newest migration.
catalog = UCCatalog.objects.create(workspace=workspace, name='main')
schema = UCSchema.objects.create(catalog=catalog, name='sales')
table = UCTable.objects.create(
    schema=schema,
    name='orders',
    table_type='MANAGED',
    columns=[{{'name': 'id'}}, {{'name': 'total'}}],
    full_name='main.sales.orders',
)

other_tenant = make_tenant('{other_slug}', 'DBX Browse Other {unique}', True)
tenant = other_tenant
{_ACTIVATE_BILLING}
other_secret = make_admin(other_tenant, '{other_email}')

gated_tenant = make_tenant('{gated_slug}', 'DBX Browse Gated {unique}', False)
tenant = gated_tenant
{_ACTIVATE_BILLING}
gated_secret = make_admin(gated_tenant, '{gated_email}')

print(
    f"OK {{key_secret}} {{other_secret}} {{gated_secret}} "
    f"{{workspace.id}} {{catalog.id}} {{schema.id}} {{table.id}}"
)
"""
    out = _docker_exec(script).strip().splitlines()[-1]
    parts = out.split()
    assert parts[0] == "OK", out
    (
        _,
        key_secret,
        other_secret,
        gated_secret,
        workspace_id,
        catalog_id,
        schema_id,
        table_id,
    ) = parts

    return {
        "api_base": os.environ.get("MESHANT_API_URL", "http://localhost:8000/api/v1"),
        "api_key": key_secret,
        "other_api_key": other_secret,
        "gated_api_key": gated_secret,
        "workspace_id": workspace_id,
        "catalog_id": catalog_id,
        "schema_id": schema_id,
        "table_id": table_id,
    }


def _get(env, path, key=None):
    session = requests.Session()
    if key is not None:
        session.headers.update({"Authorization": f"ApiKey {key}"})
    return session.get(f"{env['api_base']}{path}", timeout=30)


class TestUCBrowseRealApi:
    """The browse wire contract against the real backend."""

    def test_catalogs_reflect_the_seeded_mirror(self, api_available_flag, browse_env):
        if not api_available_flag:
            pytest.skip("API unavailable — W16 environment policy")
        response = _get(
            browse_env,
            f"/databricks/workspaces/{browse_env['workspace_id']}/uc/catalogs/",
            browse_env["api_key"],
        )
        assert response.status_code == 200, response.content
        body = response.json()
        names = [row["name"] for row in body["results"]]
        assert names == ["main"], "the browse answer must reflect the seeded mirror"

    def test_listing_carries_the_pagination_envelope(self, api_available_flag, browse_env):
        if not api_available_flag:
            pytest.skip("API unavailable — W16 environment policy")
        response = _get(
            browse_env,
            f"/databricks/workspaces/{browse_env['workspace_id']}/uc/schemas/{browse_env['schema_id']}/tables/",
            browse_env["api_key"],
        )
        assert response.status_code == 200, response.content
        body = response.json()
        for key in ("count", "page", "page_size", "total_pages", "has_next", "results"):
            assert key in body, f"pagination envelope key {key} missing"
        assert body["count"] == 1
        assert body["results"][0]["columns"] == [{"name": "id"}, {"name": "total"}], (
            "the seeded columns must reach the listing answer"
        )

    def test_foreign_tenant_gets_404(self, api_available_flag, browse_env):
        if not api_available_flag:
            pytest.skip("API unavailable — W16 environment policy")
        response = _get(
            browse_env,
            f"/databricks/workspaces/{browse_env['workspace_id']}/uc/catalogs/",
            browse_env["other_api_key"],
        )
        assert response.status_code == 404, (
            "a foreign tenant must never read another tenant's workspace mirror"
        )

    def test_table_detail_fails_closed_without_a_binding(self, api_available_flag, browse_env):
        if not api_available_flag:
            pytest.skip("API unavailable — W16 environment policy")
        # The provisioned admin has NO OBO binding — the LIVE permissions
        # leg must fail closed with the classified code (never a
        # service-credential fallback, never live-Databricks dependence).
        response = _get(
            browse_env,
            f"/databricks/workspaces/{browse_env['workspace_id']}/uc/tables/{browse_env['table_id']}/",
            browse_env["api_key"],
        )
        assert response.status_code == 502, response.content
        payload = response.json()
        assert payload["code"] == "DATABRICKS_OBO_REFRESH_FAILED"

    def test_flag_off_tenant_gets_403(self, api_available_flag, browse_env):
        if not api_available_flag:
            pytest.skip("API unavailable — W16 environment policy")
        response = _get(
            browse_env,
            f"/databricks/workspaces/{browse_env['workspace_id']}/uc/catalogs/",
            browse_env["gated_api_key"],
        )
        assert response.status_code == 403, response.content

    def test_unauthenticated_gets_401(self, api_available_flag, browse_env):
        if not api_available_flag:
            pytest.skip("API unavailable — W16 environment policy")
        response = _get(
            browse_env,
            f"/databricks/workspaces/{browse_env['workspace_id']}/uc/catalogs/",
        )
        assert response.status_code == 401
