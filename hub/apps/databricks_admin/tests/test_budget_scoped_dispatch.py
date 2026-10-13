"""P7 (openspec add-databricks-cost-guardrails task 7.8) — the
warehouse-SCOPED enforcement dispatch pins (the 7.4 review's gap #1: the
string-column warehouse scoping carried no pin; the regression class the
fix addressed is now pinned).

The caller's ``warehouse_id`` is the Databricks-SIDE string id; the
budget's FK is the mirror row's UUID PK. The enforcement must scope
through the mirror's ``warehouse_id`` column — never a direct FK lookup
(which would raise "not a valid UUID" on every scoped dispatch).

NO MOCKS: real Postgres rows (tenant/warehouse mirror/scoped + tenant-wide
budgets), REAL Redis (db 13).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from hub.apps.databricks_admin.models import (
    DatabricksCostBudget,
    DatabricksCostBudgetEnforcementMode,
)
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

pytestmark = pytest.mark.django_db(transaction=True)


from hub.apps.databricks_admin.tests._fixtures import redis_13_client

redis_13 = pytest.fixture(autouse=True)(redis_13_client)


def _mk_tenant():
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"scoped-{uid}",
        slug=f"scoped-{uid}",
        status=TenantStatus.ACTIVE,
        kyc_status=KYCStatus.UNVERIFIED,
    )
    ensure_tenant_has_active_subscription(tenant)
    return tenant


def _mk_warehouse(workspace):
    from hub.apps.databricks_admin.models import DatabricksSqlWarehouse

    return DatabricksSqlWarehouse.objects.create(
        workspace=workspace,
        warehouse_id=f"wh-{uuid.uuid4().hex[:8]}",
        name="analytics",
        state="RUNNING",
        serverless=True,
    )


def _mk_workspace(tenant):
    from hub.apps.databricks_admin.models import (
        DatabricksCloud,
        DatabricksWorkspace,
        DatabricksWorkspaceStatus,
    )

    return DatabricksWorkspace.objects.bulk_create(
        [
            DatabricksWorkspace(
                tenant=tenant,
                name=f"ws-{uuid.uuid4().hex[:8]}",
                host="dbc-fixture.cloud.databricks.com",
                cloud=DatabricksCloud.AWS,
                region="us-east-1",
                status=DatabricksWorkspaceStatus.ACTIVE,
            )
        ]
    )[0]


class TestWarehouseScopedDispatch:
    def test_a_scoped_dispatch_uses_the_mirrors_string_column(self, redis_13):
        from hub.apps.databricks_admin.budget_enforce import enforce_budget
        from hub.apps.databricks_admin.budget_window import record_units

        tenant = _mk_tenant()
        workspace = _mk_workspace(tenant)
        warehouse = _mk_warehouse(workspace)
        # A tenant-wide budget that would BLOCK at 10 — and a SCOPED
        # budget that blocks at 2. The scoped dispatch must consult the
        # SCOPED row through the mirror's string warehouse_id column.
        DatabricksCostBudget.objects.create(
            tenant=tenant,
            budget_units_per_hour=Decimal("10"),
            enforcement_mode=DatabricksCostBudgetEnforcementMode.BLOCK,
        )
        DatabricksCostBudget.objects.create(
            tenant=tenant,
            warehouse=warehouse,
            budget_units_per_hour=Decimal("2"),
            enforcement_mode=DatabricksCostBudgetEnforcementMode.BLOCK,
        )
        record_units(
            redis_13,
            str(tenant.id),
            warehouse_id=warehouse.warehouse_id,
            units=Decimal("2"),
        )

        decision = enforce_budget(
            str(tenant.id), warehouse_id=warehouse.warehouse_id, redis_client=redis_13
        )

        assert decision.mode == "block", (
            "the scoped budget row decides the scoped dispatch (via the "
            "mirror's string column — never a UUID lookup on the string id)"
        )
        assert decision.budget == Decimal("2"), "the SCOPED row's budget, not the tenant-wide 10"
        assert decision.code == "WAREHOUSE_COST_BUDGET_EXCEEDED"

    def test_a_scoped_dispatch_falls_back_to_the_tenant_wide_row(self, redis_13):
        from hub.apps.databricks_admin.budget_enforce import enforce_budget
        from hub.apps.databricks_admin.budget_window import record_units

        tenant = _mk_tenant()
        workspace = _mk_workspace(tenant)
        warehouse = _mk_warehouse(workspace)
        DatabricksCostBudget.objects.create(
            tenant=tenant,
            budget_units_per_hour=Decimal("3"),
            enforcement_mode=DatabricksCostBudgetEnforcementMode.BLOCK,
        )
        record_units(
            redis_13,
            str(tenant.id),
            warehouse_id=warehouse.warehouse_id,
            units=Decimal("3"),
        )

        decision = enforce_budget(
            str(tenant.id), warehouse_id=warehouse.warehouse_id, redis_client=redis_13
        )

        assert decision.mode == "block", (
            "no scoped row → the tenant-wide budget governs the scoped dispatch"
        )
        assert decision.budget == Decimal("3")

    def test_the_scoped_window_never_leaks_into_the_tenant_window(self, redis_13):
        from hub.apps.databricks_admin.budget_enforce import enforce_budget
        from hub.apps.databricks_admin.budget_window import record_units

        tenant = _mk_tenant()
        workspace = _mk_workspace(tenant)
        warehouse = _mk_warehouse(workspace)
        DatabricksCostBudget.objects.create(
            tenant=tenant,
            budget_units_per_hour=Decimal("3"),
            enforcement_mode=DatabricksCostBudgetEnforcementMode.BLOCK,
        )
        # The warehouse-scoped window holds 3 units — the TENANT-wide
        # dispatch must NOT see them.
        record_units(
            redis_13,
            str(tenant.id),
            warehouse_id=warehouse.warehouse_id,
            units=Decimal("3"),
        )

        decision = enforce_budget(str(tenant.id), redis_client=redis_13)

        assert decision.mode == "allow", (
            "the scoped window never counts against the tenant-wide budget"
        )
        assert decision.consumed == Decimal("0.000000")
