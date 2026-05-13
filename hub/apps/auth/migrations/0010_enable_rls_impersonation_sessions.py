"""
Phase 277.B.018a — enable RLS on `impersonation_sessions`.

Per CLAUDE.md RLS contract: every tenant_id-bearing model
MUST ship a paired RLS policy migration.
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0008_customer_billing_fields"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE impersonation_sessions ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON impersonation_sessions;
            CREATE POLICY tenant_isolation ON impersonation_sessions
            USING (
                current_setting('app.rls_impersonation_sessions_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON impersonation_sessions;
            ALTER TABLE impersonation_sessions DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
