"""
Phase 250.6.D.1 (closes G2-1 / P2-1) — Tenant onboarding-completion timestamp.

Two-step migration:

  1. ``AddField`` ``onboarding_completed_at`` (DateTimeField, null=True,
     db_index=True). The default is NULL — every existing row picks
     up NULL on the ALTER TABLE.

  2. Data migration backfill: for every existing tenant that ALREADY
     satisfies the three onboarding signals (a TENANT_ADMIN role
     assigned, ``kyc_status != UNVERIFIED``, an active Subscription),
     set ``onboarding_completed_at`` to ``now()``. Without the
     backfill, every existing tenant would suddenly look "onboarding
     incomplete" to the capabilities endpoint — which is wrong:
     they've been creating assets for months. Setting the timestamp
     to ``now()`` is semantically "this tenant had completed
     onboarding by THIS time" — accurate even if we can't reconstruct
     the actual historical completion moment.

The backfill runs via the FROZEN-state ORM (``apps.get_model(...)``)
so it survives any future model edits (e.g. removing fields). It
deliberately uses raw SQL via the ORM's ``filter()`` rather than
calling the live ``hub.apps.tenants.onboarding.evaluate_*`` helpers —
data migrations must be self-contained from the live code so they
work on any future schema state.
"""
from django.db import migrations, models
from django.utils import timezone


_BILLING_ACTIVE_STATES = ("ACTIVE", "TRIAL", "PAST_DUE")


def _backfill_onboarding_complete(apps, schema_editor):
    """Stamp ``now()`` on every tenant that already satisfies all 3 signals.

    Runs against the FROZEN models (``apps.get_model``) so the
    migration is hermetic from the live code. The signal definition
    is inlined here on purpose — see the module docstring.
    """
    Tenant = apps.get_model("tenants", "Tenant")
    UserRole = apps.get_model("users", "UserRole")
    # Phase 313 — core-only has no billing app; the backfill only matters for
    # PRE-EXISTING databases (fresh installs have no rows to backfill), so
    # an absent billing app/table is a legitimate no-op.
    if "billing" not in apps.all_models:
        return
    try:
        Subscription = apps.get_model("billing", "Subscription")
    except LookupError:
        return

    now = timezone.now()

    # Iterate tenant-by-tenant rather than a single bulk UPDATE
    # JOIN: the predicate spans three tables, and pre-existing rows
    # are bounded (small number of staging tenants today; production
    # cardinality is also low at this phase). The chunked approach
    # keeps the migration debuggable and avoids cross-table UPDATE
    # SQL that varies per backend.
    tenants_with_admin = (
        UserRole.objects.filter(role__name="TENANT_ADMIN")
        .values_list("tenant_id", flat=True)
        .distinct()
    )
    try:
        tenants_with_billing = (
            Subscription.objects.filter(status__in=_BILLING_ACTIVE_STATES)
            .values_list("tenant_id", flat=True)
            .distinct()
        )
    except Exception:
        # Billing table not yet migrated (fresh full installs reorder
        # without the dependency) — nothing to backfill from.
        return

    manager = getattr(Tenant, "all_objects", None) or Tenant._default_manager

    eligible = (
        manager.exclude(kyc_status="UNVERIFIED")
        .filter(pk__in=tenants_with_admin)
        .filter(pk__in=tenants_with_billing)
        .filter(onboarding_completed_at__isnull=True)
    )

    # Use ``update`` rather than per-row save: the field is purely
    # a stamp; no signals need to fire (the backfill is the
    # historical reconstruction, not a live state change).
    eligible.update(onboarding_completed_at=now)


def _reverse_backfill(apps, schema_editor):
    """Reverse: clear the timestamp.

    Reversing the migration drops the field via ``RemoveField`` (the
    framework auto-generates the inverse) so this reverse is a NO-OP
    — kept here only for symmetry / tooling that runs reverse
    migrations explicitly. The actual column drop is the framework's
    job.
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0038_tenant_asset_creation_enabled"),
        # Latest users migration to guarantee ``UserRole.tenant`` is
        # NOT NULL (set by users.0009) — the backfill query below
        # filters by ``role__name`` + ``tenant_id``, so we need the
        # FK column live.
        ("users", "0016_passwordhistory"),
        # Phase 313 — the billing dependency is REMOVED: core-only installs
        # have no billing app, and the backfill self-guards against an absent
        # billing table (it only matters for pre-existing databases).
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="onboarding_completed_at",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text=(
                    "Phase 250.6.D.1 — timestamp the tenant FIRST "
                    "satisfied all three onboarding signals (TENANT_ADMIN "
                    "role granted, KYC submitted, active Subscription). "
                    "NULL = onboarding not yet complete. One-way ratchet: "
                    "never cleared once set."
                ),
                null=True,
            ),
        ),
        migrations.RunPython(
            _backfill_onboarding_complete,
            reverse_code=_reverse_backfill,
        ),
    ]
