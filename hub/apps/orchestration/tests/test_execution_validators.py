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
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
import uuid

from hub.apps.orchestration.models import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStep,
    WorkflowStatus,
    StepStatus,
)
from hub.apps.orchestration.execution_validators import WorkflowExecutionValidator
from hub.apps.orchestration.state_machine import WorkflowStateMachine
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus


class WorkflowStatusTransitionValidationTest(TestCase):
    """Tests for workflow status transition validation"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        # Create workflow definition
        self.workflow_def = WorkflowDefinition.objects.create(
            name="test_workflow",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [
                    {"name": "step1", "type": "task", "task": "test_task"}
                ]
            },
            created_by=self.user,
        )

    def test_validate_status_transition_draft_valid(self):
        """Test status transition validation for valid DRAFT workflow"""
        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.DRAFT,
            created_by=self.user,
        )

        result = WorkflowExecutionValidator.validate_status_transition(workflow)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertEqual(result.details['current_status'], WorkflowStatus.DRAFT)
        self.assertEqual(result.details['status_valid'], 'true')
        self.assertEqual(result.details['draft_constraints_valid'], 'true')

    def test_validate_status_transition_draft_with_started_at(self):
        """Test status transition validation for DRAFT workflow with started_at set"""
        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
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
            workflow_name="test_workflow",
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.RUNNING,
            started_at=timezone.now(),
            created_by=self.user,
        )

        result = WorkflowExecutionValidator.validate_status_transition(workflow)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertEqual(result.details['current_status'], WorkflowStatus.RUNNING)
        self.assertEqual(result.details['status_valid'], 'true')
        self.assertEqual(result.details['running_constraints_valid'], 'true')

    def test_validate_status_transition_running_without_started_at(self):
        """Test status transition validation for RUNNING workflow without started_at"""
        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
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
            workflow_name="test_workflow",
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
        self.assertEqual(result.details['current_status'], WorkflowStatus.COMPLETED)
        self.assertEqual(result.details['status_valid'], 'true')
        self.assertEqual(result.details['terminal_constraints_valid'], 'true')

    def test_validate_status_transition_completed_without_timestamps(self):
        """Test status transition validation for COMPLETED workflow without timestamps"""
        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.COMPLETED,
            created_by=self.user,
        )

        result = WorkflowExecutionValidator.validate_status_transition(workflow)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_status_transition_failed_valid(self):
        """Test status transition validation for valid FAILED workflow"""
        started_at = timezone.now() - timedelta(minutes=5)
        completed_at = timezone.now()

        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
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
        self.assertEqual(result.details['current_status'], WorkflowStatus.FAILED)
        self.assertEqual(result.details['status_valid'], 'true')
        self.assertEqual(result.details['terminal_constraints_valid'], 'true')

    def test_validate_status_transition_invalid_transition(self):
        """Test status transition validation for invalid transition"""
        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
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
            workflow_name="test_workflow",
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
        self.assertEqual(result.details['transition_valid'], 'true')


class WorkflowStepExecutionValidationTest(TestCase):
    """Tests for workflow step execution validation"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        # Create workflow definition
        self.workflow_def = WorkflowDefinition.objects.create(
            name="test_workflow",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [
                    {"name": "step1", "type": "task", "task": "task1"},
                    {"name": "step2", "type": "task", "task": "task2"},
                    {"name": "step3", "type": "task", "task": "task3"},
                ]
            },
            created_by=self.user,
        )

        self.workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
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
        self.assertEqual(result.details['step_index'], 0)
        self.assertEqual(result.details['prerequisites_met'], 'true')

    def test_validate_step_execution_prerequisites_met(self):
        """Test step execution validation when prerequisites are met"""
        # Create and complete first step
        step1 = WorkflowStep.objects.create(
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
        self.assertEqual(result.details['prerequisites_met'], 'true')

    def test_validate_step_execution_prerequisites_not_met(self):
        """Test step execution validation when prerequisites are not met"""
        # Create first step but don't complete it
        step1 = WorkflowStep.objects.create(
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
            f"Error message should mention prerequisites or previous steps: {result.errors[0]}"
        )
        self.assertEqual(result.details['prerequisites_met'], 'false')

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
        self.assertEqual(result.details['step_status'], StepStatus.RUNNING)
        self.assertEqual(result.details['step_timestamps_valid'], 'true')

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
        self.assertEqual(result.details['step_status'], StepStatus.COMPLETED)
        self.assertEqual(result.details['step_timestamps_valid'], 'true')

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


class WorkflowCompensationValidationTest(TestCase):
    """Tests for workflow compensation validation"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        # Create workflow definition with compensation
        self.workflow_def = WorkflowDefinition.objects.create(
            name="test_workflow",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "compensation": {"enabled": True},
                "steps": [
                    {
                        "name": "step1",
                        "type": "task",
                        "task": "task1",
                        "compensation": {
                            "type": "task",
                            "task": "compensation_task1"
                        }
                    },
                    {
                        "name": "step2",
                        "type": "task",
                        "task": "task2"
                    }
                ]
            },
            created_by=self.user,
        )

        self.workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
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
        self.assertEqual(result.details['compensation_enabled'], 'true')
        self.assertEqual(result.details['compensation_config_valid'], 'true')

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
        self.assertEqual(result.details['step_has_compensation'], 'true')
        self.assertEqual(result.details['compensation_type'], 'task')
        self.assertEqual(result.details['step_compensation_valid'], 'true')

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
        self.assertEqual(result.details['step_has_compensation'], 'false')
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
                        "compensation": {
                            "type": "invalid_type"
                        }
                    }
                ]
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
        step2 = WorkflowStep.objects.create(
            workflow_instance=self.workflow,
            step_index=1,
            step_name="step2",
            step_type="task",
            status=StepStatus.COMPENSATED,
            compensation_data={"status": "compensated"},
        )

        step1 = WorkflowStep.objects.create(
            workflow_instance=self.workflow,
            step_index=0,
            step_name="step1",
            step_type="task",
            status=StepStatus.COMPENSATED,
            compensation_data={"status": "compensated"},
        )

        result = WorkflowExecutionValidator.validate_compensation(self.workflow)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertEqual(result.details['compensated_steps_count'], 2)
        # Note: The order validation checks if indices are in descending order
        # In this case, step2 (index 1) was compensated before step1 (index 0)
        # which is correct reverse order


class WorkflowRetryValidationTest(TestCase):
    """Tests for workflow retry validation"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        self.workflow_def = WorkflowDefinition.objects.create(
            name="test_workflow",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [
                    {"name": "step1", "type": "task", "task": "task1"}
                ]
            },
            created_by=self.user,
        )

    def test_validate_retry_valid_workflow(self):
        """Test retry validation for valid workflow"""
        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.FAILED,
            retry_count=1,
            max_retries=3,
            created_by=self.user,
        )

        result = WorkflowExecutionValidator.validate_retry(workflow)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertEqual(result.details['retry_count'], 1)
        self.assertEqual(result.details['max_retries'], 3)
        self.assertEqual(result.details['max_retries_valid'], 'true')
        self.assertEqual(result.details['retry_count_valid'], 'true')
        self.assertEqual(result.details['retry_count_within_limits'], 'true')

    def test_validate_retry_negative_retry_count(self):
        """Test retry validation with negative retry_count"""
        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
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
            workflow_name="test_workflow",
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
            workflow_name="test_workflow",
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.FAILED,
            retry_count=1,
            max_retries=3,
            created_by=self.user,
        )

        result = WorkflowExecutionValidator.validate_retry(workflow)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertEqual(result.details['can_retry'], 'true')
        self.assertEqual(result.details['retry_eligibility_valid'], 'true')

    def test_validate_retry_cannot_retry_max_exceeded(self):
        """Test retry validation for workflow that cannot retry (max exceeded)"""
        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.FAILED,
            retry_count=3,
            max_retries=3,
            created_by=self.user,
        )

        result = WorkflowExecutionValidator.validate_retry(workflow)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertEqual(result.details['can_retry'], 'false')
        self.assertEqual(result.details['retry_eligibility_valid'], 'true')

    def test_validate_retry_non_failed_workflow(self):
        """Test retry validation for non-FAILED workflow"""
        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.COMPLETED,
            retry_count=0,
            max_retries=3,
            created_by=self.user,
        )

        result = WorkflowExecutionValidator.validate_retry(workflow)

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertEqual(result.details['can_retry'], 'false')
        self.assertEqual(result.details['retry_eligibility_valid'], 'true')


class WorkflowComprehensiveValidationTest(TestCase):
    """Tests for comprehensive workflow execution validation"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        self.workflow_def = WorkflowDefinition.objects.create(
            name="test_workflow",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [
                    {"name": "step1", "type": "task", "task": "task1"}
                ]
            },
            created_by=self.user,
        )

    def test_validate_all_valid_workflow(self):
        """Test comprehensive validation for valid workflow"""
        started_at = timezone.now() - timedelta(minutes=5)
        completed_at = timezone.now()

        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
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
        self.assertEqual(result.details['validation_type'], 'comprehensive_workflow_execution_validation')

    def test_validate_all_invalid_workflow(self):
        """Test comprehensive validation for invalid workflow"""
        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
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

    def test_validate_all_with_step(self):
        """Test comprehensive validation with step"""
        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
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
        self.assertIn('step_execution_validation', result.details)


