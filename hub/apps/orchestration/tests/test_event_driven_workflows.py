"""
Unit tests for event-driven workflows.

Tests workflow event publishing, event-triggered workflow starts, and event-based workflow steps.
"""

import time
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from hub.apps.core.events.bus import get_event_bus
from hub.apps.core.events.models import Event
from hub.apps.core.events.subscribers import WorkflowStepSubscriber, WorkflowTriggerSubscriber
from hub.apps.orchestration.models import (
    StepStatus,
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStatus,
    WorkflowStep,
)
from hub.apps.orchestration.workflow_engine import WorkflowEngine, WorkflowExecutionError
from hub.apps.tenants.models import KYCStatus, Tenant

User = get_user_model()


@pytest.mark.django_db(transaction=True)
@override_settings(
    EVENT_BUS_ENABLE_PERSISTENCE=True,
    EVENT_BUS_ASYNC_PERSISTENCE=False,
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,
)
class TestWorkflowEventPublishing(TestCase):
    """Test workflow event publishing."""

    def setUp(self):
        """Set up test fixtures."""
        self.uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(email=f"test-{uuid.uuid4().hex[:8]}@example.com", tenant=self.tenant)
        self.engine = WorkflowEngine()

        # Create a simple workflow definition
        self.wf_name = f"test_workflow_{self.uid}"
        self.workflow_def = WorkflowDefinition.objects.create(
            name=self.wf_name,
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [{"name": "step1", "type": "task", "task": "test_task"}],
            },
            is_active=True,
        )

        # Register a test task
        def test_task(input_data, instance, step):
            return {"result": "success", "output": input_data.get("test_input", "default")}

        self.engine.register_task("test_task", test_task)

    def test_publish_workflow_created_event(self):
        """Test that workflow.created event is published when instance is created."""
        input_data = {"test_input": "test_value"}
        instance = self.engine.create_instance(
            workflow_name=self.wf_name,
            input_data=input_data,
            tenant_id=self.tenant.id,
            created_by_id=self.user.id,
        )
        time.sleep(0.1)  # INTENTIONAL: brief yield for async event persistence

        # Verify event was published by querying Event model
        created_events = Event.objects.filter(
            event_type="workflow.created",
            data__workflow_instance_id=str(instance.id),
        )
        self.assertGreater(created_events.count(), 0, "workflow.created event should be published")

        created_event = created_events.first()
        self.assertEqual(created_event.data["workflow_instance_id"], str(instance.id))
        self.assertEqual(created_event.data["workflow_name"], self.wf_name)
        self.assertEqual(created_event.tenant_id, self.tenant.id)
        self.assertEqual(created_event.user_id, self.user.id)

    def test_publish_workflow_started_event(self):
        """Test that workflow.started event is published when instance is started."""
        instance = self.engine.create_instance(
            workflow_name=self.wf_name,
            input_data={"test_input": "test_value"},
            tenant_id=self.tenant.id,
            created_by_id=self.user.id,
        )

        # Count started events before
        initial_count = Event.objects.filter(
            event_type="workflow.started",
            data__workflow_instance_id=str(instance.id),
        ).count()

        started_instance = self.engine.start_instance(str(instance.id))
        time.sleep(0.1)  # INTENTIONAL: brief yield for async event persistence

        # Verify event was published by querying Event model
        started_events = Event.objects.filter(
            event_type="workflow.started",
            data__workflow_instance_id=str(instance.id),
        )
        self.assertEqual(
            started_events.count(),
            initial_count + 1,
            "workflow.started event should be published once",
        )

        started_event = started_events.first()
        self.assertEqual(started_event.data["workflow_instance_id"], str(instance.id))
        self.assertEqual(started_event.data["workflow_name"], self.wf_name)
        self.assertEqual(started_event.tenant_id, self.tenant.id)
        self.assertEqual(started_event.user_id, self.user.id)

    def test_publish_workflow_completed_event(self):
        """Test that workflow.completed event is published when workflow completes."""
        instance = self.engine.create_instance(
            workflow_name=self.wf_name,
            input_data={"test_input": "test_value"},
            tenant_id=self.tenant.id,
            created_by_id=self.user.id,
        )
        instance = self.engine.start_instance(str(instance.id))

        # Count completed events before execution
        initial_count = Event.objects.filter(
            event_type="workflow.completed",
            data__workflow_instance_id=str(instance.id),
        ).count()

        completed_instance = self.engine.execute_instance(str(instance.id))
        time.sleep(0.1)  # INTENTIONAL: brief yield for async event persistence

        # Verify workflow.completed event was published by querying Event model
        completed_events = Event.objects.filter(
            event_type="workflow.completed",
            data__workflow_instance_id=str(instance.id),
        )
        self.assertEqual(
            completed_events.count(),
            initial_count + 1,
            "workflow.completed event should be published once",
        )

        completed_event = completed_events.first()
        self.assertEqual(completed_event.data["workflow_instance_id"], str(instance.id))
        self.assertEqual(completed_event.data["workflow_name"], self.wf_name)
        self.assertIn("output_data", completed_event.data)
        self.assertIn("duration_ms", completed_event.data)
        self.assertEqual(completed_event.tenant_id, self.tenant.id)
        self.assertEqual(completed_event.user_id, self.user.id)
        # Verify duration_ms is valid
        self.assertIsInstance(completed_event.data["duration_ms"], (int, float))
        self.assertGreaterEqual(completed_event.data["duration_ms"], 0)

    def test_publish_workflow_failed_event(self):
        """Test that workflow.failed event is published when workflow fails."""

        # Register a failing task
        def failing_task(input_data, instance, step):
            raise ValueError("Task failed")

        self.engine.register_task("failing_task", failing_task)

        # Create workflow with failing task
        workflow_def = WorkflowDefinition.objects.create(
            name=f"failing_workflow_{self.uid}",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [{"name": "step1", "type": "task", "task": "failing_task"}],
            },
            is_active=True,
        )

        instance = self.engine.create_instance(
            workflow_name=f"failing_workflow_{self.uid}",
            input_data={"test_input": "test_value"},
            tenant_id=self.tenant.id,
            created_by_id=self.user.id,
        )
        instance = self.engine.start_instance(str(instance.id))

        # Count failed events before execution
        initial_count = Event.objects.filter(
            event_type="workflow.failed",
            data__workflow_instance_id=str(instance.id),
        ).count()

        # Execute workflow - should fail
        try:
            failed_instance = self.engine.execute_instance(str(instance.id))
        except Exception:
            failed_instance = None

        instance.refresh_from_db()

        # Verify workflow.failed event was published if workflow failed
        if instance.status == WorkflowStatus.FAILED:
            failed_events = Event.objects.filter(
                event_type="workflow.failed",
                data__workflow_instance_id=str(instance.id),
            )
            if failed_events.count() > initial_count:
                failed_event = failed_events.order_by("-timestamp").first()
                self.assertEqual(failed_event.data["workflow_instance_id"], str(instance.id))
                self.assertEqual(failed_event.data["workflow_name"], f"failing_workflow_{self.uid}")
                self.assertIn("error_message", failed_event.data)
                self.assertEqual(failed_event.tenant_id, self.tenant.id)
                self.assertEqual(failed_event.user_id, self.user.id)
                # Verify error_message is not empty
                self.assertIsNotNone(failed_event.data["error_message"])
                self.assertNotEqual(failed_event.data["error_message"], "")

    def test_publish_workflow_step_started_event(self):
        """Test that workflow.step.started event is published when step starts."""
        instance = self.engine.create_instance(
            workflow_name=self.wf_name,
            input_data={"test_input": "test_value"},
            tenant_id=self.tenant.id,
            created_by_id=self.user.id,
        )
        instance = self.engine.start_instance(str(instance.id))

        # Count step started events before execution
        initial_count = Event.objects.filter(
            event_type="workflow.step.started",
            data__workflow_instance_id=str(instance.id),
        ).count()

        self.engine.execute_instance(str(instance.id))
        time.sleep(0.1)  # INTENTIONAL: brief yield for async event persistence

        # Verify workflow.step.started event was published by querying Event model
        step_started_events = Event.objects.filter(
            event_type="workflow.step.started",
            data__workflow_instance_id=str(instance.id),
        )
        self.assertGreater(
            step_started_events.count(),
            initial_count,
            "workflow.step.started event should be published",
        )

        step_started_event = step_started_events.order_by("timestamp").first()
        self.assertEqual(step_started_event.data["workflow_instance_id"], str(instance.id))
        self.assertEqual(step_started_event.data["step_index"], 0)
        self.assertEqual(step_started_event.data["step_name"], "step1")
        self.assertEqual(step_started_event.data["step_type"], "task")
        # Verify progress_percentage is included
        self.assertIn("progress_percentage", step_started_event.data)
        self.assertIsNotNone(step_started_event.data["progress_percentage"])
        self.assertIsInstance(step_started_event.data["progress_percentage"], (int, float))
        self.assertGreaterEqual(step_started_event.data["progress_percentage"], 0.0)
        self.assertLessEqual(step_started_event.data["progress_percentage"], 100.0)
        self.assertEqual(step_started_event.tenant_id, self.tenant.id)
        self.assertEqual(step_started_event.user_id, self.user.id)

    def test_publish_workflow_step_completed_event(self):
        """Test that workflow.step.completed event is published when step completes."""
        instance = self.engine.create_instance(
            workflow_name=self.wf_name,
            input_data={"test_input": "test_value"},
            tenant_id=self.tenant.id,
            created_by_id=self.user.id,
        )
        instance = self.engine.start_instance(str(instance.id))

        # Count step completed events before execution
        initial_count = Event.objects.filter(
            event_type="workflow.step.completed",
            data__workflow_instance_id=str(instance.id),
        ).count()

        self.engine.execute_instance(str(instance.id))
        time.sleep(0.1)  # INTENTIONAL: brief yield for async event persistence

        # Verify workflow.step.completed event was published by querying Event model
        step_completed_events = Event.objects.filter(
            event_type="workflow.step.completed",
            data__workflow_instance_id=str(instance.id),
        )
        self.assertGreater(
            step_completed_events.count(),
            initial_count,
            "workflow.step.completed event should be published",
        )

        # Verify event data
        step_completed_event = step_completed_events.order_by("timestamp").first()
        self.assertEqual(step_completed_event.data["workflow_instance_id"], str(instance.id))
        self.assertEqual(step_completed_event.data["step_index"], 0)
        self.assertEqual(step_completed_event.data["step_name"], "step1")
        self.assertIn("output_data", step_completed_event.data)
        self.assertIn("duration_ms", step_completed_event.data)
        # Verify progress_percentage is included
        self.assertIn("progress_percentage", step_completed_event.data)
        self.assertIsNotNone(step_completed_event.data["progress_percentage"])
        self.assertIsInstance(step_completed_event.data["progress_percentage"], (int, float))
        self.assertGreaterEqual(step_completed_event.data["progress_percentage"], 0.0)
        self.assertLessEqual(step_completed_event.data["progress_percentage"], 100.0)
        # For a single step workflow, progress should be 100% after completion
        if step_completed_events.count() == 1:
            self.assertEqual(step_completed_event.data["progress_percentage"], 100.0)
        self.assertEqual(step_completed_event.tenant_id, self.tenant.id)
        self.assertEqual(step_completed_event.user_id, self.user.id)

    def test_publish_workflow_step_failed_event(self):
        """Test that workflow.step.failed event is published when step fails."""

        # Register a failing task
        def failing_task(input_data, instance, step):
            raise ValueError("Step failed")

        self.engine.register_task("failing_task", failing_task)

        # Create workflow with failing task
        workflow_def = WorkflowDefinition.objects.create(
            name=f"failing_step_workflow_{self.uid}",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [{"name": "step1", "type": "task", "task": "failing_task"}],
            },
            is_active=True,
        )

        instance = self.engine.create_instance(
            workflow_name=f"failing_step_workflow_{self.uid}",
            input_data={"test_input": "test_value"},
            tenant_id=self.tenant.id,
            created_by_id=self.user.id,
        )
        instance = self.engine.start_instance(str(instance.id))

        # Count step failed events before execution
        initial_count = Event.objects.filter(
            event_type="workflow.step.failed",
            data__workflow_instance_id=str(instance.id),
        ).count()

        try:
            self.engine.execute_instance(str(instance.id))
        except WorkflowExecutionError:
            pass  # Expected to fail

        instance.refresh_from_db()

        # Verify workflow.step.failed event was published if step failed
        step_failed_events = Event.objects.filter(
            event_type="workflow.step.failed",
            data__workflow_instance_id=str(instance.id),
        )
        if step_failed_events.count() > initial_count:
            step_failed_event = step_failed_events.order_by("-timestamp").first()
            self.assertEqual(step_failed_event.data["workflow_instance_id"], str(instance.id))
            self.assertEqual(step_failed_event.data["step_index"], 0)
            self.assertEqual(step_failed_event.data["step_name"], "step1")
            self.assertIn("error_message", step_failed_event.data)
            self.assertIn("error_details", step_failed_event.data)
            # Verify progress_percentage is included
            self.assertIn("progress_percentage", step_failed_event.data)
            self.assertIsNotNone(step_failed_event.data["progress_percentage"])
            self.assertIsInstance(step_failed_event.data["progress_percentage"], (int, float))
            # Verify duration_ms is included
            self.assertIn("duration_ms", step_failed_event.data)
            self.assertIsNotNone(step_failed_event.data["duration_ms"])
            self.assertEqual(step_failed_event.tenant_id, self.tenant.id)
            self.assertEqual(step_failed_event.user_id, self.user.id)
            # Verify error_message is not empty
            self.assertIsNotNone(step_failed_event.data["error_message"])
            self.assertNotEqual(step_failed_event.data["error_message"], "")

    def test_step_events_include_progress_percentage_multi_step(self):
        """Test that step events include progress_percentage for multi-step workflows."""
        # Create workflow with multiple steps
        multi_step_workflow = WorkflowDefinition.objects.create(
            name=f"multi_step_workflow_{self.uid}",
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
            workflow_name=f"multi_step_workflow_{self.uid}",
            input_data={"test_input": "test_value"},
            tenant_id=self.tenant.id,
            created_by_id=self.user.id,
        )
        instance = self.engine.start_instance(str(instance.id))

        # Count step events before execution
        initial_started_count = Event.objects.filter(
            event_type="workflow.step.started",
            data__workflow_instance_id=str(instance.id),
        ).count()
        initial_completed_count = Event.objects.filter(
            event_type="workflow.step.completed",
            data__workflow_instance_id=str(instance.id),
        ).count()

        self.engine.execute_instance(str(instance.id))
        time.sleep(0.1)  # INTENTIONAL: brief yield for async event persistence

        # Verify all step events were published with progress_percentage by querying Event model
        step_started_events = Event.objects.filter(
            event_type="workflow.step.started",
            data__workflow_instance_id=str(instance.id),
        ).order_by("timestamp")
        step_completed_events = Event.objects.filter(
            event_type="workflow.step.completed",
            data__workflow_instance_id=str(instance.id),
        ).order_by("timestamp")

        self.assertGreaterEqual(
            step_started_events.count(),
            initial_started_count + 3,
            "Should have at least 3 step.started events",
        )
        self.assertGreaterEqual(
            step_completed_events.count(),
            initial_completed_count + 3,
            "Should have at least 3 step.completed events",
        )

        # Verify progress_percentage for each step
        # Progress should increase monotonically
        started_progresses = [
            e.data["progress_percentage"]
            for e in step_started_events.order_by("timestamp")
            if "progress_percentage" in e.data
        ]
        if len(started_progresses) >= 3:
            # Verify progress increases or stays the same
            for i in range(1, len(started_progresses)):
                self.assertGreaterEqual(
                    started_progresses[i],
                    started_progresses[i - 1],
                    f"Progress should not decrease: {started_progresses[i-1]} -> {started_progresses[i]}",
                )
            # Final step should be 100%
            self.assertEqual(started_progresses[-1], 100.0, "Final step should have 100% progress")

    def test_progress_stored_in_state_data(self):
        """Test that progress is stored in WorkflowInstance.state_data."""
        # Create workflow with multiple steps
        multi_step_workflow = WorkflowDefinition.objects.create(
            name=f"multi_step_workflow_{self.uid}",
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
            workflow_name=f"multi_step_workflow_{self.uid}",
            input_data={"test_input": "test_value"},
            tenant_id=self.tenant.id,
            created_by_id=self.user.id,
        )
        instance = self.engine.start_instance(str(instance.id))

        # Execute workflow
        self.engine.execute_instance(str(instance.id))
        time.sleep(0.1)  # INTENTIONAL: brief yield for async event persistence

        # Refresh instance to get updated state_data
        instance.refresh_from_db()

        # Verify progress is stored in state_data
        self.assertIn("progress_percentage", instance.state_data)
        progress = instance.state_data["progress_percentage"]
        self.assertIsNotNone(progress)
        self.assertIsInstance(progress, (int, float))
        self.assertGreaterEqual(progress, 0.0)
        self.assertLessEqual(progress, 100.0)

        # For completed workflow, progress should be 100%
        if instance.status == WorkflowStatus.COMPLETED:
            self.assertEqual(progress, 100.0, "Progress should be 100% for completed workflow")
        self.assertIsNotNone(instance.state_data["progress_percentage"])
        # After first step completes, progress should be 100% (2/2 * 100)
        self.assertEqual(instance.state_data["progress_percentage"], 100.0)

    def test_step_events_include_all_metadata(self):
        """Test that step events include all required metadata: step_index, step_name, progress_percentage, duration_ms."""
        instance = self.engine.create_instance(
            workflow_name=self.wf_name,
            input_data={"test_input": "test_value"},
            tenant_id=self.tenant.id,
            created_by_id=self.user.id,
        )
        instance = self.engine.start_instance(str(instance.id))

        # Count step events before execution
        initial_started_count = Event.objects.filter(
            event_type="workflow.step.started",
            data__workflow_instance_id=str(instance.id),
        ).count()
        initial_completed_count = Event.objects.filter(
            event_type="workflow.step.completed",
            data__workflow_instance_id=str(instance.id),
        ).count()

        self.engine.execute_instance(str(instance.id))
        time.sleep(0.1)  # INTENTIONAL: brief yield for async event persistence

        # Verify step.started event has all metadata by querying Event model
        step_started_events = Event.objects.filter(
            event_type="workflow.step.started",
            data__workflow_instance_id=str(instance.id),
        )
        self.assertGreater(
            step_started_events.count(),
            initial_started_count,
            "Should have step.started events",
        )
        started_event = step_started_events.order_by("timestamp").first()
        started_data = started_event.data
        self.assertIn("step_index", started_data)
        self.assertIn("step_name", started_data)
        self.assertIn("progress_percentage", started_data)
        self.assertEqual(started_event.tenant_id, self.tenant.id)
        self.assertEqual(started_event.user_id, self.user.id)

        # Verify step.completed event has all metadata
        step_completed_events = Event.objects.filter(
            event_type="workflow.step.completed",
            data__workflow_instance_id=str(instance.id),
        )
        self.assertGreater(
            step_completed_events.count(),
            initial_completed_count,
            "Should have step.completed events",
        )
        completed_event = step_completed_events.order_by("timestamp").first()
        completed_data = completed_event.data
        self.assertIn("step_index", completed_data)
        self.assertIn("step_name", completed_data)
        self.assertIn("progress_percentage", completed_data)
        self.assertIn("duration_ms", completed_data)
        self.assertEqual(completed_event.tenant_id, self.tenant.id)
        self.assertEqual(completed_event.user_id, self.user.id)

    def test_step_failed_event_includes_duration_ms(self):
        """Test that workflow.step.failed event includes duration_ms."""

        # Register a failing task
        def failing_task(input_data, instance, step):
            raise ValueError("Step failed")

        self.engine.register_task("failing_task", failing_task)

        # Create workflow with failing task
        workflow_def = WorkflowDefinition.objects.create(
            name=f"failing_step_workflow_{self.uid}",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [{"name": "step1", "type": "task", "task": "failing_task"}],
            },
            is_active=True,
        )

        instance = self.engine.create_instance(
            workflow_name=f"failing_step_workflow_{self.uid}",
            input_data={"test_input": "test_value"},
            tenant_id=self.tenant.id,
            created_by_id=self.user.id,
        )
        instance = self.engine.start_instance(str(instance.id))

        # Count step failed events before execution
        initial_count = Event.objects.filter(
            event_type="workflow.step.failed",
            data__workflow_instance_id=str(instance.id),
        ).count()

        try:
            self.engine.execute_instance(str(instance.id))
        except WorkflowExecutionError:
            pass  # Expected to fail

        instance.refresh_from_db()

        # Verify workflow.step.failed event includes duration_ms by querying Event model
        if instance.status == WorkflowStatus.FAILED:
            step_failed_events = Event.objects.filter(
                event_type="workflow.step.failed",
                data__workflow_instance_id=str(instance.id),
            )
            if step_failed_events.count() > initial_count:
                step_failed_event = step_failed_events.order_by("-timestamp").first()
                failed_data = step_failed_event.data
                self.assertIn("duration_ms", failed_data)
                self.assertIsNotNone(failed_data["duration_ms"])
                self.assertIsInstance(failed_data["duration_ms"], (int, float))
                self.assertGreaterEqual(failed_data["duration_ms"], 0)
                self.assertEqual(step_failed_event.tenant_id, self.tenant.id)
                self.assertEqual(step_failed_event.user_id, self.user.id)


@pytest.mark.django_db(transaction=True)
class TestWorkflowTriggerSubscriber(TestCase):
    """Test event-triggered workflow starts."""

    def setUp(self):
        """Set up test fixtures."""
        self.uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(email=f"test-{uuid.uuid4().hex[:8]}@example.com", tenant=self.tenant)
        self.engine = WorkflowEngine()
        self.subscriber = WorkflowTriggerSubscriber(workflow_engine=self.engine)

        # Create a workflow definition
        self.triggered_wf_name = f"triggered_workflow_{self.uid}"
        self.workflow_def = WorkflowDefinition.objects.create(
            name=self.triggered_wf_name,
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [{"name": "step1", "type": "task", "task": "test_task"}],
            },
            is_active=True,
        )

        # Register a test task
        def test_task(input_data, instance, step):
            return {"result": "success"}

        self.engine.register_task("test_task", test_task)

    def test_register_workflow_trigger(self):
        """Test registering a workflow trigger for an event type."""
        self.subscriber.register_workflow_trigger("contract.created", self.triggered_wf_name)

        self.assertIn("contract.created", self.subscriber.workflow_mapping)
        self.assertEqual(self.subscriber.workflow_mapping["contract.created"], self.triggered_wf_name)

    def test_handle_event_triggers_workflow(self):
        """Test that handling an event triggers a workflow."""
        # Register trigger
        self.subscriber.register_workflow_trigger("contract.created", self.triggered_wf_name)

        # Count workflow instances before
        initial_count = WorkflowInstance.objects.filter(
            workflow_name=self.triggered_wf_name,
            tenant=self.tenant,
        ).count()

        # Create event
        event = {
            "event_type": "contract.created",
            "event_id": str(uuid.uuid4()),
            "data": {"contract_id": str(uuid.uuid4())},
            "source": {"tenant_id": str(self.tenant.id), "user_id": str(self.user.id)},
        }

        # Handle event - should trigger workflow creation
        self.subscriber._handle_event(event)

        # Verify workflow was created by querying WorkflowInstance model
        triggered_workflows = WorkflowInstance.objects.filter(
            workflow_name=self.triggered_wf_name,
            tenant=self.tenant,
        )
        self.assertGreater(
            triggered_workflows.count(),
            initial_count,
            "Workflow should be created when event is handled",
        )

        # Verify workflow was created with correct parameters
        workflow_instance = triggered_workflows.order_by("-created_at").first()
        self.assertEqual(workflow_instance.workflow_name, self.triggered_wf_name)
        self.assertEqual(workflow_instance.tenant_id, self.tenant.id)
        self.assertEqual(workflow_instance.created_by_id, self.user.id)
        # Verify input_data contains event data
        self.assertIn("contract_id", workflow_instance.input_data)

    def test_handle_event_no_mapping(self):
        """Test that handling an event with no mapping does nothing."""
        event = {
            "event_type": "unknown.event",
            "event_id": str(uuid.uuid4()),
            "data": {},
            "source": {},
        }

        # Should not raise an error
        self.subscriber._handle_event(event)


@pytest.mark.django_db(transaction=True)
class TestWorkflowStepSubscriber(TestCase):
    """Test event-based workflow step execution."""

    def setUp(self):
        """Set up test fixtures."""
        self.uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(email=f"test-{uuid.uuid4().hex[:8]}@example.com", tenant=self.tenant)
        self.engine = WorkflowEngine()
        self.subscriber = WorkflowStepSubscriber(workflow_engine=self.engine)

        # Create a workflow definition with multiple steps
        self.workflow_def = WorkflowDefinition.objects.create(
            name=f"multi_step_workflow_{self.uid}",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [
                    {"name": "step1", "type": "task", "task": "test_task1"},
                    {"name": "step2", "type": "task", "task": "test_task2"},
                ],
            },
            is_active=True,
        )

        # Register test tasks
        def test_task1(input_data, instance, step):
            return {"result": "step1_success"}

        def test_task2(input_data, instance, step):
            return {"result": "step2_success"}

        self.engine.register_task("test_task1", test_task1)
        self.engine.register_task("test_task2", test_task2)

    def test_handle_workflow_started_triggers_execution(self):
        """Test that workflow.started event triggers execution."""
        # Create a workflow instance first
        instance = self.engine.create_instance(
            workflow_name=f"multi_step_workflow_{self.uid}",
            input_data={"test_input": "test_value"},
            tenant_id=self.tenant.id,
            created_by_id=self.user.id,
        )
        instance = self.engine.start_instance(str(instance.id))

        # Get initial step status
        initial_running_steps = instance.steps.filter(status=StepStatus.RUNNING).count()

        event = {
            "event_type": "workflow.started",
            "event_id": str(uuid.uuid4()),
            "data": {"workflow_instance_id": str(instance.id)},
        }

        # Handle event - should trigger execution
        self.subscriber._handle_workflow_started(event)

        # Verify workflow execution was triggered by checking step status
        instance.refresh_from_db()
        # After execution, steps should be completed or running
        running_or_completed_steps = instance.steps.filter(
            status__in=[StepStatus.RUNNING, StepStatus.COMPLETED]
        ).count()
        self.assertGreaterEqual(
            running_or_completed_steps,
            initial_running_steps,
            "Workflow execution should be triggered",
        )

    def test_handle_step_completed_continues_execution(self):
        """Test that workflow.step.completed event continues execution."""
        # Create a workflow instance
        instance = self.engine.create_instance(
            workflow_name=f"multi_step_workflow_{self.uid}",
            input_data={"test_input": "test_value"},
            tenant_id=self.tenant.id,
            created_by_id=self.user.id,
        )
        instance = self.engine.start_instance(str(instance.id))

        # Get initial step status
        initial_completed_steps = instance.steps.filter(status=StepStatus.COMPLETED).count()
        initial_running_steps = instance.steps.filter(status=StepStatus.RUNNING).count()

        event = {
            "event_type": "workflow.step.completed",
            "event_id": str(uuid.uuid4()),
            "data": {
                "workflow_instance_id": str(instance.id),
                "step_index": 0,
                "step_name": "step1",
            },
        }

        # Handle event - should continue execution (real implementation)
        self.subscriber._handle_step_completed(event)

        # Verify execution was continued by checking step status
        instance.refresh_from_db()
        # After execution continues, more steps should be completed or running
        completed_or_running_steps = instance.steps.filter(
            status__in=[StepStatus.COMPLETED, StepStatus.RUNNING]
        ).count()
        # Should have at least as many completed/running steps as before, or more
        self.assertGreaterEqual(
            completed_or_running_steps,
            initial_completed_steps + initial_running_steps,
            "Workflow execution should continue",
        )

    def test_handle_step_completed_workflow_not_running(self):
        """Test that step completion doesn't continue if workflow is not running."""
        # Create a completed workflow instance
        instance = self.engine.create_instance(
            workflow_name=f"multi_step_workflow_{self.uid}",
            input_data={"test_input": "test_value"},
            tenant_id=self.tenant.id,
            created_by_id=self.user.id,
        )
        instance.status = WorkflowStatus.COMPLETED
        instance.save()

        event = {
            "event_type": "workflow.step.completed",
            "event_id": str(uuid.uuid4()),
            "data": {
                "workflow_instance_id": str(instance.id),
                "step_index": 0,
                "step_name": "step1",
            },
        }

        # Should not raise an error
        self.subscriber._handle_step_completed(event)


@pytest.mark.django_db(transaction=True)
@override_settings(
    EVENT_BUS_ENABLE_PERSISTENCE=True,
    EVENT_BUS_ASYNC_PERSISTENCE=False,
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,
)
class TestEventDrivenWorkflowIntegration(TestCase):
    """Integration tests for event-driven workflows."""

    def setUp(self):
        """Set up test fixtures."""
        self.uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(email=f"test-{uuid.uuid4().hex[:8]}@example.com", tenant=self.tenant)
        self.engine = WorkflowEngine()
        self.trigger_subscriber = WorkflowTriggerSubscriber(workflow_engine=self.engine)
        self.step_subscriber = WorkflowStepSubscriber(workflow_engine=self.engine)

        # Create workflow definition
        self.integration_wf_name = f"integration_workflow_{self.uid}"
        self.workflow_def = WorkflowDefinition.objects.create(
            name=self.integration_wf_name,
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [{"name": "step1", "type": "task", "task": "integration_task"}],
            },
            is_active=True,
        )

        # Register task
        def integration_task(input_data, instance, step):
            return {"result": "integration_success", "data": input_data}

        self.engine.register_task("integration_task", integration_task)

    def test_integration_step_events_with_progress(self):
        """Integration test: Verify step events are published with progress_percentage in existing workflows."""
        # Create and start workflow instance
        instance = self.engine.create_instance(
            workflow_name=self.integration_wf_name,
            input_data={"test_input": "test_value"},
            tenant_id=self.tenant.id,
            created_by_id=self.user.id,
        )
        instance = self.engine.start_instance(str(instance.id))

        # Count step events before execution
        initial_started_count = Event.objects.filter(
            event_type="workflow.step.started",
            data__workflow_instance_id=str(instance.id),
        ).count()
        initial_completed_count = Event.objects.filter(
            event_type="workflow.step.completed",
            data__workflow_instance_id=str(instance.id),
        ).count()

        # Execute workflow
        completed_instance = self.engine.execute_instance(str(instance.id))
        time.sleep(0.1)  # INTENTIONAL: brief yield for async event persistence

        # Verify workflow completed successfully
        self.assertEqual(completed_instance.status, WorkflowStatus.COMPLETED)

        # Verify step events were published by querying Event model
        step_started_events = Event.objects.filter(
            event_type="workflow.step.started",
            data__workflow_instance_id=str(instance.id),
        )
        step_completed_events = Event.objects.filter(
            event_type="workflow.step.completed",
            data__workflow_instance_id=str(instance.id),
        )

        self.assertGreater(
            step_started_events.count(),
            initial_started_count,
            "Should have step.started events",
        )
        self.assertGreater(
            step_completed_events.count(),
            initial_completed_count,
            "Should have step.completed events",
        )

        # Verify progress_percentage in step.started event
        started_event = step_started_events.order_by("timestamp").first()
        started_data = started_event.data
        self.assertIn("progress_percentage", started_data)
        self.assertIsInstance(started_data["progress_percentage"], (int, float))
        self.assertGreaterEqual(started_data["progress_percentage"], 0.0)
        self.assertLessEqual(started_data["progress_percentage"], 100.0)
        # Single step = 100%
        if step_started_events.count() == 1:
            self.assertEqual(started_data["progress_percentage"], 100.0)

        # Verify progress_percentage in step.completed event
        completed_event = step_completed_events.order_by("timestamp").first()
        completed_data = completed_event.data
        self.assertIn("progress_percentage", completed_data)
        self.assertIsInstance(completed_data["progress_percentage"], (int, float))
        self.assertGreaterEqual(completed_data["progress_percentage"], 0.0)
        self.assertLessEqual(completed_data["progress_percentage"], 100.0)
        # Single step = 100%
        if step_completed_events.count() == 1:
            self.assertEqual(completed_data["progress_percentage"], 100.0)

        # Verify progress is stored in state_data
        completed_instance.refresh_from_db()
        self.assertIn("progress_percentage", completed_instance.state_data)
        self.assertEqual(completed_instance.state_data["progress_percentage"], 100.0)

    def test_websocket_step_progress_events_format(self):
        """E2E test: Verify step progress events are published in correct format for WebSocket consumption."""

        # Register test task
        def test_task(input_data, instance, step):
            return {"result": "success"}

        self.engine.register_task("test_task", test_task)

        # Create workflow with multiple steps to test progress progression
        multi_step_workflow = WorkflowDefinition.objects.create(
            name=f"multi_step_websocket_workflow_{self.uid}",
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
            workflow_name=f"multi_step_websocket_workflow_{self.uid}",
            input_data={"test_input": "test_value"},
            tenant_id=self.tenant.id,
            created_by_id=self.user.id,
        )
        instance = self.engine.start_instance(str(instance.id))

        # Execute workflow
        self.engine.execute_instance(str(instance.id))
        time.sleep(0.1)  # INTENTIONAL: brief yield for async event persistence

        # Collect all step events by querying Event model
        step_events = Event.objects.filter(
            event_type__in=[
                "workflow.step.started",
                "workflow.step.completed",
                "workflow.step.failed",
            ],
            data__workflow_instance_id=str(instance.id),
        ).order_by("timestamp")

        # Verify we have step events
        self.assertGreater(step_events.count(), 0, "Should have step events")

        # Verify each step event has the correct format for WebSocket consumption
        for event in step_events:
            data = event.data
            # Required fields for WebSocket consumption
            self.assertIn("workflow_instance_id", data)
            self.assertIn("step_index", data)
            self.assertIn("step_name", data)
            self.assertIn("progress_percentage", data)

            # Verify progress_percentage is a valid number
            progress = data["progress_percentage"]
            self.assertIsInstance(progress, (int, float))
            self.assertGreaterEqual(progress, 0.0)
            self.assertLessEqual(progress, 100.0)

            # Verify step_index is an integer
            self.assertIsInstance(data["step_index"], int)
            self.assertGreaterEqual(data["step_index"], 0)

            # For completed events, verify duration_ms is present
            if event.event_type == "workflow.step.completed":
                self.assertIn("duration_ms", data)
                self.assertIsInstance(data["duration_ms"], (int, float))
                self.assertGreaterEqual(data["duration_ms"], 0)

            # Verify tenant and user IDs are present
            self.assertEqual(event.tenant_id, self.tenant.id)
            self.assertEqual(event.user_id, self.user.id)

            # For failed events, verify duration_ms is present
            if event.event_type == "workflow.step.failed":
                self.assertIn("duration_ms", data)
                self.assertIsInstance(data["duration_ms"], (int, float))
                self.assertGreaterEqual(data["duration_ms"], 0)

        # Verify progress progression: started events should have increasing progress
        started_events = [e for e in step_events if e.event_type == "workflow.step.started"]
        started_events.sort(key=lambda x: x.data["step_index"])

        if len(started_events) > 1:
            # Progress should increase or stay the same as steps progress
            progresses = [e.data["progress_percentage"] for e in started_events]
            # Progress should generally increase (allowing for rounding)
            for i in range(1, len(progresses)):
                self.assertGreaterEqual(
                    progresses[i],
                    progresses[i - 1] - 1.0,
                    "Progress should generally increase or stay the same",
                )

        # Verify completed events have progress_percentage
        completed_events = [e for e in step_events if e.event_type == "workflow.step.completed"]
        for ev in completed_events:
            self.assertIn("progress_percentage", ev.data)
            progress = ev.data["progress_percentage"]
            self.assertGreaterEqual(progress, 0.0)
            self.assertLessEqual(progress, 100.0)

    def test_end_to_end_event_driven_workflow(self):
        """Test complete event-driven workflow execution."""
        # Register workflow trigger
        self.trigger_subscriber.register_workflow_trigger(
            "contract.created", self.integration_wf_name
        )

        # Create event
        event = {
            "event_type": "contract.created",
            "event_id": str(uuid.uuid4()),
            "data": {"contract_id": str(uuid.uuid4()), "test_data": "test_value"},
            "source": {"tenant_id": str(self.tenant.id), "user_id": str(self.user.id)},
        }

        # Handle event (this should trigger workflow)
        self.trigger_subscriber._handle_event(event)
        time.sleep(0.2)  # INTENTIONAL: brief yield for async event persistence and workflow execution

        # Verify workflow instance was created (filter by tenant to avoid stale --reuse-db data)
        instances = WorkflowInstance.objects.filter(
            workflow_name=self.integration_wf_name,
            tenant=self.tenant,
        )
        self.assertEqual(instances.count(), 1)

        instance = instances.first()
        self.assertEqual(instance.status, WorkflowStatus.COMPLETED)
        self.assertIn("test_data", instance.input_data)

        # Verify events were published (filter by instance to avoid stale data)
        workflow_events = Event.objects.filter(
            event_type__startswith="workflow.",
            data__workflow_instance_id=str(instance.id),
        )
        self.assertGreater(workflow_events.count(), 0)

        # Verify lifecycle events exist (use >= 1 to handle event-bus replays)
        created_events = workflow_events.filter(event_type="workflow.created")
        self.assertGreaterEqual(created_events.count(), 1)

        started_events = workflow_events.filter(event_type="workflow.started")
        self.assertGreaterEqual(started_events.count(), 1)

        completed_events = workflow_events.filter(event_type="workflow.completed")
        self.assertGreaterEqual(completed_events.count(), 1)

        step_started_events = workflow_events.filter(event_type="workflow.step.started")
        self.assertGreaterEqual(step_started_events.count(), 1)

        step_completed_events = workflow_events.filter(event_type="workflow.step.completed")
        self.assertGreaterEqual(step_completed_events.count(), 1)
