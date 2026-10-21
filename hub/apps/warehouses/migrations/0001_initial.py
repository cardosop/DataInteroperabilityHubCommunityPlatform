"""
Phase 275.A.1 — WarehouseConnection + WarehouseConnectionACL models.
RLS policy bundled per Phase 260 CLAUDE.md contract.
"""
from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("tenants", "0068_phase_274_marketplace_compliance_gate"),
    ]

    operations = [
        migrations.CreateModel(
            name="WarehouseConnection",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)),
                ("name", models.CharField(max_length=255)),
                ("warehouse_type", models.CharField(max_length=20, choices=[
                    ("SNOWFLAKE", "Snowflake"), ("BIGQUERY", "BigQuery"),
                    ("DATABRICKS", "Databricks"), ("ATHENA", "Athena"),
                ])),
                ("config", models.JSONField(default=dict)),
                ("region", models.CharField(max_length=64, blank=True, default="")),
                ("private_endpoint_url", models.CharField(max_length=512, blank=True, default="")),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("tenant", models.ForeignKey(
                    "tenants.Tenant", on_delete=models.CASCADE,
                    related_name="warehouse_connections",
                )),
            ],
            options={
                "db_table": "warehouse_connections",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="warehouseconnection",
            constraint=models.UniqueConstraint(
                fields=["tenant", "name"],
                name="unique_warehouse_connection_name_per_tenant",
            ),
        ),
        migrations.AddIndex(
            model_name="warehouseconnection",
            index=models.Index(fields=["tenant", "warehouse_type"], name="wh_conn_type_idx"),
        ),
        migrations.AddIndex(
            model_name="warehouseconnection",
            index=models.Index(fields=["tenant", "is_active"], name="wh_conn_active_idx"),
        ),
        migrations.CreateModel(
            name="WarehouseConnectionACL",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)),
                ("role", models.CharField(max_length=50, default="VIEWER")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("tenant", models.ForeignKey(
                    "tenants.Tenant", on_delete=models.CASCADE,
                    related_name="warehouse_acls",
                )),
                ("connection", models.ForeignKey(
                    "WarehouseConnection", on_delete=models.CASCADE,
                    related_name="acls",
                )),
                ("user", models.ForeignKey(
                    "users.User", on_delete=models.CASCADE,
                    related_name="warehouse_acls", null=True, blank=True,
                )),
            ],
            options={"db_table": "warehouse_connection_acls"},
        ),
        migrations.AddConstraint(
            model_name="warehouseconnectionacl",
            constraint=models.UniqueConstraint(
                fields=["connection", "user"],
                name="unique_warehouse_acl_per_user",
            ),
        ),
        migrations.RunSQL(
            sql="""
            ALTER TABLE warehouse_connections ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON warehouse_connections;
            CREATE POLICY tenant_isolation ON warehouse_connections
            USING (
                current_setting('app.rls_warehouse_connections_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );

            ALTER TABLE warehouse_connection_acls ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON warehouse_connection_acls;
            CREATE POLICY tenant_isolation ON warehouse_connection_acls
            USING (
                current_setting('app.rls_warehouse_connection_acls_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON warehouse_connections;
            ALTER TABLE warehouse_connections DISABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON warehouse_connection_acls;
            ALTER TABLE warehouse_connection_acls DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
