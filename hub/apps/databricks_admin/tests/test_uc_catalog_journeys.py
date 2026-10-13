"""Journey pins for the P1 UC browse surfaces (openspec
add-databricks-uc-read task 1.11) — JOURNEY-DB-005 (Browse the Unity
Catalog) and JOURNEY-DB-006 (Inspect Table Permissions).

Class/method names are PINNED by the UC docs' "Phase P1 Test" fields
(docs/mvpdocs/use-cases/UC-DB-005.md / UC-DB-006.md) — renaming them
breaks the docs↔test drift gates (GATE-28).

No mocks: real Postgres mirror rows, real RBAC, real flag gating, and
the table-detail effective-permissions call drives the PRODUCTION
client against a REAL local HTTP server through the 1.3 `_build_uc_client`
factory seam with a REAL OBO binding + REAL Redis-cached bearer.
"""

import json
import uuid

import pytest
from rest_framework.test import APIClient

from hub.apps.databricks_admin.models import (
    DatabricksCloud,
    DatabricksUserBinding,
    DatabricksWorkspace,
    UCCatalog,
    UCSchema,
    UCTable,
)
from hub.apps.databricks_admin.tests._fixtures import REAL_HOST, require_dns
from hub.apps.databricks_admin.tests._http import RecordingHandler
from hub.apps.databricks_admin.tests.test_views import _activate_billing, _make_user
from tests.factories import TenantFactory

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.uc("UC-DB-005"),
    pytest.mark.uc("UC-DB-006"),
    pytest.mark.journey("JOURNEY-DB-005"),
    pytest.mark.journey("JOURNEY-DB-006"),
]


def _seed_tenant():
    require_dns()
    tenant = TenantFactory.create_tenant()
    _activate_billing(tenant)
    tenant.databricks_control_plane_enabled = True
    tenant.save(update_fields=["databricks_control_plane_enabled"])
    admin = _make_user(tenant, f"uc-journey-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN")
    workspace = DatabricksWorkspace.objects.create(
        tenant=tenant,
        name="ws-journey",
        host=REAL_HOST,
        cloud=DatabricksCloud.AWS,
        region="us-east-1",
        status="ACTIVE",
    )
    catalog = UCCatalog.objects.create(workspace=workspace, name="main", comment="journey catalog")
    schema = UCSchema.objects.create(catalog=catalog, name="sales")
    table = UCTable.objects.create(
        schema=schema,
        name="orders",
        table_type="MANAGED",
        columns=[{"name": "id", "type_text": "BIGINT"}],
        full_name="main.sales.orders",
    )
    return tenant, admin, workspace, catalog, schema, table


class TestJOURNEYDB005BrowseUCCatalog:
    """JOURNEY-DB-005 — the mirrored browse chain over real rows."""

    def test_browse_endpoints_paginated(self):
        _tenant, admin, workspace, catalog, schema, _table = _seed_tenant()
        client = APIClient()
        client.force_authenticate(user=admin)

        catalogs = client.get(f"/api/v1/databricks/workspaces/{workspace.id}/uc/catalogs/")
        assert catalogs.status_code == 200, catalogs.content
        body = catalogs.json()
        assert "results" in body, "browse listings must be paginated"
        names = [c["name"] for c in body["results"] if c["id"] == str(catalog.id)]
        assert names == ["main"], "only THIS workspace's catalogs are visible"

        schemas = client.get(
            f"/api/v1/databricks/workspaces/{workspace.id}/uc/catalogs/{catalog.id}/schemas/"
        )
        assert schemas.status_code == 200
        assert [s["name"] for s in schemas.json()["results"]] == ["sales"]

        tables = client.get(
            f"/api/v1/databricks/workspaces/{workspace.id}/uc/schemas/{schema.id}/tables/"
        )
        assert tables.status_code == 200
        rows = tables.json()["results"]
        assert [t["name"] for t in rows] == ["orders"]
        assert rows[0]["columns"] == [{"name": "id", "type_text": "BIGINT"}]

    def test_cross_tenant_workspace_is_not_visible(self):
        _tenant, _admin, workspace, _c, _s, _t = _seed_tenant()
        other = TenantFactory.create_tenant()
        _activate_billing(other)
        other_admin = _make_user(other, f"uc-other-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN")
        client = APIClient()
        client.force_authenticate(user=other_admin)
        response = client.get(f"/api/v1/databricks/workspaces/{workspace.id}/uc/catalogs/")
        assert response.status_code == 404


class TestJOURNEYDB006InspectTablePermissions:
    """JOURNEY-DB-006 — the live effective-permissions mapping."""

    def _setup_with_binding(self, monkeypatch, local_http_server, redis_13):
        tenant, admin, workspace, _catalog, _schema, table = _seed_tenant()
        from hub.apps.tenants.models import TenantConfig

        config = TenantConfig.objects.get_or_create(tenant=tenant)[0]
        sso = config.get_sso_config()
        sso["databricks"] = {
            "host": REAL_HOST,
            "client_id": "client-abc",
            "redirect_uri": "https://hub.example.com/auth/databricks/callback",
        }
        config.sso_config = sso
        config.save()

        binding = DatabricksUserBinding.objects.create(
            tenant=tenant,
            user=admin,
            workspace=workspace,
            databricks_sub=f"sub-{uuid.uuid4().hex[:8]}",
            databricks_email=admin.email,
        )
        from hub.apps.databricks_admin.obo_tokens import OBOAccessTokenCache

        OBOAccessTokenCache(redis_client=redis_13).set(binding.id, "dapi-journey", 300)

        from hub.apps.databricks_admin import uc_views
        from hub.apps.databricks_admin.client import DatabricksApiClient
        from hub.apps.databricks_admin.obo_tokens import OBOTokenProvider

        def fake_factory(_workspace, _identity):
            provider = OBOTokenProvider(
                binding=binding,
                oidc_client_id="client-abc",
                oidc_base_url=f"http://127.0.0.1:{local_http_server}",
            )
            return DatabricksApiClient(
                base_url=f"http://127.0.0.1:{local_http_server}",
                tenant_id=str(workspace.tenant_id),
                obo_provider=provider,
                timeout_ms=5000,
                max_retries=1,
                retry_base_delay=0.05,
                retry_max_delay=0.1,
            )

        monkeypatch.setattr(uc_views, "_build_uc_client", fake_factory)
        return admin, workspace, table, binding

    def test_effective_permissions_mapping(self, monkeypatch, local_http_server, redis_13):
        admin, workspace, table, _binding = self._setup_with_binding(
            monkeypatch, local_http_server, redis_13
        )
        RecordingHandler.json_script = [
            json.dumps(
                {
                    "privilege_assignments": [
                        {"principal": "user-a", "privileges": ["SELECT", "MODIFY"]}
                    ]
                }
            )
        ]
        client = APIClient()
        client.force_authenticate(user=admin)
        response = client.get(f"/api/v1/databricks/workspaces/{workspace.id}/uc/tables/{table.id}/")
        assert response.status_code == 200, response.content
        body = response.json()
        assert body["columns"] == [{"name": "id", "type_text": "BIGINT"}]
        assignments = body["effective_permissions"]["privilege_assignments"]
        assert assignments[0]["principal"] == "user-a"

        perms_calls = [
            r
            for r in RecordingHandler.requests
            if r["path"]
            == "/api/2.1/unity-catalog/effective-permissions/table/main.sales.orders?max_results=0"
        ]
        assert len(perms_calls) == 1, "the live permissions call must target the UC REST endpoint"
        assert perms_calls[0]["headers"].get("Authorization") == "Bearer dapi-journey", (
            "the permissions call must ride the user's OBO bearer"
        )

    def test_without_binding_fails_closed(self):
        _tenant, admin, workspace, _c, _s, table = _seed_tenant()
        client = APIClient()
        client.force_authenticate(user=admin)
        response = client.get(f"/api/v1/databricks/workspaces/{workspace.id}/uc/tables/{table.id}/")
        assert response.status_code == 502
        assert response.json()["code"] == "DATABRICKS_OBO_REFRESH_FAILED"
        assert RecordingHandler.requests == [], (
            "fail-closed means ZERO network calls, never a service fallback"
        )
