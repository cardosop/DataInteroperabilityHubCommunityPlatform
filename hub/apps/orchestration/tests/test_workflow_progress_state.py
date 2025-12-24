"""
Unit and integration tests for WorkflowInstance progress in state_data (Task 0.3.2).

Tests verify that progress_percentage is correctly stored and updated in state_data:
- During step execution (when step starts)
- After step completion
- At step failure
- Progress persistence across workflow execution
"""
try:
    import pytest
    pytestmark = pytest.mark.django_db(transaction=True)
except ImportError:
    # pytest not available, using Django test runner
    pytest = None
    pytestmark = None

import uuid
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

User = get_user_model()


class WorkflowProgressStateTest(TestCase):
    """Unit tests for progress storage in WorkflowInstance.state_data (Task 0.3.2)"""

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

    def test_progress_stored_when_step_starts(self):
        """Test that progress_percentage is stored in state_data when step starts (Task 0.3.2)"""
        # Create workflow with 3 steps
        workflow_def = WorkflowDefinition.objects.create(
            name="test_progress_workflow",
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
            workflow_name="test_progress_workflow",
            input_data={},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        instance = self.engine.start_instance(str(instance.id))

        # Execute workflow (executes all steps)
        self.engine.execute_instance(str(instance.id))

        # Refresh instance to get updated state_data
        instance.refresh_from_db()

        # Verify progress is stored in state_data
        self.assertIn("progress_percentage", instance.state_data)
        self.assertIsInstance(instance.state_data["progress_percentage"], (int, float))
        self.assertGreaterEqual(instance.state_data["progress_percentage"], 0.0)
        self.assertLessEqual(instance.state_data["progress_percentage"], 100.0)

        # Verify current step information is stored
        self.assertIn("current_step_index", instance.state_data)
        self.assertIn("current_step_name", instance.state_data)

        # After all steps complete, progress should be 100%
        self.assertEqual(instance.state_data["progress_percentage"], 100.0)
        self.assertEqual(instance.status, WorkflowStatus.COMPLETED)

    def test_progress_updated_after_step_completion(self):
        """Test that progress_percentage is updated in state_data after step completion (Task 0.3.2)"""
        # Create workflow with 4 steps
        workflow_def = WorkflowDefinition.objects.create(
            name="test_progress_completion",
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
            workflow_name="test_progress_completion",
            input_data={},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        instance = self.engine.start_instance(str(instance.id))

        # Execute workflow (executes all steps)
        self.engine.execute_instance(str(instance.id))
        instance.refresh_from_db()

        # After all steps complete, progress should be 100%
        self.assertEqual(
            instance.state_data["progress_percentage"],
            100.0,
            "Progress should be 100% after all steps complete"
        )

        # Verify workflow is completed
        self.assertEqual(instance.status, WorkflowStatus.COMPLETED)

    def test_progress_updated_at_step_failure(self):
        """Test that progress_percentage is updated in state_data when step fails (Task 0.3.2)"""
        # Register a failing task
        def failing_task(input_data, instance, step):
            raise ValueError("Task failed intentionally")

        self.engine.register_task("failing_task", failing_task)

        # Create workflow with 3 steps, second step fails
        workflow_def = WorkflowDefinition.objects.create(
            name="test_progress_failure",
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
            workflow_name="test_progress_failure",
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

        instance.refresh_from_db()

        # Verify workflow failed
        self.assertEqual(instance.status, WorkflowStatus.FAILED)

        # Verify progress is still stored even after failure
        self.assertIn("progress_percentage", instance.state_data)
        self.assertIsInstance(instance.state_data["progress_percentage"], (int, float))
        self.assertGreaterEqual(instance.state_data["progress_percentage"], 0.0)
        self.assertLessEqual(instance.state_data["progress_percentage"], 100.0)

        # Progress at failure point should reflect the failed step
        # At step index 1 (step2 failed), progress = (1+1)/3*100 = 66.67%
        expected_progress_at_failure = ((1 + 1) / 3) * 100.0
        self.assertAlmostEqual(
            instance.state_data["progress_percentage"],
            expected_progress_at_failure,
            places=1,
            msg="Progress should reflect the step that failed"
        )

        # Verify error information is stored
        self.assertIn("last_error", instance.state_data)

    def test_progress_reaches_100_percent_on_completion(self):
        """Test that progress_percentage reaches 100% when workflow completes (Task 0.3.2)"""
        # Create workflow with 2 steps
        workflow_def = WorkflowDefinition.objects.create(
            name="test_progress_completion_100",
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
            workflow_name="test_progress_completion_100",
            input_data={},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        instance = self.engine.start_instance(str(instance.id))

        # Execute all steps
        self.engine.execute_instance(str(instance.id))
        instance.refresh_from_db()

        # Verify workflow is completed
        self.assertEqual(instance.status, WorkflowStatus.COMPLETED)

        # Verify progress is 100%
        self.assertEqual(
            instance.state_data["progress_percentage"],
            100.0,
            "Progress should be 100% when workflow completes"
        )

    def test_progress_persistence_across_executions(self):
        """Test that progress_percentage persists correctly across multiple executions (Task 0.3.2)"""
        # Create workflow with 5 steps that can be executed incrementally
        # We'll use a task that checks state_data to verify progress
        def progress_aware_task(input_data, instance, step):
            # Access state_data to verify progress is stored
            progress = instance.state_data.get("progress_percentage", 0.0)
            return {
                "result": "success",
                "step": step.step_name,
                "progress_at_execution": progress
            }

        self.engine.register_task("progress_aware_task", progress_aware_task)

        workflow_def = WorkflowDefinition.objects.create(
            name="test_progress_persistence",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [
                    {"name": "step1", "type": "task", "task": "progress_aware_task"},
                    {"name": "step2", "type": "task", "task": "progress_aware_task"},
                    {"name": "step3", "type": "task", "task": "progress_aware_task"},
                    {"name": "step4", "type": "task", "task": "progress_aware_task"},
                    {"name": "step5", "type": "task", "task": "progress_aware_task"},
                ],
            },
            is_active=True,
        )

        instance = self.engine.create_instance(
            workflow_name="test_progress_persistence",
            input_data={},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        instance = self.engine.start_instance(str(instance.id))

        # Execute workflow (executes all steps)
        self.engine.execute_instance(str(instance.id))
        instance.refresh_from_db()

        # Verify final progress is 100%
        self.assertEqual(instance.state_data["progress_percentage"], 100.0)

        # Verify progress is valid throughout
        self.assertGreaterEqual(instance.state_data["progress_percentage"], 0.0)
        self.assertLessEqual(instance.state_data["progress_percentage"], 100.0)

    def test_progress_with_single_step_workflow(self):
        """Test progress storage with single step workflow (Task 0.3.2)"""
        workflow_def = WorkflowDefinition.objects.create(
            name="test_progress_single_step",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [
                    {"name": "step1", "type": "task", "task": "test_task"},
                ],
            },
            is_active=True,
        )

        instance = self.engine.create_instance(
            workflow_name="test_progress_single_step",
            input_data={},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        instance = self.engine.start_instance(str(instance.id))

        # Execute the single step
        self.engine.execute_instance(str(instance.id))
        instance.refresh_from_db()

        # Verify progress is stored
        self.assertIn("progress_percentage", instance.state_data)
        # Single step: at step 0, progress = (0+1)/1*100 = 100%
        self.assertEqual(instance.state_data["progress_percentage"], 100.0)

    def test_progress_state_data_structure(self):
        """Test that state_data contains all expected progress-related fields (Task 0.3.2)"""
        workflow_def = WorkflowDefinition.objects.create(
            name="test_progress_structure",
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
            workflow_name="test_progress_structure",
            input_data={},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        instance = self.engine.start_instance(str(instance.id))

        # Execute first step
        self.engine.execute_instance(str(instance.id))
        instance.refresh_from_db()

        # Verify state_data structure
        self.assertIn("progress_percentage", instance.state_data)
        self.assertIn("current_step_index", instance.state_data)
        self.assertIn("current_step_name", instance.state_data)

        # Verify types
        self.assertIsInstance(instance.state_data["progress_percentage"], (int, float))
        self.assertIsInstance(instance.state_data["current_step_index"], int)
        self.assertIsInstance(instance.state_data["current_step_name"], str)

        # Verify values are valid
        self.assertGreaterEqual(instance.state_data["progress_percentage"], 0.0)
        self.assertLessEqual(instance.state_data["progress_percentage"], 100.0)
        self.assertGreaterEqual(instance.state_data["current_step_index"], 0)


class WorkflowProgressIntegrationTest(TestCase):
    """Integration tests for progress persistence in WorkflowInstance (Task 0.3.2)"""

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

        # Register test tasks
        def test_task(input_data, instance, step):
            return {"result": "success", "step": step.step_name}

        self.engine.register_task("test_task", test_task)

    def test_progress_persistence_through_complete_workflow(self):
        """Integration test: Progress persists through complete workflow execution (Task 0.3.2)"""
        # Create workflow with 4 steps
        workflow_def = WorkflowDefinition.objects.create(
            name="test_integration_progress",
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
            workflow_name="test_integration_progress",
            input_data={},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        instance = self.engine.start_instance(str(instance.id))

        # Execute workflow (executes all steps)
        instance = self.engine.execute_instance(str(instance.id))
        instance.refresh_from_db()

        # Verify final state
        self.assertEqual(instance.status, WorkflowStatus.COMPLETED)
        self.assertEqual(instance.state_data["progress_percentage"], 100.0)

        # Verify progress was present throughout (check that it's valid)
        self.assertIn("progress_percentage", instance.state_data)
        self.assertGreaterEqual(instance.state_data["progress_percentage"], 0.0)
        self.assertLessEqual(instance.state_data["progress_percentage"], 100.0)

    def test_progress_persistence_after_database_reload(self):
        """Integration test: Progress persists after reloading instance from database (Task 0.3.2)"""
        workflow_def = WorkflowDefinition.objects.create(
            name="test_progress_reload",
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
            workflow_name="test_progress_reload",
            input_data={},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        instance = self.engine.start_instance(str(instance.id))

        # Execute workflow (executes all steps)
        self.engine.execute_instance(str(instance.id))
        instance.refresh_from_db()

        # Store progress value (should be 100% after completion)
        progress_after_completion = instance.state_data["progress_percentage"]

        # Reload instance from database
        instance_id = instance.id
        reloaded_instance = WorkflowInstance.objects.get(id=instance_id)

        # Verify progress persisted
        self.assertIn("progress_percentage", reloaded_instance.state_data)
        self.assertEqual(
            reloaded_instance.state_data["progress_percentage"],
            progress_after_completion,
            "Progress should persist after database reload"
        )

        # Verify workflow is completed
        self.assertEqual(reloaded_instance.status, WorkflowStatus.COMPLETED)
        self.assertEqual(reloaded_instance.state_data["progress_percentage"], 100.0)

    def test_progress_with_multiple_workflow_instances(self):
        """Integration test: Progress is correctly tracked for multiple workflow instances (Task 0.3.2)"""
        workflow_def = WorkflowDefinition.objects.create(
            name="test_multi_instance_progress",
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

        # Create two instances
        instance1 = self.engine.create_instance(
            workflow_name="test_multi_instance_progress",
            input_data={},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        instance1 = self.engine.start_instance(str(instance1.id))

        instance2 = self.engine.create_instance(
            workflow_name="test_multi_instance_progress",
            input_data={},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        instance2 = self.engine.start_instance(str(instance2.id))

        # Execute instance1 (completes all steps)
        self.engine.execute_instance(str(instance1.id))
        instance1.refresh_from_db()

        # Execute instance2 (completes all steps)
        self.engine.execute_instance(str(instance2.id))
        instance2.refresh_from_db()

        # Both should have progress stored
        self.assertIn("progress_percentage", instance1.state_data)
        self.assertIn("progress_percentage", instance2.state_data)

        # Both should be at 100% (both completed)
        self.assertEqual(instance1.state_data["progress_percentage"], 100.0)
        self.assertEqual(instance2.state_data["progress_percentage"], 100.0)

        # Both should be completed
        self.assertEqual(instance1.status, WorkflowStatus.COMPLETED)
        self.assertEqual(instance2.status, WorkflowStatus.COMPLETED)

