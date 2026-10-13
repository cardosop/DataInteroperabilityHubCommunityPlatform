"""P8 (openspec add-databricks-account-plane task 8.4, design D6) — the
cross-tenant estate summary.

A read-only, DERIVED aggregate of every tenant's Databricks estate —
workspace counts by state and cost-budget figures — read over the admin
alias (BYPASSRLS, the sanctioned cross-tenant path: a platform-admin
request carries no tenant GUC, so every row is cross-tenant by
construction). Derived per request — no cached rows that could drift.
The RBAC gate lives on the view surface (PLATFORM_ADMIN only); this
module is pure aggregation.
"""

from __future__ import annotations

from decimal import Decimal


def estate_summary() -> list[dict]:
    """One row per tenant that owns any estate (workspaces or budgets),
    ordered by tenant name. Every read rides ``using("admin")``."""
    from django.db.models import Count

    from hub.apps.databricks_admin.models import (
        DatabricksCostBudget,
        DatabricksCostBudgetEnforcementMode,
        DatabricksWorkspace,
    )
    from hub.apps.tenants.models import Tenant

    workspace_rows = (
        DatabricksWorkspace.objects.using("admin")
        .values("tenant_id", "status")
        .annotate(count_of=Count("id"))
        .order_by()
    )
    workspace_counts: dict[str, int] = {}
    workspace_states: dict[str, dict[str, int]] = {}
    for row in workspace_rows:
        tid = str(row["tenant_id"])
        workspace_counts[tid] = workspace_counts.get(tid, 0) + row["count_of"]
        workspace_states.setdefault(tid, {})[row["status"]] = row["count_of"]

    budget_rows = (
        DatabricksCostBudget.objects.using("admin")
        .values("tenant_id", "enforcement_mode", "budget_units_per_hour")
        .order_by()
    )
    budgets: dict[str, dict] = {}
    for row in budget_rows:
        entry = budgets.setdefault(
            str(row["tenant_id"]),
            {
                "budget_count": 0,
                "budgeted_units_total": Decimal("0"),
                "has_units": False,
                "block_budgets": 0,
                "alert_budgets": 0,
            },
        )
        entry["budget_count"] += 1
        if row["budget_units_per_hour"] is not None:
            entry["has_units"] = True
            entry["budgeted_units_total"] += row["budget_units_per_hour"]
        if row["enforcement_mode"] == DatabricksCostBudgetEnforcementMode.BLOCK:
            entry["block_budgets"] += 1
        elif row["enforcement_mode"] == DatabricksCostBudgetEnforcementMode.ALERT:
            entry["alert_budgets"] += 1

    ids = set(workspace_counts) | set(budgets)
    names = {
        str(tid): (name, slug)
        for tid, name, slug in Tenant.objects.using("admin")
        .filter(id__in=ids)
        .values_list("id", "name", "slug")
    }

    rows: list[dict] = []
    for tid in ids:
        entry = budgets.get(tid, {})
        name, slug = names.get(tid, (None, None))
        rows.append(
            {
                "tenant_id": tid,
                "tenant_name": name,
                "tenant_slug": slug,
                "workspace_count": workspace_counts.get(tid, 0),
                "workspaces_by_state": workspace_states.get(tid, {}),
                "budget_count": entry.get("budget_count", 0),
                "budgeted_units_total": (
                    str(entry["budgeted_units_total"]) if entry.get("has_units") else None
                ),
                "block_budgets": entry.get("block_budgets", 0),
                "alert_budgets": entry.get("alert_budgets", 0),
            }
        )
    rows.sort(key=lambda row: (row["tenant_name"] or "", row["tenant_id"]))
    return rows
