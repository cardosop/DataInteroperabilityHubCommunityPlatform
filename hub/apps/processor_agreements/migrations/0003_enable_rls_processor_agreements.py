from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("processor_agreements", "0002_asset_processor_membership"),
        ("assets", "0020_asset_processors_m2m"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE pa_processor ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON pa_processor;
            CREATE POLICY tenant_isolation ON pa_processor
            USING (
                current_setting('app.rls_processor_agreements_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );

            ALTER TABLE pa_agreement ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON pa_agreement;
            CREATE POLICY tenant_isolation ON pa_agreement
            USING (
                current_setting('app.rls_processor_agreements_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );

            ALTER TABLE pa_asset_processor ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON pa_asset_processor;
            CREATE POLICY tenant_isolation ON pa_asset_processor
            USING (
                current_setting('app.rls_processor_agreements_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON pa_asset_processor;
            ALTER TABLE pa_asset_processor DISABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON pa_agreement;
            ALTER TABLE pa_agreement DISABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON pa_processor;
            ALTER TABLE pa_processor DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
