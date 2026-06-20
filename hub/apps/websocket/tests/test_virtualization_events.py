"""
Tests for Virtualization event handling in WebSocket EventConsumer.

These tests verify:
- Virtualization event type filtering (including wildcard patterns)
- Virtualization event deduplication
- Virtualization event replay on reconnection
- Virtualization-specific resource ID filtering
- Query execution progress events real-time updates
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from asgiref.sync import sync_to_async
from django.utils import timezone as django_timezone

from hub.apps.core.events.models import Event as EventModel
from hub.apps.websocket.consumers.event_consumer import EventConsumer
from hub.apps.websocket.tests.test_base import AsyncWebSocketTransactionTestCase


class EventConsumerVirtualizationEventTest(AsyncWebSocketTransactionTestCase):
    """Test Virtualization event handling in EventConsumer."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = self.create_unique_tenant()
        self.user = self.create_unique_user(
            tenant=self.tenant,
            password="testpass123",
        )

    def _create_consumer(self, user=None, tenant=None):
        """Create EventConsumer instance for testing."""
        return self.create_test_consumer(user=user, tenant=tenant)

    async def test_virtualization_event_type_filtering_exact_match(self):
        """Test that exact virtualization event types are matched."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {
            "virtualization.dataset.created",
            "virtualization.query.execution.started",
        }

        # Test exact match
        self.assertTrue(consumer._is_event_type_subscribed("virtualization.dataset.created"))
        self.assertTrue(
            consumer._is_event_type_subscribed("virtualization.query.execution.started")
        )
        self.assertFalse(consumer._is_event_type_subscribed("virtualization.dataset.updated"))
        self.assertFalse(consumer._is_event_type_subscribed("odps.created"))

    async def test_virtualization_event_type_filtering_wildcard(self):
        """Test that virtualization wildcard patterns match all virtualization events."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"virtualization.*"}

        # Test wildcard matching
        self.assertTrue(consumer._is_event_type_subscribed("virtualization.dataset.created"))
        self.assertTrue(
            consumer._is_event_type_subscribed("virtualization.query.execution.started")
        )
        self.assertTrue(
            consumer._is_event_type_subscribed("virtualization.query.execution.progress")
        )
        self.assertTrue(
            consumer._is_event_type_subscribed("virtualization.query.execution.completed")
        )
        self.assertFalse(consumer._is_event_type_subscribed("odps.created"))

    async def test_virtualization_event_type_filtering_nested_pattern(self):
        """Test that nested virtualization patterns match correctly."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"virtualization.query.*"}

        # Test nested pattern matching
        self.assertTrue(
            consumer._is_event_type_subscribed("virtualization.query.execution.started")
        )
        self.assertTrue(
            consumer._is_event_type_subscribed("virtualization.query.execution.progress")
        )
        self.assertTrue(
            consumer._is_event_type_subscribed("virtualization.query.execution.completed")
        )
        self.assertFalse(consumer._is_event_type_subscribed("virtualization.dataset.created"))

    async def test_virtualization_event_resource_id_filtering(self):
        """Test that virtualization events are filtered by resource ID correctly."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"virtualization.*"}

        virtual_dataset_id = str(uuid.uuid4())
        query_execution_id = str(uuid.uuid4())

        # Test virtualization.dataset.created event with virtual_dataset_id
        event1 = {
            "event_id": str(uuid.uuid4()),
            "event_type": "virtualization.dataset.created",
            "source": {"tenant_id": str(self.tenant.id)},
            "data": {"virtual_dataset_id": virtual_dataset_id},
        }
        consumer.filters = {"virtual_dataset_id": virtual_dataset_id}
        self.assertTrue(consumer._should_send_event(event1, event1["source"]))

        # Test virtualization.query.execution.started event with query_execution_id
        event2 = {
            "event_id": str(uuid.uuid4()),
            "event_type": "virtualization.query.execution.started",
            "source": {"tenant_id": str(self.tenant.id)},
            "data": {
                "query_execution_id": query_execution_id,
                "virtual_dataset_id": virtual_dataset_id,
            },
        }
        consumer.filters = {"query_execution_id": query_execution_id}
        self.assertTrue(consumer._should_send_event(event2, event2["source"]))

        # Test filtering out non-matching resource ID
        consumer.filters = {"query_execution_id": str(uuid.uuid4())}
        self.assertFalse(consumer._should_send_event(event2, event2["source"]))

    async def test_virtualization_event_deduplication(self):
        """Test that virtualization events are deduplicated correctly."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"virtualization.*"}

        # Mock Redis client for deduplication
        mock_redis = MagicMock()
        consumer._get_deduplication_redis_client = MagicMock(return_value=mock_redis)

        event_id = str(uuid.uuid4())
        event = {
            "event_id": event_id,
            "event_type": "virtualization.query.execution.progress",
            "event_version": "1.0.0",
            "timestamp": django_timezone.now().isoformat() + "Z",
            "source": {"tenant_id": str(self.tenant.id)},
            "data": {
                "query_execution_id": str(uuid.uuid4()),
                "virtual_dataset_id": str(uuid.uuid4()),
                "progress_percent": 50.0,
            },
            "metadata": {},
        }

        # Mock deduplication to return False (not duplicate)

        with patch(
            "hub.apps.websocket.consumers.event_consumer.check_event_duplicate"
        ) as mock_check:
            mock_check.return_value = (False, None)
            with patch("hub.apps.websocket.consumers.event_consumer.store_event_id") as mock_store:
                await consumer.send_event(event)
                # Verify event was sent
                consumer.send_json_message.assert_called_once()
                # Verify deduplication was checked
                mock_check.assert_called_once()
                # Verify event ID was stored
                mock_store.assert_called_once()

    async def test_virtualization_event_replay(self):
        """Test that virtualization events are replayed on reconnection."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"virtualization.*"}

        # Create test events in database using sync_to_async
        def _create_events():
            event1 = EventModel.objects.create(
                event_id=uuid.uuid4(),
                event_type="virtualization.dataset.created",
                tenant_id=self.tenant.id,
                source_service="virtualization_service",
                event_version="1.0.0",
                data={"virtual_dataset_id": str(uuid.uuid4()), "name": "Test Dataset"},
                timestamp=django_timezone.now() - timedelta(minutes=30),
            )

            event2 = EventModel.objects.create(
                event_id=uuid.uuid4(),
                event_type="virtualization.query.execution.progress",
                tenant_id=self.tenant.id,
                source_service="virtualization_service",
                event_version="1.0.0",
                data={
                    "query_execution_id": str(uuid.uuid4()),
                    "virtual_dataset_id": str(uuid.uuid4()),
                    "progress_percent": 75.0,
                },
                timestamp=django_timezone.now() - timedelta(minutes=15),
            )
            return event1, event2

        _event1, _event2 = await sync_to_async(_create_events)()

        # Mock Redis client for deduplication
        mock_redis = MagicMock()
        consumer._get_deduplication_redis_client = MagicMock(return_value=mock_redis)

        # Mock deduplication to return False (not duplicate) for replay
        with patch(
            "hub.apps.websocket.consumers.event_consumer.check_event_duplicate"
        ) as mock_check:
            mock_check.return_value = (False, None)
            with patch("hub.apps.websocket.consumers.event_consumer.store_event_id"):
                # Trigger replay
                await consumer._replay_missed_virtualization_events()

                # Verify events were replayed (send_json_message should be called)
                # We expect at least 2 calls (one for each event)
                self.assertGreaterEqual(consumer.send_json_message.call_count, 2)

    async def test_query_execution_progress_event_filtering(self):
        """Test that query execution progress events can be filtered by query_execution_id."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"virtualization.query.execution.progress"}

        query_execution_id = str(uuid.uuid4())
        other_execution_id = str(uuid.uuid4())

        # Create progress event
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "virtualization.query.execution.progress",
            "event_version": "1.0.0",
            "timestamp": django_timezone.now().isoformat() + "Z",
            "source": {"tenant_id": str(self.tenant.id)},
            "data": {
                "query_execution_id": query_execution_id,
                "virtual_dataset_id": str(uuid.uuid4()),
                "progress_percent": 50.0,
            },
            "metadata": {},
        }

        # Test with matching query_execution_id filter
        consumer.filters = {"query_execution_id": query_execution_id}
        self.assertTrue(consumer._should_send_event(event, event["source"]))

        # Test with non-matching query_execution_id filter
        consumer.filters = {"query_execution_id": other_execution_id}
        self.assertFalse(consumer._should_send_event(event, event["source"]))
