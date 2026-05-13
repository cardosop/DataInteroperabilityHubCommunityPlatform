"""
Phase 277.B.018a — enable RLS on `transformation_pipelines`.

Per CLAUDE.md RLS contract: every tenant_id-bearing model
MUST ship a paired RLS policy migration.
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("transformation", "0004"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE transformation_pipelines ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON transformation_pipelines;
            CREATE POLICY tenant_isolation ON transformation_pipelines
            USING (
                current_setting('app.rls_transformation_pipelines_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON transformation_pipelines;
            ALTER TABLE transformation_pipelines DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
