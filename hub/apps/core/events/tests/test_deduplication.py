"""
Tests for event deduplication utilities.

These tests use real Redis (no mocks) to ensure proper integration.
"""
import json
import hashlib
import uuid
from typing import Dict, Any
from django.test import TestCase, override_settings
from django.conf import settings
import redis
import structlog

# Import using relative import to avoid module path conflicts
from ..deduplication import (
    generate_deduplication_key,
    check_event_duplicate,
    store_event_id,
    is_event_duplicate,
    get_redis_client,
    DEFAULT_DEDUPLICATION_TTL,
)

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


class EventDeduplicationTest(TestCase):
    """Test event deduplication functionality with real Redis."""

    def setUp(self):
        """Set up test fixtures."""
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

    def test_generate_deduplication_key(self):
        """Test deduplication key generation from event."""
        event_type = "contract.created"
        event_data = {"contract_id": str(uuid.uuid4()), "name": "Test Contract"}

        key = generate_deduplication_key(event_type, event_data)

        # Key should start with prefix
        self.assertTrue(key.startswith("event:dedup:"))
        # Key should contain event type
        self.assertIn(event_type, key)
        # Same event should generate same key
        key2 = generate_deduplication_key(event_type, event_data)
        self.assertEqual(key, key2)

    def test_generate_deduplication_key_different_data(self):
        """Test that different event data generates different keys."""
        event_type = "contract.created"
        event_data1 = {"contract_id": str(uuid.uuid4()), "name": "Contract 1"}
        event_data2 = {"contract_id": str(uuid.uuid4()), "name": "Contract 2"}

        key1 = generate_deduplication_key(event_type, event_data1)
        key2 = generate_deduplication_key(event_type, event_data2)

        self.assertNotEqual(key1, key2)

    def test_generate_deduplication_key_different_types(self):
        """Test that different event types generate different keys."""
        event_data = {"contract_id": str(uuid.uuid4())}
        event_type1 = "contract.created"
        event_type2 = "contract.updated"

        key1 = generate_deduplication_key(event_type1, event_data)
        key2 = generate_deduplication_key(event_type2, event_data)

        self.assertNotEqual(key1, key2)

    def test_generate_deduplication_key_deterministic(self):
        """Test that key generation is deterministic (same input = same output)."""
        event_type = "contract.created"
        event_data = {"contract_id": "123", "name": "Test"}

        key1 = generate_deduplication_key(event_type, event_data)
        key2 = generate_deduplication_key(event_type, event_data)
        key3 = generate_deduplication_key(event_type, event_data)

        self.assertEqual(key1, key2)
        self.assertEqual(key2, key3)

    def test_generate_deduplication_key_handles_nested_data(self):
        """Test that nested event data is handled correctly."""
        event_type = "contract.created"
        event_data = {
            "contract_id": str(uuid.uuid4()),
            "metadata": {
                "nested": {"deep": "value"},
                "list": [1, 2, 3]
            }
        }

        key = generate_deduplication_key(event_type, event_data)
        self.assertIsNotNone(key)
        self.assertTrue(key.startswith("event:dedup:"))

    def test_store_event_id(self):
        """Test storing event ID in Redis."""
        event_type = "contract.created"
        event_data = {"contract_id": str(uuid.uuid4())}
        event_id = str(uuid.uuid4())

        key = generate_deduplication_key(event_type, event_data)
        store_event_id(key, event_id, redis_client=self.redis_client)

        # Verify event ID is stored
        stored_id = self.redis_client.get(key)
        self.assertIsNotNone(stored_id)
        self.assertEqual(stored_id, event_id)

    def test_store_event_id_with_ttl(self):
        """Test that stored event ID has TTL set."""
        event_type = "contract.created"
        event_data = {"contract_id": str(uuid.uuid4())}
        event_id = str(uuid.uuid4())
        ttl = 3600  # 1 hour

        key = generate_deduplication_key(event_type, event_data)
        store_event_id(key, event_id, ttl=ttl, redis_client=self.redis_client)

        # Verify TTL is set
        remaining_ttl = self.redis_client.ttl(key)
        self.assertGreater(remaining_ttl, 0)
        self.assertLessEqual(remaining_ttl, ttl)

    def test_check_event_duplicate_new_event(self):
        """Test checking for duplicate when event is new."""
        event_type = "contract.created"
        event_data = {"contract_id": str(uuid.uuid4())}

        key = generate_deduplication_key(event_type, event_data)
        is_duplicate, existing_id = check_event_duplicate(
            key, redis_client=self.redis_client
        )

        self.assertFalse(is_duplicate)
        self.assertIsNone(existing_id)

    def test_check_event_duplicate_existing_event(self):
        """Test checking for duplicate when event already exists."""
        event_type = "contract.created"
        event_data = {"contract_id": str(uuid.uuid4())}
        event_id = str(uuid.uuid4())

        key = generate_deduplication_key(event_type, event_data)
        store_event_id(key, event_id, redis_client=self.redis_client)

        is_duplicate, existing_id = check_event_duplicate(
            key, redis_client=self.redis_client
        )

        self.assertTrue(is_duplicate)
        self.assertEqual(existing_id, event_id)

    def test_is_event_duplicate_new_event(self):
        """Test is_event_duplicate helper for new event."""
        event_type = "contract.created"
        event_data = {"contract_id": str(uuid.uuid4())}

        result = is_event_duplicate(
            event_type, event_data, redis_client=self.redis_client
        )

        self.assertFalse(result)

    def test_is_event_duplicate_existing_event(self):
        """Test is_event_duplicate helper for existing event."""
        event_type = "contract.created"
        event_data = {"contract_id": str(uuid.uuid4())}
        event_id = str(uuid.uuid4())

        # Store event first
        key = generate_deduplication_key(event_type, event_data)
        store_event_id(key, event_id, redis_client=self.redis_client)

        # Check if duplicate
        result = is_event_duplicate(
            event_type, event_data, redis_client=self.redis_client
        )

        self.assertTrue(result)

    def test_deduplication_workflow(self):
        """Test complete deduplication workflow."""
        event_type = "contract.created"
        event_data = {"contract_id": str(uuid.uuid4()), "name": "Test Contract"}
        event_id1 = str(uuid.uuid4())
        event_id2 = str(uuid.uuid4())

        # First event - should not be duplicate
        key = generate_deduplication_key(event_type, event_data)
        is_dup, existing_id = check_event_duplicate(
            key, redis_client=self.redis_client
        )
        self.assertFalse(is_dup)
        self.assertIsNone(existing_id)

        # Store first event
        store_event_id(key, event_id1, redis_client=self.redis_client)

        # Second event with same data - should be duplicate
        is_dup, existing_id = check_event_duplicate(
            key, redis_client=self.redis_client
        )
        self.assertTrue(is_dup)
        self.assertEqual(existing_id, event_id1)

        # store_event_id uses setex which always overwrites (last write wins)
        store_event_id(key, event_id2, redis_client=self.redis_client)
        stored_id = self.redis_client.get(key)
        self.assertEqual(stored_id, event_id2)

    def test_deduplication_ttl_expiration(self):
        """Test that deduplication keys expire after TTL."""
        event_type = "contract.created"
        event_data = {"contract_id": str(uuid.uuid4())}
        event_id = str(uuid.uuid4())
        ttl = 1  # 1 second for testing

        key = generate_deduplication_key(event_type, event_data)
        store_event_id(key, event_id, ttl=ttl, redis_client=self.redis_client)

        # Verify event is stored
        is_dup, _ = check_event_duplicate(key, redis_client=self.redis_client)
        self.assertTrue(is_dup)

        # Wait for TTL to expire
        import time
        time.sleep(ttl + 0.5)  # INTENTIONAL: test-specific timing requirement

        # Verify event is no longer stored
        is_dup, _ = check_event_duplicate(key, redis_client=self.redis_client)
        self.assertFalse(is_dup)

    def test_deduplication_different_event_types(self):
        """Test that deduplication works per event type."""
        event_data = {"contract_id": str(uuid.uuid4())}
        event_id1 = str(uuid.uuid4())
        event_id2 = str(uuid.uuid4())

        # Store created event
        key1 = generate_deduplication_key("contract.created", event_data)
        store_event_id(key1, event_id1, redis_client=self.redis_client)

        # Store updated event (same data, different type)
        key2 = generate_deduplication_key("contract.updated", event_data)
        store_event_id(key2, event_id2, redis_client=self.redis_client)

        # Both should be stored separately
        is_dup1, stored_id1 = check_event_duplicate(
            key1, redis_client=self.redis_client
        )
        is_dup2, stored_id2 = check_event_duplicate(
            key2, redis_client=self.redis_client
        )

        self.assertTrue(is_dup1)
        self.assertTrue(is_dup2)
        self.assertEqual(stored_id1, event_id1)
        self.assertEqual(stored_id2, event_id2)

    def test_get_redis_client(self):
        """Test getting Redis client."""
        client = get_redis_client()
        self.assertIsNotNone(client)
        # Test connection
        client.ping()

    def test_get_redis_client_handles_unavailable(self):
        """Test that get_redis_client returns None when Redis is unavailable."""
        from hub.apps.core import redis_pools
        original_pool = redis_pools._redis_events_pool
        try:
            # Reset the cached pool so it gets recreated with the invalid URL
            redis_pools._redis_events_pool = None
            with override_settings(
                REDIS_EVENTS_URL='redis://invalid-host:6379/0',
                REDIS_URL='redis://invalid-host:6379/0',
            ):
                client = get_redis_client()
                self.assertIsNone(client)
        finally:
            # Restore the original pool so other tests are unaffected
            redis_pools._redis_events_pool = original_pool

    def test_deduplication_key_handles_empty_data(self):
        """Test deduplication key generation with empty data."""
        event_type = "contract.created"
        event_data = {}

        key = generate_deduplication_key(event_type, event_data)
        self.assertIsNotNone(key)
        self.assertTrue(key.startswith("event:dedup:"))

    def test_deduplication_key_handles_none_values(self):
        """Test deduplication key generation with None values."""
        event_type = "contract.created"
        event_data = {"contract_id": None, "name": "Test"}

        key = generate_deduplication_key(event_type, event_data)
        self.assertIsNotNone(key)
        self.assertTrue(key.startswith("event:dedup:"))

    def test_store_event_id_overwrites_existing(self):
        """Test that storing event ID can overwrite existing."""
        event_type = "contract.created"
        event_data = {"contract_id": str(uuid.uuid4())}
        event_id1 = str(uuid.uuid4())
        event_id2 = str(uuid.uuid4())

        key = generate_deduplication_key(event_type, event_data)
        store_event_id(key, event_id1, redis_client=self.redis_client)
        store_event_id(key, event_id2, redis_client=self.redis_client)

        # Should store the latest event ID
        stored_id = self.redis_client.get(key)
        self.assertEqual(stored_id, event_id2)

    def test_deduplication_with_full_event_dict(self):
        """Test deduplication with full event dictionary structure."""
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "contract.created",
            "event_version": "1.0.0",
            "timestamp": "2024-01-01T00:00:00Z",
            "source": {
                "service": "hub",
                "tenant_id": str(uuid.uuid4())
            },
            "data": {
                "contract_id": str(uuid.uuid4()),
                "name": "Test Contract"
            }
        }

        # Extract event_type and data for deduplication
        event_type = event["event_type"]
        event_data = event["data"]

        key = generate_deduplication_key(event_type, event_data)
        is_dup = is_event_duplicate(
            event_type, event_data, redis_client=self.redis_client
        )

        self.assertFalse(is_dup)

        # Store event
        store_event_id(key, event["event_id"], redis_client=self.redis_client)

        # Check again - should be duplicate
        is_dup = is_event_duplicate(
            event_type, event_data, redis_client=self.redis_client
        )
        self.assertTrue(is_dup)

