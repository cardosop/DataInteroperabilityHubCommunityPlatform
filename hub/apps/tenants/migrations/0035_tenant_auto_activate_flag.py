# Phase 250.2.A.1 (closes Gap 2) — auto-activate-on-gate-pass flag.
#
# Adds ``asset_auto_activate_on_gate_pass: BooleanField(default=True)``
# to ``Tenant``. Governs whether the asset-creation workflow auto-
# activates an Asset (DRAFT → ACTIVE) when all gates pass.
#
# Default-True semantic for BOTH new and existing tenants:
#
# * The platform Python-level default for ``auto_activate`` was flipped
#   to True in Phase 250.1.A.3 / D250.2; backfilling False on existing
#   tenants would silently regress current customer behaviour for
#   tenants already running on the new default.
# * Customers who want DRAFT-first review can opt out by flipping the
#   flag to False explicitly.
#
# Migration safety:
# * Single ``AddField`` with a constant default — PostgreSQL 11+
#   rewrites zero rows on the schema change.
# * No ``RunPython`` backfill needed: the AddField default fills the
#   column with True for both new INSERTs and existing rows.
# * Reverse is a clean ``RemoveField`` — the rollback drops the column
#   entirely without leaving orphan data.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0034_tenant_fail_closed_flag"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="asset_auto_activate_on_gate_pass",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Phase 250.2.A.1 — when True (default), the asset-"
                    "creation workflow auto-activates an Asset "
                    "(DRAFT → ACTIVE) once all gates pass. When False, "
                    "the workflow leaves the Asset in DRAFT regardless "
                    "of the per-call auto_activate argument; a per-"
                    "tenant DRAFT-first review queue. The effective "
                    "decision is "
                    "``per_call_auto_activate AND tenant_flag``."
                ),
            ),
        ),
    ]
