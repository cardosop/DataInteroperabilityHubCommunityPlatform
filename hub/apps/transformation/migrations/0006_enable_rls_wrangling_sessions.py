"""
Phase 277.B.018a — enable RLS on `wrangling_sessions`.

Per CLAUDE.md RLS contract: every tenant_id-bearing model
MUST ship a paired RLS policy migration.
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("transformation", "0005_enable_rls_transformation_pipelines"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE wrangling_sessions ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON wrangling_sessions;
            CREATE POLICY tenant_isolation ON wrangling_sessions
            USING (
                current_setting('app.rls_wrangling_sessions_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON wrangling_sessions;
            ALTER TABLE wrangling_sessions DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
