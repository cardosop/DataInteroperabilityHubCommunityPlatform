"""
Phase 44 (44.4) — Rotate Webhook Encryption Key

Re-encrypts all webhook secrets from an old encryption key to a new one.
Processes in batches of 100 within transaction.atomic() for safety.
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from hub.apps.webhooks.encryption import _PREFIX
from hub.apps.webhooks.models import Webhook


def _make_fernet(key: str) -> Fernet:
    """Build a Fernet instance from an arbitrary key string."""
    derived = hashlib.sha256(key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(derived))


def _decrypt_with_key(value: str, fernet: Fernet) -> str:
    """Decrypt a v1:-prefixed secret using the given Fernet instance."""
    if not value.startswith(_PREFIX):
        return value  # legacy plaintext
    return fernet.decrypt(value[len(_PREFIX):].encode()).decode()


def _encrypt_with_key(plaintext: str, fernet: Fernet) -> str:
    """Encrypt a plaintext secret using the given Fernet instance."""
    ciphertext = fernet.encrypt(plaintext.encode()).decode()
    return _PREFIX + ciphertext


class Command(BaseCommand):
    help = "Re-encrypt all webhook secrets from an old encryption key to a new one."

    def add_arguments(self, parser):
        parser.add_argument(
            "--old-key", required=True, help="Current encryption key to decrypt secrets"
        )
        parser.add_argument(
            "--new-key", required=True, help="New encryption key to re-encrypt secrets"
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="Verify decryption succeeds without saving"
        )

    def handle(self, *args, **options):
        old_key = options["old_key"]
        new_key = options["new_key"]
        dry_run = options["dry_run"]

        if old_key == new_key:
            raise CommandError("Old key and new key must be different.")

        old_fernet = _make_fernet(old_key)
        new_fernet = _make_fernet(new_key)

        total = Webhook.objects.count()
        self.stdout.write(f"Found {total} webhook(s) to process.")

        if dry_run:
            # Verify decrypt on up to first 5
            sample = Webhook.objects.all()[:5]
            for wh in sample:
                try:
                    plaintext = _decrypt_with_key(wh.secret, old_fernet)
                    self.stdout.write(
                        self.style.SUCCESS(f"  ✓ {wh.id}: decrypt OK (len={len(plaintext)})")
                    )
                except (InvalidToken, ValueError) as e:
                    self.stdout.write(
                        self.style.ERROR(f"  ✗ {wh.id}: decrypt FAILED — {e}")
                    )
            self.stdout.write(f"\nDry run complete. {total} webhook(s) would be rotated.")
            return

        BATCH_SIZE = 100
        rotated = 0
        failed = 0

        webhooks = Webhook.objects.all().order_by("id")
        batch = []

        for wh in webhooks.iterator(chunk_size=BATCH_SIZE):
            try:
                plaintext = _decrypt_with_key(wh.secret, old_fernet)
                wh.secret = _encrypt_with_key(plaintext, new_fernet)
                batch.append(wh)
                rotated += 1
            except (InvalidToken, ValueError) as e:
                self.stderr.write(self.style.ERROR(f"Failed to rotate {wh.id}: {e}"))
                failed += 1

            if len(batch) >= BATCH_SIZE:
                with transaction.atomic():
                    Webhook.objects.bulk_update(batch, ["secret"])
                batch = []

        # Flush remaining batch
        if batch:
            with transaction.atomic():
                Webhook.objects.bulk_update(batch, ["secret"])

        self.stdout.write(
            self.style.SUCCESS(f"Rotation complete: {rotated} rotated, {failed} failed.")
        )
