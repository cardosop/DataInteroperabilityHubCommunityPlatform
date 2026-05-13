"""
Phase 277.B.080 — webhook signing-key rotation drill tests.
"""
from io import StringIO

import pytest
from django.core.management import call_command
from django.test import TestCase

from hub.apps.tenants.models import Tenant, TenantStatus
from hub.apps.webhooks.models import (
    Webhook,
    WebhookSigningKey,
    WebhookSigningKeyStatus,
)

pytestmark = pytest.mark.django_db(transaction=True)


class KeyRotationDrillTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tenant = Tenant.objects.create(
            name="Drill Tenant", slug="drill-tenant", status=TenantStatus.ACTIVE,
        )
        cls.webhook = Webhook.objects.create(
            tenant=cls.tenant,
            name="Drill Webhook",
            url="https://example.com/webhook",
            event_types=["asset.created"],
        )

    def test_dry_run_reports_no_mutations(self):
        """--dry-run prints state without creating or modifying keys."""
        out = StringIO()
        call_command("drill_webhook_key_rotation", "--dry-run", stdout=out)
        output = out.getvalue()
        self.assertIn("DRY RUN", output)
        self.assertIn("no keys were mutated", output.lower())
        # No keys should have been created
        self.assertEqual(
            WebhookSigningKey.objects.filter(webhook=self.webhook).count(), 0,
        )

    def test_drill_creates_active_key(self):
        """First drill creates an ACTIVE signing key."""
        out = StringIO()
        call_command("drill_webhook_key_rotation", stdout=out)
        keys = WebhookSigningKey.objects.filter(webhook=self.webhook)
        self.assertEqual(keys.count(), 1)
        self.assertEqual(keys[0].status, WebhookSigningKeyStatus.ACTIVE)

    def test_drill_cycles_previous_key_to_retiring(self):
        """Second drill retires the previous ACTIVE key."""
        out = StringIO()
        call_command("drill_webhook_key_rotation", stdout=out)
        call_command("drill_webhook_key_rotation", stdout=out)

        keys = WebhookSigningKey.objects.filter(webhook=self.webhook)
        # Two keys total: one RETIRING, one ACTIVE
        self.assertEqual(keys.count(), 2)
        statuses = {k.status for k in keys}
        self.assertEqual(statuses, {"ACTIVE", "RETIRING"})

    def test_drill_verifies_signatures(self):
        """Drill output confirms signature verification."""
        out = StringIO()
        # First drill (no previous key)
        call_command("drill_webhook_key_rotation", stdout=out)
        self.assertIn("HMAC signature verified", out.getvalue())

        # Second drill (old + new signature verification)
        out2 = StringIO()
        call_command("drill_webhook_key_rotation", stdout=out2)
        self.assertIn("HMAC signatures verified (new + old)", out2.getvalue())

    def test_drill_with_webhook_id(self):
        """--webhook-id drills a single webhook."""
        out = StringIO()
        call_command(
            "drill_webhook_key_rotation",
            f"--webhook-id={self.webhook.id}",
            stdout=out,
        )
        self.assertEqual(
            WebhookSigningKey.objects.filter(webhook=self.webhook).count(), 1,
        )
        self.assertIn("Webhook", out.getvalue())

    def test_drill_invariant_no_duplicate_active_keys(self):
        """After drill, exactly one ACTIVE key exists per webhook."""
        call_command("drill_webhook_key_rotation", stdout=StringIO())
        call_command("drill_webhook_key_rotation", stdout=StringIO())
        call_command("drill_webhook_key_rotation", stdout=StringIO())

        active = WebhookSigningKey.objects.filter(
            webhook=self.webhook,
            status=WebhookSigningKeyStatus.ACTIVE,
        )
        self.assertEqual(active.count(), 1)

    def test_drill_output_includes_summary(self):
        """Output includes a summary with key counts and status."""
        out = StringIO()
        call_command("drill_webhook_key_rotation", stdout=out)
        output = out.getvalue()
        self.assertIn("Rotation drill complete", output)
        self.assertIn("Keys cycled:", output)
        self.assertIn("Signatures", output)

    def test_drill_generates_distinct_key_ids(self):
        """Each rotation generates a unique key_id."""
        out = StringIO()
        call_command("drill_webhook_key_rotation", stdout=out)
        call_command("drill_webhook_key_rotation", stdout=StringIO())
        call_command("drill_webhook_key_rotation", stdout=StringIO())

        key_ids = list(
            WebhookSigningKey.objects.filter(webhook=self.webhook)
            .values_list("key_id", flat=True)
        )
        self.assertEqual(len(key_ids), len(set(key_ids)), "Key IDs must be unique")

    def test_drill_creates_audit_event(self):
        """Each drill creates a WEBHOOK_KEY_ROTATION_DRILL audit event."""
        from hub.apps.audit.models import AuditEvent

        before = AuditEvent.objects.filter(
            action="WEBHOOK_KEY_ROTATION_DRILL"
        ).count()
        call_command("drill_webhook_key_rotation", stdout=StringIO())
        after = AuditEvent.objects.filter(
            action="WEBHOOK_KEY_ROTATION_DRILL"
        ).count()
        self.assertEqual(after - before, 1)
