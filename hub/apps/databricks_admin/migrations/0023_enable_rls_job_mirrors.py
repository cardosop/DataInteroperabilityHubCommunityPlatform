"""Enable RLS on the job/run mirror tables (task 4.2).

Indirect-FK policies (the 1.2 template): neither mirror table carries a
tenant_id — the jobs policy resolves the tenant through workspace →
databricks_workspaces.tenant_id; the runs policy through job →
databricks_jobs.workspace_id → databricks_workspaces.tenant_id (the
2-hop chain, the 0011 multi-hop extension). Both honor the
``app.bypass_rls`` kill-switch GUC alongside the tenant context.

Pre-flight (285.14.1.3): the tables are created empty by 0022.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("databricks_admin", "0022_databricksjob_databricksjobrun_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE databricks_jobs ENABLE ROW LEVEL SECURITY;
            ALTER TABLE databricks_jobs FORCE ROW LEVEL SECURITY;

            CREATE POLICY databricks_jobs_tenant_isolation
            ON databricks_jobs
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

            ALTER TABLE databricks_job_runs ENABLE ROW LEVEL SECURITY;
            ALTER TABLE databricks_job_runs FORCE ROW LEVEL SECURITY;

            CREATE POLICY databricks_job_runs_tenant_isolation
            ON databricks_job_runs
                USING (
                    job_id IN (
                        SELECT dj.id FROM databricks_jobs dj
                        JOIN databricks_workspaces dw ON dw.id = dj.workspace_id
                        WHERE dw.tenant_id::text =
                            current_setting('app.current_tenant_id', true)
                    )
                    OR current_setting('app.bypass_rls', true) = 'on'
                )
                WITH CHECK (
                    job_id IN (
                        SELECT dj.id FROM databricks_jobs dj
                        JOIN databricks_workspaces dw ON dw.id = dj.workspace_id
                        WHERE dw.tenant_id::text =
                            current_setting('app.current_tenant_id', true)
                    )
                    OR current_setting('app.bypass_rls', true) = 'on'
                );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS databricks_job_runs_tenant_isolation
                ON databricks_job_runs;
            ALTER TABLE databricks_job_runs DISABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS databricks_jobs_tenant_isolation
                ON databricks_jobs;
            ALTER TABLE databricks_jobs DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
