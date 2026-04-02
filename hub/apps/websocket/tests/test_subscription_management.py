"""
Tests for WebSocket subscription management.

These tests verify:
- Event subscription/unsubscription
- List active subscriptions
- Event filtering by tenant/resource
- Pattern matching for event types
"""
import uuid
from datetime import datetime, timezone as dt_timezone
from unittest.mock import AsyncMock, MagicMock
from hub.apps.websocket.tests.test_base import AsyncWebSocketTestCase

from hub.apps.websocket.consumers.event_consumer import EventConsumer
from hub.apps.websocket.protocol import (
    WebSocketMessage,
    WebSocketMessageType,
    SubscribeMessage,
)
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User


class WebSocketSubscriptionManagementTest(AsyncWebSocketTestCase):
    """Test WebSocket subscription management functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = self.create_unique_tenant()
        self.tenant2 = self.create_unique_tenant(name_prefix="Test Tenant 2", slug_prefix="test-tenant-2")
        self.user = self.create_unique_user(
            tenant=self.tenant,
            password="testpass123",
        )
        self.user2 = self.create_unique_user(
            tenant=self.tenant2,
            password="testpass123",
            email_prefix="test2",
        )

    def _create_consumer(self, user=None, tenant=None):
        """Create EventConsumer instance for testing."""
        consumer = EventConsumer()
        consumer.scope = {
            "user": user or self.user,
            "tenant": tenant or self.tenant
        }
        consumer.channel_name = "test_channel"
        consumer.channel_layer = None
        consumer.send_json_message = AsyncMock()
        consumer.send = AsyncMock()
        consumer.close = AsyncMock()
        consumer.last_activity = datetime.now(dt_timezone.utc)
        consumer._connection_closed = False
        return consumer

    async def test_subscribe_to_event_types(self):
        """Test subscribing to specific event types."""
        consumer = self._create_consumer()

        message = WebSocketMessage(
            type=WebSocketMessageType.SUBSCRIBE.value,
            data={
                "event_types": ["contract.created", "asset.activated"],
                "filters": {}
            }
        )

        await consumer.handle_subscribe(message)

        # Verify subscriptions
        self.assertIn("contract.created", consumer.subscribed_event_types)
        self.assertIn("asset.activated", consumer.subscribed_event_types)
        self.assertEqual(len(consumer.subscribed_event_types), 2)

        # Verify confirmation was sent
        self.assertTrue(consumer.send_json_message.called)
        call_args = consumer.send_json_message.call_args
        response = call_args[0][0]
        self.assertEqual(response.type, WebSocketMessageType.SUBSCRIPTION_CONFIRMED.value)
        self.assertIn("contract.created", response.data["event_types"])
        self.assertIn("asset.activated", response.data["event_types"])

    async def test_unsubscribe_from_event_types(self):
        """Test unsubscribing from specific event types."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"contract.created", "asset.activated", "contract.updated"}

        message = WebSocketMessage(
            type=WebSocketMessageType.UNSUBSCRIBE.value,
            data={"event_types": ["contract.created"]}
        )

        await consumer.handle_unsubscribe(message)

        # Verify unsubscription
        self.assertNotIn("contract.created", consumer.subscribed_event_types)
        self.assertIn("asset.activated", consumer.subscribed_event_types)
        self.assertIn("contract.updated", consumer.subscribed_event_types)

        # Verify confirmation was sent
        self.assertTrue(consumer.send_json_message.called)

    async def test_unsubscribe_from_all_event_types(self):
        """Test unsubscribing from all event types."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"contract.created", "asset.activated"}

        message = WebSocketMessage(
            type=WebSocketMessageType.UNSUBSCRIBE.value,
            data={}
        )

        await consumer.handle_unsubscribe(message)

        # Verify all subscriptions cleared
        self.assertEqual(len(consumer.subscribed_event_types), 0)

        # Verify confirmation was sent
        self.assertTrue(consumer.send_json_message.called)

    async def test_list_subscriptions(self):
        """Test listing active subscriptions."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"contract.created", "asset.activated"}
        consumer.filters = {"tenant_id": str(self.tenant.id)}

        message = WebSocketMessage(
            type=WebSocketMessageType.LIST_SUBSCRIPTIONS.value,
            request_id="test-request-123"
        )

        await consumer.handle_list_subscriptions(message)

        # Verify response was sent
        self.assertTrue(consumer.send_json_message.called)
        call_args = consumer.send_json_message.call_args
        response = call_args[0][0]

        self.assertEqual(response.type, WebSocketMessageType.SUBSCRIPTIONS_LIST.value)
        self.assertEqual(response.request_id, "test-request-123")
        self.assertIn("event_types", response.data)
        self.assertIn("filters", response.data)
        self.assertIn("count", response.data)
        self.assertEqual(response.data["count"], 2)
        self.assertIn("contract.created", response.data["event_types"])
        self.assertIn("asset.activated", response.data["event_types"])

    async def test_list_subscriptions_empty(self):
        """Test listing subscriptions when none are active."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = set()
        consumer.filters = {}

        message = WebSocketMessage(
            type=WebSocketMessageType.LIST_SUBSCRIPTIONS.value
        )

        await consumer.handle_list_subscriptions(message)

        # Verify response was sent
        self.assertTrue(consumer.send_json_message.called)
        call_args = consumer.send_json_message.call_args
        response = call_args[0][0]

        self.assertEqual(response.data["count"], 0)
        self.assertEqual(len(response.data["event_types"]), 0)

    async def test_event_type_pattern_matching(self):
        """Test event type pattern matching with wildcards."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"contract.*"}

        # Test exact pattern match
        self.assertTrue(consumer._is_event_type_subscribed("contract.created"))
        self.assertTrue(consumer._is_event_type_subscribed("contract.updated"))
        self.assertTrue(consumer._is_event_type_subscribed("contract.deleted"))
        self.assertFalse(consumer._is_event_type_subscribed("asset.created"))

        # Test exact match
        consumer.subscribed_event_types = {"contract.created", "asset.activated"}
        self.assertTrue(consumer._is_event_type_subscribed("contract.created"))
        self.assertTrue(consumer._is_event_type_subscribed("asset.activated"))
        self.assertFalse(consumer._is_event_type_subscribed("contract.updated"))

    async def test_event_filtering_by_tenant_id(self):
        """Test event filtering by tenant ID."""
        consumer = self._create_consumer(user=self.user, tenant=self.tenant)
        consumer.subscribed_event_types = {"contract.created"}
        consumer.filters = {"tenant_id": str(self.tenant.id)}

        # Event from same tenant - should pass
        event1 = {
            "event_id": str(uuid.uuid4()),
            "event_type": "contract.created",
            "source": {"tenant_id": str(self.tenant.id), "user_id": str(self.user.id)},
            "data": {"contract_id": str(uuid.uuid4())}
        }
        # Should pass because tenant matches filter
        result1 = consumer._should_send_event(event1, event1["source"])
        self.assertTrue(result1, "Event from same tenant should pass filter")

        # Event from different tenant - should be filtered out
        event2 = {
            "event_id": str(uuid.uuid4()),
            "event_type": "contract.created",
            "source": {"tenant_id": str(self.tenant2.id), "user_id": str(self.user2.id)},
            "data": {"contract_id": str(uuid.uuid4())}
        }
        # Should be filtered out because tenant doesn't match
        result2 = consumer._should_send_event(event2, event2["source"])
        self.assertFalse(result2, "Event from different tenant should be filtered out")

    async def test_event_filtering_by_resource_type(self):
        """Test event filtering by resource type."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"contract.*"}
        consumer.filters = {"resource_type": "CONTRACT"}

        # Event with matching resource type - should pass
        event1 = {
            "event_id": str(uuid.uuid4()),
            "event_type": "contract.created",
            "source": {"tenant_id": str(self.tenant.id)},
            "data": {"contract_id": str(uuid.uuid4()), "resource_type": "CONTRACT"}
        }
        self.assertTrue(consumer._should_send_event(event1, event1["source"]))

        # Event with different resource type - should be filtered out
        event2 = {
            "event_id": str(uuid.uuid4()),
            "event_type": "contract.created",
            "source": {"tenant_id": str(self.tenant.id)},
            "data": {"contract_id": str(uuid.uuid4()), "resource_type": "ASSET"}
        }
        self.assertFalse(consumer._should_send_event(event2, event2["source"]))

    async def test_event_filtering_by_resource_id(self):
        """Test event filtering by resource ID."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"contract.*"}
        resource_id = str(uuid.uuid4())
        consumer.filters = {"resource_id": resource_id}

        # Event with matching resource ID - should pass
        event1 = {
            "event_id": str(uuid.uuid4()),
            "event_type": "contract.created",
            "source": {"tenant_id": str(self.tenant.id)},
            "data": {"contract_id": resource_id}
        }
        result1 = consumer._should_send_event(event1, event1["source"])
        self.assertTrue(result1, "Event with matching resource_id should pass")

        # Event with different resource ID - should be filtered out
        event2 = {
            "event_id": str(uuid.uuid4()),
            "event_type": "contract.created",
            "source": {"tenant_id": str(self.tenant.id)},
            "data": {"contract_id": str(uuid.uuid4())}
        }
        result2 = consumer._should_send_event(event2, event2["source"])
        self.assertFalse(result2, "Event with different resource_id should be filtered out")

    async def test_event_filtering_by_user_id(self):
        """Test event filtering by user ID."""
        consumer = self._create_consumer(user=self.user, tenant=self.tenant)
        consumer.subscribed_event_types = {"contract.*"}
        consumer.filters = {"user_id": str(self.user.id)}

        # Event from same user - should pass
        event1 = {
            "event_id": str(uuid.uuid4()),
            "event_type": "contract.created",
            "source": {"tenant_id": str(self.tenant.id), "user_id": str(self.user.id)},
            "data": {"contract_id": str(uuid.uuid4())}
        }
        result1 = consumer._should_send_event(event1, event1["source"])
        self.assertTrue(result1, "Event from same user should pass")

        # Event from different user - should be filtered out
        event2 = {
            "event_id": str(uuid.uuid4()),
            "event_type": "contract.created",
            "source": {"tenant_id": str(self.tenant.id), "user_id": str(self.user2.id)},
            "data": {"contract_id": str(uuid.uuid4())}
        }
        result2 = consumer._should_send_event(event2, event2["source"])
        self.assertFalse(result2, "Event from different user should be filtered out")

    async def test_event_filtering_no_filters(self):
        """Test that events pass when no filters are set."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"contract.created"}
        consumer.filters = {}

        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "contract.created",
            "source": {"tenant_id": str(self.tenant.id)},
            "data": {"contract_id": str(uuid.uuid4())}
        }

        # Should pass when no filters
        self.assertTrue(consumer._should_send_event(event, event["source"]))

    async def test_event_filtering_multiple_filters(self):
        """Test event filtering with multiple filters."""
        consumer = self._create_consumer(user=self.user, tenant=self.tenant)
        consumer.subscribed_event_types = {"contract.*"}
        resource_id = str(uuid.uuid4())
        consumer.filters = {
            "tenant_id": str(self.tenant.id),
            "resource_id": resource_id,
            "resource_type": "CONTRACT"
        }

        # Event matching all filters - should pass
        event1 = {
            "event_id": str(uuid.uuid4()),
            "event_type": "contract.created",
            "source": {"tenant_id": str(self.tenant.id), "user_id": str(self.user.id)},
            "data": {"contract_id": resource_id, "resource_type": "CONTRACT"}
        }
        result1 = consumer._should_send_event(event1, event1["source"])
        self.assertTrue(result1, "Event matching all filters should pass")

        # Event not matching resource_id - should be filtered out
        event2 = {
            "event_id": str(uuid.uuid4()),
            "event_type": "contract.created",
            "source": {"tenant_id": str(self.tenant.id), "user_id": str(self.user.id)},
            "data": {"contract_id": str(uuid.uuid4()), "resource_type": "CONTRACT"}
        }
        result2 = consumer._should_send_event(event2, event2["source"])
        self.assertFalse(result2, "Event not matching resource_id should be filtered out")

    async def test_send_event_filters_by_subscription(self):
        """Test that send_event filters events by subscription."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"contract.created"}
        consumer.send_json_message = AsyncMock()
        consumer._get_deduplication_redis_client = MagicMock(return_value=None)  # Disable deduplication for test

        # Event type is subscribed - should be sent
        event1 = {
            "event_id": str(uuid.uuid4()),
            "event_type": "contract.created",
            "event_version": "1.0.0",
            "timestamp": datetime.now(dt_timezone.utc).isoformat(),
            "source": {"tenant_id": str(self.tenant.id), "service": "hub"},
            "data": {"contract_id": str(uuid.uuid4())}
        }

        await consumer.send_event(event1)

        # Verify event was sent
        self.assertTrue(consumer.send_json_message.called)

        # Reset mock
        consumer.send_json_message.reset_mock()

        # Event type is not subscribed - should not be sent
        event2 = {
            "event_id": str(uuid.uuid4()),
            "event_type": "asset.activated",
            "event_version": "1.0.0",
            "timestamp": datetime.now(dt_timezone.utc).isoformat(),
            "source": {"tenant_id": str(self.tenant.id), "service": "hub"},
            "data": {"asset_id": str(uuid.uuid4())}
        }

        await consumer.send_event(event2)

        # Verify event was not sent
        self.assertFalse(consumer.send_json_message.called)

    async def test_send_event_filters_by_tenant(self):
        """Test that send_event filters events by tenant."""
        consumer = self._create_consumer(user=self.user, tenant=self.tenant)
        consumer.subscribed_event_types = {"contract.created"}
        consumer.filters = {"tenant_id": str(self.tenant.id)}
        consumer.send_json_message = AsyncMock()
        consumer._get_deduplication_redis_client = MagicMock(return_value=None)  # Disable deduplication for test

        # Event from same tenant - should be sent
        event1 = {
            "event_id": str(uuid.uuid4()),
            "event_type": "contract.created",
            "event_version": "1.0.0",
            "timestamp": datetime.now(dt_timezone.utc).isoformat(),
            "source": {"tenant_id": str(self.tenant.id), "user_id": str(self.user.id), "service": "hub"},
            "data": {"contract_id": str(uuid.uuid4())}
        }

        await consumer.send_event(event1)

        # Verify event was sent
        self.assertTrue(consumer.send_json_message.called)

        # Reset mock
        consumer.send_json_message.reset_mock()

        # Event from different tenant - should not be sent
        event2 = {
            "event_id": str(uuid.uuid4()),
            "event_type": "contract.created",
            "event_version": "1.0.0",
            "timestamp": datetime.now(dt_timezone.utc).isoformat(),
            "source": {"tenant_id": str(self.tenant2.id), "user_id": str(self.user2.id), "service": "hub"},
            "data": {"contract_id": str(uuid.uuid4())}
        }

        await consumer.send_event(event2)

        # Verify event was not sent
        self.assertFalse(consumer.send_json_message.called)

    async def test_subscribe_with_filters(self):
        """Test subscribing with filters."""
        consumer = self._create_consumer()

        message = WebSocketMessage(
            type=WebSocketMessageType.SUBSCRIBE.value,
            data={
                "event_types": ["contract.created"],
                "filters": {
                    "tenant_id": str(self.tenant.id),
                    "resource_type": "CONTRACT"
                }
            }
        )

        await consumer.handle_subscribe(message)

        # Verify filters were set
        self.assertEqual(consumer.filters["tenant_id"], str(self.tenant.id))
        self.assertEqual(consumer.filters["resource_type"], "CONTRACT")
        self.assertIn("contract.created", consumer.subscribed_event_types)

    async def test_subscribe_updates_existing_subscriptions(self):
        """Test that subscribing updates existing subscriptions."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"contract.created"}

        message = WebSocketMessage(
            type=WebSocketMessageType.SUBSCRIBE.value,
            data={
                "event_types": ["asset.activated"],
                "filters": {}
            }
        )

        await consumer.handle_subscribe(message)

        # Verify both event types are subscribed
        self.assertIn("contract.created", consumer.subscribed_event_types)
        self.assertIn("asset.activated", consumer.subscribed_event_types)
        self.assertEqual(len(consumer.subscribed_event_types), 2)

    async def test_unsubscribe_updates_filters(self):
        """Test that unsubscribing updates filters appropriately."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"contract.created", "asset.activated"}
        consumer.filters = {"tenant_id": str(self.tenant.id)}

        message = WebSocketMessage(
            type=WebSocketMessageType.UNSUBSCRIBE.value,
            data={"event_types": ["contract.created"]}
        )

        await consumer.handle_unsubscribe(message)

        # Verify filters are preserved
        self.assertEqual(consumer.filters["tenant_id"], str(self.tenant.id))
        # Verify remaining subscription
        self.assertIn("asset.activated", consumer.subscribed_event_types)

    async def test_event_type_pattern_matching_edge_cases(self):
        """Test edge cases for event type pattern matching."""
        consumer = self._create_consumer()

        # Test empty subscriptions
        consumer.subscribed_event_types = set()
        self.assertFalse(consumer._is_event_type_subscribed("contract.created"))

        # Test exact match with dot
        consumer.subscribed_event_types = {"contract.created"}
        self.assertTrue(consumer._is_event_type_subscribed("contract.created"))
        self.assertFalse(consumer._is_event_type_subscribed("contractcreated"))

        # Test wildcard at end
        consumer.subscribed_event_types = {"contract.*"}
        self.assertTrue(consumer._is_event_type_subscribed("contract.created"))
        self.assertTrue(consumer._is_event_type_subscribed("contract.updated"))
        self.assertFalse(consumer._is_event_type_subscribed("contracts.created"))

    async def test_filtering_with_missing_event_data(self):
        """Test filtering when event data is missing fields."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"contract.created"}
        consumer.filters = {"resource_type": "CONTRACT"}

        # Event without resource_type in data - should be filtered out (filter requires CONTRACT)
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "contract.created",
            "source": {"tenant_id": str(self.tenant.id)},
            "data": {"contract_id": str(uuid.uuid4())}  # No resource_type
        }

        # Should be filtered out because resource_type doesn't match filter
        result = consumer._should_send_event(event, event["source"])
        self.assertFalse(result, "Event without matching resource_type should be filtered out")

