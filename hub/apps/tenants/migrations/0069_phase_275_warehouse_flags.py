"""
Phase 275.DoD.3 — Tenant warehouse connectivity flags.

Master gate: warehouse_connectivity_enabled (default False).
Per-warehouse sub-flags: snowflake, bigquery, databricks, athena
(all default False — no surprise enable, canary rollout per D275.30).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0068_phase_274_marketplace_compliance_gate"),
    ]

    operations = [
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
    ]
