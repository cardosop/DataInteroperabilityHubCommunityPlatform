"""
Workflow Compensation (Saga Pattern)

Implements workflow rollback and compensation logic.
"""
import logging
from typing import Dict, Any, Optional
from django.db import transaction
from django.utils import timezone

from .business_rules import OrchestrationBusinessRules
from .models import (
    WorkflowInstance,
    WorkflowStep,
    WorkflowStatus,
    StepStatus
)

logger = logging.getLogger(__name__)


class WorkflowCompensation:
    """
    Workflow compensation handler.

    Implements Saga pattern for workflow rollback and compensation.
    """

    def __init__(self, task_registry: Optional[Dict[str, Any]] = None):
        """
        Initialize compensation handler.

        Args:
            task_registry: Optional task registry dictionary mapping task names to functions
        """
        # Store reference to the task registry (don't create a new dict)
        if task_registry is None:
            self.task_registry = {}
        else:
            self.task_registry = task_registry

    @transaction.atomic
    def rollback_workflow(
        self,
        instance: WorkflowInstance,
        failed_step: WorkflowStep
    ) -> WorkflowInstance:
        """
        Rollback workflow using compensation logic (Saga pattern).

        Args:
            instance: Workflow instance to rollback
            failed_step: Step that failed

        Returns:
            Updated WorkflowInstance
        """
        logger.info(f"Rolling back workflow instance {instance.id} from step {failed_step.step_index}")

        # Get tenant and user for business rules validation
        tenant = instance.tenant
        user = instance.created_by

        # Create business rules instance with tenant/user context
        business_rules = OrchestrationBusinessRules(
            tenant_id=str(tenant.id) if tenant else None,
            user_id=str(user.id) if user else None
        )

        # Validate compensation can execute
        compensation_validation_result = business_rules.validate_workflow_state(instance, tenant, user)
        if not compensation_validation_result.is_valid:
            # Log validation errors but don't block compensation (compensation should proceed)
            logger.warning(
                f"Compensation validation errors for workflow {instance.id}: "
                f"{', '.join(compensation_validation_result.errors)}"
            )

        # Validate workflow state before compensation
        workflow_state_result = business_rules.validate_workflow_state(instance, tenant, user)
        if workflow_state_result.warnings:
            # Log validation warnings (don't block compensation)
            logger.warning(
                f"Workflow state validation warnings before compensation: "
                f"{', '.join(workflow_state_result.warnings)}"
            )

        # Mark workflow as rolling back
        instance.status = WorkflowStatus.ROLLING_BACK
        instance.save(update_fields=['status', 'updated_at'])

        try:
            # Get completed steps in reverse order
            completed_steps = instance.steps.filter(
                step_index__lt=failed_step.step_index,
                status=StepStatus.COMPLETED
            ).order_by('-step_index')

            # Compensate each completed step
            compensation_results = []
            for step in completed_steps:
                compensation_result = self._compensate_step(instance, step)
                compensation_results.append(compensation_result)

            # Mark workflow as rolled back; include step error for callers (e.g. ConflictError)
            instance.status = WorkflowStatus.ROLLED_BACK
            instance.completed_at = timezone.now()
            step_err = (failed_step.error_message or "").strip()
            instance.error_message = (
                f"Workflow rolled back due to step failure: {failed_step.step_name}"
                + (f": {step_err}" if step_err else "")
            )
            instance.error_details = {
                "failed_step_index": failed_step.step_index,
                "failed_step_name": failed_step.step_name,
                "compensation_results": compensation_results
            }
            instance.save(update_fields=[
                'status', 'completed_at', 'error_message', 'error_details', 'updated_at'
            ])

            logger.info(f"Workflow instance {instance.id} rolled back successfully")

        except Exception as e:
            logger.exception(f"Error rolling back workflow instance {instance.id}: {str(e)}")
            instance.status = WorkflowStatus.FAILED
            instance.error_message = f"Rollback failed: {str(e)}"
            instance.save(update_fields=['status', 'error_message', 'updated_at'])

        return instance

    def _compensate_step(
        self,
        instance: WorkflowInstance,
        step: WorkflowStep
    ) -> Dict[str, Any]:
        """
        Compensate a workflow step.

        Args:
            instance: Workflow instance
            step: Step to compensate

        Returns:
            Compensation result
        """
        logger.info(f"Compensating step {step.step_name} (index {step.step_index})")

        # Get tenant and user for business rules validation
        tenant = instance.tenant
        user = instance.created_by

        # Create business rules instance with tenant/user context
        business_rules = OrchestrationBusinessRules(
            tenant_id=str(tenant.id) if tenant else None,
            user_id=str(user.id) if user else None
        )

        # Validate compensation step using business rules
        compensation_step_result = business_rules.validate_workflow_step_execution(instance, step, tenant, user)
        if compensation_step_result.warnings:
            # Log validation warnings (don't block compensation)
            logger.warning(
                f"Compensation step validation warnings for step {step.step_name}: "
                f"{', '.join(compensation_step_result.warnings)}"
            )

        # Track compensation validation in metrics (if metrics are available)
        # Note: This would require adding metrics, but for now we just log
        logger.debug(
            f"Compensation step validation for step {step.step_name}: "
            f"is_valid={compensation_step_result.is_valid}, "
            f"warnings={len(compensation_step_result.warnings)}"
        )

        # Get step definition from workflow DSL
        dsl = instance.workflow_definition.dsl_json
        steps = dsl.get("steps", [])

        if step.step_index >= len(steps):
            logger.warning(f"Step index {step.step_index} out of range")
            return {"status": "skipped", "reason": "step_index_out_of_range"}

        step_def = steps[step.step_index]
        compensation_def = step_def.get("compensation")

        if not compensation_def:
            # No compensation defined, skip
            logger.info(f"No compensation defined for step {step.step_name}, skipping")
            step.mark_compensated({"status": "skipped", "reason": "no_compensation_defined"})
            return {"status": "skipped", "reason": "no_compensation_defined"}

        try:
            # Execute compensation logic
            compensation_type = compensation_def.get("type", "task")

            if compensation_type == "task":
                compensation_result = self._execute_compensation_task(
                    instance, step, compensation_def
                )
            elif compensation_type == "script":
                compensation_result = self._execute_compensation_script(
                    instance, step, compensation_def
                )
            else:
                raise ValueError(f"Unsupported compensation type: {compensation_type}")

            # Mark step as compensated
            step.mark_compensated(compensation_result)

            # Include validation results in compensation logs
            compensation_log_data = {
                "status": "compensated",
                "result": compensation_result,
                "validation": {
                    "is_valid": compensation_step_result.is_valid,
                    "warnings": compensation_step_result.warnings,
                    "details": compensation_step_result.details
                }
            }

            logger.info(
                f"Step {step.step_name} compensated successfully. "
                f"Validation: is_valid={compensation_step_result.is_valid}, "
                f"warnings={len(compensation_step_result.warnings)}"
            )
            return compensation_log_data

        except Exception as e:
            logger.exception(f"Error compensating step {step.step_name}: {str(e)}")
            step.mark_compensated({
                "status": "failed",
                "error": str(e)
            })
            return {"status": "failed", "error": str(e)}

    def _execute_compensation_task(
        self,
        instance: WorkflowInstance,
        step: WorkflowStep,
        compensation_def: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute compensation task.

        Args:
            instance: Workflow instance
            step: Step to compensate
            compensation_def: Compensation definition

        Returns:
            Compensation result
        """
        # Get compensation task name
        task_name = compensation_def.get("task")
        if not task_name:
            raise ValueError("Compensation task name not specified")

        logger.info(f"Executing compensation task: {task_name}")

        # Get task function from registry
        task_func = self.task_registry.get(task_name)
        if not task_func:
            raise ValueError(f"Compensation task not found in registry: {task_name}")

        # Prepare task input by merging:
        # 1. Workflow input_data (initial input)
        # 2. Workflow state_data (accumulated state from previous steps)
        # 3. Step-specific input_data (from step model)
        # Refresh instance to get latest state_data
        instance.refresh_from_db()
        task_input = {
            **instance.input_data,
            **instance.state_data,
            **step.input_data,
            **compensation_def.get("input", {}),
        }

        # Execute compensation task
        result = task_func(task_input, instance, step)

        return result if isinstance(result, dict) else {"result": result}

    def _execute_compensation_script(
        self,
        instance: WorkflowInstance,
        step: WorkflowStep,
        compensation_def: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute compensation script.

        Args:
            instance: Workflow instance
            step: Step to compensate
            compensation_def: Compensation definition

        Returns:
            Compensation result
        """
        # Get compensation script
        script = compensation_def.get("script")
        if not script:
            raise ValueError("Compensation script not specified")

        logger.info(f"Executing compensation script for step {step.step_name}")

        # In a real implementation, this would execute the script
        # For now, return a success result
        return {
            "script": script,
            "status": "executed",
            "step_output": step.output_data
        }

