"""
Integration tests for ODPS webhook delivery from event bus.

Tests that ODPS events published to the event bus trigger webhook deliveries.
Uses real TestWebhookServer (no mocks).
Uses wait_until for delivery state (no fixed time.sleep) per FIX_PLAN_FLAKY_TESTS_5_6_2.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from tests.utils.polling import wait_until

from hub.apps.contracts.services import ContractService
from hub.apps.core.events.publisher import EventPublisher
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus
from hub.apps.webhooks.models import (
    DeliveryStatus,
    Webhook,
    WebhookDelivery,
    WebhookEventType,
    WebhookStatus,
)
from hub.apps.webhooks.odps_event_subscriber import ODPSEventSubscriber, get_odps_event_subscriber
from hub.apps.webhooks.service import WebhookDeliveryService
from hub.apps.webhooks.tests.test_odps_webhook_integration import TestWebhookServer

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
        ensure_tenant_has_active_subscription(self.tenant)

        # Create user
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
            display_name="Test User",
        )

    def test_odps_created_event_triggers_webhook(self):
        """Test that odps.created event triggers webhook delivery (real server)."""
        with TestWebhookServer(response_status=200) as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="ODPS Created Webhook",
                url=server.get_url(),
                secret="test-secret",
                event_types=[WebhookEventType.ODPS_CREATED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )

            publisher = EventPublisher(
                service_name="contract_service",
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
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
                },
            )

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
                },
            }

            subscriber._handle_odps_event(event)

            def has_created_delivery():
                d = WebhookDelivery.objects.filter(webhook=webhook).first()
                return d is not None and d.status == DeliveryStatus.SUCCESS

            wait_until(has_created_delivery, timeout=5.0, message="odps.created delivery")
            deliveries = WebhookDelivery.objects.filter(webhook=webhook)
            self.assertEqual(deliveries.count(), 1)

            delivery = deliveries.first()
            self.assertEqual(delivery.event_type, "odps.created")
            self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)
            self.assertIsNotNone(delivery.delivered_at)

            requests_received = server.get_received_requests(timeout=2.0)
            self.assertEqual(len(requests_received), 1)
            self.assertEqual(requests_received[0].get("path", ""), "/webhook")

    def test_odps_linked_event_triggers_webhook(self):
        """Test that odps.linked event triggers webhook delivery (real server)."""
        with TestWebhookServer(response_status=200) as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="ODPS Linked Webhook",
                url=server.get_url(),
                secret="test-secret",
                event_types=[WebhookEventType.ODPS_LINKED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )

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
                },
            }

            subscriber._handle_odps_event(event)

            def has_linked_delivery():
                d = WebhookDelivery.objects.filter(webhook=webhook).first()
                return d is not None and d.status == DeliveryStatus.SUCCESS

            wait_until(has_linked_delivery, timeout=5.0, message="odps.linked delivery")
            deliveries = WebhookDelivery.objects.filter(webhook=webhook)
            self.assertEqual(deliveries.count(), 1)

            delivery = deliveries.first()
            self.assertEqual(delivery.event_type, "odps.linked")
            self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)

            requests_received = server.get_received_requests(timeout=2.0)
            self.assertEqual(len(requests_received), 1)

    def test_odps_event_subscriber_filters_by_tenant(self):
        """Test that ODPS event subscriber only triggers webhooks for the correct tenant (real server)."""
        with TestWebhookServer(response_status=200) as server:
            webhook1 = Webhook.objects.create(
                tenant=self.tenant,
                name="Tenant 1 Webhook",
                url=server.get_url(),
                secret="test-secret",
                event_types=[WebhookEventType.ODPS_CREATED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )

            other_tenant = Tenant.objects.create(
                name="Other Tenant",
                slug="other-tenant",
                status=TenantStatus.ACTIVE,
                kyc_status=KYCStatus.VERIFIED,
            )
            ensure_tenant_has_active_subscription(other_tenant)

            webhook2 = Webhook.objects.create(
                tenant=other_tenant,
                name="Tenant 2 Webhook",
                url="https://example.com/webhook2",
                secret="test-secret",
                event_types=[WebhookEventType.ODPS_CREATED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )

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
                },
            }

            subscriber._handle_odps_event(event)

            def tenant1_has_delivery():
                return WebhookDelivery.objects.filter(webhook=webhook1).count() >= 1

            wait_until(tenant1_has_delivery, timeout=5.0, message="tenant1 odps.created delivery")
            deliveries1 = WebhookDelivery.objects.filter(webhook=webhook1)
            self.assertEqual(deliveries1.count(), 1)

            deliveries2 = WebhookDelivery.objects.filter(webhook=webhook2)
            self.assertEqual(deliveries2.count(), 0)

            requests_received = server.get_received_requests(timeout=2.0)
            self.assertEqual(len(requests_received), 1)

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
            },
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
            },
        }

        # Should not raise exception
        subscriber._handle_odps_event(event)

        # Verify no deliveries were created
        deliveries = WebhookDelivery.objects.all()
        self.assertEqual(deliveries.count(), 0)

    def test_odps_event_subscriber_handles_webhook_errors_gracefully(self):
        """Test that ODPS event subscriber handles webhook errors gracefully (real server 500)."""
        with TestWebhookServer(response_status=500) as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="ODPS Webhook",
                url=server.get_url(),
                secret="test-secret",
                event_types=[WebhookEventType.ODPS_CREATED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )

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
                },
            }

            subscriber._handle_odps_event(event)

            def has_delivery_recorded():
                return WebhookDelivery.objects.filter(webhook=webhook).count() >= 1

            wait_until(has_delivery_recorded, timeout=5.0, message="webhook error delivery recorded")
            deliveries = WebhookDelivery.objects.filter(webhook=webhook)
            self.assertEqual(deliveries.count(), 1)

            delivery = deliveries.first()
            self.assertIn(delivery.status, [DeliveryStatus.FAILED, DeliveryStatus.PENDING])
            if delivery.status == DeliveryStatus.FAILED:
                self.assertEqual(delivery.http_status_code, 500)
