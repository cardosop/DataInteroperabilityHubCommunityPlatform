"""
Phase 277.B.018a — enable RLS on `openlineage_ingest_api_key`.

Per CLAUDE.md RLS contract: every tenant_id-bearing model
MUST ship a paired RLS policy migration.
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("contracts", "0037_enable_rls_openlineage_inbound_event"),
        ("integrations", "0010_openlineage"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE openlineage_ingest_api_key ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON openlineage_ingest_api_key;
            CREATE POLICY tenant_isolation ON openlineage_ingest_api_key
            USING (
                current_setting('app.rls_openlineage_ingest_api_keys_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON openlineage_ingest_api_key;
            ALTER TABLE openlineage_ingest_api_key DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
