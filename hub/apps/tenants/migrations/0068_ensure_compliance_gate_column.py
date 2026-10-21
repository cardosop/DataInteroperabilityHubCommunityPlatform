"""
Phase 272.2 safety migration — idempotently ensure
``tenants.access_request_compliance_gate_enabled`` exists.

Migration 0067 may be recorded as applied in ``django_migrations``
without the actual column (e.g. after a partial database restore).
This migration adds the column only when it is missing, making it
safe to run in any state.

NOTE: This file shares the 0068 prefix with
``0068_phase_274_marketplace_compliance_gate``. The merge migration
``0069_merge_compliance_gates`` resolves the fork.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0067_phase_272_compliance_gate"),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS "
                "access_request_compliance_gate_enabled boolean DEFAULT false"
            ),
            reverse_sql=(
                "ALTER TABLE tenants DROP COLUMN IF EXISTS "
                "access_request_compliance_gate_enabled"
            ),
        ),
    ]
