"""
Phase 275.DoD.3 — Tenant warehouse connectivity flags.

Master gate: warehouse_connectivity_enabled (default False).
Per-warehouse sub-flags: snowflake, bigquery, databricks, athena
(all default False — no surprise enable, canary rollout per D275.30).

NOTE: the database-level column creation is owned by the idempotent
safety migration ``0072_ensure_warehouse_flags_columns`` (ALTER TABLE
... ADD COLUMN IF NOT EXISTS), which is ordered BEFORE this migration
in the graph. To keep a clean cold-apply (fresh DB / CI) — where the
columns already exist by the time this runs — the AddField operations
here are state-only via ``SeparateDatabaseAndState``; they update
Django's model state without re-issuing the (non-idempotent) DDL.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0068_phase_274_marketplace_compliance_gate"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            # Columns are created at the DB level by
            # 0072_ensure_warehouse_flags_columns (idempotent, runs first).
            database_operations=[],
            state_operations=[
                migrations.AddField(
                    model_name="tenant",
                    name="warehouse_connectivity_enabled",
                    field=models.BooleanField(
                        default=False,
                        help_text="Phase 275 — master gate for all warehouse connectivity features.",
                    ),
                ),
                migrations.AddField(
                    model_name="tenant",
                    name="warehouse_snowflake_enabled",
                    field=models.BooleanField(
                        default=False,
                        help_text="Phase 275 — enable Snowflake warehouse connector.",
                    ),
                ),
                migrations.AddField(
                    model_name="tenant",
                    name="warehouse_bigquery_enabled",
                    field=models.BooleanField(
                        default=False,
                        help_text="Phase 275 — enable BigQuery warehouse connector.",
                    ),
                ),
                migrations.AddField(
                    model_name="tenant",
                    name="warehouse_databricks_enabled",
                    field=models.BooleanField(
                        default=False,
                        help_text="Phase 275 — enable Databricks warehouse connector.",
                    ),
                ),
                migrations.AddField(
                    model_name="tenant",
                    name="warehouse_athena_enabled",
                    field=models.BooleanField(
                        default=False,
                        help_text="Phase 275 — enable Athena warehouse connector.",
                    ),
                ),
            ],
        ),
    ]
