from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("dpia", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE dpia ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON dpia;
            CREATE POLICY tenant_isolation ON dpia
            USING (
                current_setting('app.rls_dpia_enabled', true) <> 'true'
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
            DROP POLICY IF EXISTS tenant_isolation ON dpia;
            ALTER TABLE dpia DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
