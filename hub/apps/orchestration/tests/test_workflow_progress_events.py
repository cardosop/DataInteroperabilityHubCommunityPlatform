"""
Unit and E2E tests for progress_percentage in workflow step events (Task 0.3.3).

Tests verify that progress_percentage is correctly included in:
- workflow.step.started events
- workflow.step.completed events
- workflow.step.failed events
- WebSocket events for real-time progress updates
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
from unittest.mock import patch, MagicMock

from hub.apps.orchestration.models import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStatus,
    StepStatus,
)
from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

User = get_user_model()


class WorkflowProgressEventsTest(TestCase):
    """Unit tests for progress_percentage in workflow step events (Task 0.3.3)"""

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

    def test_progress_in_step_started_event(self):
        """Test that progress_percentage is included in workflow.step.started events (Task 0.3.3)"""
        # Track published events
        published_events = []

        def capture_event(event_type, data, **kwargs):
            published_events.append({
                "event_type": event_type,
                "data": data,
                **kwargs
            })
            return str(uuid.uuid4())

        # Create workflow with 3 steps
        workflow_def = WorkflowDefinition.objects.create(
            name="test_progress_started",
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
            workflow_name="test_progress_started",
            input_data={},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        instance = self.engine.start_instance(str(instance.id))

        # Patch event publisher to capture events
        with patch.object(self.engine._event_publisher, 'publish', side_effect=capture_event):
            # Execute workflow
            self.engine.execute_instance(str(instance.id))

        # Filter step.started events
        step_started_events = [
            e for e in published_events
            if e["event_type"] == "workflow.step.started"
        ]

        # Verify we have step.started events
        self.assertGreater(len(step_started_events), 0, "Should have at least one step.started event")

        # Verify each step.started event includes progress_percentage
        for event in step_started_events:
            self.assertIn("progress_percentage", event["data"],
                         "step.started event should include progress_percentage")
            progress = event["data"]["progress_percentage"]
            self.assertIsInstance(progress, (int, float),
                                "progress_percentage should be a number")
            self.assertGreaterEqual(progress, 0.0,
                                 "progress_percentage should be >= 0")
            self.assertLessEqual(progress, 100.0,
                               "progress_percentage should be <= 100")

    def test_progress_in_step_completed_event(self):
        """Test that progress_percentage is included in workflow.step.completed events (Task 0.3.3)"""
        # Track published events
        published_events = []

        def capture_event(event_type, data, **kwargs):
            published_events.append({
                "event_type": event_type,
                "data": data,
                **kwargs
            })
            return str(uuid.uuid4())

        # Create workflow with 3 steps
        workflow_def = WorkflowDefinition.objects.create(
            name="test_progress_completed",
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
            workflow_name="test_progress_completed",
            input_data={},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        instance = self.engine.start_instance(str(instance.id))

        # Patch event publisher to capture events
        with patch.object(self.engine._event_publisher, 'publish', side_effect=capture_event):
            # Execute workflow
            self.engine.execute_instance(str(instance.id))

        # Filter step.completed events
        step_completed_events = [
            e for e in published_events
            if e["event_type"] == "workflow.step.completed"
        ]

        # Verify we have step.completed events
        self.assertGreater(len(step_completed_events), 0, "Should have at least one step.completed event")

        # Verify each step.completed event includes progress_percentage
        for event in step_completed_events:
            self.assertIn("progress_percentage", event["data"],
                         "step.completed event should include progress_percentage")
            progress = event["data"]["progress_percentage"]
            self.assertIsInstance(progress, (int, float),
                                "progress_percentage should be a number")
            self.assertGreaterEqual(progress, 0.0,
                                 "progress_percentage should be >= 0")
            self.assertLessEqual(progress, 100.0,
                               "progress_percentage should be <= 100")

    def test_progress_in_step_failed_event(self):
        """Test that progress_percentage is included in workflow.step.failed events (Task 0.3.3)"""
        # Register a failing task
        def failing_task(input_data, instance, step):
            raise ValueError("Task failed intentionally")

        self.engine.register_task("failing_task", failing_task)

        # Track published events
        published_events = []

        def capture_event(event_type, data, **kwargs):
            published_events.append({
                "event_type": event_type,
                "data": data,
                **kwargs
            })
            return str(uuid.uuid4())

        # Create workflow with 3 steps, second step fails
        workflow_def = WorkflowDefinition.objects.create(
            name="test_progress_failed",
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
            workflow_name="test_progress_failed",
            input_data={},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        instance = self.engine.start_instance(str(instance.id))

        # Patch event publisher to capture events
        with patch.object(self.engine._event_publisher, 'publish', side_effect=capture_event):
            # Execute workflow (will fail at step2)
            try:
                self.engine.execute_instance(str(instance.id))
            except Exception:
                # Expected to fail
                pass

        # Filter step.failed events
        step_failed_events = [
            e for e in published_events
            if e["event_type"] == "workflow.step.failed"
        ]

        # Verify we have step.failed events
        self.assertGreater(len(step_failed_events), 0, "Should have at least one step.failed event")

        # Verify each step.failed event includes progress_percentage
        for event in step_failed_events:
            self.assertIn("progress_percentage", event["data"],
                         "step.failed event should include progress_percentage")
            progress = event["data"]["progress_percentage"]
            self.assertIsInstance(progress, (int, float),
                                "progress_percentage should be a number")
            self.assertGreaterEqual(progress, 0.0,
                                 "progress_percentage should be >= 0")
            self.assertLessEqual(progress, 100.0,
                               "progress_percentage should be <= 100")

    def test_progress_values_in_multi_step_workflow(self):
        """Test that progress_percentage values are correct in multi-step workflow events (Task 0.3.3)"""
        # Track published events
        published_events = []

        def capture_event(event_type, data, **kwargs):
            published_events.append({
                "event_type": event_type,
                "data": data,
                **kwargs
            })
            return str(uuid.uuid4())

        # Create workflow with 4 steps
        workflow_def = WorkflowDefinition.objects.create(
            name="test_progress_values",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [
                    {"name": "step1", "type": "task", "task": "test_task"},
                    {"name": "step2", "type": "task", "task": "test_task"},
                    {"name": "step3", "type": "task", "task": "test_task"},
                    {"name": "step4", "type": "task", "task": "test_task"},
                ],
            },
            is_active=True,
        )

        instance = self.engine.create_instance(
            workflow_name="test_progress_values",
            input_data={},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        instance = self.engine.start_instance(str(instance.id))

        # Patch event publisher to capture events
        with patch.object(self.engine._event_publisher, 'publish', side_effect=capture_event):
            # Execute workflow
            self.engine.execute_instance(str(instance.id))

        # Filter step.started events and sort by step_index
        step_started_events = sorted([
            e for e in published_events
            if e["event_type"] == "workflow.step.started"
        ], key=lambda x: x["data"]["step_index"])

        # Verify progress values increase
        # Step 0: (0+1)/4*100 = 25%
        # Step 1: (1+1)/4*100 = 50%
        # Step 2: (2+1)/4*100 = 75%
        # Step 3: (3+1)/4*100 = 100%
        expected_progresses = [25.0, 50.0, 75.0, 100.0]

        self.assertEqual(len(step_started_events), 4, "Should have 4 step.started events")

        for i, event in enumerate(step_started_events):
            progress = event["data"]["progress_percentage"]
            self.assertAlmostEqual(
                progress, expected_progresses[i], places=1,
                msg=f"Step {i} should have progress {expected_progresses[i]}%, got {progress}%"
            )

    def test_progress_in_all_event_types(self):
        """Test that progress_percentage is included in all step event types (Task 0.3.3)"""
        # Track published events
        published_events = []

        def capture_event(event_type, data, **kwargs):
            published_events.append({
                "event_type": event_type,
                "data": data,
                **kwargs
            })
            return str(uuid.uuid4())

        # Create workflow with 2 steps
        workflow_def = WorkflowDefinition.objects.create(
            name="test_progress_all_events",
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
            workflow_name="test_progress_all_events",
            input_data={},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        instance = self.engine.start_instance(str(instance.id))

        # Patch event publisher to capture events
        with patch.object(self.engine._event_publisher, 'publish', side_effect=capture_event):
            # Execute workflow
            self.engine.execute_instance(str(instance.id))

        # Verify all event types include progress_percentage
        step_event_types = [
            "workflow.step.started",
            "workflow.step.completed",
        ]

        for event_type in step_event_types:
            events = [e for e in published_events if e["event_type"] == event_type]
            self.assertGreater(len(events), 0, f"Should have at least one {event_type} event")

            for event in events:
                self.assertIn("progress_percentage", event["data"],
                            f"{event_type} event should include progress_percentage")
                progress = event["data"]["progress_percentage"]
                self.assertIsInstance(progress, (int, float))
                self.assertGreaterEqual(progress, 0.0)
                self.assertLessEqual(progress, 100.0)


class WorkflowProgressWebSocketEventsTest(TestCase):
    """E2E tests for progress_percentage in WebSocket events (Task 0.3.3)"""

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

    def test_websocket_event_format_with_progress(self):
        """E2E test: Verify step events are published in correct format for WebSocket consumption (Task 0.3.3)"""
        # Track published events
        published_events = []

        def capture_event(event_type, data, tenant_id=None, user_id=None, **kwargs):
            event_record = {
                "event_type": event_type,
                "data": data,
                "tenant_id": tenant_id,
                "user_id": user_id,
            }
            published_events.append(event_record)
            return str(uuid.uuid4())

        # Create workflow with 3 steps
        workflow_def = WorkflowDefinition.objects.create(
            name="test_websocket_progress",
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
            workflow_name="test_websocket_progress",
            input_data={},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        instance = self.engine.start_instance(str(instance.id))

        # Patch event publisher to capture events
        with patch.object(self.engine._event_publisher, 'publish', side_effect=capture_event):
            # Execute workflow
            self.engine.execute_instance(str(instance.id))

        # Filter step events
        step_events = [
            e for e in published_events
            if e["event_type"] in ["workflow.step.started", "workflow.step.completed"]
        ]

        # Verify events are in correct format for WebSocket
        for event in step_events:
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
        # Track published events
        published_events = []

        def capture_event(event_type, data, **kwargs):
            published_events.append({
                "event_type": event_type,
                "data": data,
                **kwargs
            })
            return str(uuid.uuid4())

        # Create workflow with 5 steps
        workflow_def = WorkflowDefinition.objects.create(
            name="test_progress_progression",
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
            workflow_name="test_progress_progression",
            input_data={},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        instance = self.engine.start_instance(str(instance.id))

        # Patch event publisher to capture events
        with patch.object(self.engine._event_publisher, 'publish', side_effect=capture_event):
            # Execute workflow
            self.engine.execute_instance(str(instance.id))

        # Filter step.started events and sort by step_index
        step_started_events = sorted([
            e for e in published_events
            if e["event_type"] == "workflow.step.started"
        ], key=lambda x: x["data"]["step_index"])

        # Verify progress increases monotonically
        progresses = [e["data"]["progress_percentage"] for e in step_started_events]

        for i in range(1, len(progresses)):
            self.assertGreaterEqual(
                progresses[i], progresses[i - 1],
                f"Progress should increase: {progresses[i-1]}% -> {progresses[i]}%"
            )

        # Verify final progress is 100%
        self.assertEqual(progresses[-1], 100.0, "Final progress should be 100%")

