"""Phase 235.3.1 — ``Tenant.scheduled_for_deletion_at`` + ``Tenant.legal_hold``.

Two new fields land on ``Tenant`` for the soft-delete + 90-day grace +
hard-delete-sweep contract:

* ``scheduled_for_deletion_at`` — stamped when the PLATFORM_ADMIN
  ``DELETE /api/v1/admin/tenants/{id}/`` endpoint runs. The daily
  ``tenant_hard_delete_sweep`` cron hard-deletes rows where this is
  older than 90 days AND ``legal_hold=False`` AND no open
  DSAR-restriction.
* ``legal_hold`` — when True, blocks the soft-delete endpoint
  (HTTP 422 LEGAL_HOLD_ACTIVE) AND the hard-delete sweep (the sweep
  skips the tenant + logs ``legal_hold_active`` in its summary).

Both fields default to NULL / False so the migration is a non-blocking
``ALTER TABLE ADD COLUMN`` with no rewrite.

No paired RLS migration: the ``tenants`` table is the row-level
isolation BOUNDARY itself and is NOT RLS-protected (verified by
grepping for ``ENABLE ROW LEVEL SECURITY`` across
``hub/apps/tenants/migrations/`` — no hits).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0056_feature_flag_flip_approval"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="scheduled_for_deletion_at",
            field=models.DateTimeField(
                blank=True,
                help_text=(
                    "Phase 235.3 — UTC timestamp when an admin invoked "
                    "``DELETE /api/v1/admin/tenants/{id}/``. The daily "
                    "``tenant_hard_delete_sweep`` cron hard-deletes rows where "
                    "this is older than 90 days AND ``legal_hold=False`` AND "
                    "no open DSAR-restriction. NULL on live tenants."
                ),
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="tenant",
            name="legal_hold",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Phase 235.3 — when True, blocks both the PLATFORM_ADMIN "
                    "soft-delete endpoint (HTTP 422 LEGAL_HOLD_ACTIVE) AND the "
                    "daily hard-delete sweep (the sweep skips the tenant and "
                    "logs ``legal_hold_active`` in its summary). Flipped on by "
                    "legal / compliance ops when discovery is in scope; "
                    "flipped off only after the hold is lifted."
                ),
            ),
        ),
    ]
