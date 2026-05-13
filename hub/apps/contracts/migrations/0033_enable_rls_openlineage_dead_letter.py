"""
Phase 277.B.018a — enable RLS on `openlineage_dead_letter`.

Per CLAUDE.md RLS contract: every tenant_id-bearing model
MUST ship a paired RLS policy migration.
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("contracts", "0032"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE openlineage_dead_letter ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON openlineage_dead_letter;
            CREATE POLICY tenant_isolation ON openlineage_dead_letter
            USING (
                current_setting('app.rls_openlineage_dead_letters_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON openlineage_dead_letter;
            ALTER TABLE openlineage_dead_letter DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
