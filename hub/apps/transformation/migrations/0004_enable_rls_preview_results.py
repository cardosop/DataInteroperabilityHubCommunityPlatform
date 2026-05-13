"""
Phase 277.B.018a — enable RLS on `preview_results`.

Per CLAUDE.md RLS contract: every tenant_id-bearing model
MUST ship a paired RLS policy migration.
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("transformation", "0003"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE preview_results ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON preview_results;
            CREATE POLICY tenant_isolation ON preview_results
            USING (
                current_setting('app.rls_preview_results_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON preview_results;
            ALTER TABLE preview_results DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
