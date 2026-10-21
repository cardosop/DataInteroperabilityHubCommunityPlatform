"""
Integration tests for event bus with Redis.
"""

import uuid
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from django.utils import timezone

from hub.apps.core.events.bus import EventBus
from hub.apps.core.events.models import DeadLetterQueue, Event, EventSubscription
from hub.apps.core.events.publisher import EventPublisher
from hub.apps.core.events.subscriber import EventSubscriber
from hub.apps.tenants.models import Tenant

uid = uuid.uuid4().hex[:8]


@override_settings(EVENT_BUS_ASYNC_PERSISTENCE=False, EVENT_BUS_WRITE_BEHIND_ENABLED=False)
class EventBusIntegrationTest(TestCase):
    """Integration tests for event bus."""

    def setUp(self):
        """Set up test data."""
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")
        # Use mock Redis for integration tests
        self.redis_client = Mock()
        self.event_bus = EventBus(redis_client=self.redis_client)

    def test_publish_and_persist_event(self):
        """Test publishing event and verifying persistence."""
        self.redis_client.publish.return_value = 1

        event_id = self.event_bus.publish(
            event_type="contract.created",
            data={"contract_id": str(uuid.uuid4())},
            tenant_id=str(self.tenant.id),
        )

        # Verify event persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "contract.created")
        self.assertEqual(str(event.tenant_id), str(self.tenant.id))
        self.assertIsNotNone(event.data)

    def test_event_publisher_integration(self):
        """Test EventPublisher integration."""
        self.redis_client.publish.return_value = 1

        with patch("hub.apps.core.events.publisher.get_event_bus", return_value=self.event_bus):
            publisher = EventPublisher(service_name="test_service", tenant_id=str(self.tenant.id))

            event_id = publisher.publish(
                event_type="asset.created", data={"asset_id": str(uuid.uuid4())}
            )

            self.assertIsNotNone(event_id)
            self.redis_client.publish.assert_called_once()

    @patch("hub.apps.core.utils.test_mode.should_skip_initialization", return_value=False)
    def test_event_subscription_registration(self, mock_skip):
        """Test event subscription registration."""
        handler = Mock()

        subscriber = EventSubscriber("test_subscriber")
        subscriber.subscribe("contract.*", handler)

        # Verify subscription created with correct fields
        subscription = EventSubscription.objects.get(
            subscriber_name="test_subscriber", event_type_pattern="contract.*"
        )
        self.assertEqual(subscription.subscriber_name, "test_subscriber")
        self.assertEqual(subscription.event_type_pattern, "contract.*")
        self.assertTrue(subscription.is_active)

    def test_event_replay_integration(self):
        """Test event replay functionality."""
        # Create test events
        event1 = Event.objects.create(
            event_id=uuid.uuid4(),
            event_type="contract.created",
            event_version="1.0.0",
            timestamp=timezone.now(),
            source_service="hub",
            tenant_id=self.tenant.id,
            data={"contract_id": str(uuid.uuid4())},
        )

        # Replay events
        events = self.event_bus.replay_events(
            event_type="contract.created", tenant_id=str(self.tenant.id)
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_id"], str(event1.event_id))
        self.assertEqual(events[0]["event_type"], "contract.created")

    def test_dead_letter_queue_integration(self):
        """Test dead letter queue functionality."""
        event = {"event_id": str(uuid.uuid4()), "event_type": "contract.created", "data": {}}

        self.event_bus._send_to_dlq(
            subscriber_name="test_subscriber",
            event=event,
            error_message="Test error",
            retry_count=3,
        )

        dlq_entry = DeadLetterQueue.objects.get(
            subscriber="test_subscriber", event_type="contract.created"
        )

        self.assertEqual(dlq_entry.retry_count, 3)
        self.assertEqual(dlq_entry.error_message, "Test error")
        self.assertIsNotNone(dlq_entry.event)
