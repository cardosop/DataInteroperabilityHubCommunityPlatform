"""
Phase 277.B.018a — enable RLS on `user_notifications`.

Per CLAUDE.md RLS contract: every tenant_id-bearing model
MUST ship a paired RLS policy migration.
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0009"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE user_notifications ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON user_notifications;
            CREATE POLICY tenant_isolation ON user_notifications
            USING (
                current_setting('app.rls_user_notifications_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON user_notifications;
            ALTER TABLE user_notifications DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
