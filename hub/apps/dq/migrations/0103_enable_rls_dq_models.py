"""
285.12.1.11 — enable RLS on dq_runs, dq_anomalies, dq_trends, dq_alerting_rules.

Per CLAUDE.md RLS contract: every tenant_id-bearing model
MUST ship a paired RLS policy migration.
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("dq", "0001_initial"),
        ("dq", "0102_add_error_code_and_message_to_dqrun"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE dq_runs ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON dq_runs;
            CREATE POLICY tenant_isolation ON dq_runs
            USING (
                current_setting('app.rls_dq_runs_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );

            ALTER TABLE dq_anomalies ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON dq_anomalies;
            CREATE POLICY tenant_isolation ON dq_anomalies
            USING (
                current_setting('app.rls_dq_anomalies_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );

            ALTER TABLE dq_trends ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON dq_trends;
            CREATE POLICY tenant_isolation ON dq_trends
            USING (
                current_setting('app.rls_dq_trends_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );

            ALTER TABLE dq_alerting_rules ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON dq_alerting_rules;
            CREATE POLICY tenant_isolation ON dq_alerting_rules
            USING (
                current_setting('app.rls_dq_alerting_rules_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON dq_runs;
            ALTER TABLE dq_runs DISABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON dq_anomalies;
            ALTER TABLE dq_anomalies DISABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON dq_trends;
            ALTER TABLE dq_trends DISABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON dq_alerting_rules;
            ALTER TABLE dq_alerting_rules DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
