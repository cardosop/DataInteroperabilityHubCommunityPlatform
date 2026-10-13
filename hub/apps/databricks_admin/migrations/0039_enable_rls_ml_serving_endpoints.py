"""Enable RLS on the ML serving-endpoint mirror (openspec
add-databricks-ml-assets task 12.4).

Workspace-scoped indirect-FK policy (the DLT-pipelines template) with
the bypass GUC; the reverse drops the policy idempotently.

Pre-flight tenant_context audit (12.4): the model is NEW at this
migration — no pre-existing query paths exist. The only access paths
are the operation-time mirror writes (the 12.4 service functions —
``create_serving_endpoint``/``list_serving_endpoints``/
``delete_serving_endpoint``/``create_vector_search_endpoint``, the
API-reported state, never invented) and the endpoint-state reads, both
riding the request-scoped tenant context (the DRF tenant middleware
sets the RLS GUC per request). No unguarded tenant-scoped query paths
may read this table; a regression that adds unguarded reads fails the
pg_policies scan pin (test_ml_serving.py).
"""

from django.db import migrations

TABLE = "databricks_ml_serving_endpoints"


class Migration(migrations.Migration):

    dependencies = [
        ("databricks_admin", "0038_databricksmlservingendpoint"),
    ]

    operations = [
        migrations.RunSQL(
            sql=f"""
            ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY;
            CREATE POLICY ml_serving_endpoints_tenant_isolation
            ON {TABLE}
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
            reverse_sql=f"""
            DROP POLICY IF EXISTS ml_serving_endpoints_tenant_isolation ON {TABLE};
            """,
        ),
    ]
