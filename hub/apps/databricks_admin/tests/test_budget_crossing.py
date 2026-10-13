"""Phase 7 (openspec add-databricks-cost-guardrails task 7.6) — the
``databricks.budget.exceeded`` webhook (design D5, the spec's "Budget
Exceeded Webhook and Budget UX" scenarios).

The crossing observation rides the REAL enforcement decision
(``budget_enforce.enforce_budget``): when the rolling window crosses the
budget (BLOCK or ALERT) the webhook fires ONCE per crossing — the
Redis-crossing sentinel dedupes re-crossings inside the window, and a
drop below 90% of the budget re-arms it. The emission fans out through
the PRODUCTION ``WebhookDeliveryService`` to the tenant's subscribed
webhooks; a failure in ANY part of the observation never changes the
enforcement decision and never raises.

NO MOCKS: real Postgres rows (tenant/budget/webhook-subscription), REAL
Redis (the shared test cache db 13 — flushed per test), and a REAL
local HTTP server receives the delivered payload (the TestWebhookServer
convention); the sanctioned seams are the injectable redis client (a
failing double pins the cache-outage contract — the observation never
raises, never fires without the dedupe sentinel, never changes the
decision) and a refused-connection webhook URL (a REAL delivery failure
— the decision is untouched).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from hub.apps.databricks_admin.models import (
    DatabricksCostBudget,
    DatabricksCostBudgetEnforcementMode,
    DatabricksCostLedger,
)
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User

pytestmark = pytest.mark.django_db(transaction=True)


from hub.apps.databricks_admin.tests._fixtures import redis_13_client

redis_13 = pytest.fixture(autouse=True)(redis_13_client)


class _DownRedis:
    """The injectable-seam failure double: a cache whose store is
    unreachable — the crossing observation must skip the emission (no
    sentinel → no once-per-crossing guarantee) WITHOUT raising and
    WITHOUT changing the decision."""

    def zadd(self, *_args, **_kwargs):
        raise ConnectionError("redis unreachable")

    def zremrangebyscore(self, *_args, **_kwargs):
        raise ConnectionError("redis unreachable")

    def zrangebyscore(self, *_args, **_kwargs):
        raise ConnectionError("redis unreachable")

    def expire(self, *_args, **_kwargs):
        raise ConnectionError("redis unreachable")

    def get(self, *_args, **_kwargs):
        raise ConnectionError("redis unreachable")

    def set(self, *_args, **_kwargs):
        raise ConnectionError("redis unreachable")

    def delete(self, *_args, **_kwargs):
        raise ConnectionError("redis unreachable")


def _mk_tenant():
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"crossing-{uid}",
        slug=f"crossing-{uid}",
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


def _mk_user(tenant):
    return User.objects.create_user(
        email=f"crossing-{uuid.uuid4().hex[:8]}@meshant.test",
        password="testpass123",
        tenant=tenant,
    )


def _enforce(tenant, *, warehouse_id=None, redis_client):
    from hub.apps.databricks_admin.budget_enforce import enforce_budget

    return enforce_budget(str(tenant.id), warehouse_id=warehouse_id, redis_client=redis_client)


def _deliveries(tenant):
    from hub.apps.webhooks.models import WebhookDelivery

    return list(
        WebhookDelivery.objects.filter(
            webhook__tenant=tenant, event_type="databricks.budget.exceeded"
        ).order_by("created_at")
    )


def _subscribe(tenant, url, event_types=("databricks.budget.exceeded",), **overrides):
    from hub.apps.webhooks.models import Webhook, WebhookStatus

    return Webhook.objects.create(
        tenant=tenant,
        name=f"budget-wh-{uuid.uuid4().hex[:8]}",
        url=url,
        secret="test-secret-key-for-budget-webhook-signing",
        event_types=list(event_types),
        status=WebhookStatus.ACTIVE,
        created_by=_mk_user(tenant),
        **overrides,
    )


# ── The once-per-crossing contract ────────────────────────────────────


class TestBudgetCrossingWebhook:
    def test_the_budget_exceeded_event_type_is_registered(self):
        from hub.apps.webhooks.event_types import WEBHOOK_EVENT_TYPES
        from hub.apps.webhooks.models import WebhookEventType

        assert WebhookEventType.DATABRICKS_BUDGET_EXCEEDED.value == "databricks.budget.exceeded"
        assert "databricks.budget.exceeded" in WEBHOOK_EVENT_TYPES

    def test_the_webhook_fires_once_per_crossing(self, redis_13):
        from hub.apps.databricks_admin.budget_window import record_units
        from hub.apps.webhooks.tests.test_odps_webhook_integration import TestWebhookServer

        tenant = _mk_tenant()
        budget = _mk_budget(tenant, units=Decimal("100"))
        with TestWebhookServer(response_status=200) as server:
            _subscribe(tenant, server.get_url())
            record_units(redis_13, str(tenant.id), units=Decimal("101"))

            decision = _enforce(tenant, redis_client=redis_13)
            assert decision.mode == "block"

            # A second crossing inside the same window does not re-fire.
            _enforce(tenant, redis_client=redis_13)
            _enforce(tenant, redis_client=redis_13)

        deliveries = _deliveries(tenant)
        assert len(deliveries) == 1, "the webhook fires EXACTLY once per crossing"
        delivery = deliveries[0]
        from hub.apps.webhooks.models import DeliveryStatus

        assert delivery.status == DeliveryStatus.SUCCESS
        payload = delivery.payload or {}
        assert payload.get("event_type") == "databricks.budget.exceeded"
        assert payload.get("resource_type") == "DATABRICKS_COST_BUDGET"
        assert payload.get("resource_id") == str(budget.id)
        data = payload.get("data") or {}
        assert data.get("budget_id") == str(budget.id)
        assert data.get("consumed") == "101"
        assert data.get("budget") == "100.000000"
        assert data.get("mode") == "block"
        assert data.get("code") == "WAREHOUSE_COST_BUDGET_EXCEEDED"

    def test_dropping_below_90_percent_rearms_the_sentinel(self, redis_13):
        from hub.apps.databricks_admin.budget_window import record_units
        from hub.apps.webhooks.tests.test_odps_webhook_integration import TestWebhookServer

        tenant = _mk_tenant()
        _mk_budget(tenant, units=Decimal("100"))
        with TestWebhookServer(response_status=200) as server:
            _subscribe(tenant, server.get_url())
            record_units(redis_13, str(tenant.id), units=Decimal("101"))
            _enforce(tenant, redis_client=redis_13)  # first crossing — fires

            # The window falls back below 90% — the sentinel re-arms.
            redis_13.flushdb()
            record_units(redis_13, str(tenant.id), units=Decimal("50"))
            decision = _enforce(tenant, redis_client=redis_13)
            assert decision.mode == "allow"
            assert len(_deliveries(tenant)) == 1

            # A NEW crossing fires again.
            redis_13.flushdb()
            record_units(redis_13, str(tenant.id), units=Decimal("101"))
            _enforce(tenant, redis_client=redis_13)

        assert len(_deliveries(tenant)) == 2, "a drop below 90% re-arms — the next crossing fires"

    def test_alert_mode_crossing_fires_once_too(self, redis_13):
        from hub.apps.databricks_admin.budget_window import record_units
        from hub.apps.webhooks.tests.test_odps_webhook_integration import TestWebhookServer

        tenant = _mk_tenant()
        _mk_budget(tenant, units=Decimal("100"), mode=DatabricksCostBudgetEnforcementMode.ALERT)
        with TestWebhookServer(response_status=200) as server:
            _subscribe(tenant, server.get_url())
            record_units(redis_13, str(tenant.id), units=Decimal("100"))

            decision = _enforce(tenant, redis_client=redis_13)
            assert decision.mode == "alert"
            _enforce(tenant, redis_client=redis_13)

        deliveries = _deliveries(tenant)
        assert len(deliveries) == 1
        assert (deliveries[0].payload or {}).get("data", {}).get("code") == (
            "WAREHOUSE_COST_BUDGET_NEAR_EXCEEDED"
        )

    def test_a_warehouse_scoped_crossing_has_its_own_sentinel(self, redis_13):
        from hub.apps.databricks_admin.budget_window import record_units
        from hub.apps.databricks_admin.models import (
            DatabricksCloud,
            DatabricksSqlWarehouse,
            DatabricksWorkspace,
            DatabricksWorkspaceStatus,
        )
        from hub.apps.databricks_admin.tests._fixtures import REAL_HOST, require_dns
        from hub.apps.webhooks.tests.test_odps_webhook_integration import TestWebhookServer

        require_dns()
        tenant = _mk_tenant()
        workspace = DatabricksWorkspace.objects.create(
            tenant=tenant,
            name=f"crossing-ws-{uuid.uuid4().hex[:8]}",
            host=REAL_HOST,
            cloud=DatabricksCloud.AWS,
            region="us-east-1",
            status=DatabricksWorkspaceStatus.ACTIVE,
        )
        warehouse = DatabricksSqlWarehouse.objects.create(
            workspace=workspace,
            warehouse_id="wh-crossing",
            name="analytics",
            state="RUNNING",
            serverless=True,
        )
        scoped = _mk_budget(tenant, units=Decimal("10"), warehouse=warehouse)
        _mk_budget(tenant, units=Decimal("100"))
        with TestWebhookServer(response_status=200) as server:
            _subscribe(tenant, server.get_url())
            record_units(redis_13, str(tenant.id), warehouse_id="wh-crossing", units=Decimal("11"))
            _enforce(tenant, warehouse_id="wh-crossing", redis_client=redis_13)
            _enforce(tenant, warehouse_id="wh-crossing", redis_client=redis_13)

            # The tenant-wide window crosses independently — its own
            # sentinel fires even though the warehouse scope already did.
            record_units(redis_13, str(tenant.id), units=Decimal("101"))
            _enforce(tenant, redis_client=redis_13)

        deliveries = _deliveries(tenant)
        assert len(deliveries) == 2
        scoped_data = deliveries[0].payload["data"]
        assert scoped_data["warehouse_id"] == "wh-crossing"
        assert scoped_data["budget_id"] == str(scoped.id)
        assert deliveries[1].payload["data"]["warehouse_id"] is None, (
            "the tenant-wide crossing carries the tenant-wide scope"
        )

    def test_an_unsubscribed_tenant_gets_zero_deliveries(self, redis_13):
        from hub.apps.databricks_admin.budget_window import record_units

        tenant = _mk_tenant()
        _mk_budget(tenant, units=Decimal("100"))
        record_units(redis_13, str(tenant.id), units=Decimal("101"))

        decision = _enforce(tenant, redis_client=redis_13)

        assert decision.mode == "block"
        assert _deliveries(tenant) == []

    def test_the_webhook_does_not_fire_for_other_event_subscriptions(self, redis_13):
        from hub.apps.databricks_admin.budget_window import record_units
        from hub.apps.webhooks.tests.test_odps_webhook_integration import TestWebhookServer

        tenant = _mk_tenant()
        _mk_budget(tenant, units=Decimal("100"))
        with TestWebhookServer(response_status=200) as server:
            _subscribe(tenant, server.get_url(), event_types=("asset.created",))
            record_units(redis_13, str(tenant.id), units=Decimal("101"))
            _enforce(tenant, redis_client=redis_13)

        assert _deliveries(tenant) == []

    def test_the_payload_carries_ids_and_numbers_only(self, redis_13):
        from hub.apps.databricks_admin.budget_window import record_units
        from hub.apps.webhooks.tests.test_odps_webhook_integration import TestWebhookServer

        tenant = _mk_tenant()
        budget = _mk_budget(tenant, units=Decimal("100"))
        with TestWebhookServer(response_status=200) as server:
            _subscribe(tenant, server.get_url())
            record_units(redis_13, str(tenant.id), units=Decimal("101"))
            _enforce(tenant, redis_client=redis_13)

        deliveries = _deliveries(tenant)
        assert len(deliveries) == 1
        data = deliveries[0].payload["data"]
        assert set(data) == {
            "budget_id",
            "tenant_id",
            "warehouse_id",
            "consumed",
            "budget",
            "mode",
            "code",
            "window_seconds",
        }, "no secrets — ids + numbers + the classified code only"
        assert data["tenant_id"] == str(tenant.id)
        assert data["warehouse_id"] is None
        assert data["window_seconds"] == 3600
        assert data["budget_id"] == str(budget.id)

    def test_the_crossing_increments_the_observability_counter(self, redis_13, monkeypatch):
        from hub.apps.databricks_admin import metrics
        from hub.apps.databricks_admin.budget_window import record_units

        tenant = _mk_tenant()
        _mk_budget(tenant, units=Decimal("100"))
        recorder_calls = []
        monkeypatch.setattr(
            metrics,
            "record_budget_crossing",
            lambda **kwargs: recorder_calls.append(kwargs),
        )
        record_units(redis_13, str(tenant.id), units=Decimal("101"))
        _enforce(tenant, redis_client=redis_13)

        assert recorder_calls == [{"tenant_id": str(tenant.id), "scope": "tenant"}], (
            "the crossing counter fires with the webhook — the dashboards' "
            "spike view feeds the same observation"
        )

    def test_the_enforcement_stamps_the_ratio_gauge(self, redis_13, monkeypatch):
        from hub.apps.databricks_admin import metrics
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
        _enforce(tenant, redis_client=redis_13)

        assert gauge_calls == [{"tenant_id": str(tenant.id), "scope": "tenant", "ratio": 0.6}], (
            "dashboards + alerts feed the SAME window read the enforcement computed"
        )

    def test_the_sentinel_carries_the_window_ttl(self, redis_13):
        from hub.apps.databricks_admin.budget_crossing import crossing_key
        from hub.apps.databricks_admin.budget_window import record_units

        tenant = _mk_tenant()
        _mk_budget(tenant, units=Decimal("100"))
        record_units(redis_13, str(tenant.id), units=Decimal("101"))
        _enforce(tenant, redis_client=redis_13)

        assert redis_13.get(crossing_key(str(tenant.id))) == "1"
        ttl = redis_13.ttl(crossing_key(str(tenant.id)))
        assert 0 < ttl <= 3600, "the sentinel is window-bounded — it expires with the hour"

    def test_a_redis_outage_never_fires_and_never_changes_the_decision(self):
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

        decision = _enforce(tenant, redis_client=_DownRedis())

        assert decision.mode == "alert", (
            "a cache outage degrades to the alert path — never a false BLOCK"
        )
        assert _deliveries(tenant) == [], (
            "without the dedupe sentinel the once-per-crossing guarantee cannot "
            "hold — the observation fails closed to NO emission"
        )

    def test_a_delivery_failure_never_changes_the_decision(self, redis_13):
        from hub.apps.databricks_admin.budget_window import record_units
        from hub.apps.webhooks.tests.test_odps_webhook_integration import TestWebhookServer

        tenant = _mk_tenant()
        _mk_budget(tenant, units=Decimal("100"))
        server = TestWebhookServer(response_status=200)
        server.start()
        # Bound the REAL retry pipeline: one attempt, one-second interval —
        # the dead target exhausts the policy in ~1s (the default 5-attempt
        # [1,5,30,300,1800] policy would burn minutes per test) and lands
        # on the pipeline's real terminal state.
        webhook = _subscribe(tenant, server.get_url(), max_retries=1, retry_intervals=[1])
        server.stop()  # the delivery target is GONE — a real failure

        record_units(redis_13, str(tenant.id), units=Decimal("101"))
        decision = _enforce(tenant, redis_client=redis_13)

        assert decision.mode == "block", "a failed delivery never changes the decision"
        from hub.apps.webhooks.models import DeliveryStatus

        deliveries = _deliveries(tenant)
        assert len(deliveries) == 1
        assert deliveries[0].status == DeliveryStatus.DEAD_LETTER, (
            "the delivery attempt happened for real and failed for real — "
            "an exhausted connection-error delivery dead-letters (the "
            "pipeline terminal), which is exactly the outcome this test pins"
        )
        assert webhook.status == "ACTIVE"
