"""
285.12.1.10 — enable RLS on files table.

Per CLAUDE.md RLS contract: every tenant_id-bearing model
MUST ship a paired RLS policy migration.
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("files", "0010_rename_files_tenant_status_deleted_idx_files_tenant__d2fa97_idx_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE files ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON files;
            CREATE POLICY tenant_isolation ON files
            USING (
                current_setting('app.rls_files_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON files;
            ALTER TABLE files DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
