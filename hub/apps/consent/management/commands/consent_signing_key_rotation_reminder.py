"""
Remind operators to rotate per-tenant consent HMAC keys (90-day cadence).

The application does not write AWS Secrets Manager — this command is the
scheduled hook paired with the Helm CronJob. Operators prepend a new 32-byte
hex key per tenant to ``CONSENT_SIGNING_KEYS_JSON`` (max 3 keys).
"""

from __future__ import annotations
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Consent signing-key rotation reminder (Phase 232.1 / 90-day cadence)."

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.NOTICE(
                "Consent signing keys: prepend a new random 32-byte hex key per tenant to "
                "CONSENT_SIGNING_KEYS_JSON in Secrets Manager (keep at most 3 keys per tenant, "
                "newest first). Reload pods after ExternalSecret sync."
            )
        )
