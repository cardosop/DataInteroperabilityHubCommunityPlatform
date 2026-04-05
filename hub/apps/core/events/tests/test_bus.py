"""
Tests for event bus.
"""
import uuid
import json
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, override_settings
from django.utils import timezone
from datetime import datetime, timedelta

from hub.apps.core.events.bus import EventBus, EventPublishError, EventSubscribeError
from hub.apps.core.events.models import Event, DeadLetterQueue, EventSubscription
from hub.apps.tenants.models import Tenant

@override_settings(EVENT_BUS_ASYNC_PERSISTENCE=False, EVENT_BUS_WRITE_BEHIND_ENABLED=False)
class EventBusTest(TestCase):
    """Test event bus functionality."""

    def setUp(self):
        """Set up test data."""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}"
        )
        self.redis_client = Mock()
        self.event_bus = EventBus(redis_client=self.redis_client)
    
    def test_publish_event_success(self):
        """Test publishing an event successfully."""
        self.redis_client.publish.return_value = 1
        
        event_id = self.event_bus.publish(
            event_type="contract.created",
            data={"contract_id": str(uuid.uuid4())},
            tenant_id=str(self.tenant.id)
        )
        
        self.assertIsNotNone(event_id)
        self.redis_client.publish.assert_called_once()
        call_args = self.redis_client.publish.call_args
        channel = call_args[0][0] if call_args[0] else call_args[1].get("channel")
        payload = json.loads(call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("message"))
        self.assertEqual(channel, "events:contract:created")
        self.assertEqual(payload["event_type"], "contract.created")
        self.assertEqual(payload["event_id"], str(event_id))

        # Verify event persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "contract.created")
        self.assertEqual(str(event.tenant_id), str(self.tenant.id))
    
    def test_publish_event_invalid(self):
        """Test publishing invalid event."""
        with self.assertRaises(EventPublishError):
            self.event_bus.publish(
                event_type="InvalidEventType",
                data={}
            )
    
    def test_publish_event_redis_failure(self):
        """Test publishing event when Redis fails."""
        self.redis_client.publish.side_effect = Exception("Redis error")
        
        # Should still persist event
        event_id = self.event_bus.publish(
            event_type="contract.created",
            data={"contract_id": str(uuid.uuid4())},
            tenant_id=str(self.tenant.id)
        )
        
        # Event should be persisted with correct fields
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "contract.created")
        self.assertIn("contract_id", event.data)
        self.assertEqual(str(event.tenant_id), str(self.tenant.id))
    
    @override_settings(EVENT_BUS_ENABLE_PERSISTENCE=False)
    def test_publish_event_no_persistence(self):
        """Test publishing event without persistence."""
        # Recreate event bus to pick up new setting
        from hub.apps.core.events.bus import EventBus
        event_bus = EventBus(redis_client=self.redis_client)
        self.redis_client.publish.return_value = 1
        
        event_id = event_bus.publish(
            event_type="contract.created",
            data={"contract_id": str(uuid.uuid4())}
        )
        
        # Event should not be persisted
        self.assertFalse(Event.objects.filter(event_id=event_id).exists())
    
    def test_replay_events(self):
        """Test replaying events."""
        # Create test events
        event1 = Event.objects.create(
            event_id=uuid.uuid4(),
            event_type="contract.created",
            event_version="1.0.0",
            timestamp=timezone.now() - timedelta(hours=2),
            source_service="hub",
            tenant_id=self.tenant.id,
            data={"contract_id": str(uuid.uuid4())}
        )
        
        event2 = Event.objects.create(
            event_id=uuid.uuid4(),
            event_type="contract.updated",
            event_version="1.0.0",
            timestamp=timezone.now() - timedelta(hours=1),
            source_service="hub",
            tenant_id=self.tenant.id,
            data={"contract_id": str(uuid.uuid4())}
        )
        
        # Replay events
        events = self.event_bus.replay_events(
            event_type="contract.created",
            tenant_id=str(self.tenant.id)
        )
        
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "contract.created")
        self.assertEqual(events[0]["event_id"], str(event1.event_id))
        self.assertNotIn(str(event2.event_id), [e["event_id"] for e in events])
    
    def test_replay_events_with_time_range(self):
        """Test replaying events with time range."""
        now = timezone.now()
        unique_type = f"timerange.test.{uuid.uuid4().hex[:8]}"

        event1 = Event.objects.create(
            event_id=uuid.uuid4(),
            event_type=unique_type,
            event_version="1.0.0",
            timestamp=now - timedelta(hours=2),
            source_service="hub",
            tenant_id=self.tenant.id,
            data={}
        )

        event2 = Event.objects.create(
            event_id=uuid.uuid4(),
            event_type=unique_type,
            event_version="1.0.0",
            timestamp=now - timedelta(hours=1),
            source_service="hub",
            tenant_id=self.tenant.id,
            data={}
        )

        # Replay events in time range, filtered by unique type to avoid cross-test leakage
        events = self.event_bus.replay_events(
            event_type=unique_type,
            start_time=now - timedelta(hours=1, minutes=30),
            end_time=now
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_id"], str(event2.event_id))
    
    def test_send_to_dlq(self):
        """Test sending event to dead letter queue."""
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "contract.created",
            "data": {}
        }
        
        self.event_bus._send_to_dlq(
            subscriber_name="test_subscriber",
            event=event,
            error_message="Test error",
            retry_count=3
        )
        
        dlq_entry = DeadLetterQueue.objects.get(
            subscriber="test_subscriber",
            event_type="contract.created"
        )
        
        self.assertEqual(dlq_entry.retry_count, 3)
        self.assertEqual(dlq_entry.error_message, "Test error")
    
    def test_get_channel(self):
        """Test getting Redis channel name."""
        channel = self.event_bus._get_channel("contract.created")
        self.assertEqual(channel, "events:contract:created")
        
        channel = self.event_bus._get_channel("asset.activated")
        self.assertEqual(channel, "events:asset:activated")

        channel = self.event_bus._get_channel("workflow.step.started")
        self.assertEqual(channel, "events:workflow:step:started")

