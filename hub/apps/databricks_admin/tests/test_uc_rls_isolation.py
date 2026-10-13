"""Phase 1 (openspec add-databricks-uc-read task 1.12) — RLS isolation
for the UC mirror: RUNTIME enforcement + the browse endpoint contract.

Two layers are pinned:

1. RUNTIME enforcement — the 1.2 mirror policies resolve the tenant
   through the parent chain (workspace / schema → catalog → workspace).
   The test connection here is a SUPERUSER (p313-pg ``hub``), which
   Postgres exempts from RLS — policy-EXISTENCE scans (test_uc_models)
   cannot prove the policies FILTER. A dedicated ``hub_rls_probe`` role
   (NOSUPERUSER NOBYPASSRLS NOLOGIN, SELECT-only grants) switches the
   session via ``SET ROLE`` and counts visible rows under a foreign
   tenant's ``app.current_tenant_id``: exactly the owning tenant's rows
   come back, a foreign tenant sees ZERO. On non-superuser connections
   (the compose stack) the connection itself is the enforcement subject
   and the ORM asserts directly — the helper adapts to either world.

2. Endpoint isolation — a tenant B admin browsing tenant A's workspace
   (or a SIBLING workspace of tenant A) gets 404 on every surface
   (listings AND the table-detail leg), never a leak.

No mocks: real Postgres rows, real RBAC, real RLS.
"""

import uuid

import pytest
from django.test import TestCase

from hub.apps.databricks_admin.tests._fixtures import require_dns
from hub.apps.databricks_admin.tests.test_uc_browse import _api_client, _uc_url
from hub.apps.databricks_admin.tests.test_uc_sync import _make_workspace
from hub.apps.databricks_admin.tests.test_views import _activate_billing, _make_user
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)

_RLS_PROBE_ROLE = "hub_rls_probe"
_MIRROR_TABLES = (
    "databricks_uc_catalogs",
    "databricks_uc_schemas",
    "databricks_uc_tables",
    "databricks_uc_views",
    "databricks_uc_volumes",
    "databricks_uc_models",
    "databricks_uc_external_locations",
    "databricks_uc_storage_credentials",
    # 4.2 — the job/run mirror (the runs policy's subquery reads the
    # jobs table, so the probe role needs SELECT on both).
    "databricks_jobs",
    "databricks_job_runs",
    # 5.2 — the Delta Sharing recipient/token registry (direct-FK
    # policies on both tables).
    "databricks_delta_share_recipients",
    "databricks_delta_share_tokens",
    # 5.3 — the Delta Sharing snapshot table (direct-FK policy).
    "databricks_delta_share_snapshots",
    # 10.2 — the DLT pipeline/update mirror (the updates policy's
    # subquery reads the pipelines table, so the probe role needs
    # SELECT on both).
    "databricks_dlt_pipelines",
    "databricks_dlt_pipeline_updates",
)


def _ensure_rls_probe_role():
    """Create (idempotently) the non-superuser probe role + SELECT grants
    on the mirror tables and the workspace chain. Safe on shared test
    DBs: role + grants are idempotent cluster objects."""
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [_RLS_PROBE_ROLE])
        if cursor.fetchone() is None:
            cursor.execute(f"CREATE ROLE {_RLS_PROBE_ROLE} NOSUPERUSER NOBYPASSRLS NOLOGIN")
        cursor.execute(f"GRANT USAGE ON SCHEMA public TO {_RLS_PROBE_ROLE}")
        for table in (
            *_MIRROR_TABLES,
            "databricks_workspaces",
            "databricks_uc_change_requests",
            "uc_principals",
            "uc_grant_bindings",
        ):
            cursor.execute(f"GRANT SELECT ON {table} TO {_RLS_PROBE_ROLE}")


def _connection_bypasses_rls():
    """True when the test connection's role is exempt from RLS (a
    superuser). In that world the probe-role path is the only way to
    exercise enforcement."""
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('is_superuser')")
        if cursor.fetchone()[0] == "on":
            return True
        cursor.execute("SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user")
        return bool(cursor.fetchone()[0])


def _visible_count_as(role_or_none, tenant_id, table):
    """Count rows visible on *table* under *tenant_id*'s tenant GUC.
    ``role_or_none`` is the probe role when the connection bypasses RLS,
    else None (the connection itself enforces)."""
    from django.db import connection

    with connection.cursor() as cursor:
        try:
            if role_or_none:
                cursor.execute(f"SET ROLE {role_or_none}")
            cursor.execute("SELECT set_config('app.current_tenant_id', %s, true)", [str(tenant_id)])
            cursor.execute(f"SELECT count(*) FROM {table}")
            count = cursor.fetchone()[0]
            cursor.execute("SELECT set_config('app.current_tenant_id', NULL, true)")
            return count
        finally:
            if role_or_none:
                cursor.execute("RESET ROLE")


class UCMirrorRuntimeRLSTests(TestCase):
    """The multi-hop mirror policies FILTER at runtime, not just exist."""

    def setUp(self):
        require_dns()
        self.tenant_a = TenantFactory.create_tenant()
        _activate_billing(self.tenant_a)
        self.tenant_b = TenantFactory.create_tenant()
        _activate_billing(self.tenant_b)
        self.workspace = _make_workspace(self.tenant_a, name=f"ws-rls-{uuid.uuid4().hex[:8]}")

        from hub.apps.databricks_admin.models import UCCatalog, UCSchema, UCTable

        catalog = UCCatalog.objects.create(workspace=self.workspace, name="main")
        schema = UCSchema.objects.create(catalog=catalog, name="sales")
        UCTable.objects.create(
            schema=schema,
            name="orders",
            table_type="MANAGED",
            columns=[{"name": "id"}],
            full_name="main.sales.orders",
        )

    def _probe_role(self):
        if _connection_bypasses_rls():
            _ensure_rls_probe_role()
            return _RLS_PROBE_ROLE
        return None

    def test_workspace_scoped_mirror_rows_are_hidden_from_foreign_tenants(self):
        probe = self._probe_role()
        assert _visible_count_as(probe, self.tenant_a.id, "databricks_uc_catalogs") == 1
        assert _visible_count_as(probe, self.tenant_b.id, "databricks_uc_catalogs") == 0, (
            "tenant B must see ZERO of tenant A's catalogs (RLS runtime enforcement)"
        )

    def test_multi_hop_mirror_rows_are_hidden_from_foreign_tenants(self):
        # The 3-hop chain: tables → schemas → catalogs → workspaces.
        probe = self._probe_role()
        assert _visible_count_as(probe, self.tenant_a.id, "databricks_uc_tables") == 1
        assert _visible_count_as(probe, self.tenant_b.id, "databricks_uc_tables") == 0, (
            "the schema→catalog→workspace chain policy must hide the table from tenant B"
        )

    def test_no_tenant_context_hides_all_mirror_rows(self):
        # An UNSET tenant GUC (the fail-closed default) must surface NOTHING
        # through the policies — a missing context never leaks the estate.
        from django.db import connection

        probe = self._probe_role()
        with connection.cursor() as cursor:
            try:
                if probe:
                    cursor.execute(f"SET ROLE {probe}")
                cursor.execute("SELECT count(*) FROM databricks_uc_tables")
                assert cursor.fetchone()[0] == 0, (
                    "without a tenant context the policy must hide everything"
                )
            finally:
                if probe:
                    cursor.execute("RESET ROLE")


class UCBrowseRLSIsolationTests(TestCase):
    """The browse endpoints answer 404 for foreign workspaces — listings
    AND the detail leg — never a cross-tenant leak."""

    def setUp(self):
        require_dns()
        self.tenant_a, self.admin_a = self._tenant_with_admin("a")
        self.tenant_b, self.admin_b = self._tenant_with_admin("b")
        self.workspace_a = _make_workspace(self.tenant_a, name=f"ws-a-{uuid.uuid4().hex[:8]}")
        self.workspace_a2 = _make_workspace(self.tenant_a, name=f"ws-a2-{uuid.uuid4().hex[:8]}")

        from hub.apps.databricks_admin.models import UCCatalog, UCSchema, UCTable

        catalog = UCCatalog.objects.create(workspace=self.workspace_a, name="main")
        schema = UCSchema.objects.create(catalog=catalog, name="sales")
        self.table = UCTable.objects.create(
            schema=schema,
            name="orders",
            table_type="MANAGED",
            columns=[{"name": "id"}],
            full_name="main.sales.orders",
        )
        self.catalog = catalog
        self.schema = schema

    def _tenant_with_admin(self, suffix):
        tenant = TenantFactory.create_tenant()
        _activate_billing(tenant)
        admin = _make_user(
            tenant, f"uc-rls-{suffix}-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN"
        )
        return tenant, admin

    def test_foreign_tenant_cannot_list_workspace_catalogs(self):
        response = _api_client(self.admin_b).get(_uc_url(self.workspace_a.id, "catalogs/"))
        assert response.status_code == 404

    def test_foreign_tenant_cannot_list_schemas_or_tables(self):
        client = _api_client(self.admin_b)
        assert (
            client.get(
                _uc_url(self.workspace_a.id, f"catalogs/{self.catalog.id}/schemas/")
            ).status_code
            == 404
        )
        assert (
            client.get(
                _uc_url(self.workspace_a.id, f"schemas/{self.schema.id}/tables/")
            ).status_code
            == 404
        )

    def test_foreign_tenant_cannot_read_table_detail(self):
        response = _api_client(self.admin_b).get(
            _uc_url(self.workspace_a.id, f"tables/{self.table.id}/")
        )
        assert response.status_code == 404

    def test_sibling_workspace_of_the_same_tenant_is_isolated(self):
        # Same tenant, different workspace: the mirror of workspace A2 is
        # empty — workspace A's rows must never bleed into A2's browse.
        response = _api_client(self.admin_a).get(_uc_url(self.workspace_a2.id, "catalogs/"))
        assert response.status_code == 200, response.content
        assert response.json()["results"] == [], (
            "a sibling workspace must not surface another workspace's mirrors"
        )

    def test_foreign_tenant_cannot_list_workspace_scoped_surfaces(self):
        client = _api_client(self.admin_b)
        for tail in ("external-locations/", "storage-credentials/"):
            response = client.get(_uc_url(self.workspace_a.id, tail))
            assert response.status_code == 404, tail


class Phase2RuntimeRLSTests(TestCase):
    """Task 2.11 — runtime RLS enforcement on the THREE Phase-2 tables:
    databricks_uc_change_requests (direct-FK) + uc_principals /
    uc_grant_bindings (workspace-resolved policies, migration 0017)."""

    def setUp(self):
        require_dns()
        self.tenant_a = TenantFactory.create_tenant()
        _activate_billing(self.tenant_a)
        self.tenant_b = TenantFactory.create_tenant()
        _activate_billing(self.tenant_b)
        self.workspace = _make_workspace(self.tenant_a, name=f"ws-rls2-{uuid.uuid4().hex[:8]}")
        from hub.apps.users.models import User, UserStatus

        self.requester = User.objects.create_user(
            email=f"{uuid.uuid4().hex[:8]}-rls2@test.com",
            password="testpass123",
            tenant=self.tenant_a,
            status=UserStatus.ACTIVE,
        )
        from hub.apps.databricks_admin.models import (
            UCChangeAction,
            UCChangeRequest,
            UCObjectType,
        )

        self.change_request = UCChangeRequest.objects.create(
            tenant=self.tenant_a,
            workspace=self.workspace,
            requested_by=self.requester,
            change_type=UCChangeAction.CREATE,
            securable_type=UCObjectType.TABLE,
            full_name="main.sales.orders_v2",
            definition={"identifiers": ["main", "sales", "orders_v2"], "options": {}},
        )
        from hub.apps.databricks_admin.models import (
            UCGrantBinding,
            UCGrantBindingStatus,
            UCPPrincipal,
            UCPPrincipalType,
        )

        self.principal = UCPPrincipal.objects.create(
            workspace=self.workspace, name="data-team", principal_type=UCPPrincipalType.GROUP
        )
        self.binding = UCGrantBinding.objects.create(
            workspace=self.workspace,
            principal=self.principal,
            securable_type="TABLE",
            securable_full_name="main.sales.orders",
            privilege="SELECT",
            status=UCGrantBindingStatus.PLANNED,
        )

    def _probe_role(self):
        if _connection_bypasses_rls():
            _ensure_rls_probe_role()
            return _RLS_PROBE_ROLE
        return None

    def test_uc_change_request_rows_are_hidden_from_foreign_tenants(self):
        probe = self._probe_role()
        table = "databricks_uc_change_requests"
        assert _visible_count_as(probe, self.tenant_a.id, table) == 1
        assert _visible_count_as(probe, self.tenant_b.id, table) == 0, (
            "tenant B must see ZERO of tenant A's change requests"
        )
        assert _visible_count_as(probe, None, table) == 0, (
            "an unset tenant GUC must hide ALL rows (fail-closed)"
        )

    def test_uc_principal_rows_are_hidden_from_foreign_tenants(self):
        probe = self._probe_role()
        table = "uc_principals"
        assert _visible_count_as(probe, self.tenant_a.id, table) == 1
        assert _visible_count_as(probe, self.tenant_b.id, table) == 0, (
            "the workspace-resolved policy must hide the principal from tenant B"
        )

    def test_uc_grant_binding_rows_are_hidden_from_foreign_tenants(self):
        probe = self._probe_role()
        table = "uc_grant_bindings"
        assert _visible_count_as(probe, self.tenant_a.id, table) == 1
        assert _visible_count_as(probe, self.tenant_b.id, table) == 0, (
            "the workspace-resolved policy must hide the binding from tenant B"
        )
        assert _visible_count_as(probe, None, table) == 0, (
            "an unset tenant GUC must hide ALL bindings (fail-closed)"
        )
