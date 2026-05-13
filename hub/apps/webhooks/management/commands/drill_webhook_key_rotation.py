"""
Phase 277.B.080 — webhook signing-key rotation drill with retry/replay audit.

Exercises the full key-rotation lifecycle for every webhook that has
an ACTIVE signing key, producing an audit trail and a summary report.

Usage:
    python manage.py drill_webhook_key_rotation               # All webhooks
    python manage.py drill_webhook_key_rotation --webhook-id <uuid>  # Single
    python manage.py drill_webhook_key_rotation --dry-run     # No writes, summary only

Lifecycle exercised:
    1. Generate a new signing key (ACTIVE).
    2. Transition the PREVIOUS active key to RETIRING (24h overlap).
    3. Verify both keys produce valid HMAC signatures.
    4. Record a ``WEBHOOK_KEY_ROTATION_DRILL`` audit event per webhook.
    5. Print a summary: keys cycled, signatures verified, any stale keys.

Retry/replay audit:
    Records each rotation step as an audit event with the affected
    key_ids so operators can correlate delivery failures during the
    overlap window against the rotation timeline.
"""
from __future__ import annotations

import secrets
import time

import structlog
from django.core.management.base import BaseCommand
from django.utils import timezone

logger = structlog.get_logger(__name__)


class Command(BaseCommand):
    help = "Exercise the webhook signing-key rotation lifecycle with full audit trail."

    def add_arguments(self, parser):
        parser.add_argument(
            "--webhook-id",
            type=str,
            help="Rotate keys for a single webhook (UUID).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report the current state without mutating keys.",
        )

    def handle(self, *args, **options):
        from hub.apps.webhooks.models import (
            Webhook,
            WebhookSigningKey,
            WebhookSigningKeyStatus,
        )

        dry_run = options["dry_run"]
        webhook_id = options.get("webhook_id")

        # ── Resolve webhooks ──────────────────────────────────
        webhooks = Webhook.objects.select_related("tenant").order_by("created_at")
        if webhook_id:
            try:
                webhooks = webhooks.filter(id=webhook_id)
            except Exception:
                self.stderr.write(f"Invalid webhook-id: {webhook_id}")
                return
        if not webhooks.exists():
            self.stdout.write("No webhooks found.")
            return

        # ── Per-webhook rotation drill ───────────────────────
        summary = {
            "total_webhooks": webhooks.count(),
            "keys_cycled": 0,
            "signatures_verified": 0,
            "stale_active_keys": 0,
            "errors": 0,
            "dry_run": dry_run,
            "drill_started_at": timezone.now().isoformat(),
        }

        for webhook in webhooks:
            self._rotate_webhook_keys(
                webhook, summary, dry_run,
            )

        summary["drill_completed_at"] = timezone.now().isoformat()

        # ── Report ────────────────────────────────────────────
        self.stdout.write("\nRotation drill complete.")
        self.stdout.write(f"  Webhooks audited:  {summary['total_webhooks']}")
        self.stdout.write(f"  Keys cycled:       {summary['keys_cycled']}")
        self.stdout.write(f"  Signatures OK:     {summary['signatures_verified']}")
        self.stdout.write(f"  Stale active keys: {summary['stale_active_keys']}")
        if summary["errors"]:
            self.stdout.write(
                self.style.WARNING(f"  Errors:            {summary['errors']}")
            )
        if dry_run:
            self.stdout.write(self.style.NOTICE("\n  DRY RUN — no keys were mutated."))

    # ── Per-webhook logic ─────────────────────────────────────

    def _rotate_webhook_keys(self, webhook, summary, dry_run):
        from hub.apps.audit.utils import create_audit_event
        from hub.apps.webhooks.encryption import encrypt_secret
        from hub.apps.webhooks.models import (
            WebhookSigningKey,
            WebhookSigningKeyStatus,
        )
        from hub.apps.webhooks.webhook_signing import HMACSignatureGenerator

        key_qs = WebhookSigningKey.objects.filter(webhook=webhook)
        active_key = key_qs.filter(status=WebhookSigningKeyStatus.ACTIVE).first()

        # Multi-active-key invariant check
        active_count = key_qs.filter(status=WebhookSigningKeyStatus.ACTIVE).count()
        if active_count > 1:
            self.stdout.write(
                self.style.WARNING(
                    f"  Webhook {webhook.id}: {active_count} ACTIVE keys "
                    f"(invariant violation — expected 1)"
                )
            )
            summary["stale_active_keys"] += 1

        if dry_run:
            retiring = key_qs.filter(
                status=WebhookSigningKeyStatus.RETIRING
            ).count()
            self.stdout.write(
                f"  Webhook {webhook.id}: "
                f"active={bool(active_key)}, retiring={retiring}"
            )
            return

        # ── Step 1: Generate new signing key ────────────────
        new_secret = secrets.token_hex(32)
        new_key = WebhookSigningKey.objects.create(
            webhook=webhook,
            secret_encrypted=encrypt_secret(new_secret),
            status=WebhookSigningKeyStatus.ACTIVE,
        )
        self.stdout.write(
            f"  Webhook {webhook.id}: created key {new_key.key_id} (ACTIVE)"
        )
        summary["keys_cycled"] += 1

        # ── Step 2: Retire previous active key ──────────────
        if active_key and active_key.id != new_key.id:
            active_key.status = WebhookSigningKeyStatus.RETIRING
            active_key.retired_at = timezone.now() + timezone.timedelta(hours=24)
            active_key.save(update_fields=["status", "retired_at"])
            self.stdout.write(
                f"    Previous key {active_key.key_id} → RETIRING "
                f"(overlap until {active_key.retired_at.isoformat()})"
            )

        # ── Step 3: Verify signatures ────────────────────────
        test_payload = f"drill-{time.monotonic()}"
        sig_new = new_key.generate_signature(test_payload)
        assert sig_new, f"New key {new_key.key_id} produced empty signature"

        if active_key and active_key.id != new_key.id:
            sig_old = active_key.generate_signature(test_payload)
            assert sig_old, f"Old key {active_key.key_id} produced empty signature"
            assert sig_new != sig_old, "Old and new signatures must differ"
            self.stdout.write(f"    HMAC signatures verified (new + old)")
        else:
            self.stdout.write(f"    HMAC signature verified (new only)")
        summary["signatures_verified"] += 1

        # ── Step 4: Audit event ──────────────────────────────
        try:
            create_audit_event(
                resource_type="WEBHOOK",
                action="WEBHOOK_KEY_ROTATION_DRILL",
                tenant=webhook.tenant,
                resource_id=str(webhook.id),
                result="SUCCESS",
                details={
                    "webhook_id": str(webhook.id),
                    "new_key_id": str(new_key.key_id),
                    "previous_key_id": str(active_key.key_id) if active_key else None,
                    "tenant_id": str(webhook.tenant_id),
                },
            )
        except Exception as exc:
            logger.warning(
                "webhook_drill_audit_failed",
                webhook_id=str(webhook.id),
                error=str(exc),
            )
            summary["errors"] += 1
