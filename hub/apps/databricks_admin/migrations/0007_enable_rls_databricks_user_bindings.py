"""P0b (openspec add-databricks-control-plane task 0b.3) — RLS for `databricks_user_bindings`.

Per the CLAUDE.md RLS contract: every tenant_id-bearing model MUST ship
a paired RLS policy migration. Direct-FK template (the model stores
tenant_id directly), mirroring `0002_enable_rls_databricks_workspaces.py`.

Pre-flight tenant_context audit (285.14.1.3):
  - The model is NEW — no pre-existing query paths exist at this migration.
  - Planned access paths (tasks 0b.4–0b.5): the OBO token vault resolves
    bindings inside the request GUC (TenantMiddleware sets
    app.current_tenant_id); the SSO callback provisions bindings under the
    state-resolved tenant (request-scoped).
  - Cross-tenant iteration (logout revocation sweeps, workspace deletion
    cleanup) will use DATABASES["admin"] (meshant_admin, BYPASSRLS) per
    CLAUDE.md.

No unguarded query paths found. RLS policy is safe to enable.

Kill switch: setting app.rls_databricks_user_bindings_enabled to 'true'
disables the USING clause restriction (emergency rollback path; WITH
CHECK still enforces tenant_id on writes). Pattern per
hub/apps/audit/migrations/0005_enable_rls_audit_events.py.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("databricks_admin", "0006_databricksuserbinding"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE databricks_user_bindings ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON databricks_user_bindings;
            CREATE POLICY tenant_isolation ON databricks_user_bindings
            USING (
                current_setting('app.rls_databricks_user_bindings_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON databricks_user_bindings;
            ALTER TABLE databricks_user_bindings DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
