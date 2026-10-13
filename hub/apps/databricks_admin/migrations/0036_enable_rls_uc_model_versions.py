"""Enable RLS on the UC model-version mirror (openspec
add-databricks-ml-assets task 12.2).

Indirect-FK policy through the parent chain
(version.model → models.schema → schemas.catalog → catalogs.workspace)
— the 10.2 DLT-updates template's JOIN shape. The policy uses the
global ``app.bypass_rls`` bypass GUC only — there is NO per-table
``app.rls_uc_model_versions_enabled`` kill-switch GUC in the deployed
SQL (the constant below is legacy and unused; the W1.20 inventory
sync test pins settings ↔ deployed-policy GUCs, so no phantom
``RLS_UC_MODEL_VERSIONS_ENABLED`` setting exists). The reverse drops
the policy idempotently.

Pre-flight tenant_context audit (12.2): the model is NEW at this
migration — no pre-existing query paths exist. The only access paths
are the operation-time mirror writes (``ml_assets.register_model_version``
— the MLflow surface's reported-payload row) and the model-scoped reads,
both riding the request-scoped tenant context (the DRF tenant
middleware sets the RLS GUC per request). No unguarded tenant-scoped
query paths may read this table; a regression that adds unguarded
reads fails the pg_policies scan pin (test_ml_assets_versions.py).
"""

from django.db import migrations

TABLE = "databricks_uc_model_versions"
GUC = "app.rls_uc_model_versions_enabled"


class Migration(migrations.Migration):

    dependencies = [
        ("databricks_admin", "0035_ucmodelversion"),
    ]

    operations = [
        migrations.RunSQL(
            sql=f"""
            ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY;
            CREATE POLICY uc_model_versions_tenant_isolation
            ON {TABLE}
                USING (
                    model_id IN (
                        SELECT um.id
                        FROM databricks_uc_models um
                        JOIN databricks_uc_schemas us ON us.id = um.schema_id
                        JOIN databricks_uc_catalogs uc ON uc.id = us.catalog_id
                        JOIN databricks_workspaces dw ON dw.id = uc.workspace_id
                        WHERE dw.tenant_id::text =
                            current_setting('app.current_tenant_id', true)
                    )
                    OR current_setting('app.bypass_rls', true) = 'on'
                )
                WITH CHECK (
                    model_id IN (
                        SELECT um.id
                        FROM databricks_uc_models um
                        JOIN databricks_uc_schemas us ON us.id = um.schema_id
                        JOIN databricks_uc_catalogs uc ON uc.id = us.catalog_id
                        JOIN databricks_workspaces dw ON dw.id = uc.workspace_id
                        WHERE dw.tenant_id::text =
                            current_setting('app.current_tenant_id', true)
                    )
                    OR current_setting('app.bypass_rls', true) = 'on'
                );
            """,
            reverse_sql=f"""
            DROP POLICY IF EXISTS uc_model_versions_tenant_isolation ON {TABLE};
            """,
        ),
    ]
