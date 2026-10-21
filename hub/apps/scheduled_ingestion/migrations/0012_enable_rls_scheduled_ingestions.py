"""
Phase 277.B.034 — enable RLS on `scheduled_ingestions`.

Per CLAUDE.md RLS contract: every tenant_id-bearing model
MUST ship a paired RLS policy migration.
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("scheduled_ingestion", "0011_rename_ingestion_te_tenant__idx_ingestion_t_tenant__766711_idx_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE scheduled_ingestions ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON scheduled_ingestions;
            CREATE POLICY tenant_isolation ON scheduled_ingestions
            USING (
                current_setting('app.rls_scheduled_ingestions_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON scheduled_ingestions;
            ALTER TABLE scheduled_ingestions DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
