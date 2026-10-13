"""P8 (openspec add-databricks-account-plane task 8.7) — the admin-DB
path pinned per the 1.12 RLS pre-flight template (the
``test_uc_rls_isolation`` conventions).

The estate summary's truth source is the ADMIN connection
(``using("admin")``, BYPASSRLS) reading the tenant-scoped tables. This
suite proves the RUNTIME foundation the summary relies on — the
CONTRAST, both halves:

- the TENANT path enforces: under the ``hub_rls_probe`` role
  (NOSUPERUSER NOBYPASSRLS — the test connection itself is a superuser
  and RLS-exempt) with a tenant GUC set, only the owning tenant's
  workspace/budget rows are visible — a foreign tenant sees ZERO (the
  1.2 template's runtime-filtering proof, applied to the 7.2/7.4
  tables the summary aggregates);
- the ADMIN path bypasses: the same rows are ALL visible on the admin
  alias regardless of the tenant GUC — the BYPASSRLS read the
  ``estate_summary`` derives from, pinned at runtime (a regression that
  makes the admin alias tenant-filtered would break the summary's
  cross-tenant contract).

NO MOCKS: real Postgres rows (two tenants' workspaces + budgets), the
REAL RLS policies, the REAL admin alias, the 1.12 probe role (created
idempotently, SELECT grants), and the PRODUCTION ``estate_summary()``
service end-to-end. ``TransactionTestCase`` — the cross-alias pins need
the two COMMITTED connections the production role split actually has
(the 8.2 lesson: a plain TestCase wraps every alias in test atomics).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from django.db import connections
from django.test import TransactionTestCase

from hub.apps.databricks_admin.models import (
    DatabricksCloud,
    DatabricksCostBudget,
    DatabricksWorkspace,
    DatabricksWorkspaceStatus,
)
from hub.apps.databricks_admin.tests._fixtures import REAL_HOST, require_dns
from hub.apps.databricks_admin.tests.test_uc_rls_isolation import (
    _RLS_PROBE_ROLE,
    _connection_bypasses_rls,
    _ensure_rls_probe_role,
)
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

_BUDGET_TABLE = "databricks_cost_budgets"
_WORKSPACE_TABLE = "databricks_workspaces"


def _mk_tenant(*, name):
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"{name}-{uid}",
        slug=f"{name.lower()}-{uid}",
        status=TenantStatus.ACTIVE,
        kyc_status=KYCStatus.UNVERIFIED,
    )
    ensure_tenant_has_active_subscription(tenant)
    return tenant


class AdminDBPathPreflightTests(TransactionTestCase):
    """The 1.12 template's runtime contrast applied to the estate
    summary's admin-DB path."""

    def setUp(self):
        require_dns()
        self.tenant_a = _mk_tenant(name="Alpha")
        self.tenant_b = _mk_tenant(name="Beta")

        self.ws_a = DatabricksWorkspace.objects.create(
            tenant=self.tenant_a,
            name=f"ws-{uuid.uuid4().hex[:8]}",
            host=REAL_HOST,
            cloud=DatabricksCloud.AWS,
            region="us-east-1",
            status=DatabricksWorkspaceStatus.ACTIVE,
        )
        self.ws_b = DatabricksWorkspace.objects.create(
            tenant=self.tenant_b,
            name=f"ws-{uuid.uuid4().hex[:8]}",
            host=REAL_HOST,
            cloud=DatabricksCloud.AWS,
            region="us-east-1",
            status=DatabricksWorkspaceStatus.ACTIVE,
        )
        self.budget_a = DatabricksCostBudget.objects.create(
            tenant=self.tenant_a,
            budget_units_per_hour=Decimal("100"),
            enforcement_mode="BLOCK",
        )
        self.budget_b = DatabricksCostBudget.objects.create(
            tenant=self.tenant_b,
            budget_units_per_hour=Decimal("200"),
            enforcement_mode="BLOCK",
        )

    def _probe_role(self):
        """The 1.12 probe role when the connection bypasses RLS, with the
        summary's tables granted (idempotently)."""
        from django.db import connection

        if not _connection_bypasses_rls():
            return None
        _ensure_rls_probe_role()
        with connection.cursor() as cursor:
            cursor.execute(f"GRANT SELECT ON {_BUDGET_TABLE} TO {_RLS_PROBE_ROLE}")
        return _RLS_PROBE_ROLE

    def _row_visible_count_as(self, role_or_none, tenant_id, table, row_id):
        """The 1.12 probe — wrapped in an EXPLICIT transaction: the
        TransactionTestCase connection runs in autocommit, where a
        ``set_config(..., is_local=true)`` dies with its own implicit
        commit (the template's TestCase has a wrapping atomic; this
        suite does not — the probe would read the session default and
        see nothing). BEGIN/ROLLBACK reverts the ROLE + GUC atomically."""
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("BEGIN")
            try:
                if role_or_none:
                    cursor.execute(f"SET ROLE {role_or_none}")
                cursor.execute(
                    "SELECT set_config('app.current_tenant_id', %s, false)",
                    [str(tenant_id)] if tenant_id is not None else [None],
                )
                cursor.execute(f"SELECT count(*) FROM {table} WHERE id = %s", [row_id])
                count = cursor.fetchone()[0]
                return count
            finally:
                cursor.execute("ROLLBACK")

    def _admin_alias_count(self, table, row_id, tenant_id):
        """The estate summary's own path: the admin alias with a tenant
        GUC set on that connection — BYPASSRLS must show the row. The
        same explicit-transaction discipline as the probe (the alias
        connection is autocommit too)."""
        conn = connections["admin"]
        with conn.cursor() as cursor:
            cursor.execute("BEGIN")
            try:
                cursor.execute(
                    "SELECT set_config('app.current_tenant_id', %s, false)",
                    [str(tenant_id)],
                )
                cursor.execute(f"SELECT count(*) FROM {table} WHERE id = %s", [row_id])
                count = cursor.fetchone()[0]
                return count
            finally:
                cursor.execute("ROLLBACK")

    def test_the_workspace_table_filters_on_the_tenant_path_and_bypasses_on_the_admin_path(self):
        probe = self._probe_role()
        # TENANT path — the probe role (NOBYPASSRLS) sees only the
        # owning tenant's row under the tenant GUC; a foreign tenant
        # sees ZERO (the 1.2 runtime-filtering proof).
        assert (
            self._row_visible_count_as(probe, self.tenant_a.id, _WORKSPACE_TABLE, self.ws_a.id) == 1
        )
        assert (
            self._row_visible_count_as(probe, self.tenant_b.id, _WORKSPACE_TABLE, self.ws_a.id) == 0
        ), "the tenant path enforces: tenant B's GUC never sees tenant A's workspace"
        assert (
            self._row_visible_count_as(probe, self.tenant_a.id, _WORKSPACE_TABLE, self.ws_b.id) == 0
        )
        # ADMIN path — the estate summary's alias sees the row under
        # ANY tenant GUC (BYPASSRLS — the cross-tenant read the summary
        # derives from).
        assert self._admin_alias_count(_WORKSPACE_TABLE, self.ws_a.id, self.tenant_a.id) == 1
        assert self._admin_alias_count(_WORKSPACE_TABLE, self.ws_a.id, self.tenant_b.id) == 1, (
            "the admin alias bypasses RLS: tenant B's GUC must not hide "
            "tenant A's workspace on the summary's read path"
        )

    def test_the_budget_table_filters_on_the_tenant_path_and_bypasses_on_the_admin_path(self):
        probe = self._probe_role()
        assert (
            self._row_visible_count_as(probe, self.tenant_a.id, _BUDGET_TABLE, self.budget_a.id)
            == 1
        )
        assert (
            self._row_visible_count_as(probe, self.tenant_b.id, _BUDGET_TABLE, self.budget_a.id)
            == 0
        ), "the tenant path enforces on the budget table too"
        assert self._admin_alias_count(_BUDGET_TABLE, self.budget_a.id, self.tenant_b.id) == 1, (
            "the admin alias sees every tenant's budget row — the "
            "summary's budget figures rest on this bypass"
        )

    def test_the_estate_summary_reflects_the_admin_path_at_runtime(self):
        from hub.apps.databricks_admin.account_estate import estate_summary

        # A tenant GUC set on the ADMIN connection must not filter the
        # summary — the derived rows come from the bypassed read. The
        # explicit transaction keeps the session GUC alive across the
        # service's own admin-alias queries (the autocommit discipline).
        conn = connections["admin"]
        with conn.cursor() as cursor:
            cursor.execute("BEGIN")
            try:
                cursor.execute(
                    "SELECT set_config('app.current_tenant_id', %s, false)",
                    [str(self.tenant_a.id)],
                )
                rows = {row["tenant_id"]: row for row in estate_summary()}
            finally:
                cursor.execute("ROLLBACK")

        assert str(self.tenant_a.id) in rows
        assert str(self.tenant_b.id) in rows, (
            "the summary is cross-tenant BY CONSTRUCTION — tenant A's GUC "
            "on the admin connection never narrows it"
        )
