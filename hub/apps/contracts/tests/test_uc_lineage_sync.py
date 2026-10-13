"""Phase 1 (openspec add-databricks-uc-read task 1.6) — UC lineage reads.

The UC lineage reader (``contracts/lineage_sync.py``) extends the
existing ``LineageEdge`` graph with table → view reference edges
discovered from the UC MIRROR — no new surface, no API-shape change.
The spec scenario: a mirrored view ``v_orders`` defined over ``orders``
and ``customers`` yields ``v_orders → orders`` and
``v_orders → customers`` edges.

No mocks: real Postgres mirror rows (databricks_admin mirror models,
created directly — test-side imports are boundary-free), the REAL
reader over ``apps.get_model`` string references (the provider-boundary
pattern — the contracts app never imports a databricks_admin model), and
real SCD Type 2 edge rows (close-then-insert, DB-side NOW()).
"""

import pytest
from django.test import TestCase

from hub.apps.contracts.models import LineageEdge, LineageEdgeType
from hub.apps.databricks_admin.models import (
    DatabricksCloud,
    DatabricksWorkspace,
    UCCatalog,
    UCSchema,
    UCTable,
    UCView,
)
from hub.apps.databricks_admin.tests._fixtures import REAL_HOST, require_dns
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


def _make_workspace(tenant, name="ws-1"):
    return DatabricksWorkspace.objects.create(
        tenant=tenant,
        name=name,
        host=REAL_HOST,
        cloud=DatabricksCloud.AWS,
        region="us-east-1",
        status="ACTIVE",
    )


def _mirror_table(catalog, schema, name):
    return UCTable.objects.create(
        schema=schema,
        name=name,
        table_type="MANAGED",
        columns=[],
        full_name=f"{catalog.name}.{schema.name}.{name}",
    )


class UcLineageSyncTests(TestCase):
    """The UC mirror feeds the lineage graph."""

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        self.workspace = _make_workspace(self.tenant)
        self.catalog = UCCatalog.objects.create(workspace=self.workspace, name="main")
        self.sales = UCSchema.objects.create(catalog=self.catalog, name="sales")
        self.orders = _mirror_table(self.catalog, self.sales, "orders")
        self.customers = _mirror_table(self.catalog, self.sales, "customers")
        self.v_orders = UCView.objects.create(
            schema=self.sales,
            name="v_orders",
            view_definition="SELECT * FROM orders JOIN customers USING (customer_id)",
            full_name="main.sales.v_orders",
        )
        self.job_ref = f"databricks_uc_metadata_sync:{self.workspace.id}"

    def _sync(self):
        from hub.apps.contracts.lineage_sync import sync_uc_lineage

        return sync_uc_lineage(tenant=self.tenant, workspace_id=str(self.workspace.id))

    def _open_edges(self):
        return LineageEdge.objects.filter(
            tenant=self.tenant, job_ref=self.job_ref, valid_to__isnull=True
        )

    def test_view_dependencies_become_reference_edges(self):
        result = self._sync()
        assert result["added"] == 2, result
        assert result["removed"] == 0, result
        edges = self._open_edges()
        assert {(e.source_model, e.target_model) for e in edges} == {
            ("main.sales.orders", "main.sales.v_orders"),
            ("main.sales.customers", "main.sales.v_orders"),
        }
        for edge in edges:
            assert edge.edge_type == LineageEdgeType.REFERENCE
            assert edge.source_contract_id is None
            assert edge.target_contract_id is None
            assert edge.transformation_ref == "main.sales.v_orders"
            assert edge.valid_from is not None

    def test_sync_is_idempotent(self):
        self._sync()
        second = self._sync()
        assert second["added"] == 0, second
        assert second["removed"] == 0, second
        assert self._open_edges().count() == 2

    def test_removed_dependency_closes_the_edge(self):
        self._sync()
        self.v_orders.view_definition = "SELECT * FROM orders"
        self.v_orders.save(update_fields=["view_definition"])
        result = self._sync()
        assert result["removed"] == 1, result
        open_edges = self._open_edges()
        assert {(e.source_model, e.target_model) for e in open_edges} == {
            ("main.sales.orders", "main.sales.v_orders")
        }
        closed = LineageEdge.objects.filter(
            tenant=self.tenant,
            job_ref=self.job_ref,
            source_model="main.sales.customers",
            valid_to__isnull=False,
        )
        assert closed.exists(), "the dropped dependency must be SCD-closed"

    def test_deleted_view_closes_all_its_edges(self):
        self._sync()
        self.v_orders.delete()
        result = self._sync()
        assert result["removed"] == 2, result
        assert self._open_edges().count() == 0

    def test_qualified_cross_schema_reference_matches(self):
        finance = UCSchema.objects.create(catalog=self.catalog, name="finance")
        invoices = _mirror_table(self.catalog, finance, "invoices")
        self.v_orders.view_definition = "SELECT * FROM finance.invoices"
        self.v_orders.save(update_fields=["view_definition"])

        result = self._sync()
        assert result["added"] == 1, result
        edge = self._open_edges().get()
        assert edge.source_model == "main.finance.invoices"
        assert edge.target_model == "main.sales.v_orders"
        assert invoices.full_name == "main.finance.invoices"

    def test_bare_name_matches_only_the_views_own_schema(self):
        finance = UCSchema.objects.create(catalog=self.catalog, name="finance")
        _mirror_table(self.catalog, finance, "orders")  # same name, other schema
        self.v_orders.view_definition = "SELECT * FROM orders"
        self.v_orders.save(update_fields=["view_definition"])

        result = self._sync()
        assert result["added"] == 1, result
        edge = self._open_edges().get()
        assert edge.source_model == "main.sales.orders", (
            "a bare table name must resolve to the VIEW's own schema, "
            "never an ambiguous sibling schema"
        )

    def test_comments_and_string_literals_do_not_create_edges(self):
        self.v_orders.view_definition = (
            "SELECT 1 -- orders\n/* customers */\nWHERE note = 'orders customers'"
        )
        self.v_orders.save(update_fields=["view_definition"])

        result = self._sync()
        assert result["added"] == 0, result
        assert self._open_edges().count() == 0

    def test_workspace_without_views_adds_no_edges(self):
        empty_ws = _make_workspace(self.tenant, name="ws-2")
        from hub.apps.contracts.lineage_sync import sync_uc_lineage

        result = sync_uc_lineage(tenant=self.tenant, workspace_id=str(empty_ws.id))
        assert result["added"] == 0, result
        assert not self._open_edges().exists()

    def test_edges_do_not_leak_across_tenants(self):
        other_tenant = TenantFactory.create_tenant()
        self._sync()
        other_edges = LineageEdge.objects.filter(
            tenant=other_tenant,
            job_ref=self.job_ref,
            valid_to__isnull=True,
        )
        assert not other_edges.exists(), "lineage edges are tenant-scoped rows"

    def test_edges_do_not_leak_across_workspaces(self):
        second_ws = _make_workspace(self.tenant, name="ws-2")
        catalog_b = UCCatalog.objects.create(workspace=second_ws, name="main")
        schema_b = UCSchema.objects.create(catalog=catalog_b, name="sales")
        orders_b = _mirror_table(catalog_b, schema_b, "orders")
        UCView.objects.create(
            schema=schema_b,
            name="v_orders",
            view_definition="SELECT * FROM orders",
            full_name="main.sales.v_orders",
        )

        self._sync()
        first_ws_edges = self._open_edges()
        assert {(e.source_model, e.target_model) for e in first_ws_edges} == {
            ("main.sales.orders", "main.sales.v_orders"),
            ("main.sales.customers", "main.sales.v_orders"),
        }
        # The second workspace's own sync — scoped by its job_ref.
        from hub.apps.contracts.lineage_sync import sync_uc_lineage

        result = sync_uc_lineage(tenant=self.tenant, workspace_id=str(second_ws.id))
        assert result["added"] == 1, result
        assert orders_b.full_name == "main.sales.orders"

    # ── 1.6 review pins (gaps found in the review pass) ────────────────────

    def test_backtick_quoted_qualified_reference_matches_cross_schema(self):
        # `` `finance`.`invoices` `` is ONE qualified identifier chain —
        # the tokenizer must keep the segments joined so the cross-schema
        # reference resolves (the naive per-segment split would treat
        # `invoices` as a BARE token and never match the sibling schema).
        finance = UCSchema.objects.create(catalog=self.catalog, name="finance")
        _mirror_table(self.catalog, finance, "invoices")
        self.v_orders.view_definition = "SELECT * FROM `finance`.`invoices`"
        self.v_orders.save(update_fields=["view_definition"])

        result = self._sync()
        assert result["added"] == 1, result
        edge = self._open_edges().get()
        assert edge.source_model == "main.finance.invoices"

    def test_ambiguous_two_part_reference_resolves_to_the_views_own_catalog(self):
        # Two catalogs each hold a sales.orders table. BOTH directions:
        # a main-catalog view's `sales.orders` must resolve to main's
        # table, and an aux-catalog view's `sales.orders` must resolve to
        # AUX's table — the view's OWN catalog decides, never the mirror's
        # query order.
        aux = UCCatalog.objects.create(workspace=self.workspace, name="aux")
        aux_sales = UCSchema.objects.create(catalog=aux, name="sales")
        aux_orders = _mirror_table(aux, aux_sales, "orders")
        UCView.objects.create(
            schema=aux_sales,
            name="v_orders_aux",
            view_definition="SELECT * FROM sales.orders",
            full_name="aux.sales.v_orders_aux",
        )
        self.v_orders.view_definition = "SELECT * FROM sales.orders"
        self.v_orders.save(update_fields=["view_definition"])

        result = self._sync()
        assert result["added"] == 2, result
        edges = {(e.source_model, e.target_model) for e in self._open_edges()}
        assert edges == {
            ("main.sales.orders", "main.sales.v_orders"),
            ("aux.sales.orders", "aux.sales.v_orders_aux"),
        }, "each view's 2-part token must resolve within its OWN catalog"
        assert aux_orders.full_name == "aux.sales.orders"

    def test_created_edge_audit_carries_the_edge_id(self):
        from hub.apps.audit.models import LINEAGE_EDGE_CREATED, AuditEvent

        self._sync()
        audit = (
            AuditEvent.objects.filter(
                tenant=self.tenant,
                action=LINEAGE_EDGE_CREATED,
            )
            .order_by("-timestamp")
            .first()
        )
        assert audit is not None, "edge creation must be audited"
        assert audit.resource_id is not None, (
            "the audit row must link the persisted edge row (the "
            "REQ-LIN-007 discipline: resource_id = the edge id)"
        )
        assert LineageEdge.objects.filter(id=audit.resource_id).exists()
