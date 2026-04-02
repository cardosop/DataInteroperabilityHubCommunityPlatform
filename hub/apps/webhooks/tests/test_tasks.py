"""
Phase 86.3 — webhooks/tasks.py tests.

Tests deliver_webhook: success, missing delivery, error propagation.
Patches at the source module since imports are inside the function body.
"""
import uuid
from unittest.mock import patch, MagicMock

import pytest
from django.test import TestCase


_MODELS = "hub.apps.webhooks.models"
_SERVICE = "hub.apps.webhooks.service"


class DeliverWebhookTaskTest(TestCase):

    @patch(f"{_SERVICE}.WebhookDeliveryService._attempt_delivery")
    @patch(f"{_MODELS}.WebhookDelivery.objects")
    def test_delivery_success(self, mock_qs, mock_attempt):
        mock_delivery = MagicMock()
        mock_delivery.webhook_id = uuid.uuid4()
        mock_delivery.event_type = "contract.created"
        mock_qs.select_related.return_value.get.return_value = mock_delivery

        from hub.apps.webhooks.tasks import deliver_webhook
        deliver_webhook(str(uuid.uuid4()))
        mock_attempt.assert_called_once_with(mock_delivery)

    @patch(f"{_MODELS}.WebhookDelivery.objects")
    def test_missing_delivery_returns_gracefully(self, mock_qs):
        from hub.apps.webhooks.models import WebhookDelivery
        mock_qs.select_related.return_value.get.side_effect = (
            WebhookDelivery.DoesNotExist
        )
        from hub.apps.webhooks.tasks import deliver_webhook
        # Should NOT raise
        deliver_webhook(str(uuid.uuid4()))

    @patch(f"{_SERVICE}.WebhookDeliveryService._attempt_delivery")
    @patch(f"{_MODELS}.WebhookDelivery.objects")
    def test_delivery_error_propagates(self, mock_qs, mock_attempt):
        mock_delivery = MagicMock()
        mock_delivery.webhook_id = uuid.uuid4()
        mock_delivery.event_type = "asset.updated"
        mock_qs.select_related.return_value.get.return_value = mock_delivery
        mock_attempt.side_effect = ConnectionError("timeout")

        from hub.apps.webhooks.tasks import deliver_webhook
        with self.assertRaises(ConnectionError):
            deliver_webhook(str(uuid.uuid4()))

    @patch(f"{_SERVICE}.WebhookDeliveryService._attempt_delivery")
    @patch(f"{_MODELS}.WebhookDelivery.objects")
    def test_select_related_webhook(self, mock_qs, mock_attempt):
        mock_delivery = MagicMock()
        mock_delivery.webhook_id = uuid.uuid4()
        mock_delivery.event_type = "x"
        mock_qs.select_related.return_value.get.return_value = mock_delivery

        from hub.apps.webhooks.tasks import deliver_webhook
        deliver_webhook("d1")
        mock_qs.select_related.assert_called_with("webhook")
