"""
Tests for event publishers.
"""
import json
import uuid
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings

from hub.apps.core.events.bus import EventBus
from hub.apps.core.events.models import Event
from hub.apps.core.events.publisher import EventPublisher, publish_event
from hub.apps.tenants.models import Tenant


@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,
)
class EventPublisherTest(TestCase):
    """Test event publisher functionality."""

    def setUp(self):
        """Set up test data."""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
        )
        self.redis_client = Mock()
        self.event_bus = EventBus(
            redis_client=self.redis_client,
            force_sync_persistence=True,
        )
        self.redis_client.publish.return_value = 1

    @patch("hub.apps.core.events.publisher.get_event_bus")
    def test_event_publisher_publish(self, mock_get_bus):
        """Test EventPublisher.publish persists event and publishes correct payload."""
        mock_get_bus.return_value = self.event_bus

        contract_id = str(uuid.uuid4())
        publisher = EventPublisher(
            service_name="test_service",
            tenant_id=str(self.tenant.id),
        )

        event_id = publisher.publish(
            event_type="contract.created",
            data={"contract_id": contract_id},
            skip_deduplication=True,
        )

        # event_id must be a valid UUID
        uuid.UUID(event_id)

        # Verify Redis publish received the correct channel and payload
        self.redis_client.publish.assert_called_once()
        call_args = self.redis_client.publish.call_args
        channel = call_args[0][0]
        self.assertIn("contract", channel)
        self.assertIn("created", channel)
        self.assertEqual(channel, "events:contract:created")

        payload = json.loads(call_args[0][1])
        self.assertEqual(payload["event_type"], "contract.created")
        self.assertEqual(payload["event_id"], event_id)
        self.assertEqual(payload["data"]["contract_id"], contract_id)

        # Verify the event was persisted to the DB
        event_obj = Event.objects.get(event_id=event_id)
        self.assertEqual(event_obj.event_type, "contract.created")
        self.assertEqual(event_obj.data["contract_id"], contract_id)
        self.assertEqual(event_obj.source_service, "test_service")
        self.assertEqual(str(event_obj.tenant_id), str(self.tenant.id))

    @patch("hub.apps.core.events.publisher.get_event_bus")
    def test_publish_event_function(self, mock_get_bus):
        """Test publish_event convenience function persists and publishes correctly."""
        mock_get_bus.return_value = self.event_bus

        contract_id = str(uuid.uuid4())
        event_id = publish_event(
            event_type="contract.created",
            data={"contract_id": contract_id},
            tenant_id=str(self.tenant.id),
            skip_deduplication=True,
        )

        # event_id must be a valid UUID
        uuid.UUID(event_id)

        # Verify Redis publish received the correct channel and payload
        self.redis_client.publish.assert_called_once()
        call_args = self.redis_client.publish.call_args
        channel = call_args[0][0]
        self.assertEqual(channel, "events:contract:created")

        payload = json.loads(call_args[0][1])
        self.assertEqual(payload["event_type"], "contract.created")
        self.assertEqual(payload["event_id"], event_id)
        self.assertEqual(payload["data"]["contract_id"], contract_id)

        # Verify the event was persisted to the DB
        event_obj = Event.objects.get(event_id=event_id)
        self.assertEqual(event_obj.event_type, "contract.created")
        self.assertEqual(event_obj.data["contract_id"], contract_id)
