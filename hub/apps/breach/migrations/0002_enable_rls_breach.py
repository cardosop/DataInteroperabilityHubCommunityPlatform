from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("breach", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE breach_incident ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON breach_incident;
            CREATE POLICY tenant_isolation ON breach_incident
            USING (
                current_setting('app.rls_breach_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );

            ALTER TABLE breach_notification ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON breach_notification;
            CREATE POLICY tenant_isolation ON breach_notification
            USING (
                current_setting('app.rls_breach_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );

            ALTER TABLE breach_tenant_template_override ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON breach_tenant_template_override;
            CREATE POLICY tenant_isolation ON breach_tenant_template_override
            USING (
                current_setting('app.rls_breach_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON breach_tenant_template_override;
            ALTER TABLE breach_tenant_template_override DISABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON breach_notification;
            ALTER TABLE breach_notification DISABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON breach_incident;
            ALTER TABLE breach_incident DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
