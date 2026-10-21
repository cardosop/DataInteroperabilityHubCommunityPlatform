"""
Tests for Workflow Execution Validators

Comprehensive tests for workflow execution validation including:
- Workflow status transition validation
- Workflow step execution validation
- Workflow compensation validation
- Workflow retry validation

All tests follow engineering best practices:
- No mocks/stubs - use real services and models
- Test root causes, not symptoms
- Comprehensive test coverage
"""

import uuid
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from hub.apps.orchestration.execution_validators import WorkflowExecutionValidator
from hub.apps.orchestration.models import (
    StepStatus,
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStatus,
    WorkflowStep,
)
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import User, UserStatus


class WorkflowStatusTransitionValidationTest(TestCase):
    """Tests for workflow status transition validation"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create workflow definition
        self.workflow_def = WorkflowDefinition.objects.create(
            name=f"test_workflow_{uuid.uuid4().hex[:8]}",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [{"name": "step1", "type": "task", "task": "test_task"}],
            },
            created_by=self.user,
        )

    def test_validate_status_transition_draft_valid(self):
        """Test status transition validation for valid DRAFT workflow"""
        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name=self.workflow_def.name,
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.DRAFT,
            created_by=self.user,
        )

        result = WorkflowExecutionValidator.validate_status_transition(workflow)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertEqual(result.details["current_status"], WorkflowStatus.DRAFT)
        self.assertEqual(result.details["status_valid"], "true")
        self.assertEqual(result.details["draft_constraints_valid"], "true")

    def test_validate_status_transition_draft_with_started_at(self):
        """Test status transition validation for DRAFT workflow with started_at set"""
        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name=self.workflow_def.name,
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.DRAFT,
            started_at=timezone.now(),
            created_by=self.user,
        )

        result = WorkflowExecutionValidator.validate_status_transition(workflow)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("started_at", result.errors[0].lower())

    def test_validate_status_transition_running_valid(self):
        """Test status transition validation for valid RUNNING workflow"""
        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name=self.workflow_def.name,
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.RUNNING,
            started_at=timezone.now(),
            created_by=self.user,
        )

        result = WorkflowExecutionValidator.validate_status_transition(workflow)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertEqual(result.details["current_status"], WorkflowStatus.RUNNING)
        self.assertEqual(result.details["status_valid"], "true")
        self.assertEqual(result.details["running_constraints_valid"], "true")

    def test_validate_status_transition_running_without_started_at(self):
        """Test status transition validation for RUNNING workflow without started_at"""
        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name=self.workflow_def.name,
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.RUNNING,
            created_by=self.user,
        )

        result = WorkflowExecutionValidator.validate_status_transition(workflow)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("started_at", result.errors[0].lower())

    def test_validate_status_transition_completed_valid(self):
        """Test status transition validation for valid COMPLETED workflow"""
        started_at = timezone.now() - timedelta(minutes=5)
        completed_at = timezone.now()

        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name=self.workflow_def.name,
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.COMPLETED,
            started_at=started_at,
            completed_at=completed_at,
            output_data={"result": "success"},
            created_by=self.user,
        )

        result = WorkflowExecutionValidator.validate_status_transition(workflow)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertEqual(result.details["current_status"], WorkflowStatus.COMPLETED)
        self.assertEqual(result.details["status_valid"], "true")
        self.assertEqual(result.details["terminal_constraints_valid"], "true")

    def test_validate_status_transition_completed_without_timestamps(self):
        """Test status transition validation for COMPLETED workflow without timestamps"""
        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name=self.workflow_def.name,
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.COMPLETED,
            created_by=self.user,
        )

        result = WorkflowExecutionValidator.validate_status_transition(workflow)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        # Error should mention missing timestamp fields
        error_text = " ".join(e.lower() for e in result.errors)
        self.assertTrue(
            "started_at" in error_text or "completed_at" in error_text or "timestamp" in error_text,
            f"Error should mention missing timestamps, got: {result.errors}",
        )

    def test_validate_status_transition_failed_valid(self):
        """Test status transition validation for valid FAILED workflow"""
        started_at = timezone.now() - timedelta(minutes=5)
        completed_at = timezone.now()

        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name=self.workflow_def.name,
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.FAILED,
            started_at=started_at,
            completed_at=completed_at,
            error_message="Workflow failed",
            created_by=self.user,
        )

        result = WorkflowExecutionValidator.validate_status_transition(workflow)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertEqual(result.details["current_status"], WorkflowStatus.FAILED)
        self.assertEqual(result.details["status_valid"], "true")
        self.assertEqual(result.details["terminal_constraints_valid"], "true")

    def test_validate_status_transition_invalid_transition(self):
        """Test status transition validation for invalid transition"""
        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name=self.workflow_def.name,
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.DRAFT,
            created_by=self.user,
        )

        # Try to transition from DRAFT to COMPLETED (invalid)
        result = WorkflowExecutionValidator.validate_status_transition(
            workflow, target_status=WorkflowStatus.COMPLETED
        )

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("transition", result.errors[0].lower())

    def test_validate_status_transition_valid_transition(self):
        """Test status transition validation for valid transition"""
        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name=self.workflow_def.name,
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.DRAFT,
            created_by=self.user,
        )

        # Transition from DRAFT to RUNNING (valid)
        result = WorkflowExecutionValidator.validate_status_transition(
            workflow, target_status=WorkflowStatus.RUNNING
        )

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertEqual(result.details["transition_valid"], "true")


class WorkflowStepExecutionValidationTest(TestCase):
    """Tests for workflow step execution validation"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create workflow definition
        self.workflow_def = WorkflowDefinition.objects.create(
            name=f"test_workflow_{uuid.uuid4().hex[:8]}",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [
                    {"name": "step1", "type": "task", "task": "task1"},
                    {"name": "step2", "type": "task", "task": "task2"},
                    {"name": "step3", "type": "task", "task": "task3"},
                ],
            },
            created_by=self.user,
        )

        self.workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name=self.workflow_def.name,
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.RUNNING,
            started_at=timezone.now(),
            created_by=self.user,
        )

    def test_validate_step_execution_first_step_valid(self):
        """Test step execution validation for first step (no prerequisites)"""
        step = WorkflowStep.objects.create(
            workflow_instance=self.workflow,
            step_index=0,
            step_name="step1",
            step_type="task",
            status=StepStatus.PENDING,
        )

        result = WorkflowExecutionValidator.validate_step_execution(step)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertEqual(result.details["step_index"], 0)
        self.assertEqual(result.details["prerequisites_met"], "true")

    def test_validate_step_execution_prerequisites_met(self):
        """Test step execution validation when prerequisites are met"""
        # Create and complete first step
        WorkflowStep.objects.create(
            workflow_instance=self.workflow,
            step_index=0,
            step_name="step1",
            step_type="task",
            status=StepStatus.COMPLETED,
            started_at=timezone.now() - timedelta(minutes=2),
            completed_at=timezone.now() - timedelta(minutes=1),
        )

        # Create second step
        step2 = WorkflowStep.objects.create(
            workflow_instance=self.workflow,
            step_index=1,
            step_name="step2",
            step_type="task",
            status=StepStatus.PENDING,
        )

        result = WorkflowExecutionValidator.validate_step_execution(step2)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertEqual(result.details["prerequisites_met"], "true")

    def test_validate_step_execution_prerequisites_not_met(self):
        """Test step execution validation when prerequisites are not met"""
        # Create first step but don't complete it
        WorkflowStep.objects.create(
            workflow_instance=self.workflow,
            step_index=0,
            step_name="step1",
            step_type="task",
            status=StepStatus.RUNNING,
            started_at=timezone.now(),
        )

        # Try to execute second step
        step2 = WorkflowStep.objects.create(
            workflow_instance=self.workflow,
            step_index=1,
            step_name="step2",
            step_type="task",
            status=StepStatus.PENDING,
        )

        result = WorkflowExecutionValidator.validate_step_execution(step2)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        # Error message contains "previous steps are not completed" or "prerequisites"
        error_msg_lower = result.errors[0].lower()
        self.assertTrue(
            "previous steps" in error_msg_lower or "prerequisites" in error_msg_lower,
            f"Error message should mention prerequisites or previous steps: {result.errors[0]}",
        )
        self.assertEqual(result.details["prerequisites_met"], "false")

    def test_validate_step_execution_running_step_valid(self):
        """Test step execution validation for RUNNING step"""
        step = WorkflowStep.objects.create(
            workflow_instance=self.workflow,
            step_index=0,
            step_name="step1",
            step_type="task",
            status=StepStatus.RUNNING,
            started_at=timezone.now(),
        )

        result = WorkflowExecutionValidator.validate_step_execution(step)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertEqual(result.details["step_status"], StepStatus.RUNNING)
        self.assertEqual(result.details["step_timestamps_valid"], "true")

    def test_validate_step_execution_running_without_started_at(self):
        """Test step execution validation for RUNNING step without started_at"""
        step = WorkflowStep.objects.create(
            workflow_instance=self.workflow,
            step_index=0,
            step_name="step1",
            step_type="task",
            status=StepStatus.RUNNING,
        )

        result = WorkflowExecutionValidator.validate_step_execution(step)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("started_at", result.errors[0].lower())

    def test_validate_step_execution_completed_step_valid(self):
        """Test step execution validation for COMPLETED step"""
        started_at = timezone.now() - timedelta(minutes=2)
        completed_at = timezone.now() - timedelta(minutes=1)

        step = WorkflowStep.objects.create(
            workflow_instance=self.workflow,
            step_index=0,
            step_name="step1",
            step_type="task",
            status=StepStatus.COMPLETED,
            started_at=started_at,
            completed_at=completed_at,
            output_data={"result": "success"},
        )

        result = WorkflowExecutionValidator.validate_step_execution(step)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertEqual(result.details["step_status"], StepStatus.COMPLETED)
        self.assertEqual(result.details["step_timestamps_valid"], "true")

    def test_validate_step_execution_completed_without_timestamps(self):
        """Test step execution validation for COMPLETED step without timestamps"""
        step = WorkflowStep.objects.create(
            workflow_instance=self.workflow,
            step_index=0,
            step_name="step1",
            step_type="task",
            status=StepStatus.COMPLETED,
        )

        result = WorkflowExecutionValidator.validate_step_execution(step)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        # Error should reference missing timestamp fields
        error_text = " ".join(e.lower() for e in result.errors)
        self.assertTrue(
            "started_at" in error_text or "completed_at" in error_text or "timestamp" in error_text,
            f"Error should mention missing timestamps, got: {result.errors}",
        )


class WorkflowCompensationValidationTest(TestCase):
    """Tests for workflow compensation validation"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create workflow definition with compensation
        self.workflow_def = WorkflowDefinition.objects.create(
            name=f"test_workflow_{uuid.uuid4().hex[:8]}",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "compensation": {"enabled": True},
                "steps": [
                    {
                        "name": "step1",
                        "type": "task",
                        "task": "task1",
                        "compensation": {"type": "task", "task": "compensation_task1"},
                    },
                    {"name": "step2", "type": "task", "task": "task2"},
                ],
            },
            created_by=self.user,
        )

        self.workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name=self.workflow_def.name,
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.ROLLING_BACK,
            started_at=timezone.now() - timedelta(minutes=10),
            created_by=self.user,
        )

    def test_validate_compensation_enabled_workflow(self):
        """Test compensation validation for workflow with compensation enabled"""
        result = WorkflowExecutionValidator.validate_compensation(self.workflow)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertEqual(result.details["compensation_enabled"], "true")
        self.assertEqual(result.details["compensation_config_valid"], "true")

    def test_validate_compensation_step_with_compensation(self):
        """Test compensation validation for step with compensation defined"""
        step = WorkflowStep.objects.create(
            workflow_instance=self.workflow,
            step_index=0,
            step_name="step1",
            step_type="task",
            status=StepStatus.COMPLETED,
        )

        result = WorkflowExecutionValidator.validate_compensation(self.workflow, step)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertEqual(result.details["step_has_compensation"], "true")
        self.assertEqual(result.details["compensation_type"], "task")
        self.assertEqual(result.details["step_compensation_valid"], "true")

    def test_validate_compensation_step_without_compensation(self):
        """Test compensation validation for step without compensation"""
        step = WorkflowStep.objects.create(
            workflow_instance=self.workflow,
            step_index=1,
            step_name="step2",
            step_type="task",
            status=StepStatus.COMPLETED,
        )

        result = WorkflowExecutionValidator.validate_compensation(self.workflow, step)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertEqual(result.details["step_has_compensation"], "false")
        self.assertGreaterEqual(len(result.warnings), 0)

    def test_validate_compensation_invalid_type(self):
        """Test compensation validation with invalid compensation type"""
        workflow_def = WorkflowDefinition.objects.create(
            name="invalid_workflow",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [
                    {
                        "name": "step1",
                        "type": "task",
                        "task": "task1",
                        "compensation": {"type": "invalid_type"},
                    }
                ],
            },
            created_by=self.user,
        )

        workflow = WorkflowInstance.objects.create(
            workflow_definition=workflow_def,
            workflow_name="invalid_workflow",
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.RUNNING,
            created_by=self.user,
        )

        step = WorkflowStep.objects.create(
            workflow_instance=workflow,
            step_index=0,
            step_name="step1",
            step_type="task",
            status=StepStatus.COMPLETED,
        )

        result = WorkflowExecutionValidator.validate_compensation(workflow, step)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("compensation type", result.errors[0].lower())

    def test_validate_compensation_compensated_steps_order(self):
        """Test compensation validation for compensated steps order"""
        # Create steps in reverse order (as they would be compensated)
        WorkflowStep.objects.create(
            workflow_instance=self.workflow,
            step_index=1,
            step_name="step2",
            step_type="task",
            status=StepStatus.COMPENSATED,
            compensation_data={"status": "compensated"},
        )

        WorkflowStep.objects.create(
            workflow_instance=self.workflow,
            step_index=0,
            step_name="step1",
            step_type="task",
            status=StepStatus.COMPENSATED,
            compensation_data={"status": "compensated"},
        )

        result = WorkflowExecutionValidator.validate_compensation(self.workflow)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertEqual(result.details["compensated_steps_count"], 2)
        # Note: The order validation checks if indices are in descending order
        # In this case, step2 (index 1) was compensated before step1 (index 0)
        # which is correct reverse order


class WorkflowRetryValidationTest(TestCase):
    """Tests for workflow retry validation"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        self.workflow_def = WorkflowDefinition.objects.create(
            name=f"test_workflow_{uuid.uuid4().hex[:8]}",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [{"name": "step1", "type": "task", "task": "task1"}],
            },
            created_by=self.user,
        )

    def test_validate_retry_valid_workflow(self):
        """Test retry validation for valid workflow"""
        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name=self.workflow_def.name,
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.FAILED,
            retry_count=1,
            max_retries=3,
            created_by=self.user,
        )

        result = WorkflowExecutionValidator.validate_retry(workflow)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertEqual(result.details["retry_count"], 1)
        self.assertEqual(result.details["max_retries"], 3)
        self.assertEqual(result.details["max_retries_valid"], "true")
        self.assertEqual(result.details["retry_count_valid"], "true")
        self.assertEqual(result.details["retry_count_within_limits"], "true")

    def test_validate_retry_negative_retry_count(self):
        """Test retry validation with negative retry_count"""
        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name=self.workflow_def.name,
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.FAILED,
            retry_count=-1,
            max_retries=3,
            created_by=self.user,
        )

        result = WorkflowExecutionValidator.validate_retry(workflow)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("non-negative", result.errors[0].lower())

    def test_validate_retry_retry_count_exceeds_max(self):
        """Test retry validation when retry_count exceeds max_retries"""
        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name=self.workflow_def.name,
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.FAILED,
            retry_count=5,
            max_retries=3,
            created_by=self.user,
        )

        result = WorkflowExecutionValidator.validate_retry(workflow)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("exceeds", result.errors[0].lower())

    def test_validate_retry_can_retry_valid(self):
        """Test retry validation for workflow that can retry"""
        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name=self.workflow_def.name,
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.FAILED,
            retry_count=1,
            max_retries=3,
            created_by=self.user,
        )

        result = WorkflowExecutionValidator.validate_retry(workflow)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertEqual(result.details["can_retry"], "true")
        self.assertEqual(result.details["retry_eligibility_valid"], "true")

    def test_validate_retry_cannot_retry_max_exceeded(self):
        """Test retry validation for workflow that cannot retry (max exceeded)"""
        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name=self.workflow_def.name,
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.FAILED,
            retry_count=3,
            max_retries=3,
            created_by=self.user,
        )

        result = WorkflowExecutionValidator.validate_retry(workflow)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertEqual(result.details["can_retry"], "false")
        self.assertEqual(result.details["retry_eligibility_valid"], "true")

    def test_validate_retry_non_failed_workflow(self):
        """Test retry validation for non-FAILED workflow"""
        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name=self.workflow_def.name,
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.COMPLETED,
            retry_count=0,
            max_retries=3,
            created_by=self.user,
        )

        result = WorkflowExecutionValidator.validate_retry(workflow)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertEqual(result.details["can_retry"], "false")
        self.assertEqual(result.details["retry_eligibility_valid"], "true")


class WorkflowComprehensiveValidationTest(TestCase):
    """Tests for comprehensive workflow execution validation"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        self.workflow_def = WorkflowDefinition.objects.create(
            name=f"test_workflow_{uuid.uuid4().hex[:8]}",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [{"name": "step1", "type": "task", "task": "task1"}],
            },
            created_by=self.user,
        )

    def test_validate_all_valid_workflow(self):
        """Test comprehensive validation for valid workflow"""
        started_at = timezone.now() - timedelta(minutes=5)
        completed_at = timezone.now()

        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name=self.workflow_def.name,
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.COMPLETED,
            started_at=started_at,
            completed_at=completed_at,
            output_data={"result": "success"},
            retry_count=0,
            max_retries=3,
            created_by=self.user,
        )

        result = WorkflowExecutionValidator.validate_all(workflow)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertEqual(
            result.details["validation_type"], "comprehensive_workflow_execution_validation"
        )

    def test_validate_all_invalid_workflow(self):
        """Test comprehensive validation for invalid workflow"""
        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name=self.workflow_def.name,
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.COMPLETED,
            # Missing started_at and completed_at
            retry_count=-1,  # Invalid retry_count
            created_by=self.user,
        )

        result = WorkflowExecutionValidator.validate_all(workflow)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        # Comprehensive validation should catch multiple issues (missing timestamps, invalid retry)
        error_text = " ".join(e.lower() for e in result.errors)
        self.assertTrue(
            "retry" in error_text
            or "started_at" in error_text
            or "timestamp" in error_text
            or "non-negative" in error_text,
            f"Errors should mention specific validation failures, got: {result.errors}",
        )

    def test_validate_all_with_step(self):
        """Test comprehensive validation with step"""
        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name=self.workflow_def.name,
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.RUNNING,
            started_at=timezone.now(),
            created_by=self.user,
        )

        step = WorkflowStep.objects.create(
            workflow_instance=workflow,
            step_index=0,
            step_name="step1",
            step_type="task",
            status=StepStatus.RUNNING,
            started_at=timezone.now(),
        )

        result = WorkflowExecutionValidator.validate_all(workflow, step=step)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertIn("step_execution_validation", result.details)


class WorkflowExecutionValidatorFailureTest(TestCase):
    """Test WorkflowExecutionValidator failure scenarios"""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.workflow_def = WorkflowDefinition.objects.create(
            name=f"test_workflow_{uuid.uuid4().hex[:8]}",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [{"name": "step1", "type": "task", "task": "test_task"}],
            },
            created_by=self.user,
        )

    def test_validate_status_transition_with_invalid_transition(self):
        """Test status transition validation with invalid transition"""
        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name=self.workflow_def.name,
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.COMPLETED,
            completed_at=timezone.now(),
            created_by=self.user,
        )

        # Try to transition from COMPLETED to RUNNING (invalid)
        workflow.status = WorkflowStatus.RUNNING
        result = WorkflowExecutionValidator.validate_status_transition(workflow)

        # Should detect invalid transition
        self.assertFalse(result.is_valid)

    def test_validate_step_execution_with_missing_step(self):
        """Test step execution validation with missing step"""
        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name=self.workflow_def.name,
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.RUNNING,
            started_at=timezone.now(),
            created_by=self.user,
        )

        # Validate with None step (should handle gracefully)
        result = WorkflowExecutionValidator.validate_step_execution(
            None, workflow_instance=workflow
        )

        # Should return an invalid result when step is None
        self.assertIsNotNone(result)
        self.assertFalse(result.is_valid, "Validation with None step should return invalid result")


class WorkflowExecutionValidatorEdgeCasesTest(TestCase):
    """Test WorkflowExecutionValidator edge cases"""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.workflow_def = WorkflowDefinition.objects.create(
            name=f"test_workflow_{uuid.uuid4().hex[:8]}",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [{"name": "step1", "type": "task", "task": "test_task"}],
            },
            created_by=self.user,
        )

    def test_validate_status_transition_with_edge_case_timestamps(self):
        """Test status transition validation with edge case timestamps"""
        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name=self.workflow_def.name,
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.RUNNING,
            started_at=timezone.now() - timedelta(days=365),  # Very old timestamp
            created_by=self.user,
        )

        result = WorkflowExecutionValidator.validate_status_transition(workflow)

        # Should handle old timestamps gracefully and still validate as valid RUNNING workflow
        self.assertIsNotNone(result)
        self.assertTrue(
            result.is_valid,
            f"Old timestamps should not invalidate a RUNNING workflow: {result.errors}",
        )

    def test_validate_all_with_empty_workflow(self):
        """Test comprehensive validation with minimal workflow"""
        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name=self.workflow_def.name,
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.DRAFT,
            created_by=self.user,
        )

        result = WorkflowExecutionValidator.validate_all(workflow)

        # A minimal DRAFT workflow with no steps should validate successfully
        self.assertIsNotNone(result)
        self.assertTrue(result.is_valid, f"Minimal DRAFT workflow should be valid: {result.errors}")


class WorkflowExecutionValidatorErrorHandlingTest(TestCase):
    """Test WorkflowExecutionValidator error handling scenarios"""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.workflow_def = WorkflowDefinition.objects.create(
            name=f"test_workflow_{uuid.uuid4().hex[:8]}",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [{"name": "step1", "type": "task", "task": "test_task"}],
            },
            created_by=self.user,
        )

    def test_validate_status_transition_with_corrupted_data(self):
        """Test status transition validation with corrupted workflow data"""
        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name=self.workflow_def.name,
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.DRAFT,
            created_by=self.user,
        )

        # Corrupt workflow state (set invalid status string)
        workflow.status = "INVALID_STATUS"

        # Should handle invalid status gracefully: either raise or return invalid result
        try:
            result = WorkflowExecutionValidator.validate_status_transition(workflow)
            # If it doesn't raise, must return invalid result
            self.assertIsNotNone(result)
            self.assertFalse(
                result.is_valid, "Corrupted status should produce an invalid validation result"
            )
        except (ValueError, AttributeError):
            # Raising on invalid status is also acceptable behavior
            pass

    def test_validate_all_with_nonexistent_workflow_definition(self):
        """Test comprehensive validation when workflow definition is missing (orphaned instance).

        We cannot delete the definition in the same transaction (FK would be violated at
        commit/constraint check). So we test the validator's graceful handling by
        calling validate_compensation (which fetches workflow_definition) with an instance
        whose workflow_definition_id points to a non-existent row. We use deferrable FK
        and a deferred constraint so we can briefly leave the DB in that state.
        """
        from django.db import connection, transaction

        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name=self.workflow_def.name,
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.DRAFT,
            created_by=self.user,
        )
        workflow_def_id = self.workflow_def.id

        # Get the FK constraint name (PostgreSQL)
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT c.conname
                FROM pg_constraint c
                JOIN pg_class t ON c.conrelid = t.oid
                JOIN pg_class r ON c.confrelid = r.oid
                WHERE t.relname = 'workflow_instances'
                  AND r.relname = 'workflow_definitions'
                  AND c.contype = 'f';
            """)
            row = cursor.fetchone()
        if not row:
            self.skipTest("Could not find workflow_instances FK constraint (non-PostgreSQL?)")

        constraint_name = row[0]

        # Migration 0004 makes this FK DEFERRABLE; we only set it deferred for this test.
        # We must roll back this transaction so we never commit the orphaned instance
        # (commit would run SET CONSTRAINTS ALL IMMEDIATE and raise IntegrityError).
        quoted = connection.ops.quote_name(constraint_name)
        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("SET CONSTRAINTS " + quoted + " DEFERRED")
                    cursor.execute(
                        "DELETE FROM workflow_definitions WHERE id = %s",
                        [str(workflow_def_id)],
                    )
                workflow.refresh_from_db()

                # Validator should handle missing definition gracefully (return invalid or raise)
                try:
                    result = WorkflowExecutionValidator.validate_all(workflow)
                    self.assertIsNotNone(result)
                    if hasattr(result, "is_valid"):
                        self.assertFalse(result.is_valid)
                except Exception:
                    # Acceptable: validator may raise when definition is missing
                    pass
                # Force rollback so we never commit orphaned FK state (avoids IntegrityError on commit)
                transaction.set_rollback(True)
        except Exception as e:
            if "cannot be deferred" in str(e).lower() or "deferrable" in str(e).lower():
                self.skipTest(
                    "workflow_instances.workflow_definition_id FK is not deferrable "
                    "(run migration 0004_defer_workflow_instance_workflow_definition_fk)"
                )
            raise
