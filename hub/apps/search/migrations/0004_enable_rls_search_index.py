from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        (
            "search",
            "0003_rename_search_anal_tenant__created_at_idx_search_anal_tenant__f24a36_idx_and_more",
        ),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE search_index ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON search_index;
            CREATE POLICY tenant_isolation ON search_index
            USING (
                current_setting('app.rls_search_index_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON search_index;
            ALTER TABLE search_index DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
