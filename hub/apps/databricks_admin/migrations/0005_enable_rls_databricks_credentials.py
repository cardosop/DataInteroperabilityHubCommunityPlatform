"""P0 (openspec add-databricks-control-plane task 0.3) — RLS for `databricks_credentials`.

Per the CLAUDE.md RLS contract: every tenant-scoped model MUST ship a paired
RLS policy migration. This table carries NO tenant_id column — tenant
isolation resolves through the workspace parent chain (indirect-FK
template, docs/rls-migration-template.md).

Pre-flight tenant_context audit (285.14.1.3):
  - The model is NEW — no pre-existing query paths exist at this migration.
  - Planned access paths (task 0.9): the credential create/rotate endpoints
    resolve the tenant from the request (TenantMiddleware sets
    app.current_tenant_id) and scope through the workspace FK.
  - Cross-tenant iteration (credential rotation sweeps — later phases) will
    use DATABASES["admin"] (meshant_admin, BYPASSRLS) per CLAUDE.md.
  - Worker/signal code touching this model will wrap in
    tenant_context(tenant_id).

No unguarded query paths found. RLS policy is safe to enable.

Kill switch: setting app.rls_databricks_credentials_enabled to 'true'
disables the USING clause restriction (emergency rollback path; WITH CHECK
still enforces the workspace's tenant on writes). Pattern per
hub/apps/audit/migrations/0005_enable_rls_audit_events.py.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("databricks_admin", "0004_databrickscredential"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE databricks_credentials ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON databricks_credentials;
            CREATE POLICY tenant_isolation ON databricks_credentials
            USING (
                current_setting('app.rls_databricks_credentials_enabled', true) <> 'true'
                OR workspace_id IN (
                    SELECT id FROM databricks_workspaces
                    WHERE tenant_id::text =
                          current_setting('app.current_tenant_id', true)
                )
            )
            WITH CHECK (
                workspace_id IN (
                    SELECT id FROM databricks_workspaces
                    WHERE tenant_id::text =
                          current_setting('app.current_tenant_id', true)
                )
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON databricks_credentials;
            ALTER TABLE databricks_credentials DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
