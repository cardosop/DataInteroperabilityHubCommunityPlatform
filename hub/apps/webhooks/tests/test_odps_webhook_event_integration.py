"""
Integration tests for ODPS webhook delivery from event bus.

Tests that ODPS events published to the event bus trigger webhook deliveries.
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
from hub.apps.webhooks.odps_event_subscriber import ODPSEventSubscriber, get_odps_event_subscriber
from hub.apps.contracts.services import ContractService
from hub.apps.tenants.models import Tenant, TenantStatus, KYCStatus
from hub.apps.users.models import UserStatus
from hub.apps.core.events.publisher import EventPublisher

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class ODPSWebhookEventIntegrationTest(TestCase):
    """Integration tests for ODPS webhook delivery from event bus"""

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
    def test_odps_created_event_triggers_webhook(self, mock_post):
        """Test that odps.created event triggers webhook delivery"""
        # Create webhook subscribed to ODPS events
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="ODPS Created Webhook",
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

        # Create event publisher and publish ODPS event
        publisher = EventPublisher(
            service_name="contract_service",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        contract_id = str(uuid.uuid4())
        event_id = publisher.publish(
            event_type="odps.created",
            data={
                "contract_id": contract_id,
                "asset_id": str(uuid.uuid4()),
                "status": "ACTIVE",
                "odps_version": "4.1",
                "original_format": "JSON",
            }
        )

        # Simulate event subscriber handling the event
        subscriber = get_odps_event_subscriber()
        event = {
            "event_id": event_id,
            "event_type": "odps.created",
            "data": {
                "contract_id": contract_id,
                "asset_id": str(uuid.uuid4()),
                "status": "ACTIVE",
                "odps_version": "4.1",
                "original_format": "JSON",
            },
            "source": {
                "service": "contract_service",
                "tenant_id": str(self.tenant.id),
                "user_id": str(self.user.id),
            }
        }

        subscriber._handle_odps_event(event)

        # Verify webhook was triggered
        deliveries = WebhookDelivery.objects.filter(webhook=webhook)
        self.assertEqual(deliveries.count(), 1)

        delivery = deliveries.first()
        self.assertEqual(delivery.event_type, "odps.created")
        self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)
        self.assertIsNotNone(delivery.delivered_at)

        # Verify HTTP request was made
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(call_args[0][0], webhook.url)

    @patch('hub.apps.webhooks.service.requests.post')
    def test_odps_linked_event_triggers_webhook(self, mock_post):
        """Test that odps.linked event triggers webhook delivery"""
        # Create webhook subscribed to ODPS linked events
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="ODPS Linked Webhook",
            url="https://example.com/webhook",
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_LINKED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response

        # Simulate event subscriber handling the event
        subscriber = get_odps_event_subscriber()
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "odps.linked",
            "data": {
                "odps_contract_id": str(uuid.uuid4()),
                "odcs_contract_id": str(uuid.uuid4()),
                "link_type": "bidirectional",
            },
            "source": {
                "service": "contract_service",
                "tenant_id": str(self.tenant.id),
                "user_id": str(self.user.id),
            }
        }

        subscriber._handle_odps_event(event)

        # Verify webhook was triggered
        deliveries = WebhookDelivery.objects.filter(webhook=webhook)
        self.assertEqual(deliveries.count(), 1)

        delivery = deliveries.first()
        self.assertEqual(delivery.event_type, "odps.linked")

    @patch('hub.apps.webhooks.service.requests.post')
    def test_odps_event_subscriber_filters_by_tenant(self, mock_post):
        """Test that ODPS event subscriber only triggers webhooks for the correct tenant"""
        # Create webhook for current tenant
        webhook1 = Webhook.objects.create(
            tenant=self.tenant,
            name="Tenant 1 Webhook",
            url="https://example.com/webhook1",
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        # Create another tenant
        other_tenant = Tenant.objects.create(
            name="Other Tenant",
            slug="other-tenant",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )

        # Create webhook for other tenant
        webhook2 = Webhook.objects.create(
            tenant=other_tenant,
            name="Tenant 2 Webhook",
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

        # Simulate event subscriber handling the event for current tenant
        subscriber = get_odps_event_subscriber()
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "odps.created",
            "data": {
                "contract_id": str(uuid.uuid4()),
            },
            "source": {
                "service": "contract_service",
                "tenant_id": str(self.tenant.id),  # Current tenant
                "user_id": str(self.user.id),
            }
        }

        subscriber._handle_odps_event(event)

        # Verify only webhook for current tenant was triggered
        deliveries1 = WebhookDelivery.objects.filter(webhook=webhook1)
        self.assertEqual(deliveries1.count(), 1)

        deliveries2 = WebhookDelivery.objects.filter(webhook=webhook2)
        self.assertEqual(deliveries2.count(), 0)

    def test_odps_event_subscriber_handles_missing_tenant_id(self):
        """Test that ODPS event subscriber handles events without tenant_id gracefully"""
        subscriber = get_odps_event_subscriber()
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "odps.created",
            "data": {
                "contract_id": str(uuid.uuid4()),
            },
            "source": {
                "service": "contract_service",
                # Missing tenant_id
            }
        }

        # Should not raise exception
        subscriber._handle_odps_event(event)

        # Verify no deliveries were created
        deliveries = WebhookDelivery.objects.all()
        self.assertEqual(deliveries.count(), 0)

    def test_odps_event_subscriber_handles_missing_contract_id(self):
        """Test that ODPS event subscriber handles events without contract_id gracefully"""
        subscriber = get_odps_event_subscriber()
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "odps.created",
            "data": {
                # Missing contract_id
            },
            "source": {
                "service": "contract_service",
                "tenant_id": str(self.tenant.id),
            }
        }

        # Should not raise exception
        subscriber._handle_odps_event(event)

        # Verify no deliveries were created
        deliveries = WebhookDelivery.objects.all()
        self.assertEqual(deliveries.count(), 0)

    @patch('hub.apps.webhooks.service.requests.post')
    def test_odps_event_subscriber_handles_webhook_errors_gracefully(self, mock_post):
        """Test that ODPS event subscriber handles webhook errors gracefully"""
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

        # Mock failed HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        # Simulate event subscriber handling the event
        subscriber = get_odps_event_subscriber()
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "odps.created",
            "data": {
                "contract_id": str(uuid.uuid4()),
            },
            "source": {
                "service": "contract_service",
                "tenant_id": str(self.tenant.id),
                "user_id": str(self.user.id),
            }
        }

        # Should not raise exception even if webhook delivery fails
        subscriber._handle_odps_event(event)

        # Verify delivery was created (even though it failed)
        deliveries = WebhookDelivery.objects.filter(webhook=webhook)
        self.assertEqual(deliveries.count(), 1)

        delivery = deliveries.first()
        # Delivery should be in failed state and scheduled for retry
        self.assertIn(delivery.status, [DeliveryStatus.FAILED, DeliveryStatus.PENDING])

