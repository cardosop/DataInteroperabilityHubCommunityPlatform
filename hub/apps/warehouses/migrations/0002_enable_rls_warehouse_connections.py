"""
Phase 277.B.018a — enable RLS on `warehouse_connections`.

Per CLAUDE.md RLS contract: every tenant_id-bearing model
MUST ship a paired RLS policy migration.
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("warehouses", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE warehouse_connections ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON warehouse_connections;
            CREATE POLICY tenant_isolation ON warehouse_connections
            USING (
                current_setting('app.rls_warehouse_connections_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON warehouse_connections;
            ALTER TABLE warehouse_connections DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
