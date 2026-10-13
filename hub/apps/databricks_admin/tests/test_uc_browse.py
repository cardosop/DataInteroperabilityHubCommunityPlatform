"""Phase 1 (openspec add-databricks-uc-read task 1.3) — UC browse endpoints.

No mocks: real Postgres mirror rows, real RBAC, real flag gating, and the
table-detail effective-permissions call drives the PRODUCTION client
against a REAL local HTTP server through the view's client factory (the
repo's `_build_probe_client`-style seam) with a REAL binding + REAL OBO
provider (access token seeded in the REAL Redis cache — get_bearer never
touches the network).

Contracts pinned:
- mirror listings (catalogs/schemas/tables/views/volumes/external
  locations/storage credentials/models) are tenant-scoped + paginated;
- table detail carries columns AND the LIVE effective-permissions answer;
- browse is fail-closed WITHOUT an OBO binding (no service fallback);
- the workspace-registry flag gate + kill switch apply;
- throttle scope enforced.
"""

import json
import uuid

import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.databricks_admin.models import (
    DatabricksCloud,
    DatabricksWorkspace,
    UCCatalog,
    UCSchema,
    UCTable,
)
from hub.apps.databricks_admin.tests._fixtures import REAL_HOST, require_dns
from hub.apps.databricks_admin.tests._http import RecordingHandler
from hub.apps.databricks_admin.tests.test_views import (
    _activate_billing,
    _make_user,
)
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


def _seed_estate(tenant, name="ws-1"):
    workspace = DatabricksWorkspace.objects.create(
        tenant=tenant,
        name=name,
        host=REAL_HOST,
        cloud=DatabricksCloud.AWS,
        region="us-east-1",
        status="ACTIVE",
    )
    catalog = UCCatalog.objects.create(workspace=workspace, name="main", comment="primary catalog")
    schema = UCSchema.objects.create(catalog=catalog, name="sales", comment="sales schema")
    table = UCTable.objects.create(
        schema=schema,
        name="orders",
        table_type="MANAGED",
        columns=[{"name": "id"}, {"name": "total"}],
        full_name="main.sales.orders",
        comment="Order fact table",
    )
    return workspace, catalog, schema, table


def _setup_tenant(flag=True):
    require_dns()
    tenant = TenantFactory.create_tenant()
    _activate_billing(tenant)
    tenant.databricks_control_plane_enabled = flag
    tenant.save(update_fields=["databricks_control_plane_enabled"])
    admin = _make_user(tenant, f"uc-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN")
    return tenant, admin


def _api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _uc_url(workspace_id, tail=""):
    return f"/api/v1/databricks/workspaces/{workspace_id}/uc/{tail}"


class UCBrowseListTests(TestCase):
    def setUp(self):
        self.tenant, self.admin = _setup_tenant()
        self.workspace, self.catalog, self.schema, self.table = _seed_estate(self.tenant)

    def test_catalog_list_is_paginated_and_tenant_scoped(self):
        other_tenant = TenantFactory.create_tenant()
        _activate_billing(other_tenant)
        _seed_estate(other_tenant, name="ws-other")

        response = _api_client(self.admin).get(_uc_url(self.workspace.id, "catalogs/"))
        assert response.status_code == 200, response.content
        body = response.json()
        assert "results" in body, "browse listings must be paginated"
        names = [c["name"] for c in body["results"]]
        assert names == ["main"], "only THIS workspace's catalogs are visible"

    def test_schema_and_table_lists(self):
        client = _api_client(self.admin)
        schemas = client.get(_uc_url(self.workspace.id, f"catalogs/{self.catalog.id}/schemas/"))
        assert schemas.status_code == 200
        assert [s["name"] for s in schemas.json()["results"]] == ["sales"]

        tables = client.get(_uc_url(self.workspace.id, f"schemas/{self.schema.id}/tables/"))
        assert tables.status_code == 200
        rows = tables.json()["results"]
        assert [t["name"] for t in rows] == ["orders"]
        assert rows[0]["columns"] == [{"name": "id"}, {"name": "total"}]

    def test_remaining_mirror_surfaces_list(self):
        client = _api_client(self.admin)
        # Workspace-level mirrors: external locations + storage credentials.
        for tail in ("external-locations/", "storage-credentials/"):
            assert client.get(_uc_url(self.workspace.id, tail)).status_code == 200, tail
        assert (
            client.get(_uc_url(self.workspace.id, f"schemas/{self.schema.id}/views/")).status_code
            == 200
        )
        assert (
            client.get(_uc_url(self.workspace.id, f"schemas/{self.schema.id}/volumes/")).status_code
            == 200
        )
        assert (
            client.get(_uc_url(self.workspace.id, f"schemas/{self.schema.id}/models/")).status_code
            == 200
        )

    def test_cross_tenant_workspace_path_is_404(self):
        other_tenant = TenantFactory.create_tenant()
        _activate_billing(other_tenant)
        other_admin = _make_user(
            other_tenant, f"uc-other-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN"
        )
        response = _api_client(other_admin).get(_uc_url(self.workspace.id, "catalogs/"))
        assert response.status_code == 404

    def test_flag_off_returns_403(self):
        tenant, admin = _setup_tenant(flag=False)
        workspace, _c, _s, _t = _seed_estate(tenant)
        response = _api_client(admin).get(_uc_url(workspace.id, "catalogs/"))
        assert response.status_code == 403

    def test_unauthenticated_returns_401(self):
        response = APIClient().get(_uc_url(self.workspace.id, "catalogs/"))
        assert response.status_code == 401

    def test_throttle_scope_enforced_after_burst(self):
        throttled = _make_user(
            self.tenant, f"uc-throttle-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN"
        )
        client = _api_client(throttled)
        for _ in range(30):
            assert client.get(_uc_url(self.workspace.id, "catalogs/")).status_code == 200
        assert client.get(_uc_url(self.workspace.id, "catalogs/")).status_code == 429


class TestUCTableDetailPermissions:
    """Fixture-driven (monkeypatch seams) — the live permissions path.

    NOTE: the class was previously named ``UCTableDetailPermissionsTests``
    — pytest's ``python_classes = Test*`` convention silently SKIPPED it,
    so the live-permissions + fail-closed pins never ran (the 1.3 review
    caught this; renamed so the pins actually execute)."""

    def _setup(self, with_binding=True, with_cache=True):
        require_dns()
        tenant, admin = _setup_tenant()
        # The OBO provider needs the workspace's SSO config (client_id) —
        # without it _build_uc_obo_provider fails closed even WITH a
        # binding (1.3 review fix: the first version of this test never
        # ran and the missing config masked the live path).
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
        workspace, _catalog, _schema, table = _seed_estate(tenant)

        binding = None
        if with_binding:
            from hub.apps.databricks_admin.models import DatabricksUserBinding

            binding = DatabricksUserBinding.objects.create(
                tenant=tenant,
                user=admin,
                workspace=workspace,
                databricks_sub=f"sub-{uuid.uuid4().hex[:8]}",
                databricks_email=admin.email,
            )
            if with_cache:
                from hub.apps.databricks_admin.obo_tokens import OBOAccessTokenCache

                OBOAccessTokenCache().set(binding.id, "dapi-uc-access", 300)
        return tenant, admin, workspace, table, binding

    def _patch_client_factory(self, monkeypatch, port, binding):
        from hub.apps.databricks_admin import uc_views
        from hub.apps.databricks_admin.client import DatabricksApiClient
        from hub.apps.databricks_admin.obo_tokens import OBOTokenProvider

        def fake_factory(workspace, _identity):
            provider = OBOTokenProvider(
                binding=binding,
                oidc_client_id="client-abc",
                oidc_base_url=f"http://127.0.0.1:{port}",
            )
            return DatabricksApiClient(
                base_url=f"http://127.0.0.1:{port}",
                tenant_id=str(workspace.tenant_id),
                obo_provider=provider,
                timeout_ms=5000,
                max_retries=1,
                retry_base_delay=0.05,
                retry_max_delay=0.1,
            )

        monkeypatch.setattr(uc_views, "_build_uc_client", fake_factory)

    def test_table_detail_returns_columns_and_live_permissions(
        self, monkeypatch, local_http_server, redis_13
    ):
        _tenant, admin, workspace, table, binding = self._setup()
        # Seed the cache on the fixture's Redis so get_bearer is a pure hit.
        from hub.apps.databricks_admin.obo_tokens import OBOAccessTokenCache

        OBOAccessTokenCache(redis_client=redis_13).set(binding.id, "dapi-uc-access", 300)
        self._patch_client_factory(monkeypatch, local_http_server, binding)

        RecordingHandler.json_script = [
            json.dumps(
                {
                    "privilege_assignments": [
                        {
                            "principal": "user-a",
                            "privileges": ["SELECT", "MODIFY"],
                        }
                    ]
                }
            )
        ]

        response = _api_client(admin).get(_uc_url(workspace.id, f"tables/{table.id}/"))
        assert response.status_code == 200, response.content
        body = response.json()
        assert body["name"] == "orders"
        assert body["columns"] == [{"name": "id"}, {"name": "total"}]
        assert body["effective_permissions"]["privilege_assignments"][0]["principal"] == "user-a"

        perms_calls = [
            r
            for r in RecordingHandler.requests
            if r["path"]
            == "/api/2.1/unity-catalog/effective-permissions/table/main.sales.orders?max_results=0"
        ]
        assert len(perms_calls) == 1, "the live permissions call must target the UC REST endpoint"
        assert perms_calls[0]["headers"].get("Authorization") == "Bearer dapi-uc-access", (
            "the permissions call must ride the user's OBO bearer"
        )

    def test_table_detail_without_binding_fails_closed(self):
        _tenant, admin, workspace, table, _binding = self._setup(with_binding=False)

        response = _api_client(admin).get(_uc_url(workspace.id, f"tables/{table.id}/"))
        assert response.status_code == 502
        assert response.json()["code"] == "DATABRICKS_OBO_REFRESH_FAILED"
        assert RecordingHandler.requests == [], (
            "fail-closed means ZERO network calls, never a service fallback"
        )

    def test_empty_permissions_passthrough_reflects_none(
        self, monkeypatch, local_http_server, redis_13
    ):
        # UC Browse API spec scenario "Browse respects the user's UC
        # grants": a user with NO grants sees the UC answer verbatim
        # (empty privilege_assignments = NONE) — the view must not
        # fabricate permissions.
        _tenant, admin, workspace, table, binding = self._setup()
        from hub.apps.databricks_admin.obo_tokens import OBOAccessTokenCache

        OBOAccessTokenCache(redis_client=redis_13).set(binding.id, "dapi-uc-access", 300)
        self._patch_client_factory(monkeypatch, local_http_server, binding)

        RecordingHandler.json_script = [json.dumps({"privilege_assignments": []})]

        response = _api_client(admin).get(_uc_url(workspace.id, f"tables/{table.id}/"))
        assert response.status_code == 200, response.content
        body = response.json()
        assert body["effective_permissions"] == {"privilege_assignments": []}, (
            "an empty UC answer must pass through verbatim (NONE permissions)"
        )

    def test_gcp_fallback_client_carries_the_workspace_credential(self):
        # 0b.8 GCP fallback: INTERACTIVE catalog browse on GCP resolves
        # the workspace's OWN credential (obo_provider=None). The browse
        # client must carry that credential — the 1.3 first version
        # DISCARDED the D12 result and built an auth-less client.
        #
        # Unit pin: the workspace is an UNSAVED instance (save() runs the
        # 0.4 SSRF/DNS validation — a fabricated GCP host would fail it)
        # and the credential is the boundary duck-type the branch reads
        # (get_config() + auth_mode — the real-credential GCP path is
        # pinned by the 0b.8 identity tests).
        from types import SimpleNamespace

        from hub.apps.databricks_admin.identity import ResolvedIdentity
        from hub.apps.databricks_admin.models import DatabricksCloud
        from hub.apps.databricks_admin.uc_views import _build_uc_client

        tenant, _admin = _setup_tenant()
        workspace = DatabricksWorkspace(
            tenant=tenant,
            name=f"gcp-{uuid.uuid4().hex[:8]}",
            host="dbc-111.gcp.databricks.com",
            cloud=DatabricksCloud.GCP,
            region="us-central1",
            status="ACTIVE",
        )
        credential = SimpleNamespace(
            auth_mode="PAT",
            get_config=lambda: {"token": "dapi-gcp-fallback"},
        )
        identity = ResolvedIdentity(
            kind="m2m",
            purpose="catalog_browse",
            workspace_id=str(workspace.id),
            credential=credential,
            approval_linkage={"gcp_fallback": True},
        )

        client = _build_uc_client(workspace, identity)
        assert client._obo_provider is None
        assert client._auth_mode == "PAT"
        assert client._credential_config.get("token") == "dapi-gcp-fallback", (
            "the GCP fallback credential must reach the client"
        )
