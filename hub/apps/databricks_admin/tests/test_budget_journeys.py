"""P7 (openspec add-databricks-cost-guardrails task 7.7) — the
JOURNEY-DB-015 / UC-DB-015 backend journey pins: the platform admin sets
a Databricks budget (BLOCK or ALERT overage behavior), usage flows into
the ledger from the hourly sync, the dispatch enforces the rolling-window
budget (429 vs proceed), and the window's recovery resumes execution.

NO MOCKS: real Postgres rows (tenant/budget/ledger/workspace/connection/
asset), REAL Redis (the shared test cache db 13, flushed per test), the
REAL DRF live-query view over real HTTP; the sanctioned seam is the
view's `_do_query` symbol (a recorder proving zero warehouse work on the
BLOCK path). The budget rows are set through the model — the API write
surface ships with the 7.6 budget page.
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
        name=f"j015-{uid}",
        slug=f"j015-{uid}",
        status=TenantStatus.ACTIVE,
        kyc_status=KYCStatus.UNVERIFIED,
    )
    ensure_tenant_has_active_subscription(tenant)
    return tenant


def _mk_budget(tenant, *, units, mode):
    return DatabricksCostBudget.objects.create(
        tenant=tenant,
        budget_units_per_hour=units,
        enforcement_mode=mode,
    )


def _mk_live_query_asset(tenant):
    from hub.apps.assets.models import Asset, DataStrategy
    from hub.apps.warehouses.models import WarehouseConnection, WarehouseType

    connection = WarehouseConnection.objects.create(
        tenant=tenant,
        name=f"conn-{uuid.uuid4().hex[:8]}",
        warehouse_type=WarehouseType.DATABRICKS,
        config={"host": "adb-fixture.cloud.databricks.com", "pat_token": "dapi-x"},
    )
    return Asset.objects.create(
        tenant=tenant,
        name="live",
        data_strategy=DataStrategy.LIVE_QUERY,
        warehouse_connection=connection,
    )


def _api_client(tenant):
    user = User.objects.create_user(
        email=f"j015-{uuid.uuid4().hex[:8]}@meshant.test",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class TestJOURNEYDB015SetDatabricksBudget:
    """The journey the prose doc pins (docs/mvpdocs/use-cases/UC-DB-015.md
    "Phase P7 Test"): the platform admin sets the budget, the dispatch
    enforces it, the window recovers, and the sync ledger feeds it."""

    @pytest.mark.journey("JOURNEY-DB-015")
    @pytest.mark.uc("UC-DB-015")
    def test_block_vs_alert(self, redis_13):
        from hub.apps.databricks_admin.budget_window import record_units

        tenant = _mk_tenant()
        budget = _mk_budget(
            tenant, units=Decimal("5"), mode=DatabricksCostBudgetEnforcementMode.BLOCK
        )
        asset = _mk_live_query_asset(tenant)
        client = _api_client(tenant)
        record_units(redis_13, str(tenant.id), units=Decimal("5"))

        # BLOCK: the dispatch fails closed with the 429 + code and ZERO
        # warehouse work.
        with mock.patch(
            "hub.apps.warehouses.views.LiveQueryViewSet._do_query",
            recorder := mock.Mock(),
        ):
            blocked = client.get(f"/api/v1/warehouses/query/?asset_id={asset.id}&limit=10")
        assert blocked.status_code == 429
        assert blocked.json()["code"] == "WAREHOUSE_COST_BUDGET_EXCEEDED"
        recorder.assert_not_called()

        from hub.apps.audit.models import AuditEvent

        assert AuditEvent.objects.filter(
            tenant=tenant, action="WAREHOUSE_COST_BUDGET_EXCEEDED"
        ).exists(), "the BLOCK carries the audit row"

        # ALERT: the same budget row switched to ALERT lets the query
        # through and fires the near-exceeded alert.
        budget.enforcement_mode = DatabricksCostBudgetEnforcementMode.ALERT
        budget.save(update_fields=["enforcement_mode"])

        from rest_framework.response import Response

        with mock.patch(
            "hub.apps.warehouses.views.LiveQueryViewSet._do_query",
            return_value=Response({"rows": []}),
        ) as do_query:
            allowed = client.get(f"/api/v1/warehouses/query/?asset_id={asset.id}&limit=10")
        assert allowed.status_code == 200, "ALERT mode lets the query through — no 429"
        do_query.assert_called_once()
        assert AuditEvent.objects.filter(
            tenant=tenant, action="WAREHOUSE_COST_BUDGET_NEAR_EXCEEDED"
        ).exists(), "the ALERT fires the near-exceeded audit row"

    @pytest.mark.journey("JOURNEY-DB-015")
    @pytest.mark.uc("UC-DB-015")
    def test_the_rolling_window_recovers_execution(self, redis_13):
        from hub.apps.databricks_admin.budget_window import record_units, window_sum

        tenant = _mk_tenant()
        _mk_budget(tenant, units=Decimal("5"), mode=DatabricksCostBudgetEnforcementMode.BLOCK)
        asset = _mk_live_query_asset(tenant)
        client = _api_client(tenant)

        # Exhaust the budget an hour ago — the rolling window drains and
        # execution resumes automatically (the journey's "Recover" step).
        record_units(redis_13, str(tenant.id), units=Decimal("5"), now=1_700_000_000)
        assert window_sum(redis_13, str(tenant.id), now=1_800_000_000) == Decimal("0.000000")

        from rest_framework.response import Response

        with mock.patch(
            "hub.apps.warehouses.views.LiveQueryViewSet._do_query",
            return_value=Response({"rows": []}),
        ) as do_query:
            resp = client.get(f"/api/v1/warehouses/query/?asset_id={asset.id}&limit=10")
        assert resp.status_code == 200, "the drained window resumes execution"
        do_query.assert_called_once()

    @pytest.mark.journey("JOURNEY-DB-015")
    @pytest.mark.uc("UC-DB-015")
    def test_the_sync_ledger_feeds_the_budget_window(self, redis_13):
        from hub.apps.databricks_admin.budget_window import window_sum
        from hub.apps.databricks_admin.cost_sync import _ingest_rows
        from hub.apps.databricks_admin.models import (
            DatabricksCloud,
            DatabricksWorkspace,
            DatabricksWorkspaceStatus,
        )

        tenant = _mk_tenant()
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

        ingested = _ingest_rows(
            workspace,
            [
                ["meta-1", "2.5", "DBU", "2026-09-01T10:00:00Z"],
                ["meta-2", "1.5", "DBU", "2026-09-01T10:05:00Z"],
            ],
        )

        assert ingested == 2
        assert window_sum(redis_13, str(tenant.id)) == Decimal("4.000000"), (
            "the hourly sync's ledger rows feed the budget window"
        )
