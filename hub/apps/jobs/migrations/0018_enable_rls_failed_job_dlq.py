"""
Phase 277.B.018a — enable RLS on `failed_job_dlq`.

Per CLAUDE.md RLS contract: every tenant_id-bearing model
MUST ship a paired RLS policy migration.
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("jobs", "0013_alter_job_type"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE failed_job_dlq ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON failed_job_dlq;
            CREATE POLICY tenant_isolation ON failed_job_dlq
            USING (
                current_setting('app.rls_failed_job_dlqs_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON failed_job_dlq;
            ALTER TABLE failed_job_dlq DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
