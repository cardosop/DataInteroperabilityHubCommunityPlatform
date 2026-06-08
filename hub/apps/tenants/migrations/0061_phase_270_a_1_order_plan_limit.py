"""Phase 270.A.1 — seed ``max_marketplace_orders_per_month`` into existing TenantPlan rows.

The Python model's ``KNOWN_LIMIT_KEYS`` already lists the new key
(it's a frozenset literal, not a DB column). What this migration does
is BACKFILL each pre-existing ``TenantPlan.limits_json`` so:

* FREE-tier plans cap at 10 marketplace orders / month — the
  trial-credit allowance, sized so a sole-trader trialling a few
  data feeds stays within budget but a high-volume buyer needs to
  upgrade.
* PRO-tier plans cap at 100 marketplace orders / month — order of
  magnitude above FREE; matches the existing PRO-cap shape on
  other monthly counters.
* ENTERPRISE-tier plans are uncapped (``null``) — ENTERPRISE
  customers buy support-revenue with the platform, not retail
  data; capping them would just generate sales escalations.

A plan whose ``limits_json`` already carries the key is LEFT
ALONE (forward-compatible re-deploy). New keys are added with the
tier-mapped default; the reverse migration removes the key from
every plan (best-effort cleanup — there's no harm to leaving the
key behind, but we keep the reverse pristine for symmetry).

Idempotent — re-running the migration is a no-op because the
"already present" branch short-circuits.
"""
from django.db import migrations


LIMIT_KEY = "max_marketplace_orders_per_month"
TIER_DEFAULTS = {
    "FREE": 10,
    "PRO": 100,
    "ENTERPRISE": None,  # null = unlimited per ``PlanLimitService.check_limit``
}


def _backfill_orders_cap(apps, schema_editor):
    TenantPlan = apps.get_model("tenants", "TenantPlan")
    for plan in TenantPlan.objects.all():
        limits = dict(plan.limits_json or {})
        if LIMIT_KEY in limits:
            # Forward-compatible: do NOT overwrite an explicit value.
            # An operator who pre-seeded a custom cap (e.g. a bespoke
            # enterprise plan with a 500 cap) keeps it.
            continue
        # Map tier → default; unknown tiers (custom plans) get the
        # FREE default as the safer fail-closed baseline.
        limits[LIMIT_KEY] = TIER_DEFAULTS.get(plan.tier, TIER_DEFAULTS["FREE"])
        plan.limits_json = limits
        plan.save(update_fields=["limits_json", "updated_at"])


def _strip_orders_cap(apps, schema_editor):
    """Reverse migration — remove the new key from every plan's limits_json.

    Best-effort symmetric undo: an operator running ``manage.py
    migrate tenants 0060`` to revert this phase gets a clean slate.
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
        ("tenants", "0059_phase_235_4_impersonation"),
    ]

    operations = [
        migrations.RunPython(_backfill_orders_cap, reverse_code=_strip_orders_cap),
    ]
