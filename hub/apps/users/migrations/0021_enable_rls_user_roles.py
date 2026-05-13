"""
Phase 277.B.018a — enable RLS on `user_roles`.

Per CLAUDE.md RLS contract: every tenant_id-bearing model
MUST ship a paired RLS policy migration.
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0016_passwordhistory"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE user_roles ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON user_roles;
            CREATE POLICY tenant_isolation ON user_roles
            USING (
                current_setting('app.rls_user_roles_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON user_roles;
            ALTER TABLE user_roles DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
