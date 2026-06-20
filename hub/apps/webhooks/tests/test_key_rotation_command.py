"""
Phase 44 (44.8) — Webhook Encryption Key Rotation Command Tests

Tests the rotate_webhook_encryption_key management command.
"""

from io import StringIO

import pytest
from django.core.management import call_command
from django.test import TestCase

from hub.apps.webhooks.management.commands.rotate_webhook_encryption_key import (
    _decrypt_with_key,
    _encrypt_with_key,
    _make_fernet,
)
from hub.apps.webhooks.models import Webhook, WebhookStatus

OLD_KEY = "old-encryption-key-for-testing"
NEW_KEY = "new-encryption-key-for-testing"


@pytest.mark.django_db(transaction=True)
class KeyRotationCommandTest(TestCase):
    """Test rotate_webhook_encryption_key management command."""

    def _create_webhooks(self, count=3):
        """Create webhooks with secrets encrypted under OLD_KEY."""
        from hub.apps.tenants.models import Tenant

        tenant, _ = Tenant.objects.get_or_create(
            name="key-rotation-test-tenant",
            defaults={"slug": "key-rotation-test"},
        )
        old_fernet = _make_fernet(OLD_KEY)
        webhooks = []
        for i in range(count):
            secret_plaintext = f"my-secret-{i}"
            encrypted = _encrypt_with_key(secret_plaintext, old_fernet)
            wh = Webhook.objects.create(
                tenant=tenant,
                name=f"Rotation Test {i}",
                url=f"https://example.com/hook{i}",
                secret=encrypted,
                event_types=["asset.created"],
                status=WebhookStatus.ACTIVE,
                max_retries=5,
                retry_intervals=[1, 5, 30, 300, 1800],
            )
            webhooks.append((wh, secret_plaintext))
        return webhooks

    def test_rotation_re_encrypts_all_secrets(self):
        """After rotation, all secrets decrypt correctly with the new key."""
        wh_pairs = self._create_webhooks(3)
        new_fernet = _make_fernet(NEW_KEY)

        out = StringIO()
        call_command(
            "rotate_webhook_encryption_key",
            f"--old-key={OLD_KEY}",
            f"--new-key={NEW_KEY}",
            f"--tenant-id={wh_pairs[0][0].tenant_id}",
            stdout=out,
        )

        for wh, original_plaintext in wh_pairs:
            wh.refresh_from_db()
            decrypted = _decrypt_with_key(wh.secret, new_fernet)
            self.assertEqual(decrypted, original_plaintext)

        self.assertIn("Rotation complete: 3 rotated, 0 failed.", out.getvalue())

    def test_dry_run_does_not_save(self):
        """--dry-run verifies decrypt but does not change secrets."""
        wh_pairs = self._create_webhooks(2)

        # Record original secrets
        original_secrets = {str(wh.id): wh.secret for wh, _ in wh_pairs}

        out = StringIO()
        call_command(
            "rotate_webhook_encryption_key",
            f"--old-key={OLD_KEY}",
            f"--new-key={NEW_KEY}",
            f"--tenant-id={wh_pairs[0][0].tenant_id}",
            "--dry-run",
            stdout=out,
        )

        for wh, _ in wh_pairs:
            wh.refresh_from_db()
            self.assertEqual(wh.secret, original_secrets[str(wh.id)])

        self.assertIn("Dry run complete", out.getvalue())

    def test_same_key_raises_error(self):
        """Using same key for old and new raises CommandError."""
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command(
                "rotate_webhook_encryption_key",
                "--old-key=same-key",
                "--new-key=same-key",
            )
