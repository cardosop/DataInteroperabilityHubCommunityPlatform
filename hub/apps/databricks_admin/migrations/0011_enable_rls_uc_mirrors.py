"""P1 (openspec add-databricks-uc-read task 1.2) — RLS for the UC mirror tables.

Per the CLAUDE.md RLS contract: every tenant-scoped model MUST ship a
paired RLS policy migration. INDIRECT-FK template: the mirror tables
carry no tenant_id column — each policy resolves the tenant through the
parent chain (catalog → workspace for workspace-level rows; table/view/
volume/model → schema → catalog → workspace for schema-level rows),
mirroring `0005_enable_rls_databricks_credentials.py` extended to the
multi-hop shape. The policy SQL is written LITERALLY per table (the
285.14.3.8 scan contract greps the migration text for the per-table
statements).

Pre-flight tenant_context audit (285.14.1.3):
  - The mirror tables are NEW — no pre-existing query paths.
  - Planned access paths (tasks 1.3–1.6): browse views and the metadata
    sync job run inside the request/job GUC (TenantMiddleware /
    tenant_context set app.current_tenant_id); the sync job discovers
    tenants via DATABASES["admin"] and iterates under tenant_context.
  - No unguarded query paths found.

Kill switch per table: setting app.rls_<table>_enabled to 'true' disables
the USING clause restriction (emergency rollback path; WITH CHECK still
enforces tenant visibility on writes via the chain check).
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("databricks_admin", "0010_uccatalog_ucexternallocation_ucschema_ucmodel_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE databricks_uc_catalogs ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON databricks_uc_catalogs;
            CREATE POLICY tenant_isolation ON databricks_uc_catalogs
            USING (
                current_setting('app.rls_uc_catalogs_enabled', true) <> 'true'
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

            ALTER TABLE databricks_uc_external_locations ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON databricks_uc_external_locations;
            CREATE POLICY tenant_isolation ON databricks_uc_external_locations
            USING (
                current_setting('app.rls_uc_external_locations_enabled', true) <> 'true'
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

            ALTER TABLE databricks_uc_storage_credentials ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON databricks_uc_storage_credentials;
            CREATE POLICY tenant_isolation ON databricks_uc_storage_credentials
            USING (
                current_setting('app.rls_uc_storage_credentials_enabled', true) <> 'true'
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

            ALTER TABLE databricks_uc_schemas ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON databricks_uc_schemas;
            CREATE POLICY tenant_isolation ON databricks_uc_schemas
            USING (
                current_setting('app.rls_uc_schemas_enabled', true) <> 'true'
                OR catalog_id IN (
                    SELECT id FROM databricks_uc_catalogs
                    WHERE workspace_id IN (
                        SELECT id FROM databricks_workspaces
                        WHERE tenant_id::text =
                            current_setting('app.current_tenant_id', true)
                    )
                )
            )
            WITH CHECK (
                catalog_id IN (
                    SELECT id FROM databricks_uc_catalogs
                    WHERE workspace_id IN (
                        SELECT id FROM databricks_workspaces
                        WHERE tenant_id::text =
                            current_setting('app.current_tenant_id', true)
                    )
                )
            );

            ALTER TABLE databricks_uc_tables ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON databricks_uc_tables;
            CREATE POLICY tenant_isolation ON databricks_uc_tables
            USING (
                current_setting('app.rls_uc_tables_enabled', true) <> 'true'
                OR schema_id IN (
                    SELECT id FROM databricks_uc_schemas
                    WHERE catalog_id IN (
                        SELECT id FROM databricks_uc_catalogs
                        WHERE workspace_id IN (
                            SELECT id FROM databricks_workspaces
                            WHERE tenant_id::text =
                                current_setting('app.current_tenant_id', true)
                        )
                    )
                )
            )
            WITH CHECK (
                schema_id IN (
                    SELECT id FROM databricks_uc_schemas
                    WHERE catalog_id IN (
                        SELECT id FROM databricks_uc_catalogs
                        WHERE workspace_id IN (
                            SELECT id FROM databricks_workspaces
                            WHERE tenant_id::text =
                                current_setting('app.current_tenant_id', true)
                        )
                    )
                )
            );

            ALTER TABLE databricks_uc_views ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON databricks_uc_views;
            CREATE POLICY tenant_isolation ON databricks_uc_views
            USING (
                current_setting('app.rls_uc_views_enabled', true) <> 'true'
                OR schema_id IN (
                    SELECT id FROM databricks_uc_schemas
                    WHERE catalog_id IN (
                        SELECT id FROM databricks_uc_catalogs
                        WHERE workspace_id IN (
                            SELECT id FROM databricks_workspaces
                            WHERE tenant_id::text =
                                current_setting('app.current_tenant_id', true)
                        )
                    )
                )
            )
            WITH CHECK (
                schema_id IN (
                    SELECT id FROM databricks_uc_schemas
                    WHERE catalog_id IN (
                        SELECT id FROM databricks_uc_catalogs
                        WHERE workspace_id IN (
                            SELECT id FROM databricks_workspaces
                            WHERE tenant_id::text =
                                current_setting('app.current_tenant_id', true)
                        )
                    )
                )
            );

            ALTER TABLE databricks_uc_volumes ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON databricks_uc_volumes;
            CREATE POLICY tenant_isolation ON databricks_uc_volumes
            USING (
                current_setting('app.rls_uc_volumes_enabled', true) <> 'true'
                OR schema_id IN (
                    SELECT id FROM databricks_uc_schemas
                    WHERE catalog_id IN (
                        SELECT id FROM databricks_uc_catalogs
                        WHERE workspace_id IN (
                            SELECT id FROM databricks_workspaces
                            WHERE tenant_id::text =
                                current_setting('app.current_tenant_id', true)
                        )
                    )
                )
            )
            WITH CHECK (
                schema_id IN (
                    SELECT id FROM databricks_uc_schemas
                    WHERE catalog_id IN (
                        SELECT id FROM databricks_uc_catalogs
                        WHERE workspace_id IN (
                            SELECT id FROM databricks_workspaces
                            WHERE tenant_id::text =
                                current_setting('app.current_tenant_id', true)
                        )
                    )
                )
            );

            ALTER TABLE databricks_uc_models ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON databricks_uc_models;
            CREATE POLICY tenant_isolation ON databricks_uc_models
            USING (
                current_setting('app.rls_uc_models_enabled', true) <> 'true'
                OR schema_id IN (
                    SELECT id FROM databricks_uc_schemas
                    WHERE catalog_id IN (
                        SELECT id FROM databricks_uc_catalogs
                        WHERE workspace_id IN (
                            SELECT id FROM databricks_workspaces
                            WHERE tenant_id::text =
                                current_setting('app.current_tenant_id', true)
                        )
                    )
                )
            )
            WITH CHECK (
                schema_id IN (
                    SELECT id FROM databricks_uc_schemas
                    WHERE catalog_id IN (
                        SELECT id FROM databricks_uc_catalogs
                        WHERE workspace_id IN (
                            SELECT id FROM databricks_workspaces
                            WHERE tenant_id::text =
                                current_setting('app.current_tenant_id', true)
                        )
                    )
                )
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON databricks_uc_catalogs;
            ALTER TABLE databricks_uc_catalogs DISABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON databricks_uc_external_locations;
            ALTER TABLE databricks_uc_external_locations DISABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON databricks_uc_storage_credentials;
            ALTER TABLE databricks_uc_storage_credentials DISABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON databricks_uc_schemas;
            ALTER TABLE databricks_uc_schemas DISABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON databricks_uc_tables;
            ALTER TABLE databricks_uc_tables DISABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON databricks_uc_views;
            ALTER TABLE databricks_uc_views DISABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON databricks_uc_volumes;
            ALTER TABLE databricks_uc_volumes DISABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON databricks_uc_models;
            ALTER TABLE databricks_uc_models DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
