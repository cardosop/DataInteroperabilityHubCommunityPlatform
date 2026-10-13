"""Enable RLS on the Delta Sharing recipient/token tables (task 5.2).

Direct-FK policies (the CLAUDE.md contract): both tables carry a
tenant_id — the recipients policy filters on it directly; the tokens
policy too (the tenant column is DENORMALIZED from the recipient and
``DeltaShareToken.clean()`` pins the two equal, so the direct-FK policy
is exact). Both honor the ``app.bypass_rls`` kill-switch GUC alongside
the tenant context.

Pre-flight (285.14.1.3): the tables are created empty by 0024.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("databricks_admin", "0024_deltasharerecipient_deltasharetoken_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE databricks_delta_share_recipients ENABLE ROW LEVEL SECURITY;
            ALTER TABLE databricks_delta_share_recipients FORCE ROW LEVEL SECURITY;

            CREATE POLICY databricks_delta_share_recipients_tenant_isolation
            ON databricks_delta_share_recipients
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

            ALTER TABLE databricks_delta_share_tokens ENABLE ROW LEVEL SECURITY;
            ALTER TABLE databricks_delta_share_tokens FORCE ROW LEVEL SECURITY;

            CREATE POLICY databricks_delta_share_tokens_tenant_isolation
            ON databricks_delta_share_tokens
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
            DROP POLICY IF EXISTS databricks_delta_share_tokens_tenant_isolation
                ON databricks_delta_share_tokens;
            ALTER TABLE databricks_delta_share_tokens DISABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS databricks_delta_share_recipients_tenant_isolation
                ON databricks_delta_share_recipients;
            ALTER TABLE databricks_delta_share_recipients DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
