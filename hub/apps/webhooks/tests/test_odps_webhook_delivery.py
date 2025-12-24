"""
Integration tests for ODPS webhook delivery.

Tests that ODPS events properly trigger webhook delivery with correct filtering.
"""

import json
import uuid
from unittest.mock import patch, MagicMock

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from hub.apps.webhooks.models import (
    Webhook,
    WebhookDelivery,
    WebhookEventType,
    WebhookStatus,
    DeliveryStatus,
)
from hub.apps.webhooks.service import WebhookDeliveryService
from hub.apps.webhooks.odps_webhook_errors import ODPSWebhookValidationError
from hub.apps.tenants.models import Tenant, TenantStatus, KYCStatus
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class ODPSWebhookDeliveryTest(TestCase):
    """Integration tests for ODPS webhook delivery"""

    def setUp(self):
        """Set up test fixtures"""
        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )

        # Create user
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
            display_name="Test User",
        )

    @patch('hub.apps.webhooks.service.requests.post')
    def test_trigger_odps_webhook_delivery(self, mock_post):
        """Test that ODPS events trigger webhook delivery"""
        # Create webhook subscribed to ODPS events
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="ODPS Webhook",
            url="https://example.com/webhook",
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response

        # Trigger ODPS webhook
        event_data = {
            "contract_id": str(uuid.uuid4()),
            "asset_id": str(uuid.uuid4()),
            "status": "ACTIVE",
        }

        count = WebhookDeliveryService.trigger_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.ODPS_CREATED,
            resource_type="ODPS",
            resource_id=str(uuid.uuid4()),
            event_data=event_data,
        )

        # Verify webhook was triggered
        self.assertEqual(count, 1)

        # Verify delivery was created
        deliveries = WebhookDelivery.objects.filter(webhook=webhook)
        self.assertEqual(deliveries.count(), 1)

        delivery = deliveries.first()
        self.assertEqual(delivery.event_type, WebhookEventType.ODPS_CREATED)
        self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)
        self.assertIsNotNone(delivery.delivered_at)

        # Verify HTTP request was made
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(call_args[0][0], webhook.url)
        self.assertEqual(call_args[1]["headers"]["X-Webhook-Event-Type"], WebhookEventType.ODPS_CREATED)

    @patch('hub.apps.webhooks.service.requests.post')
    def test_trigger_odps_webhook_convenience_method(self, mock_post):
        """Test trigger_odps_webhook() convenience method"""
        # Create webhook subscribed to ODPS events
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="ODPS Webhook",
            url="https://example.com/webhook",
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_UPDATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response

        # Trigger ODPS webhook using convenience method
        event_data = {
            "contract_id": str(uuid.uuid4()),
            "changes": {"status": "ACTIVE"},
        }

        count = WebhookDeliveryService.trigger_odps_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.ODPS_UPDATED,
            resource_type="ODPS",
            resource_id=str(uuid.uuid4()),
            event_data=event_data,
        )

        # Verify webhook was triggered
        self.assertEqual(count, 1)

        # Verify delivery was created
        deliveries = WebhookDelivery.objects.filter(webhook=webhook)
        self.assertEqual(deliveries.count(), 1)

        delivery = deliveries.first()
        self.assertEqual(delivery.event_type, WebhookEventType.ODPS_UPDATED)

    def test_trigger_odps_webhook_invalid_event_type(self):
        """Test that trigger_odps_webhook() raises error for non-ODPS events"""
        with self.assertRaises(ODPSWebhookValidationError) as cm:
            WebhookDeliveryService.trigger_odps_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.CONTRACT_CREATED,  # Not an ODPS event
                resource_type="CONTRACT",
                resource_id=str(uuid.uuid4()),
                event_data={},
            )

        self.assertIn("is not an ODPS event type", str(cm.exception))
        self.assertEqual(cm.exception.error_code, ODPSWebhookValidationError.ERROR_CODE_INVALID_EVENT_TYPE)

    @patch('hub.apps.webhooks.service.requests.post')
    def test_odps_webhook_filtering(self, mock_post):
        """Test that only webhooks subscribed to ODPS events receive deliveries"""
        # Create webhook subscribed to ODPS events
        odps_webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="ODPS Webhook",
            url="https://example.com/odps",
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        # Create webhook subscribed to contract events only
        contract_webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Contract Webhook",
            url="https://example.com/contract",
            secret="test-secret",
            event_types=[WebhookEventType.CONTRACT_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response

        # Trigger ODPS event
        event_data = {
            "contract_id": str(uuid.uuid4()),
        }

        count = WebhookDeliveryService.trigger_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.ODPS_CREATED,
            resource_type="ODPS",
            resource_id=str(uuid.uuid4()),
            event_data=event_data,
        )

        # Only ODPS webhook should receive delivery
        self.assertEqual(count, 1)

        # Verify only ODPS webhook has delivery
        odps_deliveries = WebhookDelivery.objects.filter(webhook=odps_webhook)
        self.assertEqual(odps_deliveries.count(), 1)

        contract_deliveries = WebhookDelivery.objects.filter(webhook=contract_webhook)
        self.assertEqual(contract_deliveries.count(), 0)

    @patch('hub.apps.webhooks.service.requests.post')
    def test_multiple_odps_webhooks_receive_delivery(self, mock_post):
        """Test that multiple webhooks subscribed to same ODPS event receive delivery"""
        # Create multiple webhooks subscribed to same ODPS event
        webhook1 = Webhook.objects.create(
            tenant=self.tenant,
            name="ODPS Webhook 1",
            url="https://example.com/webhook1",
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        webhook2 = Webhook.objects.create(
            tenant=self.tenant,
            name="ODPS Webhook 2",
            url="https://example.com/webhook2",
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response

        # Trigger ODPS event
        event_data = {
            "contract_id": str(uuid.uuid4()),
        }

        count = WebhookDeliveryService.trigger_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.ODPS_CREATED,
            resource_type="ODPS",
            resource_id=str(uuid.uuid4()),
            event_data=event_data,
        )

        # Both webhooks should receive delivery
        self.assertEqual(count, 2)

        # Verify both webhooks have deliveries
        deliveries1 = WebhookDelivery.objects.filter(webhook=webhook1)
        self.assertEqual(deliveries1.count(), 1)

        deliveries2 = WebhookDelivery.objects.filter(webhook=webhook2)
        self.assertEqual(deliveries2.count(), 1)

    def test_get_webhooks_for_odps_events(self):
        """Test get_webhooks_for_odps_events() service method"""
        # Create webhooks with different event types
        odps_webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="ODPS Webhook",
            url="https://example.com/odps",
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        contract_webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Contract Webhook",
            url="https://example.com/contract",
            secret="test-secret",
            event_types=[WebhookEventType.CONTRACT_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        mixed_webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Mixed Webhook",
            url="https://example.com/mixed",
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_CREATED, WebhookEventType.CONTRACT_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        # Get webhooks for ODPS events
        odps_webhooks = WebhookDeliveryService.get_webhooks_for_odps_events(str(self.tenant.id))

        webhook_ids = {w.id for w in odps_webhooks}
        self.assertIn(odps_webhook.id, webhook_ids)
        self.assertIn(mixed_webhook.id, webhook_ids)
        self.assertNotIn(contract_webhook.id, webhook_ids)

    def test_get_webhooks_for_event_type(self):
        """Test get_webhooks_for_event_type() service method"""
        # Create webhooks
        webhook1 = Webhook.objects.create(
            tenant=self.tenant,
            name="Webhook 1",
            url="https://example.com/1",
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        webhook2 = Webhook.objects.create(
            tenant=self.tenant,
            name="Webhook 2",
            url="https://example.com/2",
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_UPDATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        webhook3 = Webhook.objects.create(
            tenant=self.tenant,
            name="Webhook 3",
            url="https://example.com/3",
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_CREATED, WebhookEventType.ODPS_UPDATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        # Get webhooks for specific event type
        created_webhooks = WebhookDeliveryService.get_webhooks_for_event_type(
            str(self.tenant.id),
            WebhookEventType.ODPS_CREATED
        )

        webhook_ids = {w.id for w in created_webhooks}
        self.assertIn(webhook1.id, webhook_ids)
        self.assertIn(webhook3.id, webhook_ids)
        self.assertNotIn(webhook2.id, webhook_ids)

    @patch('hub.apps.webhooks.service.requests.post')
    def test_odps_webhook_payload_structure(self, mock_post):
        """Test that ODPS webhook payload has correct structure"""
        # Create webhook
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="ODPS Webhook",
            url="https://example.com/webhook",
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response

        # Trigger ODPS webhook
        contract_id = str(uuid.uuid4())
        resource_id = str(uuid.uuid4())
        event_data = {
            "contract_id": contract_id,
            "status": "ACTIVE",
        }

        WebhookDeliveryService.trigger_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.ODPS_CREATED,
            resource_type="ODPS",
            resource_id=resource_id,
            event_data=event_data,
        )

        # Verify payload structure
        delivery = WebhookDelivery.objects.filter(webhook=webhook).first()
        self.assertIsNotNone(delivery)

        payload = delivery.payload
        self.assertEqual(payload["event_type"], WebhookEventType.ODPS_CREATED)
        self.assertEqual(payload["resource_type"], "ODPS")
        self.assertEqual(payload["resource_id"], resource_id)
        self.assertEqual(payload["data"], event_data)
        self.assertIn("timestamp", payload)

        # Verify signature is present
        self.assertIsNotNone(delivery.signature)
        self.assertEqual(len(delivery.signature), 64)  # SHA256 hex digest length

