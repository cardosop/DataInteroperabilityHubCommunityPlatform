"""
285.9.1.4.9-fix — Ensure prefect_flow_run_id column exists on
transformation_pipeline_executions.

Migration 0008 was recorded as applied but the underlying ALTER TABLE may
not have executed.  This migration uses SeparateDatabaseAndState so the
Django migration state is unchanged (the field already exists in the model
and migration state) — only the database operation runs.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("transformation", "0014_add_dbt_credential_fields"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE transformation_pipeline_executions "
                        "ADD COLUMN IF NOT EXISTS prefect_flow_run_id "
                        "varchar(255) NULL"
                    ),
                    reverse_sql=(
                        "ALTER TABLE transformation_pipeline_executions "
                        "DROP COLUMN IF EXISTS prefect_flow_run_id"
                    ),
                ),
            ],
            state_operations=[],
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "CREATE INDEX IF NOT EXISTS "
                        "transformation_pip_prefect_flow_run_id_idx "
                        "ON transformation_pipeline_executions "
                        "(prefect_flow_run_id)"
                    ),
                    reverse_sql=(
                        "DROP INDEX IF EXISTS "
                        "transformation_pip_prefect_flow_run_id_idx"
                    ),
                ),
            ],
            state_operations=[],
        ),
    ]
