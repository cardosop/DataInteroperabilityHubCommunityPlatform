from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("mesh", "0003_add_workflow_instance_to_domain"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE data_mesh_domains ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON data_mesh_domains;
            CREATE POLICY tenant_isolation ON data_mesh_domains
            USING (
                current_setting('app.rls_data_mesh_domains_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON data_mesh_domains;
            ALTER TABLE data_mesh_domains DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
