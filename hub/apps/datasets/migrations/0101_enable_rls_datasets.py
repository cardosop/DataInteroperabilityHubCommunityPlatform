from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("datasets", "0100_dataset_semantic_federate_optout"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE datasets ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON datasets;
            CREATE POLICY tenant_isolation ON datasets
            USING (
                current_setting('app.rls_datasets_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON datasets;
            ALTER TABLE datasets DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
