from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("compliance", "0099_alter_compliancerun_dataset_set_null"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE compliance_runs ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON compliance_runs;
            CREATE POLICY tenant_isolation ON compliance_runs
            USING (
                current_setting('app.rls_compliance_runs_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON compliance_runs;
            ALTER TABLE compliance_runs DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
