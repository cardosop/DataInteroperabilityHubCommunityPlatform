"""
Migration 0003 — Phase 11.4 (data)

Encrypts every existing plaintext webhook secret using the Fernet-based
encrypt_secret() helper (hub/apps/webhooks/encryption.py).

The helper is idempotent: secrets already prefixed with "v1:" are left
unchanged, so the migration is safe to re-run.
"""
from django.db import migrations


def encrypt_existing_secrets(apps, schema_editor):
    # Import at call time so the app registry is ready and ENCRYPTION_KEY
    # is resolved from settings (not available at module import time in tests).
    from hub.apps.webhooks.encryption import encrypt_secret

    Webhook = apps.get_model("webhooks", "Webhook")
    to_update = []
    for wh in Webhook.objects.only("id", "secret"):
        if wh.secret:
            encrypted = encrypt_secret(wh.secret)
            if encrypted != wh.secret:
                wh.secret = encrypted
                to_update.append(wh)
    if to_update:
        Webhook.objects.bulk_update(to_update, ["secret"])


class Migration(migrations.Migration):

    dependencies = [
        (
            "webhooks",
            "0002_rename_webhooks_tenant_status_idx_webhooks_tenant__3268c0_idx_and_more",
        ),
    ]

    operations = [
        migrations.RunPython(
            encrypt_existing_secrets,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
