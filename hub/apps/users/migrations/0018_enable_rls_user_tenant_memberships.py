from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0017_enable_rls_users"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE user_tenant_memberships ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON user_tenant_memberships;
            CREATE POLICY tenant_isolation ON user_tenant_memberships
            USING (
                current_setting(
                    'app.rls_user_tenant_memberships_enabled', true
                ) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON user_tenant_memberships;
            ALTER TABLE user_tenant_memberships DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
