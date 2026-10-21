from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0004_auditevent_full_details_json"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON audit_events;
            CREATE POLICY tenant_isolation ON audit_events
            USING (
                current_setting('app.rls_audit_events_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON audit_events;
            ALTER TABLE audit_events DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
