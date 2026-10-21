"""Phase 234.6.2 — non-blocking ``CREATE INDEX CONCURRENTLY`` GIN index
on ``audit_events (details_json_tsvector)``.

Postgres refuses ``CREATE INDEX CONCURRENTLY`` inside a transaction
block, so this migration is marked ``atomic = False`` (same shape as
the Phase 234.1.2 index migration ``0007_chain_index_concurrent``).

Rollback uses ``DROP INDEX CONCURRENTLY`` for the same reason a plain
``DROP INDEX`` takes an ACCESS EXCLUSIVE lock that would freeze every
audit-write while it runs — concurrent drop is the safe path on the
hot audit table.

The matching state-only ``models.Index`` declaration is registered
via ``SeparateDatabaseAndState`` below so ``makemigrations`` doesn't
re-issue the index in a future migration.
"""
import django.contrib.postgres.indexes
from django.db import migrations


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("audit", "0010_audit_event_details_tsvector"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
                        "audit_events_details_tsv_gin "
                        "ON audit_events USING GIN (details_json_tsvector);"
                    ),
                    reverse_sql=(
                        "DROP INDEX CONCURRENTLY IF EXISTS "
                        "audit_events_details_tsv_gin;"
                    ),
                ),
            ],
            state_operations=[
                migrations.AddIndex(
                    model_name="auditevent",
                    index=django.contrib.postgres.indexes.GinIndex(
                        fields=["details_json_tsvector"],
                        name="audit_events_details_tsv_gin",
                    ),
                ),
            ],
        ),
    ]
