"""Enable RLS on the SQL warehouse mirror (task 3.2).

Indirect-FK policy (the 1.2 template): the mirror table carries NO
tenant_id — the policy resolves the tenant through workspace →
databricks_workspaces.tenant_id, with the ``app.bypass_rls``
kill-switch GUC honoring the tenant context.

Pre-flight (285.14.1.3): the table is created empty by 0020.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("databricks_admin", "0020_databrickssqlwarehouse"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE databricks_sql_warehouses ENABLE ROW LEVEL SECURITY;
            ALTER TABLE databricks_sql_warehouses FORCE ROW LEVEL SECURITY;

            CREATE POLICY databricks_sql_warehouses_tenant_isolation
            ON databricks_sql_warehouses
                USING (
                    workspace_id IN (
                        SELECT dw.id FROM databricks_workspaces dw
                        WHERE dw.tenant_id::text =
                            current_setting('app.current_tenant_id', true)
                    )
                    OR current_setting('app.bypass_rls', true) = 'on'
                )
                WITH CHECK (
                    workspace_id IN (
                        SELECT dw.id FROM databricks_workspaces dw
                        WHERE dw.tenant_id::text =
                            current_setting('app.current_tenant_id', true)
                    )
                    OR current_setting('app.bypass_rls', true) = 'on'
                );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS databricks_sql_warehouses_tenant_isolation
                ON databricks_sql_warehouses;
            ALTER TABLE databricks_sql_warehouses DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
