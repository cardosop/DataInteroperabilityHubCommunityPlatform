"""
Integration tests for workflow execution.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.orchestration.models import (
    StepStatus,
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStatus,
)
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.tenants.models import KYCStatus, Tenant

pytestmark = pytest.mark.django_db(transaction=True)

User = get_user_model()


class WorkflowIntegrationTest(TestCase):
    """Integration tests for workflow execution"""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", status="ACTIVE", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass", tenant=self.tenant
        )
        self.engine = WorkflowEngine()
        self.registry = WorkflowRegistry()

        # Register a test task
        def test_task(input_data, instance, step):
            return {"result": "success", "input": input_data}

        self.engine.register_task("test_task", test_task)

    def test_complete_workflow_execution(self):
        """Test complete workflow execution flow"""
        # Register workflow
        dsl_json = {
            "version": "1.0.0",
            "steps": [
                {"name": "step1", "type": "task", "task": "test_task"},
                {"name": "step2", "type": "task", "task": "test_task"},
            ],
        }

        workflow_def = self.registry.register_workflow(
            workflow_name="test_workflow", dsl_json=dsl_json
        )

        # Create workflow instance
        instance = self.engine.create_instance(
            workflow_name="test_workflow",
            input_data={"key": "value"},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )

        self.assertEqual(instance.status, WorkflowStatus.DRAFT)
        self.assertEqual(instance.workflow_name, "test_workflow")

        # Start workflow
        instance = self.engine.start_instance(str(instance.id))
        self.assertEqual(instance.status, WorkflowStatus.RUNNING)

        # Execute workflow
        instance = self.engine.execute_instance(str(instance.id))

        # Check workflow completed
        self.assertEqual(instance.status, WorkflowStatus.COMPLETED)
        self.assertIsNotNone(instance.completed_at)

        # Check steps completed
        steps = instance.steps.all()
        self.assertEqual(len(steps), 2)
        for step in steps:
            self.assertEqual(step.status, StepStatus.COMPLETED)

    def test_workflow_with_failure(self):
        """Test workflow execution with step failure"""

        # Register a failing task
        def failing_task(input_data, instance, step):
            raise Exception("Task failed")

        self.engine.register_task("failing_task", failing_task)

        # Register workflow
        dsl_json = {
            "version": "1.0.0",
            "steps": [
                {"name": "step1", "type": "task", "task": "test_task"},
                {"name": "step2", "type": "task", "task": "failing_task"},
            ],
        }

        self.registry.register_workflow(workflow_name="failing_workflow", dsl_json=dsl_json)

        # Create and execute workflow
        instance = self.engine.create_instance(workflow_name="failing_workflow", input_data={})
        instance = self.engine.start_instance(str(instance.id))

        # Execute workflow (should fail)
        instance = self.engine.execute_instance(str(instance.id))

        # Check workflow failed
        self.assertEqual(instance.status, WorkflowStatus.FAILED)
        self.assertIsNotNone(instance.error_message)

        # Check step failed
        failed_step = instance.steps.get(step_index=1)
        self.assertEqual(failed_step.status, StepStatus.FAILED)


class WorkflowIntegrationEdgeCasesTest(TestCase):
    """Integration tests for workflow execution edge cases"""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", status="ACTIVE", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass", tenant=self.tenant
        )
        self.engine = WorkflowEngine()
        self.registry = WorkflowRegistry()

        def test_task(input_data, instance, step):
            return {"result": "success", "input": input_data}

        self.engine.register_task("test_task", test_task)

    def test_workflow_with_empty_input_data(self):
        """Test workflow execution with empty input_data"""
        dsl_json = {
            "version": "1.0.0",
            "steps": [{"name": "step1", "type": "task", "task": "test_task"}],
        }

        self.registry.register_workflow(workflow_name="empty_input_workflow", dsl_json=dsl_json)

        instance = self.engine.create_instance(
            workflow_name="empty_input_workflow",
            input_data={},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )

        instance = self.engine.start_instance(str(instance.id))
        instance = self.engine.execute_instance(str(instance.id))

        self.assertEqual(instance.status, WorkflowStatus.COMPLETED)

    def test_workflow_with_many_steps(self):
        """Test workflow execution with many steps"""
        dsl_json = {
            "version": "1.0.0",
            "steps": [{"name": f"step{i}", "type": "task", "task": "test_task"} for i in range(50)],
        }

        self.registry.register_workflow(workflow_name="many_steps_workflow", dsl_json=dsl_json)

        instance = self.engine.create_instance(
            workflow_name="many_steps_workflow",
            input_data={"key": "value"},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )

        instance = self.engine.start_instance(str(instance.id))
        instance = self.engine.execute_instance(str(instance.id))

        self.assertEqual(instance.status, WorkflowStatus.COMPLETED)
        self.assertEqual(instance.steps.count(), 50)


class WorkflowIntegrationErrorHandlingTest(TestCase):
    """Integration tests for workflow execution error handling"""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", status="ACTIVE", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass", tenant=self.tenant
        )
        self.engine = WorkflowEngine()
        self.registry = WorkflowRegistry()

    def test_workflow_with_nonexistent_task(self):
        """Test workflow execution with nonexistent task"""
        dsl_json = {
            "version": "1.0.0",
            "steps": [{"name": "step1", "type": "task", "task": "nonexistent_task"}],
        }

        self.registry.register_workflow(
            workflow_name="nonexistent_task_workflow", dsl_json=dsl_json
        )

        instance = self.engine.create_instance(
            workflow_name="nonexistent_task_workflow",
            input_data={},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )

        instance = self.engine.start_instance(str(instance.id))

        # Execute workflow (should fail due to nonexistent task)
        instance = self.engine.execute_instance(str(instance.id))

        # Workflow should fail
        self.assertEqual(instance.status, WorkflowStatus.FAILED)
        self.assertIsNotNone(instance.error_message)

    def test_workflow_with_invalid_dsl(self):
        """Test workflow registration with invalid DSL (empty steps)."""
        invalid_dsl = {"version": "1.0.0", "steps": []}

        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            self.registry.register_workflow(
                workflow_name="invalid_dsl_workflow", dsl_json=invalid_dsl
            )
