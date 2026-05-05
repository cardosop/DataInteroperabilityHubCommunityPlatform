# Phase 250.1.A.8 — fail-closed-at-intake flags.
#
# Adds two BooleanField columns to ``Tenant``:
#
# * ``compliance_fail_closed_enabled``: BooleanField(default=True) —
#   the column-level default governs NEW INSERTs (a tenant created
#   after this migration runs picks up the production-safe TRUE).
#   For EXISTING rows we explicitly UPDATE to FALSE so a customer
#   already running on the legacy draft-then-scan path doesn't have
#   their workflow re-sequenced overnight without ops sign-off.
#
# * ``allow_intake_on_compliance_degraded``: BooleanField(default=False)
#   — opt-in per tenant; default False for both new and existing
#   tenants so a misconfigured circuit breaker can't accidentally
#   bypass compliance scanning.
#
# Migration safety:
# - Both AddField operations supply a constant default, so PostgreSQL
#   11+ rewrites no rows on the schema change.
# - The existing-row backfill is a single UPDATE statement scoped by
#   the primary key range; on Aurora/RDS this still locks each row
#   briefly, but the operation is idempotent and bounded.
# - The reverse_code is a no-op so a roll-back leaves the columns
#   in place and lets the RemoveField operations drop them cleanly.
#
# This file deliberately predates the workflow re-sequence in
# 250.1.A.3 so the column exists everywhere the workflow may read
# from it before the workflow code lands.
from django.db import migrations, models


def _backfill_existing_rows(apps, schema_editor):
    """Set ``compliance_fail_closed_enabled=False`` for pre-existing tenants.

    This is the "default TRUE on new, FALSE on existing" semantic the
    spec calls for: the column-level default kicks in for new INSERTs,
    while this RunPython hook backfills rows that existed at the
    moment the migration ran.
    """
    Tenant = apps.get_model("tenants", "Tenant")
    # Use the broadest historical manager available. On this model
    # ``default_manager_name`` points to ``all_objects`` in modern
    # code, and historical state may not expose ``objects``.
    manager = getattr(Tenant, "all_objects", None) or Tenant._default_manager
    manager.update(compliance_fail_closed_enabled=False)


def _reverse_backfill(apps, schema_editor):
    """No-op reverse — RemoveField below drops the column entirely."""
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0033_tenant_data_quality_flags"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="compliance_fail_closed_enabled",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Phase 250.1.A.8 — when True, a compliance "
                    "FAIL/UNKNOWN at intake refuses to persist the "
                    "Asset row (fail-closed). Default True for NEW "
                    "tenants (production-safe); existing tenants are "
                    "backfilled to False by migration 0034 to "
                    "preserve legacy draft-then-scan behaviour until "
                    "ops opts them in."
                ),
            ),
        ),
        migrations.AddField(
            model_name="tenant",
            name="allow_intake_on_compliance_degraded",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Phase 250.1.A.8 / D250.9 — when True, allow "
                    "asset intake while the compliance-service "
                    "circuit breaker is OPEN (the scan is queued for "
                    "later). Default False — intake blocks with 503 "
                    "+ Retry-After until the breaker recovers."
                ),
            ),
        ),
        migrations.RunPython(
            _backfill_existing_rows,
            reverse_code=_reverse_backfill,
        ),
    ]
