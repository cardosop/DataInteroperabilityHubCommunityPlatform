from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0017_asset_version_increment_on_edit"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE assets ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON assets;
            CREATE POLICY tenant_isolation ON assets
            USING (
                current_setting('app.rls_assets_enabled', true) <> 'true'
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
            DROP POLICY IF EXISTS tenant_isolation ON assets;
            ALTER TABLE assets DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
