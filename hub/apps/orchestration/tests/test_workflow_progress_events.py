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

    pytestmark = pytest.mark.django_db
except ImportError:
    # pytest not available, using Django test runner
    pytest = None
    pytestmark = None

import json
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from hub.apps.core.events.models import Event
from hub.apps.orchestration.models import (
    StepStatus,
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStatus,
)
from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import UserStatus

User = get_user_model()


@override_settings(
    EVENT_BUS_FORCE_SYNC_PERSISTENCE=True,
    EVENT_BUS_ENABLE_PERSISTENCE=True,
    EVENT_BUS_ASYNC_PERSISTENCE=False,
)
class WorkflowProgressEventsTest(TestCase):
    """Unit tests for progress_percentage in workflow step events (Task 0.3.3)"""

    def setUp(self):
        """Set up test fixtures: sync event persistence so Event model sees step events."""
        import hub.apps.core.events.bus as bus_module

        bus_module._event_bus = None

        self.engine = WorkflowEngine()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", status="ACTIVE", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", tenant=self.tenant, status=UserStatus.ACTIVE
        )

        # Register a test task
        def test_task(input_data, instance, step):
            return {"result": "success", "step": step.step_name}

        self.engine.register_task("test_task", test_task)

    def test_progress_in_step_started_event(self):
        """Test that progress_percentage is included in workflow.step.started events (Task 0.3.3)"""
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

        # Count step.started events before execution
        initial_count = Event.objects.filter(
            event_type="workflow.step.started",
            data__workflow_instance_id=str(instance.id),
        ).count()

        # Execute workflow
        self.engine.execute_instance(str(instance.id))

        # Query step.started events from Event model
        step_started_events = Event.objects.filter(
            event_type="workflow.step.started",
            data__workflow_instance_id=str(instance.id),
        ).order_by("timestamp")

        # Verify we have step.started events
        self.assertGreater(
            step_started_events.count(),
            initial_count,
            "Should have at least one step.started event",
        )

        # Verify each step.started event includes progress_percentage
        for event in step_started_events:
            self.assertIn(
                "progress_percentage",
                event.data,
                "step.started event should include progress_percentage",
            )
            progress = event.data["progress_percentage"]
            self.assertIsInstance(progress, (int, float), "progress_percentage should be a number")
            self.assertGreaterEqual(progress, 0.0, "progress_percentage should be >= 0")
            self.assertLessEqual(progress, 100.0, "progress_percentage should be <= 100")
            # Verify tenant and user IDs
            self.assertEqual(event.tenant_id, self.tenant.id)
            self.assertEqual(event.user_id, self.user.id)

    def test_progress_in_step_completed_event(self):
        """Test that progress_percentage is included in workflow.step.completed events (Task 0.3.3)"""
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

        # Count step.completed events before execution
        initial_count = Event.objects.filter(
            event_type="workflow.step.completed",
            data__workflow_instance_id=str(instance.id),
        ).count()

        # Execute workflow
        self.engine.execute_instance(str(instance.id))

        # Query step.completed events from Event model
        step_completed_events = Event.objects.filter(
            event_type="workflow.step.completed",
            data__workflow_instance_id=str(instance.id),
        ).order_by("timestamp")

        # Verify we have step.completed events
        self.assertGreater(
            step_completed_events.count(),
            initial_count,
            "Should have at least one step.completed event",
        )

        # Verify each step.completed event includes progress_percentage
        for event in step_completed_events:
            self.assertIn(
                "progress_percentage",
                event.data,
                "step.completed event should include progress_percentage",
            )
            progress = event.data["progress_percentage"]
            self.assertIsInstance(progress, (int, float), "progress_percentage should be a number")
            self.assertGreaterEqual(progress, 0.0, "progress_percentage should be >= 0")
            self.assertLessEqual(progress, 100.0, "progress_percentage should be <= 100")
            # Verify tenant and user IDs
            self.assertEqual(event.tenant_id, self.tenant.id)
            self.assertEqual(event.user_id, self.user.id)

    def test_progress_in_step_failed_event(self):
        """Test that progress_percentage is included in workflow.step.failed events (Task 0.3.3)"""

        # Register a failing task
        def failing_task(input_data, instance, step):
            raise ValueError("Task failed intentionally")

        self.engine.register_task("failing_task", failing_task)

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

        # Count step.failed events before execution
        initial_count = Event.objects.filter(
            event_type="workflow.step.failed",
            data__workflow_instance_id=str(instance.id),
        ).count()

        # Execute workflow (will fail at step2)
        try:
            self.engine.execute_instance(str(instance.id))
        except Exception:
            # Expected to fail
            pass

        instance.refresh_from_db()

        # Query step.failed events from Event model
        step_failed_events = Event.objects.filter(
            event_type="workflow.step.failed",
            data__workflow_instance_id=str(instance.id),
        ).order_by("timestamp")

        # Verify we have step.failed events if workflow failed
        if instance.status == WorkflowStatus.FAILED:
            self.assertGreater(
                step_failed_events.count(),
                initial_count,
                "Should have at least one step.failed event",
            )

            # Verify each step.failed event includes progress_percentage
            for event in step_failed_events:
                self.assertIn(
                    "progress_percentage",
                    event.data,
                    "step.failed event should include progress_percentage",
                )
                progress = event.data["progress_percentage"]
                self.assertIsInstance(
                    progress, (int, float), "progress_percentage should be a number"
                )
                self.assertGreaterEqual(progress, 0.0, "progress_percentage should be >= 0")
                self.assertLessEqual(progress, 100.0, "progress_percentage should be <= 100")
                # Verify tenant and user IDs
                self.assertEqual(event.tenant_id, self.tenant.id)
                self.assertEqual(event.user_id, self.user.id)

    def test_progress_values_in_multi_step_workflow(self):
        """Test that progress_percentage values are correct in multi-step workflow events (Task 0.3.3)"""
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

        # Execute workflow
        self.engine.execute_instance(str(instance.id))

        # Query step.started events from Event model and sort by step_index
        step_started_events = Event.objects.filter(
            event_type="workflow.step.started",
            data__workflow_instance_id=str(instance.id),
        ).order_by("timestamp")

        # Verify we have step.started events
        self.assertGreaterEqual(
            step_started_events.count(),
            4,
            "Should have at least 4 step.started events",
        )

        # Verify progress values increase monotonically
        progresses = [
            event.data["progress_percentage"]
            for event in step_started_events
            if "progress_percentage" in event.data
        ]

        # Verify progress increases or stays the same
        for i in range(1, len(progresses)):
            self.assertGreaterEqual(
                progresses[i],
                progresses[i - 1],
                f"Progress should not decrease: {progresses[i-1]} -> {progresses[i]}",
            )

        # Final step should be 100%
        if len(progresses) > 0:
            self.assertEqual(progresses[-1], 100.0, "Final step should have 100% progress")

    def test_progress_in_all_event_types(self):
        """Test that progress_percentage is included in all step event types (Task 0.3.3)"""
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

        # Execute workflow
        self.engine.execute_instance(str(instance.id))

        # Verify all event types include progress_percentage by querying Event model
        step_event_types = [
            "workflow.step.started",
            "workflow.step.completed",
        ]

        for event_type in step_event_types:
            events = Event.objects.filter(
                event_type=event_type,
                data__workflow_instance_id=str(instance.id),
            )
            self.assertGreater(
                events.count(),
                0,
                f"Should have at least one {event_type} event",
            )

            for event in events:
                self.assertIn(
                    "progress_percentage",
                    event.data,
                    f"{event_type} event should include progress_percentage",
                )
                progress = event.data["progress_percentage"]
                self.assertIsInstance(progress, (int, float))
                self.assertGreaterEqual(progress, 0.0)
                self.assertLessEqual(progress, 100.0)
                # Verify tenant and user IDs
                self.assertEqual(event.tenant_id, self.tenant.id)
                self.assertEqual(event.user_id, self.user.id)


@override_settings(
    EVENT_BUS_FORCE_SYNC_PERSISTENCE=True,
    EVENT_BUS_ENABLE_PERSISTENCE=True,
    EVENT_BUS_ASYNC_PERSISTENCE=False,
)
class WorkflowProgressWebSocketEventsTest(TestCase):
    """E2E tests for progress_percentage in WebSocket events (Task 0.3.3)"""

    def setUp(self):
        """Set up test fixtures: sync event persistence so Event model sees step events."""
        import hub.apps.core.events.bus as bus_module

        bus_module._event_bus = None

        self.engine = WorkflowEngine()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", status="ACTIVE", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", tenant=self.tenant, status=UserStatus.ACTIVE
        )

        # Register a test task
        def test_task(input_data, instance, step):
            return {"result": "success", "step": step.step_name}

        self.engine.register_task("test_task", test_task)

    def test_websocket_event_format_with_progress(self):
        """E2E test: Verify step events are published in correct format for WebSocket consumption (Task 0.3.3)"""
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

        # Execute workflow
        self.engine.execute_instance(str(instance.id))

        # Query step events from Event model
        step_events = Event.objects.filter(
            event_type__in=["workflow.step.started", "workflow.step.completed"],
            data__workflow_instance_id=str(instance.id),
        ).order_by("timestamp")

        # Verify events are in correct format for WebSocket
        for event in step_events:
            # Verify event structure
            self.assertIsNotNone(event.event_type)
            self.assertIsNotNone(event.data)

            # Verify data structure
            data = event.data
            self.assertIn("workflow_instance_id", data)
            self.assertIn("step_index", data)
            self.assertIn("step_name", data)
            self.assertIn("progress_percentage", data)

            # Verify progress_percentage is valid
            progress = data["progress_percentage"]
            self.assertIsInstance(progress, (int, float))
            self.assertGreaterEqual(progress, 0.0)
            self.assertLessEqual(progress, 100.0)

            # Verify tenant and user IDs
            self.assertEqual(event.tenant_id, self.tenant.id)
            self.assertEqual(event.user_id, self.user.id)

            # Verify event can be serialized to JSON (for WebSocket)
            try:
                json.dumps(
                    {
                        "event_type": event.event_type,
                        "data": data,
                        "tenant_id": str(event.tenant_id) if event.tenant_id else None,
                        "user_id": str(event.user_id) if event.user_id else None,
                    }
                )
            except TypeError:
                self.fail("Event should be JSON serializable for WebSocket transmission")

    def test_progress_progression_in_websocket_events(self):
        """E2E test: Verify progress_percentage increases correctly in WebSocket events (Task 0.3.3)"""
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

        # Execute workflow
        self.engine.execute_instance(str(instance.id))

        # Query step.started events from Event model and sort by step_index
        step_started_events = Event.objects.filter(
            event_type="workflow.step.started",
            data__workflow_instance_id=str(instance.id),
        ).order_by("timestamp")

        # Verify progress increases monotonically
        progresses = [
            event.data["progress_percentage"]
            for event in step_started_events
            if "progress_percentage" in event.data
        ]

        self.assertGreater(len(progresses), 0, "Should have at least one progress value")

        for i in range(1, len(progresses)):
            self.assertGreaterEqual(
                progresses[i],
                progresses[i - 1],
                f"Progress should increase: {progresses[i-1]}% -> {progresses[i]}%",
            )

        # Verify final progress is 100%
        if len(progresses) > 0:
            self.assertEqual(progresses[-1], 100.0, "Final progress should be 100%")
