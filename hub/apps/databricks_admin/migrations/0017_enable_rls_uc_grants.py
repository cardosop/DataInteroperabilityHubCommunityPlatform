"""Enable RLS on the grants-bridge tables (task 2.6).

Paired RLS policies for `uc_principals` and `uc_grant_bindings` — the
direct-workspace-FK template (same shape as the databricks_credentials
policy): both tables carry a DIRECT `workspace_id` FK, so the policy
resolves the tenant from `databricks_workspaces.tenant_id` and the
kill-switch GUC honors the tenant context.

Pre-flight (285.14.1.3): before enabling, verify no pre-existing rows
violate the policy predicate; `app.bypass_rls` is the emergency
kill-switch.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("databricks_admin", "0016_ucpprincipal_ucgrantbinding_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE uc_principals ENABLE ROW LEVEL SECURITY;
            ALTER TABLE uc_principals FORCE ROW LEVEL SECURITY;

            CREATE POLICY uc_principals_tenant_isolation ON uc_principals
                USING (
                    workspace_id IN (
                        SELECT dw.id FROM databricks_workspaces dw
                        WHERE dw.tenant_id::text = current_setting('app.current_tenant_id', true)
                    )
                    OR current_setting('app.bypass_rls', true) = 'on'
                )
                WITH CHECK (
                    workspace_id IN (
                        SELECT dw.id FROM databricks_workspaces dw
                        WHERE dw.tenant_id::text = current_setting('app.current_tenant_id', true)
                    )
                    OR current_setting('app.bypass_rls', true) = 'on'
                );

            ALTER TABLE uc_grant_bindings ENABLE ROW LEVEL SECURITY;
            ALTER TABLE uc_grant_bindings FORCE ROW LEVEL SECURITY;

            CREATE POLICY uc_grant_bindings_tenant_isolation ON uc_grant_bindings
                USING (
                    workspace_id IN (
                        SELECT dw.id FROM databricks_workspaces dw
                        WHERE dw.tenant_id::text = current_setting('app.current_tenant_id', true)
                    )
                    OR current_setting('app.bypass_rls', true) = 'on'
                )
                WITH CHECK (
                    workspace_id IN (
                        SELECT dw.id FROM databricks_workspaces dw
                        WHERE dw.tenant_id::text = current_setting('app.current_tenant_id', true)
                    )
                    OR current_setting('app.bypass_rls', true) = 'on'
                );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS uc_grant_bindings_tenant_isolation ON uc_grant_bindings;
            DROP POLICY IF EXISTS uc_principals_tenant_isolation ON uc_principals;
            ALTER TABLE uc_grant_bindings NO FORCE ROW LEVEL SECURITY;
            ALTER TABLE uc_grant_bindings DISABLE ROW LEVEL SECURITY;
            ALTER TABLE uc_principals NO FORCE ROW LEVEL SECURITY;
            ALTER TABLE uc_principals DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
