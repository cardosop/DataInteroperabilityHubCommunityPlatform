"""
Unit and E2E tests for progress_percentage in workflow step events without mocks (Task 0.3.3).

Tests verify that progress_percentage is correctly included in:
- workflow.step.started events
- workflow.step.completed events
- workflow.step.failed events
- WebSocket events for real-time progress updates

All tests use the actual event system (EventOutbox) without mocks/stubs.
"""
try:
    import pytest
    pytestmark = pytest.mark.django_db(transaction=True)
except ImportError:
    # pytest not available, using Django test runner
    pytest = None
    pytestmark = None

import uuid
import json
from django.test import TestCase
from django.contrib.auth import get_user_model

from hub.apps.orchestration.models import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStatus,
    StepStatus,
)
from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus
from hub.apps.core.events.outbox import EventOutbox

User = get_user_model()


class WorkflowProgressEventsNoMocksTest(TestCase):
    """Unit tests for progress_percentage in workflow step events without mocks (Task 0.3.3)"""

    def setUp(self):
        """Set up test fixtures"""
        self.engine = WorkflowEngine()
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="VERIFIED"
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        # Register a test task
        def test_task(input_data, instance, step):
            return {"result": "success", "step": step.step_name}

        self.engine.register_task("test_task", test_task)

    def _get_step_events_from_outbox(self, workflow_instance_id: str, event_type: str = None):
        """Helper to get step events from EventOutbox without mocks"""
        events = EventOutbox.objects.filter(
            event_type__in=[
                "workflow.step.started",
                "workflow.step.completed",
                "workflow.step.failed"
            ]
        ).order_by('created_at')

        if event_type:
            events = events.filter(event_type=event_type)

        result = []
        for event in events:
            try:
                # EventOutbox uses event_data field, not payload
                event_data = event.event_data if hasattr(event, 'event_data') else json.loads(event.payload) if isinstance(event.payload, str) else event.payload
                if event_data.get("workflow_instance_id") == workflow_instance_id:
                    result.append({
                        "event_type": event.event_type,
                        "data": event_data,
                        "tenant_id": str(event.tenant_id) if event.tenant_id else None,
                        "created_at": event.created_at
                    })
            except (json.JSONDecodeError, AttributeError, TypeError) as e:
                # Skip events that can't be parsed
                continue

        return result

    def test_progress_in_step_started_event(self):
        """Test that progress_percentage is included in workflow.step.started events (Task 0.3.3)"""
        # Create workflow with 3 steps
        workflow_def = WorkflowDefinition.objects.create(
            name="test_progress_started_no_mocks",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [
                    {"name": "step1", "type": "task", "task": "test_task"},
                    {"name": "step2", "type": "task", "task": "test_task"},
                    {"name": "step3", "type": "task", "task": "test_task"},
                ],
            },
            is_active=True,
        )

        instance = self.engine.create_instance(
            workflow_name="test_progress_started_no_mocks",
            input_data={},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        instance = self.engine.start_instance(str(instance.id))

        # Execute workflow
        self.engine.execute_instance(str(instance.id))

        # Get step.started events from outbox
        step_started_events = self._get_step_events_from_outbox(
            str(instance.id),
            event_type="workflow.step.started"
        )

        # Verify events were published
        self.assertGreater(len(step_started_events), 0, "At least one step.started event should be published")

        # Verify each event includes progress_percentage
        for event in step_started_events:
            self.assertIn("progress_percentage", event["data"])
            progress = event["data"]["progress_percentage"]
            self.assertIsInstance(progress, (int, float))
            self.assertGreaterEqual(progress, 0.0)
            self.assertLessEqual(progress, 100.0)

            # Verify other required fields
            self.assertIn("workflow_instance_id", event["data"])
            self.assertIn("step_index", event["data"])
            self.assertIn("step_name", event["data"])

    def test_progress_in_step_completed_event(self):
        """Test that progress_percentage is included in workflow.step.completed events (Task 0.3.3)"""
        # Create workflow with 3 steps
        workflow_def = WorkflowDefinition.objects.create(
            name="test_progress_completed_no_mocks",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [
                    {"name": "step1", "type": "task", "task": "test_task"},
                    {"name": "step2", "type": "task", "task": "test_task"},
                    {"name": "step3", "type": "task", "task": "test_task"},
                ],
            },
            is_active=True,
        )

        instance = self.engine.create_instance(
            workflow_name="test_progress_completed_no_mocks",
            input_data={},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        instance = self.engine.start_instance(str(instance.id))

        # Execute workflow
        self.engine.execute_instance(str(instance.id))

        # Get step.completed events from outbox
        step_completed_events = self._get_step_events_from_outbox(
            str(instance.id),
            event_type="workflow.step.completed"
        )

        # Verify events were published
        self.assertGreater(len(step_completed_events), 0, "At least one step.completed event should be published")

        # Verify each event includes progress_percentage
        for event in step_completed_events:
            self.assertIn("progress_percentage", event["data"])
            progress = event["data"]["progress_percentage"]
            self.assertIsInstance(progress, (int, float))
            self.assertGreaterEqual(progress, 0.0)
            self.assertLessEqual(progress, 100.0)

            # Verify other required fields
            self.assertIn("workflow_instance_id", event["data"])
            self.assertIn("step_index", event["data"])
            self.assertIn("step_name", event["data"])
            self.assertIn("duration_ms", event["data"])

    def test_progress_in_step_failed_event(self):
        """Test that progress_percentage is included in workflow.step.failed events (Task 0.3.3)"""
        # Register a failing task
        def failing_task(input_data, instance, step):
            raise ValueError("Task failed intentionally")

        self.engine.register_task("failing_task", failing_task)

        # Create workflow with 3 steps, second step fails
        workflow_def = WorkflowDefinition.objects.create(
            name="test_progress_failed_no_mocks",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [
                    {"name": "step1", "type": "task", "task": "test_task"},
                    {"name": "step2", "type": "task", "task": "failing_task"},
                    {"name": "step3", "type": "task", "task": "test_task"},
                ],
            },
            is_active=True,
        )

        instance = self.engine.create_instance(
            workflow_name="test_progress_failed_no_mocks",
            input_data={},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        instance = self.engine.start_instance(str(instance.id))

        # Execute workflow (will fail at step2)
        try:
            self.engine.execute_instance(str(instance.id))
        except Exception:
            # Expected to fail
            pass

        # Get step.failed events from outbox
        step_failed_events = self._get_step_events_from_outbox(
            str(instance.id),
            event_type="workflow.step.failed"
        )

        # Verify at least one failed event was published
        self.assertGreater(len(step_failed_events), 0, "At least one step.failed event should be published")

        # Verify each event includes progress_percentage
        for event in step_failed_events:
            self.assertIn("progress_percentage", event["data"])
            progress = event["data"]["progress_percentage"]
            self.assertIsInstance(progress, (int, float))
            self.assertGreaterEqual(progress, 0.0)
            self.assertLessEqual(progress, 100.0)

            # Verify other required fields
            self.assertIn("workflow_instance_id", event["data"])
            self.assertIn("step_index", event["data"])
            self.assertIn("step_name", event["data"])
            self.assertIn("error_message", event["data"])
            self.assertIn("duration_ms", event["data"])

    def test_progress_progression_in_events(self):
        """Test that progress_percentage increases correctly across step events (Task 0.3.3)"""
        # Create workflow with 5 steps
        workflow_def = WorkflowDefinition.objects.create(
            name="test_progress_progression_no_mocks",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [
                    {"name": "step1", "type": "task", "task": "test_task"},
                    {"name": "step2", "type": "task", "task": "test_task"},
                    {"name": "step3", "type": "task", "task": "test_task"},
                    {"name": "step4", "type": "task", "task": "test_task"},
                    {"name": "step5", "type": "task", "task": "test_task"},
                ],
            },
            is_active=True,
        )

        instance = self.engine.create_instance(
            workflow_name="test_progress_progression_no_mocks",
            input_data={},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        instance = self.engine.start_instance(str(instance.id))

        # Execute workflow
        self.engine.execute_instance(str(instance.id))

        # Get all step events from outbox
        all_step_events = self._get_step_events_from_outbox(str(instance.id))

        # Filter step.started events and sort by step_index
        step_started_events = sorted([
            e for e in all_step_events
            if e["event_type"] == "workflow.step.started"
        ], key=lambda x: x["data"]["step_index"])

        # Verify progress increases monotonically
        progresses = [e["data"]["progress_percentage"] for e in step_started_events]

        self.assertGreater(len(progresses), 0, "At least one step.started event should have progress")

        for i in range(1, len(progresses)):
            self.assertGreaterEqual(
                progresses[i], progresses[i - 1],
                f"Progress should increase or stay the same: {progresses[i-1]}% -> {progresses[i]}%"
            )

        # Verify final progress is 100%
        if len(progresses) > 0:
            # Get step.completed events
            step_completed_events = sorted([
                e for e in all_step_events
                if e["event_type"] == "workflow.step.completed"
            ], key=lambda x: x["data"]["step_index"])

            if len(step_completed_events) > 0:
                final_progress = step_completed_events[-1]["data"]["progress_percentage"]
                self.assertEqual(final_progress, 100.0, "Final progress should be 100%")

    def test_progress_in_all_event_types(self):
        """Test that progress_percentage is included in all step event types (Task 0.3.3)"""
        # Create workflow with 2 steps
        workflow_def = WorkflowDefinition.objects.create(
            name="test_progress_all_events_no_mocks",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [
                    {"name": "step1", "type": "task", "task": "test_task"},
                    {"name": "step2", "type": "task", "task": "test_task"},
                ],
            },
            is_active=True,
        )

        instance = self.engine.create_instance(
            workflow_name="test_progress_all_events_no_mocks",
            input_data={},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        instance = self.engine.start_instance(str(instance.id))

        # Execute workflow
        self.engine.execute_instance(str(instance.id))

        # Get all step events from outbox
        all_step_events = self._get_step_events_from_outbox(str(instance.id))

        # Verify we have events
        self.assertGreater(len(all_step_events), 0, "At least one step event should be published")

        # Verify each event type includes progress_percentage
        event_types_found = set()
        for event in all_step_events:
            event_type = event["event_type"]
            event_types_found.add(event_type)

            self.assertIn("progress_percentage", event["data"])
            progress = event["data"]["progress_percentage"]
            self.assertIsInstance(progress, (int, float))
            self.assertGreaterEqual(progress, 0.0)
            self.assertLessEqual(progress, 100.0)

        # Verify we have both started and completed events
        self.assertIn("workflow.step.started", event_types_found)
        self.assertIn("workflow.step.completed", event_types_found)


class WorkflowProgressWebSocketEventsTest(TestCase):
    """E2E tests for progress_percentage in WebSocket events without mocks (Task 0.3.3)"""

    def setUp(self):
        """Set up test fixtures"""
        self.engine = WorkflowEngine()
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="VERIFIED"
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        # Register a test task
        def test_task(input_data, instance, step):
            return {"result": "success", "step": step.step_name}

        self.engine.register_task("test_task", test_task)

    def _get_step_events_from_outbox(self, workflow_instance_id: str):
        """Helper to get step events from EventOutbox"""
        events = EventOutbox.objects.filter(
            event_type__in=[
                "workflow.step.started",
                "workflow.step.completed",
                "workflow.step.failed"
            ]
        ).order_by('created_at')

        result = []
        for event in events:
            try:
                # EventOutbox uses event_data field, not payload
                event_data = event.event_data if hasattr(event, 'event_data') else json.loads(event.payload) if isinstance(event.payload, str) else event.payload
                if event_data.get("workflow_instance_id") == workflow_instance_id:
                    result.append({
                        "event_type": event.event_type,
                        "data": event_data,
                        "tenant_id": str(event.tenant_id) if event.tenant_id else None,
                        "created_at": event.created_at
                    })
            except (json.JSONDecodeError, AttributeError, TypeError):
                continue

        return result

    def test_websocket_event_format(self):
        """E2E test: Verify events are in correct format for WebSocket transmission (Task 0.3.3)"""
        # Create workflow with 3 steps
        workflow_def = WorkflowDefinition.objects.create(
            name="test_websocket_format_no_mocks",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [
                    {"name": "step1", "type": "task", "task": "test_task"},
                    {"name": "step2", "type": "task", "task": "test_task"},
                    {"name": "step3", "type": "task", "task": "test_task"},
                ],
            },
            is_active=True,
        )

        instance = self.engine.create_instance(
            workflow_name="test_websocket_format_no_mocks",
            input_data={},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        instance = self.engine.start_instance(str(instance.id))

        # Execute workflow
        self.engine.execute_instance(str(instance.id))

        # Get step events from outbox
        step_events = self._get_step_events_from_outbox(str(instance.id))

        # Filter step events
        step_events_filtered = [
            e for e in step_events
            if e["event_type"] in ["workflow.step.started", "workflow.step.completed"]
        ]

        # Verify events are in correct format for WebSocket
        for event in step_events_filtered:
            # Verify event structure
            self.assertIn("event_type", event)
            self.assertIn("data", event)

            # Verify data structure
            data = event["data"]
            self.assertIn("workflow_instance_id", data)
            self.assertIn("step_index", data)
            self.assertIn("step_name", data)
            self.assertIn("progress_percentage", data)

            # Verify progress_percentage is valid
            progress = data["progress_percentage"]
            self.assertIsInstance(progress, (int, float))
            self.assertGreaterEqual(progress, 0.0)
            self.assertLessEqual(progress, 100.0)

            # Verify event can be serialized to JSON (for WebSocket)
            try:
                json.dumps(event)
            except TypeError:
                self.fail("Event should be JSON serializable for WebSocket transmission")

    def test_progress_progression_in_websocket_events(self):
        """E2E test: Verify progress_percentage increases correctly in WebSocket events (Task 0.3.3)"""
        # Create workflow with 5 steps
        workflow_def = WorkflowDefinition.objects.create(
            name="test_websocket_progression_no_mocks",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [
                    {"name": "step1", "type": "task", "task": "test_task"},
                    {"name": "step2", "type": "task", "task": "test_task"},
                    {"name": "step3", "type": "task", "task": "test_task"},
                    {"name": "step4", "type": "task", "task": "test_task"},
                    {"name": "step5", "type": "task", "task": "test_task"},
                ],
            },
            is_active=True,
        )

        instance = self.engine.create_instance(
            workflow_name="test_websocket_progression_no_mocks",
            input_data={},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        instance = self.engine.start_instance(str(instance.id))

        # Execute workflow
        self.engine.execute_instance(str(instance.id))

        # Get step events from outbox
        step_events = self._get_step_events_from_outbox(str(instance.id))

        # Filter step.started events and sort by step_index
        step_started_events = sorted([
            e for e in step_events
            if e["event_type"] == "workflow.step.started"
        ], key=lambda x: x["data"]["step_index"])

        # Verify progress increases monotonically
        progresses = [e["data"]["progress_percentage"] for e in step_started_events]

        self.assertGreater(len(progresses), 0, "At least one step.started event should have progress")

        for i in range(1, len(progresses)):
            self.assertGreaterEqual(
                progresses[i], progresses[i - 1],
                f"Progress should increase: {progresses[i-1]}% -> {progresses[i]}%"
            )

        # Verify final progress is 100%
        step_completed_events = sorted([
            e for e in step_events
            if e["event_type"] == "workflow.step.completed"
        ], key=lambda x: x["data"]["step_index"])

        if len(step_completed_events) > 0:
            final_progress = step_completed_events[-1]["data"]["progress_percentage"]
            self.assertEqual(final_progress, 100.0, "Final progress should be 100%")

