"""P0 (openspec add-databricks-control-plane task 0.2) — RLS for `databricks_workspaces`.

Per the CLAUDE.md RLS contract: every tenant_id-bearing model MUST ship
a paired RLS policy migration. This model is the RLS parent for the whole
databricks_admin family (credentials, UC mirrors, warehouses, jobs, DLT
pipelines, budgets).

Pre-flight tenant_context audit (285.14.1.3):
  - The model is NEW — no pre-existing query paths exist at this migration.
  - Planned access paths (tasks 0.8–0.9): the workspace ViewSet resolves
    the tenant from the request (TenantMiddleware sets
    app.current_tenant_id) and scopes querysets with tenant=...; the
    credential rotation endpoint runs inside the request GUC as well.
  - Cross-tenant iteration (UC metadata sync, cost sync — later phases)
    will use DATABASES["admin"] (meshant_admin, BYPASSRLS) per CLAUDE.md.
  - Worker/signal code touching this model will wrap in
    tenant_context(tenant_id).

No unguarded query paths found. RLS policy is safe to enable.

Kill switch: setting app.rls_databricks_workspaces_enabled to 'true'
disables the USING clause restriction (emergency rollback path; WITH
CHECK still enforces tenant_id on writes). Pattern per
hub/apps/audit/migrations/0005_enable_rls_audit_events.py.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("databricks_admin", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE databricks_workspaces ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON databricks_workspaces;
            CREATE POLICY tenant_isolation ON databricks_workspaces
            USING (
                current_setting('app.rls_databricks_workspaces_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON databricks_workspaces;
            ALTER TABLE databricks_workspaces DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
