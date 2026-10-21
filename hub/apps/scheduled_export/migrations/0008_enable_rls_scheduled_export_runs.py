"""
Phase 277.B.034 — enable RLS on `scheduled_export_runs`.

Per CLAUDE.md RLS contract: every tenant_id-bearing model
MUST ship a paired RLS policy migration.
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("scheduled_export", "0007_enable_rls_scheduled_exports"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE scheduled_export_runs ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON scheduled_export_runs;
            CREATE POLICY tenant_isolation ON scheduled_export_runs
            USING (
                current_setting('app.rls_scheduled_export_runs_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON scheduled_export_runs;
            ALTER TABLE scheduled_export_runs DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
