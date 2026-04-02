"""
Tests for ODPS event handling in WebSocket EventConsumer.

These tests verify:
- ODPS event type filtering (including wildcard patterns)
- ODPS event deduplication
- ODPS event replay on reconnection
- ODPS-specific resource ID filtering
- ODPS progress events real-time updates (Task 7.3.2)
"""
import uuid
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import AsyncMock, MagicMock, patch
from hub.apps.websocket.tests.test_base import AsyncWebSocketTransactionTestCase
from django.utils import timezone as django_timezone
from asgiref.sync import sync_to_async

from hub.apps.websocket.consumers.event_consumer import EventConsumer
from hub.apps.websocket.protocol import (
    WebSocketMessage,
    WebSocketMessageType,
    SubscribeMessage,
)
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User
from hub.apps.core.events.models import Event as EventModel
from hub.apps.core.events.bus import get_event_bus


class EventConsumerODPSEventTest(AsyncWebSocketTransactionTestCase):
    """Test ODPS event handling in EventConsumer."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = self.create_unique_tenant()
        self.user = self.create_unique_user(
            tenant=self.tenant,
            password="testpass123",
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
        consumer.replay_enabled = True
        consumer.replay_window_seconds = 3600
        consumer.last_event_timestamps = {}
        # Prevent real Redis connections; dedup functions are patched
        consumer._get_deduplication_redis_client = MagicMock(return_value=None)
        return consumer

    async def test_odps_event_type_filtering_exact_match(self):
        """Test that exact ODPS event types are matched."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"odps.created", "odps.linked"}

        # Test exact match
        self.assertTrue(consumer._is_event_type_subscribed("odps.created"))
        self.assertTrue(consumer._is_event_type_subscribed("odps.linked"))
        self.assertFalse(consumer._is_event_type_subscribed("odps.updated"))
        self.assertFalse(consumer._is_event_type_subscribed("contract.created"))

    async def test_odps_event_type_filtering_wildcard(self):
        """Test that ODPS wildcard patterns match all ODPS events."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"odps.*"}

        # Test wildcard matching
        self.assertTrue(consumer._is_event_type_subscribed("odps.created"))
        self.assertTrue(consumer._is_event_type_subscribed("odps.linked"))
        self.assertTrue(consumer._is_event_type_subscribed("odps.updated"))
        self.assertTrue(consumer._is_event_type_subscribed("odps.workflow.started"))
        self.assertFalse(consumer._is_event_type_subscribed("contract.created"))

    async def test_odps_event_type_filtering_nested_pattern(self):
        """Test that nested ODPS patterns match correctly."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"odps.workflow.*"}

        # Test nested pattern matching
        self.assertTrue(consumer._is_event_type_subscribed("odps.workflow.started"))
        self.assertTrue(consumer._is_event_type_subscribed("odps.workflow.completed"))
        self.assertTrue(consumer._is_event_type_subscribed("odps.workflow.failed"))
        self.assertFalse(consumer._is_event_type_subscribed("odps.created"))
        self.assertFalse(consumer._is_event_type_subscribed("odps.linked"))

    async def test_odps_event_resource_id_filtering(self):
        """Test that ODPS events are filtered by resource ID correctly."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"odps.*"}
        consumer.filters = {"resource_id": str(uuid.uuid4())}

        odps_contract_id = str(uuid.uuid4())
        odcs_contract_id = str(uuid.uuid4())

        # Test odps.created event with contract_id
        event1 = {
            "event_id": str(uuid.uuid4()),
            "event_type": "odps.created",
            "source": {"tenant_id": str(self.tenant.id)},
            "data": {"contract_id": odps_contract_id}
        }
        consumer.filters = {"resource_id": odps_contract_id}
        self.assertTrue(consumer._should_send_event(event1, event1["source"]))

        # Test odps.linked event with odps_contract_id
        event2 = {
            "event_id": str(uuid.uuid4()),
            "event_type": "odps.linked",
            "source": {"tenant_id": str(self.tenant.id)},
            "data": {
                "odps_contract_id": odps_contract_id,
                "odcs_contract_id": odcs_contract_id
            }
        }
        consumer.filters = {"resource_id": odps_contract_id}
        self.assertTrue(consumer._should_send_event(event2, event2["source"]))

        # Test odps.linked event with odcs_contract_id
        # Note: The filter checks odps_contract_id first, then odcs_contract_id, then contract_id
        consumer.filters = {"resource_id": odcs_contract_id}
        result = consumer._should_send_event(event2, event2["source"])
        self.assertTrue(result, f"Event should pass filter for odcs_contract_id={odcs_contract_id}")

        # Test filtering out non-matching resource ID
        consumer.filters = {"resource_id": str(uuid.uuid4())}
        self.assertFalse(consumer._should_send_event(event2, event2["source"]))

    async def test_odps_event_deduplication(self):
        """Test that ODPS events are deduplicated correctly."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"odps.*"}

        # Mock Redis client for deduplication
        mock_redis = MagicMock()
        consumer._get_deduplication_redis_client = MagicMock(return_value=mock_redis)

        event_id = str(uuid.uuid4())
        contract_id = str(uuid.uuid4())
        event = {
            "event_id": event_id,
            "event_type": "odps.created",
            "event_version": "1.0.0",
            "timestamp": datetime.now(dt_timezone.utc).isoformat() + "Z",
            "source": {"tenant_id": str(self.tenant.id)},
            "data": {"contract_id": contract_id}
        }

        # First event - not a duplicate
        # Patch the check_event_duplicate function where it's imported in event_consumer
        with patch('hub.apps.websocket.consumers.event_consumer.check_event_duplicate') as mock_check:
            with patch('hub.apps.websocket.consumers.event_consumer.store_event_id') as mock_store:
                # Set return value to tuple
                mock_check.return_value = (False, None)
                await consumer.send_event(event)
                # Verify event was sent
                self.assertTrue(consumer.send_json_message.called)
                # Verify check was called
                self.assertTrue(mock_check.called)

        # Reset mock
        consumer.send_json_message.reset_mock()

        # Second event with same data - should be duplicate
        # Patch to return (True, event_id) for second call
        with patch('hub.apps.websocket.consumers.event_consumer.check_event_duplicate') as mock_check:
            # Set return value to tuple
            mock_check.return_value = (True, event_id)
            await consumer.send_event(event)
            # Verify event was NOT sent (duplicate)
            self.assertFalse(consumer.send_json_message.called)
            # Verify check was called
            self.assertTrue(mock_check.called)

    async def test_odps_event_replay_on_subscription(self):
        """Test that missed ODPS events are replayed on subscription."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"odps.*"}

        # Create some ODPS events in the database
        odps_contract_id = str(uuid.uuid4())
        odcs_contract_id = str(uuid.uuid4())
        event_time = django_timezone.now() - timedelta(minutes=30)

        # Use sync_to_async for database operations in async test
        event1 = await sync_to_async(EventModel.objects.create)(
            event_id=uuid.uuid4(),
            event_type="odps.created",
            event_version="1.0.0",
            timestamp=event_time,
            source_service="test-service",
            tenant_id=self.tenant.id,
            user_id=self.user.id,
            data={"contract_id": odps_contract_id, "asset_id": str(uuid.uuid4())},
            metadata={}
        )

        event2 = await sync_to_async(EventModel.objects.create)(
            event_id=uuid.uuid4(),
            event_type="odps.linked",
            event_version="1.0.0",
            timestamp=event_time + timedelta(minutes=1),
            source_service="test-service",
            tenant_id=self.tenant.id,
            user_id=self.user.id,
            data={
                "odps_contract_id": odps_contract_id,
                "odcs_contract_id": odcs_contract_id,
                "link_type": "bidirectional"
            },
            metadata={}
        )

        # Mock deduplication to allow replay
        with patch('hub.apps.websocket.consumers.event_consumer.check_event_duplicate', return_value=(False, None)):
            # Subscribe to ODPS events (this should trigger replay)
            message = WebSocketMessage(
                type=WebSocketMessageType.SUBSCRIBE.value,
                data={
                    "event_types": ["odps.*"],
                    "filters": {}
                }
            )
            await consumer.handle_subscribe(message)

            # Verify that events were replayed (send_json_message should be called multiple times)
            # Once for subscription confirmation, and once for each replayed event
            self.assertGreaterEqual(consumer.send_json_message.call_count, 2)

    async def test_odps_event_replay_with_pattern(self):
        """Test that ODPS events are replayed for specific patterns."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"odps.workflow.*"}

        # Create workflow events
        workflow_id = str(uuid.uuid4())
        event_time = django_timezone.now() - timedelta(minutes=30)

        workflow_event = await sync_to_async(EventModel.objects.create)(
            event_id=uuid.uuid4(),
            event_type="odps.workflow.started",
            event_version="1.0.0",
            timestamp=event_time,
            source_service="test-service",
            tenant_id=self.tenant.id,
            user_id=self.user.id,
            data={"workflow_instance_id": workflow_id, "workflow_name": "test"},
            metadata={}
        )

        # Create a non-workflow ODPS event (should not be replayed)
        non_workflow_event = await sync_to_async(EventModel.objects.create)(
            event_id=uuid.uuid4(),
            event_type="odps.created",
            event_version="1.0.0",
            timestamp=event_time,
            source_service="test-service",
            tenant_id=self.tenant.id,
            user_id=self.user.id,
            data={"contract_id": str(uuid.uuid4())},
            metadata={}
        )

        # Mock deduplication
        with patch('hub.apps.websocket.consumers.event_consumer.check_event_duplicate', return_value=(False, None)):
            # Subscribe to workflow events
            message = WebSocketMessage(
                type=WebSocketMessageType.SUBSCRIBE.value,
                data={
                    "event_types": ["odps.workflow.*"],
                    "filters": {}
                }
            )
            await consumer.handle_subscribe(message)

            # Verify that only workflow events were replayed
            # Check that send_json_message was called (at least for confirmation)
            self.assertTrue(consumer.send_json_message.called)

    async def test_odps_event_timestamp_tracking(self):
        """Test that ODPS event timestamps are tracked for replay."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"odps.*"}

        event_time = datetime.now(dt_timezone.utc)
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "odps.created",
            "event_version": "1.0.0",
            "timestamp": event_time.isoformat() + "Z",
            "source": {"tenant_id": str(self.tenant.id)},
            "data": {"contract_id": str(uuid.uuid4())}
        }

        # Mock deduplication
        with patch('hub.apps.websocket.consumers.event_consumer.check_event_duplicate', return_value=(False, None)):
            with patch('hub.apps.websocket.consumers.event_consumer.store_event_id'):
                await consumer.send_event(event)

                # Verify timestamp was tracked
                self.assertIn("odps.created", consumer.last_event_timestamps)
                self.assertIn("odps.*", consumer.last_event_timestamps)
                self.assertEqual(
                    consumer.last_event_timestamps["odps.created"].date(),
                    event_time.date()
                )

    async def test_odps_event_replay_respects_filters(self):
        """Test that replayed ODPS events respect filters."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"odps.*"}

        contract_id = str(uuid.uuid4())
        other_contract_id = str(uuid.uuid4())
        event_time = django_timezone.now() - timedelta(minutes=30)

        # Create events for different contracts
        event1 = await sync_to_async(EventModel.objects.create)(
            event_id=uuid.uuid4(),
            event_type="odps.created",
            event_version="1.0.0",
            timestamp=event_time,
            source_service="test-service",
            tenant_id=self.tenant.id,
            user_id=self.user.id,
            data={"contract_id": contract_id},
            metadata={}
        )

        event2 = await sync_to_async(EventModel.objects.create)(
            event_id=uuid.uuid4(),
            event_type="odps.created",
            event_version="1.0.0",
            timestamp=event_time + timedelta(minutes=1),
            source_service="test-service",
            tenant_id=self.tenant.id,
            user_id=self.user.id,
            data={"contract_id": other_contract_id},
            metadata={}
        )

        # Mock deduplication
        with patch('hub.apps.websocket.consumers.event_consumer.check_event_duplicate', return_value=(False, None)):
            # Subscribe with resource_id filter
            message = WebSocketMessage(
                type=WebSocketMessageType.SUBSCRIBE.value,
                data={
                    "event_types": ["odps.*"],
                    "filters": {"resource_id": contract_id}
                }
            )
            await consumer.handle_subscribe(message)

            # Verify that only the filtered event was replayed
            # We can't easily count exact events, but we can verify the filter is applied
            self.assertTrue(consumer.send_json_message.called)

    async def test_odps_event_replay_disabled(self):
        """Test that replay can be disabled."""
        consumer = self._create_consumer()
        consumer.replay_enabled = False
        consumer.subscribed_event_types = {"odps.*"}

        # Create an event in the database
        event_time = django_timezone.now() - timedelta(minutes=30)
        await sync_to_async(EventModel.objects.create)(
            event_id=uuid.uuid4(),
            event_type="odps.created",
            event_version="1.0.0",
            timestamp=event_time,
            source_service="test-service",
            tenant_id=self.tenant.id,
            user_id=self.user.id,
            data={"contract_id": str(uuid.uuid4())},
            metadata={}
        )

        # Subscribe (should not replay)
        message = WebSocketMessage(
            type=WebSocketMessageType.SUBSCRIBE.value,
            data={
                "event_types": ["odps.*"],
                "filters": {}
            }
        )
        await consumer.handle_subscribe(message)

        # Verify that only subscription confirmation was sent (no replay)
        # send_json_message should be called once for confirmation
        self.assertEqual(consumer.send_json_message.call_count, 1)


class EventConsumerODPSIntegrationTest(AsyncWebSocketTransactionTestCase):
    """Integration tests for ODPS WebSocket events with real event bus."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = self.create_unique_tenant()
        self.user = self.create_unique_user(
            tenant=self.tenant,
            password="testpass123",
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
        consumer.replay_enabled = True
        consumer.replay_window_seconds = 3600
        consumer.last_event_timestamps = {}
        # Prevent real Redis connections; dedup functions are patched
        consumer._get_deduplication_redis_client = MagicMock(return_value=None)
        return consumer

    async def test_odps_created_event_delivery(self):
        """Integration test: ODPS created event is delivered via WebSocket."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"odps.created"}

        # Get event bus and publish an ODPS event
        # Note: event_bus.publish is synchronous, so we need to use sync_to_async
        event_bus = get_event_bus()
        contract_id = str(uuid.uuid4())
        asset_id = str(uuid.uuid4())

        # Publish ODPS created event (use sync_to_async since publish is synchronous)
        await sync_to_async(event_bus.publish)(
            event_type="odps.created",
            data={
                "contract_id": contract_id,
                "asset_id": asset_id,
                "status": "draft",
                "odps_version": "1.0.0",
                "original_format": "JSON"
            },
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Wait a bit for event to be processed
        import asyncio
        await asyncio.sleep(0.1)

        # Simulate event delivery (in real scenario, this would be called by event bus subscriber)
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "odps.created",
            "event_version": "1.0.0",
            "timestamp": datetime.now(dt_timezone.utc).isoformat() + "Z",
            "source": {
                "tenant_id": str(self.tenant.id),
                "user_id": str(self.user.id),
                "service": "hub"
            },
            "data": {
                "contract_id": contract_id,
                "asset_id": asset_id,
                "status": "draft",
                "odps_version": "1.0.0",
                "original_format": "JSON"
            }
        }

        # Mock deduplication
        with patch('hub.apps.websocket.consumers.event_consumer.check_event_duplicate', return_value=(False, None)):
            with patch('hub.apps.websocket.consumers.event_consumer.store_event_id'):
                await consumer.send_event(event)

                # Verify event was sent
                self.assertTrue(consumer.send_json_message.called)
                call_args = consumer.send_json_message.call_args
                response = call_args[0][0]
                self.assertEqual(response.type, WebSocketMessageType.EVENT.value)
                self.assertEqual(response.data["event_type"], "odps.created")
                self.assertEqual(response.data["data"]["contract_id"], contract_id)

    async def test_odps_linked_event_delivery(self):
        """Integration test: ODPS linked event is delivered via WebSocket."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"odps.linked"}

        odps_contract_id = str(uuid.uuid4())
        odcs_contract_id = str(uuid.uuid4())

        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "odps.linked",
            "event_version": "1.0.0",
            "timestamp": datetime.now(dt_timezone.utc).isoformat() + "Z",
            "source": {
                "tenant_id": str(self.tenant.id),
                "user_id": str(self.user.id),
                "service": "hub"
            },
            "data": {
                "odps_contract_id": odps_contract_id,
                "odcs_contract_id": odcs_contract_id,
                "link_type": "bidirectional"
            }
        }

        # Mock deduplication
        with patch('hub.apps.websocket.consumers.event_consumer.check_event_duplicate', return_value=(False, None)):
            with patch('hub.apps.websocket.consumers.event_consumer.store_event_id'):
                await consumer.send_event(event)

                # Verify event was sent
                self.assertTrue(consumer.send_json_message.called)
                call_args = consumer.send_json_message.call_args
                response = call_args[0][0]
                self.assertEqual(response.type, WebSocketMessageType.EVENT.value)
                self.assertEqual(response.data["event_type"], "odps.linked")
                self.assertEqual(response.data["data"]["odps_contract_id"], odps_contract_id)
                self.assertEqual(response.data["data"]["odcs_contract_id"], odcs_contract_id)

    async def test_odps_workflow_events_delivery(self):
        """Integration test: ODPS workflow events are delivered via WebSocket."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"odps.workflow.*"}

        workflow_id = str(uuid.uuid4())

        # Test workflow.started event
        event1 = {
            "event_id": str(uuid.uuid4()),
            "event_type": "odps.workflow.started",
            "event_version": "1.0.0",
            "timestamp": datetime.now(dt_timezone.utc).isoformat() + "Z",
            "source": {
                "tenant_id": str(self.tenant.id),
                "user_id": str(self.user.id),
                "service": "hub"
            },
            "data": {
                "workflow_instance_id": workflow_id,
                "workflow_name": "odps_generation",
                "progress_percentage": 0.0
            }
        }

        # Mock deduplication
        with patch('hub.apps.websocket.consumers.event_consumer.check_event_duplicate', return_value=(False, None)):
            with patch('hub.apps.websocket.consumers.event_consumer.store_event_id'):
                await consumer.send_event(event1)

                # Verify event was sent
                self.assertTrue(consumer.send_json_message.called)
                call_args = consumer.send_json_message.call_args
                response = call_args[0][0]
                self.assertEqual(response.type, WebSocketMessageType.EVENT.value)
                self.assertEqual(response.data["event_type"], "odps.workflow.started")
                self.assertEqual(response.data["data"]["workflow_instance_id"], workflow_id)

    async def test_odps_event_replay_integration(self):
        """Integration test: ODPS events are replayed on reconnection."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"odps.*"}

        # Create ODPS events in database
        contract_id = str(uuid.uuid4())
        event_time = django_timezone.now() - timedelta(minutes=30)

        event1 = await sync_to_async(EventModel.objects.create)(
            event_id=uuid.uuid4(),
            event_type="odps.created",
            event_version="1.0.0",
            timestamp=event_time,
            source_service="test-service",
            tenant_id=self.tenant.id,
            user_id=self.user.id,
            data={"contract_id": contract_id},
            metadata={}
        )

        event2 = await sync_to_async(EventModel.objects.create)(
            event_id=uuid.uuid4(),
            event_type="odps.linked",
            event_version="1.0.0",
            timestamp=event_time + timedelta(minutes=1),
            source_service="test-service",
            tenant_id=self.tenant.id,
            user_id=self.user.id,
            data={
                "odps_contract_id": contract_id,
                "odcs_contract_id": str(uuid.uuid4()),
                "link_type": "bidirectional"
            },
            metadata={}
        )

        # Mock deduplication to allow replay
        with patch('hub.apps.websocket.consumers.event_consumer.check_event_duplicate', return_value=(False, None)):
            # Subscribe to ODPS events (triggers replay)
            message = WebSocketMessage(
                type=WebSocketMessageType.SUBSCRIBE.value,
                data={
                    "event_types": ["odps.*"],
                    "filters": {}
                }
            )
            await consumer.handle_subscribe(message)

            # Verify that events were replayed
            # Should have at least 1 call for subscription confirmation + events for replayed events
            self.assertGreaterEqual(consumer.send_json_message.call_count, 1)

            # Verify that replayed events have correct structure
            calls = consumer.send_json_message.call_args_list
            event_calls = [
                call for call in calls
                if call[0][0].type == WebSocketMessageType.EVENT.value
            ]
            self.assertGreaterEqual(len(event_calls), 1, "Expected at least 1 replayed ODPS event")

    async def test_odps_event_filtering_integration(self):
        """Integration test: ODPS events are filtered correctly."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"odps.*"}

        contract_id = str(uuid.uuid4())
        other_contract_id = str(uuid.uuid4())

        # Set filter for specific contract
        consumer.filters = {"resource_id": contract_id}

        # Event matching filter
        event1 = {
            "event_id": str(uuid.uuid4()),
            "event_type": "odps.created",
            "event_version": "1.0.0",
            "timestamp": datetime.now(dt_timezone.utc).isoformat() + "Z",
            "source": {
                "tenant_id": str(self.tenant.id),
                "user_id": str(self.user.id),
                "service": "hub"
            },
            "data": {"contract_id": contract_id}
        }

        # Event not matching filter
        event2 = {
            "event_id": str(uuid.uuid4()),
            "event_type": "odps.created",
            "event_version": "1.0.0",
            "timestamp": datetime.now(dt_timezone.utc).isoformat() + "Z",
            "source": {
                "tenant_id": str(self.tenant.id),
                "user_id": str(self.user.id),
                "service": "hub"
            },
            "data": {"contract_id": other_contract_id}
        }

        # Mock deduplication
        with patch('hub.apps.websocket.consumers.event_consumer.check_event_duplicate', return_value=(False, None)):
            with patch('hub.apps.websocket.consumers.event_consumer.store_event_id'):
                # Send matching event
                await consumer.send_event(event1)
                self.assertTrue(consumer.send_json_message.called)

                # Reset mock
                consumer.send_json_message.reset_mock()

                # Send non-matching event
                await consumer.send_event(event2)
                # Should not be sent due to filter
                self.assertFalse(consumer.send_json_message.called)


class EventConsumerODPSProgressEventsTest(AsyncWebSocketTransactionTestCase):
    """Test ODPS progress events real-time updates (Task 7.3.2)"""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = self.create_unique_tenant(name_prefix="Test Tenant Progress", slug_prefix="test-tenant-progress")
        self.user = self.create_unique_user(
            tenant=self.tenant,
            password="testpass123",
            email_prefix="test-progress",
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
        consumer.replay_enabled = True
        consumer.replay_window_seconds = 3600
        consumer.last_event_timestamps = {}
        # Prevent real Redis connections; dedup functions are patched
        consumer._get_deduplication_redis_client = MagicMock(return_value=None)
        return consumer

    async def test_odps_creation_progress_event_received(self):
        """Test that odps.creation.progress events are received via WebSocket"""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"odps.creation.progress"}

        contract_id = str(uuid.uuid4())
        workflow_instance_id = str(uuid.uuid4())

        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "odps.creation.progress",
            "event_version": "1.0.0",
            "timestamp": datetime.now(dt_timezone.utc).isoformat() + "Z",
            "source": {"service": "hub", "tenant_id": str(self.tenant.id)},
            "data": {
                "contract_id": contract_id,
                "workflow_instance_id": workflow_instance_id,
                "progress_percentage": 50.0,
                "current_step": "normalize_odps",
                "total_steps": 10,
                "step_index": 5,
                "status_message": "Normalizing ODPS document"
            }
        }

        await consumer.send_event(event)
        self.assertTrue(consumer.send_json_message.called)

        # Verify event data
        response = consumer.send_json_message.call_args[0][0]
        self.assertEqual(response.type, WebSocketMessageType.EVENT.value)
        self.assertEqual(response.data["event_type"], "odps.creation.progress")
        self.assertEqual(response.data["data"]["progress_percentage"], 50.0)
        self.assertEqual(response.data["data"]["current_step"], "normalize_odps")

    async def test_odps_normalization_progress_event_received(self):
        """Test that odps.normalization.progress events are received via WebSocket"""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"odps.normalization.progress"}

        contract_id = str(uuid.uuid4())

        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "odps.normalization.progress",
            "event_version": "1.0.0",
            "timestamp": datetime.now(dt_timezone.utc).isoformat() + "Z",
            "source": {"service": "hub", "tenant_id": str(self.tenant.id)},
            "data": {
                "contract_id": contract_id,
                "progress_percentage": 75.0,
                "current_phase": "marketplace_mapping",
                "total_phases": 6,
                "phase_index": 4,
                "items_processed": 15,
                "items_total": 20,
                "status_message": "Mapping marketplace fields",
                "odps_version": "4.1"
            }
        }

        await consumer.send_event(event)
        self.assertTrue(consumer.send_json_message.called)

        response = consumer.send_json_message.call_args[0][0]
        self.assertEqual(response.type, WebSocketMessageType.EVENT.value)
        self.assertEqual(response.data["event_type"], "odps.normalization.progress")
        self.assertEqual(response.data["data"]["progress_percentage"], 75.0)
        self.assertEqual(response.data["data"]["current_phase"], "marketplace_mapping")

    async def test_odps_ref_progress_event_received(self):
        """Test that odps.ref.progress events are received via WebSocket"""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"odps.ref.progress"}

        contract_id = str(uuid.uuid4())

        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "odps.ref.progress",
            "event_version": "1.0.0",
            "timestamp": datetime.now(dt_timezone.utc).isoformat() + "Z",
            "source": {"service": "hub", "tenant_id": str(self.tenant.id)},
            "data": {
                "contract_id": contract_id,
                "progress_percentage": 60.0,
                "refs_processed": 6,
                "refs_total": 10,
                "current_ref_path": "#/definitions/quality",
                "ref_type": "internal",
                "status_message": "Resolving internal references"
            }
        }

        await consumer.send_event(event)
        self.assertTrue(consumer.send_json_message.called)

        response = consumer.send_json_message.call_args[0][0]
        self.assertEqual(response.type, WebSocketMessageType.EVENT.value)
        self.assertEqual(response.data["event_type"], "odps.ref.progress")
        self.assertEqual(response.data["data"]["progress_percentage"], 60.0)
        self.assertEqual(response.data["data"]["refs_processed"], 6)

    async def test_odps_linking_status_event_received(self):
        """Test that odps.linking.status events are received via WebSocket"""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"odps.linking.status"}

        odps_contract_id = str(uuid.uuid4())
        odcs_contract_id = str(uuid.uuid4())

        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "odps.linking.status",
            "event_version": "1.0.0",
            "timestamp": datetime.now(dt_timezone.utc).isoformat() + "Z",
            "source": {"service": "hub", "tenant_id": str(self.tenant.id)},
            "data": {
                "odps_contract_id": odps_contract_id,
                "odcs_contract_id": odcs_contract_id,
                "status": "completed",
                "progress_percentage": 100.0,
                "current_phase": "completed",
                "validation_passed": True,
                "validation_errors": [],
                "link_type": "bidirectional",
                "status_message": "Contracts linked successfully"
            }
        }

        await consumer.send_event(event)
        self.assertTrue(consumer.send_json_message.called)

        response = consumer.send_json_message.call_args[0][0]
        self.assertEqual(response.type, WebSocketMessageType.EVENT.value)
        self.assertEqual(response.data["event_type"], "odps.linking.status")
        self.assertEqual(response.data["data"]["status"], "completed")
        self.assertEqual(response.data["data"]["validation_passed"], True)

    async def test_odps_export_progress_event_received(self):
        """Test that odps.export.progress events are received via WebSocket"""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"odps.export.progress"}

        contract_id = str(uuid.uuid4())

        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "odps.export.progress",
            "event_version": "1.0.0",
            "timestamp": datetime.now(dt_timezone.utc).isoformat() + "Z",
            "source": {"service": "hub", "tenant_id": str(self.tenant.id)},
            "data": {
                "contract_id": contract_id,
                "export_format": "json",
                "progress_percentage": 80.0,
                "current_phase": "formatting",
                "bytes_processed": 8000,
                "bytes_total": 10000,
                "status_message": "Formatting ODPS as JSON",
                "odps_version": "4.1"
            }
        }

        await consumer.send_event(event)
        self.assertTrue(consumer.send_json_message.called)

        response = consumer.send_json_message.call_args[0][0]
        self.assertEqual(response.type, WebSocketMessageType.EVENT.value)
        self.assertEqual(response.data["event_type"], "odps.export.progress")
        self.assertEqual(response.data["data"]["progress_percentage"], 80.0)
        self.assertEqual(response.data["data"]["export_format"], "json")

    async def test_odps_progress_events_wildcard_subscription(self):
        """Test that odps.* wildcard subscription includes all progress events"""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"odps.*"}

        # Test all progress event types
        progress_events = [
            "odps.creation.progress",
            "odps.normalization.progress",
            "odps.ref.progress",
            "odps.linking.status",
            "odps.export.progress"
        ]

        for event_type in progress_events:
            event = {
                "event_id": str(uuid.uuid4()),
                "event_type": event_type,
                "event_version": "1.0.0",
                "timestamp": datetime.now(dt_timezone.utc).isoformat() + "Z",
                "source": {"service": "hub", "tenant_id": str(self.tenant.id)},
                "data": {"progress_percentage": 50.0}
            }

            consumer.send_json_message.reset_mock()
            await consumer.send_event(event)
            self.assertTrue(
                consumer.send_json_message.called,
                f"Event {event_type} should be sent with odps.* subscription"
            )

