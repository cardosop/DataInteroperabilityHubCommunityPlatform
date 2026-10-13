"""P7 (openspec add-databricks-cost-guardrails task 7.6, design D5) — the
U9 budget-page summary.

``budget_status`` renders the tenant's budget rows with the rolling-hour
consumed figure — the SAME window read the enforcement uses, with the
ledger fallback on a cache outage (the enforcement's degradation
discipline — a Redis hiccup never empties the page) — plus the
per-warehouse breakdown from the ledger (the window's source of truth).
The progress fields are raw (a ratio above 1.0 renders — the page
clamps the bar visually; the numbers never lie).
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)

WINDOW_SECONDS: int = 3600


def _ledger_breakdown(tenant_id: str, warehouse_id: str | None) -> list[dict]:
    """The rolling-hour ledger sums per warehouse (the unattributed
    rows — warehouse NULL — render as the null-warehouse entry)."""
    from django.db.models import Sum
    from django.utils import timezone

    from hub.apps.databricks_admin.models import DatabricksCostLedger

    cutoff = timezone.now() - timezone.timedelta(seconds=WINDOW_SECONDS)
    rows = DatabricksCostLedger.objects.filter(tenant_id=tenant_id, recorded_at__gte=cutoff)
    if warehouse_id:
        # The scope is the Databricks-SIDE string id — the ledger's FK
        # is the mirror row's UUID PK (the enforcement's join discipline).
        rows = rows.filter(warehouse__warehouse_id=warehouse_id)
    sums = (
        rows.values("warehouse__warehouse_id", "warehouse__name")
        .annotate(total=Sum("units"))
        .order_by("-total")
    )
    return [
        {
            "warehouse_id": row["warehouse__warehouse_id"],
            "warehouse_name": row["warehouse__name"],
            "units": str(row["total"]),
        }
        for row in sums
    ]


def budget_status(tenant, *, redis_client=None) -> list[dict]:
    """The budget rows for the tenant — window-consumed (ledger
    fallback on a cache outage) + the per-warehouse breakdown."""
    import redis as redis_mod

    from hub.apps.databricks_admin.budget_enforce import _ledger_fallback
    from hub.apps.databricks_admin.budget_window import window_sum
    from hub.apps.databricks_admin.models import DatabricksCostBudget

    budgets = list(
        DatabricksCostBudget.objects.filter(tenant_id=tenant.id)
        .select_related("warehouse")
        .order_by("warehouse_id")
    )

    client = redis_client
    if client is None:
        from hub.apps.core.redis_pools import get_redis_cache_pool

        client = redis_mod.Redis(connection_pool=get_redis_cache_pool())

    rows: list[dict] = []
    for budget in budgets:
        scope = budget.warehouse.warehouse_id if budget.warehouse else None
        try:
            consumed = window_sum(client, str(tenant.id), warehouse_id=scope)
        except (redis_mod.RedisError, ConnectionError, OSError):
            logger.warning(
                "budget_page_window_unavailable",
                tenant_id=str(tenant.id),
                warehouse_id=scope,
            )
            consumed = _ledger_fallback(str(tenant.id), scope)

        units = budget.budget_units_per_hour
        ratio = float(consumed / units) if units is not None else None
        if ratio is not None:
            # The page read refreshes the SAME window-metric gauge the
            # enforcement stamps (dashboards + alerts feed it).
            from hub.apps.databricks_admin.metrics import record_budget_consumed_ratio

            record_budget_consumed_ratio(
                tenant_id=str(tenant.id),
                scope=scope or "tenant",
                ratio=ratio,
            )
        rows.append(
            {
                "id": str(budget.id),
                "warehouse_id": scope,
                "warehouse_name": budget.warehouse.name if budget.warehouse else None,
                "budget_units_per_hour": str(units) if units is not None else None,
                "enforcement_mode": budget.enforcement_mode,
                "consumed": str(consumed),
                "ratio": ratio,
                "percent": round(ratio * 100, 1) if ratio is not None else None,
                "window_seconds": WINDOW_SECONDS,
                "breakdown": _ledger_breakdown(str(tenant.id), scope),
            }
        )
    return rows
