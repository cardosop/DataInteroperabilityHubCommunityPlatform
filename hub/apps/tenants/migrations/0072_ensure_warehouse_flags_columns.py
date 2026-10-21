"""
Phase 275 safety migration — idempotently ensure all five
``tenants.warehouse_*`` columns exist.

Migration 0069 adds 5 BooleanFields (warehouse_connectivity_enabled,
warehouse_snowflake_enabled, warehouse_bigquery_enabled,
warehouse_databricks_enabled, warehouse_athena_enabled). It may be
recorded as applied in ``django_migrations`` without the actual
columns (e.g. after a partial database restore). This migration
adds each column only when it is missing, making it safe to run in
any state.
"""
from django.db import migrations

_COLUMNS = [
    "warehouse_connectivity_enabled",
    "warehouse_snowflake_enabled",
    "warehouse_bigquery_enabled",
    "warehouse_databricks_enabled",
    "warehouse_athena_enabled",
]

_ADD_SQL = ";\n".join(
    f"ALTER TABLE tenants ADD COLUMN IF NOT EXISTS {col} boolean NOT NULL DEFAULT false"
    for col in _COLUMNS
)

_DROP_SQL = ";\n".join(
    f"ALTER TABLE tenants DROP COLUMN IF EXISTS {col}"
    for col in _COLUMNS
)


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0070_tenant_continuous_compliance_enforcement"),
    ]

    operations = [
        migrations.RunSQL(
            sql=_ADD_SQL,
            reverse_sql=_DROP_SQL,
        ),
    ]
