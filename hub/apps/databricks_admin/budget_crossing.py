"""P7 (openspec add-databricks-cost-guardrails task 7.6, design D5) — the
``databricks.budget.exceeded`` webhook, ONCE per budget crossing.

The enforcement decision (``budget_enforce.enforce_budget``) is the
crossing observation point: on a BLOCK or ALERT decision (the window
consumed the budget) the observation fires the webhook through the
PRODUCTION ``WebhookDeliveryService`` — but ONLY once per crossing. A
Redis-crossing sentinel per window scope dedupes re-crossings inside the
window, and a drop below 90% of the budget re-arms it (the sentinel
also expires with the window TTL, so a stale crossing can never
suppress a later one).

Failure discipline (the same best-effort contract the enforcement
already carries):

- a Redis outage during the sentinel read fails CLOSED to no emission —
  without the sentinel the once-per-crossing guarantee cannot hold;
- a delivery failure never raises and never changes the enforcement
  decision (the decision is computed and returned BEFORE the
  observation runs).

The webhook data carries ids + numbers + the classified code only — no
secrets.
"""

from __future__ import annotations

from decimal import Decimal

import structlog

from hub.apps.webhooks.models import WebhookEventType

logger = structlog.get_logger(__name__)

EVENT_TYPE: str = str(WebhookEventType.DATABRICKS_BUDGET_EXCEEDED)
RESOURCE_TYPE: str = "DATABRICKS_COST_BUDGET"
WINDOW_SECONDS: int = 3600
REARM_RATIO: Decimal = Decimal("0.90")


def crossing_key(tenant_id: str, warehouse_id: str | None = None) -> str:
    """The once-per-crossing sentinel key, scoped to the WINDOW the
    decision read (the tenant-wide window, or a warehouse-scoped one)."""
    key = f"databricks_budget_crossed_{tenant_id}"
    if warehouse_id:
        key = f"{key}_{warehouse_id}"
    return key


def _record_crossing_metric(*, tenant_id: str, warehouse_id: str | None) -> None:
    """Increment the crossings counter when the webhook fires (the
    dashboards' spike view). Best-effort — never raises."""
    try:
        from hub.apps.databricks_admin.metrics import record_budget_crossing

        record_budget_crossing(tenant_id=tenant_id, scope=warehouse_id or "tenant")
    except Exception:
        return


def _fire_webhook(
    *,
    tenant_id: str,
    warehouse_id: str | None,
    budget_id: str,
    consumed: Decimal,
    budget: Decimal,
    mode: str,
    code: str | None,
) -> None:
    """Fan the crossing out to the tenant's subscribed webhooks
    (best-effort — a delivery failure never reaches the caller)."""
    from hub.apps.webhooks.service import WebhookDeliveryService

    WebhookDeliveryService.trigger_webhook(
        tenant_id=tenant_id,
        event_type=EVENT_TYPE,
        resource_type=RESOURCE_TYPE,
        resource_id=budget_id,
        event_data={
            "budget_id": budget_id,
            "tenant_id": tenant_id,
            "warehouse_id": warehouse_id,
            "consumed": str(consumed),
            "budget": str(budget),
            "mode": mode,
            "code": code,
            "window_seconds": WINDOW_SECONDS,
        },
    )


def observe_crossing(
    *,
    tenant_id: str,
    warehouse_id: str | None,
    decision,
    budget_id: str,
    redis_client,
) -> bool:
    """Observe one enforcement decision for a budget crossing.

    Returns True when the webhook fired on THIS observation. Never
    raises: a sentinel outage skips the emission (fail-closed — no
    dedupe sentinel means no once-per-crossing guarantee), and a
    delivery failure is logged and swallowed. The caller's decision is
    untouched by design — run this AFTER the decision is final.
    """
    import redis as redis_mod

    key = crossing_key(tenant_id, warehouse_id)
    try:
        crossed = redis_client.get(key)
    except (redis_mod.RedisError, ConnectionError, OSError):
        logger.warning(
            "budget_crossing_sentinel_unavailable",
            tenant_id=tenant_id,
            warehouse_id=warehouse_id,
        )
        return False

    if decision.mode in ("block", "alert"):
        # The window crossed the budget. A second crossing inside the
        # window (sentinel present) does NOT re-fire.
        if crossed is None:
            try:
                redis_client.set(key, "1", ex=WINDOW_SECONDS)
            except (redis_mod.RedisError, ConnectionError, OSError):
                # Without the sentinel the once-per-crossing guarantee
                # cannot hold — skip the emission.
                logger.warning(
                    "budget_crossing_sentinel_set_failed",
                    tenant_id=tenant_id,
                    warehouse_id=warehouse_id,
                )
                return False
            try:
                _fire_webhook(
                    tenant_id=tenant_id,
                    warehouse_id=warehouse_id,
                    budget_id=budget_id,
                    consumed=decision.consumed,
                    budget=decision.budget or Decimal("0"),
                    mode=decision.mode,
                    code=decision.code,
                )
            except Exception:
                logger.warning(
                    "databricks_budget_exceeded_webhook_failed",
                    tenant_id=tenant_id,
                    warehouse_id=warehouse_id,
                    budget_id=budget_id,
                )
                return False
            _record_crossing_metric(tenant_id=tenant_id, warehouse_id=warehouse_id)
            return True
        return False

    # Under budget: a drop below 90% re-arms the sentinel so the NEXT
    # crossing fires again.
    if (
        crossed is not None
        and decision.budget is not None
        and decision.consumed < decision.budget * REARM_RATIO
    ):
        try:
            redis_client.delete(key)
        except (redis_mod.RedisError, ConnectionError, OSError):
            logger.warning(
                "budget_crossing_sentinel_rearm_failed",
                tenant_id=tenant_id,
                warehouse_id=warehouse_id,
            )
    return False
