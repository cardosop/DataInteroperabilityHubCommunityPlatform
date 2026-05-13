from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        (
            "contracts",
            "0029_alter_migrationcheckpoint_migration_name_and_more",
        ),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE contracts ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON contracts;
            CREATE POLICY tenant_isolation ON contracts
            USING (
                current_setting('app.rls_contracts_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON contracts;
            ALTER TABLE contracts DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
