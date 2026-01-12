"""
Workflow Execution Validators

Comprehensive validation for workflow execution operations including:
- Workflow status transition validation (DRAFT → RUNNING → COMPLETED/FAILED/CANCELLED)
- Workflow step execution validation (step prerequisites met)
- Workflow compensation validation (compensation logic valid)
- Workflow retry validation (retry logic, max retries)

All validation methods follow engineering best practices:
- No mocks/stubs - use real services and models
- Fix root causes, not symptoms
- Comprehensive error messages with context
- Follow DRY, SOLID, and clean code principles
"""
from typing import Optional, Dict, Any, List
from datetime import timedelta

from django.utils import timezone

from hub.apps.core.business_rules.base import ValidationResult
from hub.apps.orchestration.models import (
    WorkflowInstance,
    WorkflowStep,
    WorkflowStatus,
    StepStatus,
    WorkflowDefinition,
)
from hub.apps.orchestration.state_machine import WorkflowStateMachine
from hub.apps.orchestration.compensation import WorkflowCompensation

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class WorkflowExecutionValidator:
    """
    Validator for workflow execution operations.

    Provides comprehensive validation for:
    - Status transitions
    - Step execution prerequisites
    - Compensation logic
    - Retry logic
    """

    @staticmethod
    def validate_status_transition(
        workflow_instance: WorkflowInstance,
        target_status: Optional[WorkflowStatus] = None
    ) -> ValidationResult:
        """
        Validate workflow status transitions (DRAFT → RUNNING → COMPLETED/FAILED/CANCELLED).

        Validates:
        - Current status is valid
        - Status transitions follow expected flow
        - Status matches workflow state (timestamps, error messages, etc.)
        - Terminal states have proper completion data

        Args:
            workflow_instance: WorkflowInstance to validate
            target_status: Optional target status to validate transition to

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details: Dict[str, Any] = {
            'status_transition_validation': 'workflow_status_transition',
            'current_status': workflow_instance.status,
        }

        # Validate current status is valid
        valid_statuses = [choice[0] for choice in WorkflowStatus.choices]
        if workflow_instance.status not in valid_statuses:
            errors.append(
                f"Invalid workflow status: {workflow_instance.status}. "
                f"Valid statuses are: {valid_statuses}"
            )
            details['status_valid'] = 'false'
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['status_valid'] = 'true'
        current_status = WorkflowStatus(workflow_instance.status)

        # Validate transition if target_status provided
        if target_status is not None:
            if not WorkflowStateMachine.can_transition(current_status, target_status):
                errors.append(
                    f"Invalid status transition: {current_status.value} → {target_status.value}. "
                    f"Valid transitions from {current_status.value}: "
                    f"{[s.value for s in WorkflowStateMachine.get_valid_transitions(current_status)]}"
                )
                details['transition_valid'] = 'false'
            else:
                details['transition_valid'] = 'true'
                details['target_status'] = target_status.value

        # Validate status-specific constraints
        if current_status == WorkflowStatus.DRAFT:
            # DRAFT workflows should not have started_at or completed_at
            if workflow_instance.started_at is not None:
                errors.append(
                    f"Workflow with status DRAFT should not have started_at timestamp set"
                )
                details['draft_constraints_valid'] = 'false'
            else:
                details['draft_constraints_valid'] = 'true'

            if workflow_instance.completed_at is not None:
                errors.append(
                    f"Workflow with status DRAFT should not have completed_at timestamp set"
                )
                details['draft_constraints_valid'] = 'false'

            # DRAFT workflows should not have error_message
            if workflow_instance.error_message:
                warnings.append(
                    f"Workflow with status DRAFT should not have error_message set"
                )
                details['draft_constraints_valid'] = details.get('draft_constraints_valid', 'true')

        elif current_status == WorkflowStatus.RUNNING:
            # RUNNING workflows must have started_at set
            if workflow_instance.started_at is None:
                errors.append(
                    f"Workflow with status RUNNING must have started_at timestamp set"
                )
                details['running_constraints_valid'] = 'false'
            else:
                details['running_constraints_valid'] = 'true'

                # Validate started_at is in the past
                if workflow_instance.started_at > timezone.now():
                    warnings.append(
                        f"Workflow started_at ({workflow_instance.started_at}) is in the future"
                    )
                    details['running_constraints_valid'] = 'true'

            # RUNNING workflows should not have completed_at set
            if workflow_instance.completed_at is not None:
                errors.append(
                    f"Workflow with status RUNNING should not have completed_at timestamp set"
                )
                details['running_constraints_valid'] = 'false'

            # RUNNING workflows should not have output_data (not completed yet)
            if workflow_instance.output_data:
                warnings.append(
                    f"Workflow with status RUNNING should not have output_data set (not completed yet)"
                )
                details['running_constraints_valid'] = details.get('running_constraints_valid', 'true')

        elif current_status in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, WorkflowStatus.CANCELLED, WorkflowStatus.ROLLED_BACK]:
            # Terminal states must have both started_at and completed_at
            if workflow_instance.started_at is None:
                errors.append(
                    f"Workflow with status {current_status.value} must have started_at timestamp set"
                )
                details['terminal_constraints_valid'] = 'false'
            else:
                details['terminal_constraints_valid'] = 'true'

            if workflow_instance.completed_at is None:
                errors.append(
                    f"Workflow with status {current_status.value} must have completed_at timestamp set"
                )
                details['terminal_constraints_valid'] = 'false'
            else:
                # Validate completed_at is after started_at
                if workflow_instance.started_at and workflow_instance.completed_at < workflow_instance.started_at:
                    errors.append(
                        f"Workflow completed_at ({workflow_instance.completed_at}) must be after "
                        f"started_at ({workflow_instance.started_at})"
                    )
                    details['terminal_constraints_valid'] = 'false'

            # COMPLETED workflows should have output_data
            if current_status == WorkflowStatus.COMPLETED:
                if workflow_instance.output_data is None:
                    warnings.append(
                        f"Workflow with status COMPLETED should have output_data set"
                    )
                    details['terminal_constraints_valid'] = details.get('terminal_constraints_valid', 'true')

                # COMPLETED workflows should not have error_message
                if workflow_instance.error_message:
                    warnings.append(
                        f"Workflow with status COMPLETED should not have error_message set"
                    )
                    details['terminal_constraints_valid'] = details.get('terminal_constraints_valid', 'true')

            # FAILED/ROLLED_BACK workflows should have error_message
            elif current_status in [WorkflowStatus.FAILED, WorkflowStatus.ROLLED_BACK]:
                if not workflow_instance.error_message:
                    warnings.append(
                        f"Workflow with status {current_status.value} should have error_message set for debugging"
                    )
                    details['terminal_constraints_valid'] = details.get('terminal_constraints_valid', 'true')

        elif current_status == WorkflowStatus.PAUSED:
            # PAUSED workflows should have started_at set
            if workflow_instance.started_at is None:
                warnings.append(
                    f"Workflow with status PAUSED should have started_at timestamp set"
                )
                details['paused_constraints_valid'] = 'true'
            else:
                details['paused_constraints_valid'] = 'true'

            # PAUSED workflows should not have completed_at set
            if workflow_instance.completed_at is not None:
                errors.append(
                    f"Workflow with status PAUSED should not have completed_at timestamp set"
                )
                details['paused_constraints_valid'] = 'false'

        elif current_status == WorkflowStatus.ROLLING_BACK:
            # ROLLING_BACK workflows should have started_at set
            if workflow_instance.started_at is None:
                errors.append(
                    f"Workflow with status ROLLING_BACK must have started_at timestamp set"
                )
                details['rolling_back_constraints_valid'] = 'false'
            else:
                details['rolling_back_constraints_valid'] = 'true'

            # ROLLING_BACK workflows should not have completed_at set (yet)
            if workflow_instance.completed_at is not None:
                warnings.append(
                    f"Workflow with status ROLLING_BACK should not have completed_at timestamp set (rollback in progress)"
                )
                details['rolling_back_constraints_valid'] = details.get('rolling_back_constraints_valid', 'true')

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    @staticmethod
    def validate_step_execution(
        step: WorkflowStep,
        workflow_instance: Optional[WorkflowInstance] = None
    ) -> ValidationResult:
        """
        Validate workflow step execution (step prerequisites met).

        Validates:
        - Step status is valid
        - Step prerequisites are met (previous steps completed)
        - Step execution order is correct
        - Step input/output data consistency

        Args:
            step: WorkflowStep to validate
            workflow_instance: Optional WorkflowInstance (will be fetched if not provided)

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details: Dict[str, Any] = {
            'step_execution_validation': 'workflow_step_execution',
            'step_index': step.step_index,
            'step_name': step.step_name,
            'step_status': step.status,
        }

        # Fetch workflow instance if not provided
        if workflow_instance is None:
            try:
                workflow_instance = step.workflow_instance
            except Exception as e:
                errors.append(f"Failed to fetch workflow instance for step: {str(e)}")
                details['workflow_instance_fetch_error'] = str(e)
                return ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    details=details
                )

        if workflow_instance is None:
            errors.append("Workflow instance is required for step execution validation")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['workflow_instance_id'] = str(workflow_instance.id)
        details['workflow_status'] = workflow_instance.status

        # Validate step status is valid
        valid_step_statuses = [choice[0] for choice in StepStatus.choices]
        if step.status not in valid_step_statuses:
            errors.append(
                f"Invalid step status: {step.status}. "
                f"Valid statuses are: {valid_step_statuses}"
            )
            details['step_status_valid'] = 'false'
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['step_status_valid'] = 'true'

        # Validate step prerequisites (previous steps must be completed)
        if step.step_index > 0:
            previous_steps = workflow_instance.steps.filter(
                step_index__lt=step.step_index
            ).exclude(
                status__in=[StepStatus.COMPLETED, StepStatus.SKIPPED]
            )

            incomplete_previous_steps = list(previous_steps.values_list('step_index', 'step_name', 'status'))

            if incomplete_previous_steps:
                errors.append(
                    f"Step {step.step_index} ({step.step_name}) cannot execute because "
                    f"previous steps are not completed: {incomplete_previous_steps}"
                )
                details['prerequisites_met'] = 'false'
                details['incomplete_previous_steps'] = incomplete_previous_steps
            else:
                details['prerequisites_met'] = 'true'
        else:
            # First step (index 0) has no prerequisites
            details['prerequisites_met'] = 'true'

        # Validate step status matches workflow status
        if workflow_instance.status == WorkflowStatus.RUNNING:
            # Running workflows can have steps in PENDING, RUNNING, COMPLETED, FAILED, SKIPPED
            if step.status not in [StepStatus.PENDING, StepStatus.RUNNING, StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.SKIPPED]:
                warnings.append(
                    f"Step status {step.status} is unusual for a RUNNING workflow. "
                    f"Expected: PENDING, RUNNING, COMPLETED, FAILED, or SKIPPED"
                )
                details['status_workflow_match'] = 'false'
            else:
                details['status_workflow_match'] = 'true'
        elif workflow_instance.status == WorkflowStatus.DRAFT:
            # Draft workflows should have all steps in PENDING
            if step.status != StepStatus.PENDING:
                warnings.append(
                    f"Step status {step.status} is unusual for a DRAFT workflow. "
                    f"Expected: PENDING"
                )
                details['status_workflow_match'] = 'false'
            else:
                details['status_workflow_match'] = 'true'
        elif workflow_instance.status in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, WorkflowStatus.CANCELLED]:
            # Terminal workflows should have steps in terminal states
            terminal_step_statuses = [StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.SKIPPED, StepStatus.COMPENSATED]
            if step.status not in terminal_step_statuses:
                warnings.append(
                    f"Step status {step.status} is unusual for a {workflow_instance.status} workflow. "
                    f"Expected terminal states: COMPLETED, FAILED, SKIPPED, or COMPENSATED"
                )
                details['status_workflow_match'] = 'false'
            else:
                details['status_workflow_match'] = 'true'

        # Validate step execution timestamps
        if step.status == StepStatus.RUNNING:
            # RUNNING steps must have started_at set
            if step.started_at is None:
                errors.append(
                    f"Step with status RUNNING must have started_at timestamp set"
                )
                details['step_timestamps_valid'] = 'false'
            else:
                details['step_timestamps_valid'] = 'true'

            # RUNNING steps should not have completed_at set
            if step.completed_at is not None:
                errors.append(
                    f"Step with status RUNNING should not have completed_at timestamp set"
                )
                details['step_timestamps_valid'] = 'false'

        elif step.status in [StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.SKIPPED]:
            # Completed steps must have both started_at and completed_at
            if step.started_at is None:
                errors.append(
                    f"Step with status {step.status} must have started_at timestamp set"
                )
                details['step_timestamps_valid'] = 'false'
            else:
                details['step_timestamps_valid'] = 'true'

            if step.completed_at is None:
                errors.append(
                    f"Step with status {step.status} must have completed_at timestamp set"
                )
                details['step_timestamps_valid'] = 'false'
            else:
                # Validate completed_at is after started_at
                if step.started_at and step.completed_at < step.started_at:
                    errors.append(
                        f"Step completed_at ({step.completed_at}) must be after "
                        f"started_at ({step.started_at})"
                    )
                    details['step_timestamps_valid'] = 'false'

        # Validate step status-specific constraints
        if step.status == StepStatus.COMPLETED:
            # COMPLETED steps should have output_data
            if step.output_data is None:
                warnings.append(
                    f"Step with status COMPLETED should have output_data set"
                )
                details['step_constraints_valid'] = 'true'

            # COMPLETED steps should not have error_message
            if step.error_message:
                warnings.append(
                    f"Step with status COMPLETED should not have error_message set"
                )
                details['step_constraints_valid'] = 'true'

        elif step.status == StepStatus.FAILED:
            # FAILED steps should have error_message
            if not step.error_message:
                warnings.append(
                    f"Step with status FAILED should have error_message set for debugging"
                )
                details['step_constraints_valid'] = 'true'

            # FAILED steps should not have output_data (unless partial output)
            # This is a warning, not an error, as some steps may produce partial output before failing

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    @staticmethod
    def validate_compensation(
        workflow_instance: WorkflowInstance,
        step: Optional[WorkflowStep] = None
    ) -> ValidationResult:
        """
        Validate workflow compensation validation (compensation logic valid).

        Validates:
        - Compensation configuration is valid
        - Compensation steps are properly defined
        - Compensation execution order is correct
        - Compensation data is consistent

        Args:
            workflow_instance: WorkflowInstance to validate
            step: Optional WorkflowStep to validate compensation for

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details: Dict[str, Any] = {
            'compensation_validation': 'workflow_compensation',
        }

        # Get workflow definition
        try:
            workflow_def = workflow_instance.workflow_definition
            dsl = workflow_def.dsl_json
        except Exception as e:
            errors.append(f"Failed to fetch workflow definition: {str(e)}")
            details['workflow_definition_fetch_error'] = str(e)
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['workflow_name'] = workflow_instance.workflow_name
        details['workflow_version'] = workflow_instance.workflow_version

        # Check if compensation is enabled in workflow DSL
        compensation_config = dsl.get("compensation", {})
        compensation_enabled = compensation_config.get("enabled", False)
        details['compensation_enabled'] = 'true' if compensation_enabled else 'false'

        # Validate compensation configuration structure
        if compensation_config:
            if not isinstance(compensation_config, dict):
                errors.append(
                    f"Compensation configuration must be a dictionary, got {type(compensation_config).__name__}"
                )
                details['compensation_config_valid'] = 'false'
            else:
                details['compensation_config_valid'] = 'true'

        # Validate step-level compensation if step provided
        if step is not None:
            details['step_index'] = step.step_index
            details['step_name'] = step.step_name

            # Get step definition from DSL
            steps = dsl.get("steps", [])
            if step.step_index < len(steps):
                step_def = steps[step.step_index]
                step_compensation = step_def.get("compensation")

                if step_compensation:
                    details['step_has_compensation'] = 'true'

                    # Validate compensation structure
                    if not isinstance(step_compensation, dict):
                        errors.append(
                            f"Step compensation must be a dictionary, got {type(step_compensation).__name__}"
                        )
                        details['step_compensation_valid'] = 'false'
                    else:
                        compensation_type = step_compensation.get("type", "task")
                        details['compensation_type'] = compensation_type

                        # Validate compensation type
                        valid_compensation_types = ["task", "script"]
                        if compensation_type not in valid_compensation_types:
                            errors.append(
                                f"Invalid compensation type: {compensation_type}. "
                                f"Valid types are: {valid_compensation_types}"
                            )
                            details['step_compensation_valid'] = 'false'
                        else:
                            details['step_compensation_valid'] = 'true'

                            # Validate compensation task/script is specified
                            if compensation_type == "task":
                                if "task" not in step_compensation:
                                    errors.append(
                                        f"Compensation type 'task' requires 'task' field to be specified"
                                    )
                                    details['step_compensation_valid'] = 'false'
                            elif compensation_type == "script":
                                if "script" not in step_compensation:
                                    errors.append(
                                        f"Compensation type 'script' requires 'script' field to be specified"
                                    )
                                    details['step_compensation_valid'] = 'false'
                else:
                    details['step_has_compensation'] = 'false'
                    if compensation_enabled:
                        warnings.append(
                            f"Workflow has compensation enabled but step {step.step_name} "
                            f"does not define compensation logic"
                        )
            else:
                warnings.append(
                    f"Step index {step.step_index} out of range for workflow definition"
                )

        # Validate compensation execution for ROLLING_BACK or ROLLED_BACK workflows
        if workflow_instance.status in [WorkflowStatus.ROLLING_BACK, WorkflowStatus.ROLLED_BACK]:
            # Get compensated steps
            compensated_steps = workflow_instance.steps.filter(
                status=StepStatus.COMPENSATED
            ).order_by('-step_index')

            details['compensated_steps_count'] = compensated_steps.count()

            # Validate compensation order (should be reverse of execution order)
            compensated_indices = list(compensated_steps.values_list('step_index', flat=True))
            if compensated_indices:
                # Check if indices are in descending order (reverse execution order)
                if compensated_indices != sorted(compensated_indices, reverse=True):
                    warnings.append(
                        f"Compensated steps are not in reverse execution order: {compensated_indices}"
                    )
                    details['compensation_order_valid'] = 'false'
                else:
                    details['compensation_order_valid'] = 'true'

                # Validate each compensated step has compensation_data
                steps_without_data = []
                for comp_step in compensated_steps:
                    if not comp_step.compensation_data:
                        steps_without_data.append(comp_step.step_index)

                if steps_without_data:
                    warnings.append(
                        f"Compensated steps without compensation_data: {steps_without_data}"
                    )
                    details['compensation_data_complete'] = 'false'
                else:
                    details['compensation_data_complete'] = 'true'

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    @staticmethod
    def validate_retry(
        workflow_instance: WorkflowInstance
    ) -> ValidationResult:
        """
        Validate workflow retry validation (retry logic, max retries).

        Validates:
        - Retry count is within limits
        - Max retries configuration is valid
        - Retry logic is correct
        - Retry eligibility (can_retry method)

        Args:
            workflow_instance: WorkflowInstance to validate

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details: Dict[str, Any] = {
            'retry_validation': 'workflow_retry',
            'retry_count': workflow_instance.retry_count,
            'max_retries': workflow_instance.max_retries,
        }

        # Validate max_retries configuration
        if workflow_instance.max_retries < 0:
            errors.append(
                f"Workflow max_retries must be non-negative, got: {workflow_instance.max_retries}"
            )
            details['max_retries_valid'] = 'false'
        else:
            details['max_retries_valid'] = 'true'

        # Validate retry_count is non-negative
        if workflow_instance.retry_count < 0:
            errors.append(
                f"Workflow retry_count must be non-negative, got: {workflow_instance.retry_count}"
            )
            details['retry_count_valid'] = 'false'
        else:
            details['retry_count_valid'] = 'true'

        # Validate retry_count against max_retries
        if workflow_instance.retry_count > workflow_instance.max_retries:
            errors.append(
                f"Workflow retry_count ({workflow_instance.retry_count}) exceeds "
                f"max_retries ({workflow_instance.max_retries})"
            )
            details['retry_count_within_limits'] = 'false'
        else:
            details['retry_count_within_limits'] = 'true'

        # Validate retry eligibility
        can_retry = workflow_instance.can_retry()
        details['can_retry'] = 'true' if can_retry else 'false'

        # Validate can_retry logic
        if workflow_instance.status == WorkflowStatus.FAILED:
            if workflow_instance.retry_count < workflow_instance.max_retries:
                if not can_retry:
                    errors.append(
                        f"Workflow with status FAILED and retry_count ({workflow_instance.retry_count}) < "
                        f"max_retries ({workflow_instance.max_retries}) should be eligible for retry"
                    )
                    details['retry_eligibility_valid'] = 'false'
                else:
                    details['retry_eligibility_valid'] = 'true'
            else:
                if can_retry:
                    warnings.append(
                        f"Workflow with retry_count ({workflow_instance.retry_count}) >= "
                        f"max_retries ({workflow_instance.max_retries}) should not be eligible for retry"
                    )
                    details['retry_eligibility_valid'] = 'false'
                else:
                    details['retry_eligibility_valid'] = 'true'
        else:
            # Non-FAILED workflows should not be eligible for retry
            if can_retry:
                warnings.append(
                    f"Workflow with status {workflow_instance.status} should not be eligible for retry"
                )
                details['retry_eligibility_valid'] = 'false'
            else:
                details['retry_eligibility_valid'] = 'true'

        # Validate step-level retry counts
        steps = workflow_instance.steps.all()
        details['total_steps'] = steps.count()

        steps_with_excessive_retries = []
        for step in steps:
            # Note: Steps don't have max_retries field, so we can't validate against a limit
            # But we can validate retry_count is non-negative
            if step.retry_count < 0:
                errors.append(
                    f"Step {step.step_index} ({step.step_name}) has invalid retry_count: {step.retry_count}"
                )
                details['step_retry_counts_valid'] = 'false'
            else:
                details['step_retry_counts_valid'] = 'true'

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    @staticmethod
    def validate_all(
        workflow_instance: WorkflowInstance,
        target_status: Optional[WorkflowStatus] = None,
        step: Optional[WorkflowStep] = None
    ) -> ValidationResult:
        """
        Validate all workflow execution aspects (status transition, step execution, compensation, retry).

        Args:
            workflow_instance: WorkflowInstance to validate
            target_status: Optional target status to validate transition to
            step: Optional WorkflowStep to validate (for step-specific validation)

        Returns:
            Combined ValidationResult with all validation checks
        """
        # Run all validations
        status_result = WorkflowExecutionValidator.validate_status_transition(
            workflow_instance, target_status
        )
        retry_result = WorkflowExecutionValidator.validate_retry(workflow_instance)
        compensation_result = WorkflowExecutionValidator.validate_compensation(
            workflow_instance, step
        )

        # Combine results
        combined_result = status_result.combine(retry_result).combine(compensation_result)
        combined_result.details['validation_type'] = 'comprehensive_workflow_execution_validation'

        # Add step execution validation if step provided
        if step is not None:
            step_result = WorkflowExecutionValidator.validate_step_execution(step, workflow_instance)
            combined_result = combined_result.combine(step_result)

        return combined_result

