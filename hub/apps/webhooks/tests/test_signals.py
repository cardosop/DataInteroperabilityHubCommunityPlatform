"""TR.G.8 — Webhook signal handler tests: delivery task enqueued on model event."""

import uuid

import pytest
from django.test import TestCase, override_settings

from hub.apps.tenants.models import Tenant
from hub.apps.webhooks.models import (
    Webhook,
    WebhookDelivery,
    WebhookEventType,
    WebhookStatus,
)
from hub.apps.webhooks.service import WebhookDeliveryService

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.integration
class TestWebhookSignalHandlers(TestCase):
    """Delivery triggered on model event. Tenant-scoped delivery only."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"sig-{uid}",
            slug=f"sig-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="test-webhook",
            url="https://example.com/webhook",
            event_types=[WebhookEventType.ASSET_CREATED],
            secret=uuid.uuid4().hex[:16],
            status=WebhookStatus.ACTIVE,
        )

    @pytest.mark.integration
    @override_settings(WEBHOOK_ASYNC_DELIVERY=False, WEBHOOK_SSRF_ENABLED=False)
    def test_webhook_triggered_on_matching_event_type(self):
        """trigger_webhook creates a WebhookDelivery for a matching subscription."""
        before = WebhookDelivery.objects.filter(webhook=self.webhook).count()

        count = WebhookDeliveryService.trigger_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.ASSET_CREATED,
            resource_type="ASSET",
            resource_id=str(uuid.uuid4()),
            event_data={"event_id": str(uuid.uuid4())},
        )

        self.assertEqual(count, 1, "Expected exactly one webhook to be triggered")
        deliveries = WebhookDelivery.objects.filter(webhook=self.webhook)
        self.assertEqual(deliveries.count() - before, 1)
        delivery = deliveries.order_by("-created_at").first()
        self.assertEqual(delivery.event_type, WebhookEventType.ASSET_CREATED)

    @pytest.mark.integration
    @override_settings(WEBHOOK_ASYNC_DELIVERY=False, WEBHOOK_SSRF_ENABLED=False)
    def test_webhook_not_triggered_on_non_matching_event_type(self):
        """trigger_webhook does NOT create a delivery for event types the webhook doesn't subscribe to."""
        before = WebhookDelivery.objects.filter(webhook=self.webhook).count()

        count = WebhookDeliveryService.trigger_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.CONTRACT_CREATED,
            resource_type="CONTRACT",
            resource_id=str(uuid.uuid4()),
            event_data={"event_id": str(uuid.uuid4())},
        )

        self.assertEqual(count, 0, "Expected zero webhooks triggered for non-matching event type")
        after = WebhookDelivery.objects.filter(webhook=self.webhook).count()
        self.assertEqual(after, before)

    @pytest.mark.integration
    @override_settings(WEBHOOK_ASYNC_DELIVERY=False, WEBHOOK_SSRF_ENABLED=False)
    def test_tenant_scoped_delivery_only(self):
        """trigger_webhook only delivers to webhooks in the specified tenant."""
        uid_b = uuid.uuid4().hex[:8]
        tenant_b = Tenant.objects.create(
            name=f"sig-{uid_b}",
            slug=f"sig-{uid_b}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        webhook_b = Webhook.objects.create(
            tenant=tenant_b,
            name="webhook-b",
            url="https://b.example.com/webhook",
            event_types=[WebhookEventType.ASSET_CREATED],
            secret=uuid.uuid4().hex[:16],
            status=WebhookStatus.ACTIVE,
        )

        # Trigger in tenant A — only tenant A's webhook should fire.
        count = WebhookDeliveryService.trigger_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.ASSET_CREATED,
            resource_type="ASSET",
            resource_id=str(uuid.uuid4()),
            event_data={"event_id": str(uuid.uuid4())},
        )

        self.assertEqual(count, 1)
        self.assertEqual(
            WebhookDelivery.objects.filter(webhook=self.webhook).count(),
            1,
            "Tenant A's webhook should have received the delivery",
        )
        self.assertEqual(
            WebhookDelivery.objects.filter(webhook=webhook_b).count(),
            0,
            "Tenant B's webhook must NOT receive tenant A's event",
        )

        # Trigger in tenant B — only tenant B's webhook should fire.
        count_b = WebhookDeliveryService.trigger_webhook(
            tenant_id=str(tenant_b.id),
            event_type=WebhookEventType.ASSET_CREATED,
            resource_type="ASSET",
            resource_id=str(uuid.uuid4()),
            event_data={"event_id": str(uuid.uuid4())},
        )

        self.assertEqual(count_b, 1)
        self.assertEqual(
            WebhookDelivery.objects.filter(webhook=webhook_b).count(),
            1,
            "Tenant B's webhook should have received the delivery",
        )

    @pytest.mark.integration
    @override_settings(WEBHOOK_ASYNC_DELIVERY=False, WEBHOOK_SSRF_ENABLED=False)
    def test_paused_webhook_not_triggered(self):
        """trigger_webhook does NOT deliver to PAUSED webhooks."""
        self.webhook.status = WebhookStatus.PAUSED
        self.webhook.save(update_fields=["status"])

        before = WebhookDelivery.objects.filter(webhook=self.webhook).count()
        count = WebhookDeliveryService.trigger_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.ASSET_CREATED,
            resource_type="ASSET",
            resource_id=str(uuid.uuid4()),
            event_data={"event_id": str(uuid.uuid4())},
        )

        self.assertEqual(count, 0, "PAUSED webhook must not be triggered")
        self.assertEqual(WebhookDelivery.objects.filter(webhook=self.webhook).count(), before)

    @pytest.mark.integration
    @override_settings(WEBHOOK_ASYNC_DELIVERY=False, WEBHOOK_SSRF_ENABLED=False)
    def test_disabled_webhook_not_triggered(self):
        """trigger_webhook does NOT deliver to DISABLED webhooks."""
        self.webhook.status = WebhookStatus.DISABLED
        self.webhook.save(update_fields=["status"])

        before = WebhookDelivery.objects.filter(webhook=self.webhook).count()
        count = WebhookDeliveryService.trigger_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.ASSET_CREATED,
            resource_type="ASSET",
            resource_id=str(uuid.uuid4()),
            event_data={"event_id": str(uuid.uuid4())},
        )

        self.assertEqual(count, 0, "DISABLED webhook must not be triggered")
        self.assertEqual(WebhookDelivery.objects.filter(webhook=self.webhook).count(), before)
