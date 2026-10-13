"""Phase 1 (openspec add-databricks-uc-read task 1.4) — UC search feed.

No mocks: the feed writes REAL `SearchIndex` rows in real Postgres, and
the end-to-end test runs the REAL `SearchEngine` full-text search over
the mirrored UC table (tenant-scoped). The provider boundary holds: the
feed lives in `databricks_admin` and imports the core search model — the
search app never imports a databricks_admin model.
"""

import uuid

import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.audit.event_types import SEARCH_PERFORMED
from hub.apps.audit.models import AuditEvent
from hub.apps.databricks_admin.models import (
    DatabricksCloud,
    DatabricksWorkspace,
    UCCatalog,
    UCExternalLocation,
    UCModel,
    UCSchema,
    UCTable,
    UCView,
    UCVolume,
)
from hub.apps.databricks_admin.tests._fixtures import REAL_HOST, require_dns
from hub.apps.databricks_admin.tests.test_views import (
    _activate_billing,
    _make_user,
)
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


def _seed(tenant):
    workspace = DatabricksWorkspace.objects.create(
        tenant=tenant,
        name="ws-1",
        host=REAL_HOST,
        cloud=DatabricksCloud.AWS,
        region="us-east-1",
        status="ACTIVE",
    )
    catalog = UCCatalog.objects.create(workspace=workspace, name="main", comment="primary")
    schema = UCSchema.objects.create(catalog=catalog, name="sales", comment="sales schema")
    table = UCTable.objects.create(
        schema=schema,
        name="orders",
        table_type="MANAGED",
        columns=[{"name": "customer_id"}, {"name": "total_usd"}],
        full_name="main.sales.orders",
        comment="Order fact table",
    )
    view = UCView.objects.create(
        schema=schema, name="v_orders", view_definition="SELECT 1", comment="orders view"
    )
    volume = UCVolume.objects.create(schema=schema, name="raw", comment="raw volume")
    model = UCModel.objects.create(schema=schema, name="churn", comment="churn model")
    return workspace, catalog, schema, table, view, volume, model


class UcSearchFeedTests(TestCase):
    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        _make_user(self.tenant, f"ucs-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN")
        (
            self.workspace,
            self.catalog,
            self.schema,
            self.table,
            self.view,
            self.volume,
            self.model,
        ) = _seed(self.tenant)

    def test_index_uc_table_creates_search_row(self):
        from hub.apps.databricks_admin.uc_search import index_uc_object
        from hub.apps.search.models import SearchIndex

        index_uc_object(self.table)
        row = SearchIndex.objects.get(
            tenant=self.tenant,
            resource_type="DATABRICKS_UC_TABLE",
            resource_id=self.table.id,
        )
        assert row.title == "orders"
        assert row.description == "Order fact table"
        assert "customer_id" in (row.schema_text or "")
        assert "total_usd" in (row.schema_text or "")
        assert row.lineage_metadata["full_name"] == "main.sales.orders"
        assert row.lineage_metadata["catalog"] == "main"
        assert row.lineage_metadata["schema"] == "sales"

    def test_index_is_an_idempotent_update(self):
        from hub.apps.databricks_admin.uc_search import index_uc_object
        from hub.apps.search.models import SearchIndex

        first = index_uc_object(self.table)
        self.table.comment = "renamed comment"
        self.table.save(update_fields=["comment"])
        second = index_uc_object(self.table)
        assert second.id == first.id, "re-indexing must update the SAME row"
        assert (
            SearchIndex.objects.filter(
                tenant=self.tenant, resource_type="DATABRICKS_UC_TABLE"
            ).count()
            == 1
        )
        assert second.description == "renamed comment"

    def test_all_uc_surfaces_index_with_their_types(self):
        from hub.apps.databricks_admin.uc_search import index_uc_object
        from hub.apps.search.models import SearchIndex

        expectations = (
            (self.catalog, "DATABRICKS_UC_CATALOG"),
            (self.schema, "DATABRICKS_UC_SCHEMA"),
            (self.table, "DATABRICKS_UC_TABLE"),
            (self.view, "DATABRICKS_UC_VIEW"),
            (self.volume, "DATABRICKS_UC_VOLUME"),
            (self.model, "DATABRICKS_UC_MODEL"),
        )
        for obj, resource_type in expectations:
            index_uc_object(obj)
            assert SearchIndex.objects.filter(
                tenant=self.tenant, resource_type=resource_type, resource_id=obj.id
            ).exists(), resource_type

    def test_delete_uc_index_removes_the_row(self):
        from hub.apps.databricks_admin.uc_search import delete_uc_index, index_uc_object
        from hub.apps.search.models import SearchIndex

        index_uc_object(self.table)
        delete_uc_index(self.table)
        assert not SearchIndex.objects.filter(
            tenant=self.tenant, resource_type="DATABRICKS_UC_TABLE"
        ).exists()

    def test_reindex_uc_workspace_indexes_the_whole_estate(self):
        from hub.apps.databricks_admin.uc_search import reindex_uc_workspace
        from hub.apps.search.models import SearchIndex

        reindex_uc_workspace(self.workspace)
        count = SearchIndex.objects.filter(tenant=self.tenant).count()
        assert count == 6, f"the whole estate must be indexed, got {count} rows"

    def test_reindex_deletes_stale_rows(self):
        from hub.apps.databricks_admin.uc_search import reindex_uc_workspace
        from hub.apps.search.models import SearchIndex

        stale = UCTable.objects.create(schema=self.schema, name="stale_table")
        from hub.apps.databricks_admin.uc_search import index_uc_object

        index_uc_object(stale)
        stale.delete()
        reindex_uc_workspace(self.workspace)
        assert not SearchIndex.objects.filter(
            tenant=self.tenant, resource_type="DATABRICKS_UC_TABLE", resource_id=stale.id
        ).exists(), "mirror deletions must drop their index rows"


class UcSearchEndToEndTests(TestCase):
    """The REAL full-text search finds the mirrored UC table."""

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        _make_user(self.tenant, f"ucs-e2e-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN")
        _w, _c, _s, self.table, _v, _vo, _m = _seed(self.tenant)

    def test_search_engine_finds_the_mirrored_table(self):
        from hub.apps.databricks_admin.uc_search import index_uc_object
        from hub.apps.search.search_engine import SearchEngine

        index_uc_object(self.table)

        results, total = SearchEngine().search(str(self.tenant.id), "orders")
        assert total >= 1
        assert any(
            r.get("type") == "DATABRICKS_UC_TABLE" and r.get("title") == "orders" for r in results
        ), "the mirrored table must surface in the real search results"

    def test_search_is_tenant_scoped(self):
        from hub.apps.databricks_admin.uc_search import index_uc_object
        from hub.apps.search.search_engine import SearchEngine

        other_tenant = TenantFactory.create_tenant()
        _activate_billing(other_tenant)
        index_uc_object(self.table)

        _results, total = SearchEngine().search(str(other_tenant.id), "orders")
        assert total == 0, "a tenant must never see another tenant's UC search rows"


class UcSearchSweepIsolationTests(TestCase):
    """1.4 review — the stale-row sweep must never cross workspace
    boundaries, and must clean rows whose workspace was hard-deleted
    (mirror rows cascade, index rows do not)."""

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        _make_user(self.tenant, f"ucs-sweep-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN")
        # Workspace A: the full seeded estate.
        self.workspace_a, _ca, _sa, _ta, _va, _voa, _ma = _seed(self.tenant)
        # Workspace B: same tenant, second estate (names must differ only
        # where unique constraints are (tenant, name) — the chain below
        # reuses catalog/schema/table names freely, they are scoped deeper).
        self.workspace_b = DatabricksWorkspace.objects.create(
            tenant=self.tenant,
            name="ws-2",
            host=REAL_HOST,
            cloud=DatabricksCloud.AWS,
            region="us-east-1",
            status="ACTIVE",
        )
        self.catalog_b = UCCatalog.objects.create(workspace=self.workspace_b, name="main")
        self.schema_b = UCSchema.objects.create(catalog=self.catalog_b, name="sales")
        self.table_b = UCTable.objects.create(
            schema=self.schema_b,
            name="b_orders",
            table_type="MANAGED",
            columns=[{"name": "order_id"}],
            full_name="main.sales.b_orders",
        )

    def test_reindex_one_workspace_keeps_the_other_workspaces_rows(self):
        from hub.apps.databricks_admin.uc_search import index_uc_object, reindex_uc_workspace
        from hub.apps.search.models import SearchIndex

        index_uc_object(self.table_b)
        reindex_uc_workspace(self.workspace_a)
        assert SearchIndex.objects.filter(
            tenant=self.tenant,
            resource_type="DATABRICKS_UC_TABLE",
            resource_id=self.table_b.id,
        ).exists(), "reindexing workspace A must never delete workspace B's rows"

    def test_reindex_sweeps_rows_of_a_deleted_workspace(self):
        from hub.apps.databricks_admin.uc_search import index_uc_object, reindex_uc_workspace
        from hub.apps.search.models import SearchIndex

        index_uc_object(self.table_b)
        index_uc_object(_table_of(self.workspace_a))
        # Hard-delete workspace B — its mirror rows cascade, its index
        # rows must be swept by the NEXT reindex of any sibling workspace.
        self.workspace_b.delete()
        reindex_uc_workspace(self.workspace_a)
        assert not SearchIndex.objects.filter(
            tenant=self.tenant, resource_type="DATABRICKS_UC_TABLE", resource_id=self.table_b.id
        ).exists(), "a deleted workspace's index rows must be swept"
        assert SearchIndex.objects.filter(
            tenant=self.tenant, resource_type="DATABRICKS_UC_TABLE"
        ).exists(), "the surviving workspace's rows must be kept"


class UcSearchDocumentTests(TestCase):
    """1.4 review — document content gaps."""

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        _make_user(self.tenant, f"ucs-doc-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN")
        self.workspace, _c, _s, self.table, _v, _vo, _m = _seed(self.tenant)

    def test_table_schema_text_includes_column_types(self):
        from hub.apps.databricks_admin.uc_search import index_uc_object
        from hub.apps.search.models import SearchIndex

        self.table.columns = [
            {"name": "customer_id", "type_text": "BIGINT"},
            {"name": "total_usd", "type_name": "DECIMAL(10,2)"},
        ]
        self.table.save(update_fields=["columns"])
        index_uc_object(self.table)
        row = SearchIndex.objects.get(
            tenant=self.tenant,
            resource_type="DATABRICKS_UC_TABLE",
            resource_id=self.table.id,
        )
        assert "BIGINT" in (row.schema_text or ""), "column types must be searchable"
        assert "DECIMAL(10,2)" in (row.schema_text or "")

    def test_non_searchable_mirror_types_are_a_noop(self):
        from hub.apps.databricks_admin.uc_search import (
            delete_uc_index,
            index_uc_object,
        )
        from hub.apps.search.models import SearchIndex

        external = UCExternalLocation.objects.create(
            workspace=self.workspace, name="s3-raw", url="s3://bucket/raw"
        )
        assert index_uc_object(external) is None
        delete_uc_index(external)  # must not raise
        assert not SearchIndex.objects.filter(
            tenant=self.tenant, resource_type__startswith="DATABRICKS_UC_"
        ).exists()


class UcSearchApiEndToEndTests(TestCase):
    """1.4 review — the canonical /api/search/ (UnifiedSearchView) must
    surface the mirrored UC table with the Phase 273 contract: the
    SEARCH_PERFORMED audit row (spec scenario of add-databricks-uc-read).

    No mocks: real SearchIndex rows, the real view, real audit rows.
    """

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        self.user = _make_user(
            self.tenant, f"ucs-api-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN"
        )
        _w, _c, _s, self.table, _v, _vo, _m = _seed(self.tenant)
        from hub.apps.databricks_admin.uc_search import index_uc_object

        index_uc_object(self.table)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_canonical_search_surfaces_uc_table_and_emits_seach_performed(self):
        response = self.client.get("/api/search/", {"q": "orders", "types": "assets,contracts,uc"})
        assert response.status_code == 200, response.data
        results = response.data["results"]
        assert any(r.get("type") == "uc_table" and r.get("name") == "orders" for r in results), (
            f"the UC table must surface in the canonical search: {results}"
        )

        audit = (
            AuditEvent.objects.filter(
                tenant=self.tenant,
                action=SEARCH_PERFORMED,
                resource_type="SEARCH_QUERY",
            )
            .order_by("-timestamp")
            .first()
        )
        assert audit is not None, "SEARCH_PERFORMED must be emitted for UC searches"
        assert "orders" in (audit.details_json or {}).get("query_truncated", "")


def _table_of(workspace):
    """The first table of the given workspace's seeded estate."""
    from hub.apps.databricks_admin.models import UCTable

    return UCTable.objects.get(schema__catalog__workspace=workspace, name="orders")
