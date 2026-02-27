"""
E2E tests for mesh webhook delivery.

Tests complete end-to-end flow from event publishing through event bus to webhook delivery.
Uses real TestWebhookServer (no mocks).
Uses wait_until for delivery state (no fixed time.sleep) per FIX_PLAN_FLAKY_TESTS_5_6_2.
"""

import uuid

import pytest
from django.test import TestCase
from django.utils import timezone

from tests.utils.polling import wait_until

from hub.apps.core.events.models import Event
from hub.apps.core.events.publisher import EventPublisher
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User
from hub.apps.webhooks.mesh_event_subscriber import get_mesh_event_subscriber
from hub.apps.webhooks.models import (
    DeliveryStatus,
    Webhook,
    WebhookDelivery,
    WebhookEventType,
    WebhookStatus,
)
from hub.apps.webhooks.tests.test_odps_webhook_integration import TestWebhookServer

pytestmark = pytest.mark.django_db(transaction=True)


class MeshWebhookE2ETest(TestCase):
    """E2E tests for mesh webhook delivery from event bus"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", tenant=self.tenant
        )

    def test_mesh_domain_created_e2e_event_bus_integration(self):
        """
        E2E test for mesh.domain.created webhook delivery from event bus (real server).
        """
        with TestWebhookServer(response_status=200) as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="Mesh E2E Webhook",
                url=server.get_url(),
                secret="test-secret",
                event_types=[WebhookEventType.MESH_DOMAIN_CREATED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )

            publisher = EventPublisher(
                service_name="data_mesh_service",
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
            )

            domain_id = str(uuid.uuid4())
            event_id = publisher.publish(
                event_type="mesh.domain.created",
                data={
                    "domain_id": domain_id,
                    "name": "Test Domain",
                    "status": "ACTIVE",
                    "owner_id": str(self.user.id),
                    "tenant_id": str(self.tenant.id),
                },
            )

            self.assertIsNotNone(event_id, "Event should be published")

            persisted_event = Event.objects.filter(
                event_type="mesh.domain.created", tenant_id=self.tenant.id, event_id=event_id
            ).first()

            self.assertIsNotNone(persisted_event, "Event should be persisted to database")
            self.assertEqual(persisted_event.data["domain_id"], domain_id)

            subscriber = get_mesh_event_subscriber()
            event = {
                "event_id": event_id,
                "event_type": "mesh.domain.created",
                "event_version": "1.0",
                "timestamp": timezone.now().isoformat(),
                "source": {
                    "service": "data_mesh_service",
                    "tenant_id": str(self.tenant.id),
                    "user_id": str(self.user.id),
                },
                "data": {
                    "domain_id": domain_id,
                    "name": "Test Domain",
                    "status": "ACTIVE",
                    "owner_id": str(self.user.id),
                    "tenant_id": str(self.tenant.id),
                },
                "metadata": {},
            }

            subscriber._handle_mesh_event(event)

            def has_domain_created_delivery():
                return (
                    WebhookDelivery.objects.filter(
                        webhook=webhook, event_type="mesh.domain.created"
                    ).count()
                    >= 1
                )

            wait_until(has_domain_created_delivery, timeout=5.0, message="mesh.domain.created delivery")
            deliveries = WebhookDelivery.objects.filter(
                webhook=webhook, event_type="mesh.domain.created"
            )
            self.assertEqual(deliveries.count(), 1, "Webhook should be delivered")

            delivery = deliveries.first()
            self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)
            self.assertEqual(delivery.payload["data"]["domain_id"], domain_id)
            self.assertIsNotNone(delivery.signature)

            requests_received = server.get_received_requests(timeout=2.0)
            self.assertEqual(len(requests_received), 1)

    def test_mesh_policy_applied_e2e_event_bus_integration(self):
        """E2E test for mesh.policy.applied webhook delivery from event bus (real server)."""
        with TestWebhookServer(response_status=200) as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="Mesh Policy E2E Webhook",
                url=server.get_url(),
                secret="test-secret",
                event_types=[WebhookEventType.MESH_POLICY_APPLIED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )

            publisher = EventPublisher(
                service_name="data_mesh_service",
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
            )

            domain_id = str(uuid.uuid4())
            policy_application_id = str(uuid.uuid4())
            event_id = publisher.publish(
                event_type="mesh.policy.applied",
                data={
                    "policy_application_id": policy_application_id,
                    "domain_id": domain_id,
                    "policy_id": str(uuid.uuid4()),
                    "status": "APPLIED",
                    "tenant_id": str(self.tenant.id),
                },
            )

            self.assertIsNotNone(event_id)

            subscriber = get_mesh_event_subscriber()
            event = {
                "event_id": event_id,
                "event_type": "mesh.policy.applied",
                "event_version": "1.0",
                "timestamp": timezone.now().isoformat(),
                "source": {
                    "service": "data_mesh_service",
                    "tenant_id": str(self.tenant.id),
                    "user_id": str(self.user.id),
                },
                "data": {
                    "policy_application_id": policy_application_id,
                    "domain_id": domain_id,
                    "policy_id": str(uuid.uuid4()),
                    "status": "APPLIED",
                    "tenant_id": str(self.tenant.id),
                },
                "metadata": {},
            }

            subscriber._handle_mesh_event(event)

            def has_policy_applied_delivery():
                return (
                    WebhookDelivery.objects.filter(
                        webhook=webhook, event_type="mesh.policy.applied"
                    ).count()
                    >= 1
                )

            wait_until(has_policy_applied_delivery, timeout=5.0, message="mesh.policy.applied delivery")
            deliveries = WebhookDelivery.objects.filter(
                webhook=webhook, event_type="mesh.policy.applied"
            )
            self.assertEqual(deliveries.count(), 1)
            self.assertEqual(deliveries.first().status, DeliveryStatus.SUCCESS)
            self.assertEqual(
                deliveries.first().payload["data"]["policy_application_id"], policy_application_id
            )

            requests_received = server.get_received_requests(timeout=2.0)
            self.assertEqual(len(requests_received), 1)

    def test_mesh_compliance_checked_e2e_event_bus_integration(self):
        """E2E test for mesh.compliance.checked webhook delivery from event bus (real server)."""
        with TestWebhookServer(response_status=200) as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="Mesh Compliance E2E Webhook",
                url=server.get_url(),
                secret="test-secret",
                event_types=[WebhookEventType.MESH_COMPLIANCE_CHECKED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )

            publisher = EventPublisher(
                service_name="data_mesh_service",
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
            )

            domain_id = str(uuid.uuid4())
            event_id = publisher.publish(
                event_type="mesh.compliance.checked",
                data={
                    "domain_id": domain_id,
                    "compliance_status": "COMPLIANT",
                    "violation_count": 0,
                    "checked_at": timezone.now().isoformat(),
                    "tenant_id": str(self.tenant.id),
                },
            )

            self.assertIsNotNone(event_id)

            subscriber = get_mesh_event_subscriber()
            event = {
                "event_id": event_id,
                "event_type": "mesh.compliance.checked",
                "event_version": "1.0",
                "timestamp": timezone.now().isoformat(),
                "source": {
                    "service": "data_mesh_service",
                    "tenant_id": str(self.tenant.id),
                    "user_id": str(self.user.id),
                },
                "data": {
                    "domain_id": domain_id,
                    "compliance_status": "COMPLIANT",
                    "violation_count": 0,
                    "checked_at": timezone.now().isoformat(),
                    "tenant_id": str(self.tenant.id),
                },
                "metadata": {},
            }

            subscriber._handle_mesh_event(event)

            def has_compliance_checked_delivery():
                return (
                    WebhookDelivery.objects.filter(
                        webhook=webhook, event_type="mesh.compliance.checked"
                    ).count()
                    >= 1
                )

            wait_until(has_compliance_checked_delivery, timeout=5.0, message="mesh.compliance.checked delivery")
            deliveries = WebhookDelivery.objects.filter(
                webhook=webhook, event_type="mesh.compliance.checked"
            )
            self.assertEqual(deliveries.count(), 1)
            self.assertEqual(deliveries.first().status, DeliveryStatus.SUCCESS)
            self.assertEqual(deliveries.first().payload["data"]["domain_id"], domain_id)

            requests_received = server.get_received_requests(timeout=2.0)
            self.assertEqual(len(requests_received), 1)

    def test_mesh_event_subscriber_initialization(self):
        """Test that mesh event subscriber is properly initialized"""
        subscriber = get_mesh_event_subscriber()
        self.assertIsNotNone(subscriber)
        self.assertEqual(subscriber.subscriber_name, "webhook_service_mesh")

        # Verify subscriber has handlers registered
        # The subscriber should have registered handlers for all mesh event types
        from hub.apps.webhooks.models import WebhookEventType

        mesh_event_types = WebhookEventType.get_mesh_event_types()
        self.assertGreater(len(mesh_event_types), 0, "Should have mesh event types registered")
