"""285.14.3.9 — Add RLS policy for email_deliveries table.

Already covered: user_notifications (0010).
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0011_alter_emaildelivery_email_type"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE email_deliveries ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON email_deliveries;
            CREATE POLICY tenant_isolation ON email_deliveries
            USING (
                current_setting('app.rls_email_deliveries_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON email_deliveries;
            ALTER TABLE email_deliveries DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
