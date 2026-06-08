"""
285.12.1.12 — enable RLS on webhooks table only.

Per CLAUDE.md RLS contract: every tenant_id-bearing model
MUST ship a paired RLS policy migration.
(webhook_deliveries excluded — no direct tenant_id column.)
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("webhooks", "0007_rename_wh_signing_keys_wh_stat_idx_webhook_sig_webhook_375250_idx_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE webhooks ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON webhooks;
            CREATE POLICY tenant_isolation ON webhooks
            USING (
                current_setting('app.rls_webhooks_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );

            -- webhook_deliveries omitted: WebhookDelivery model has no
            -- tenant_id column (scoped via webhook FK).
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON webhooks;
            ALTER TABLE webhooks DISABLE ROW LEVEL SECURITY;
            -- webhook_deliveries omitted (no tenant_id column)
            """,
        ),
    ]
