"""
Integration tests for event flow.
"""
import uuid
from unittest.mock import Mock, patch
from django.test import TestCase, override_settings
from django.utils import timezone
from hub.apps.core.events.bus import EventBus
from hub.apps.core.events.models import Event, EventSubscription
from hub.apps.core.events.schema import EventSchema
from hub.apps.core.events.event_types import validate_event_data
from hub.apps.tenants.models import Tenant

uid = uuid.uuid4().hex[:8]


@override_settings(EVENT_BUS_ASYNC_PERSISTENCE=False, EVENT_BUS_WRITE_BEHIND_ENABLED=False)
class EventFlowIntegrationTest(TestCase):
    """Integration tests for event flow."""

    def setUp(self):
        """Set up test data."""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}"
        )
        self.redis_client = Mock()
        self.event_bus = EventBus(redis_client=self.redis_client)
        self.redis_client.publish.return_value = 1

    def test_publish_and_persist_contract_created(self):
        """Test publishing and persisting contract.created event."""
        contract_id = str(uuid.uuid4())
        data = {
            "contract_id": contract_id,
            "status": "ACTIVE"
        }

        # Validate data first
        is_valid, error = validate_event_data("contract.created", data)
        self.assertTrue(is_valid, f"Data validation failed: {error}")

        # Publish event
        event_id = self.event_bus.publish(
            event_type="contract.created",
            data=data,
            tenant_id=str(self.tenant.id)
        )

        self.assertIsNotNone(event_id)

        # Verify event persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "contract.created")
        self.assertEqual(str(event.tenant_id), str(self.tenant.id))
        self.assertEqual(event.data["contract_id"], contract_id)

    def test_publish_and_persist_asset_created(self):
        """Test publishing and persisting asset.created event."""
        asset_id = str(uuid.uuid4())
        data = {
            "asset_id": asset_id,
            "name": "Test Asset",
            "domain": "test"
        }

        # Validate data first
        is_valid, error = validate_event_data("asset.created", data)
        self.assertTrue(is_valid, f"Data validation failed: {error}")

        # Publish event
        event_id = self.event_bus.publish(
            event_type="asset.created",
            data=data,
            tenant_id=str(self.tenant.id)
        )

        self.assertIsNotNone(event_id)

        # Verify event persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "asset.created")
        self.assertEqual(event.data["asset_id"], asset_id)

    def test_publish_and_persist_workflow_started(self):
        """Test publishing and persisting workflow.started event."""
        workflow_instance_id = str(uuid.uuid4())
        data = {
            "workflow_instance_id": workflow_instance_id,
            "workflow_name": "test_workflow",
            "workflow_version": "1.0.0"
        }

        # Validate data first
        is_valid, error = validate_event_data("workflow.started", data)
        self.assertTrue(is_valid, f"Data validation failed: {error}")

        # Publish event
        event_id = self.event_bus.publish(
            event_type="workflow.started",
            data=data,
            tenant_id=str(self.tenant.id)
        )

        self.assertIsNotNone(event_id)

        # Verify event persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "workflow.started")
        self.assertEqual(event.data["workflow_instance_id"], workflow_instance_id)

    @patch('hub.apps.core.utils.test_mode.should_skip_initialization', return_value=False)
    def test_event_subscription_registration(self, mock_skip):
        """Test event subscription registration via EventSubscriber."""
        from hub.apps.core.events.subscriber import EventSubscriber

        handler = Mock()
        subscriber = EventSubscriber("test_subscriber")
        subscriber.subscribe("contract.*", handler)

        # Verify DB record created by EventSubscriber
        subscription = EventSubscription.objects.get(
            subscriber_name="test_subscriber",
            event_type_pattern="contract.*"
        )
        self.assertEqual(subscription.subscriber_name, "test_subscriber")
        self.assertEqual(subscription.event_type_pattern, "contract.*")
        self.assertTrue(subscription.is_active)

    def test_event_replay(self):
        """Test event replay functionality."""
        # Create test events
        event1_data = {
            "contract_id": str(uuid.uuid4()),
            "status": "ACTIVE"
        }
        event2_data = {
            "contract_id": str(uuid.uuid4()),
            "status": "ACTIVE"
        }

        event_id1 = self.event_bus.publish(
            event_type="contract.created",
            data=event1_data,
            tenant_id=str(self.tenant.id)
        )

        event_id2 = self.event_bus.publish(
            event_type="contract.created",
            data=event2_data,
            tenant_id=str(self.tenant.id)
        )

        # Replay events
        events = self.event_bus.replay_events(
            event_type="contract.created",
            tenant_id=str(self.tenant.id)
        )

        self.assertGreaterEqual(len(events), 2)
        event_ids = [e["event_id"] for e in events]
        self.assertIn(event_id1, event_ids)
        self.assertIn(event_id2, event_ids)

    def test_event_validation_failure(self):
        """Test that invalid event data is rejected."""
        # Missing required field
        invalid_data = {}

        is_valid, error = validate_event_data("contract.created", invalid_data)
        self.assertFalse(is_valid)
        self.assertIn("Missing required field", error)

        # Try to publish invalid event
        with self.assertRaises(Exception):
            self.event_bus.publish(
                event_type="contract.created",
                data=invalid_data,
                tenant_id=str(self.tenant.id)
            )

    def test_publish_and_persist_workflow_step_started(self):
        """Test publishing and persisting workflow.step.started event."""
        workflow_instance_id = str(uuid.uuid4())
        data = {
            "workflow_instance_id": workflow_instance_id,
            "step_index": 0,
            "step_name": "process_data",
            "step_type": "task"
        }

        # Validate data first
        is_valid, error = validate_event_data("workflow.step.started", data)
        self.assertTrue(is_valid, f"Data validation failed: {error}")

        # Publish event
        event_id = self.event_bus.publish(
            event_type="workflow.step.started",
            data=data,
            tenant_id=str(self.tenant.id)
        )

        self.assertIsNotNone(event_id)

        # Verify event persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "workflow.step.started")
        self.assertEqual(event.data["workflow_instance_id"], workflow_instance_id)
        self.assertEqual(event.data["step_index"], 0)
        self.assertEqual(event.data["step_name"], "process_data")
        self.assertEqual(event.data["step_type"], "task")

    def test_publish_and_persist_workflow_step_completed(self):
        """Test publishing and persisting workflow.step.completed event."""
        workflow_instance_id = str(uuid.uuid4())
        data = {
            "workflow_instance_id": workflow_instance_id,
            "step_index": 1,
            "step_name": "validate_input",
            "output_data": {"result": "success", "records_processed": 100},
            "duration_ms": 500
        }

        # Validate data first
        is_valid, error = validate_event_data("workflow.step.completed", data)
        self.assertTrue(is_valid, f"Data validation failed: {error}")

        # Publish event
        event_id = self.event_bus.publish(
            event_type="workflow.step.completed",
            data=data,
            tenant_id=str(self.tenant.id)
        )

        self.assertIsNotNone(event_id)

        # Verify event persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "workflow.step.completed")
        self.assertEqual(event.data["workflow_instance_id"], workflow_instance_id)
        self.assertEqual(event.data["step_index"], 1)
        self.assertEqual(event.data["step_name"], "validate_input")
        self.assertEqual(event.data["output_data"]["result"], "success")
        self.assertEqual(event.data["duration_ms"], 500)

    def test_publish_and_persist_workflow_step_failed(self):
        """Test publishing and persisting workflow.step.failed event."""
        workflow_instance_id = str(uuid.uuid4())
        data = {
            "workflow_instance_id": workflow_instance_id,
            "step_index": 2,
            "step_name": "transform_data",
            "error_message": "Transformation failed: invalid format",
            "error_details": {"field": "data", "reason": "invalid format"},
            "retry_count": 1
        }

        # Validate data first
        is_valid, error = validate_event_data("workflow.step.failed", data)
        self.assertTrue(is_valid, f"Data validation failed: {error}")

        # Publish event
        event_id = self.event_bus.publish(
            event_type="workflow.step.failed",
            data=data,
            tenant_id=str(self.tenant.id)
        )

        self.assertIsNotNone(event_id)

        # Verify event persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "workflow.step.failed")
        self.assertEqual(event.data["workflow_instance_id"], workflow_instance_id)
        self.assertEqual(event.data["step_index"], 2)
        self.assertEqual(event.data["step_name"], "transform_data")
        self.assertEqual(event.data["error_message"], "Transformation failed: invalid format")
        self.assertEqual(event.data["error_details"]["field"], "data")
        self.assertEqual(event.data["retry_count"], 1)

    def test_workflow_step_events_sequence(self):
        """Test a sequence of workflow step events (started -> completed)."""
        workflow_instance_id = str(uuid.uuid4())

        # Publish step started event
        started_data = {
            "workflow_instance_id": workflow_instance_id,
            "step_index": 0,
            "step_name": "step_1",
            "step_type": "task"
        }
        started_event_id = self.event_bus.publish(
            event_type="workflow.step.started",
            data=started_data,
            tenant_id=str(self.tenant.id)
        )

        # Publish step completed event
        completed_data = {
            "workflow_instance_id": workflow_instance_id,
            "step_index": 0,
            "step_name": "step_1",
            "output_data": {"status": "success"},
            "duration_ms": 1000
        }
        completed_event_id = self.event_bus.publish(
            event_type="workflow.step.completed",
            data=completed_data,
            tenant_id=str(self.tenant.id)
        )

        # Verify both events persisted
        started_event = Event.objects.get(event_id=started_event_id)
        completed_event = Event.objects.get(event_id=completed_event_id)

        self.assertEqual(started_event.event_type, "workflow.step.started")
        self.assertEqual(completed_event.event_type, "workflow.step.completed")
        self.assertEqual(started_event.data["workflow_instance_id"], workflow_instance_id)
        self.assertEqual(completed_event.data["workflow_instance_id"], workflow_instance_id)
        self.assertEqual(started_event.data["step_index"], completed_event.data["step_index"])

    def test_workflow_step_failed_event_validation(self):
        """Test validation of workflow.step.failed event with missing required fields."""
        # Missing required field: error_message
        invalid_data = {
            "workflow_instance_id": str(uuid.uuid4()),
            "step_index": 0,
            "step_name": "test_step"
        }

        is_valid, error = validate_event_data("workflow.step.failed", invalid_data)
        self.assertFalse(is_valid)
        self.assertIn("Missing required field", error)

    def test_workflow_step_events_with_service_publisher(self):
        """Test workflow step events using WorkflowEventPublisher."""
        from hub.apps.core.events.service_publishers import WorkflowEventPublisher

        tenant_id = str(self.tenant.id)

        class TestWorkflowService(WorkflowEventPublisher):
            def __init__(self):
                self.tenant_id = tenant_id
                self.user_id = None
                super().__init__()

        service = TestWorkflowService()
        workflow_instance_id = str(uuid.uuid4())

        # Publish step started event
        started_event_id = service.publish_workflow_step_started(
            workflow_instance_id=workflow_instance_id,
            step_index=0,
            step_name="test_step",
            step_type="task",
            tenant_id=tenant_id
        )

        # Publish step completed event
        completed_event_id = service.publish_workflow_step_completed(
            workflow_instance_id=workflow_instance_id,
            step_index=0,
            step_name="test_step",
            output_data={"result": "success"},
            duration_ms=500,
            tenant_id=tenant_id
        )

        # Verify events persisted
        started_event = Event.objects.get(event_id=started_event_id)
        completed_event = Event.objects.get(event_id=completed_event_id)

        self.assertEqual(started_event.event_type, "workflow.step.started")
        self.assertEqual(completed_event.event_type, "workflow.step.completed")
        self.assertEqual(str(started_event.tenant_id), tenant_id)
        self.assertEqual(str(completed_event.tenant_id), tenant_id)

