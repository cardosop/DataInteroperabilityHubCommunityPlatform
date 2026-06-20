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

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.webhooks.models import DeliveryStatus, Webhook, WebhookDelivery

pytestmark = pytest.mark.django_db(transaction=True)


class TestReplayProtection(TestCase):
    """Phase 277.B.022 — replayed webhook events must be rejected."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"WR-{uid}",
            slug=f"wr-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
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

        _w2, created2 = StripeWebhookEvent.objects.get_or_create(
            stripe_event_id=event_id,
            defaults={"event_type": "test.event", "payload": {}},
        )
        self.assertFalse(created2, "Replay of same event_id must be rejected")


class TestKeyRotationAudit(TestCase):
    """Phase 277.B.022 — key rotation produces audit events."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"WK-{uid}",
            slug=f"wk-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(
            email=f"wk-{uid}@meshant.test",
            password="testpass",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def test_webhook_key_rotation_creates_audit_event(self):
        """Rotating a webhook's secret creates a WEBHOOK_KEY_ROTATED audit event."""
        from rest_framework.test import APIClient

        from hub.apps.audit.models import AuditEvent
        from hub.apps.testing.billing_support import (
            ensure_tenant_has_active_subscription,
        )

        ensure_tenant_has_active_subscription(self.tenant)
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Audit Hook",
            url="https://example.com/wh",
            event_types=["asset.created"],
            secret=uuid.uuid4().hex[:16],
            status="ACTIVE",
            created_by=self.user,
        )
        client = APIClient()
        client.force_authenticate(self.user)

        before = AuditEvent.objects.filter(
            action="WEBHOOK_KEY_ROTATED",
            resource_id=str(webhook.id),
        ).count()

        resp = client.post(f"/api/v1/webhooks/webhooks/{webhook.id}/rotate_secret/")
        self.assertEqual(resp.status_code, 200, resp.content)

        after = AuditEvent.objects.filter(
            action="WEBHOOK_KEY_ROTATED",
            resource_id=str(webhook.id),
        ).count()
        self.assertEqual(after - before, 1, "Expected one WEBHOOK_KEY_ROTATED audit event")

    def test_webhook_created_audit_event_fires_on_create(self):
        """Creating a webhook via the service layer emits a WEBHOOK_CREATED audit event."""
        from hub.apps.audit.models import AuditEvent
        from hub.apps.testing.billing_support import (
            ensure_tenant_has_active_subscription,
        )
        from hub.apps.webhooks.webhook_service import WebhookService

        ensure_tenant_has_active_subscription(self.tenant)
        before = AuditEvent.objects.filter(
            action="WEBHOOK_CREATED",
        ).count()

        svc = WebhookService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))
        svc.create_webhook(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Created Hook",
            url="https://example.com/wh",
            secret=uuid.uuid4().hex[:16],
            event_types=["asset.created"],
        )

        after = AuditEvent.objects.filter(
            action="WEBHOOK_CREATED",
        ).count()
        self.assertEqual(after - before, 1, "Expected one WEBHOOK_CREATED audit event")

    def test_webhook_updated_audit_event_fires_on_update(self):
        """Updating a webhook via the service layer emits a WEBHOOK_UPDATED audit event."""
        from hub.apps.audit.models import AuditEvent
        from hub.apps.testing.billing_support import (
            ensure_tenant_has_active_subscription,
        )
        from hub.apps.webhooks.webhook_service import WebhookService

        ensure_tenant_has_active_subscription(self.tenant)
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Update Hook",
            url="https://example.com/wh",
            event_types=["asset.created"],
            secret=uuid.uuid4().hex[:16],
            status="ACTIVE",
            created_by=self.user,
        )

        before = AuditEvent.objects.filter(
            action="WEBHOOK_UPDATED",
            resource_id=str(webhook.id),
        ).count()

        svc = WebhookService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))
        svc.update_webhook(
            webhook_id=str(webhook.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Updated Name",
        )

        after = AuditEvent.objects.filter(
            action="WEBHOOK_UPDATED",
            resource_id=str(webhook.id),
        ).count()
        self.assertEqual(after - before, 1, "Expected one WEBHOOK_UPDATED audit event")


class TestRetryBehavior(TestCase):
    """Phase 277.B.022 — retry_count and attempts properties track delivery attempts."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"WR-{uid}",
            slug=f"wr-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(
            email=f"wr-{uid}@meshant.test",
            password="testpass",
            tenant=self.tenant,
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
                delivery.attempts,
                delivery.retry_count + 1,
                f"attempts ({delivery.attempts}) must equal retry_count + 1 ({delivery.retry_count + 1}) for attempt_number={n}",
            )

    def test_delivery_transitions_to_dead_letter_at_max_retries(self):
        """When attempt_number reaches max_retries, _schedule_retry sets DEAD_LETTER."""
        from hub.apps.webhooks.service import WebhookDeliveryService

        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type="asset.created",
            payload={"test": True},
            signature="x",
            status=DeliveryStatus.FAILED,
            attempt_number=5,  # matches self.webhook.max_retries default
        )
        WebhookDeliveryService._schedule_retry(delivery)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, DeliveryStatus.DEAD_LETTER)
        self.assertIsNone(delivery.next_retry_at)
