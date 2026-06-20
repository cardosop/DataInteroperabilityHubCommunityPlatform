"""
Integration tests for ODPS webhook delivery.

Tests that ODPS events properly trigger webhook delivery with correct filtering.
Uses real HTTP server (TestWebhookServer) for delivery tests; no mocks.
Uses wait_until for delivery state (no fixed time.sleep) per FIX_PLAN_FLAKY_TESTS_5_6_2.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from hub.apps.core.resilience.circuit_breaker import reset_circuit_breaker_by_name
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
from hub.apps.webhooks.odps_webhook_errors import ODPSWebhookValidationError
from hub.apps.webhooks.service import WebhookDeliveryService
from hub.apps.webhooks.tests.test_odps_webhook_integration import TestWebhookServer
from tests.utils.polling import wait_until

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


@override_settings(WEBHOOK_ASYNC_DELIVERY=False)
class ODPSWebhookDeliveryTest(TestCase):
    """Integration tests for ODPS webhook delivery"""

    reset_sequences = False
    serialized_rollback = False

    def _fixture_teardown(self):
        pass

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        reset_circuit_breaker_by_name("webhook-delivery")
        # Create tenant
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)

        # Create user
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
            display_name="Test User",
        )

    def test_trigger_odps_webhook_delivery(self):
        """Test that ODPS events trigger webhook delivery via real HTTP server."""
        with TestWebhookServer(response_status=200) as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="ODPS Webhook",
                url=server.get_url(),
                secret="test-secret",
                event_types=[WebhookEventType.ODPS_CREATED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )
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
            self.assertEqual(count, 1)

            def has_success_delivery():
                d = WebhookDelivery.objects.filter(webhook=webhook).first()
                return d is not None and d.status == DeliveryStatus.SUCCESS

            wait_until(
                has_success_delivery, timeout=5.0, message="ODPS webhook delivery not SUCCESS"
            )
            deliveries = WebhookDelivery.objects.filter(webhook=webhook)
            self.assertEqual(deliveries.count(), 1)
            delivery = deliveries.first()
            self.assertEqual(delivery.event_type, WebhookEventType.ODPS_CREATED)
            self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)
            self.assertIsNotNone(delivery.delivered_at)
            received = server.get_received_requests(timeout=2.0)
            self.assertEqual(len(received), 1)
            self.assertEqual(
                received[0]["headers"].get("X-Webhook-Event-Type"), WebhookEventType.ODPS_CREATED
            )

    def test_trigger_odps_webhook_convenience_method(self):
        """Test trigger_odps_webhook() convenience method via real HTTP server."""
        with TestWebhookServer(response_status=200) as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="ODPS Webhook",
                url=server.get_url(),
                secret="test-secret",
                event_types=[WebhookEventType.ODPS_UPDATED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )
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
            self.assertEqual(count, 1)

            def has_delivery():
                return WebhookDelivery.objects.filter(webhook=webhook).count() >= 1

            wait_until(has_delivery, timeout=5.0, message="ODPS webhook delivery not recorded")
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
        self.assertEqual(
            cm.exception.error_code, ODPSWebhookValidationError.ERROR_CODE_INVALID_EVENT_TYPE
        )

    def test_odps_webhook_filtering(self):
        """Test that only webhooks subscribed to ODPS events receive deliveries (real HTTP)."""
        with TestWebhookServer(response_status=200) as server_odps:
            with TestWebhookServer(response_status=200) as server_contract:
                odps_webhook = Webhook.objects.create(
                    tenant=self.tenant,
                    name="ODPS Webhook",
                    url=server_odps.get_url(),
                    secret="test-secret",
                    event_types=[WebhookEventType.ODPS_CREATED],
                    status=WebhookStatus.ACTIVE,
                    created_by=self.user,
                )

                contract_webhook = Webhook.objects.create(
                    tenant=self.tenant,
                    name="Contract Webhook",
                    url=server_contract.get_url(),
                    secret="test-secret",
                    event_types=[WebhookEventType.CONTRACT_CREATED],
                    status=WebhookStatus.ACTIVE,
                    created_by=self.user,
                )

                event_data = {"contract_id": str(uuid.uuid4())}

                count = WebhookDeliveryService.trigger_webhook(
                    tenant_id=str(self.tenant.id),
                    event_type=WebhookEventType.ODPS_CREATED,
                    resource_type="ODPS",
                    resource_id=str(uuid.uuid4()),
                    event_data=event_data,
                )

                self.assertEqual(count, 1)

                odps_deliveries = WebhookDelivery.objects.filter(webhook=odps_webhook)
                self.assertEqual(odps_deliveries.count(), 1)

                contract_deliveries = WebhookDelivery.objects.filter(webhook=contract_webhook)
                self.assertEqual(contract_deliveries.count(), 0)

    def test_multiple_odps_webhooks_receive_delivery(self):
        """Test that multiple webhooks subscribed to same ODPS event receive delivery (real HTTP)."""
        with TestWebhookServer(response_status=200) as server:
            webhook1 = Webhook.objects.create(
                tenant=self.tenant,
                name="ODPS Webhook 1",
                url=server.get_url(),
                secret="test-secret",
                event_types=[WebhookEventType.ODPS_CREATED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )

            webhook2 = Webhook.objects.create(
                tenant=self.tenant,
                name="ODPS Webhook 2",
                url=server.get_url(),
                secret="test-secret",
                event_types=[WebhookEventType.ODPS_CREATED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )

            event_data = {"contract_id": str(uuid.uuid4())}

            count = WebhookDeliveryService.trigger_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.ODPS_CREATED,
                resource_type="ODPS",
                resource_id=str(uuid.uuid4()),
                event_data=event_data,
            )

            self.assertEqual(count, 2)

            deliveries1 = WebhookDelivery.objects.filter(webhook=webhook1)
            self.assertEqual(deliveries1.count(), 1)

            deliveries2 = WebhookDelivery.objects.filter(webhook=webhook2)
            self.assertEqual(deliveries2.count(), 1)

            # Use received_count (non-consuming) for wait; get_received_requests consumes the queue
            def two_requests_received():
                return server.received_count() >= 2

            wait_until(
                two_requests_received, timeout=5.0, message="Server did not receive 2 requests"
            )
            received = server.get_received_requests(timeout=2.0)
            self.assertEqual(len(received), 2)

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
            str(self.tenant.id), WebhookEventType.ODPS_CREATED
        )

        webhook_ids = {w.id for w in created_webhooks}
        self.assertIn(webhook1.id, webhook_ids)
        self.assertIn(webhook3.id, webhook_ids)
        self.assertNotIn(webhook2.id, webhook_ids)

    def test_odps_webhook_payload_structure(self):
        """Test that ODPS webhook payload has correct structure (real server)."""
        with TestWebhookServer(response_status=200) as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="ODPS Webhook",
                url=server.get_url(),
                secret="test-secret",
                event_types=[WebhookEventType.ODPS_CREATED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )
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

            def has_delivery():
                return WebhookDelivery.objects.filter(webhook=webhook).first() is not None

            wait_until(has_delivery, timeout=5.0, message="ODPS webhook delivery not recorded")
            delivery = WebhookDelivery.objects.filter(webhook=webhook).first()
            self.assertIsNotNone(delivery)
            payload = delivery.payload
            self.assertEqual(payload["event_type"], WebhookEventType.ODPS_CREATED)
            self.assertEqual(payload["resource_type"], "ODPS")
            self.assertEqual(payload["resource_id"], resource_id)
            self.assertEqual(payload["data"], event_data)
            self.assertIn("timestamp", payload)
            self.assertIsNotNone(delivery.signature)
            self.assertEqual(len(delivery.signature), 64)
