"""P7 (openspec add-databricks-cost-guardrails task 7.4, design D3) — the
budget enforcement decision at the dispatch surface.

The decision reads the REAL budget row (the warehouse-scoped row wins for
a warehouse-scoped check, else the tenant-wide row) and the rolling-hour
window sum. Over budget: BLOCK mode → ``block`` with the
``WAREHOUSE_COST_BUDGET_EXCEEDED`` code (the caller returns HTTP 429 with
the audit row and ZERO warehouse work); ALERT mode → ``alert`` with the
``WAREHOUSE_COST_BUDGET_NEAR_EXCEEDED`` code (the query proceeds, the
alert fires). Under budget (or no budget row / unlimited) → ``allow``.

A cache outage NEVER falsely blocks: the window read is best-effort and a
failure degrades to the ledger-read fallback on the ALERT path — the
movement never loses a query to a Redis hiccup (the spec's
"cache failure never blocks" scenario).
"""

from __future__ import annotations

from decimal import Decimal

import structlog

# W4.6 (oss-release-remediation, G1) — the provider-agnostic decision
# shape lives at the warehouses budget-gate seam; the estate enforcer
# conforms to it (the re-export keeps this module's public surface
# unchanged for the estate's own tests and callers).
from hub.apps.warehouses.budget_gate import BudgetDecision

__all__ = ["BudgetDecision", "enforce_budget"]

logger = structlog.get_logger(__name__)


def _ledger_fallback(tenant_id: str, warehouse_id: str | None) -> Decimal:
    """The REAL ledger aggregate for the rolling hour (the degraded
    read when the window cache is unavailable).

    ``warehouse_id`` is the Databricks-SIDE string id — the ledger's FK
    is the mirror row's UUID PK, so the scope joins through the
    mirror's string column (``warehouse__warehouse_id``)."""
    from django.db.models import Sum
    from django.utils import timezone

    from hub.apps.databricks_admin.models import DatabricksCostLedger

    cutoff = timezone.now() - timezone.timedelta(seconds=3600)
    rows = DatabricksCostLedger.objects.filter(
        tenant_id=tenant_id, recorded_at__gte=cutoff
    )
    if warehouse_id:
        rows = rows.filter(warehouse__warehouse_id=warehouse_id)
    return rows.aggregate(total=Sum("units"))["total"] or Decimal("0")


def _observe_crossing(
    *, tenant_id: str, warehouse_id, decision, budget, redis_client
) -> None:
    """P7 (7.6) — post-decision side effects: the window-metric gauge
    (dashboards + alerts feed the SAME window read) and the crossing
    observation (the ``databricks.budget.exceeded`` webhook, once per
    crossing). The side effects NEVER change the decision — best-effort
    by contract."""
    try:
        from hub.apps.databricks_admin.budget_crossing import observe_crossing
        from hub.apps.databricks_admin.metrics import record_budget_consumed_ratio

        scope = warehouse_id or "tenant"
        if decision.budget is not None:
            record_budget_consumed_ratio(
                tenant_id=tenant_id,
                scope=scope,
                ratio=float(decision.consumed / decision.budget),
            )
        observe_crossing(
            tenant_id=tenant_id,
            warehouse_id=warehouse_id,
            decision=decision,
            budget_id=str(budget.id),
            redis_client=redis_client,
        )
    except Exception:
        logger.warning(
            "budget_crossing_observation_failed",
            tenant_id=tenant_id,
            warehouse_id=warehouse_id,
        )


def enforce_budget(
    tenant_id: str,
    *,
    warehouse_id: str | None = None,
    redis_client=None,
) -> BudgetDecision:
    """Decide BLOCK vs ALERT vs allow for the tenant's (optionally
    warehouse-scoped) dispatch."""
    import redis as redis_mod

    from hub.apps.databricks_admin.budget_window import window_sum
    from hub.apps.databricks_admin.models import (
        DatabricksCostBudget,
        DatabricksCostBudgetEnforcementMode,
    )

    budgets = DatabricksCostBudget.objects.filter(tenant_id=tenant_id)
    if warehouse_id:
        # ``warehouse_id`` is the Databricks-SIDE string id; the budget's
        # FK is the mirror row's UUID PK — scope through the mirror's
        # string column (the direct string lookup would raise
        # "not a valid UUID" on every warehouse-scoped dispatch).
        budget = budgets.filter(warehouse__warehouse_id=warehouse_id).first()
        if budget is None:
            budget = budgets.filter(warehouse__isnull=True).first()
    else:
        budget = budgets.filter(warehouse__isnull=True).first()

    if budget is None or budget.budget_units_per_hour is None:
        return BudgetDecision(mode="allow")

    client = redis_client
    if client is None:
        from hub.apps.core.redis_pools import get_redis_cache_pool

        client = redis_mod.Redis(connection_pool=get_redis_cache_pool())

    try:
        consumed = window_sum(client, tenant_id, warehouse_id=warehouse_id)
    except (redis_mod.RedisError, ConnectionError, OSError):
        # Best-effort degradation: the ledger fallback carries the REAL
        # consumed figure, and the decision is ALERT — a cache outage
        # never falsely BLOCKS the movement.
        logger.warning(
            "budget_window_unavailable",
            tenant_id=tenant_id,
            warehouse_id=warehouse_id,
        )
        consumed = _ledger_fallback(tenant_id, warehouse_id)
        decision = BudgetDecision(
            mode="alert",
            consumed=consumed,
            budget=budget.budget_units_per_hour,
            code="WAREHOUSE_COST_BUDGET_NEAR_EXCEEDED",
            reason="window cache unavailable — ledger fallback on the alert path",
        )
        # The crossing observation runs with the SAME failing client —
        # the sentinel read fails closed to no emission (without the
        # dedupe sentinel the once-per-crossing guarantee cannot hold).
        _observe_crossing(
            tenant_id=tenant_id,
            warehouse_id=warehouse_id,
            decision=decision,
            budget=budget,
            redis_client=client,
        )
        return decision

    if consumed < budget.budget_units_per_hour:
        decision = BudgetDecision(
            mode="allow", consumed=consumed, budget=budget.budget_units_per_hour
        )
    elif budget.enforcement_mode == DatabricksCostBudgetEnforcementMode.BLOCK:
        decision = BudgetDecision(
            mode="block",
            consumed=consumed,
            budget=budget.budget_units_per_hour,
            code="WAREHOUSE_COST_BUDGET_EXCEEDED",
        )
    else:
        decision = BudgetDecision(
            mode="alert",
            consumed=consumed,
            budget=budget.budget_units_per_hour,
            code="WAREHOUSE_COST_BUDGET_NEAR_EXCEEDED",
        )

    _observe_crossing(
        tenant_id=tenant_id,
        warehouse_id=warehouse_id,
        decision=decision,
        budget=budget,
        redis_client=client,
    )
    return decision
