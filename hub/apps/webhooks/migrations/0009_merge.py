"""Merge conflicting migration leaves."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("webhooks", "0002_rename_webhooks_tenant_status_idx_webhooks_tenant__3268c0_idx_and_more"),
        ("webhooks", "0006_webhookdelivery_signing_key_uuid"),
        ("webhooks", "0008_enable_rls_webhooks"),
    ]

    operations = [
    ]
