"""
Phase 277.B.018a — enable RLS on `contracts_lineage_edge`.

Per CLAUDE.md RLS contract: every tenant_id-bearing model
MUST ship a paired RLS policy migration.
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("contracts", "0030"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE contracts_lineage_edge ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON contracts_lineage_edge;
            CREATE POLICY tenant_isolation ON contracts_lineage_edge
            USING (
                current_setting('app.rls_contracts_lineage_edges_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON contracts_lineage_edge;
            ALTER TABLE contracts_lineage_edge DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
