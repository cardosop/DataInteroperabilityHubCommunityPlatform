"""
W2.2 (oss-release-remediation, R2-D2/D3) — backfill_plan_order:
backfill the canonical ``TenantPlan.order`` for pre-existing seeded
rows.

The change-plan downgrade guard compares ``plan.order``
(``new_order < current_order``), but the seeder historically never
populated the field — every seeded plan carries the model default 0,
so the guard can never observe a downgrade.  ``seed_default_plans``
now seeds/repairs the canonical orders (W2.2); this migration
backfills rows created before that fix.

Backfill scope: ONLY canonical slugs whose order is still the stale
default (0).  Custom plan rows and rows where an operator set a
deliberate custom order are left untouched — the UPDATE is keyed on
both the slug and the stale value.  Canonical orders follow the
plan_defaults.py scheme (sandbox=-1, free=0, starter=1, growth=2,
pro=3, scale=4, enterprise=5, ML=10/11/12).

The reverse restores the stale default for the canonical slugs — the
honest inverse of the forward change (custom orders are not
reconstructible, so rows with a custom order stay as-is in BOTH
directions; documented, best-effort reversibility).

Backfill-bypass note (convention 274.16.7): this is a DATA migration
backfilling a denormalised ordering column from a slug mapping — there
is no service-layer write path for historical rows, and the mapping is
the same canonical table the seeder applies at runtime.  No
tenant-scoped data is touched; no chain applies.
"""

from django.db import migrations

_CANONICAL_ORDERS = {
    "sandbox": -1,
    "free": 0,
    "starter": 1,
    "growth": 2,
    "pro": 3,
    "scale": 4,
    "enterprise": 5,
    "ml-starter": 10,
    "ml-professional": 11,
    "ml-enterprise": 12,
}

_FORWARD = "\n".join(
    f"UPDATE tenant_plans SET \"order\" = {order} "
    f"WHERE slug = '{slug}' AND \"order\" = 0;"
    for slug, order in _CANONICAL_ORDERS.items()
)

_REVERSE = "\n".join(
    f"UPDATE tenant_plans SET \"order\" = 0 WHERE slug = '{slug}';"
    for slug in _CANONICAL_ORDERS
)


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0117_remove_tenant_mfa_required"),
    ]

    operations = [
        migrations.RunSQL(sql=_FORWARD, reverse_sql=_REVERSE),
    ]
