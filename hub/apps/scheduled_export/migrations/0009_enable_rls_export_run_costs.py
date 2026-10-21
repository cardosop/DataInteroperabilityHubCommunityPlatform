"""
Phase 277.B.034 — enable RLS on `export_run_costs`.

Per CLAUDE.md RLS contract: every tenant_id-bearing model
MUST ship a paired RLS policy migration.
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("scheduled_export", "0008_enable_rls_scheduled_export_runs"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE export_run_costs ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON export_run_costs;
            CREATE POLICY tenant_isolation ON export_run_costs
            USING (
                current_setting('app.rls_export_run_costs_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON export_run_costs;
            ALTER TABLE export_run_costs DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
