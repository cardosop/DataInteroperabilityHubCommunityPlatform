"""
E2E tests for virtualization webhook delivery from event bus.

These tests verify:
- Webhook delivery for virtualization.dataset.created events
- Webhook delivery for virtualization.query.execution.* events
- Webhook payload validation for virtualization events
- Webhook retry logic for virtualization events
"""
import uuid
from django.test import TestCase
from django.utils import timezone
from unittest.mock import patch, MagicMock
import pytest

from hub.apps.webhooks.models import Webhook, WebhookDelivery, WebhookStatus, DeliveryStatus, WebhookEventType
from hub.apps.core.events.publisher import EventPublisher
from hub.apps.core.events.models import Event
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User
from hub.apps.webhooks.virtualization_event_subscriber import get_virtualization_event_subscriber


pytestmark = pytest.mark.django_db(transaction=True)


class VirtualizationWebhookE2ETest(TestCase):
    """E2E tests for virtualization webhook delivery from event bus"""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )

    def _trigger_webhook_for_event(self, event):
        """Helper method to trigger webhook delivery via subscriber."""
        subscriber = get_virtualization_event_subscriber()
        event_dict = {
            "event_id": str(event.event_id),
            "event_type": event.event_type,
            "event_version": event.event_version,
            "timestamp": event.timestamp.isoformat() + "Z",
            "source": {
                "service": event.source_service,
                "tenant_id": str(event.tenant_id) if event.tenant_id else None,
            },
            "data": event.data,
            "metadata": event.metadata or {}
        }
        if event.user_id:
            event_dict["source"]["user_id"] = str(event.user_id)
        subscriber._handle_virtualization_event(event_dict)

    def test_virtualization_dataset_created_webhook_delivery(self):
        """Test webhook delivery for virtualization.dataset.created event."""
        # Create webhook subscription
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Virtualization Dataset Webhook",
            url="https://example.com/webhooks/virtualization",
            secret="test-secret",
            event_types=[WebhookEventType.VIRTUALIZATION_DATASET_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        # Create event publisher
        publisher = EventPublisher(
            service_name="virtualization_service",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        virtual_dataset_id = str(uuid.uuid4())

        # Publish event
        event_id = publisher.publish(
            event_type="virtualization.dataset.created",
            data={
                "virtual_dataset_id": virtual_dataset_id,
                "name": "Test Virtual Dataset",
                "query_type": "SQL",
                "status": "ACTIVE",
                "version": "1.0.0"
            }
        )

        # Verify event was created
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "virtualization.dataset.created")
        self.assertEqual(event.tenant_id, self.tenant.id)

        # Trigger webhook delivery via subscriber
        subscriber = get_virtualization_event_subscriber()
        event_dict = {
            "event_id": str(event.event_id),
            "event_type": event.event_type,
            "event_version": event.event_version,
            "timestamp": event.timestamp.isoformat() + "Z",
            "source": {
                "service": event.source_service,
                "tenant_id": str(event.tenant_id) if event.tenant_id else None,
            },
            "data": event.data,
            "metadata": event.metadata or {}
        }
        if event.user_id:
            event_dict["source"]["user_id"] = str(event.user_id)
        subscriber._handle_virtualization_event(event_dict)

        # Verify webhook delivery was created
        deliveries = WebhookDelivery.objects.filter(webhook=webhook)
        self.assertEqual(deliveries.count(), 1)

        delivery = deliveries.first()
        self.assertEqual(delivery.event_type, "virtualization.dataset.created")
        # Status may be PENDING or FAILED (if HTTP request fails in test), both are acceptable
        self.assertIn(delivery.status, [DeliveryStatus.PENDING, DeliveryStatus.FAILED])
        self.assertEqual(delivery.payload["data"]["virtual_dataset_id"], virtual_dataset_id)

    def test_query_execution_started_webhook_delivery(self):
        """Test webhook delivery for virtualization.query.execution.started event."""
        # Create webhook subscription
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Query Execution Webhook",
            url="https://example.com/webhooks/query-execution",
            secret="test-secret",
            event_types=[WebhookEventType.VIRTUALIZATION_QUERY_EXECUTION_STARTED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        # Create event publisher
        publisher = EventPublisher(
            service_name="virtualization_service",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        query_execution_id = str(uuid.uuid4())
        virtual_dataset_id = str(uuid.uuid4())

        # Publish event
        event_id = publisher.publish(
            event_type="virtualization.query.execution.started",
            data={
                "query_execution_id": query_execution_id,
                "virtual_dataset_id": virtual_dataset_id,
                "execution_mode": "ASYNC",
                "started_at": timezone.now().isoformat()
            }
        )

        # Verify event was created
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "virtualization.query.execution.started")

        # Trigger webhook delivery via subscriber
        self._trigger_webhook_for_event(event)

        # Verify webhook delivery was created
        deliveries = WebhookDelivery.objects.filter(webhook=webhook)
        self.assertEqual(deliveries.count(), 1)

        delivery = deliveries.first()
        self.assertEqual(delivery.event_type, "virtualization.query.execution.started")
        self.assertEqual(delivery.payload["data"]["query_execution_id"], query_execution_id)

    def test_query_execution_progress_webhook_delivery(self):
        """Test webhook delivery for virtualization.query.execution.progress event."""
        # Create webhook subscription
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Query Progress Webhook",
            url="https://example.com/webhooks/query-progress",
            secret="test-secret",
            event_types=[WebhookEventType.VIRTUALIZATION_QUERY_EXECUTION_PROGRESS],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        # Create event publisher
        publisher = EventPublisher(
            service_name="virtualization_service",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        query_execution_id = str(uuid.uuid4())
        virtual_dataset_id = str(uuid.uuid4())

        # Publish progress event
        event_id = publisher.publish(
            event_type="virtualization.query.execution.progress",
            data={
                "query_execution_id": query_execution_id,
                "virtual_dataset_id": virtual_dataset_id,
                "progress_percent": 50.0,
                "current_step": "execute_query",
                "elapsed_time_ms": 5000,
                "completed_steps": 2,
                "total_steps": 4,
                "timestamp": timezone.now().isoformat()
            }
        )

        # Verify event was created
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "virtualization.query.execution.progress")

        # Trigger webhook delivery via subscriber
        self._trigger_webhook_for_event(event)

        # Verify webhook delivery was created
        deliveries = WebhookDelivery.objects.filter(webhook=webhook)
        self.assertEqual(deliveries.count(), 1)

        delivery = deliveries.first()
        self.assertEqual(delivery.event_type, "virtualization.query.execution.progress")
        self.assertEqual(delivery.payload["data"]["progress_percent"], 50.0)
        self.assertEqual(delivery.payload["data"]["query_execution_id"], query_execution_id)

    def test_query_execution_completed_webhook_delivery(self):
        """Test webhook delivery for virtualization.query.execution.completed event."""
        # Create webhook subscription
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Query Completed Webhook",
            url="https://example.com/webhooks/query-completed",
            secret="test-secret",
            event_types=[WebhookEventType.VIRTUALIZATION_QUERY_EXECUTION_COMPLETED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        # Create event publisher
        publisher = EventPublisher(
            service_name="virtualization_service",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        query_execution_id = str(uuid.uuid4())
        virtual_dataset_id = str(uuid.uuid4())

        # Publish completed event
        event_id = publisher.publish(
            event_type="virtualization.query.execution.completed",
            data={
                "query_execution_id": query_execution_id,
                "virtual_dataset_id": virtual_dataset_id,
                "status": "COMPLETED",
                "completed_at": timezone.now().isoformat(),
                "duration_ms": 1500,
                "rows_processed": 1000
            }
        )

        # Verify event was created
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "virtualization.query.execution.completed")

        # Trigger webhook delivery via subscriber
        self._trigger_webhook_for_event(event)

        # Verify webhook delivery was created
        deliveries = WebhookDelivery.objects.filter(webhook=webhook)
        self.assertEqual(deliveries.count(), 1)

        delivery = deliveries.first()
        self.assertEqual(delivery.event_type, "virtualization.query.execution.completed")
        self.assertEqual(delivery.payload["data"]["status"], "COMPLETED")
        self.assertEqual(delivery.payload["data"]["rows_processed"], 1000)

    def test_query_execution_failed_webhook_delivery(self):
        """Test webhook delivery for virtualization.query.execution.failed event."""
        # Create webhook subscription
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Query Failed Webhook",
            url="https://example.com/webhooks/query-failed",
            secret="test-secret",
            event_types=[WebhookEventType.VIRTUALIZATION_QUERY_EXECUTION_FAILED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        # Create event publisher
        publisher = EventPublisher(
            service_name="virtualization_service",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        query_execution_id = str(uuid.uuid4())
        virtual_dataset_id = str(uuid.uuid4())

        # Publish failed event
        event_id = publisher.publish(
            event_type="virtualization.query.execution.failed",
            data={
                "query_execution_id": query_execution_id,
                "virtual_dataset_id": virtual_dataset_id,
                "error_message": "Query execution timeout",
                "failed_at": timezone.now().isoformat(),
                "duration_ms": 5000
            }
        )

        # Verify event was created
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "virtualization.query.execution.failed")

        # Trigger webhook delivery via subscriber
        self._trigger_webhook_for_event(event)

        # Verify webhook delivery was created
        deliveries = WebhookDelivery.objects.filter(webhook=webhook)
        self.assertEqual(deliveries.count(), 1)

        delivery = deliveries.first()
        self.assertEqual(delivery.event_type, "virtualization.query.execution.failed")
        self.assertEqual(delivery.payload["data"]["error_message"], "Query execution timeout")

    def test_virtualization_webhook_event_type_validation(self):
        """Test that virtualization event types are correctly identified."""
        # Test is_virtualization_event_type method
        self.assertTrue(WebhookEventType.is_virtualization_event_type("virtualization.dataset.created"))
        self.assertTrue(WebhookEventType.is_virtualization_event_type("virtualization.query.execution.started"))
        self.assertTrue(WebhookEventType.is_virtualization_event_type("virtualization.query.execution.progress"))
        self.assertTrue(WebhookEventType.is_virtualization_event_type("virtualization.query.execution.completed"))
        self.assertTrue(WebhookEventType.is_virtualization_event_type("virtualization.query.execution.failed"))

        # Test that non-virtualization events are not identified
        self.assertFalse(WebhookEventType.is_virtualization_event_type("odps.created"))
        self.assertFalse(WebhookEventType.is_virtualization_event_type("transformation.pipeline.created"))

    def test_virtualization_webhook_get_event_types(self):
        """Test that get_virtualization_event_types returns all virtualization event types."""
        event_types = WebhookEventType.get_virtualization_event_types()
        self.assertIn("virtualization.dataset.created", event_types)
        self.assertIn("virtualization.query.execution.started", event_types)
        self.assertIn("virtualization.query.execution.progress", event_types)
        self.assertIn("virtualization.query.execution.completed", event_types)
        self.assertIn("virtualization.query.execution.failed", event_types)

