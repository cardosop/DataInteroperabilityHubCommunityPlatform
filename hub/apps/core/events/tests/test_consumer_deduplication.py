"""
Tests for event consumer deduplication integration.

These tests use real Redis and real event bus (no mocks) to ensure proper integration.
"""
import uuid
from django.test import TestCase, override_settings
from django.conf import settings
import redis
import structlog

from hub.apps.core.events.bus import EventBus, get_event_bus
from hub.apps.core.events.deduplication import (
    generate_deduplication_key,
    check_event_duplicate,
    store_event_id,
    get_redis_client as get_deduplication_redis_client,
    DEFAULT_DEDUPLICATION_TTL,
)
from hub.apps.tenants.models import Tenant

uid = uuid.uuid4().hex[:8]

logger = structlog.get_logger(__name__)


def get_real_redis_client_or_none():
    """Get real Redis client for events (deduplication) or return None if unavailable."""
    try:
        # Use REDIS_EVENTS_URL (same Redis the deduplication module uses)
        redis_url = getattr(settings, 'REDIS_EVENTS_URL', None) or \
            getattr(settings, 'REDIS_URL', 'redis://redis-events-test:6379/0')
        client = redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2
        )
        client.ping()
        return client
    except Exception:
        return None


class EventConsumerDeduplicationTest(TestCase):
    """Test event consumer deduplication integration with real Redis."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}"
        )

        # Use the same Redis that the deduplication module uses (events Redis)
        self.redis_client = get_real_redis_client_or_none()
        if self.redis_client is None:
            self.skipTest("Redis not available for integration tests")

        # Create event bus with Redis client
        self.event_bus = EventBus(redis_client=self.redis_client)

        # Clear deduplication keys before each test
        try:
            keys = self.redis_client.keys("event:dedup:*")
            if keys:
                self.redis_client.delete(*keys)
        except Exception:
            pass

    def tearDown(self):
        """Clean up test fixtures."""
        try:
            keys = self.redis_client.keys("event:dedup:*")
            if keys:
                self.redis_client.delete(*keys)
        except Exception:
            pass

    def test_consumer_skips_duplicate_event(self):
        """Test that consumer skips processing duplicate events."""
        event_type = "contract.created"
        event_data = {"contract_id": str(uuid.uuid4()), "name": "Test Contract"}
        event_id = str(uuid.uuid4())

        # Create event dictionary
        event = {
            "event_id": event_id,
            "event_type": event_type,
            "event_version": "1.0.0",
            "timestamp": "2024-01-01T00:00:00Z",
            "source": {
                "service": "hub",
                "tenant_id": str(self.tenant.id)
            },
            "data": event_data
        }

        # Store event ID in Redis (simulating already processed event)
        deduplication_key = generate_deduplication_key(event_type, event_data)
        store_event_id(
            deduplication_key,
            event_id,
            redis_client=self.redis_client
        )

        # Track handler calls
        handler_called = []

        def test_handler(event_dict):
            handler_called.append(event_dict)

        # Try to handle event - should skip due to deduplication
        self.event_bus._handle_event(
            subscriber_name="test_subscriber",
            event=event,
            handler=test_handler,
            retry_count=0
        )

        # Handler should not be called (duplicate skipped)
        self.assertEqual(len(handler_called), 0)

    def test_consumer_processes_new_event(self):
        """Test that consumer processes new (non-duplicate) events."""
        event_type = "contract.created"
        event_data = {"contract_id": str(uuid.uuid4()), "name": "Test Contract"}
        event_id = str(uuid.uuid4())

        # Create event dictionary
        event = {
            "event_id": event_id,
            "event_type": event_type,
            "event_version": "1.0.0",
            "timestamp": "2024-01-01T00:00:00Z",
            "source": {
                "service": "hub",
                "tenant_id": str(self.tenant.id)
            },
            "data": event_data
        }

        # Track handler calls
        handler_called = []

        def test_handler(event_dict):
            handler_called.append(event_dict)

        # Handle event - should process (not duplicate)
        self.event_bus._handle_event(
            subscriber_name="test_subscriber",
            event=event,
            handler=test_handler,
            retry_count=0
        )

        # Handler should be called
        self.assertEqual(len(handler_called), 1)
        self.assertEqual(handler_called[0]["event_id"], event_id)

        # Verify event ID is stored after processing
        deduplication_key = generate_deduplication_key(event_type, event_data)
        is_dup, stored_id = check_event_duplicate(
            deduplication_key,
            redis_client=self.redis_client
        )
        self.assertTrue(is_dup)
        self.assertEqual(stored_id, event_id)

    def test_consumer_stores_event_id_after_processing(self):
        """Test that consumer stores event ID after successful processing."""
        event_type = "contract.created"
        event_data = {"contract_id": str(uuid.uuid4())}
        event_id = str(uuid.uuid4())

        event = {
            "event_id": event_id,
            "event_type": event_type,
            "data": event_data,
            "source": {"tenant_id": str(self.tenant.id)}
        }

        def test_handler(event_dict):
            pass  # Simple handler

        # Process event
        self.event_bus._handle_event(
            subscriber_name="test_subscriber",
            event=event,
            handler=test_handler,
            retry_count=0
        )

        # Verify event ID is stored
        deduplication_key = generate_deduplication_key(event_type, event_data)
        is_dup, stored_id = check_event_duplicate(
            deduplication_key,
            redis_client=self.redis_client
        )
        self.assertTrue(is_dup)
        self.assertEqual(stored_id, event_id)

    def test_consumer_handles_duplicate_after_first_processing(self):
        """Test that consumer skips duplicate event after first processing."""
        event_type = "contract.created"
        event_data = {"contract_id": str(uuid.uuid4()), "name": "Test Contract"}
        event_id = str(uuid.uuid4())

        event = {
            "event_id": event_id,
            "event_type": event_type,
            "data": event_data,
            "source": {"tenant_id": str(self.tenant.id)}
        }

        handler_called = []

        def test_handler(event_dict):
            handler_called.append(event_dict)

        # First processing - should succeed
        self.event_bus._handle_event(
            subscriber_name="test_subscriber",
            event=event,
            handler=test_handler,
            retry_count=0
        )

        self.assertEqual(len(handler_called), 1)

        # Second processing - should skip (duplicate)
        handler_called.clear()
        self.event_bus._handle_event(
            subscriber_name="test_subscriber",
            event=event,
            handler=test_handler,
            retry_count=0
        )

        # Handler should not be called again
        self.assertEqual(len(handler_called), 0)

    def test_consumer_allows_different_events(self):
        """Test that consumer allows different events to be processed."""
        event_type = "contract.created"
        event_data1 = {"contract_id": str(uuid.uuid4()), "name": "Contract 1"}
        event_data2 = {"contract_id": str(uuid.uuid4()), "name": "Contract 2"}

        event1 = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "data": event_data1,
            "source": {"tenant_id": str(self.tenant.id)}
        }

        event2 = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "data": event_data2,
            "source": {"tenant_id": str(self.tenant.id)}
        }

        handler_called = []

        def test_handler(event_dict):
            handler_called.append(event_dict)

        # Process first event
        self.event_bus._handle_event(
            subscriber_name="test_subscriber",
            event=event1,
            handler=test_handler,
            retry_count=0
        )

        # Process second event (different data) - should succeed
        self.event_bus._handle_event(
            subscriber_name="test_subscriber",
            event=event2,
            handler=test_handler,
            retry_count=0
        )

        # Both handlers should be called
        self.assertEqual(len(handler_called), 2)

    def test_consumer_deduplication_per_event_type(self):
        """Test that deduplication works per event type."""
        event_data = {"contract_id": str(uuid.uuid4())}

        event1 = {
            "event_id": str(uuid.uuid4()),
            "event_type": "contract.created",
            "data": event_data,
            "source": {"tenant_id": str(self.tenant.id)}
        }

        event2 = {
            "event_id": str(uuid.uuid4()),
            "event_type": "contract.updated",
            "data": event_data,  # Same data, different type
            "source": {"tenant_id": str(self.tenant.id)}
        }

        handler_called = []

        def test_handler(event_dict):
            handler_called.append(event_dict)

        # Process created event
        self.event_bus._handle_event(
            subscriber_name="test_subscriber",
            event=event1,
            handler=test_handler,
            retry_count=0
        )

        # Process updated event (same data, different type) - should succeed
        self.event_bus._handle_event(
            subscriber_name="test_subscriber",
            event=event2,
            handler=test_handler,
            retry_count=0
        )

        # Both handlers should be called (different event types)
        self.assertEqual(len(handler_called), 2)

        # Try to process created again - should skip (duplicate)
        handler_called.clear()
        self.event_bus._handle_event(
            subscriber_name="test_subscriber",
            event=event1,
            handler=test_handler,
            retry_count=0
        )

        # Handler should not be called (duplicate)
        self.assertEqual(len(handler_called), 0)

    def test_consumer_handles_redis_unavailable_gracefully(self):
        """Test that consumer handles Redis unavailability gracefully."""
        event_type = "contract.created"
        event_data = {"contract_id": str(uuid.uuid4())}
        event_id = str(uuid.uuid4())

        event = {
            "event_id": event_id,
            "event_type": event_type,
            "data": event_data,
            "source": {"tenant_id": str(self.tenant.id)}
        }

        handler_called = []

        def test_handler(event_dict):
            handler_called.append(event_dict)

        # Temporarily break Redis connection
        original_redis = self.event_bus.redis_client
        self.event_bus.redis_client = None

        # Should still process event (fail open)
        self.event_bus._handle_event(
            subscriber_name="test_subscriber",
            event=event,
            handler=test_handler,
            retry_count=0
        )

        # Handler should be called (fail open behavior)
        self.assertEqual(len(handler_called), 1)

        # Restore Redis client
        self.event_bus.redis_client = original_redis

    def test_consumer_deduplication_with_nested_data(self):
        """Test deduplication with nested event data."""
        event_type = "contract.created"
        event_data = {
            "contract_id": str(uuid.uuid4()),
            "metadata": {
                "nested": {"deep": "value"},
                "list": [1, 2, 3]
            }
        }

        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "data": event_data,
            "source": {"tenant_id": str(self.tenant.id)}
        }

        handler_called = []

        def test_handler(event_dict):
            handler_called.append(event_dict)

        # First processing
        self.event_bus._handle_event(
            subscriber_name="test_subscriber",
            event=event,
            handler=test_handler,
            retry_count=0
        )

        self.assertEqual(len(handler_called), 1)

        # Second processing with same nested data - should skip
        handler_called.clear()
        self.event_bus._handle_event(
            subscriber_name="test_subscriber",
            event=event,
            handler=test_handler,
            retry_count=0
        )

        # Handler should not be called (duplicate)
        self.assertEqual(len(handler_called), 0)

    def test_consumer_deduplication_workflow_complete(self):
        """Test complete consumer deduplication workflow."""
        event_type = "contract.created"
        event_data = {"contract_id": str(uuid.uuid4()), "name": "Test Contract"}
        event_id = str(uuid.uuid4())

        event = {
            "event_id": event_id,
            "event_type": event_type,
            "data": event_data,
            "source": {"tenant_id": str(self.tenant.id)}
        }

        handler_called = []

        def test_handler(event_dict):
            handler_called.append(event_dict)

        # Step 1: Check if duplicate (should not be)
        deduplication_key = generate_deduplication_key(event_type, event_data)
        is_dup, existing_id = check_event_duplicate(
            deduplication_key,
            redis_client=self.redis_client
        )
        self.assertFalse(is_dup)
        self.assertIsNone(existing_id)

        # Step 2: Process event
        self.event_bus._handle_event(
            subscriber_name="test_subscriber",
            event=event,
            handler=test_handler,
            retry_count=0
        )

        # Handler should be called
        self.assertEqual(len(handler_called), 1)

        # Step 3: Verify event ID is stored
        is_dup, stored_id = check_event_duplicate(
            deduplication_key,
            redis_client=self.redis_client
        )
        self.assertTrue(is_dup)
        self.assertEqual(stored_id, event_id)

        # Step 4: Try to process again - should skip
        handler_called.clear()
        self.event_bus._handle_event(
            subscriber_name="test_subscriber",
            event=event,
            handler=test_handler,
            retry_count=0
        )

        # Handler should not be called (duplicate)
        self.assertEqual(len(handler_called), 0)

    def test_consumer_deduplication_ttl_respected(self):
        """Test that deduplication TTL is respected."""
        event_type = "contract.created"
        event_data = {"contract_id": str(uuid.uuid4())}
        event_id = str(uuid.uuid4())

        event = {
            "event_id": event_id,
            "event_type": event_type,
            "data": event_data,
            "source": {"tenant_id": str(self.tenant.id)}
        }

        def test_handler(event_dict):
            pass

        # Process event
        self.event_bus._handle_event(
            subscriber_name="test_subscriber",
            event=event,
            handler=test_handler,
            retry_count=0
        )

        # Verify TTL is set
        deduplication_key = generate_deduplication_key(event_type, event_data)
        ttl = self.redis_client.ttl(deduplication_key)
        self.assertGreater(ttl, 0)
        self.assertLessEqual(ttl, DEFAULT_DEDUPLICATION_TTL)

    def test_consumer_deduplication_with_multiple_subscribers(self):
        """Test that deduplication works across multiple subscribers."""
        event_type = "contract.created"
        event_data = {"contract_id": str(uuid.uuid4())}
        event_id = str(uuid.uuid4())

        event = {
            "event_id": event_id,
            "event_type": event_type,
            "data": event_data,
            "source": {"tenant_id": str(self.tenant.id)}
        }

        handler1_called = []
        handler2_called = []

        def handler1(event_dict):
            handler1_called.append(event_dict)

        def handler2(event_dict):
            handler2_called.append(event_dict)

        # First subscriber processes event
        self.event_bus._handle_event(
            subscriber_name="subscriber1",
            event=event,
            handler=handler1,
            retry_count=0
        )

        self.assertEqual(len(handler1_called), 1)

        # Second subscriber tries to process same event - should skip (duplicate)
        self.event_bus._handle_event(
            subscriber_name="subscriber2",
            event=event,
            handler=handler2,
            retry_count=0
        )

        # Handler2 should not be called (duplicate detected)
        self.assertEqual(len(handler2_called), 0)

