"""
Phase 277.B.034 — enable RLS on `scheduled_exports`.

Per CLAUDE.md RLS contract: every tenant_id-bearing model
MUST ship a paired RLS policy migration.
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("scheduled_export", "0006_alter_scheduledexport_status"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE scheduled_exports ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON scheduled_exports;
            CREATE POLICY tenant_isolation ON scheduled_exports
            USING (
                current_setting('app.rls_scheduled_exports_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON scheduled_exports;
            ALTER TABLE scheduled_exports DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
