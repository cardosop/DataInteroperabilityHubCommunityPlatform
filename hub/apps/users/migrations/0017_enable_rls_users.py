from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0016_passwordhistory"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE users ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON users;
            CREATE POLICY tenant_isolation ON users
            USING (
                current_setting('app.rls_users_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON users;
            ALTER TABLE users DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
