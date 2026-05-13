from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("consent", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE consent_purpose ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON consent_purpose;
            CREATE POLICY tenant_isolation ON consent_purpose
            USING (
                current_setting('app.rls_consent_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );

            ALTER TABLE consent_record ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON consent_record;
            CREATE POLICY tenant_isolation ON consent_record
            USING (
                current_setting('app.rls_consent_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON consent_record;
            ALTER TABLE consent_record DISABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON consent_purpose;
            ALTER TABLE consent_purpose DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
