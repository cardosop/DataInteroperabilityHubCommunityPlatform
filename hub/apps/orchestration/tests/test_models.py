"""
Unit tests for workflow models.
"""

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from hub.apps.orchestration.models import (
    StepStatus,
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStatus,
    WorkflowStep,
)
from hub.apps.tenants.models import KYCStatus, Tenant
import uuid

pytestmark = pytest.mark.django_db(transaction=True)

User = get_user_model()


class WorkflowDefinitionTest(TestCase):
    """Test WorkflowDefinition model"""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", status="ACTIVE", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass", tenant=self.tenant
        )
        self.valid_dsl = {
            "version": "1.0.0",
            "steps": [{"name": "step1", "type": "task", "task": "test_task"}],
        }

    def test_create_workflow_definition(self):
        """Test creating workflow definition"""
        workflow_def = WorkflowDefinition.objects.create(
            name="test_workflow", version="1.0.0", dsl_json=self.valid_dsl, created_by=self.user
        )

        self.assertEqual(workflow_def.name, "test_workflow")
        self.assertEqual(workflow_def.version, "1.0.0")
        self.assertEqual(workflow_def.dsl_json, self.valid_dsl)

    def test_workflow_definition_unique_name_version(self):
        """Test unique constraint on name+version"""
        WorkflowDefinition.objects.create(
            name="test_workflow", version="1.0.0", dsl_json=self.valid_dsl
        )

        with self.assertRaises(Exception):  # IntegrityError or ValidationError
            WorkflowDefinition.objects.create(
                name="test_workflow", version="1.0.0", dsl_json=self.valid_dsl
            )

    def test_workflow_definition_clean_valid(self):
        """Test clean() with valid DSL"""
        workflow_def = WorkflowDefinition(
            name="test_workflow", version="1.0.0", dsl_json=self.valid_dsl
        )
        workflow_def.clean()  # Should not raise

    def test_workflow_definition_clean_invalid_dsl(self):
        """Test clean() with invalid DSL"""
        workflow_def = WorkflowDefinition(
            name="test_workflow", version="1.0.0", dsl_json={"invalid": "dsl"}
        )

        with self.assertRaises(ValidationError):
            workflow_def.clean()

    def test_workflow_definition_str(self):
        """Test __str__ method"""
        workflow_def = WorkflowDefinition.objects.create(
            name="test_workflow", version="1.0.0", dsl_json=self.valid_dsl
        )

        self.assertEqual(str(workflow_def), "test_workflow v1.0.0")


class WorkflowInstanceTest(TestCase):
    """Test WorkflowInstance model"""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", status="ACTIVE", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass", tenant=self.tenant
        )
        self.workflow_def = WorkflowDefinition.objects.create(
            name="test_workflow",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [{"name": "step1", "type": "task", "task": "test_task"}],
            },
        )

    def test_create_workflow_instance(self):
        """Test creating workflow instance"""
        instance = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
            workflow_version="1.0.0",
            tenant=self.tenant,
            input_data={"key": "value"},
            created_by=self.user,
        )

        self.assertEqual(instance.workflow_name, "test_workflow")
        self.assertEqual(instance.status, WorkflowStatus.DRAFT)
        self.assertEqual(instance.input_data, {"key": "value"})

    def test_workflow_instance_is_terminal(self):
        """Test is_terminal() method"""
        instance = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
            workflow_version="1.0.0",
        )

        self.assertFalse(instance.is_terminal())

        instance.status = WorkflowStatus.COMPLETED
        self.assertTrue(instance.is_terminal())

        instance.status = WorkflowStatus.FAILED
        self.assertTrue(instance.is_terminal())

    def test_workflow_instance_is_running(self):
        """Test is_running() method"""
        instance = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
            workflow_version="1.0.0",
        )

        self.assertFalse(instance.is_running())

        instance.status = WorkflowStatus.RUNNING
        self.assertTrue(instance.is_running())

    def test_workflow_instance_can_retry(self):
        """Test can_retry() method"""
        instance = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
            workflow_version="1.0.0",
            status=WorkflowStatus.FAILED,
            retry_count=0,
            max_retries=3,
        )

        self.assertTrue(instance.can_retry())

        instance.retry_count = 3
        self.assertFalse(instance.can_retry())

        instance.status = WorkflowStatus.COMPLETED
        self.assertFalse(instance.can_retry())

    def test_workflow_instance_mark_started(self):
        """Test mark_started() method"""
        instance = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
            workflow_version="1.0.0",
        )

        instance.mark_started()

        self.assertEqual(instance.status, WorkflowStatus.RUNNING)
        self.assertIsNotNone(instance.started_at)

    def test_workflow_instance_mark_completed(self):
        """Test mark_completed() method"""
        instance = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
            workflow_version="1.0.0",
            status=WorkflowStatus.RUNNING,
        )

        output_data = {"result": "success"}
        instance.mark_completed(output_data=output_data)

        self.assertEqual(instance.status, WorkflowStatus.COMPLETED)
        self.assertEqual(instance.output_data, output_data)
        self.assertIsNotNone(instance.completed_at)

    def test_workflow_instance_mark_failed(self):
        """Test mark_failed() method"""
        instance = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
            workflow_version="1.0.0",
            status=WorkflowStatus.RUNNING,
        )

        error_message = "Test error"
        error_details = {"error_code": "TEST_ERROR"}
        instance.mark_failed(error_message, error_details)

        self.assertEqual(instance.status, WorkflowStatus.FAILED)
        self.assertEqual(instance.error_message, error_message)
        self.assertEqual(instance.error_details, error_details)
        self.assertIsNotNone(instance.completed_at)

    def test_workflow_instance_str(self):
        """Test __str__ method"""
        instance = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
            workflow_version="1.0.0",
        )

        self.assertIn("test_workflow", str(instance))
        self.assertIn("DRAFT", str(instance))


class WorkflowStepTest(TestCase):
    """Test WorkflowStep model"""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", status="ACTIVE", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass", tenant=self.tenant
        )
        self.workflow_def = WorkflowDefinition.objects.create(
            name="test_workflow",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [{"name": "step1", "type": "task", "task": "test_task"}],
            },
        )
        self.instance = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
            workflow_version="1.0.0",
        )

    def test_create_workflow_step(self):
        """Test creating workflow step"""
        step = WorkflowStep.objects.create(
            workflow_instance=self.instance,
            step_index=0,
            step_name="step1",
            step_type="task",
            input_data={"key": "value"},
        )

        self.assertEqual(step.step_name, "step1")
        self.assertEqual(step.status, StepStatus.PENDING)
        self.assertEqual(step.input_data, {"key": "value"})

    def test_workflow_step_is_terminal(self):
        """Test is_terminal() method"""
        step = WorkflowStep.objects.create(
            workflow_instance=self.instance, step_index=0, step_name="step1", step_type="task"
        )

        self.assertFalse(step.is_terminal())

        step.status = StepStatus.COMPLETED
        self.assertTrue(step.is_terminal())

        step.status = StepStatus.FAILED
        self.assertTrue(step.is_terminal())

    def test_workflow_step_mark_started(self):
        """Test mark_started() method"""
        step = WorkflowStep.objects.create(
            workflow_instance=self.instance, step_index=0, step_name="step1", step_type="task"
        )

        step.mark_started()

        self.assertEqual(step.status, StepStatus.RUNNING)
        self.assertIsNotNone(step.started_at)

    def test_workflow_step_mark_completed(self):
        """Test mark_completed() method"""
        step = WorkflowStep.objects.create(
            workflow_instance=self.instance,
            step_index=0,
            step_name="step1",
            step_type="task",
            status=StepStatus.RUNNING,
        )

        output_data = {"result": "success"}
        step.mark_completed(output_data=output_data)

        self.assertEqual(step.status, StepStatus.COMPLETED)
        self.assertEqual(step.output_data, output_data)
        self.assertIsNotNone(step.completed_at)

    def test_workflow_step_mark_failed(self):
        """Test mark_failed() method"""
        step = WorkflowStep.objects.create(
            workflow_instance=self.instance,
            step_index=0,
            step_name="step1",
            step_type="task",
            status=StepStatus.RUNNING,
        )

        error_message = "Test error"
        error_details = {"error_code": "TEST_ERROR"}
        step.mark_failed(error_message, error_details)

        self.assertEqual(step.status, StepStatus.FAILED)
        self.assertEqual(step.error_message, error_message)
        self.assertEqual(step.error_details, error_details)
        self.assertIsNotNone(step.completed_at)

    def test_workflow_step_mark_compensated(self):
        """Test mark_compensated() method"""
        step = WorkflowStep.objects.create(
            workflow_instance=self.instance,
            step_index=0,
            step_name="step1",
            step_type="task",
            status=StepStatus.COMPLETED,
        )

        compensation_data = {"status": "compensated"}
        step.mark_compensated(compensation_data=compensation_data)

        self.assertEqual(step.status, StepStatus.COMPENSATED)
        self.assertEqual(step.compensation_data, compensation_data)

    def test_workflow_step_str(self):
        """Test __str__ method"""
        step = WorkflowStep.objects.create(
            workflow_instance=self.instance, step_index=0, step_name="step1", step_type="task"
        )

        self.assertIn("step1", str(step))
        self.assertIn("PENDING", str(step))


class WorkflowDefinitionFailureTest(TestCase):
    """Test WorkflowDefinition model failure scenarios"""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", status="ACTIVE", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass", tenant=self.tenant
        )

    def test_workflow_definition_clean_with_malformed_dsl(self):
        """Test clean() raises ValidationError with malformed DSL"""
        workflow_def = WorkflowDefinition(
            name="test_workflow", version="1.0.0", dsl_json={"malformed": True, "invalid": None}
        )

        with self.assertRaises(ValidationError):
            workflow_def.clean()

    def test_workflow_definition_clean_with_missing_required_fields(self):
        """Test clean() raises ValidationError when required DSL fields are missing"""
        workflow_def = WorkflowDefinition(
            name="test_workflow", version="1.0.0", dsl_json={"steps": []}  # Missing version in DSL
        )

        with self.assertRaises(ValidationError):
            workflow_def.clean()


class WorkflowDefinitionEdgeCasesTest(TestCase):
    """Test WorkflowDefinition model edge cases"""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", status="ACTIVE", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass", tenant=self.tenant
        )

    def test_workflow_definition_with_empty_name(self):
        """Test workflow definition with empty name"""
        workflow_def = WorkflowDefinition(
            name="",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [{"name": "step1", "type": "task", "task": "test_task"}],
            },
        )
        # Empty name should be allowed (may be validated elsewhere)
        workflow_def.clean()

    def test_workflow_definition_with_very_long_name(self):
        """Test workflow definition with very long name"""
        long_name = "a" * 500
        workflow_def = WorkflowDefinition(
            name=long_name,
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [{"name": "step1", "type": "task", "task": "test_task"}],
            },
        )
        # Very long name should be handled (may be truncated or validated elsewhere)
        workflow_def.clean()


class WorkflowInstanceFailureTest(TestCase):
    """Test WorkflowInstance model failure scenarios"""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", status="ACTIVE", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass", tenant=self.tenant
        )
        self.workflow_def = WorkflowDefinition.objects.create(
            name="test_workflow",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [{"name": "step1", "type": "task", "task": "test_task"}],
            },
        )

    def test_workflow_instance_mark_completed_from_wrong_status(self):
        """Test mark_completed() from non-running status"""
        instance = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
            workflow_version="1.0.0",
            status=WorkflowStatus.DRAFT,
        )

        # mark_completed should handle non-running status gracefully
        instance.mark_completed(output_data={"result": "success"})
        self.assertEqual(instance.status, WorkflowStatus.COMPLETED)

    def test_workflow_instance_mark_failed_with_empty_error_message(self):
        """Test mark_failed() with empty error message"""
        instance = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
            workflow_version="1.0.0",
            status=WorkflowStatus.RUNNING,
        )

        instance.mark_failed("", {})
        self.assertEqual(instance.status, WorkflowStatus.FAILED)
        self.assertEqual(instance.error_message, "")


class WorkflowInstanceEdgeCasesTest(TestCase):
    """Test WorkflowInstance model edge cases"""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", status="ACTIVE", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass", tenant=self.tenant
        )
        self.workflow_def = WorkflowDefinition.objects.create(
            name="test_workflow",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [{"name": "step1", "type": "task", "task": "test_task"}],
            },
        )

    def test_workflow_instance_with_empty_input_data(self):
        """Test workflow instance with empty input_data"""
        instance = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
            workflow_version="1.0.0",
            input_data={},
        )

        self.assertEqual(instance.input_data, {})

    def test_workflow_instance_with_large_input_data(self):
        """Test workflow instance with very large input_data"""
        large_data = {"key" + str(i): "value" * 1000 for i in range(100)}
        instance = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
            workflow_version="1.0.0",
            input_data=large_data,
        )

        self.assertEqual(len(instance.input_data), 100)


class WorkflowStepFailureTest(TestCase):
    """Test WorkflowStep model failure scenarios"""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", status="ACTIVE", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass", tenant=self.tenant
        )
        self.workflow_def = WorkflowDefinition.objects.create(
            name="test_workflow",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [{"name": "step1", "type": "task", "task": "test_task"}],
            },
        )
        self.instance = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
            workflow_version="1.0.0",
        )

    def test_workflow_step_mark_completed_from_wrong_status(self):
        """Test mark_completed() from non-running status"""
        step = WorkflowStep.objects.create(
            workflow_instance=self.instance,
            step_index=0,
            step_name="step1",
            step_type="task",
            status=StepStatus.PENDING,
        )

        # mark_completed should handle non-running status gracefully
        step.mark_completed(output_data={"result": "success"})
        self.assertEqual(step.status, StepStatus.COMPLETED)

    def test_workflow_step_mark_failed_with_empty_error_message(self):
        """Test mark_failed() with empty error message"""
        step = WorkflowStep.objects.create(
            workflow_instance=self.instance,
            step_index=0,
            step_name="step1",
            step_type="task",
            status=StepStatus.RUNNING,
        )

        step.mark_failed("", {})
        self.assertEqual(step.status, StepStatus.FAILED)
        self.assertEqual(step.error_message, "")


class WorkflowStepEdgeCasesTest(TestCase):
    """Test WorkflowStep model edge cases"""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", status="ACTIVE", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass", tenant=self.tenant
        )
        self.workflow_def = WorkflowDefinition.objects.create(
            name="test_workflow",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [{"name": "step1", "type": "task", "task": "test_task"}],
            },
        )
        self.instance = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
            workflow_version="1.0.0",
        )

    def test_workflow_step_with_empty_input_data(self):
        """Test workflow step with empty input_data"""
        step = WorkflowStep.objects.create(
            workflow_instance=self.instance,
            step_index=0,
            step_name="step1",
            step_type="task",
            input_data={},
        )

        self.assertEqual(step.input_data, {})

    def test_workflow_step_with_large_output_data(self):
        """Test workflow step with very large output_data"""
        large_data = {"key" + str(i): "value" * 1000 for i in range(100)}
        step = WorkflowStep.objects.create(
            workflow_instance=self.instance,
            step_index=0,
            step_name="step1",
            step_type="task",
            status=StepStatus.RUNNING,
        )

        step.mark_completed(output_data=large_data)
        self.assertEqual(len(step.output_data), 100)
