# Generated manually — ensures the ``lineage_edge_id`` column physically
# exists on ``pipeline_dependencies`` in PostgreSQL.
#
# Migration 0007 added the field in Django's state and was recorded as
# applied, but the ALTER TABLE never executed (likely faked during test-DB
# provisioning).  This migration runs the DDL unconditionally with
# ``IF NOT EXISTS`` so it is idempotent and safe for all environments.
#
# ``SeparateDatabaseAndState`` is used because the Django migration state
# already knows about the field — we only need the database-level change.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orchestration", "0011_rename_pipeline_tables_to_match_model"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE pipeline_dependencies "
                        "ADD COLUMN IF NOT EXISTS lineage_edge_id uuid NULL "
                        "CONSTRAINT pipeline_de_lineage_edge_id_fk "
                        "REFERENCES contracts_lineage_edge(id) "
                        "ON DELETE SET NULL"
                    ),
                    reverse_sql=(
                        "ALTER TABLE pipeline_dependencies "
                        "DROP COLUMN IF EXISTS lineage_edge_id"
                    ),
                ),
                migrations.RunSQL(
                    sql=(
                        "CREATE INDEX IF NOT EXISTS pipeline_de_lineage_69baca_idx "
                        "ON pipeline_dependencies (lineage_edge_id)"
                    ),
                    reverse_sql=(
                        "DROP INDEX IF EXISTS pipeline_de_lineage_69baca_idx"
                    ),
                ),
            ],
            state_operations=[],
        ),
    ]
