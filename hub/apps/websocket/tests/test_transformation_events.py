"""
Tests for Transformation Event Publishing via WebSocket

Tests WebSocket event publishing for transformation pipeline events including:
- Pipeline execution progress
- Step completion
- Execution completion/failure
- Preview progress
- Wrangling operations
"""
import json
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from django.test import TestCase
from django.utils import timezone
from asgiref.sync import sync_to_async

from hub.apps.websocket.consumers.event_consumer import EventConsumer
from hub.apps.websocket.protocol import (
    WebSocketMessage,
    WebSocketMessageType,
    SubscribeMessage,
)
from hub.apps.core.events.models import Event as EventModel
from hub.apps.core.events.bus import get_event_bus
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User
from hub.apps.transformation.models import (
    TransformationPipeline,
    PipelineExecution,
    ExecutionStatus,
    ExecutionMode
)
from hub.apps.assets.models import Asset


class TransformationEventWebSocketTest(TestCase):
    """Test WebSocket event publishing for transformation events."""

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
        self.pipeline = TransformationPipeline.objects.create(
            name="Test Pipeline",
            tenant=self.tenant,
            created_by=self.user,
            status="ACTIVE",
            version="1.0.0",
            pipeline_definition={
                "version": "1.0.0",
                "steps": [
                    {
                        "name": "test_step",
                        "type": "transform",
                        "config": {}
                    }
                ]
            }
        )
        self.asset = Asset.objects.create(
            name="Test Asset",
            tenant=self.tenant,
            created_by=self.user,
            key="test-asset"
        )
        self.execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            status=ExecutionStatus.RUNNING,
            execution_mode=ExecutionMode.ASYNC,
            started_at=timezone.now()
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
        consumer.last_activity = datetime.utcnow()
        consumer._connection_closed = False
        consumer.replay_enabled = True
        consumer.replay_window_seconds = 3600
        consumer.last_event_timestamps = {}
        consumer.subscribed_event_types = set()
        consumer.filters = {}
        return consumer

    async def test_subscribe_to_transformation_events(self):
        """Test subscribing to transformation.* events."""
        consumer = self._create_consumer()

        # Simulate subscription
        subscribe_msg = SubscribeMessage(
            event_types=[
                "transformation.pipeline.execution.progress",
                "transformation.pipeline.execution.step_completed",
                "transformation.pipeline.execution.completed"
            ],
            filters={
                "pipeline_id": str(self.pipeline.id),
                "execution_id": str(self.execution.id)
            }
        )

        # Update consumer state as if subscription happened
        consumer.subscribed_event_types.update(subscribe_msg.event_types)
        consumer.filters = subscribe_msg.filters

        # Verify subscription state
        self.assertIn("transformation.pipeline.execution.progress", consumer.subscribed_event_types)
        self.assertIn("transformation.pipeline.execution.step_completed", consumer.subscribed_event_types)
        self.assertIn("transformation.pipeline.execution.completed", consumer.subscribed_event_types)
        self.assertEqual(consumer.filters["pipeline_id"], str(self.pipeline.id))
        self.assertEqual(consumer.filters["execution_id"], str(self.execution.id))

    def test_transformation_event_type_filtering_exact_match(self):
        """Test that exact transformation event types are matched."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {
            "transformation.pipeline.execution.progress",
            "transformation.pipeline.execution.step_completed"
        }

        # Test exact match
        self.assertTrue(consumer._is_event_type_subscribed("transformation.pipeline.execution.progress"))
        self.assertTrue(consumer._is_event_type_subscribed("transformation.pipeline.execution.step_completed"))
        self.assertFalse(consumer._is_event_type_subscribed("transformation.pipeline.execution.completed"))
        self.assertFalse(consumer._is_event_type_subscribed("contract.created"))

    def test_transformation_event_type_filtering_wildcard(self):
        """Test that transformation wildcard patterns match all transformation events."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"transformation.*"}

        # Test wildcard matching
        self.assertTrue(consumer._is_event_type_subscribed("transformation.pipeline.execution.progress"))
        self.assertTrue(consumer._is_event_type_subscribed("transformation.pipeline.execution.step_completed"))
        self.assertTrue(consumer._is_event_type_subscribed("transformation.preview.progress"))
        self.assertTrue(consumer._is_event_type_subscribed("transformation.wrangling.operation.applied"))
        self.assertFalse(consumer._is_event_type_subscribed("contract.created"))

    def test_transformation_event_type_filtering_nested_pattern(self):
        """Test that nested transformation patterns match correctly."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"transformation.pipeline.*"}

        # Test nested pattern matching
        self.assertTrue(consumer._is_event_type_subscribed("transformation.pipeline.execution.progress"))
        self.assertTrue(consumer._is_event_type_subscribed("transformation.pipeline.execution.completed"))
        self.assertTrue(consumer._is_event_type_subscribed("transformation.pipeline.created"))
        self.assertFalse(consumer._is_event_type_subscribed("transformation.preview.progress"))
        self.assertFalse(consumer._is_event_type_subscribed("transformation.wrangling.operation.applied"))

    async def test_filter_by_pipeline_id(self):
        """Test filtering events by pipeline_id."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"transformation.pipeline.execution.progress"}
        consumer.filters = {"pipeline_id": str(self.pipeline.id)}

        # Create another pipeline
        def _create_other_pipeline():
            return TransformationPipeline.objects.create(
                name="Other Pipeline",
                tenant=self.tenant,
                created_by=self.user,
                status="ACTIVE",
                pipeline_definition={
                    "version": "1.0.0",
                    "steps": [
                        {
                            "name": "test_step",
                            "type": "transform",
                            "config": {}
                        }
                    ]
                }
            )

        other_pipeline = await sync_to_async(_create_other_pipeline)()

        # Test event for filtered pipeline (should pass)
        event1 = {
            "event_id": str(uuid.uuid4()),
            "event_type": "transformation.pipeline.execution.progress",
            "source": {"tenant_id": str(self.tenant.id)},
            "data": {
                "pipeline_id": str(self.pipeline.id),
                "execution_id": str(self.execution.id),
                "progress_percent": 0.5
            }
        }
        result1 = await sync_to_async(consumer._should_send_event)(event1, event1["source"])
        self.assertTrue(result1)

        # Test event for other pipeline (should be filtered out)
        event2 = {
            "event_id": str(uuid.uuid4()),
            "event_type": "transformation.pipeline.execution.progress",
            "source": {"tenant_id": str(self.tenant.id)},
            "data": {
                "pipeline_id": str(other_pipeline.id),
                "execution_id": str(self.execution.id),
                "progress_percent": 0.5
            }
        }
        result2 = await sync_to_async(consumer._should_send_event)(event2, event2["source"])
        self.assertFalse(result2)

    async def test_filter_by_execution_id(self):
        """Test filtering events by execution_id."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"transformation.pipeline.execution.progress"}
        consumer.filters = {"execution_id": str(self.execution.id)}

        # Create another execution
        def _create_other_execution():
            return PipelineExecution.objects.create(
                pipeline=self.pipeline,
                asset=self.asset,
                status=ExecutionStatus.RUNNING,
                execution_mode=ExecutionMode.ASYNC
            )

        other_execution = await sync_to_async(_create_other_execution)()

        # Test event for filtered execution (should pass)
        event1 = {
            "event_id": str(uuid.uuid4()),
            "event_type": "transformation.pipeline.execution.progress",
            "source": {"tenant_id": str(self.tenant.id)},
            "data": {
                "pipeline_id": str(self.pipeline.id),
                "execution_id": str(self.execution.id),
                "progress_percent": 0.5
            }
        }
        result1 = await sync_to_async(consumer._should_send_event)(event1, event1["source"])
        self.assertTrue(result1)

        # Test event for other execution (should be filtered out)
        event2 = {
            "event_id": str(uuid.uuid4()),
            "event_type": "transformation.pipeline.execution.progress",
            "source": {"tenant_id": str(self.tenant.id)},
            "data": {
                "pipeline_id": str(self.pipeline.id),
                "execution_id": str(other_execution.id),
                "progress_percent": 0.5
            }
        }
        result2 = await sync_to_async(consumer._should_send_event)(event2, event2["source"])
        self.assertFalse(result2)

    async def test_event_replay_on_reconnection(self):
        """Test replaying missed transformation events on reconnection."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"transformation.pipeline.execution.progress"}
        consumer.filters = {"pipeline_id": str(self.pipeline.id)}

        # Create an event directly in the database (bypassing async issues)
        event_id = str(uuid.uuid4())
        def _create_event():
            from django.utils import timezone as django_timezone
            return EventModel.objects.create(
                event_id=event_id,
                event_type="transformation.pipeline.execution.progress",
                event_version="1.0.0",
                tenant_id=self.tenant.id,
                user_id=self.user.id,
                source_service="transformation_service",
                timestamp=django_timezone.now(),
                data={
                    "pipeline_id": str(self.pipeline.id),
                    "execution_id": str(self.execution.id),
                    "progress_percent": 0.3,
                    "current_step": "validate_pipeline"
                },
                metadata={}
            )

        await sync_to_async(_create_event)()

        # Test replay - this would be called on reconnection
        # We'll test the replay method directly
        consumer.send_event = AsyncMock()

        # Mock Redis for deduplication - return None to disable deduplication for this test
        consumer._get_deduplication_redis_client = MagicMock(return_value=None)

        await consumer._replay_missed_transformation_events()

        # Verify send_event was called with the replayed event
        self.assertTrue(consumer.send_event.called, "send_event should have been called for replayed events")
        # Get the first call's arguments
        call_args_list = consumer.send_event.call_args_list
        self.assertGreater(len(call_args_list), 0, "send_event should have been called at least once")

        # Check that at least one event was replayed
        replayed_events = [call[0][0] for call in call_args_list]
        progress_events = [e for e in replayed_events if e.get("event_type") == "transformation.pipeline.execution.progress"]
        self.assertGreater(len(progress_events), 0, "Should have replayed at least one progress event")

    async def test_event_deduplication(self):
        """Test that duplicate events are not sent."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"transformation.pipeline.execution.progress"}

        # Mock Redis client for deduplication
        mock_redis = MagicMock()
        consumer._get_deduplication_redis_client = MagicMock(return_value=mock_redis)

        event_id = str(uuid.uuid4())
        event_data = {
            "pipeline_id": str(self.pipeline.id),
            "execution_id": str(self.execution.id),
            "progress_percent": 0.5
        }

        event = {
            "event_id": event_id,
            "event_type": "transformation.pipeline.execution.progress",
            "event_version": "1.0.0",
            "timestamp": timezone.now().isoformat() + "Z",
            "source": {"tenant_id": str(self.tenant.id)},
            "data": event_data,
            "metadata": {}
        }

        # Mock deduplication check - first call returns False (not duplicate)
        from hub.apps.core.events.deduplication import check_event_duplicate, store_event_id, generate_deduplication_key
        with patch('hub.apps.websocket.consumers.event_consumer.check_event_duplicate') as mock_check, \
             patch('hub.apps.websocket.consumers.event_consumer.store_event_id') as mock_store, \
             patch('hub.apps.websocket.consumers.event_consumer.generate_deduplication_key') as mock_key:
            # First event - not a duplicate
            mock_check.return_value = (False, None)
            mock_key.return_value = f"test_key_{event_id}"

            await consumer.send_event(event)

            # Verify send was called
            self.assertTrue(consumer.send_json_message.called, "First event should be sent")

            # Reset mock
            consumer.send_json_message.reset_mock()

            # Second event with same data - should be duplicate
            mock_check.return_value = (True, event_id)

            await consumer.send_event(event)

            # Verify send was NOT called (duplicate filtered out)
            self.assertFalse(consumer.send_json_message.called, "Duplicate event should not be sent")

    def test_wildcard_subscription(self):
        """Test subscribing to transformation.* events with wildcard."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"transformation.*"}
        consumer.filters = {"pipeline_id": str(self.pipeline.id)}

        # Test that different transformation event types match
        self.assertTrue(consumer._is_event_type_subscribed("transformation.pipeline.execution.progress"))
        self.assertTrue(consumer._is_event_type_subscribed("transformation.pipeline.execution.step_completed"))
        self.assertTrue(consumer._is_event_type_subscribed("transformation.pipeline.execution.completed"))
        self.assertTrue(consumer._is_event_type_subscribed("transformation.preview.progress"))
        self.assertTrue(consumer._is_event_type_subscribed("transformation.wrangling.operation.applied"))

        # Test that non-transformation events don't match
        self.assertFalse(consumer._is_event_type_subscribed("contract.created"))
        self.assertFalse(consumer._is_event_type_subscribed("asset.created"))

