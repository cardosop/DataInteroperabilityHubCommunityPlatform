"""Phase 1 (openspec add-databricks-uc-read task 1.12) — browse endpoint
units driven by fixture JSON (``tests/fixtures/databricks/``).

The 1.12 acceptance line — "catalog browse reflects a fixture workspace"
— is pinned end-to-end with REAL transports: the fixture estate file is
served by a REAL threaded HTTP server to the PRODUCTION
``DatabricksApiClient`` (the 1.5 ``_build_uc_client`` seam), the sync
writes REAL mirror rows, and the browse endpoints answer from those rows
— the API response is asserted field-for-field against the fixture file
(the fixture is the single source of truth; a drift between the fixture
and the endpoint answer fails the pin).

No mocks. The table-detail permissions pin serves
``effective_permissions.json`` through the real local server and asserts
the passthrough (the 1.3 live-permissions contract).
"""

import json
import uuid

import pytest
from django.test import TestCase

from hub.apps.databricks_admin.tests._fixtures import require_dns
from hub.apps.databricks_admin.tests._http import RecordingHandler, UCEstateHandler
from hub.apps.databricks_admin.tests._uc_fixtures import load_fixture
from hub.apps.databricks_admin.tests.test_uc_browse import _api_client, _setup_tenant, _uc_url
from hub.apps.databricks_admin.tests.test_uc_sync import (
    _local_client_factory,
    _make_approval,
    _make_credential,
    _make_workspace,
    _routes_for,
    _start_estate_server,
    _stop_estate_server,
)
from hub.apps.databricks_admin.tests.test_views import _activate_billing, _make_user
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


class UCBrowseFixtureDataTests(TestCase):
    """The fixture files exist, parse, and carry the documented shape."""

    def test_estate_fixture_covers_every_mirror_surface(self):
        estate = load_fixture("estate")
        for surface in (
            "catalogs",
            "schemas",
            "tables",
            "views",
            "volumes",
            "models",
            "external_locations",
            "storage_credentials",
        ):
            assert isinstance(estate[surface], list), f"{surface} must be a list"
        assert estate["tables"][0]["columns"], "tables must carry columns (detail contract)"

    def test_multi_page_fixture_carries_next_page_token_chains(self):
        routes = load_fixture("estate_multi_page")["routes"]
        tables_pages = routes["/api/2.1/unity-catalog/tables"]
        assert len(tables_pages) == 2, "the multi-page fixture must split tables across 2 pages"
        assert tables_pages[0]["next_page_token"], "page 1 must carry the continuation token"
        assert tables_pages[1]["next_page_token"] is None, "page 2 must terminate the chain"

    def test_effective_permissions_fixture_matches_the_uc_envelope(self):
        payload = load_fixture("effective_permissions")
        assert isinstance(payload["privilege_assignments"], list)
        assert payload["privilege_assignments"][0]["principal"]


class UCBrowseFixtureWorkspaceTests(TestCase):
    """The acceptance flow: fixture estate → real sync → browse reflects
    the fixture workspace field-for-field."""

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        self.admin = _make_user(
            self.tenant, f"uc-fix-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN"
        )
        self.workspace = _make_workspace(self.tenant)
        self.approval = _make_approval(self.tenant, self.admin)
        _make_credential(self.workspace, self.approval)
        self._server, self.port = _start_estate_server()
        self.addCleanup(_stop_estate_server, self._server)
        UCEstateHandler.routes = _routes_for(load_fixture("estate"))

        import hub.apps.databricks_admin.uc_sync as uc_sync_module

        self._original_factory = uc_sync_module._build_uc_client
        uc_sync_module._build_uc_client = _local_client_factory(self.port)
        self.addCleanup(setattr, uc_sync_module, "_build_uc_client", self._original_factory)

    def _sync(self):
        from hub.apps.databricks_admin.uc_sync import sync_uc_workspace

        outcome = sync_uc_workspace(self.workspace)
        assert "counters" in outcome, outcome
        return outcome

    def test_browse_reflects_the_fixture_workspace(self):
        estate = load_fixture("estate")
        self._sync()

        client = _api_client(self.admin)
        catalogs = client.get(_uc_url(self.workspace.id, "catalogs/"))
        assert catalogs.status_code == 200, catalogs.content
        assert [c["name"] for c in catalogs.json()["results"]] == [
            c["name"] for c in estate["catalogs"]
        ]

        catalog_id = catalogs.json()["results"][0]["id"]
        schemas = client.get(_uc_url(self.workspace.id, f"catalogs/{catalog_id}/schemas/"))
        assert schemas.status_code == 200
        assert [s["name"] for s in schemas.json()["results"]] == [
            s["name"] for s in estate["schemas"]
        ]

        schema_id = schemas.json()["results"][0]["id"]
        tables = client.get(_uc_url(self.workspace.id, f"schemas/{schema_id}/tables/"))
        assert tables.status_code == 200
        rows = tables.json()["results"]
        # The fixture is the contract: names, comments, and the column
        # payload travel from the file through the sync into the answer.
        fixture_tables = {t["name"]: t for t in estate["tables"]}
        assert {r["name"] for r in rows} == set(fixture_tables)
        for row in rows:
            fixture = fixture_tables[row["name"]]
            assert row["columns"] == fixture["columns"], (
                f"table {row['name']} columns must match the fixture file"
            )
            assert row["comment"] == fixture["comment"]
            assert row["full_name"] == fixture["full_name"]

        # The remaining schema-scoped surfaces answer from the fixture too.
        for tail, surface in (
            ("views/", "views"),
            ("volumes/", "volumes"),
            ("models/", "models"),
        ):
            listing = client.get(_uc_url(self.workspace.id, f"schemas/{schema_id}/{tail}"))
            assert listing.status_code == 200, tail
            assert [r["name"] for r in listing.json()["results"]] == [
                item["name"] for item in estate[surface]
            ], f"{tail} must reflect the fixture estate"

        # Workspace-scoped surfaces.
        for tail, surface in (
            ("external-locations/", "external_locations"),
            ("storage-credentials/", "storage_credentials"),
        ):
            listing = client.get(_uc_url(self.workspace.id, tail))
            assert listing.status_code == 200, tail
            assert [r["name"] for r in listing.json()["results"]] == [
                item["name"] for item in estate[surface]
            ], f"{tail} must reflect the fixture estate"

    def test_table_detail_without_binding_fails_closed_on_the_fixture_workspace(self):
        self._sync()
        client = _api_client(self.admin)

        from hub.apps.databricks_admin.models import UCTable

        table = UCTable.objects.get(schema__catalog__workspace=self.workspace, name="orders")
        # No OBO binding → the LIVE permissions leg fails closed (the
        # 1.3 contract) — the mirror leg (columns/comment/full_name) is
        # pinned by UCBrowseFixturePermissionsTests.
        response = client.get(_uc_url(self.workspace.id, f"tables/{table.id}/"))
        assert response.status_code == 502
        assert response.json()["code"] == "DATABRICKS_OBO_REFRESH_FAILED"


class TestUCBrowseFixturePermissions:
    """The table-detail LIVE permissions leg serves the fixture envelope.

    NOTE: named ``Test*`` deliberately — pytest's ``python_classes = Test*``
    convention silently SKIPS classes with any other prefix (the 1.3
    lesson; this class's first name repeated the trap and the pin never
    ran)."""

    def _setup(self):
        require_dns()
        tenant, admin = _setup_tenant()
        from hub.apps.tenants.models import TenantConfig

        config = TenantConfig.objects.get_or_create(tenant=tenant)[0]
        sso = config.get_sso_config()
        sso["databricks"] = {
            "host": "dbc-6710eb95-8fe1.cloud.databricks.com",
            "client_id": "client-abc",
            "redirect_uri": "https://hub.example.com/auth/databricks/callback",
        }
        config.sso_config = sso
        config.save()

        from hub.apps.databricks_admin.models import (
            DatabricksCloud,
            DatabricksUserBinding,
            DatabricksWorkspace,
            UCCatalog,
            UCSchema,
            UCTable,
        )

        workspace = DatabricksWorkspace.objects.create(
            tenant=tenant,
            name=f"ws-fixperm-{uuid.uuid4().hex[:8]}",
            host="dbc-6710eb95-8fe1.cloud.databricks.com",
            cloud=DatabricksCloud.AWS,
            region="us-east-1",
            status="ACTIVE",
        )
        catalog = UCCatalog.objects.create(workspace=workspace, name="main")
        schema = UCSchema.objects.create(catalog=catalog, name="sales")
        table = UCTable.objects.create(
            schema=schema,
            name="orders",
            table_type="MANAGED",
            columns=load_fixture("estate")["tables"][0]["columns"],
            full_name="main.sales.orders",
        )
        binding = DatabricksUserBinding.objects.create(
            tenant=tenant,
            user=admin,
            workspace=workspace,
            databricks_sub=f"sub-{uuid.uuid4().hex[:8]}",
            databricks_email=admin.email,
        )
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

    def test_table_detail_passthrough_matches_the_fixture_permissions(
        self, monkeypatch, local_http_server
    ):
        _tenant, admin, workspace, table, binding = self._setup()
        from hub.apps.databricks_admin.obo_tokens import OBOAccessTokenCache

        # Seed the DEFAULT access cache — that is the pool the provider
        # actually reads (OBOTokenProvider falls back to the module-level
        # _DEFAULT_ACCESS_CACHE = OBOAccessTokenCache()). The 1.3 pin also
        # seeds the redis_13 fixture DB, which the provider NEVER reads —
        # a red herring this pin deliberately does not copy.
        OBOAccessTokenCache().set(binding.id, "dapi-uc-access", 300)
        self._patch_client_factory(monkeypatch, local_http_server, binding)

        fixture = load_fixture("effective_permissions")
        RecordingHandler.json_script = [json.dumps(fixture)]

        response = _api_client(admin).get(_uc_url(workspace.id, f"tables/{table.id}/"))
        assert response.status_code == 200, response.content
        body = response.json()
        # The mirror leg serves the fixture's columns; the LIVE leg serves
        # the fixture's permissions envelope — both from the files.
        assert body["columns"] == load_fixture("estate")["tables"][0]["columns"], (
            "the detail columns must match the fixture estate"
        )
        assert body["effective_permissions"] == fixture, (
            "the LIVE permissions answer must pass the fixture envelope through verbatim"
        )
        perms_calls = [
            r
            for r in RecordingHandler.requests
            if r["path"]
            == "/api/2.1/unity-catalog/effective-permissions/table/main.sales.orders?max_results=0"
        ]
        assert len(perms_calls) == 1
        assert perms_calls[0]["headers"].get("Authorization") == "Bearer dapi-uc-access", (
            "the permissions call must ride the user's OBO bearer"
        )


class UCBrowsePaginationTests(TestCase):
    """The browse listings carry the StandardPageNumberPagination envelope
    (the 1.3 spec: listing endpoints SHALL be paginated)."""

    def setUp(self):
        require_dns()
        self.tenant, self.admin = _setup_tenant()
        from hub.apps.databricks_admin.models import (
            DatabricksCloud,
            DatabricksWorkspace,
            UCCatalog,
            UCSchema,
            UCTable,
        )

        self.workspace = DatabricksWorkspace.objects.create(
            tenant=self.tenant,
            name=f"ws-pag-{uuid.uuid4().hex[:8]}",
            host="dbc-6710eb95-8fe1.cloud.databricks.com",
            cloud=DatabricksCloud.AWS,
            region="us-east-1",
            status="ACTIVE",
        )
        catalog = UCCatalog.objects.create(workspace=self.workspace, name="main")
        self.schema = UCSchema.objects.create(catalog=catalog, name="sales")
        # 55 tables > the 50-row page size → two pages.
        for index in range(55):
            UCTable.objects.create(
                schema=self.schema,
                name=f"t_{index:02d}",
                table_type="MANAGED",
                columns=[{"name": "id"}],
                full_name=f"main.sales.t_{index:02d}",
            )

    def _tables_url(self, tail=""):
        return _uc_url(self.workspace.id, f"schemas/{self.schema.id}/tables/{tail}")

    def test_first_page_carries_the_pagination_envelope(self):
        response = _api_client(self.admin).get(self._tables_url())
        assert response.status_code == 200, response.content
        body = response.json()
        assert body["count"] == 55
        assert body["page"] == 1
        assert body["page_size"] == 50
        assert body["total_pages"] == 2
        assert body["has_next"] is True
        assert len(body["results"]) == 50

    def test_second_page_returns_the_remainder(self):
        response = _api_client(self.admin).get(self._tables_url("?page=2"))
        assert response.status_code == 200, response.content
        body = response.json()
        assert body["page"] == 2
        assert body["has_next"] is False
        assert len(body["results"]) == 5

    def test_page_size_query_param_respects_the_cap(self):
        response = _api_client(self.admin).get(self._tables_url("?page_size=10"))
        assert response.status_code == 200, response.content
        body = response.json()
        assert body["page_size"] == 10
        assert body["total_pages"] == 6
        assert len(body["results"]) == 10

    def test_beyond_last_page_is_a_client_error(self):
        # DRF's PageNumberPagination standard: an out-of-range page is a
        # 404 ("Invalid page"), not an empty 200 — the repo's
        # StandardPageNumberPagination does not override that contract.
        response = _api_client(self.admin).get(self._tables_url("?page=99"))
        assert response.status_code == 404
