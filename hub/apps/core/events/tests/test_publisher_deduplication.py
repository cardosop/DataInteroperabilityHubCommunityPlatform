"""
Tests for event publisher deduplication integration.

These tests use real Redis and real event bus (no mocks) to ensure proper integration.
"""
import uuid
from django.test import TestCase, override_settings
from django.conf import settings
import redis
import structlog

from hub.apps.core.events.publisher import EventPublisher, publish_event
from hub.apps.core.events.deduplication import (
    generate_deduplication_key,
    check_event_duplicate,
    store_event_id,
    is_event_duplicate,
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


class EventPublisherDeduplicationTest(TestCase):
    """Test event publisher deduplication integration with real Redis."""

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

    def test_publisher_skips_duplicate_event(self):
        """Test that publisher skips publishing duplicate events."""
        event_type = "contract.created"
        event_data = {"contract_id": str(uuid.uuid4()), "name": "Test Contract"}

        publisher = EventPublisher(
            service_name="test_service",
            tenant_id=str(self.tenant.id)
        )

        # First publish - should succeed
        event_id1 = publisher.publish(
            event_type=event_type,
            data=event_data
        )
        self.assertIsNotNone(event_id1)

        # Second publish with same data - should return existing event ID (deduplicated)
        event_id2 = publisher.publish(
            event_type=event_type,
            data=event_data
        )

        # Should return the same event ID (deduplicated)
        self.assertEqual(event_id1, event_id2)

    def test_publisher_allows_different_events(self):
        """Test that publisher allows different events to be published."""
        event_type = "contract.created"
        event_data1 = {"contract_id": str(uuid.uuid4()), "name": "Contract 1"}
        event_data2 = {"contract_id": str(uuid.uuid4()), "name": "Contract 2"}

        publisher = EventPublisher(
            service_name="test_service",
            tenant_id=str(self.tenant.id)
        )

        # First publish
        event_id1 = publisher.publish(
            event_type=event_type,
            data=event_data1
        )
        self.assertIsNotNone(event_id1)

        # Second publish with different data - should succeed (not duplicate)
        event_id2 = publisher.publish(
            event_type=event_type,
            data=event_data2
        )
        self.assertIsNotNone(event_id2)
        self.assertNotEqual(event_id1, event_id2)

    def test_publisher_deduplication_per_event_type(self):
        """Test that deduplication works per event type."""
        event_data = {"contract_id": str(uuid.uuid4())}

        publisher = EventPublisher(
            service_name="test_service",
            tenant_id=str(self.tenant.id)
        )

        # Publish created event
        event_id1 = publisher.publish(
            event_type="contract.created",
            data=event_data
        )

        # Publish updated event with same data - should succeed (different type)
        event_id2 = publisher.publish(
            event_type="contract.updated",
            data=event_data
        )

        self.assertNotEqual(event_id1, event_id2)

        # Try to publish created again - should be deduplicated
        event_id3 = publisher.publish(
            event_type="contract.created",
            data=event_data
        )
        self.assertEqual(event_id1, event_id3)

    def test_publish_event_function_deduplication(self):
        """Test that publish_event function respects deduplication."""
        event_type = "contract.created"
        event_data = {"contract_id": str(uuid.uuid4()), "name": "Test Contract"}

        # First publish
        event_id1 = publish_event(
            event_type=event_type,
            data=event_data,
            tenant_id=str(self.tenant.id)
        )
        self.assertIsNotNone(event_id1)

        # Second publish with same data - should be deduplicated
        event_id2 = publish_event(
            event_type=event_type,
            data=event_data,
            tenant_id=str(self.tenant.id)
        )
        self.assertEqual(event_id1, event_id2)

    def test_publisher_stores_event_id_after_publish(self):
        """Test that publisher stores event ID in Redis after successful publish."""
        event_type = "contract.created"
        event_data = {"contract_id": str(uuid.uuid4())}

        publisher = EventPublisher(
            service_name="test_service",
            tenant_id=str(self.tenant.id)
        )

        # Publish event
        event_id = publisher.publish(
            event_type=event_type,
            data=event_data
        )

        # Verify event ID is stored in Redis
        deduplication_key = generate_deduplication_key(event_type, event_data)
        is_dup, stored_id = check_event_duplicate(
            deduplication_key,
            redis_client=self.redis_client
        )
        self.assertTrue(is_dup)
        self.assertEqual(stored_id, event_id)

    def test_publisher_handles_redis_unavailable_gracefully(self):
        """Test that publisher handles Redis unavailability gracefully."""
        event_type = "contract.created"
        event_data = {"contract_id": str(uuid.uuid4())}

        publisher = EventPublisher(
            service_name="test_service",
            tenant_id=str(self.tenant.id)
        )

        # Temporarily break Redis connection
        original_redis_url = getattr(settings, 'REDIS_URL', None)
        with override_settings(REDIS_URL='redis://invalid-host:6379/0'):
            # Should still publish (fail open)
            event_id = publisher.publish(
                event_type=event_type,
                data=event_data
            )
            self.assertIsNotNone(event_id)

    def test_publisher_deduplication_with_tenant_id(self):
        """Test that deduplication works correctly with tenant IDs."""
        event_type = "contract.created"
        event_data = {"contract_id": str(uuid.uuid4())}

        publisher = EventPublisher(
            service_name="test_service",
            tenant_id=str(self.tenant.id)
        )

        # Publish with tenant ID
        event_id1 = publisher.publish(
            event_type=event_type,
            data=event_data,
            tenant_id=str(self.tenant.id)
        )

        # Publish again with same tenant ID - should be deduplicated
        event_id2 = publisher.publish(
            event_type=event_type,
            data=event_data,
            tenant_id=str(self.tenant.id)
        )
        self.assertEqual(event_id1, event_id2)

    def test_publisher_deduplication_ignores_metadata(self):
        """Test that deduplication ignores metadata fields (request_id, correlation_id, etc.)."""
        event_type = "contract.created"
        event_data = {"contract_id": str(uuid.uuid4())}

        publisher = EventPublisher(
            service_name="test_service",
            tenant_id=str(self.tenant.id)
        )

        # First publish
        event_id1 = publisher.publish(
            event_type=event_type,
            data=event_data,
            request_id="req-1",
            correlation_id="corr-1"
        )

        # Second publish with different metadata but same data - should be deduplicated
        event_id2 = publisher.publish(
            event_type=event_type,
            data=event_data,
            request_id="req-2",  # Different request ID
            correlation_id="corr-2"  # Different correlation ID
        )

        # Should be deduplicated because data is the same
        self.assertEqual(event_id1, event_id2)

    def test_publisher_deduplication_workflow_complete(self):
        """Test complete deduplication workflow."""
        event_type = "contract.created"
        event_data = {"contract_id": str(uuid.uuid4()), "name": "Test Contract"}

        publisher = EventPublisher(
            service_name="test_service",
            tenant_id=str(self.tenant.id)
        )

        # Step 1: Check if duplicate (should not be)
        deduplication_key = generate_deduplication_key(event_type, event_data)
        is_dup, existing_id = check_event_duplicate(
            deduplication_key,
            redis_client=self.redis_client
        )
        self.assertFalse(is_dup)
        self.assertIsNone(existing_id)

        # Step 2: Publish event
        event_id1 = publisher.publish(
            event_type=event_type,
            data=event_data
        )
        self.assertIsNotNone(event_id1)

        # Step 3: Verify event ID is stored
        is_dup, stored_id = check_event_duplicate(
            deduplication_key,
            redis_client=self.redis_client
        )
        self.assertTrue(is_dup)
        self.assertEqual(stored_id, event_id1)

        # Step 4: Try to publish again - should be deduplicated
        event_id2 = publisher.publish(
            event_type=event_type,
            data=event_data
        )
        self.assertEqual(event_id1, event_id2)

    def test_publisher_deduplication_with_nested_data(self):
        """Test deduplication with nested event data."""
        event_type = "contract.created"
        event_data = {
            "contract_id": str(uuid.uuid4()),
            "metadata": {
                "nested": {"deep": "value"},
                "list": [1, 2, 3]
            }
        }

        publisher = EventPublisher(
            service_name="test_service",
            tenant_id=str(self.tenant.id)
        )

        # First publish
        event_id1 = publisher.publish(
            event_type=event_type,
            data=event_data
        )

        # Second publish with same nested data - should be deduplicated
        event_id2 = publisher.publish(
            event_type=event_type,
            data=event_data
        )
        self.assertEqual(event_id1, event_id2)

    def test_publisher_deduplication_ttl_respected(self):
        """Test that deduplication TTL is respected."""
        event_type = "contract.created"
        event_data = {"contract_id": str(uuid.uuid4())}

        publisher = EventPublisher(
            service_name="test_service",
            tenant_id=str(self.tenant.id)
        )

        # Publish event
        event_id1 = publisher.publish(
            event_type=event_type,
            data=event_data
        )

        # Verify TTL is set
        deduplication_key = generate_deduplication_key(event_type, event_data)
        ttl = self.redis_client.ttl(deduplication_key)
        self.assertGreater(ttl, 0)
        self.assertLessEqual(ttl, DEFAULT_DEDUPLICATION_TTL)

