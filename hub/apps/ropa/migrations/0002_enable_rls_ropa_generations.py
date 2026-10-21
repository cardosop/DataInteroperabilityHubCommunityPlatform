from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("ropa", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE ropa_generations ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON ropa_generations;
            CREATE POLICY tenant_isolation ON ropa_generations
            USING (
                current_setting('app.rls_ropa_generations_enabled', true) <> 'true'
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
            DROP POLICY IF EXISTS tenant_isolation ON ropa_generations;
            ALTER TABLE ropa_generations DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
