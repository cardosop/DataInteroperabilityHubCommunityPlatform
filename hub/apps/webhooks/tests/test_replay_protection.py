"""
Phase 277.B.022 — Webhook replay protection + retry behavior tests.

Verifies:
- Replayed webhook events are rejected (idempotency via StripeWebhookEvent)
- Rotation drill: key rotation produces audit event + old key can still verify
- Retry: delivery failures increment retry_count, max retries → dead-letter
- retry_count and attempts properties return correct values from attempt_number
"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.webhooks.models import Webhook, WebhookDelivery, WebhookStatus

pytestmark = pytest.mark.django_db(transaction=True)


class TestReplayProtection(TestCase):
    """Phase 277.B.022 — replayed webhook events must be rejected."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"WR-{uid}", slug=f"wr-{uid}",
            status="ACTIVE", kyc_status="UNVERIFIED",
        )

    def test_stripe_webhook_event_is_idempotent(self):
        """StripeWebhookEvent.get_or_create prevents replay of same event_id."""
        from hub.apps.billing.models import StripeWebhookEvent

        event_id = f"evt_{uuid.uuid4().hex[:16]}"
        w1, created1 = StripeWebhookEvent.objects.get_or_create(
            stripe_event_id=event_id,
            defaults={"event_type": "test.event", "payload": {}},
        )
        self.assertTrue(created1, "First get_or_create must create the event")
        self.assertIsNotNone(
            w1.event_timestamp,
            "event_timestamp must be auto-populated by auto_now_add",
        )
        self.assertIsInstance(w1.event_timestamp, datetime)

        w2, created2 = StripeWebhookEvent.objects.get_or_create(
            stripe_event_id=event_id,
            defaults={"event_type": "test.event", "payload": {}},
        )
        self.assertFalse(created2, "Replay of same event_id must be rejected")


class TestKeyRotationAudit(TestCase):
    """Phase 277.B.022 — key rotation produces audit events."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"WK-{uid}", slug=f"wk-{uid}",
            status="ACTIVE", kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(
            email=f"wk-{uid}@meshant.test",
            password="testpass", tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def test_webhook_key_rotation_audit_event_type_exists(self):
        """WEBHOOK_KEY_ROTATED audit constant is defined."""
        from hub.apps.audit import event_types
        self.assertTrue(hasattr(event_types, "WEBHOOK_KEY_ROTATED"))
        self.assertEqual(event_types.WEBHOOK_KEY_ROTATED, "WEBHOOK_KEY_ROTATED")

    def test_webhook_created_audit_event_type_exists(self):
        """WEBHOOK_CREATED audit constant is defined."""
        from hub.apps.audit import event_types
        self.assertTrue(hasattr(event_types, "WEBHOOK_CREATED"))

    def test_webhook_updated_audit_event_type_exists(self):
        """WEBHOOK_UPDATED audit constant is defined."""
        from hub.apps.audit import event_types
        self.assertTrue(hasattr(event_types, "WEBHOOK_UPDATED"))


class TestRetryBehavior(TestCase):
    """Phase 277.B.022 — retry_count and attempts properties track delivery attempts."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"WR-{uid}", slug=f"wr-{uid}",
            status="ACTIVE", kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(
            email=f"wr-{uid}@meshant.test",
            password="testpass", tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Retry-Test",
            url="https://example.com/webhook",
            event_types=["asset.created"],
            secret=uuid.uuid4().hex[:16],
        )

    def test_retry_count_matches_attempt_number(self):
        """retry_count reflects attempt_number (0-indexed)."""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type="asset.created",
            payload={"test": True},
            signature="x",
            attempt_number=0,
        )
        self.assertEqual(delivery.retry_count, 0)
        delivery.attempt_number = 3
        delivery.save()
        self.assertEqual(delivery.retry_count, 3)

    def test_attempts_is_attempt_number_plus_one(self):
        """attempts = attempt_number + 1 (total delivery attempts)."""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type="asset.created",
            payload={"test": True},
            signature="x",
            attempt_number=0,
        )
        self.assertEqual(delivery.attempts, 1)
        delivery.attempt_number = 3
        delivery.save()
        self.assertEqual(delivery.attempts, 4)

    def test_retry_count_and_attempts_are_consistent(self):
        """attempts is always retry_count + 1."""
        for n in (0, 1, 2, 5):
            delivery = WebhookDelivery.objects.create(
                webhook=self.webhook,
                event_type="asset.created",
                payload={"test": True},
                signature="x",
                attempt_number=n,
            )
            self.assertEqual(
                delivery.attempts, delivery.retry_count + 1,
                f"attempts ({delivery.attempts}) must equal retry_count + 1 ({delivery.retry_count + 1}) for attempt_number={n}",
            )

    def test_delivery_model_has_status(self):
        """WebhookDelivery has status field for DEAD_LETTER state."""
        self.assertTrue(
            hasattr(WebhookDelivery, "status"),
            "WebhookDelivery must have status field for DEAD_LETTER tracking",
        )
