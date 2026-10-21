from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("jobs", "0013_alter_job_type"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON jobs;
            CREATE POLICY tenant_isolation ON jobs
            USING (
                current_setting('app.rls_jobs_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON jobs;
            ALTER TABLE jobs DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
