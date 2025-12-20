"""
Unit tests for event-driven workflows.

Tests workflow event publishing, event-triggered workflow starts, and event-based workflow steps.
"""

import uuid
from unittest.mock import MagicMock, Mock, patch

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
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
from hub.apps.tenants.models import Tenant

User = get_user_model()


@pytest.mark.django_db
class TestWorkflowEventPublishing(TestCase):
    """Test workflow event publishing."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.user = User.objects.create_user(email="test@example.com", tenant=self.tenant)
        self.engine = WorkflowEngine()

        # Create a simple workflow definition
        self.workflow_def = WorkflowDefinition.objects.create(
            name="test_workflow",
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

    @patch("hub.apps.core.events.service_publishers.EventPublisher.publish")
    def test_publish_workflow_created_event(self, mock_publish):
        """Test that workflow.created event is published when instance is created."""
        mock_publish.return_value = str(uuid.uuid4())

        input_data = {"test_input": "test_value"}
        instance = self.engine.create_instance(
            workflow_name="test_workflow",
            input_data=input_data,
            tenant_id=self.tenant.id,
            created_by_id=self.user.id,
        )

        # Verify event was published
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        self.assertEqual(call_args[1]["event_type"], "workflow.created")
        self.assertEqual(call_args[1]["data"]["workflow_instance_id"], str(instance.id))
        self.assertEqual(call_args[1]["data"]["workflow_name"], "test_workflow")
        self.assertEqual(call_args[1]["tenant_id"], str(self.tenant.id))
        self.assertEqual(call_args[1]["user_id"], str(self.user.id))

    @patch("hub.apps.core.events.service_publishers.EventPublisher.publish")
    def test_publish_workflow_started_event(self, mock_publish):
        """Test that workflow.started event is published when instance is started."""
        mock_publish.return_value = str(uuid.uuid4())

        instance = self.engine.create_instance(
            workflow_name="test_workflow",
            input_data={"test_input": "test_value"},
            tenant_id=self.tenant.id,
            created_by_id=self.user.id,
        )

        # Reset mock to only count started event
        mock_publish.reset_mock()

        started_instance = self.engine.start_instance(str(instance.id))

        # Verify event was published
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        self.assertEqual(call_args[1]["event_type"], "workflow.started")
        self.assertEqual(call_args[1]["data"]["workflow_instance_id"], str(instance.id))
        self.assertEqual(call_args[1]["data"]["workflow_name"], "test_workflow")

    @patch("hub.apps.core.events.service_publishers.EventPublisher.publish")
    def test_publish_workflow_completed_event(self, mock_publish):
        """Test that workflow.completed event is published when workflow completes."""
        mock_publish.return_value = str(uuid.uuid4())

        instance = self.engine.create_instance(
            workflow_name="test_workflow",
            input_data={"test_input": "test_value"},
            tenant_id=self.tenant.id,
            created_by_id=self.user.id,
        )
        instance = self.engine.start_instance(str(instance.id))

        # Reset mock to only count completed event
        mock_publish.reset_mock()

        completed_instance = self.engine.execute_instance(str(instance.id))

        # Verify workflow.completed event was published
        completed_calls = [
            call
            for call in mock_publish.call_args_list
            if call[1]["event_type"] == "workflow.completed"
        ]
        self.assertEqual(len(completed_calls), 1)

        call_args = completed_calls[0]
        self.assertEqual(call_args[1]["data"]["workflow_instance_id"], str(instance.id))
        self.assertEqual(call_args[1]["data"]["workflow_name"], "test_workflow")
        self.assertIn("output_data", call_args[1]["data"])
        self.assertIn("duration_ms", call_args[1]["data"])

    @patch("hub.apps.core.events.service_publishers.EventPublisher.publish")
    def test_publish_workflow_failed_event(self, mock_publish):
        """Test that workflow.failed event is published when workflow fails."""
        mock_publish.return_value = str(uuid.uuid4())

        # Register a failing task
        def failing_task(input_data, instance, step):
            raise ValueError("Task failed")

        self.engine.register_task("failing_task", failing_task)

        # Create workflow with failing task
        workflow_def = WorkflowDefinition.objects.create(
            name="failing_workflow",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [{"name": "step1", "type": "task", "task": "failing_task"}],
            },
            is_active=True,
        )

        instance = self.engine.create_instance(
            workflow_name="failing_workflow",
            input_data={"test_input": "test_value"},
            tenant_id=self.tenant.id,
            created_by_id=self.user.id,
        )
        instance = self.engine.start_instance(str(instance.id))

        # Reset mock to only count failed event
        mock_publish.reset_mock()

        failed_instance = self.engine.execute_instance(str(instance.id))

        # Verify workflow.failed event was published
        failed_calls = [
            call
            for call in mock_publish.call_args_list
            if call[1]["event_type"] == "workflow.failed"
        ]
        self.assertEqual(len(failed_calls), 1)

        call_args = failed_calls[0]
        self.assertEqual(call_args[1]["data"]["workflow_instance_id"], str(instance.id))
        self.assertEqual(call_args[1]["data"]["workflow_name"], "failing_workflow")
        self.assertIn("error_message", call_args[1]["data"])

    @patch("hub.apps.core.events.service_publishers.EventPublisher.publish")
    def test_publish_workflow_step_started_event(self, mock_publish):
        """Test that workflow.step.started event is published when step starts."""
        mock_publish.return_value = str(uuid.uuid4())

        instance = self.engine.create_instance(
            workflow_name="test_workflow",
            input_data={"test_input": "test_value"},
            tenant_id=self.tenant.id,
            created_by_id=self.user.id,
        )
        instance = self.engine.start_instance(str(instance.id))

        # Reset mock to only count step events
        mock_publish.reset_mock()

        self.engine.execute_instance(str(instance.id))

        # Verify workflow.step.started event was published
        step_started_calls = [
            call
            for call in mock_publish.call_args_list
            if call[1]["event_type"] == "workflow.step.started"
        ]
        self.assertEqual(len(step_started_calls), 1)

        call_args = step_started_calls[0]
        self.assertEqual(call_args[1]["data"]["workflow_instance_id"], str(instance.id))
        self.assertEqual(call_args[1]["data"]["step_index"], 0)
        self.assertEqual(call_args[1]["data"]["step_name"], "step1")
        self.assertEqual(call_args[1]["data"]["step_type"], "task")
        # Verify progress_percentage is included
        self.assertIn("progress_percentage", call_args[1]["data"])
        self.assertIsNotNone(call_args[1]["data"]["progress_percentage"])
        # For a single step workflow, progress should be 100% when starting the only step
        self.assertEqual(call_args[1]["data"]["progress_percentage"], 100.0)

    @patch("hub.apps.core.events.service_publishers.EventPublisher.publish")
    def test_publish_workflow_step_completed_event(self, mock_publish):
        """Test that workflow.step.completed event is published when step completes."""
        mock_publish.return_value = str(uuid.uuid4())

        instance = self.engine.create_instance(
            workflow_name="test_workflow",
            input_data={"test_input": "test_value"},
            tenant_id=self.tenant.id,
            created_by_id=self.user.id,
        )
        instance = self.engine.start_instance(str(instance.id))

        # Reset mock to only count step events
        mock_publish.reset_mock()

        self.engine.execute_instance(str(instance.id))

        # Verify workflow.step.completed event was published
        step_completed_calls = [
            call
            for call in mock_publish.call_args_list
            if call[1]["event_type"] == "workflow.step.completed"
        ]
        self.assertEqual(len(step_completed_calls), 1)

        call_args = step_completed_calls[0]
        self.assertEqual(call_args[1]["data"]["workflow_instance_id"], str(instance.id))
        self.assertEqual(call_args[1]["data"]["step_index"], 0)
        self.assertEqual(call_args[1]["data"]["step_name"], "step1")
        self.assertIn("output_data", call_args[1]["data"])
        self.assertIn("duration_ms", call_args[1]["data"])
        # Verify progress_percentage is included
        self.assertIn("progress_percentage", call_args[1]["data"])
        self.assertIsNotNone(call_args[1]["data"]["progress_percentage"])
        # For a single step workflow, progress should be 100% after completion
        self.assertEqual(call_args[1]["data"]["progress_percentage"], 100.0)

    @patch("hub.apps.core.events.service_publishers.EventPublisher.publish")
    def test_publish_workflow_step_failed_event(self, mock_publish):
        """Test that workflow.step.failed event is published when step fails."""
        mock_publish.return_value = str(uuid.uuid4())

        # Register a failing task
        def failing_task(input_data, instance, step):
            raise ValueError("Step failed")

        self.engine.register_task("failing_task", failing_task)

        # Create workflow with failing task
        workflow_def = WorkflowDefinition.objects.create(
            name="failing_step_workflow",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [{"name": "step1", "type": "task", "task": "failing_task"}],
            },
            is_active=True,
        )

        instance = self.engine.create_instance(
            workflow_name="failing_step_workflow",
            input_data={"test_input": "test_value"},
            tenant_id=self.tenant.id,
            created_by_id=self.user.id,
        )
        instance = self.engine.start_instance(str(instance.id))

        # Reset mock to only count step events
        mock_publish.reset_mock()

        try:
            self.engine.execute_instance(str(instance.id))
        except WorkflowExecutionError:
            pass  # Expected to fail

        # Verify workflow.step.failed event was published
        step_failed_calls = [
            call
            for call in mock_publish.call_args_list
            if call[1]["event_type"] == "workflow.step.failed"
        ]
        self.assertEqual(len(step_failed_calls), 1)

        call_args = step_failed_calls[0]
        self.assertEqual(call_args[1]["data"]["workflow_instance_id"], str(instance.id))
        self.assertEqual(call_args[1]["data"]["step_index"], 0)
        self.assertEqual(call_args[1]["data"]["step_name"], "step1")
        self.assertIn("error_message", call_args[1]["data"])
        self.assertIn("error_details", call_args[1]["data"])
        # Verify progress_percentage is included
        self.assertIn("progress_percentage", call_args[1]["data"])
        self.assertIsNotNone(call_args[1]["data"]["progress_percentage"])
        # Verify duration_ms is included
        self.assertIn("duration_ms", call_args[1]["data"])
        self.assertIsNotNone(call_args[1]["data"]["duration_ms"])

    @patch("hub.apps.core.events.service_publishers.EventPublisher.publish")
    def test_step_events_include_progress_percentage_multi_step(self, mock_publish):
        """Test that step events include progress_percentage for multi-step workflows."""
        mock_publish.return_value = str(uuid.uuid4())

        # Create workflow with multiple steps
        multi_step_workflow = WorkflowDefinition.objects.create(
            name="multi_step_workflow",
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
            workflow_name="multi_step_workflow",
            input_data={"test_input": "test_value"},
            tenant_id=self.tenant.id,
            created_by_id=self.user.id,
        )
        instance = self.engine.start_instance(str(instance.id))

        # Reset mock to only count step events
        mock_publish.reset_mock()

        self.engine.execute_instance(str(instance.id))

        # Verify all step events were published with progress_percentage
        step_started_calls = [
            call
            for call in mock_publish.call_args_list
            if call[1]["event_type"] == "workflow.step.started"
        ]
        step_completed_calls = [
            call
            for call in mock_publish.call_args_list
            if call[1]["event_type"] == "workflow.step.completed"
        ]

        self.assertEqual(len(step_started_calls), 3, "Should have 3 step.started events")
        self.assertEqual(len(step_completed_calls), 3, "Should have 3 step.completed events")

        # Verify progress_percentage for each step
        # Step 0: 33.33% (1/3 * 100)
        # Step 1: 66.67% (2/3 * 100)
        # Step 2: 100% (3/3 * 100)
        expected_progresses = [100.0 / 3, 200.0 / 3, 100.0]
        for i, call_args in enumerate(step_started_calls):
            self.assertIn("progress_percentage", call_args[1]["data"])
            progress = call_args[1]["data"]["progress_percentage"]
            self.assertAlmostEqual(progress, expected_progresses[i], places=1)

    @patch("hub.apps.core.events.service_publishers.EventPublisher.publish")
    def test_progress_stored_in_state_data(self, mock_publish):
        """Test that progress is stored in WorkflowInstance.state_data."""
        mock_publish.return_value = str(uuid.uuid4())

        # Create workflow with multiple steps
        multi_step_workflow = WorkflowDefinition.objects.create(
            name="multi_step_workflow",
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
            workflow_name="multi_step_workflow",
            input_data={"test_input": "test_value"},
            tenant_id=self.tenant.id,
            created_by_id=self.user.id,
        )
        instance = self.engine.start_instance(str(instance.id))

        # Execute first step only
        self.engine.execute_instance(str(instance.id))

        # Refresh instance to get updated state_data
        instance.refresh_from_db()

        # Verify progress is stored in state_data
        self.assertIn("progress_percentage", instance.state_data)
        self.assertIn("current_step_index", instance.state_data)
        self.assertIn("current_step_name", instance.state_data)
        self.assertIsNotNone(instance.state_data["progress_percentage"])
        # After first step completes, progress should be 100% (2/2 * 100)
        self.assertEqual(instance.state_data["progress_percentage"], 100.0)

    @patch("hub.apps.core.events.service_publishers.EventPublisher.publish")
    def test_step_events_include_all_metadata(self, mock_publish):
        """Test that step events include all required metadata: step_index, step_name, progress_percentage, duration_ms."""
        mock_publish.return_value = str(uuid.uuid4())

        instance = self.engine.create_instance(
            workflow_name="test_workflow",
            input_data={"test_input": "test_value"},
            tenant_id=self.tenant.id,
            created_by_id=self.user.id,
        )
        instance = self.engine.start_instance(str(instance.id))

        # Reset mock to only count step events
        mock_publish.reset_mock()

        self.engine.execute_instance(str(instance.id))

        # Verify step.started event has all metadata
        step_started_calls = [
            call
            for call in mock_publish.call_args_list
            if call[1]["event_type"] == "workflow.step.started"
        ]
        self.assertEqual(len(step_started_calls), 1)
        started_data = step_started_calls[0][1]["data"]
        self.assertIn("step_index", started_data)
        self.assertIn("step_name", started_data)
        self.assertIn("progress_percentage", started_data)

        # Verify step.completed event has all metadata
        step_completed_calls = [
            call
            for call in mock_publish.call_args_list
            if call[1]["event_type"] == "workflow.step.completed"
        ]
        self.assertEqual(len(step_completed_calls), 1)
        completed_data = step_completed_calls[0][1]["data"]
        self.assertIn("step_index", completed_data)
        self.assertIn("step_name", completed_data)
        self.assertIn("progress_percentage", completed_data)
        self.assertIn("duration_ms", completed_data)

    @patch("hub.apps.core.events.service_publishers.EventPublisher.publish")
    def test_step_failed_event_includes_duration_ms(self, mock_publish):
        """Test that workflow.step.failed event includes duration_ms."""
        mock_publish.return_value = str(uuid.uuid4())

        # Register a failing task
        def failing_task(input_data, instance, step):
            raise ValueError("Step failed")

        self.engine.register_task("failing_task", failing_task)

        # Create workflow with failing task
        workflow_def = WorkflowDefinition.objects.create(
            name="failing_step_workflow",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [{"name": "step1", "type": "task", "task": "failing_task"}],
            },
            is_active=True,
        )

        instance = self.engine.create_instance(
            workflow_name="failing_step_workflow",
            input_data={"test_input": "test_value"},
            tenant_id=self.tenant.id,
            created_by_id=self.user.id,
        )
        instance = self.engine.start_instance(str(instance.id))

        # Reset mock to only count step events
        mock_publish.reset_mock()

        try:
            self.engine.execute_instance(str(instance.id))
        except WorkflowExecutionError:
            pass  # Expected to fail

        # Verify workflow.step.failed event includes duration_ms
        step_failed_calls = [
            call
            for call in mock_publish.call_args_list
            if call[1]["event_type"] == "workflow.step.failed"
        ]
        self.assertEqual(len(step_failed_calls), 1)
        failed_data = step_failed_calls[0][1]["data"]
        self.assertIn("duration_ms", failed_data)
        self.assertIsInstance(failed_data["duration_ms"], int)
        self.assertGreaterEqual(failed_data["duration_ms"], 0)


@pytest.mark.django_db
class TestWorkflowTriggerSubscriber(TestCase):
    """Test event-triggered workflow starts."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.user = User.objects.create_user(email="test@example.com", tenant=self.tenant)
        self.engine = WorkflowEngine()
        self.subscriber = WorkflowTriggerSubscriber(workflow_engine=self.engine)

        # Create a workflow definition
        self.workflow_def = WorkflowDefinition.objects.create(
            name="triggered_workflow",
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
        self.subscriber.register_workflow_trigger("contract.created", "triggered_workflow")

        self.assertIn("contract.created", self.subscriber.workflow_mapping)
        self.assertEqual(self.subscriber.workflow_mapping["contract.created"], "triggered_workflow")

    @patch("hub.apps.orchestration.workflow_engine.WorkflowEngine.create_instance")
    @patch("hub.apps.orchestration.workflow_engine.WorkflowEngine.start_instance")
    @patch("hub.apps.orchestration.workflow_engine.WorkflowEngine.execute_instance")
    def test_handle_event_triggers_workflow(self, mock_execute, mock_start, mock_create):
        """Test that handling an event triggers a workflow."""
        # Register trigger
        self.subscriber.register_workflow_trigger("contract.created", "triggered_workflow")

        # Create mock workflow instance
        mock_instance = Mock()
        mock_instance.id = uuid.uuid4()
        mock_create.return_value = mock_instance
        mock_start.return_value = mock_instance
        mock_execute.return_value = mock_instance

        # Create event
        event = {
            "event_type": "contract.created",
            "event_id": str(uuid.uuid4()),
            "data": {"contract_id": str(uuid.uuid4())},
            "source": {"tenant_id": str(self.tenant.id), "user_id": str(self.user.id)},
        }

        # Handle event
        self.subscriber._handle_event(event)

        # Verify workflow was created, started, and executed
        mock_create.assert_called_once()
        mock_start.assert_called_once()
        mock_execute.assert_called_once()

        # Verify workflow was created with correct parameters
        create_call = mock_create.call_args
        self.assertEqual(create_call[1]["workflow_name"], "triggered_workflow")
        self.assertEqual(create_call[1]["tenant_id"], str(self.tenant.id))
        self.assertEqual(create_call[1]["created_by_id"], str(self.user.id))
        self.assertEqual(create_call[1]["input_data"], event["data"])

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


@pytest.mark.django_db
class TestWorkflowStepSubscriber(TestCase):
    """Test event-based workflow step execution."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.user = User.objects.create_user(email="test@example.com", tenant=self.tenant)
        self.engine = WorkflowEngine()
        self.subscriber = WorkflowStepSubscriber(workflow_engine=self.engine)

        # Create a workflow definition with multiple steps
        self.workflow_def = WorkflowDefinition.objects.create(
            name="multi_step_workflow",
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

    @patch("hub.apps.orchestration.workflow_engine.WorkflowEngine.execute_instance")
    def test_handle_workflow_started_triggers_execution(self, mock_execute):
        """Test that workflow.started event triggers execution."""
        mock_instance = Mock()
        mock_instance.id = uuid.uuid4()
        mock_execute.return_value = mock_instance

        event = {
            "event_type": "workflow.started",
            "event_id": str(uuid.uuid4()),
            "data": {"workflow_instance_id": str(uuid.uuid4())},
        }

        self.subscriber._handle_workflow_started(event)

        mock_execute.assert_called_once_with(event["data"]["workflow_instance_id"])

    @patch("hub.apps.orchestration.workflow_engine.WorkflowEngine.execute_instance")
    def test_handle_step_completed_continues_execution(self, mock_execute):
        """Test that workflow.step.completed event continues execution."""
        # Create a workflow instance
        instance = self.engine.create_instance(
            workflow_name="multi_step_workflow",
            input_data={"test_input": "test_value"},
            tenant_id=self.tenant.id,
            created_by_id=self.user.id,
        )
        instance.status = WorkflowStatus.RUNNING
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

        self.subscriber._handle_step_completed(event)

        # Verify execution was continued
        mock_execute.assert_called_once_with(str(instance.id))

    def test_handle_step_completed_workflow_not_running(self):
        """Test that step completion doesn't continue if workflow is not running."""
        # Create a completed workflow instance
        instance = self.engine.create_instance(
            workflow_name="multi_step_workflow",
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


@pytest.mark.django_db
class TestEventDrivenWorkflowIntegration(TestCase):
    """Integration tests for event-driven workflows."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.user = User.objects.create_user(email="test@example.com", tenant=self.tenant)
        self.engine = WorkflowEngine()
        self.trigger_subscriber = WorkflowTriggerSubscriber(workflow_engine=self.engine)
        self.step_subscriber = WorkflowStepSubscriber(workflow_engine=self.engine)

        # Create workflow definition
        self.workflow_def = WorkflowDefinition.objects.create(
            name="integration_workflow",
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

    @patch("hub.apps.core.events.service_publishers.EventPublisher.publish")
    def test_integration_step_events_with_progress(self, mock_publish):
        """Integration test: Verify step events are published with progress_percentage in existing workflows."""
        mock_publish.return_value = str(uuid.uuid4())

        # Create and start workflow instance
        instance = self.engine.create_instance(
            workflow_name="integration_workflow",
            input_data={"test_input": "test_value"},
            tenant_id=self.tenant.id,
            created_by_id=self.user.id,
        )
        instance = self.engine.start_instance(str(instance.id))

        # Reset mock to only count step events
        mock_publish.reset_mock()

        # Execute workflow
        completed_instance = self.engine.execute_instance(str(instance.id))

        # Verify workflow completed successfully
        self.assertEqual(completed_instance.status, WorkflowStatus.COMPLETED)

        # Verify step events were published
        step_started_calls = [
            call
            for call in mock_publish.call_args_list
            if call[1]["event_type"] == "workflow.step.started"
        ]
        step_completed_calls = [
            call
            for call in mock_publish.call_args_list
            if call[1]["event_type"] == "workflow.step.completed"
        ]

        self.assertEqual(len(step_started_calls), 1)
        self.assertEqual(len(step_completed_calls), 1)

        # Verify progress_percentage in step.started event
        started_data = step_started_calls[0][1]["data"]
        self.assertIn("progress_percentage", started_data)
        self.assertEqual(started_data["progress_percentage"], 100.0)  # Single step = 100%

        # Verify progress_percentage in step.completed event
        completed_data = step_completed_calls[0][1]["data"]
        self.assertIn("progress_percentage", completed_data)
        self.assertEqual(completed_data["progress_percentage"], 100.0)

        # Verify progress is stored in state_data
        completed_instance.refresh_from_db()
        self.assertIn("progress_percentage", completed_instance.state_data)
        self.assertEqual(completed_instance.state_data["progress_percentage"], 100.0)

    @patch("hub.apps.core.events.service_publishers.EventPublisher.publish")
    def test_websocket_step_progress_events_format(self, mock_publish):
        """E2E test: Verify step progress events are published in correct format for WebSocket consumption."""
        mock_publish.return_value = str(uuid.uuid4())

        # Create workflow with multiple steps to test progress progression
        multi_step_workflow = WorkflowDefinition.objects.create(
            name="multi_step_websocket_workflow",
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
            workflow_name="multi_step_websocket_workflow",
            input_data={"test_input": "test_value"},
            tenant_id=self.tenant.id,
            created_by_id=self.user.id,
        )
        instance = self.engine.start_instance(str(instance.id))

        # Reset mock to only count step events
        mock_publish.reset_mock()

        # Execute workflow
        self.engine.execute_instance(str(instance.id))

        # Collect all step events
        step_events = []
        for call in mock_publish.call_args_list:
            event_type = call[1]["event_type"]
            if event_type in ["workflow.step.started", "workflow.step.completed", "workflow.step.failed"]:
                step_events.append({
                    "event_type": event_type,
                    "data": call[1]["data"],
                })

        # Verify we have step events
        self.assertGreater(len(step_events), 0, "Should have step events")

        # Verify each step event has the correct format for WebSocket consumption
        for event in step_events:
            data = event["data"]
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
            if event["event_type"] == "workflow.step.completed":
                self.assertIn("duration_ms", data)
                self.assertIsInstance(data["duration_ms"], int)
                self.assertGreaterEqual(data["duration_ms"], 0)

            # For failed events, verify duration_ms is present
            if event["event_type"] == "workflow.step.failed":
                self.assertIn("duration_ms", data)
                self.assertIsInstance(data["duration_ms"], int)
                self.assertGreaterEqual(data["duration_ms"], 0)

        # Verify progress progression: started events should have increasing progress
        started_events = [e for e in step_events if e["event_type"] == "workflow.step.started"]
        started_events.sort(key=lambda x: x["data"]["step_index"])

        if len(started_events) > 1:
            # Progress should increase or stay the same as steps progress
            progresses = [e["data"]["progress_percentage"] for e in started_events]
            # Progress should generally increase (allowing for rounding)
            for i in range(1, len(progresses)):
                self.assertGreaterEqual(progresses[i], progresses[i-1] - 1.0,
                    "Progress should generally increase or stay the same")

        # Verify completed events have progress_percentage
        completed_events = [e for e in step_events if e["event_type"] == "workflow.step.completed"]
        for event in completed_events:
            self.assertIn("progress_percentage", event["data"])
            progress = event["data"]["progress_percentage"]
            self.assertGreaterEqual(progress, 0.0)
            self.assertLessEqual(progress, 100.0)

    def test_end_to_end_event_driven_workflow(self):
        """Test complete event-driven workflow execution."""
        # Register workflow trigger
        self.trigger_subscriber.register_workflow_trigger(
            "contract.created", "integration_workflow"
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

        # Verify workflow instance was created
        instances = WorkflowInstance.objects.filter(workflow_name="integration_workflow")
        self.assertEqual(instances.count(), 1)

        instance = instances.first()
        self.assertEqual(instance.status, WorkflowStatus.COMPLETED)
        self.assertIn("test_data", instance.input_data)

        # Verify events were published
        workflow_events = Event.objects.filter(event_type__startswith="workflow.")
        self.assertGreater(workflow_events.count(), 0)

        # Verify workflow.created event exists
        created_events = workflow_events.filter(event_type="workflow.created")
        self.assertEqual(created_events.count(), 1)

        # Verify workflow.started event exists
        started_events = workflow_events.filter(event_type="workflow.started")
        self.assertEqual(started_events.count(), 1)

        # Verify workflow.completed event exists
        completed_events = workflow_events.filter(event_type="workflow.completed")
        self.assertEqual(completed_events.count(), 1)

        # Verify step events exist
        step_started_events = workflow_events.filter(event_type="workflow.step.started")
        self.assertEqual(step_started_events.count(), 1)

        step_completed_events = workflow_events.filter(event_type="workflow.step.completed")
        self.assertEqual(step_completed_events.count(), 1)
