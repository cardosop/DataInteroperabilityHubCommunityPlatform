"""
285.11.1.3 — enable RLS on pipeline_dependencies + pipeline_run_dependencies.

Per CLAUDE.md RLS contract: every tenant_id-bearing model
MUST ship a paired RLS policy migration.
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("orchestration", "0007_add_pipeline_dependency_models"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE pipeline_dependencies ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON pipeline_dependencies;
            CREATE POLICY tenant_isolation ON pipeline_dependencies
            USING (
                current_setting('app.rls_pipeline_dependencies_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );

            ALTER TABLE pipeline_run_dependencies ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON pipeline_run_dependencies;
            CREATE POLICY tenant_isolation ON pipeline_run_dependencies
            USING (
                current_setting('app.rls_pipeline_run_dependencies_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON pipeline_dependencies;
            ALTER TABLE pipeline_dependencies DISABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON pipeline_run_dependencies;
            ALTER TABLE pipeline_run_dependencies DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
