"""
Phase 86.3 — webhooks/tasks.py tests.

Tests deliver_webhook RQ task and retry_delivery service method.
Uses real DB records; only _attempt_delivery is patched to avoid
real HTTP calls to subscriber URLs.
"""

import uuid
from unittest.mock import patch

from django.test import TestCase

from hub.apps.tenants.models import Tenant
from hub.apps.webhooks.models import (
    DeliveryStatus,
    Webhook,
    WebhookDelivery,
    WebhookEventType,
    WebhookStatus,
)
from hub.apps.webhooks.service import WebhookDeliveryService

_MODEL = "hub.apps.webhooks.models.WebhookDelivery"
_SERVICE_ATTEMPT = "hub.apps.webhooks.service.WebhookDeliveryService._attempt_delivery"


def _make_delivery(tenant=None, status=DeliveryStatus.PENDING, attempt_number=0):
    """Create a tenant + webhook + delivery in the real DB."""
    if tenant is None:
        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"Task-{uid}",
            slug=f"task-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
    webhook = Webhook.objects.create(
        tenant=tenant,
        name="Task Webhook",
        url="https://example.com/webhook",
        event_types=[WebhookEventType.ASSET_CREATED],
        secret=uuid.uuid4().hex[:16],
        status=WebhookStatus.ACTIVE,
        max_retries=5,
    )
    delivery = WebhookDelivery.objects.create(
        webhook=webhook,
        event_type=WebhookEventType.ASSET_CREATED,
        payload={"test": True},
        signature="x",
        status=status,
        attempt_number=attempt_number,
    )
    return delivery


class DeliverWebhookTaskTest(TestCase):
    """Integration tests for deliver_webhook RQ task."""

    @patch(_SERVICE_ATTEMPT)
    def test_delivery_success(self, mock_attempt):
        """deliver_webhook loads the delivery from DB and calls _attempt_delivery."""
        delivery = _make_delivery()

        from hub.apps.webhooks.tasks import deliver_webhook

        deliver_webhook(str(delivery.id))

        mock_attempt.assert_called_once()
        called_delivery = mock_attempt.call_args[0][0]
        self.assertEqual(str(called_delivery.id), str(delivery.id))
        self.assertEqual(called_delivery.event_type, WebhookEventType.ASSET_CREATED)

    def test_missing_delivery_logs_error_and_returns_gracefully(self):
        """When the delivery ID does not exist, the task returns without raising."""
        from hub.apps.webhooks.models import WebhookDelivery
        from hub.apps.webhooks.tasks import deliver_webhook

        # Ensure the DB is set up (creates tables), then use nonexistent ID.
        nonexistent_id = "00000000-0000-0000-0000-000000000000"
        self.assertFalse(WebhookDelivery.objects.filter(id=nonexistent_id).exists())

        with self.assertLogs("hub.apps.webhooks.tasks", level="ERROR") as log_cm:
            deliver_webhook(nonexistent_id)

        self.assertTrue(
            any("webhook_delivery_not_found" in record for record in log_cm.output),
            "Expected 'webhook_delivery_not_found' ERROR log entry",
        )

    @patch(_SERVICE_ATTEMPT)
    def test_delivery_error_propagates(self, mock_attempt):
        """When _attempt_delivery raises, the task propagates the error so RQ can retry."""
        delivery = _make_delivery()
        mock_attempt.side_effect = ConnectionError("timeout")

        from hub.apps.webhooks.tasks import deliver_webhook

        with self.assertRaises(ConnectionError):
            deliver_webhook(str(delivery.id))


class RetryDeliveryTest(TestCase):
    """Tests for WebhookDeliveryService.retry_delivery edge cases."""

    def test_retry_already_successful_returns_false(self):
        """Calling retry_delivery on a SUCCESS delivery returns False."""
        delivery = _make_delivery(status=DeliveryStatus.SUCCESS)
        result = WebhookDeliveryService.retry_delivery(str(delivery.id))
        self.assertFalse(result)

    def test_retry_nonexistent_delivery_returns_false(self):
        """Calling retry_delivery with a nonexistent ID returns False."""
        result = WebhookDeliveryService.retry_delivery(
            "00000000-0000-0000-0000-000000000000"
        )
        self.assertFalse(result)

    @patch(_SERVICE_ATTEMPT)
    def test_retry_dead_letter_resets_to_pending(self, mock_attempt):
        """retry_delivery resets a DEAD_LETTER delivery to PENDING and attempts delivery."""
        delivery = _make_delivery(status=DeliveryStatus.DEAD_LETTER, attempt_number=5)
        result = WebhookDeliveryService.retry_delivery(str(delivery.id))
        self.assertTrue(result)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, DeliveryStatus.PENDING)
        self.assertEqual(delivery.attempt_number, 0)
        mock_attempt.assert_called_once()
