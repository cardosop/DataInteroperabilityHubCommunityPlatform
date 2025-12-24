"""
Workflow Execution Engine

Core workflow execution engine with step execution, retry logic, and error handling.
Includes metrics and tracing for observability.
"""

import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from hub.apps.core.events.service_publishers import WorkflowEventPublisher, ODPSEventPublisher

from .compensation import WorkflowCompensation
from .dsl_parser import WorkflowDSLParser
from .metrics import (
    get_error_type,
    get_tenant_id,
    workflow_compensation_duration_seconds,
    workflow_compensations_completed_total,
    workflow_compensations_triggered_total,
    workflow_execution_duration_seconds,
    workflow_instances_cancelled_total,
    workflow_instances_completed_total,
    workflow_instances_created_total,
    workflow_instances_failed_current,
    workflow_instances_failed_total,
    workflow_instances_pending,
    workflow_instances_retried_total,
    workflow_instances_running,
    workflow_instances_started_total,
    workflow_instances_timed_out_total,
    workflow_state_size_bytes,
    workflow_step_execution_duration_seconds,
    workflow_steps_completed_total,
    workflow_steps_failed_total,
    workflow_steps_per_instance,
    workflow_steps_retried_total,
    workflow_steps_started_total,
)
from .models import StepStatus, WorkflowDefinition, WorkflowInstance, WorkflowStatus, WorkflowStep
from .state_machine import WorkflowStateMachine
from .versioning import WorkflowVersionManager

logger = logging.getLogger(__name__)

# Try to import OpenTelemetry tracing
try:
    from hub.apps.observability.tracing import get_tracer

    _tracer = get_tracer(__name__)
except ImportError:
    _tracer = None


class WorkflowExecutionError(Exception):
    """Workflow execution error"""

    pass


class WorkflowEngine(WorkflowEventPublisher):
    """
    Workflow execution engine.

    Executes workflow instances, manages step execution, retries, and error handling.
    """

    def __init__(self):
        super().__init__()
        self.dsl_parser = WorkflowDSLParser()
        self.version_manager = WorkflowVersionManager()
        self.compensation = WorkflowCompensation()
        self.task_registry: Dict[str, Callable] = {}

        # ODPS workflows that should publish ODPS-specific events (Task 7.1.4)
        self._odps_workflow_names = {"product_creation"}

    def register_task(self, task_name: str, task_func: Callable):
        """
        Register a task function for workflow execution.

        Args:
            task_name: Task identifier (matches 'task' field in workflow DSL)
            task_func: Task function to execute
        """
        self.task_registry[task_name] = task_func
        logger.info(f"Registered task: {task_name}")

    @transaction.atomic
    def create_instance(
        self,
        workflow_name: str,
        input_data: Dict[str, Any],
        tenant_id: Optional[str] = None,
        created_by_id: Optional[str] = None,
        workflow_version: Optional[str] = None,
    ) -> WorkflowInstance:
        """
        Create a new workflow instance.

        Args:
            workflow_name: Workflow name
            input_data: Workflow input data
            tenant_id: Optional tenant ID
            created_by_id: Optional user ID who created the instance
            workflow_version: Optional workflow version (uses active version if not specified)

        Returns:
            Created WorkflowInstance
        """
        # Get workflow definition
        workflow_def = self.version_manager.get_workflow_definition(
            workflow_name, version=workflow_version
        )

        if not workflow_def:
            raise WorkflowExecutionError(f"Workflow definition not found: {workflow_name}")

        # Create workflow instance
        # Convert tenant_id to Tenant object if provided
        tenant_obj = None
        if tenant_id:
            from hub.apps.tenants.models import Tenant

            try:
                tenant_obj = Tenant.objects.get(id=tenant_id)
            except Tenant.DoesNotExist:
                logger.warning(f"Tenant {tenant_id} not found, creating workflow without tenant")

        instance = WorkflowInstance.objects.create(
            workflow_definition=workflow_def,
            workflow_name=workflow_name,
            workflow_version=workflow_def.version,
            tenant=tenant_obj,
            input_data=input_data,
            created_by_id=created_by_id,
            status=WorkflowStatus.DRAFT,
        )

        # Create workflow steps
        dsl = workflow_def.dsl_json
        steps = dsl.get("steps", [])

        for i, step_def in enumerate(steps):
            WorkflowStep.objects.create(
                workflow_instance=instance,
                step_index=i,
                step_name=step_def.get("name", f"step_{i}"),
                step_type=step_def.get("type", "task"),
                status=StepStatus.PENDING,
                input_data=step_def.get("input", {}),
            )

        # Record metrics
        tenant_id_str = get_tenant_id(tenant_id)
        workflow_instances_created_total.labels(
            workflow_name=workflow_name,
            workflow_version=workflow_def.version,
            tenant_id=tenant_id_str,
        ).inc()

        # Record steps per instance metric
        workflow_steps_per_instance.labels(
            workflow_name=workflow_name,
            workflow_version=workflow_def.version,
            tenant_id=tenant_id_str,
        ).observe(len(steps))

        logger.info(f"Created workflow instance: {instance.id} ({workflow_name})")

        # Publish workflow.created event
        try:
            tenant_id_str = str(instance.tenant_id) if instance.tenant_id else None
            user_id_str = str(created_by_id) if created_by_id else None
            self.publish_workflow_created(
                workflow_instance_id=str(instance.id),
                workflow_name=workflow_name,
                workflow_version=workflow_def.version,
                input_data=input_data,
                tenant_id=tenant_id_str,
                user_id=user_id_str,
            )
        except Exception as e:
            logger.warning(f"Failed to publish workflow.created event: {e}")

        return instance

    @transaction.atomic
    def start_instance(self, instance_id: str) -> WorkflowInstance:
        """
        Start workflow instance execution.

        Args:
            instance_id: Workflow instance ID

        Returns:
            Updated WorkflowInstance
        """
        instance = WorkflowInstance.objects.select_for_update().get(id=instance_id)

        # Validate state transition
        WorkflowStateMachine.validate_transition(
            WorkflowStatus(instance.status), WorkflowStatus.RUNNING
        )

        # Mark instance as started
        instance.mark_started()

        # Record metrics
        tenant_id_str = get_tenant_id(instance.tenant_id)
        workflow_instances_started_total.labels(
            workflow_name=instance.workflow_name,
            workflow_version=instance.workflow_version,
            tenant_id=tenant_id_str,
        ).inc()

        # Update gauge metrics
        workflow_instances_running.labels(
            workflow_name=instance.workflow_name,
            workflow_version=instance.workflow_version,
            tenant_id=tenant_id_str,
        ).inc()

        workflow_instances_pending.labels(
            workflow_name=instance.workflow_name,
            workflow_version=instance.workflow_version,
            tenant_id=tenant_id_str,
        ).dec()

        # Publish workflow.started event
        try:
            tenant_id_str_for_event = str(instance.tenant_id) if instance.tenant_id else None
            user_id_str = str(instance.created_by_id) if instance.created_by_id else None
            self.publish_workflow_started(
                workflow_instance_id=str(instance.id),
                workflow_name=instance.workflow_name,
                workflow_version=instance.workflow_version,
                input_data=instance.input_data,
                tenant_id=tenant_id_str_for_event,
                user_id=user_id_str,
            )
        except Exception as e:
            logger.warning(f"Failed to publish workflow.started event: {e}")

        # Publish ODPS workflow.started event if this is an ODPS workflow (Task 7.1.4)
        self._publish_odps_workflow_event_if_applicable(
            instance, "started",
            odps_version=self._extract_odps_version_from_input(instance.input_data),
            progress_percentage=instance.state_data.get("progress_percentage") if instance.state_data else None
        )

        logger.info(f"Started workflow instance: {instance.id}")
        return instance

    @transaction.atomic
    def execute_instance(self, instance_id: str) -> WorkflowInstance:
        """
        Execute workflow instance (run all steps).

        Args:
            instance_id: Workflow instance ID

        Returns:
            Updated WorkflowInstance
        """
        instance = WorkflowInstance.objects.select_for_update().get(id=instance_id)

        # Ensure instance is running
        if instance.status != WorkflowStatus.RUNNING:
            raise WorkflowExecutionError(
                f"Cannot execute workflow instance {instance_id}: status is {instance.status}"
            )

        # Start tracing span
        span = None
        if _tracer:
            span = _tracer.start_span(
                name=f"workflow.execute.{instance.workflow_name}",
                attributes={
                    "workflow.instance_id": str(instance.id),
                    "workflow.name": instance.workflow_name,
                    "workflow.version": instance.workflow_version,
                    "workflow.tenant_id": (
                        str(instance.tenant_id) if instance.tenant_id else "system"
                    ),
                },
            )

        execution_start_time = time.time()
        tenant_id_str = get_tenant_id(instance.tenant_id)

        try:
            # Execute steps sequentially
            dsl = instance.workflow_definition.dsl_json
            steps = dsl.get("steps", [])

            for i in range(instance.current_step_index, len(steps)):
                step_def = steps[i]
                step = instance.steps.get(step_index=i)

                # Publish ODPS creation progress event if this is an ODPS workflow (Task 7.3.2)
                if self._is_odps_workflow(instance.workflow_name):
                    self._publish_odps_creation_progress_if_applicable(
                        instance=instance,
                        step_index=i,
                        step_name=step_def.get("name", "unknown"),
                        total_steps=len(steps)
                    )

                # Execute step
                step_output = self._execute_step(instance, step, step_def)

                # Update workflow state with step output
                # Merge step output into state_data (excluding 'state' key which is for nested state)
                step_state = step_output.get("state", {})
                if step_state:
                    instance.state_data.update(step_state)
                # Also merge top-level step output keys into state_data
                for key, value in step_output.items():
                    if key != "state" and key != "output":
                        instance.state_data[key] = value

                instance.current_step_index = i + 1
                instance.save(update_fields=["current_step_index", "state_data", "updated_at"])

                # Publish ODPS creation progress event after step completion (Task 7.3.2)
                if self._is_odps_workflow(instance.workflow_name):
                    self._publish_odps_creation_progress_if_applicable(
                        instance=instance,
                        step_index=i + 1,
                        step_name=step_def.get("name", "unknown"),
                        total_steps=len(steps),
                        status_message=f"Step {step_def.get('name', 'unknown')} completed"
                    )

                # Check if step failed
                if step.status == StepStatus.FAILED:
                    # Handle step failure
                    result = self._handle_step_failure(instance, step)
                    self._record_execution_metrics(
                        instance, execution_start_time, tenant_id_str, span
                    )
                    return result

            # All steps completed successfully
            # Store final state in output_data
            instance.output_data = instance.state_data.copy()
            instance.mark_completed(output_data=instance.output_data)

            # Record success metrics
            execution_duration = time.time() - execution_start_time
            execution_duration_ms = int(execution_duration * 1000)
            workflow_instances_completed_total.labels(
                workflow_name=instance.workflow_name,
                workflow_version=instance.workflow_version,
                status="COMPLETED",
                tenant_id=tenant_id_str,
            ).inc()

            workflow_execution_duration_seconds.labels(
                workflow_name=instance.workflow_name,
                workflow_version=instance.workflow_version,
                status="COMPLETED",
                tenant_id=tenant_id_str,
            ).observe(execution_duration)

            # Update gauge metrics
            workflow_instances_running.labels(
                workflow_name=instance.workflow_name,
                workflow_version=instance.workflow_version,
                tenant_id=tenant_id_str,
            ).dec()

            # Record state size
            state_size = len(json.dumps(instance.state_data).encode("utf-8"))
            workflow_state_size_bytes.labels(
                workflow_name=instance.workflow_name,
                workflow_version=instance.workflow_version,
                tenant_id=tenant_id_str,
            ).observe(state_size)

            # Publish workflow.completed event
            try:
                tenant_id_str_for_event = str(instance.tenant_id) if instance.tenant_id else None
                user_id_str = str(instance.created_by_id) if instance.created_by_id else None
                self.publish_workflow_completed(
                    workflow_instance_id=str(instance.id),
                    workflow_name=instance.workflow_name,
                    output_data=instance.output_data,
                    duration_ms=execution_duration_ms,
                    tenant_id=tenant_id_str_for_event,
                    user_id=user_id_str,
                )
            except Exception as e:
                logger.warning(f"Failed to publish workflow.completed event: {e}")

            # Publish ODPS workflow.completed event if this is an ODPS workflow (Task 7.1.4)
            self._publish_odps_workflow_event_if_applicable(
                instance, "completed",
                output_data=instance.output_data,
                duration_ms=execution_duration_ms,
                odps_contract_id=instance.state_data.get("odps_contract_id") if instance.state_data else None,
                odcs_contract_id=instance.state_data.get("odcs_contract_id") if instance.state_data else None,
                progress_percentage=instance.state_data.get("progress_percentage") if instance.state_data else 100.0
            )

            if span:
                span.set_attribute("workflow.status", "COMPLETED")
                span.set_attribute("workflow.duration_seconds", execution_duration)
                span.set_attribute("workflow.steps_completed", instance.current_step_index)

            logger.info(f"Workflow instance completed: {instance.id}")

        except Exception as e:
            logger.exception(f"Error executing workflow instance {instance_id}: {str(e)}")
            instance.mark_failed(
                error_message=str(e), error_details={"exception_type": type(e).__name__}
            )
            self._record_execution_metrics(
                instance, execution_start_time, tenant_id_str, span, error=e
            )

            # Publish workflow.failed event
            try:
                tenant_id_str_for_event = str(instance.tenant_id) if instance.tenant_id else None
                user_id_str = str(instance.created_by_id) if instance.created_by_id else None
                self.publish_workflow_failed(
                    workflow_instance_id=str(instance.id),
                    workflow_name=instance.workflow_name,
                    error_message=str(e),
                    error_details={"exception_type": type(e).__name__},
                    failed_step_index=instance.current_step_index,
                    tenant_id=tenant_id_str_for_event,
                    user_id=user_id_str,
                )
            except Exception as e2:
                logger.warning(f"Failed to publish workflow.failed event: {e2}")

            # Publish ODPS workflow.failed event if this is an ODPS workflow (Task 7.1.4)
            self._publish_odps_workflow_event_if_applicable(
                instance, "failed",
                error_message=str(e),
                error_details={"exception_type": type(e).__name__},
                failed_step_index=instance.current_step_index,
                failed_step_name=instance.state_data.get("current_step_name") if instance.state_data else None,
                progress_percentage=instance.state_data.get("progress_percentage") if instance.state_data else None
            )
        finally:
            if span:
                span.end()

        return instance

    def _record_execution_metrics(
        self,
        instance: WorkflowInstance,
        start_time: float,
        tenant_id_str: str,
        span: Optional[Any] = None,
        error: Optional[Exception] = None,
    ):
        """Record execution metrics for workflow instance"""
        execution_duration = time.time() - start_time

        if instance.status == WorkflowStatus.FAILED:
            error_type = get_error_type(instance.error_details)
            workflow_instances_failed_total.labels(
                workflow_name=instance.workflow_name,
                workflow_version=instance.workflow_version,
                error_type=error_type,
                tenant_id=tenant_id_str,
            ).inc()

            workflow_execution_duration_seconds.labels(
                workflow_name=instance.workflow_name,
                workflow_version=instance.workflow_version,
                status="FAILED",
                tenant_id=tenant_id_str,
            ).observe(execution_duration)

            # Update gauge metrics
            workflow_instances_running.labels(
                workflow_name=instance.workflow_name,
                workflow_version=instance.workflow_version,
                tenant_id=tenant_id_str,
            ).dec()

            workflow_instances_failed_current.labels(
                workflow_name=instance.workflow_name,
                workflow_version=instance.workflow_version,
                tenant_id=tenant_id_str,
            ).inc()

            if span:
                span.set_attribute("workflow.status", "FAILED")
                span.set_attribute("workflow.error_type", error_type)
                span.set_attribute("workflow.duration_seconds", execution_duration)
                if error:
                    span.record_exception(error)

    def _execute_step(
        self, instance: WorkflowInstance, step: WorkflowStep, step_def: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a single workflow step.

        Args:
            instance: Workflow instance
            step: Workflow step model
            step_def: Step definition from DSL

        Returns:
            Step output data
        """
        # Check if step has a condition - if so, evaluate it before executing
        condition = step_def.get("condition")
        if condition:
            # Refresh instance to get latest state_data before evaluating condition
            instance.refresh_from_db()
            # Merge input_data and state_data for condition evaluation
            # (conditions may reference values from either)
            condition_context = {
                **instance.input_data,
                **instance.state_data
            }
            condition_result = self._evaluate_condition(condition, condition_context)
            logger.debug(
                f"Condition evaluation for step {step.step_name}: "
                f"condition={condition}, result={condition_result}, "
                f"context_keys={list(condition_context.keys())}, "
                f"auto_activate={condition_context.get('auto_activate')}, "
                f"auto_activate_type={type(condition_context.get('auto_activate'))}"
            )
            if not condition_result:
                # Condition is false - skip this step
                logger.info(
                    f"Skipping step {step.step_name} - condition evaluated to False "
                    f"(workflow_instance_id={instance.id}, condition={condition}, "
                    f"auto_activate={condition_context.get('auto_activate')}, "
                    f"auto_activate_type={type(condition_context.get('auto_activate'))})"
                )
                step.mark_skipped(reason="Condition evaluated to False")
                return {
                    "skipped": True,
                    "reason": "Condition evaluated to False",
                    "condition": condition
                }

        step.mark_started()

        # Calculate progress percentage for the step that's starting
        # Use a temporary instance state to calculate progress at this step index
        progress_percentage = self._calculate_progress(instance)

        # Store progress in WorkflowInstance.state_data
        if instance.state_data is None:
            instance.state_data = {}
        instance.state_data["progress_percentage"] = progress_percentage
        instance.state_data["current_step_index"] = step.step_index
        instance.state_data["current_step_name"] = step.step_name
        # Save the instance to persist progress in state_data
        instance.save(update_fields=["state_data"])

        # Publish ODPS workflow progress event if this is an ODPS workflow (Task 7.1.4)
        self._publish_odps_workflow_progress_if_applicable(instance, progress_percentage)

        # Record step started metric
        tenant_id_str = get_tenant_id(instance.tenant_id)
        workflow_steps_started_total.labels(
            workflow_name=instance.workflow_name,
            workflow_version=instance.workflow_version,
            step_name=step.step_name,
            step_type=step.step_type,
            tenant_id=tenant_id_str,
        ).inc()

        # Publish workflow.step.started event
        try:
            tenant_id_str_for_event = str(instance.tenant_id) if instance.tenant_id else None
            user_id_str = str(instance.created_by_id) if instance.created_by_id else None
            self.publish_workflow_step_started(
                workflow_instance_id=str(instance.id),
                step_index=step.step_index,
                step_name=step.step_name,
                step_type=step.step_type,
                progress_percentage=progress_percentage,
                tenant_id=tenant_id_str_for_event,
                user_id=user_id_str,
            )
        except Exception as e:
            logger.warning(f"Failed to publish workflow.step.started event: {e}")

        # Start tracing span for step
        step_span = None
        if _tracer:
            step_span = _tracer.start_span(
                name=f"workflow.step.{step.step_name}",
                attributes={
                    "workflow.instance_id": str(instance.id),
                    "workflow.name": instance.workflow_name,
                    "workflow.step.name": step.step_name,
                    "workflow.step.type": step.step_type,
                    "workflow.step.index": step.step_index,
                },
            )

        step_start_time = time.time()

        try:
            step_type = step_def.get("type", "task")

            if step_type == "task":
                output = self._execute_task_step(instance, step, step_def)
            elif step_type == "parallel":
                output = self._execute_parallel_step(instance, step, step_def)
            elif step_type == "conditional":
                output = self._execute_conditional_step(instance, step, step_def)
            elif step_type == "loop":
                output = self._execute_loop_step(instance, step, step_def)
            elif step_type == "retry":
                output = self._execute_retry_step(instance, step, step_def)
            else:
                raise WorkflowExecutionError(f"Unsupported step type: {step_type}")

            step.mark_completed(output_data=output)

            # Record step completed metrics
            step_duration = time.time() - step_start_time
            step_duration_ms = int(step_duration * 1000)
            workflow_steps_completed_total.labels(
                workflow_name=instance.workflow_name,
                workflow_version=instance.workflow_version,
                step_name=step.step_name,
                step_type=step.step_type,
                status="COMPLETED",
                tenant_id=tenant_id_str,
            ).inc()

            workflow_step_execution_duration_seconds.labels(
                workflow_name=instance.workflow_name,
                workflow_version=instance.workflow_version,
                step_name=step.step_name,
                step_type=step.step_type,
                status="COMPLETED",
                tenant_id=tenant_id_str,
            ).observe(step_duration)

            # Calculate progress percentage after step completion
            # Refresh instance to get updated current_step_index after step completion
            instance.refresh_from_db()
            progress_percentage_after = self._calculate_progress(instance)

            # Update progress in WorkflowInstance.state_data
            if instance.state_data is None:
                instance.state_data = {}
            instance.state_data["progress_percentage"] = progress_percentage_after
            instance.state_data["current_step_index"] = instance.current_step_index
            instance.state_data["current_step_name"] = step.step_name
            instance.save(update_fields=["state_data"])

            # Publish ODPS workflow progress event if this is an ODPS workflow (Task 7.1.4)
            self._publish_odps_workflow_progress_if_applicable(instance, progress_percentage_after)

            # Publish workflow.step.completed event
            try:
                tenant_id_str_for_event = str(instance.tenant_id) if instance.tenant_id else None
                user_id_str = str(instance.created_by_id) if instance.created_by_id else None
                self.publish_workflow_step_completed(
                    workflow_instance_id=str(instance.id),
                    step_index=step.step_index,
                    step_name=step.step_name,
                    output_data=output,
                    duration_ms=step_duration_ms,
                    progress_percentage=progress_percentage_after,
                    tenant_id=tenant_id_str_for_event,
                    user_id=user_id_str,
                )
            except Exception as e:
                logger.warning(f"Failed to publish workflow.step.completed event: {e}")

            # Publish ODPS workflow.step.completed event if this is an ODPS workflow (Task 7.1.4)
            self._publish_odps_workflow_step_event_if_applicable(
                instance, step, "completed",
                output_data=output,
                duration_ms=step_duration_ms,
                progress_percentage=progress_percentage_after
            )

            if step_span:
                step_span.set_attribute("workflow.step.status", "COMPLETED")
                step_span.set_attribute("workflow.step.duration_seconds", step_duration)

            return {"output": output, "state": output.get("state", {})}

        except Exception as e:
            logger.exception(f"Error executing step {step.step_name}: {str(e)}")
            step.mark_failed(
                error_message=str(e), error_details={"exception_type": type(e).__name__}
            )

            # Record step failed metrics
            step_duration = time.time() - step_start_time
            step_duration_ms = int(step_duration * 1000)
            error_type = get_error_type(step.error_details)
            workflow_steps_failed_total.labels(
                workflow_name=instance.workflow_name,
                workflow_version=instance.workflow_version,
                step_name=step.step_name,
                step_type=step.step_type,
                error_type=error_type,
                tenant_id=tenant_id_str,
            ).inc()

            workflow_step_execution_duration_seconds.labels(
                workflow_name=instance.workflow_name,
                workflow_version=instance.workflow_version,
                step_name=step.step_name,
                step_type=step.step_type,
                status="FAILED",
                tenant_id=tenant_id_str,
            ).observe(step_duration)

            # Calculate progress percentage at failure point
            # Refresh instance to get current state
            instance.refresh_from_db()
            progress_percentage_at_failure = self._calculate_progress(instance)

            # Update progress in WorkflowInstance.state_data
            if instance.state_data is None:
                instance.state_data = {}
            instance.state_data["progress_percentage"] = progress_percentage_at_failure
            instance.state_data["current_step_index"] = step.step_index
            instance.state_data["current_step_name"] = step.step_name
            instance.state_data["last_error"] = str(e)
            instance.save(update_fields=["state_data"])

            # Publish workflow.step.failed event
            try:
                tenant_id_str_for_event = str(instance.tenant_id) if instance.tenant_id else None
                user_id_str = str(instance.created_by_id) if instance.created_by_id else None
                self.publish_workflow_step_failed(
                    workflow_instance_id=str(instance.id),
                    step_index=step.step_index,
                    step_name=step.step_name,
                    error_message=str(e),
                    error_details={"exception_type": type(e).__name__},
                    retry_count=step.retry_count,
                    duration_ms=step_duration_ms,
                    progress_percentage=progress_percentage_at_failure,
                    tenant_id=tenant_id_str_for_event,
                    user_id=user_id_str,
                )
            except Exception as e2:
                logger.warning(f"Failed to publish workflow.step.failed event: {e2}")

            # Publish ODPS workflow.step.failed event if this is an ODPS workflow (Task 7.1.4)
            self._publish_odps_workflow_step_event_if_applicable(
                instance, step, "failed",
                error_message=str(e),
                error_details={"exception_type": type(e).__name__},
                retry_count=step.retry_count,
                duration_ms=step_duration_ms,
                progress_percentage=progress_percentage_at_failure
            )

            if step_span:
                step_span.set_attribute("workflow.step.status", "FAILED")
                step_span.set_attribute("workflow.step.error_type", error_type)
                step_span.set_attribute("workflow.step.duration_seconds", step_duration)
                step_span.record_exception(e)

            raise
        finally:
            if step_span:
                step_span.end()

    def _execute_task_step(
        self, instance: WorkflowInstance, step: WorkflowStep, step_def: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a task step"""
        task_name = step_def.get("task")
        if not task_name:
            raise WorkflowExecutionError(f"Step {step.step_name} missing 'task' field")

        # Get task function
        task_func = self.task_registry.get(task_name)
        if not task_func:
            raise WorkflowExecutionError(f"Task not found: {task_name}")

        # Prepare task input by merging:
        # 1. Workflow input_data (initial input)
        # 2. Workflow state_data (accumulated state from previous steps)
        # 3. Step-specific input_data (from step model)
        # 4. Step definition input (from DSL)
        # Refresh instance to get latest state_data
        instance.refresh_from_db()
        task_input = {
            **instance.input_data,
            **instance.state_data,
            **step.input_data,
            **step_def.get("input", {}),
        }

        # Execute task
        result = task_func(task_input, instance, step)

        return result if isinstance(result, dict) else {"result": result}

    def _execute_parallel_step(
        self, instance: WorkflowInstance, step: WorkflowStep, step_def: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a parallel step"""
        # For now, execute sequentially (can be enhanced with threading/async)
        parallel_steps = step_def.get("steps", [])
        results = []

        for parallel_step_def in parallel_steps:
            # Create temporary step for parallel execution
            temp_step = WorkflowStep(
                workflow_instance=instance,
                step_index=step.step_index,
                step_name=parallel_step_def.get("name", "parallel_step"),
                step_type=parallel_step_def.get("type", "task"),
                status=StepStatus.PENDING,
            )
            result = self._execute_step(instance, temp_step, parallel_step_def)
            results.append(result)

        return {"results": results}

    def _execute_conditional_step(
        self, instance: WorkflowInstance, step: WorkflowStep, step_def: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a conditional step"""
        condition = step_def.get("condition")
        if not condition:
            raise WorkflowExecutionError(f"Step {step.step_name} missing 'condition' field")

        # Evaluate condition (simplified - can be enhanced with expression evaluator)
        condition_result = self._evaluate_condition(condition, instance.state_data)

        if condition_result:
            then_steps = step_def.get("then", [])
            for sub_index, then_step_def in enumerate(then_steps):
                # Use a unique sub-index to avoid unique constraint violations
                # Use step_index * 1000 + sub_index to ensure uniqueness
                temp_step_index = step.step_index * 1000 + sub_index
                # Check if step already exists (e.g., from a retry)
                temp_step, created = WorkflowStep.objects.get_or_create(
                    workflow_instance=instance,
                    step_index=temp_step_index,
                    defaults={
                        'step_name': then_step_def.get("name", "then_step"),
                        'step_type': then_step_def.get("type", "task"),
                        'status': StepStatus.PENDING,
                    }
                )
                # If step already exists and is completed/failed, skip it
                if not created and temp_step.is_terminal():
                    continue
                self._execute_step(instance, temp_step, then_step_def)
        else:
            else_steps = step_def.get("else", [])
            for sub_index, else_step_def in enumerate(else_steps):
                # Use a unique sub-index to avoid unique constraint violations
                # Use step_index * 1000 + 500 + sub_index to ensure uniqueness from then steps
                temp_step_index = step.step_index * 1000 + 500 + sub_index
                # Check if step already exists (e.g., from a retry)
                temp_step, created = WorkflowStep.objects.get_or_create(
                    workflow_instance=instance,
                    step_index=temp_step_index,
                    defaults={
                        'step_name': else_step_def.get("name", "else_step"),
                        'step_type': else_step_def.get("type", "task"),
                        'status': StepStatus.PENDING,
                    }
                )
                # If step already exists and is completed/failed, skip it
                if not created and temp_step.is_terminal():
                    continue
                self._execute_step(instance, temp_step, else_step_def)

        return {"condition_result": condition_result}

    def _execute_loop_step(
        self, instance: WorkflowInstance, step: WorkflowStep, step_def: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a loop step"""
        items = step_def.get("items", [])
        loop_steps = step_def.get("steps", [])
        results = []

        # Support dynamic items from state_data (if items is a string starting with ${)
        if isinstance(items, str) and items.startswith("${") and items.endswith("}"):
            # Extract field name from ${field_name}
            field_name = items[2:-1]
            items = instance.state_data.get(field_name, [])
            if not isinstance(items, list):
                raise WorkflowExecutionError(
                    f"Loop items field '{field_name}' must be a list, got {type(items)}"
                )

        for loop_index, item in enumerate(items):
            # Add item to state for loop steps
            instance.state_data["loop_item"] = item
            instance.save(update_fields=["state_data"])

            for sub_index, loop_step_def in enumerate(loop_steps):
                # Use a unique sub-index to avoid unique constraint violations
                # Use step_index * 10000 + loop_index * 100 + sub_index to ensure uniqueness
                temp_step_index = step.step_index * 10000 + loop_index * 100 + sub_index
                # Check if step already exists (e.g., from a retry)
                temp_step, created = WorkflowStep.objects.get_or_create(
                    workflow_instance=instance,
                    step_index=temp_step_index,
                    defaults={
                        'step_name': loop_step_def.get("name", "loop_step"),
                        'step_type': loop_step_def.get("type", "task"),
                        'status': StepStatus.PENDING,
                    }
                )
                # If step already exists and is completed/failed, skip it
                if not created and temp_step.is_terminal():
                    continue
                result = self._execute_step(instance, temp_step, loop_step_def)
                results.append(result)

        return {"results": results}

    def _execute_retry_step(
        self, instance: WorkflowInstance, step: WorkflowStep, step_def: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a retry step"""
        max_retries = step_def.get("max_retries", 3)
        retry_steps = step_def.get("steps", [])

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                results = []
                for retry_step_def in retry_steps:
                    temp_step = WorkflowStep(
                        workflow_instance=instance,
                        step_index=step.step_index,
                        step_name=retry_step_def.get("name", "retry_step"),
                        step_type=retry_step_def.get("type", "task"),
                        status=StepStatus.PENDING,
                    )
                    result = self._execute_step(instance, temp_step, retry_step_def)
                    results.append(result)

                return {"results": results, "attempts": attempt + 1}

            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    logger.warning(f"Retry step attempt {attempt + 1} failed, retrying...")
                else:
                    raise

        raise WorkflowExecutionError(
            f"Retry step failed after {max_retries} attempts: {last_error}"
        )

    def _evaluate_condition(self, condition: Any, state_data: Dict[str, Any]) -> bool:
        """
        Evaluate a condition expression.

        Args:
            condition: Condition expression (can be dict with operator, or simple value)
            state_data: Workflow state data (or merged input_data + state_data)

        Returns:
            Condition evaluation result
        """
        # Simplified condition evaluation
        # Can be enhanced with a proper expression evaluator
        if isinstance(condition, dict):
            # Support template string format: {"if": "{{ field == value }}" or "{{ field != null }}"}
            if "if" in condition:
                if_str = condition["if"]
                import re

                # Pattern 1: Equality comparison: "{{ auto_activate == true }}"
                match = re.match(r'\{\{\s*(\w+)\s*==\s*(\w+)\s*\}\}', if_str)
                if match:
                    field_name = match.group(1)
                    value_str = match.group(2)
                    # Convert value string to appropriate type
                    if value_str.lower() == "true":
                        value = True
                    elif value_str.lower() == "false":
                        value = False
                    elif value_str.isdigit():
                        value = int(value_str)
                    else:
                        value = value_str
                    field_value = state_data.get(field_name)
                    logger.debug(
                        f"Condition evaluation: field_name={field_name}, "
                        f"value_str={value_str}, value={value}, "
                        f"field_value={field_value}, field_value_type={type(field_value)}, "
                        f"result={field_value == value}"
                    )
                    return field_value == value

                # Pattern 2: Not null check: "{{ field != null }}" or "{{ field != null && ... }}"
                match = re.match(r'\{\{\s*(\w+)\s*!=\s*null\s*\}\}', if_str)
                if match:
                    field_name = match.group(1)
                    field_value = state_data.get(field_name)
                    return field_value is not None and field_value != ""

                # Pattern 3: Complex condition with &&: "{{ field1 != null && field2 != 'VALUE' }}"
                # Handle && conditions by extracting field names and operators from template syntax
                if '&&' in if_str:
                    # Remove outer {{ }} and split by &&
                    inner = if_str.strip()
                    if inner.startswith('{{'):
                        inner = inner[2:].strip()
                    if inner.endswith('}}'):
                        inner = inner[:-2].strip()

                    parts = [p.strip() for p in inner.split('&&')]
                    results = []
                    for part in parts:
                        # Check for != null (without {{ }} wrapper since we already removed it)
                        match = re.match(r'(\w+)\s*!=\s*null', part)
                        if match:
                            field_name = match.group(1)
                            field_value = state_data.get(field_name)
                            results.append(field_value is not None and field_value != "")
                            continue
                        # Check for == null
                        match = re.match(r'(\w+)\s*==\s*null', part)
                        if match:
                            field_name = match.group(1)
                            field_value = state_data.get(field_name)
                            results.append(field_value is None or field_value == "")
                            continue
                        # Check for != 'value'
                        match = re.match(r'(\w+)\s*!=\s*[\'"](\w+)[\'"]', part)
                        if match:
                            field_name = match.group(1)
                            expected_value = match.group(2)
                            field_value = state_data.get(field_name)
                            results.append(str(field_value) != expected_value)
                            continue
                        # Check for == comparison
                        match = re.match(r'(\w+)\s*==\s*(\w+)', part)
                        if match:
                            field_name = match.group(1)
                            expected_value = match.group(2)
                            field_value = state_data.get(field_name)
                            # Convert value string to appropriate type
                            if expected_value.lower() == "true":
                                expected_value = True
                            elif expected_value.lower() == "false":
                                expected_value = False
                            elif expected_value.isdigit():
                                expected_value = int(expected_value)
                            results.append(field_value == expected_value)
                            continue
                        # If no pattern matches, default to False
                        results.append(False)
                    # All parts must be true for && condition
                    return all(results) if results else False

                # Fallback: unsupported format
                logger.warning(f"Unsupported condition format: {if_str}")
                return False

            # Support operator-based format: {"operator": "equals", "field": "auto_activate", "value": True}
            operator = condition.get("operator")
            field = condition.get("field")
            value = condition.get("value")

            if operator == "equals":
                return state_data.get(field) == value
            elif operator == "not_equals":
                return state_data.get(field) != value
            elif operator == "exists":
                return field in state_data
            else:
                raise WorkflowExecutionError(f"Unsupported condition operator: {operator}")
        else:
            # Simple boolean condition
            return bool(condition)

    def _handle_step_failure(
        self, instance: WorkflowInstance, failed_step: WorkflowStep
    ) -> WorkflowInstance:
        """
        Handle workflow step failure.

        Args:
            instance: Workflow instance
            failed_step: Failed workflow step

        Returns:
            Updated WorkflowInstance
        """
        tenant_id_str = get_tenant_id(instance.tenant_id)

        # Check if compensation is enabled
        dsl = instance.workflow_definition.dsl_json
        compensation_enabled = dsl.get("compensation", {}).get("enabled", False)

        if compensation_enabled:
            # Record compensation triggered metric
            workflow_compensations_triggered_total.labels(
                workflow_name=instance.workflow_name,
                workflow_version=instance.workflow_version,
                failed_step_name=failed_step.step_name,
                tenant_id=tenant_id_str,
            ).inc()

            # Start tracing span for compensation
            comp_span = None
            if _tracer:
                comp_span = _tracer.start_span(
                    name=f"workflow.compensation.{instance.workflow_name}",
                    attributes={
                        "workflow.instance_id": str(instance.id),
                        "workflow.name": instance.workflow_name,
                        "workflow.failed_step": failed_step.step_name,
                    },
                )

            comp_start_time = time.time()

            try:
                # Rollback workflow
                result = self.compensation.rollback_workflow(instance, failed_step)

                # Record compensation completed metric
                comp_duration = time.time() - comp_start_time
                workflow_compensations_completed_total.labels(
                    workflow_name=instance.workflow_name,
                    workflow_version=instance.workflow_version,
                    status="COMPLETED",
                    tenant_id=tenant_id_str,
                ).inc()

                workflow_compensation_duration_seconds.labels(
                    workflow_name=instance.workflow_name,
                    workflow_version=instance.workflow_version,
                    status="COMPLETED",
                    tenant_id=tenant_id_str,
                ).observe(comp_duration)

                if comp_span:
                    comp_span.set_attribute("workflow.compensation.status", "COMPLETED")
                    comp_span.set_attribute("workflow.compensation.duration_seconds", comp_duration)

                return result
            except Exception as e:
                # Record compensation failure
                comp_duration = time.time() - comp_start_time
                workflow_compensations_completed_total.labels(
                    workflow_name=instance.workflow_name,
                    workflow_version=instance.workflow_version,
                    status="FAILED",
                    tenant_id=tenant_id_str,
                ).inc()

                workflow_compensation_duration_seconds.labels(
                    workflow_name=instance.workflow_name,
                    workflow_version=instance.workflow_version,
                    status="FAILED",
                    tenant_id=tenant_id_str,
                ).observe(comp_duration)

                if comp_span:
                    comp_span.set_attribute("workflow.compensation.status", "FAILED")
                    comp_span.set_attribute("workflow.compensation.duration_seconds", comp_duration)
                    comp_span.record_exception(e)
                raise
            finally:
                if comp_span:
                    comp_span.end()
        else:
            # Mark workflow as failed
            instance.mark_failed(
                error_message=f"Step {failed_step.step_name} failed: {failed_step.error_message}",
                error_details={
                    "failed_step_index": failed_step.step_index,
                    "failed_step_name": failed_step.step_name,
                    "error_details": failed_step.error_details,
                },
            )
            return instance

    @transaction.atomic
    def retry_instance(self, instance_id: str) -> WorkflowInstance:
        """
        Retry a failed workflow instance.

        Args:
            instance_id: Workflow instance ID

        Returns:
            Updated WorkflowInstance
        """
        instance = WorkflowInstance.objects.select_for_update().get(id=instance_id)

        if not instance.can_retry():
            raise WorkflowExecutionError(
                f"Cannot retry workflow instance {instance_id}: "
                f"status={instance.status}, retry_count={instance.retry_count}, "
                f"max_retries={instance.max_retries}"
            )

        # Record retry metric
        tenant_id_str = get_tenant_id(instance.tenant_id)
        workflow_instances_retried_total.labels(
            workflow_name=instance.workflow_name,
            workflow_version=instance.workflow_version,
            retry_count=str(instance.retry_count + 1),
            tenant_id=tenant_id_str,
        ).inc()

        # Update gauge metrics
        workflow_instances_failed_current.labels(
            workflow_name=instance.workflow_name,
            workflow_version=instance.workflow_version,
            tenant_id=tenant_id_str,
        ).dec()

        workflow_instances_running.labels(
            workflow_name=instance.workflow_name,
            workflow_version=instance.workflow_version,
            tenant_id=tenant_id_str,
        ).inc()

        # Reset instance state
        instance.status = WorkflowStatus.RUNNING
        instance.retry_count += 1
        instance.error_message = None
        instance.error_details = None
        instance.save(
            update_fields=["status", "retry_count", "error_message", "error_details", "updated_at"]
        )

        # Reset failed steps
        failed_steps = instance.steps.filter(status=StepStatus.FAILED)
        for step in failed_steps:
            step.status = StepStatus.PENDING
            step.error_message = None
            step.error_details = None
            step.save(update_fields=["status", "error_message", "error_details"])

            # Record step retry metric
            workflow_steps_retried_total.labels(
                workflow_name=instance.workflow_name,
                workflow_version=instance.workflow_version,
                step_name=step.step_name,
                step_type=step.step_type,
                retry_count=str(step.retry_count + 1),
                tenant_id=tenant_id_str,
            ).inc()

        logger.info(f"Retrying workflow instance: {instance.id} (attempt {instance.retry_count})")
        return self.execute_instance(instance_id)

    def _calculate_progress(
        self, instance: WorkflowInstance
    ) -> float:
        """
        Calculate workflow execution progress percentage.

        Formula: progress_percentage = (current_step_index + 1) / total_steps * 100

        Edge cases handled:
        - If total_steps = 0: Returns 0.0 (no steps to execute)
        - If current_step_index = -1: Returns 0.0 (not started)
        - If current_step_index >= total_steps: Returns 100.0 (completed or beyond)

        Args:
            instance: WorkflowInstance to calculate progress for

        Returns:
            Progress percentage as float (0.0 to 100.0)

        Example:
            >>> progress = engine._calculate_progress(instance)
            >>> print(f"Progress: {progress}%")
            Progress: 50.0%
        """
        # Get total number of steps from workflow definition
        dsl = instance.workflow_definition.dsl_json
        steps = dsl.get("steps", [])
        total_steps = len(steps)

        # Handle edge case: no steps defined
        if total_steps == 0:
            return 0.0

        # Get current step index (0-based)
        current_step_index = instance.current_step_index

        # Handle edge case: not started (current_step_index = -1 or 0 before any step)
        # If current_step_index is -1, workflow hasn't started
        if current_step_index < 0:
            return 0.0

        # Handle edge case: completed or beyond (current_step_index >= total_steps)
        # When all steps are done, current_step_index equals total_steps
        if current_step_index >= total_steps:
            return 100.0

        # Calculate progress: (current_step_index + 1) / total_steps * 100
        # Adding 1 because current_step_index is 0-based, and we want to count
        # the current step as progress (e.g., step 0 of 2 = 50%, not 0%)
        progress_percentage = ((current_step_index + 1) / total_steps) * 100.0

        # Ensure result is between 0.0 and 100.0
        return max(0.0, min(100.0, progress_percentage))

    def _is_odps_workflow(self, workflow_name: str) -> bool:
        """
        Check if a workflow is an ODPS workflow (Task 7.1.4).

        Args:
            workflow_name: Workflow name to check

        Returns:
            True if workflow is an ODPS workflow, False otherwise
        """
        return workflow_name in self._odps_workflow_names

    def _extract_odps_version_from_input(self, input_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract ODPS version from workflow input data (Task 7.1.4).

        Args:
            input_data: Workflow input data

        Returns:
            ODPS version string or None if not found
        """
        # Try to get ODPS version from various possible locations
        if not input_data:
            return None

        # Check direct odps_version field
        if "odps_version" in input_data:
            return input_data.get("odps_version")

        # Check state_data if it's nested
        state_data = input_data.get("state_data")
        if state_data and isinstance(state_data, dict):
            if "odps_version" in state_data:
                return state_data.get("odps_version")

        # Try to extract from original_raw if it's an ODPS document
        if "original_raw" in input_data:
            try:
                import json
                raw_content = input_data["original_raw"]
                if isinstance(raw_content, str):
                    doc = json.loads(raw_content)
                    if isinstance(doc, dict):
                        # Check for ODPS schema/version fields
                        if "version" in doc:
                            return doc.get("version")
                        if "schema" in doc:
                            schema = doc.get("schema", "")
                            if "v4.1" in schema or "v4.0" in schema:
                                return "4.1"
            except Exception:
                pass

        return None

    def _get_odps_event_publisher(self, instance: WorkflowInstance) -> Optional[ODPSEventPublisher]:
        """
        Get ODPSEventPublisher instance for ODPS workflow event publishing (Task 7.1.4).

        Args:
            instance: Workflow instance

        Returns:
            ODPSEventPublisher instance or None if not applicable
        """
        if not self._is_odps_workflow(instance.workflow_name):
            return None

        try:
            # Create ODPSEventPublisher instance
            odps_publisher = ODPSEventPublisher()
            tenant_id_str = str(instance.tenant_id) if instance.tenant_id else None
            user_id_str = str(instance.created_by_id) if instance.created_by_id else None

            # Initialize event publisher with correct tenant/user
            from hub.apps.core.events.publisher import EventPublisher
            odps_publisher._event_publisher = EventPublisher(
                service_name="workflow_engine",
                tenant_id=tenant_id_str,
                user_id=user_id_str,
            )

            return odps_publisher
        except Exception as e:
            logger.warning(f"Failed to create ODPSEventPublisher: {e}")
            return None

    def _publish_odps_workflow_event_if_applicable(
        self,
        instance: WorkflowInstance,
        event_type: str,
        **kwargs
    ) -> None:
        """
        Publish ODPS workflow event if this is an ODPS workflow (Task 7.1.4).

        Args:
            instance: Workflow instance
            event_type: Event type ("started", "completed", "failed")
            **kwargs: Additional event data
        """
        if not self._is_odps_workflow(instance.workflow_name):
            return

        odps_publisher = self._get_odps_event_publisher(instance)
        if not odps_publisher:
            return

        try:
            tenant_id_str = str(instance.tenant_id) if instance.tenant_id else None
            user_id_str = str(instance.created_by_id) if instance.created_by_id else None

            if event_type == "started":
                odps_publisher.publish_odps_workflow_started(
                    workflow_instance_id=str(instance.id),
                    workflow_name=instance.workflow_name,
                    workflow_version=instance.workflow_version,
                    input_data=instance.input_data,
                    odps_version=kwargs.get("odps_version"),
                    progress_percentage=kwargs.get("progress_percentage"),
                    tenant_id=tenant_id_str,
                    user_id=user_id_str,
                )
            elif event_type == "completed":
                odps_publisher.publish_odps_workflow_completed(
                    workflow_instance_id=str(instance.id),
                    workflow_name=instance.workflow_name,
                    workflow_version=instance.workflow_version,
                    output_data=kwargs.get("output_data"),
                    duration_ms=kwargs.get("duration_ms"),
                    odps_contract_id=kwargs.get("odps_contract_id"),
                    odcs_contract_id=kwargs.get("odcs_contract_id"),
                    progress_percentage=kwargs.get("progress_percentage"),
                    tenant_id=tenant_id_str,
                    user_id=user_id_str,
                )
            elif event_type == "failed":
                odps_publisher.publish_odps_workflow_failed(
                    workflow_instance_id=str(instance.id),
                    workflow_name=instance.workflow_name,
                    error_message=kwargs.get("error_message", "Unknown error"),
                    workflow_version=instance.workflow_version,
                    error_details=kwargs.get("error_details"),
                    failed_step_index=kwargs.get("failed_step_index"),
                    failed_step_name=kwargs.get("failed_step_name"),
                    progress_percentage=kwargs.get("progress_percentage"),
                    tenant_id=tenant_id_str,
                    user_id=user_id_str,
                )
        except Exception as e:
            logger.warning(f"Failed to publish ODPS workflow.{event_type} event: {e}")

    def _publish_odps_workflow_step_event_if_applicable(
        self,
        instance: WorkflowInstance,
        step: WorkflowStep,
        event_type: str,
        **kwargs
    ) -> None:
        """
        Publish ODPS workflow step event if this is an ODPS workflow (Task 7.1.4).

        Args:
            instance: Workflow instance
            step: Workflow step
            event_type: Event type ("completed", "failed")
            **kwargs: Additional event data
        """
        if not self._is_odps_workflow(instance.workflow_name):
            return

        odps_publisher = self._get_odps_event_publisher(instance)
        if not odps_publisher:
            return

        try:
            tenant_id_str = str(instance.tenant_id) if instance.tenant_id else None
            user_id_str = str(instance.created_by_id) if instance.created_by_id else None

            # Extract ODPS version from step output or state
            odps_version = None
            if instance.state_data:
                odps_version = instance.state_data.get("odps_version")
            if not odps_version and kwargs.get("output_data"):
                odps_version = kwargs.get("output_data", {}).get("odps_version")

            if event_type == "completed":
                odps_publisher.publish_odps_workflow_step_completed(
                    workflow_instance_id=str(instance.id),
                    step_index=step.step_index,
                    step_name=step.step_name,
                    step_type=step.step_type,
                    output_data=kwargs.get("output_data"),
                    duration_ms=kwargs.get("duration_ms"),
                    progress_percentage=kwargs.get("progress_percentage"),
                    odps_version=odps_version,
                    tenant_id=tenant_id_str,
                    user_id=user_id_str,
                )
            elif event_type == "failed":
                odps_publisher.publish_odps_workflow_step_failed(
                    workflow_instance_id=str(instance.id),
                    step_index=step.step_index,
                    step_name=step.step_name,
                    error_message=kwargs.get("error_message", "Unknown error"),
                    error_details=kwargs.get("error_details"),
                    retry_count=kwargs.get("retry_count"),
                    duration_ms=kwargs.get("duration_ms"),
                    progress_percentage=kwargs.get("progress_percentage"),
                    tenant_id=tenant_id_str,
                    user_id=user_id_str,
                )
        except Exception as e:
            logger.warning(f"Failed to publish ODPS workflow.step.{event_type} event: {e}")

    def _publish_odps_workflow_progress_if_applicable(
        self,
        instance: WorkflowInstance,
        progress_percentage: float
    ) -> None:
        """
        Publish ODPS workflow progress event if this is an ODPS workflow (Task 7.1.4).

        Args:
            instance: Workflow instance
            progress_percentage: Current progress percentage
        """
        if not self._is_odps_workflow(instance.workflow_name):
            return

        odps_publisher = self._get_odps_event_publisher(instance)
        if not odps_publisher:
            return

        try:
            tenant_id_str = str(instance.tenant_id) if instance.tenant_id else None
            user_id_str = str(instance.created_by_id) if instance.created_by_id else None

            # Get total steps from workflow definition
            dsl = instance.workflow_definition.dsl_json
            steps = dsl.get("steps", [])
            total_steps = len(steps)

            odps_publisher.publish_odps_workflow_progress(
                workflow_instance_id=str(instance.id),
                workflow_name=instance.workflow_name,
                progress_percentage=progress_percentage,
                workflow_version=instance.workflow_version,
                current_step_index=instance.current_step_index,
                current_step_name=instance.state_data.get("current_step_name") if instance.state_data else None,
                total_steps=total_steps,
                tenant_id=tenant_id_str,
                user_id=user_id_str,
            )
        except Exception as e:
            logger.warning(f"Failed to publish ODPS workflow.progress event: {e}")

    def _publish_odps_creation_progress_if_applicable(
        self,
        instance: WorkflowInstance,
        step_index: int,
        step_name: str,
        total_steps: int,
        status_message: Optional[str] = None
    ) -> None:
        """
        Publish ODPS creation progress event if this is an ODPS workflow (Task 7.3.2).

        Args:
            instance: Workflow instance
            step_index: Current step index (0-based)
            step_name: Current step name
            total_steps: Total number of steps
            status_message: Optional status message
        """
        if not self._is_odps_workflow(instance.workflow_name):
            return

        odps_publisher = self._get_odps_event_publisher(instance)
        if not odps_publisher:
            return

        try:
            tenant_id_str = str(instance.tenant_id) if instance.tenant_id else None
            user_id_str = str(instance.created_by_id) if instance.created_by_id else None

            # Calculate progress percentage
            progress_percentage = ((step_index + 1) / total_steps * 100.0) if total_steps > 0 else 0.0

            # Get contract ID from state if available
            contract_id = None
            if instance.state_data:
                contract_id = instance.state_data.get("odps_contract_id") or instance.state_data.get("contract_id")

            odps_publisher.publish_odps_creation_progress(
                contract_id=contract_id,
                workflow_instance_id=str(instance.id),
                progress_percentage=progress_percentage,
                current_step=step_name,
                total_steps=total_steps,
                step_index=step_index,
                status_message=status_message,
                tenant_id=tenant_id_str,
                user_id=user_id_str,
            )
        except Exception as e:
            logger.warning(f"Failed to publish ODPS creation.progress event: {e}")
