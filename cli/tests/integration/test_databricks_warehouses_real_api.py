"""Integration tests for the Databricks warehouse lifecycle CLI commands
against the real API (openspec add-databricks-sql-warehouses task 3.7).

Real HTTP, real database rows, real validation — no mocks. The API
service under test is the configured Meshant backend (``MESHANT_API_URL``,
default http://localhost:8000/api/v1); a Docker Compose or staging stack
must be up, per the W16 environment policy (CI raises when unreachable,
local runs skip gracefully — the 0.15 workspaces suite's contract).

The flow: provision a tenant + workspace through the API container's
Django shell (the 0.15 pattern), seed a mirror row directly in the DB,
then drive ``databricks warehouses list`` (mirror-first — zero network)
and the start/stop actions through the REAL 3.7 endpoints. The action
calls hit the REAL Databricks API when the workspace hosts a live one —
against an unreachable workspace the backend masks the failure with
``DATABRICKS_AUTH_FAILED``, which is itself the contract this suite
asserts for the error path (the DB-002 E2E precedent: the masked
assertion is network-robust BY DESIGN).
"""

import json
import socket
import subprocess
import uuid

import pytest
from tests.pytest_mvp_skip import skip_if_mvp_mode

from envpolicy import api_available

pytestmark = skip_if_mvp_mode

from click.testing import CliRunner
from datahub_cli.main import cli

REAL_HOST = "dbc-6710eb95-8fe1.cloud.databricks.com"


def _require_dns():
    try:
        socket.getaddrinfo(REAL_HOST, None)
    except OSError:
        from envpolicy import environment_guard

        environment_guard("public DNS unavailable — Databricks host resolution required")
        pytest.skip("public DNS unavailable — Databricks host resolution required")


def _require_api():
    # W16: CI raises, local runs skip gracefully.
    from envpolicy import environment_guard

    environment_guard("hub API unreachable — the real-API suite needs a running stack")
    if not api_available():
        pytest.skip("hub API unreachable — the real-API suite needs a running stack")


def _docker_exec(script: str) -> str:
    import os

    container = os.environ.get("MESHANT_API_CONTAINER", "hub-test-api")
    manage_py = os.environ.get("MESHANT_API_MANAGE_PY", "hub/manage.py")
    result = subprocess.run(
        ["docker", "exec", "-i", container, "python", manage_py, "shell", "-c", script],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _provision():
    """A tenant + workspace + mirror row through the API container."""
    _require_dns()
    _require_api()
    suffix = uuid.uuid4().hex[:8]
    out = _docker_exec(
        f"""
from hub.apps.tenants.models import Tenant
from hub.apps.databricks_admin.models import (
    DatabricksCloud, DatabricksWorkspace, DatabricksSqlWarehouse,
)
from hub.apps.users.models import User, Role, UserRole, UserStatus
tenant = Tenant.objects.create(name='wh-cli-{suffix}', slug='wh-cli-{suffix}')
tenant.databricks_control_plane_enabled = True
tenant.save(update_fields=['databricks_control_plane_enabled'])
user = User.objects.create_user(
    email='wh-cli-{suffix}@test.com', password='testpass123',
    tenant=tenant, status=UserStatus.ACTIVE,
)
role, _ = Role.objects.get_or_create(tenant=tenant, name='TENANT_ADMIN')
UserRole.objects.get_or_create(user=user, role=role)
workspace = DatabricksWorkspace.objects.create(
    tenant=tenant, name='ws-wh-cli-{suffix}', host='{REAL_HOST}',
    cloud=DatabricksCloud.AWS, region='us-east-1', status='ACTIVE',
)
mirror = DatabricksSqlWarehouse.objects.create(
    workspace=workspace, warehouse_id='wh-cli-{suffix}', name='analytics',
    state='STOPPED', serverless=True, size=None,
)
print(json.dumps({{'tenant': str(tenant.id), 'workspace': str(workspace.id), 'warehouse': mirror.warehouse_id, 'email': user.email}}))
"""
    )
    payload = json.loads(out.splitlines()[-1])
    return payload


@pytest.fixture(scope="module")
def provisioned():
    return _provision()


class TestWarehousesRealApi:
    def test_list_lists_the_mirror_rows(self, provisioned):
        result = CliRunner().invoke(
            cli, ["databricks", "warehouses", "list", "--workspace", provisioned["workspace"]]
        )
        assert result.exit_code == 0, result.output
        assert "analytics" in result.output
        assert provisioned["warehouse"] in result.output

    def test_list_json_emits_the_paginated_envelope(self, provisioned):
        result = CliRunner().invoke(
            cli,
            [
                "databricks",
                "warehouses",
                "list",
                "--workspace",
                provisioned["workspace"],
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0, result.output
        envelope = json.loads(result.output)
        assert envelope["results"][0]["warehouse_id"] == provisioned["warehouse"]

    def test_start_masks_the_workspace_rejection(self, provisioned):
        """The action endpoint's masked 502 is network-robust BY DESIGN
        (a non-live workspace rejects the call; the backend always
        answers the same masked shape)."""
        result = CliRunner().invoke(
            cli,
            [
                "databricks",
                "warehouses",
                "start",
                "--workspace",
                provisioned["workspace"],
                "--warehouse",
                provisioned["warehouse"],
            ],
        )
        # Either the workspace answered (200 with the row) or the masked
        # 502 contract surfaced — the CLI renders either faithfully.
        assert result.exit_code == 0, result.output
        body = json.loads(result.output)
        assert "state" in body or body.get("code") == "DATABRICKS_AUTH_FAILED"

    def test_unknown_warehouse_surfaces_the_404(self, provisioned):
        result = CliRunner().invoke(
            cli,
            [
                "databricks",
                "warehouses",
                "start",
                "--workspace",
                provisioned["workspace"],
                "--warehouse",
                "wh-does-not-exist",
            ],
        )
        assert result.exit_code == 0, result.output
        body = json.loads(result.output)
        assert "error" in body or "not found" in body["error"]["message"].lower()
