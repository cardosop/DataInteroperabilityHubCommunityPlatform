"""
Phase 277.B.018a — enable RLS on `openlineage_inbound_event`.

Per CLAUDE.md RLS contract: every tenant_id-bearing model
MUST ship a paired RLS policy migration.
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("contracts", "0036_enable_rls_openlineage_dead_letter"),
        ("integrations", "0011_openlineage_inbound_and_retry"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE openlineage_inbound_event ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON openlineage_inbound_event;
            CREATE POLICY tenant_isolation ON openlineage_inbound_event
            USING (
                current_setting('app.rls_openlineage_inbound_events_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON openlineage_inbound_event;
            ALTER TABLE openlineage_inbound_event DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
