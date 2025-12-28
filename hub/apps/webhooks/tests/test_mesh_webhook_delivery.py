"""
Integration tests for mesh webhook delivery.

Tests webhook delivery for mesh events.
"""
import pytest
from django.test import TestCase
from django.utils import timezone
from unittest.mock import patch, Mock
import uuid

from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.users.models import User
from hub.apps.webhooks.models import Webhook, WebhookDelivery, WebhookStatus, DeliveryStatus
from hub.apps.webhooks.service import WebhookDeliveryService
from hub.apps.core.events.publisher import publish_event


pytestmark = pytest.mark.django_db(transaction=True)


class MeshWebhookDeliveryTest(TestCase):
    """Test webhook delivery for mesh events"""

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

        # Create webhook subscription for mesh events
        self.webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Mesh Events Webhook",
            url="https://example.com/webhooks/mesh",
            secret="test-secret-key",
            event_types=["mesh.domain.created", "mesh.domain.updated", "mesh.policy.applied",
                        "mesh.compliance.checked", "mesh.topology.updated", "mesh.health.status_changed"],
            status=WebhookStatus.ACTIVE,
            created_by=self.user
        )

    @patch('hub.apps.webhooks.service.requests.post')
    def test_mesh_domain_created_webhook_delivery(self, mock_post):
        """Test webhook delivery for mesh.domain.created event"""
        # Mock successful HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response

        # Publish event and trigger webhook
        domain_id = str(uuid.uuid4())
        event_data = {
            "domain_id": domain_id,
            "name": "Test Domain",
            "status": "ACTIVE",
            "owner_id": str(self.user.id),
            "tenant_id": str(self.tenant.id),
        }

        # Trigger webhook directly (simulating event subscriber behavior)
        WebhookDeliveryService.trigger_webhook(
            tenant_id=str(self.tenant.id),
            event_type="mesh.domain.created",
            resource_type="DATA_MESH_DOMAIN",
            resource_id=domain_id,
            event_data=event_data
        )

        # Verify webhook was triggered
        deliveries = WebhookDelivery.objects.filter(webhook=self.webhook, event_type="mesh.domain.created")
        self.assertEqual(deliveries.count(), 1)

        delivery = deliveries.first()
        self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)
        self.assertEqual(delivery.payload["data"]["domain_id"], domain_id)
        self.assertIsNotNone(delivery.signature)

        # Verify HTTP request was made
        mock_post.assert_called_once()
        call_args, call_kwargs = mock_post.call_args
        self.assertEqual(call_kwargs.get("url") or call_args[0], "https://example.com/webhooks/mesh")

    @patch('hub.apps.webhooks.service.requests.post')
    def test_mesh_domain_updated_webhook_delivery(self, mock_post):
        """Test webhook delivery for mesh.domain.updated event"""
        # Mock successful HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response

        # Trigger webhook directly
        domain_id = str(uuid.uuid4())
        event_data = {
            "domain_id": domain_id,
            "changes": {"name": {"old": "Old Name", "new": "New Name"}},
            "previous_status": "ACTIVE",
            "new_status": "INACTIVE",
            "tenant_id": str(self.tenant.id),
        }

        WebhookDeliveryService.trigger_webhook(
            tenant_id=str(self.tenant.id),
            event_type="mesh.domain.updated",
            resource_type="DATA_MESH_DOMAIN",
            resource_id=domain_id,
            event_data=event_data
        )

        # Verify webhook was triggered
        deliveries = WebhookDelivery.objects.filter(webhook=self.webhook, event_type="mesh.domain.updated")
        self.assertEqual(deliveries.count(), 1)

        delivery = deliveries.first()
        self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)
        self.assertEqual(delivery.payload["data"]["domain_id"], domain_id)

    @patch('hub.apps.webhooks.service.requests.post')
    def test_mesh_policy_applied_webhook_delivery(self, mock_post):
        """Test webhook delivery for mesh.policy.applied event"""
        # Mock successful HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response

        # Trigger webhook directly
        domain_id = str(uuid.uuid4())
        policy_application_id = str(uuid.uuid4())
        event_data = {
            "policy_application_id": policy_application_id,
            "domain_id": domain_id,
            "policy_id": str(uuid.uuid4()),
            "status": "APPLIED",
            "tenant_id": str(self.tenant.id),
        }

        WebhookDeliveryService.trigger_webhook(
            tenant_id=str(self.tenant.id),
            event_type="mesh.policy.applied",
            resource_type="POLICY_APPLICATION",
            resource_id=policy_application_id,
            event_data=event_data
        )

        # Verify webhook was triggered
        deliveries = WebhookDelivery.objects.filter(webhook=self.webhook, event_type="mesh.policy.applied")
        self.assertEqual(deliveries.count(), 1)

        delivery = deliveries.first()
        self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)
        self.assertEqual(delivery.payload["data"]["policy_application_id"], policy_application_id)

    @patch('hub.apps.webhooks.service.requests.post')
    def test_mesh_compliance_checked_webhook_delivery(self, mock_post):
        """Test webhook delivery for mesh.compliance.checked event"""
        # Mock successful HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response

        # Trigger webhook directly
        domain_id = str(uuid.uuid4())
        event_data = {
            "domain_id": domain_id,
            "compliance_status": "COMPLIANT",
            "violation_count": 0,
            "checked_at": timezone.now().isoformat(),
            "tenant_id": str(self.tenant.id),
        }

        WebhookDeliveryService.trigger_webhook(
            tenant_id=str(self.tenant.id),
            event_type="mesh.compliance.checked",
            resource_type="DATA_MESH_DOMAIN",
            resource_id=domain_id,
            event_data=event_data
        )

        # Verify webhook was triggered
        deliveries = WebhookDelivery.objects.filter(webhook=self.webhook, event_type="mesh.compliance.checked")
        self.assertEqual(deliveries.count(), 1)

        delivery = deliveries.first()
        self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)
        self.assertEqual(delivery.payload["data"]["domain_id"], domain_id)

    @patch('hub.apps.webhooks.service.requests.post')
    def test_mesh_topology_updated_webhook_delivery(self, mock_post):
        """Test webhook delivery for mesh.topology.updated event"""
        # Mock successful HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response

        # Trigger webhook directly
        event_data = {
            "tenant_id": str(self.tenant.id),
            "domain_count": 5,
            "relationship_count": 10,
            "updated_at": timezone.now().isoformat(),
            "user_id": str(self.user.id),
        }

        WebhookDeliveryService.trigger_webhook(
            tenant_id=str(self.tenant.id),
            event_type="mesh.topology.updated",
            resource_type="DATA_MESH_TOPOLOGY",
            resource_id=str(self.tenant.id),
            event_data=event_data
        )

        # Verify webhook was triggered
        deliveries = WebhookDelivery.objects.filter(webhook=self.webhook, event_type="mesh.topology.updated")
        self.assertEqual(deliveries.count(), 1)

        delivery = deliveries.first()
        self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)
        self.assertEqual(delivery.payload["data"]["domain_count"], 5)

    @patch('hub.apps.webhooks.service.requests.post')
    def test_mesh_health_status_changed_webhook_delivery(self, mock_post):
        """Test webhook delivery for mesh.health.status_changed event"""
        # Mock successful HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response

        # Trigger webhook directly
        domain_id = str(uuid.uuid4())
        event_data = {
            "domain_id": domain_id,
            "previous_status": "HEALTHY",
            "new_status": "DEGRADED",
            "health_metrics": {"cpu": 85, "memory": 70},
            "changed_at": timezone.now().isoformat(),
            "tenant_id": str(self.tenant.id),
        }

        WebhookDeliveryService.trigger_webhook(
            tenant_id=str(self.tenant.id),
            event_type="mesh.health.status_changed",
            resource_type="DATA_MESH_DOMAIN",
            resource_id=domain_id,
            event_data=event_data
        )

        # Verify webhook was triggered
        deliveries = WebhookDelivery.objects.filter(webhook=self.webhook, event_type="mesh.health.status_changed")
        self.assertEqual(deliveries.count(), 1)

        delivery = deliveries.first()
        self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)
        self.assertEqual(delivery.payload["data"]["domain_id"], domain_id)
        self.assertEqual(delivery.payload["data"]["new_status"], "DEGRADED")

    @patch('hub.apps.webhooks.service.requests.post')
    def test_webhook_filters_mesh_events(self, mock_post):
        """Test that webhook only receives subscribed mesh events"""
        # Mock successful HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response

        # Create webhook subscribed only to mesh.domain.created
        specific_webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Domain Created Only",
            url="https://example.com/webhooks/domain-created",
            secret="test-secret",
            event_types=["mesh.domain.created"],
            status=WebhookStatus.ACTIVE,
            created_by=self.user
        )

        # Trigger multiple mesh events
        domain_id = str(uuid.uuid4())

        WebhookDeliveryService.trigger_webhook(
            tenant_id=str(self.tenant.id),
            event_type="mesh.domain.created",
            resource_type="DATA_MESH_DOMAIN",
            resource_id=domain_id,
            event_data={"domain_id": domain_id, "name": "Test Domain"}
        )

        WebhookDeliveryService.trigger_webhook(
            tenant_id=str(self.tenant.id),
            event_type="mesh.domain.updated",
            resource_type="DATA_MESH_DOMAIN",
            resource_id=domain_id,
            event_data={"domain_id": domain_id, "changes": {}}
        )

        WebhookDeliveryService.trigger_webhook(
            tenant_id=str(self.tenant.id),
            event_type="mesh.policy.applied",
            resource_type="POLICY_APPLICATION",
            resource_id=str(uuid.uuid4()),
            event_data={"policy_application_id": str(uuid.uuid4()), "domain_id": domain_id}
        )

        # Verify only mesh.domain.created triggered webhook
        deliveries = WebhookDelivery.objects.filter(webhook=specific_webhook)
        self.assertEqual(deliveries.count(), 1)
        self.assertEqual(deliveries.first().event_type, "mesh.domain.created")

