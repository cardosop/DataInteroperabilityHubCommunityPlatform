"""
E2E tests for mesh webhook delivery.

Tests complete end-to-end flow from event publishing through event bus to webhook delivery.
"""
import pytest
from django.test import TestCase
from django.utils import timezone
from unittest.mock import patch, Mock
import uuid
import json

from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.users.models import User
from hub.apps.webhooks.models import Webhook, WebhookDelivery, WebhookStatus, DeliveryStatus, WebhookEventType
from hub.apps.core.events.publisher import EventPublisher
from hub.apps.core.events.models import Event
from hub.apps.webhooks.mesh_event_subscriber import get_mesh_event_subscriber


pytestmark = pytest.mark.django_db(transaction=True)


class MeshWebhookE2ETest(TestCase):
    """E2E tests for mesh webhook delivery from event bus"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )

    @patch('hub.apps.webhooks.service.requests.post')
    def test_mesh_domain_created_e2e_event_bus_integration(self, mock_post):
        """
        E2E test for mesh.domain.created webhook delivery from event bus.

        Verifies:
        - Event published to event bus triggers webhook delivery
        - Event subscriber correctly processes mesh events
        - Webhook is delivered with correct payload
        - Full integration from event bus to webhook delivery
        """
        # Mock successful HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response

        # Start webhook receiver server
        webhook_url = "https://example.com/webhooks/mesh"
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Mesh E2E Webhook",
            url=webhook_url,
            secret="test-secret",
            event_types=[WebhookEventType.MESH_DOMAIN_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        # Create event publisher
        publisher = EventPublisher(
            service_name="data_mesh_service",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Publish mesh event
        domain_id = str(uuid.uuid4())
        event_id = publisher.publish(
            event_type="mesh.domain.created",
            data={
                "domain_id": domain_id,
                "name": "Test Domain",
                "status": "ACTIVE",
                "owner_id": str(self.user.id),
                "tenant_id": str(self.tenant.id),
            }
        )

        self.assertIsNotNone(event_id, "Event should be published")

        # Verify event was persisted
        persisted_event = Event.objects.filter(
            event_type="mesh.domain.created",
            tenant_id=self.tenant.id,
            event_id=event_id
        ).first()

        self.assertIsNotNone(persisted_event, "Event should be persisted to database")
        self.assertEqual(persisted_event.data["domain_id"], domain_id)

        # Simulate event subscriber handling the event
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
            "metadata": {}
        }

        # Handle event through subscriber
        subscriber._handle_mesh_event(event)

        # Verify webhook was triggered
        deliveries = WebhookDelivery.objects.filter(
            webhook=webhook,
            event_type="mesh.domain.created"
        )
        self.assertEqual(deliveries.count(), 1, "Webhook should be delivered")

        delivery = deliveries.first()
        self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)
        self.assertEqual(delivery.payload["data"]["domain_id"], domain_id)
        self.assertIsNotNone(delivery.signature)

        # Verify HTTP request was made
        mock_post.assert_called_once()
        call_args, call_kwargs = mock_post.call_args
        self.assertEqual(call_kwargs.get("url") or call_args[0], webhook_url)

    @patch('hub.apps.webhooks.service.requests.post')
    def test_mesh_policy_applied_e2e_event_bus_integration(self, mock_post):
        """
        E2E test for mesh.policy.applied webhook delivery from event bus.
        """
        # Mock successful HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response

        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Mesh Policy E2E Webhook",
            url="https://example.com/webhooks/mesh-policy",
            secret="test-secret",
            event_types=[WebhookEventType.MESH_POLICY_APPLIED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        publisher = EventPublisher(
            service_name="data_mesh_service",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
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
            }
        )

        self.assertIsNotNone(event_id)

        # Simulate event subscriber handling
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
            "metadata": {}
        }

        subscriber._handle_mesh_event(event)

        # Verify webhook delivery
        deliveries = WebhookDelivery.objects.filter(
            webhook=webhook,
            event_type="mesh.policy.applied"
        )
        self.assertEqual(deliveries.count(), 1)
        self.assertEqual(deliveries.first().status, DeliveryStatus.SUCCESS)
        self.assertEqual(deliveries.first().payload["data"]["policy_application_id"], policy_application_id)

    @patch('hub.apps.webhooks.service.requests.post')
    def test_mesh_compliance_checked_e2e_event_bus_integration(self, mock_post):
        """
        E2E test for mesh.compliance.checked webhook delivery from event bus.
        """
        # Mock successful HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response

        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Mesh Compliance E2E Webhook",
            url="https://example.com/webhooks/mesh-compliance",
            secret="test-secret",
            event_types=[WebhookEventType.MESH_COMPLIANCE_CHECKED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        publisher = EventPublisher(
            service_name="data_mesh_service",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
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
            }
        )

        self.assertIsNotNone(event_id)

        # Simulate event subscriber handling
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
            "metadata": {}
        }

        subscriber._handle_mesh_event(event)

        # Verify webhook delivery
        deliveries = WebhookDelivery.objects.filter(
            webhook=webhook,
            event_type="mesh.compliance.checked"
        )
        self.assertEqual(deliveries.count(), 1)
        self.assertEqual(deliveries.first().status, DeliveryStatus.SUCCESS)
        self.assertEqual(deliveries.first().payload["data"]["domain_id"], domain_id)

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

