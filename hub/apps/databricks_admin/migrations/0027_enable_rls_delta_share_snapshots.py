"""Enable RLS on the Delta Sharing snapshot table (task 5.3).

Direct-FK policy (the CLAUDE.md contract): the table carries tenant_id,
so the policy filters on it directly. Honors the ``app.bypass_rls``
kill-switch GUC alongside the tenant context.

Pre-flight (285.14.1.3): the table is created empty by 0026.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("databricks_admin", "0026_deltasharesnapshot"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE databricks_delta_share_snapshots ENABLE ROW LEVEL SECURITY;
            ALTER TABLE databricks_delta_share_snapshots FORCE ROW LEVEL SECURITY;

            CREATE POLICY databricks_delta_share_snapshots_tenant_isolation
            ON databricks_delta_share_snapshots
                USING (
                    tenant_id::text =
                        current_setting('app.current_tenant_id', true)
                    OR current_setting('app.bypass_rls', true) = 'on'
                )
                WITH CHECK (
                    tenant_id::text =
                        current_setting('app.current_tenant_id', true)
                    OR current_setting('app.bypass_rls', true) = 'on'
                );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS databricks_delta_share_snapshots_tenant_isolation
                ON databricks_delta_share_snapshots;
            ALTER TABLE databricks_delta_share_snapshots DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
