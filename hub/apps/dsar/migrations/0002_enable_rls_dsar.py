from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("dsar", "0001_phase232_dsar_and_tenant_flag"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE dsar_requests ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON dsar_requests;
            CREATE POLICY tenant_isolation ON dsar_requests
            USING (
                current_setting('app.rls_dsar_enabled', true) <> 'true'
                OR tenant_id::text = current_setting(
                    'app.current_tenant_id',
                    true
                )
            )
            WITH CHECK (
                tenant_id::text = current_setting(
                    'app.current_tenant_id',
                    true
                )
            );

            ALTER TABLE dsar_backup_affected_subjects ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON dsar_backup_affected_subjects;
            CREATE POLICY tenant_isolation ON dsar_backup_affected_subjects
            USING (
                current_setting('app.rls_dsar_enabled', true) <> 'true'
                OR tenant_id::text = current_setting(
                    'app.current_tenant_id',
                    true
                )
            )
            WITH CHECK (
                tenant_id::text = current_setting(
                    'app.current_tenant_id',
                    true
                )
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON dsar_backup_affected_subjects;
            ALTER TABLE dsar_backup_affected_subjects DISABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON dsar_requests;
            ALTER TABLE dsar_requests DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
