"""
Phase 277.B.018a — enable RLS on `warehouse_connection_acls`.

Per CLAUDE.md RLS contract: every tenant_id-bearing model
MUST ship a paired RLS policy migration.
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("warehouses", "0002_enable_rls_warehouse_connections"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE warehouse_connection_acls ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON warehouse_connection_acls;
            CREATE POLICY tenant_isolation ON warehouse_connection_acls
            USING (
                current_setting('app.rls_warehouse_connection_acls_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON warehouse_connection_acls;
            ALTER TABLE warehouse_connection_acls DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
