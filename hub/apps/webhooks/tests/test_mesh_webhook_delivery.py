"""
Integration tests for mesh webhook delivery.

Tests webhook delivery for mesh events. Uses real HTTP server (TestWebhookServer); no mocks.
Uses wait_until for delivery state (no fixed time.sleep) per FIX_PLAN_FLAKY_TESTS_5_6_2.
"""

import uuid

import pytest
from django.test import TestCase
from django.utils import timezone

from tests.utils.polling import wait_until

from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User
from hub.apps.webhooks.models import DeliveryStatus, Webhook, WebhookDelivery, WebhookStatus
from hub.apps.webhooks.service import WebhookDeliveryService
from hub.apps.webhooks.tests.test_odps_webhook_integration import TestWebhookServer

pytestmark = pytest.mark.django_db(transaction=True)


class MeshWebhookDeliveryTest(TestCase):
    """Test webhook delivery for mesh events"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", tenant=self.tenant
        )

        self.mesh_event_types = [
            "mesh.domain.created",
            "mesh.domain.updated",
            "mesh.policy.applied",
            "mesh.compliance.checked",
            "mesh.topology.updated",
            "mesh.health.status_changed",
        ]

    def test_mesh_domain_created_webhook_delivery(self):
        """Test webhook delivery for mesh.domain.created event via real HTTP server."""
        with TestWebhookServer(response_status=200) as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="Mesh Events Webhook",
                url=server.get_url(),
                secret="test-secret-key",
                event_types=self.mesh_event_types,
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )
            domain_id = str(uuid.uuid4())
            event_data = {
                "domain_id": domain_id,
                "name": "Test Domain",
                "status": "ACTIVE",
                "owner_id": str(self.user.id),
                "tenant_id": str(self.tenant.id),
            }
            WebhookDeliveryService.trigger_webhook(
                tenant_id=str(self.tenant.id),
                event_type="mesh.domain.created",
                resource_type="DATA_MESH_DOMAIN",
                resource_id=domain_id,
                event_data=event_data,
            )
            wait_until(
                lambda: WebhookDelivery.objects.filter(
                    webhook=webhook, event_type="mesh.domain.created"
                ).count()
                >= 1,
                timeout=5.0,
                message="mesh.domain.created delivery not recorded",
            )
            deliveries = WebhookDelivery.objects.filter(
                webhook=webhook, event_type="mesh.domain.created"
            )
            self.assertEqual(deliveries.count(), 1)
            delivery = deliveries.first()
            self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)
            self.assertEqual(delivery.payload["data"]["domain_id"], domain_id)
            self.assertIsNotNone(delivery.signature)
            received = server.get_received_requests(timeout=2.0)
            self.assertEqual(len(received), 1)

    def test_mesh_domain_updated_webhook_delivery(self):
        """Test webhook delivery for mesh.domain.updated event via real HTTP server."""
        with TestWebhookServer(response_status=200) as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="Mesh Events Webhook",
                url=server.get_url(),
                secret="test-secret-key",
                event_types=self.mesh_event_types,
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )
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
                event_data=event_data,
            )
            wait_until(
                lambda: WebhookDelivery.objects.filter(
                    webhook=webhook, event_type="mesh.domain.updated"
                ).count()
                >= 1,
                timeout=5.0,
                message="mesh.domain.updated delivery not recorded",
            )
            deliveries = WebhookDelivery.objects.filter(
                webhook=webhook, event_type="mesh.domain.updated"
            )
            self.assertEqual(deliveries.count(), 1)
            delivery = deliveries.first()
            self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)
            self.assertEqual(delivery.payload["data"]["domain_id"], domain_id)

    def test_mesh_policy_applied_webhook_delivery(self):
        """Test webhook delivery for mesh.policy.applied event via real HTTP server."""
        with TestWebhookServer(response_status=200) as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="Mesh Events Webhook",
                url=server.get_url(),
                secret="test-secret-key",
                event_types=self.mesh_event_types,
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )
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
                event_data=event_data,
            )
            wait_until(
                lambda: WebhookDelivery.objects.filter(
                    webhook=webhook, event_type="mesh.policy.applied"
                ).count()
                >= 1,
                timeout=5.0,
                message="mesh.policy.applied delivery not recorded",
            )
            deliveries = WebhookDelivery.objects.filter(
                webhook=webhook, event_type="mesh.policy.applied"
            )
            self.assertEqual(deliveries.count(), 1)
            delivery = deliveries.first()
            self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)
            self.assertEqual(
                delivery.payload["data"]["policy_application_id"], policy_application_id
            )

    def test_mesh_compliance_checked_webhook_delivery(self):
        """Test webhook delivery for mesh.compliance.checked event via real HTTP server."""
        with TestWebhookServer(response_status=200) as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="Mesh Events Webhook",
                url=server.get_url(),
                secret="test-secret-key",
                event_types=self.mesh_event_types,
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )
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
                event_data=event_data,
            )
            wait_until(
                lambda: WebhookDelivery.objects.filter(
                    webhook=webhook, event_type="mesh.compliance.checked"
                ).count()
                >= 1,
                timeout=5.0,
                message="mesh.compliance.checked delivery not recorded",
            )
            deliveries = WebhookDelivery.objects.filter(
                webhook=webhook, event_type="mesh.compliance.checked"
            )
            self.assertEqual(deliveries.count(), 1)
            delivery = deliveries.first()
            self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)
            self.assertEqual(delivery.payload["data"]["domain_id"], domain_id)

    def test_mesh_topology_updated_webhook_delivery(self):
        """Test webhook delivery for mesh.topology.updated event via real HTTP server."""
        with TestWebhookServer(response_status=200) as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="Mesh Events Webhook",
                url=server.get_url(),
                secret="test-secret-key",
                event_types=self.mesh_event_types,
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )
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
                event_data=event_data,
            )
            wait_until(
                lambda: WebhookDelivery.objects.filter(
                    webhook=webhook, event_type="mesh.topology.updated"
                ).count()
                >= 1,
                timeout=5.0,
                message="mesh.topology.updated delivery not recorded",
            )
            deliveries = WebhookDelivery.objects.filter(
                webhook=webhook, event_type="mesh.topology.updated"
            )
            self.assertEqual(deliveries.count(), 1)
            delivery = deliveries.first()
            self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)
            self.assertEqual(delivery.payload["data"]["domain_count"], 5)

    def test_mesh_health_status_changed_webhook_delivery(self):
        """Test webhook delivery for mesh.health.status_changed event via real HTTP server."""
        with TestWebhookServer(response_status=200) as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="Mesh Events Webhook",
                url=server.get_url(),
                secret="test-secret-key",
                event_types=self.mesh_event_types,
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )
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
                event_data=event_data,
            )
            wait_until(
                lambda: WebhookDelivery.objects.filter(
                    webhook=webhook, event_type="mesh.health.status_changed"
                ).count()
                >= 1,
                timeout=5.0,
                message="mesh.health.status_changed delivery not recorded",
            )
            deliveries = WebhookDelivery.objects.filter(
                webhook=webhook, event_type="mesh.health.status_changed"
            )
            self.assertEqual(deliveries.count(), 1)
            delivery = deliveries.first()
            self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)
            self.assertEqual(delivery.payload["data"]["domain_id"], domain_id)
            self.assertEqual(delivery.payload["data"]["new_status"], "DEGRADED")

    def test_webhook_filters_mesh_events(self):
        """Test that webhook only receives subscribed mesh events (real server)."""
        with TestWebhookServer(response_status=200) as server:
            specific_webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="Domain Created Only",
                url=server.get_url(),
                secret="test-secret",
                event_types=["mesh.domain.created"],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )
            domain_id = str(uuid.uuid4())
            WebhookDeliveryService.trigger_webhook(
                tenant_id=str(self.tenant.id),
                event_type="mesh.domain.created",
                resource_type="DATA_MESH_DOMAIN",
                resource_id=domain_id,
                event_data={"domain_id": domain_id, "name": "Test Domain"},
            )
            WebhookDeliveryService.trigger_webhook(
                tenant_id=str(self.tenant.id),
                event_type="mesh.domain.updated",
                resource_type="DATA_MESH_DOMAIN",
                resource_id=domain_id,
                event_data={"domain_id": domain_id, "changes": {}},
            )
            WebhookDeliveryService.trigger_webhook(
                tenant_id=str(self.tenant.id),
                event_type="mesh.policy.applied",
                resource_type="POLICY_APPLICATION",
                resource_id=str(uuid.uuid4()),
                event_data={"policy_application_id": str(uuid.uuid4()), "domain_id": domain_id},
            )
            wait_until(
                lambda: WebhookDelivery.objects.filter(webhook=specific_webhook).count() >= 1,
                timeout=5.0,
                message="mesh filter delivery not recorded",
            )
            deliveries = WebhookDelivery.objects.filter(webhook=specific_webhook)
            self.assertEqual(deliveries.count(), 1)
            self.assertEqual(deliveries.first().event_type, "mesh.domain.created")
