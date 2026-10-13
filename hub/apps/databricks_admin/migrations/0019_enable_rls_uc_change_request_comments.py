"""Enable RLS on the U4 comment table (task 2.8).

Indirect-FK policy: the comment table carries NO tenant_id — the policy
resolves the tenant through request → workspace (the multi-hop chain),
with the ``app.bypass_rls`` kill-switch GUC honoring the tenant context.

Pre-flight (285.14.1.3): before enabling, verify no pre-existing rows
violate the policy predicate (the table is created empty by 0018).
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("databricks_admin", "0018_ucchangerequestcomment"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE databricks_uc_change_request_comments
                ENABLE ROW LEVEL SECURITY;
            ALTER TABLE databricks_uc_change_request_comments
                FORCE ROW LEVEL SECURITY;

            CREATE POLICY uc_change_request_comments_tenant_isolation
            ON databricks_uc_change_request_comments
                USING (
                    request_id IN (
                        SELECT cr.id FROM databricks_uc_change_requests cr
                        JOIN databricks_workspaces dw ON dw.id = cr.workspace_id
                        WHERE dw.tenant_id::text =
                            current_setting('app.current_tenant_id', true)
                    )
                    OR current_setting('app.bypass_rls', true) = 'on'
                )
                WITH CHECK (
                    request_id IN (
                        SELECT cr.id FROM databricks_uc_change_requests cr
                        JOIN databricks_workspaces dw ON dw.id = cr.workspace_id
                        WHERE dw.tenant_id::text =
                            current_setting('app.current_tenant_id', true)
                    )
                    OR current_setting('app.bypass_rls', true) = 'on'
                );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS uc_change_request_comments_tenant_isolation
                ON databricks_uc_change_request_comments;
            ALTER TABLE databricks_uc_change_request_comments
                DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
