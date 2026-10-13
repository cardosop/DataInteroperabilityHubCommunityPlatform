"""Enable RLS on the DLT pipeline/update mirror tables (task 10.2).

Indirect-FK policies (the 1.2 template): neither mirror table carries a
tenant_id — the pipelines policy resolves the tenant through workspace →
databricks_workspaces.tenant_id; the updates policy through pipeline →
databricks_dlt_pipelines.workspace_id → databricks_workspaces.tenant_id
(the 2-hop chain, the 0011 multi-hop extension). Both honor the
``app.bypass_rls`` kill-switch GUC alongside the tenant context.

Pre-flight (285.14.1.3): the tables are created empty by 0031.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("databricks_admin", "0031_databricksdltpipeline_databricksdltpipelineupdate_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE databricks_dlt_pipelines ENABLE ROW LEVEL SECURITY;
            ALTER TABLE databricks_dlt_pipelines FORCE ROW LEVEL SECURITY;

            CREATE POLICY databricks_dlt_pipelines_tenant_isolation
            ON databricks_dlt_pipelines
                USING (
                    workspace_id IN (
                        SELECT dw.id FROM databricks_workspaces dw
                        WHERE dw.tenant_id::text =
                            current_setting('app.current_tenant_id', true)
                    )
                    OR current_setting('app.bypass_rls', true) = 'on'
                )
                WITH CHECK (
                    workspace_id IN (
                        SELECT dw.id FROM databricks_workspaces dw
                        WHERE dw.tenant_id::text =
                            current_setting('app.current_tenant_id', true)
                    )
                    OR current_setting('app.bypass_rls', true) = 'on'
                );

            ALTER TABLE databricks_dlt_pipeline_updates ENABLE ROW LEVEL SECURITY;
            ALTER TABLE databricks_dlt_pipeline_updates FORCE ROW LEVEL SECURITY;

            CREATE POLICY databricks_dlt_pipeline_updates_tenant_isolation
            ON databricks_dlt_pipeline_updates
                USING (
                    pipeline_id IN (
                        SELECT dp.id FROM databricks_dlt_pipelines dp
                        JOIN databricks_workspaces dw ON dw.id = dp.workspace_id
                        WHERE dw.tenant_id::text =
                            current_setting('app.current_tenant_id', true)
                    )
                    OR current_setting('app.bypass_rls', true) = 'on'
                )
                WITH CHECK (
                    pipeline_id IN (
                        SELECT dp.id FROM databricks_dlt_pipelines dp
                        JOIN databricks_workspaces dw ON dw.id = dp.workspace_id
                        WHERE dw.tenant_id::text =
                            current_setting('app.current_tenant_id', true)
                    )
                    OR current_setting('app.bypass_rls', true) = 'on'
                );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS databricks_dlt_pipeline_updates_tenant_isolation
                ON databricks_dlt_pipeline_updates;
            ALTER TABLE databricks_dlt_pipeline_updates DISABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS databricks_dlt_pipelines_tenant_isolation
                ON databricks_dlt_pipelines;
            ALTER TABLE databricks_dlt_pipelines DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
