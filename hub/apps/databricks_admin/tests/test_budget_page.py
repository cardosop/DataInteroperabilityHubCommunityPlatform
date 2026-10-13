"""Phase 7 (openspec add-databricks-cost-guardrails task 7.6) — the U9
budget page API (design D5, the spec's "The budget page shows the
progress bar" scenario).

``GET /api/v1/databricks/budgets/`` renders the tenant's budget rows
with the rolling-hour consumed figure — the SAME window read the
enforcement uses (with the ledger fallback on a cache outage, the
enforcement's degradation discipline) — plus the per-warehouse
breakdown from the ledger.

NO MOCKS: real Postgres rows (tenant/budget/ledger/warehouse mirror),
REAL Redis (the shared test cache db 13 — flushed per test), the REAL
DRF view over real HTTP; the sanctioned seam is the injectable redis
client on the summary service (a failing double pins the ledger
fallback).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from hub.apps.databricks_admin.models import (
    DatabricksCloud,
    DatabricksCostBudget,
    DatabricksCostBudgetEnforcementMode,
    DatabricksCostLedger,
    DatabricksSqlWarehouse,
    DatabricksWorkspace,
    DatabricksWorkspaceStatus,
)
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


from hub.apps.databricks_admin.tests._fixtures import redis_13_client

redis_13 = pytest.fixture(autouse=True)(redis_13_client)


class _DownRedis:
    """The injectable-seam failure double — the summary falls back to
    the REAL ledger aggregate (the enforcement's degradation)."""

    def zadd(self, *_args, **_kwargs):
        raise ConnectionError("redis unreachable")

    def zremrangebyscore(self, *_args, **_kwargs):
        raise ConnectionError("redis unreachable")

    def zrangebyscore(self, *_args, **_kwargs):
        raise ConnectionError("redis unreachable")

    def expire(self, *_args, **_kwargs):
        raise ConnectionError("redis unreachable")


def _mk_tenant(*, control_plane_enabled=True):
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"page-{uid}",
        slug=f"page-{uid}",
        status=TenantStatus.ACTIVE,
        kyc_status=KYCStatus.UNVERIFIED,
        databricks_control_plane_enabled=control_plane_enabled,
    )
    ensure_tenant_has_active_subscription(tenant)
    return tenant


def _mk_budget(
    tenant, *, units=None, mode=DatabricksCostBudgetEnforcementMode.BLOCK, warehouse=None
):
    return DatabricksCostBudget.objects.create(
        tenant=tenant,
        warehouse=warehouse,
        budget_units_per_hour=units,
        enforcement_mode=mode,
    )


def _mk_warehouse(tenant, *, warehouse_id, name):
    from hub.apps.databricks_admin.tests._fixtures import REAL_HOST, require_dns

    require_dns()
    workspace = DatabricksWorkspace.objects.create(
        tenant=tenant,
        name=f"page-ws-{uuid.uuid4().hex[:8]}",
        host=REAL_HOST,
        cloud=DatabricksCloud.AWS,
        region="us-east-1",
        status=DatabricksWorkspaceStatus.ACTIVE,
    )
    return DatabricksSqlWarehouse.objects.create(
        workspace=workspace,
        warehouse_id=warehouse_id,
        name=name,
        state="RUNNING",
        serverless=True,
    )


def _client(tenant):
    user = User.objects.create_user(
        email=f"page-{uuid.uuid4().hex[:8]}@meshant.test",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _get(client):
    return client.get("/api/v1/databricks/budgets/")


def _row(resp):
    assert resp.status_code == 200, resp.content
    results = resp.json()["results"]
    assert len(results) == 1
    return results[0]


class TestBudgetPageAPI:
    def test_the_page_renders_the_60_percent_progress_row(self, redis_13):
        from hub.apps.databricks_admin.budget_window import record_units

        tenant = _mk_tenant()
        budget = _mk_budget(tenant, units=Decimal("100"))
        record_units(redis_13, str(tenant.id), units=Decimal("60"))

        resp = _get(_client(tenant))

        row = _row(resp)
        assert row["id"] == str(budget.id)
        assert row["warehouse_id"] is None
        assert row["warehouse_name"] is None
        assert row["budget_units_per_hour"] == "100.000000"
        assert row["enforcement_mode"] == "BLOCK"
        assert row["consumed"] == "60"
        assert row["ratio"] == 0.6
        assert row["percent"] == 60.0
        assert row["window_seconds"] == 3600

    def test_the_page_renders_the_per_warehouse_breakdown(self):
        tenant = _mk_tenant()
        analytics = _mk_warehouse(tenant, warehouse_id="wh-analytics", name="Analytics")
        bi = _mk_warehouse(tenant, warehouse_id="wh-bi", name="BI")
        _mk_budget(tenant, units=Decimal("100"))
        DatabricksCostLedger.objects.create(
            tenant=tenant,
            workspace=analytics.workspace,
            warehouse=analytics,
            source="query",
            units=Decimal("40"),
            unit_label="DBU",
        )
        DatabricksCostLedger.objects.create(
            tenant=tenant,
            workspace=bi.workspace,
            warehouse=bi,
            source="query",
            units=Decimal("20"),
            unit_label="DBU",
        )
        DatabricksCostLedger.objects.create(
            tenant=tenant,
            workspace=None,
            warehouse=None,
            source="job",
            units=Decimal("7"),
            unit_label="DBU",
        )

        resp = _get(_client(tenant))

        row = _row(resp)
        breakdown = {b["warehouse_id"]: b for b in row["breakdown"]}
        assert breakdown["wh-analytics"]["warehouse_name"] == "Analytics"
        assert breakdown["wh-analytics"]["units"] == "40.000000"
        assert breakdown["wh-bi"]["units"] == "20.000000"
        assert breakdown[None]["units"] == "7.000000", (
            "the unattributed ledger rows render as the null-warehouse entry"
        )

    def test_an_unlimited_budget_renders_without_a_ratio(self, redis_13):
        from hub.apps.databricks_admin.budget_window import record_units

        tenant = _mk_tenant()
        _mk_budget(tenant, units=None)
        record_units(redis_13, str(tenant.id), units=Decimal("12"))

        resp = _get(_client(tenant))

        row = _row(resp)
        assert row["budget_units_per_hour"] is None
        assert row["consumed"] == "12"
        assert row["ratio"] is None
        assert row["percent"] is None

    def test_other_tenants_budgets_never_appear(self):
        tenant = _mk_tenant()
        stranger = _mk_tenant()
        _mk_budget(tenant, units=Decimal("100"))
        _mk_budget(stranger, units=Decimal("500"))

        resp = _get(_client(tenant))

        rows = resp.json()["results"]
        assert [r["budget_units_per_hour"] for r in rows] == ["100.000000"]

    def test_unauthenticated_requests_get_401(self):
        resp = APIClient().get("/api/v1/databricks/budgets/")
        assert resp.status_code == 401

    def test_the_capability_gate_blocks_a_disabled_tenant(self):
        tenant = _mk_tenant(control_plane_enabled=False)
        _mk_budget(tenant, units=Decimal("100"))

        resp = _get(_client(tenant))

        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "DATABRICKS_CONTROL_PLANE_DISABLED"

    def test_a_cache_outage_falls_back_to_the_ledger(self):
        from hub.apps.databricks_admin.budget_ux import budget_status

        tenant = _mk_tenant()
        _mk_budget(tenant, units=Decimal("10"), mode=DatabricksCostBudgetEnforcementMode.BLOCK)
        DatabricksCostLedger.objects.create(
            tenant=tenant,
            workspace=None,
            warehouse=None,
            source="query",
            units=Decimal("12"),
            unit_label="DBU",
        )

        rows = budget_status(tenant, redis_client=_DownRedis())

        assert len(rows) == 1
        row = rows[0]
        assert row["consumed"] == "12.000000", "the ledger fallback carries the REAL figure"
        assert row["ratio"] == 1.2
        assert row["percent"] == 120.0, "over-budget rows report the RAW percentage"

    def test_the_page_read_refreshes_the_ratio_gauge(self, redis_13, monkeypatch):
        from hub.apps.databricks_admin import metrics
        from hub.apps.databricks_admin.budget_ux import budget_status
        from hub.apps.databricks_admin.budget_window import record_units

        tenant = _mk_tenant()
        _mk_budget(tenant, units=Decimal("100"))
        gauge_calls = []
        monkeypatch.setattr(
            metrics,
            "record_budget_consumed_ratio",
            lambda **kwargs: gauge_calls.append(kwargs),
        )
        record_units(redis_13, str(tenant.id), units=Decimal("60"))

        budget_status(tenant, redis_client=redis_13)

        assert gauge_calls == [{"tenant_id": str(tenant.id), "scope": "tenant", "ratio": 0.6}], (
            "the U9 page read refreshes the SAME window metric the dashboards + alerts feed"
        )
