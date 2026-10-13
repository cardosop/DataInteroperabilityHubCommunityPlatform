"""Phase 7 (openspec add-databricks-cost-guardrails task 7.4) — the
Redis rolling-hour budget window + the enforcement decisions (design D3,
the spec's "Rolling-Window Budget Enforcement" scenarios).

The window is a REAL Redis sorted set per tenant (+ optional warehouse
scope, 3600s TTL); the enforcement reads the REAL budget row and decides
BLOCK (HTTP 429 + audit, zero warehouse work) vs ALERT (the query runs,
the near-exceeded alert fires) vs allow. A cache failure NEVER falsely
blocks — the enforcement degrades to the ledger-read fallback on the
alert path (best-effort, never a movement outage).

NO MOCKS: real Postgres rows (tenant/budget/ledger), REAL Redis (the
shared test cache db 13 — flushed per test), the REAL DRF view over real
HTTP; the sanctioned seams are the injectable redis client (a failing
double pins the cache-outage contract) and the view's `_do_query` symbol
(a recorder proving zero warehouse work on the BLOCK path).
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest import mock

import pytest
from rest_framework.test import APIClient

from hub.apps.databricks_admin.models import (
    DatabricksCostBudget,
    DatabricksCostBudgetEnforcementMode,
    DatabricksCostLedger,
)
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


from hub.apps.databricks_admin.tests._fixtures import redis_13_client

redis_13 = pytest.fixture(autouse=True)(redis_13_client)


def _mk_tenant():
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"budget-{uid}",
        slug=f"budget-{uid}",
        status=TenantStatus.ACTIVE,
        kyc_status=KYCStatus.UNVERIFIED,
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


class _DownRedis:
    """The injectable-seam failure double: a cache whose store is
    unreachable — the enforcement must degrade to the ledger fallback on
    the ALERT path, never a false BLOCK."""

    def zadd(self, *_args, **_kwargs):
        raise ConnectionError("redis unreachable")

    def zremrangebyscore(self, *_args, **_kwargs):
        raise ConnectionError("redis unreachable")

    def zrangebyscore(self, *_args, **_kwargs):
        raise ConnectionError("redis unreachable")

    def expire(self, *_args, **_kwargs):
        raise ConnectionError("redis unreachable")


# ── Window arithmetic ─────────────────────────────────────────────────


class TestBudgetWindowArithmetic:
    def test_recorded_units_sum_in_the_rolling_window(self, redis_13):
        from hub.apps.databricks_admin.budget_window import record_units, window_sum

        tenant = _mk_tenant()
        record_units(redis_13, str(tenant.id), units=Decimal("3"))
        record_units(redis_13, str(tenant.id), units=Decimal("4"))

        assert window_sum(redis_13, str(tenant.id)) == Decimal("7.000000")

    def test_the_window_prunes_entries_older_than_the_hour(self, redis_13):
        from hub.apps.databricks_admin.budget_window import record_units, window_sum

        tenant = _mk_tenant()
        record_units(redis_13, str(tenant.id), units=Decimal("5"), now=1_700_000_000)
        record_units(redis_13, str(tenant.id), units=Decimal("2"), now=1_800_000_000)

        assert window_sum(redis_13, str(tenant.id), now=1_800_000_000) == Decimal("2.000000")

    def test_the_window_key_is_tenant_scoped(self, redis_13):
        from hub.apps.databricks_admin.budget_window import record_units, window_sum

        tenant_a = _mk_tenant()
        tenant_b = _mk_tenant()
        record_units(redis_13, str(tenant_a.id), units=Decimal("9"))

        assert window_sum(redis_13, str(tenant_b.id)) == Decimal("0.000000"), (
            "tenant A's consumption never counts against tenant B (the Phase 273 key discipline)"
        )
        assert window_sum(redis_13, str(tenant_a.id)) == Decimal("9.000000")

    def test_a_warehouse_scoped_window_is_distinct(self, redis_13):
        from hub.apps.databricks_admin.budget_window import record_units, window_sum

        tenant = _mk_tenant()
        warehouse_id = str(uuid.uuid4())
        record_units(redis_13, str(tenant.id), warehouse_id=warehouse_id, units=Decimal("6"))

        assert window_sum(redis_13, str(tenant.id), warehouse_id=warehouse_id) == Decimal(
            "6.000000"
        )
        assert window_sum(redis_13, str(tenant.id)) == Decimal("0.000000"), (
            "the per-warehouse window never leaks into the tenant-wide window"
        )


# ── Enforcement decisions ─────────────────────────────────────────────


class TestBudgetEnforcement:
    def test_block_mode_over_budget_decides_block(self, redis_13):
        from hub.apps.databricks_admin.budget_enforce import enforce_budget
        from hub.apps.databricks_admin.budget_window import record_units

        tenant = _mk_tenant()
        _mk_budget(tenant, units=Decimal("10"), mode=DatabricksCostBudgetEnforcementMode.BLOCK)
        record_units(redis_13, str(tenant.id), units=Decimal("10"))

        decision = enforce_budget(str(tenant.id), redis_client=redis_13)

        assert decision.mode == "block"
        assert decision.code == "WAREHOUSE_COST_BUDGET_EXCEEDED"
        assert decision.consumed == Decimal("10.000000")
        assert decision.budget == Decimal("10")

    def test_alert_mode_over_budget_decides_alert(self, redis_13):
        from hub.apps.databricks_admin.budget_enforce import enforce_budget
        from hub.apps.databricks_admin.budget_window import record_units

        tenant = _mk_tenant()
        _mk_budget(tenant, units=Decimal("10"), mode=DatabricksCostBudgetEnforcementMode.ALERT)
        record_units(redis_13, str(tenant.id), units=Decimal("10"))

        decision = enforce_budget(str(tenant.id), redis_client=redis_13)

        assert decision.mode == "alert"
        assert decision.code == "WAREHOUSE_COST_BUDGET_NEAR_EXCEEDED"

    def test_under_budget_decides_allow(self, redis_13):
        from hub.apps.databricks_admin.budget_enforce import enforce_budget
        from hub.apps.databricks_admin.budget_window import record_units

        tenant = _mk_tenant()
        _mk_budget(tenant, units=Decimal("10"))
        record_units(redis_13, str(tenant.id), units=Decimal("3"))

        decision = enforce_budget(str(tenant.id), redis_client=redis_13)

        assert decision.mode == "allow"
        assert decision.code is None

    def test_no_budget_row_decides_allow(self, redis_13):
        from hub.apps.databricks_admin.budget_enforce import enforce_budget

        tenant = _mk_tenant()
        decision = enforce_budget(str(tenant.id), redis_client=redis_13)
        assert decision.mode == "allow"

    def test_a_cache_outage_never_blocks(self):
        from hub.apps.databricks_admin.budget_enforce import enforce_budget

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

        decision = enforce_budget(str(tenant.id), redis_client=_DownRedis())

        assert decision.mode == "alert", (
            "a cache outage degrades to the alert path — never a false BLOCK, "
            "never a movement outage"
        )
        # The ledger fallback carries the REAL consumed figure.
        assert decision.consumed == Decimal("12.000000")


# ── The dispatch surface ──────────────────────────────────────────────


class TestBudgetDispatchSurface:
    def _mk_live_query_asset(self, tenant):
        from hub.apps.assets.models import Asset, DataStrategy
        from hub.apps.warehouses.models import WarehouseConnection, WarehouseType

        connection = WarehouseConnection.objects.create(
            tenant=tenant,
            name=f"conn-{uuid.uuid4().hex[:8]}",
            warehouse_type=WarehouseType.DATABRICKS,
            config={"host": "adb-fixture.cloud.databricks.com", "pat_token": "dapi-x"},
        )
        asset = Asset.objects.create(
            tenant=tenant,
            name="live",
            data_strategy=DataStrategy.LIVE_QUERY,
            warehouse_connection=connection,
        )
        return asset

    def _client(self, tenant):
        user = User.objects.create_user(
            email=f"bw-{uuid.uuid4().hex[:8]}@meshant.test",
            password="testpass123",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def test_the_view_returns_429_with_the_audit_row_and_zero_queries(self, redis_13):
        from hub.apps.databricks_admin.budget_window import record_units

        tenant = _mk_tenant()
        _mk_budget(tenant, units=Decimal("1"), mode=DatabricksCostBudgetEnforcementMode.BLOCK)
        record_units(redis_13, str(tenant.id), units=Decimal("1"))
        asset = self._mk_live_query_asset(tenant)
        client = self._client(tenant)

        with mock.patch(
            "hub.apps.warehouses.views.LiveQueryViewSet._do_query",
            recorder := mock.Mock(),
        ):
            resp = client.get(f"/api/v1/warehouses/query/?asset_id={asset.id}&limit=10")

        assert resp.status_code == 429
        assert resp.json()["code"] == "WAREHOUSE_COST_BUDGET_EXCEEDED"
        recorder.assert_not_called(), "the BLOCK fails closed BEFORE any warehouse query"

        from hub.apps.audit.models import AuditEvent

        audit_row = AuditEvent.objects.filter(
            tenant=tenant, action="WAREHOUSE_COST_BUDGET_EXCEEDED"
        ).first()
        assert audit_row is not None, "the 429 carries the audit row"

    def test_an_alert_mode_view_proceeds_and_fires_the_alert(self, redis_13):
        from hub.apps.databricks_admin.budget_window import record_units

        tenant = _mk_tenant()
        _mk_budget(tenant, units=Decimal("1"), mode=DatabricksCostBudgetEnforcementMode.ALERT)
        record_units(redis_13, str(tenant.id), units=Decimal("1"))
        asset = self._mk_live_query_asset(tenant)
        client = self._client(tenant)

        from rest_framework.response import Response

        with mock.patch(
            "hub.apps.warehouses.views.LiveQueryViewSet._do_query",
            return_value=Response({"rows": []}),
        ) as do_query:
            resp = client.get(f"/api/v1/warehouses/query/?asset_id={asset.id}&limit=10")

        assert resp.status_code == 200, "ALERT mode lets the query through — no 429"
        do_query.assert_called_once()

        from hub.apps.audit.models import AuditEvent

        assert AuditEvent.objects.filter(
            tenant=tenant, action="WAREHOUSE_COST_BUDGET_NEAR_EXCEEDED"
        ).exists(), "the near-exceeded alert fired"


# ── The sync recording hook ───────────────────────────────────────────


class TestSyncRecordsTheWindow:
    def test_the_sync_ingest_records_the_window(self):
        import redis as redis_mod

        from hub.apps.core.redis_pools import get_redis_cache_pool
        from hub.apps.databricks_admin.budget_window import window_sum
        from hub.apps.databricks_admin.cost_sync import _ingest_rows
        from hub.apps.databricks_admin.models import (
            DatabricksCloud,
            DatabricksWorkspace,
            DatabricksWorkspaceStatus,
        )

        tenant = _mk_tenant()
        # bulk_create skips the save-time SSRF/DNS host guard — the
        # fixture host is never dialed (the 6.6 convention).
        workspace = DatabricksWorkspace.objects.bulk_create(
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
        rows = [
            ["meta-1", "2.5", "DBU", "2026-09-01T10:00:00Z"],
            ["meta-2", "1.5", "DBU", "2026-09-01T10:05:00Z"],
        ]

        ingested = _ingest_rows(workspace, rows)

        assert ingested == 2
        # Read through the SAME canonical pool the sync wrote through
        # (_ingest_rows → get_redis_cache_pool) — a test-local hardcoded
        # endpoint would read a different Redis instance and was the
        # in-container skip/failure root cause.
        assert window_sum(
            redis_mod.Redis(connection_pool=get_redis_cache_pool()),
            str(tenant.id),
        ) == Decimal("4.000000"), (
            "every ledger row lands in the rolling window (the 7.5 per-query "
            "chokepoint joins the same recorder)"
        )
