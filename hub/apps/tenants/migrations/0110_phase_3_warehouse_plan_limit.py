"""Phase 3.4 — seed ``max_databricks_warehouses`` into existing TenantPlan rows.

The Python model's ``KNOWN_LIMIT_KEYS`` already lists the new key
(it's a frozenset literal, not a DB column). What this migration does
is BACKFILL each pre-existing ``TenantPlan.limits_json`` so the
``databricks.warehouse.create`` chain's quota step resolves a cap for
plans created before the key shipped (the 0061 convention):

* FREE-tier plans cap at 2 SQL warehouses — a trial tenant can stand
  up a small warehouse pair but a fleet needs an upgrade.
* PRO-tier plans cap at 10 — an order of magnitude above FREE,
  matching the existing PRO-cap shape on the other counters.
* ENTERPRISE-tier plans are uncapped (``null``) — ENTERPRISE
  customers buy platform support, not per-warehouse seats; the
  tier-gated size allowlist (3.4) is the ENTERPRISE control surface.

A plan whose ``limits_json`` already carries the key is LEFT ALONE
(forward-compatible re-deploy; an operator-seeded custom cap — e.g. a
bespoke plan with a 500 cap — is never overwritten). New keys are
added with the tier-mapped default; the reverse migration removes the
key from every plan (best-effort cleanup — no harm leaving the key,
but the reverse is pristine for symmetry).

Idempotent — re-running the migration is a no-op because the
"already present" branch short-circuits.
"""
from django.db import migrations


LIMIT_KEY = "max_databricks_warehouses"
TIER_DEFAULTS = {
    "FREE": 2,
    "PRO": 10,
    "ENTERPRISE": None,  # null = unlimited per ``PlanLimitService.check_limit``
}


def _backfill_warehouse_caps(apps, schema_editor):
    TenantPlan = apps.get_model("tenants", "TenantPlan")
    for plan in TenantPlan.objects.all():
        limits = dict(plan.limits_json or {})
        if LIMIT_KEY in limits:
            # Forward-compatible: do NOT overwrite an explicit value.
            continue
        # Map tier → default; unknown tiers (custom plans) get the
        # FREE default as the safer fail-closed baseline.
        limits[LIMIT_KEY] = TIER_DEFAULTS.get(plan.tier, TIER_DEFAULTS["FREE"])
        plan.limits_json = limits
        plan.save(update_fields=["limits_json", "updated_at"])


def _strip_warehouse_caps(apps, schema_editor):
    """Reverse migration — remove the new key from every plan's limits_json.

    Best-effort symmetric undo: an operator running ``manage.py
    migrate tenants 0109`` to revert this phase gets a clean slate.
    Plans whose ``limits_json`` lacked the key in the first place
    are untouched.
    """
    TenantPlan = apps.get_model("tenants", "TenantPlan")
    for plan in TenantPlan.objects.all():
        limits = dict(plan.limits_json or {})
        if LIMIT_KEY not in limits:
            continue
        del limits[LIMIT_KEY]
        plan.limits_json = limits
        plan.save(update_fields=["limits_json", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0109_tenant_databricks_uc_destructive_ddl_enabled"),
    ]

    operations = [
        migrations.RunPython(_backfill_warehouse_caps, _strip_warehouse_caps),
    ]
