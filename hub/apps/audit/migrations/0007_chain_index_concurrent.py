"""Phase 234.1.2 — non-blocking ``CREATE INDEX CONCURRENTLY`` on
``audit_events (tenant_id, chain_sequence)``.

PostgreSQL refuses ``CREATE INDEX CONCURRENTLY`` inside a transaction
block, so this migration is marked ``atomic = False``. The matching
state-only ``models.Index`` declaration lives on
``AuditEvent.Meta.indexes`` and is registered (without a SQL change) by
``SeparateDatabaseAndState`` below — so ``makemigrations`` doesn't try
to re-create the index in a future migration when the model and the
schema are otherwise in sync.

Rollback uses ``DROP INDEX CONCURRENTLY`` for the same reason: a normal
``DROP INDEX`` takes an ACCESS EXCLUSIVE lock that would block every
audit-write while it runs.
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("audit", "0006_add_chain_fields"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
                        "ae_tenant_chain_seq_idx "
                        "ON audit_events (tenant_id, chain_sequence)"
                    ),
                    reverse_sql=(
                        "DROP INDEX CONCURRENTLY IF EXISTS "
                        "ae_tenant_chain_seq_idx"
                    ),
                ),
            ],
            state_operations=[
                # The index is already declared on the model's ``Meta.indexes``
                # in 0006; we re-declare it here as a state-only no-op so
                # makemigrations sees a clean "no diff" against the model
                # after both migrations are applied.
                migrations.AddIndex(
                    model_name="auditevent",
                    index=models.Index(
                        fields=["tenant", "chain_sequence"],
                        name="ae_tenant_chain_seq_idx",
                    ),
                ),
            ],
        ),
    ]
