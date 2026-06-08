"""
Phase 277.B.018a — enable RLS on `audit_merkle_snapshots`.

Per CLAUDE.md RLS contract: every tenant_id-bearing model
MUST ship a paired RLS policy migration.
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0006_add_chain_fields"),
        ("audit", "0004_auditevent_full_details_json"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE audit_merkle_snapshots ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON audit_merkle_snapshots;
            CREATE POLICY tenant_isolation ON audit_merkle_snapshots
            USING (
                current_setting('app.rls_audit_merkle_snapshots_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON audit_merkle_snapshots;
            ALTER TABLE audit_merkle_snapshots DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
