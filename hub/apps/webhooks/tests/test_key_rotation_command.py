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

    # ── W11.5 — non-Fernet ciphertexts must be SKIPPED, never wrapped ────

    def _create_webhook_with_secret(self, secret: str) -> Webhook:
        from hub.apps.tenants.models import Tenant

        tenant, _ = Tenant.objects.get_or_create(
            name="key-rotation-prefix-test-tenant",
            defaults={"slug": "key-rotation-prefix-test"},
        )
        return Webhook.objects.create(
            tenant=tenant,
            name=f"Prefix Test {secret[:12]}",
            url="https://example.com/prefix-hook",
            secret=secret,
            event_types=["asset.created"],
            status=WebhookStatus.ACTIVE,
            max_retries=5,
            retry_intervals=[1, 5, 30, 300, 1800],
        )

    def test_rotation_skips_aws_kms_prefixed_rows(self):
        """An aws-kms: ciphertext is NOT Fernet — rotation must leave it
        byte-identical (the pre-fix loop wrapped it as plaintext,
        double-encrypting the KMS blob)."""
        kms_secret = "aws-kms:QUJDREVGRw=="
        wh = self._create_webhook_with_secret(kms_secret)

        out = StringIO()
        call_command(
            "rotate_webhook_encryption_key",
            f"--old-key={OLD_KEY}",
            f"--new-key={NEW_KEY}",
            f"--tenant-id={wh.tenant_id}",
            stdout=out,
        )

        wh.refresh_from_db()
        self.assertEqual(wh.secret, kms_secret)
        self.assertIn("0 rotated", out.getvalue())

    def test_rotation_skips_vault_prefixed_rows(self):
        """Legacy vault:v1: rows are not Fernet either — untouched."""
        vault_secret = "vault:v1:hvs.abcd1234"
        wh = self._create_webhook_with_secret(vault_secret)

        out = StringIO()
        call_command(
            "rotate_webhook_encryption_key",
            f"--old-key={OLD_KEY}",
            f"--new-key={NEW_KEY}",
            f"--tenant-id={wh.tenant_id}",
            stdout=out,
        )

        wh.refresh_from_db()
        self.assertEqual(wh.secret, vault_secret)

    def test_rotation_migrates_plaintext_rows(self):
        """Legacy plaintext secrets are opportunistically encrypted with
        the NEW key (consistent with encrypt_secret's save-path
        migration).  The row is written via ``update()`` because
        ``Webhook.save()`` re-encrypts — a plaintext row only exists as
        pre-migration legacy data."""
        plaintext = "legacy-plain-secret"
        wh = self._create_webhook_with_secret("placeholder")
        Webhook.objects.filter(pk=wh.pk).update(secret=plaintext)

        out = StringIO()
        call_command(
            "rotate_webhook_encryption_key",
            f"--old-key={OLD_KEY}",
            f"--new-key={NEW_KEY}",
            f"--tenant-id={wh.tenant_id}",
            stdout=out,
        )

        wh.refresh_from_db()
        self.assertEqual(_decrypt_with_key(wh.secret, _make_fernet(NEW_KEY)), plaintext)
