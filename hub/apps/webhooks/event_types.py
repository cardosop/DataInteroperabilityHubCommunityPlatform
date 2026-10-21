"""
285.13.9.5 — Canonical webhook event-type constants.

Every outbound webhook payload MUST reference a type string from this
module so subscribers can route on stable, documented event type names.
"""

from __future__ import annotations

# ── 285.13.9.5 — Tenant plan lifecycle webhook events ──────────────────

#: Fired when a tenant successfully upgrades their subscription plan.
#: Payload carries: tenant_id, old_plan_slug, new_plan_slug,
#: old_plan_tier, new_plan_tier, subscription_id, timestamp.
TENANT_PLAN_UPGRADED: str = "tenant.plan.upgraded"

#: Fired when a tenant successfully downgrades their subscription plan.
#: Payload carries: tenant_id, old_plan_slug, new_plan_slug,
#: old_plan_tier, new_plan_tier, subscription_id, timestamp.
TENANT_PLAN_DOWNGRADED: str = "tenant.plan.downgraded"

#: Fired ONCE per Databricks rolling-window budget crossing (openspec
#: add-databricks-cost-guardrails task 7.6) — the enforcement
#: observation's Redis-crossing sentinel dedupes re-crossings inside the
#: window and re-arms on a drop below 90% of the budget. Payload carries:
#: budget_id, tenant_id, warehouse_id, consumed, budget, mode, code,
#: window_seconds (ids + numbers only — no secrets).
DATABRICKS_BUDGET_EXCEEDED: str = "databricks.budget.exceeded"

# ── Canonical list for registration ────────────────────────────────────

WEBHOOK_EVENT_TYPES: tuple[str, ...] = (
    TENANT_PLAN_UPGRADED,
    TENANT_PLAN_DOWNGRADED,
    DATABRICKS_BUDGET_EXCEEDED,
)
