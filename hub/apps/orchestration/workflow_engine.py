"""
Workflow Execution Engine

Core workflow execution engine with step execution, retry logic, and error handling.
Includes metrics and tracing for observability.
"""

import hashlib
import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Set

import structlog
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from hub.apps.core.events.service_publishers import ODPSEventPublisher, WorkflowEventPublisher
from hub.apps.core.services.base import ValidationError as ServiceValidationError

from .business_rules import OrchestrationBusinessRules, OrchestrationRuleExecutionContext
from .compensation import WorkflowCompensation
from .dsl_parser import WorkflowDSLParser
from .feature_flags import is_business_rules_validation_enabled
from .metrics import (
    get_error_type,
    get_tenant_id,
    workflow_business_rules_validation_cache_hits_total,
    workflow_business_rules_validation_cache_misses_total,
    workflow_business_rules_validation_duration_seconds,
    workflow_business_rules_validations_total,
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

logger = structlog.get_logger(__name__)

# === CHECKPOINT: Business-rules validation caching + warnings persistence (2026-01-28) ===

# Try to import OpenTelemetry tracing
try:
    from hub.apps.observability.tracing import get_tracer

    _tracer = get_tracer(__name__)
except ImportError:
    _tracer = None


class ControlledWorkflowException(Exception):
    """Marker for exceptions that represent an expected / controlled
    business outcome rather than an unanticipated system fault.

    Step failures derived from this marker are logged at WARNING level
    (they are normal domain rejections, timeouts, or validation
    failures).  Everything else continues to log at ERROR level because
    it represents an unhandled code path or infrastructure problem.

    Subclasses:
      * ``FailClosedRejection`` — gate refused intake (by design)
      * ``WorkflowDeadlineExceeded`` — wall-clock cap (by design)
      * ``WorkflowStepValueError`` — domain rejection from a task
        (file not found in storage, invalid input, etc.)
    """


class WorkflowStepValueError(ControlledWorkflowException, ValueError):
    """A ``ValueError`` raised by a workflow step that represents a
    controlled domain rejection (e.g. file missing from storage,
    unsupported format, missing required field), not an unanticipated
    system fault.

    Inherits from both ``ControlledWorkflowException`` (so the engine
    logs at WARNING) and ``ValueError`` (so existing ``except
    ValueError`` handlers continue to work without modification).
    """


class WorkflowExecutionError(Exception):
    """Workflow execution error"""

    pass


class WorkflowEngine(WorkflowEventPublisher):
    """
    Workflow execution engine.

    Executes workflow instances, manages step execution, retries, and error handling.
    """

    def __init__(
        self,
        step_failure_injector: Optional[Callable[[int, str], None]] = None,
        compensation_observer: Optional[Callable[[str], None]] = None,
    ):
        super().__init__()
        self.dsl_parser = WorkflowDSLParser()
        self.version_manager = WorkflowVersionManager()
        self.task_registry: Dict[str, Callable] = {}
        self.compensation = WorkflowCompensation(
            task_registry=self.task_registry,
            compensation_observer=compensation_observer,
        )
        # Track registered task names to avoid duplicate registrations
        self._registered_task_names: Set[str] = set()
        # Phase 250.1.A test-mode hook — only set during property-based testing.
        self._step_failure_injector = step_failure_injector

        # ODPS workflows that should publish ODPS-specific events (Task 7.1.4)
        self._odps_workflow_names = {"product_creation"}

    def register_task(self, task_name: str, task_func: Callable):
        """
        Register a task function for workflow execution (idempotent).

        Args:
            task_name: Task identifier (matches 'task' field in workflow DSL)
            task_func: Task function to execute
        """
        # Skip if already registered (idempotent)
        if task_name in self._registered_task_names:
            logger.debug("Task already registered, skipping", task_name=task_name)
            return

        self.task_registry[task_name] = task_func
        self._registered_task_names.add(task_name)
        logger.info("Registered task", task_name=task_name)

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

        # Defensive: the cached definition may reference a row that was
        # truncated/rolled-back by a prior test.  Force a DB refresh so
        # we fail early with a clear error rather than hitting a FK
        # violation on WorkflowInstance insert.
        try:
            workflow_def.refresh_from_db()
        except Exception:
            raise WorkflowExecutionError(
                f"Workflow definition {workflow_name!r} exists in the "
                f"process cache but its DB row is gone (likely a stale "
                f"cache entry from a rolled-back transaction)."
            )

        # Create workflow instance
        # Convert tenant_id to Tenant object if provided
        tenant_obj = None
        if tenant_id:
            from hub.apps.core.services.base import ValidationError as ServiceValidationError
            from hub.apps.tenants.models import Tenant
            from hub.apps.tenants.services import get_tenant_config_value

            try:
                tenant_obj = Tenant.objects.get(id=tenant_id)
            except Tenant.DoesNotExist:
                logger.warning(
                    "Tenant not found, creating workflow without tenant", tenant_id=tenant_id
                )
            else:
                # Phase 14: Enforce workflows_enabled when tenant has config
                workflows_enabled = get_tenant_config_value(
                    tenant_obj, "workflows_enabled", default=True
                )
                if not workflows_enabled:
                    raise ServiceValidationError(
                        "Workflows are disabled for this tenant.",
                        code="WORKFLOWS_DISABLED",
                        http_status=403,
                    )

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

        logger.info(
            "Created workflow instance",
            workflow_instance_id=str(instance.id),
            workflow_name=workflow_name,
        )

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
            logger.warning("Failed to publish workflow.created event", error=str(e), exc_info=True)

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
        # Use skip_locked to avoid blocking on concurrent access attempts
        instance = WorkflowInstance.objects.select_for_update(skip_locked=True).get(id=instance_id)

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
            logger.warning("Failed to publish workflow.started event", error=str(e), exc_info=True)

        # Publish ODPS workflow.started event if this is an ODPS workflow (Task 7.1.4)
        self._publish_odps_workflow_event_if_applicable(
            instance,
            "started",
            odps_version=self._extract_odps_version_from_input(instance.input_data),
            progress_percentage=(
                instance.state_data.get("progress_percentage") if instance.state_data else None
            ),
        )

        logger.info("Started workflow instance", workflow_instance_id=str(instance.id))
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
        # Use skip_locked to avoid blocking on concurrent access attempts
        # This allows multiple workers to process different workflows concurrently
        instance = WorkflowInstance.objects.select_for_update(skip_locked=True).get(id=instance_id)

        # Ensure instance is running
        if instance.status != WorkflowStatus.RUNNING:
            raise WorkflowExecutionError(
                f"Cannot execute workflow instance {instance_id}: status is {instance.status}"
            )

        # Start tracing span and set as current so child spans (step, validation) share trace_id
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

        def _optional_span_context(active_span):
            """Context manager that sets span as current when non-None (so child spans share trace)."""
            if active_span is None:
                from contextlib import nullcontext

                return nullcontext()
            from opentelemetry import trace

            return trace.use_span(active_span, end_on_exit=False)

        try:
            with _optional_span_context(span):
                # Execute steps sequentially
                dsl = instance.workflow_definition.dsl_json
                steps = dsl.get("steps", [])

                for i in range(instance.current_step_index, len(steps)):
                    # Note: We don't refresh_from_db() here because:
                    # 1. We're already in a transaction with select_for_update lock
                    # 2. We merge step outputs into state_data in memory (lines 342-355)
                    # 3. We save state_data after each step (line 363)
                    # 4. Refreshing inside a locked transaction can cause deadlocks
                    # The instance.state_data is already up-to-date from previous step's merge

                    step_def = steps[i]
                    step = instance.steps.get(step_index=i)
                    step_name = step_def.get("name", "unknown")

                    # Publish ODPS creation progress event if this is an ODPS workflow (Task 7.3.2)
                    if self._is_odps_workflow(instance.workflow_name):
                        self._publish_odps_creation_progress_if_applicable(
                            instance=instance,
                            step_index=i,
                            step_name=step_name,
                            total_steps=len(steps),
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
                    # Merge keys from inside 'output' dict if present (task return values)
                    step_output_dict = step_output.get("output", {})
                    if isinstance(step_output_dict, dict):
                        for key, value in step_output_dict.items():
                            instance.state_data[key] = value

                    # Update step index and batch all state updates into single save
                    instance.current_step_index = i + 1
                    # Keep state_data in sync with the model field
                    instance.state_data["current_step_index"] = instance.current_step_index
                    next_step_name = (
                        steps[i + 1].get("name", "unknown")
                        if i + 1 < len(steps)
                        else "completed"
                    )
                    instance.state_data["current_step_name"] = next_step_name
                    # Recalculate progress after step completion (state_data already updated in _execute_step)
                    if instance.state_data:
                        instance.state_data["progress_percentage"] = self._calculate_progress(
                            instance
                        )
                    # Single save for all state updates (batched)
                    instance.save(update_fields=["current_step_index", "state_data", "updated_at"])

                    # Publish ODPS creation progress event after step completion (Task 7.3.2)
                    if self._is_odps_workflow(instance.workflow_name):
                        self._publish_odps_creation_progress_if_applicable(
                            instance=instance,
                            step_index=i + 1,
                            step_name=step_def.get("name", "unknown"),
                            total_steps=len(steps),
                            status_message=f"Step {step_def.get('name', 'unknown')} completed",
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

                # Publish workflow.completed event (non-blocking - fire and forget)
                try:
                    tenant_id_str_for_event = (
                        str(instance.tenant_id) if instance.tenant_id else None
                    )
                    user_id_str = str(instance.created_by_id) if instance.created_by_id else None
                    # Use fire-and-forget pattern to avoid blocking workflow execution
                    try:
                        self.publish_workflow_completed(
                            workflow_instance_id=str(instance.id),
                            workflow_name=instance.workflow_name,
                            output_data=instance.output_data,
                            duration_ms=execution_duration_ms,
                            tenant_id=tenant_id_str_for_event,
                            user_id=user_id_str,
                        )
                    except Exception as publish_error:
                        # Log but don't fail - events are best-effort
                        logger.debug(
                            "Event publish failed (non-blocking)", error=str(publish_error)
                        )
                except Exception as e:
                    logger.warning(
                        "Failed to publish workflow.completed event", error=str(e), exc_info=True
                    )

                # Publish ODPS workflow.completed event if this is an ODPS workflow (Task 7.1.4)
                self._publish_odps_workflow_event_if_applicable(
                    instance,
                    "completed",
                    output_data=instance.output_data,
                    duration_ms=execution_duration_ms,
                    odps_contract_id=(
                        instance.state_data.get("odps_contract_id") if instance.state_data else None
                    ),
                    odcs_contract_id=(
                        instance.state_data.get("odcs_contract_id") if instance.state_data else None
                    ),
                    progress_percentage=(
                        instance.state_data.get("progress_percentage")
                        if instance.state_data
                        else 100.0
                    ),
                )

                if span:
                    span.set_attribute("workflow.status", "COMPLETED")
                    span.set_attribute("workflow.duration_seconds", execution_duration)
                    span.set_attribute("workflow.steps_completed", instance.current_step_index)

                logger.info("Workflow instance completed", workflow_instance_id=str(instance.id))

        except Exception as e:
            logger.exception(
                "Error executing workflow instance", workflow_instance_id=instance_id, error=str(e)
            )
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
                logger.warning(
                    "Failed to publish workflow.failed event", error=str(e2), exc_info=True
                )

            # Publish ODPS workflow.failed event if this is an ODPS workflow (Task 7.1.4)
            self._publish_odps_workflow_event_if_applicable(
                instance,
                "failed",
                error_message=str(e),
                error_details={"exception_type": type(e).__name__},
                failed_step_index=instance.current_step_index,
                failed_step_name=(
                    instance.state_data.get("current_step_name") if instance.state_data else None
                ),
                progress_percentage=(
                    instance.state_data.get("progress_percentage") if instance.state_data else None
                ),
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
            # Use in-memory instance data - no need to refresh unless we suspect concurrent modification
            # Merge input_data and state_data for condition evaluation
            # (conditions may reference values from either)
            condition_context = {**instance.input_data, **instance.state_data}
            condition_result = self._evaluate_condition(condition, condition_context)
            logger.debug(
                "Condition evaluation for step",
                step_name=step.step_name,
                condition=condition,
                result=condition_result,
                context_keys=list(condition_context.keys()),
                auto_activate=condition_context.get("auto_activate"),
                auto_activate_type=str(type(condition_context.get("auto_activate"))),
            )
            if not condition_result:
                # Condition is false - skip this step
                logger.info(
                    "Skipping step - condition evaluated to False",
                    step_name=step.step_name,
                    workflow_instance_id=str(instance.id),
                    condition=condition,
                    auto_activate=condition_context.get("auto_activate"),
                    auto_activate_type=str(type(condition_context.get("auto_activate"))),
                )
                step.mark_skipped(reason="Condition evaluated to False")
                return {
                    "skipped": True,
                    "reason": "Condition evaluated to False",
                    "condition": condition,
                }

        # Validate step is executable (PENDING or RUNNING) before marking started.
        # If step is already COMPLETED/FAILED/SKIPPED, fail the workflow with validation context
        # so we don't overwrite step status and silently proceed.
        if step.status not in (StepStatus.PENDING, StepStatus.RUNNING):
            tenant = instance.tenant
            user = instance.created_by
            tenant_id_str = str(tenant.id) if tenant else None
            if is_business_rules_validation_enabled(
                workflow_name=instance.workflow_name,
                tenant_id=tenant_id_str,
                workflow_instance_id=str(instance.id),
            ):
                business_rules = OrchestrationBusinessRules(
                    tenant_id=tenant_id_str,
                    user_id=str(user.id) if user else None,
                )
                step_execution_result = business_rules.validate_workflow_step_execution(
                    instance, step, tenant=tenant, user=user
                )
                if not step_execution_result.is_valid:
                    error_msg = self._format_validation_error(
                        "step_execution", step_execution_result, instance, step
                    )
                    raise WorkflowExecutionError(error_msg)
            raise WorkflowExecutionError(
                f"Workflow step cannot execute: step status is {step.status}, "
                f"expected {StepStatus.PENDING} or {StepStatus.RUNNING}"
            )

        step.mark_started()

        # Calculate progress percentage for the step that's starting
        # Use a temporary instance state to calculate progress at this step index
        progress_percentage = self._calculate_progress(instance)

        # Store progress in WorkflowInstance.state_data (will be saved after step execution)
        if instance.state_data is None:
            instance.state_data = {}
        instance.state_data["progress_percentage"] = progress_percentage
        instance.state_data["current_step_index"] = step.step_index
        instance.state_data["current_step_name"] = step.step_name
        # Don't save here - batch with step completion save

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

        # Publish workflow.step.started event (non-blocking - fire and forget)
        # Note: Validation results are not available yet at step start, so we'll include
        # validation status as "pending" and update in step.completed event
        try:
            tenant_id_str_for_event = str(instance.tenant_id) if instance.tenant_id else None
            user_id_str = str(instance.created_by_id) if instance.created_by_id else None
            # Use fire-and-forget pattern to avoid blocking workflow execution
            # Event publishing failures should not block workflow progress
            try:
                # Get validation results if available (from instance state_data)
                validation_status = "pending"
                validation_context = None
                validation_results_data = (
                    instance.state_data.get("_validation_results") if instance.state_data else None
                )
                if validation_results_data:
                    # Pre-validation results available
                    pre_validation = validation_results_data.get(
                        "workflow_state"
                    ) or validation_results_data.get("step_execution")
                    if pre_validation:
                        validation_status = (
                            "valid" if pre_validation.get("valid", False) else "invalid"
                        )
                        validation_context = {
                            "rule_name": "OrchestrationBusinessRules",
                            "validation_type": "pre_step",
                            "duration_seconds": pre_validation.get("duration", 0.0),
                            "cached": pre_validation.get("cached", False),
                        }

                self.publish_workflow_step_started(
                    workflow_instance_id=str(instance.id),
                    step_index=step.step_index,
                    step_name=step.step_name,
                    step_type=step.step_type,
                    progress_percentage=progress_percentage,
                    tenant_id=tenant_id_str_for_event,
                    user_id=user_id_str,
                    validation_status=validation_status,
                    validation_context=validation_context,
                )
            except Exception as publish_error:
                # Log but don't fail - events are best-effort
                logger.debug(f"Event publish failed (non-blocking): {publish_error}")
        except Exception as e:
            logger.warning(
                "Failed to publish workflow.step.started event", error=str(e), exc_info=True
            )

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

        sid = None
        try:
            sid = transaction.savepoint()

            # Phase 250.1.A test-mode hook — when a step_failure_injector
            # is configured (property-based testing only), call it inside
            # the savepoint so that a raised exception is caught by the
            # except block below, the step is marked FAILED, and the saga
            # compensation path activates. In production this is always
            # None (zero overhead).
            if self._step_failure_injector is not None:
                self._step_failure_injector(step.step_index, step.step_name)
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
            # Use in-memory instance - current_step_index is updated in main loop
            progress_percentage_after = self._calculate_progress(instance)

            # Update progress in WorkflowInstance.state_data (will be saved in main loop)
            if instance.state_data is None:
                instance.state_data = {}
            instance.state_data["progress_percentage"] = progress_percentage_after
            instance.state_data["current_step_index"] = instance.current_step_index
            instance.state_data["current_step_name"] = step.step_name
            # Don't save here - batch with main loop save

            # Publish ODPS workflow progress event if this is an ODPS workflow (Task 7.1.4)
            self._publish_odps_workflow_progress_if_applicable(instance, progress_percentage_after)

            # Publish workflow.step.completed event (non-blocking - fire and forget)
            try:
                tenant_id_str_for_event = str(instance.tenant_id) if instance.tenant_id else None
                user_id_str = str(instance.created_by_id) if instance.created_by_id else None
                # Use fire-and-forget pattern to avoid blocking workflow execution
                try:
                    # Get validation results from instance state_data
                    validation_status = "unknown"
                    validation_context = None
                    validation_results_data = (
                        instance.state_data.get("_validation_results")
                        if instance.state_data
                        else None
                    )
                    if validation_results_data:
                        # Determine overall validation status
                        all_valid = all(
                            v.get("valid", False) for v in validation_results_data.values() if v
                        )
                        validation_status = "valid" if all_valid else "invalid"

                        # Build validation context
                        validation_context = {
                            "rule_name": "OrchestrationBusinessRules",
                            "validations": {},
                            "total_duration_seconds": 0.0,
                            "cache_hits": 0,
                            "cache_misses": 0,
                        }

                        for val_type, val_data in validation_results_data.items():
                            if val_data:
                                validation_context["validations"][val_type] = {
                                    "valid": val_data.get("valid", False),
                                    "duration_seconds": val_data.get("duration", 0.0),
                                    "cached": val_data.get("cached", False),
                                    "error_count": val_data.get("error_count", 0),
                                    "warning_count": val_data.get("warning_count", 0),
                                    "errors": val_data.get("errors", []),
                                    "warnings": val_data.get("warnings", []),
                                }
                                validation_context["total_duration_seconds"] += val_data.get(
                                    "duration", 0.0
                                )
                                if val_data.get("cached", False):
                                    validation_context["cache_hits"] += 1
                                else:
                                    validation_context["cache_misses"] += 1

                    self.publish_workflow_step_completed(
                        workflow_instance_id=str(instance.id),
                        step_index=step.step_index,
                        step_name=step.step_name,
                        output_data=output,
                        duration_ms=step_duration_ms,
                        progress_percentage=progress_percentage_after,
                        tenant_id=tenant_id_str_for_event,
                        user_id=user_id_str,
                        validation_status=validation_status,
                        validation_context=validation_context,
                    )
                except Exception as publish_error:
                    # Log but don't fail - events are best-effort
                    logger.debug("Event publish failed (non-blocking)", error=str(publish_error))
            except Exception as e:
                logger.warning(
                    "Failed to publish workflow.step.completed event", error=str(e), exc_info=True
                )

            # Publish ODPS workflow.step.completed event if this is an ODPS workflow (Task 7.1.4)
            self._publish_odps_workflow_step_event_if_applicable(
                instance,
                step,
                "completed",
                output_data=output,
                duration_ms=step_duration_ms,
                progress_percentage=progress_percentage_after,
            )

            if step_span:
                step_span.set_attribute("workflow.step.status", "COMPLETED")
                step_span.set_attribute("workflow.step.duration_seconds", step_duration)

            return {"output": output, "state": output.get("state", {})}

        except Exception as e:
            # Controlled / expected business-outcome exceptions (fail-closed
            # gate rejections, deadline caps) are normal domain events, not
            # system faults — log at WARNING so they don't pollute ERROR-rate
            # dashboards or mask real infrastructure incidents.
            if isinstance(e, ControlledWorkflowException):
                logger.warning(
                    "Step failed (controlled)",
                    step_name=step.step_name,
                    error=str(e),
                    exception_type=type(e).__name__,
                )
            else:
                logger.exception(
                    "Error executing step",
                    step_name=step.step_name,
                    error=str(e),
                )
            # Rollback savepoint to restore transaction to valid state before DB writes.
            # Without this, Django marks the transaction for rollback on exception, and
            # subsequent queries (mark_failed, instance.save) fail with "can't execute
            # queries until the end of the 'atomic' block".
            if sid is not None:
                try:
                    transaction.savepoint_rollback(sid)
                except Exception as rollback_err:
                    logger.warning(
                        "Savepoint rollback failed (non-fatal)",
                        error=str(rollback_err),
                        step_name=step.step_name,
                    )
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
            # Use in-memory instance - we have the current state
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

                # Get validation results from instance state_data if available
                validation_status = "unknown"
                validation_context = None
                validation_results_data = (
                    instance.state_data.get("_validation_results") if instance.state_data else None
                )
                if validation_results_data:
                    # Determine overall validation status
                    all_valid = all(
                        v.get("valid", False) for v in validation_results_data.values() if v
                    )
                    validation_status = "valid" if all_valid else "invalid"

                    # Build validation context
                    validation_context = {
                        "rule_name": "OrchestrationBusinessRules",
                        "validations": {},
                        "total_duration_seconds": 0.0,
                        "cache_hits": 0,
                        "cache_misses": 0,
                    }

                    for val_type, val_data in validation_results_data.items():
                        if val_data:
                            validation_context["validations"][val_type] = {
                                "valid": val_data.get("valid", False),
                                "duration_seconds": val_data.get("duration", 0.0),
                                "cached": val_data.get("cached", False),
                                "error_count": val_data.get("error_count", 0),
                                "warning_count": val_data.get("warning_count", 0),
                                "errors": val_data.get("errors", []),
                                "warnings": val_data.get("warnings", []),
                            }
                            validation_context["total_duration_seconds"] += val_data.get(
                                "duration", 0.0
                            )
                            if val_data.get("cached", False):
                                validation_context["cache_hits"] += 1
                            else:
                                validation_context["cache_misses"] += 1

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
                    validation_status=validation_status,
                    validation_context=validation_context,
                )
            except Exception as e2:
                logger.warning(
                    "Failed to publish workflow.step.failed event", error=str(e2), exc_info=True
                )

            # Publish ODPS workflow.step.failed event if this is an ODPS workflow (Task 7.1.4)
            self._publish_odps_workflow_step_event_if_applicable(
                instance,
                step,
                "failed",
                error_message=str(e),
                error_details={"exception_type": type(e).__name__},
                retry_count=step.retry_count,
                duration_ms=step_duration_ms,
                progress_percentage=progress_percentage_at_failure,
            )

            if step_span:
                step_span.set_attribute("workflow.step.status", "FAILED")
                step_span.set_attribute("workflow.step.error_type", error_type)
                step_span.set_attribute("workflow.step.duration_seconds", step_duration)
                step_span.record_exception(e)

            # When compensation is enabled, do not re-raise so the execute loop can
            # call _handle_step_failure(instance, step) and run compensation.
            # Re-raising would be caught by the outer handler and mark workflow FAILED
            # without ever triggering rollback.
            dsl = instance.workflow_definition.dsl_json
            compensation_enabled = dsl.get("compensation", {}).get("enabled", False)
            if not compensation_enabled:
                raise
            return {"state": {}}
        finally:
            if step_span:
                step_span.end()

    # === CHECKPOINT: Validation caching helper methods (2026-01-28) ===
    def _validation_cache_ttl_seconds(self) -> int:
        """
        Cache TTL for workflow validation results.

        Uses the same TTL as core business rules caching to keep behavior consistent.
        """
        return getattr(settings, "CACHE_TTL_BUSINESS_RULES", 300)

    def _validation_cache_key(
        self,
        *,
        instance: WorkflowInstance,
        step: WorkflowStep,
        validation_type: str,
        fingerprint_hash: str,
    ) -> str:
        return f"workflow:validation:{instance.id}:{step.id}:{validation_type}:{fingerprint_hash}"

    def _fingerprint_hash(self, payload_fingerprint: Dict[str, Any]) -> str:
        """
        Stable hash for cache keys.

        Uses JSON canonicalization so key changes when state/input changes.
        """
        fingerprint_json = json.dumps(payload_fingerprint, sort_keys=True, default=str)
        return hashlib.sha256(fingerprint_json.encode("utf-8")).hexdigest()

    def _cached_orchestration_validation(
        self,
        *,
        validation_type: str,
        instance: WorkflowInstance,
        step: WorkflowStep,
        payload_fingerprint: Dict[str, Any],
        compute: Callable[[], Any],
    ):
        """
        Execute a validation function with per-workflow-instance caching.

        Returns:
            (ValidationResult, cached_bool)

        Notes:
        - Only *valid* results are cached (mirrors BusinessRules.execute()).
        - Cache invalidation is achieved by including a fingerprint of the relevant
          workflow/step state in the cache key.
        """
        ttl = self._validation_cache_ttl_seconds()
        fingerprint_hash = self._fingerprint_hash(payload_fingerprint)
        cache_key = self._validation_cache_key(
            instance=instance,
            step=step,
            validation_type=validation_type,
            fingerprint_hash=fingerprint_hash,
        )

        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return cached_result, True

        result = compute()
        if getattr(result, "is_valid", False):
            cache.set(cache_key, result, ttl)
        return result, False

    def _execute_task_step(
        self, instance: WorkflowInstance, step: WorkflowStep, step_def: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a task step with business rules validation"""
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
        # Use in-memory instance - state_data is already up-to-date
        task_input = {
            **instance.input_data,
            **instance.state_data,
            **step.input_data,
            **step_def.get("input", {}),
        }

        # Get tenant and user for business rules validation
        tenant = instance.tenant
        user = instance.created_by

        # Check if business rules validation is enabled for this workflow
        tenant_id_str = str(tenant.id) if tenant else None
        validation_enabled = is_business_rules_validation_enabled(
            workflow_name=instance.workflow_name,
            tenant_id=tenant_id_str,
            workflow_instance_id=str(instance.id),
        )

        if not validation_enabled:
            # Skip validation if feature flag is disabled
            logger.debug(
                "Business rules validation disabled for workflow",
                workflow_instance_id=str(instance.id),
                workflow_name=instance.workflow_name,
                tenant_id=tenant_id_str,
            )
            # Execute task without validation
            result = task_func(task_input, instance, step)
            return result if isinstance(result, dict) else {"result": result}

        # Create business rules instance with tenant/user context
        business_rules = OrchestrationBusinessRules(
            tenant_id=tenant_id_str, user_id=str(user.id) if user else None
        )

        # Get tenant ID for metrics
        tenant_id_str = get_tenant_id(tenant_id_str)
        rule_name = business_rules.get_rule_name()

        # Track validation results for observability
        validation_results = {
            "workflow_state": None,
            "step_input": None,
            "step_execution": None,
            "step_output": None,
            "post_workflow_state": None,
        }

        # Pre-step validation: Validate workflow state before step execution
        validation_start = time.time()

        # Create validation trace span
        validation_span = None
        if _tracer:
            validation_span = _tracer.start_span(
                name=f"workflow.validation.workflow_state",
                attributes={
                    "workflow.instance_id": str(instance.id),
                    "workflow.name": instance.workflow_name,
                    "workflow.step.name": step.step_name,
                    "workflow.step.index": step.step_index,
                    "business_rules.rule_name": rule_name,
                    "business_rules.validation_type": "workflow_state",
                },
            )

        workflow_state_cached = False
        try:
            # CRITICAL: Prefetch steps to avoid N+1 queries and potential database locks
            # This prevents hanging on workflow.steps.all() calls in validate_workflow_state.
            # Use a separate variable so we do not replace `instance`; _validation_results must
            # be written to the caller's instance so the main loop persists it.
            from django.db.models import Prefetch

            from hub.apps.orchestration.models import WorkflowStep

            instance_for_validation = instance
            if (
                not hasattr(instance, "_prefetched_objects_cache")
                or "steps" not in instance._prefetched_objects_cache
            ):
                try:
                    instance_for_validation = WorkflowInstance.objects.prefetch_related(
                        Prefetch(
                            "steps",
                            queryset=WorkflowStep.objects.only(
                                "step_index",
                                "step_name",
                                "output_data",
                                "status",
                                "workflow_instance_id",
                            ).order_by("step_index"),
                        )
                    ).get(id=instance.id)
                except Exception as prefetch_error:
                    logger.warning(
                        "Failed to prefetch workflow steps for validation",
                        workflow_instance_id=str(instance.id),
                        error=str(prefetch_error),
                    )

            # Validate workflow state (now with prefetched steps to avoid hanging)
            steps_signature = []
            try:
                if (
                    hasattr(instance_for_validation, "_prefetched_objects_cache")
                    and "steps" in instance_for_validation._prefetched_objects_cache
                ):
                    prefetched_steps = instance_for_validation._prefetched_objects_cache["steps"]
                    steps_signature = [
                        {
                            "step_index": s.step_index,
                            "step_name": s.step_name,
                            "status": s.status,
                            "updated_at": str(getattr(s, "updated_at", "")),
                        }
                        for s in prefetched_steps
                    ]
            except Exception:
                steps_signature = []

            workflow_state_result, workflow_state_cached = self._cached_orchestration_validation(
                validation_type="workflow_state",
                instance=instance,
                step=step,
                payload_fingerprint={
                    "workflow_id": str(instance.id),
                    "workflow_status": instance_for_validation.status,
                    "current_step_index": instance_for_validation.current_step_index,
                    "state_data": instance_for_validation.state_data,
                    "steps": steps_signature,
                },
                compute=lambda: business_rules.validate_workflow_state(
                    instance_for_validation, tenant, user
                ),
            )
        finally:
            validation_duration = time.time() - validation_start
            if validation_span:
                validation_span.set_attribute(
                    "business_rules.is_valid", workflow_state_result.is_valid
                )
                validation_span.set_attribute(
                    "business_rules.error_count", len(workflow_state_result.errors)
                )
                validation_span.set_attribute(
                    "business_rules.warning_count", len(workflow_state_result.warnings)
                )
                validation_span.set_attribute(
                    "business_rules.duration_seconds", validation_duration
                )
                validation_span.set_attribute("business_rules.cached", workflow_state_cached)
                validation_span.end()

        validation_results["workflow_state"] = {
            "result": workflow_state_result,
            "duration": validation_duration,
            "cached": workflow_state_cached,
        }

        # Record validation metrics
        self._record_validation_metrics(
            instance,
            step,
            rule_name,
            "workflow_state",
            workflow_state_result,
            validation_duration,
            workflow_state_cached,
            tenant_id_str,
        )
        logger.debug(
            "Business rules validation completed (duration_seconds=%s, validation_type=%s)",
            validation_duration,
            "workflow_state",
            extra={
                "workflow_instance_id": str(instance.id),
                "workflow_name": instance.workflow_name,
                "step_name": step.step_name,
                "rule_name": rule_name,
                "validation_type": "workflow_state",
                "duration_seconds": validation_duration,
                "is_valid": workflow_state_result.is_valid,
                "cached": workflow_state_cached,
            },
        )

        if not workflow_state_result.is_valid:
            error_message = self._format_validation_error(
                "workflow state validation", workflow_state_result, instance, step
            )
            raise WorkflowExecutionError(error_message)

        # Pre-step validation: Validate step input data
        validation_start = time.time()

        # Create validation trace span
        validation_span = None
        if _tracer:
            validation_span = _tracer.start_span(
                name=f"workflow.validation.step_input",
                attributes={
                    "workflow.instance_id": str(instance.id),
                    "workflow.name": instance.workflow_name,
                    "workflow.step.name": step.step_name,
                    "workflow.step.index": step.step_index,
                    "business_rules.rule_name": rule_name,
                    "business_rules.validation_type": "step_input",
                },
            )

        step_input_cached = False
        try:
            step_input_result, step_input_cached = self._cached_orchestration_validation(
                validation_type="step_input",
                instance=instance,
                step=step,
                payload_fingerprint={
                    "workflow_id": str(instance.id),
                    "step_id": str(step.id),
                    "step_index": step.step_index,
                    "step_status": step.status,
                    "task_input": task_input,
                },
                compute=lambda: business_rules.validate_step_input(
                    instance, step, task_input, tenant, user
                ),
            )
        finally:
            validation_duration = time.time() - validation_start
            if validation_span:
                validation_span.set_attribute("business_rules.is_valid", step_input_result.is_valid)
                validation_span.set_attribute(
                    "business_rules.error_count", len(step_input_result.errors)
                )
                validation_span.set_attribute(
                    "business_rules.warning_count", len(step_input_result.warnings)
                )
                validation_span.set_attribute(
                    "business_rules.duration_seconds", validation_duration
                )
                validation_span.set_attribute("business_rules.cached", step_input_cached)
                validation_span.end()

        validation_results["step_input"] = {
            "result": step_input_result,
            "duration": validation_duration,
            "cached": step_input_cached,
        }

        # Record validation metrics
        self._record_validation_metrics(
            instance,
            step,
            rule_name,
            "step_input",
            step_input_result,
            validation_duration,
            step_input_cached,
            tenant_id_str,
        )

        if not step_input_result.is_valid:
            error_message = self._format_validation_error(
                "step input validation", step_input_result, instance, step
            )
            raise WorkflowExecutionError(error_message)

        # Pre-step validation: Validate step can execute in current workflow state
        validation_start = time.time()

        # Create validation trace span
        validation_span = None
        if _tracer:
            validation_span = _tracer.start_span(
                name=f"workflow.validation.step_execution",
                attributes={
                    "workflow.instance_id": str(instance.id),
                    "workflow.name": instance.workflow_name,
                    "workflow.step.name": step.step_name,
                    "workflow.step.index": step.step_index,
                    "business_rules.rule_name": rule_name,
                    "business_rules.validation_type": "step_execution",
                },
            )

        step_execution_cached = False
        try:
            step_execution_result, step_execution_cached = self._cached_orchestration_validation(
                validation_type="step_execution",
                instance=instance,
                step=step,
                payload_fingerprint={
                    "workflow_id": str(instance.id),
                    "workflow_status": instance.status,
                    "workflow_current_step_index": instance.current_step_index,
                    "step_id": str(step.id),
                    "step_index": step.step_index,
                    "step_status": step.status,
                },
                compute=lambda: business_rules.validate_workflow_step_execution(
                    instance, step, tenant, user
                ),
            )
        finally:
            validation_duration = time.time() - validation_start
            if validation_span:
                validation_span.set_attribute(
                    "business_rules.is_valid", step_execution_result.is_valid
                )
                validation_span.set_attribute(
                    "business_rules.error_count", len(step_execution_result.errors)
                )
                validation_span.set_attribute(
                    "business_rules.warning_count", len(step_execution_result.warnings)
                )
                validation_span.set_attribute(
                    "business_rules.duration_seconds", validation_duration
                )
                validation_span.set_attribute("business_rules.cached", step_execution_cached)
                validation_span.end()

        validation_results["step_execution"] = {
            "result": step_execution_result,
            "duration": validation_duration,
            "cached": step_execution_cached,
        }

        # Record validation metrics
        self._record_validation_metrics(
            instance,
            step,
            rule_name,
            "step_execution",
            step_execution_result,
            validation_duration,
            step_execution_cached,
            tenant_id_str,
        )

        if not step_execution_result.is_valid:
            error_message = self._format_validation_error(
                "step execution validation", step_execution_result, instance, step
            )
            raise WorkflowExecutionError(error_message)

        # Log validation warnings (don't block execution) with structured logging
        if workflow_state_result.warnings:
            logger.warning(
                "Workflow state validation warnings",
                workflow_instance_id=str(instance.id),
                workflow_name=instance.workflow_name,
                step_name=step.step_name,
                step_index=step.step_index,
                rule_name=rule_name,
                validation_type="workflow_state",
                warnings=workflow_state_result.warnings,
                tenant_id=tenant_id_str,
            )
        if step_input_result.warnings:
            logger.warning(
                "Step input validation warnings",
                workflow_instance_id=str(instance.id),
                workflow_name=instance.workflow_name,
                step_name=step.step_name,
                step_index=step.step_index,
                rule_name=rule_name,
                validation_type="step_input",
                warnings=step_input_result.warnings,
                tenant_id=tenant_id_str,
            )
        if step_execution_result.warnings:
            logger.warning(
                "Step execution validation warnings",
                workflow_instance_id=str(instance.id),
                workflow_name=instance.workflow_name,
                step_name=step.step_name,
                step_index=step.step_index,
                rule_name=rule_name,
                validation_type="step_execution",
                warnings=step_execution_result.warnings,
                tenant_id=tenant_id_str,
            )

        # Execute task.  Domain-level ValidationError (business rule
        # rejections) is a controlled outcome — wrap it so the error
        # handler logs at WARNING instead of ERROR.
        try:
            result = task_func(task_input, instance, step)
        except (ValidationError, ServiceValidationError) as e:
            raise WorkflowStepValueError(str(e)) from e

        # Ensure result is a dictionary
        result = result if isinstance(result, dict) else {"result": result}

        # Post-step validation: Validate step output data
        validation_start = time.time()

        # Create validation trace span
        validation_span = None
        if _tracer:
            validation_span = _tracer.start_span(
                name=f"workflow.validation.step_output",
                attributes={
                    "workflow.instance_id": str(instance.id),
                    "workflow.name": instance.workflow_name,
                    "workflow.step.name": step.step_name,
                    "workflow.step.index": step.step_index,
                    "business_rules.rule_name": rule_name,
                    "business_rules.validation_type": "step_output",
                },
            )

        step_output_cached = False
        try:
            step_output_result, step_output_cached = self._cached_orchestration_validation(
                validation_type="step_output",
                instance=instance,
                step=step,
                payload_fingerprint={
                    "workflow_id": str(instance.id),
                    "step_id": str(step.id),
                    "step_index": step.step_index,
                    "step_status": step.status,
                    "result": result,
                },
                compute=lambda: business_rules.validate_step_output(
                    instance, step, result, tenant, user
                ),
            )
        finally:
            validation_duration = time.time() - validation_start
            if validation_span:
                validation_span.set_attribute(
                    "business_rules.is_valid", step_output_result.is_valid
                )
                validation_span.set_attribute(
                    "business_rules.error_count", len(step_output_result.errors)
                )
                validation_span.set_attribute(
                    "business_rules.warning_count", len(step_output_result.warnings)
                )
                validation_span.set_attribute(
                    "business_rules.duration_seconds", validation_duration
                )
                validation_span.set_attribute("business_rules.cached", step_output_cached)
                validation_span.end()

        validation_results["step_output"] = {
            "result": step_output_result,
            "duration": validation_duration,
            "cached": step_output_cached,
        }

        # Record validation metrics
        self._record_validation_metrics(
            instance,
            step,
            rule_name,
            "step_output",
            step_output_result,
            validation_duration,
            step_output_cached,
            tenant_id_str,
        )

        if not step_output_result.is_valid:
            error_message = self._format_validation_error(
                "step output validation", step_output_result, instance, step
            )
            raise WorkflowExecutionError(error_message)

        # Post-step validation: Validate workflow state after step
        validation_start = time.time()

        # Create validation trace span
        validation_span = None
        if _tracer:
            validation_span = _tracer.start_span(
                name=f"workflow.validation.post_workflow_state",
                attributes={
                    "workflow.instance_id": str(instance.id),
                    "workflow.name": instance.workflow_name,
                    "workflow.step.name": step.step_name,
                    "workflow.step.index": step.step_index,
                    "business_rules.rule_name": rule_name,
                    "business_rules.validation_type": "post_workflow_state",
                },
            )

        post_workflow_state_cached = False
        try:
            post_workflow_state_result, post_workflow_state_cached = (
                self._cached_orchestration_validation(
                    validation_type="post_workflow_state",
                    instance=instance,
                    step=step,
                    payload_fingerprint={
                        "workflow_id": str(instance.id),
                        "workflow_status": instance.status,
                        "current_step_index": instance.current_step_index,
                        "state_data": instance.state_data,
                    },
                    compute=lambda: business_rules.validate_workflow_state(instance, tenant, user),
                )
            )
        finally:
            validation_duration = time.time() - validation_start
            if validation_span:
                validation_span.set_attribute(
                    "business_rules.is_valid", post_workflow_state_result.is_valid
                )
                validation_span.set_attribute(
                    "business_rules.error_count", len(post_workflow_state_result.errors)
                )
                validation_span.set_attribute(
                    "business_rules.warning_count", len(post_workflow_state_result.warnings)
                )
                validation_span.set_attribute(
                    "business_rules.duration_seconds", validation_duration
                )
                validation_span.set_attribute("business_rules.cached", post_workflow_state_cached)
                validation_span.end()

        validation_results["post_workflow_state"] = {
            "result": post_workflow_state_result,
            "duration": validation_duration,
            "cached": post_workflow_state_cached,
        }

        # Record validation metrics
        self._record_validation_metrics(
            instance,
            step,
            rule_name,
            "post_workflow_state",
            post_workflow_state_result,
            validation_duration,
            post_workflow_state_cached,
            tenant_id_str,
        )

        if not post_workflow_state_result.is_valid:
            error_message = self._format_validation_error(
                "post-step workflow state validation", post_workflow_state_result, instance, step
            )
            raise WorkflowExecutionError(error_message)

        # Log post-validation warnings with structured logging
        if step_output_result.warnings:
            logger.warning(
                "Step output validation warnings",
                workflow_instance_id=str(instance.id),
                workflow_name=instance.workflow_name,
                step_name=step.step_name,
                step_index=step.step_index,
                rule_name=rule_name,
                validation_type="step_output",
                warnings=step_output_result.warnings,
                tenant_id=tenant_id_str,
            )
        if post_workflow_state_result.warnings:
            logger.warning(
                "Post-step workflow state validation warnings",
                workflow_instance_id=str(instance.id),
                workflow_name=instance.workflow_name,
                step_name=step.step_name,
                step_index=step.step_index,
                rule_name=rule_name,
                validation_type="post_workflow_state",
                warnings=post_workflow_state_result.warnings,
                tenant_id=tenant_id_str,
            )

        # Log validation results with structured logging
        logger.info(
            "Step validation completed",
            workflow_instance_id=str(instance.id),
            workflow_name=instance.workflow_name,
            step_name=step.step_name,
            step_index=step.step_index,
            rule_name=rule_name,
            pre_validation_valid=step_execution_result.is_valid,
            post_validation_valid=step_output_result.is_valid,
            validation_results={
                "workflow_state": {
                    "valid": workflow_state_result.is_valid,
                    "duration": validation_results["workflow_state"]["duration"],
                },
                "step_input": {
                    "valid": step_input_result.is_valid,
                    "duration": validation_results["step_input"]["duration"],
                },
                "step_execution": {
                    "valid": step_execution_result.is_valid,
                    "duration": validation_results["step_execution"]["duration"],
                },
                "step_output": {
                    "valid": step_output_result.is_valid,
                    "duration": validation_results["step_output"]["duration"],
                },
                "post_workflow_state": {
                    "valid": post_workflow_state_result.is_valid,
                    "duration": validation_results["post_workflow_state"]["duration"],
                },
            },
            tenant_id=tenant_id_str,
        )

        # Store validation results in instance state_data for event publishing
        if instance.state_data is None:
            instance.state_data = {}
        instance.state_data["_validation_results"] = {
            "workflow_state": {
                "valid": workflow_state_result.is_valid,
                "duration": validation_results["workflow_state"]["duration"],
                "cached": validation_results["workflow_state"].get("cached", False),
                "error_count": len(workflow_state_result.errors),
                "warning_count": len(workflow_state_result.warnings),
                "errors": workflow_state_result.errors,
                "warnings": workflow_state_result.warnings,
            },
            "step_input": {
                "valid": step_input_result.is_valid,
                "duration": validation_results["step_input"]["duration"],
                "cached": validation_results["step_input"].get("cached", False),
                "error_count": len(step_input_result.errors),
                "warning_count": len(step_input_result.warnings),
                "errors": step_input_result.errors,
                "warnings": step_input_result.warnings,
            },
            "step_execution": {
                "valid": step_execution_result.is_valid,
                "duration": validation_results["step_execution"]["duration"],
                "cached": validation_results["step_execution"].get("cached", False),
                "error_count": len(step_execution_result.errors),
                "warning_count": len(step_execution_result.warnings),
                "errors": step_execution_result.errors,
                "warnings": step_execution_result.warnings,
            },
            "step_output": {
                "valid": step_output_result.is_valid,
                "duration": validation_results["step_output"]["duration"],
                "cached": validation_results["step_output"].get("cached", False),
                "error_count": len(step_output_result.errors),
                "warning_count": len(step_output_result.warnings),
                "errors": step_output_result.errors,
                "warnings": step_output_result.warnings,
            },
            "post_workflow_state": {
                "valid": post_workflow_state_result.is_valid,
                "duration": validation_results["post_workflow_state"]["duration"],
                "cached": validation_results["post_workflow_state"].get("cached", False),
                "error_count": len(post_workflow_state_result.errors),
                "warning_count": len(post_workflow_state_result.warnings),
                "errors": post_workflow_state_result.errors,
                "warnings": post_workflow_state_result.warnings,
            },
        }

        return result

    def _record_validation_metrics(
        self,
        instance: WorkflowInstance,
        step: WorkflowStep,
        rule_name: str,
        validation_type: str,
        validation_result: Any,
        duration: float,
        cached: bool,
        tenant_id_str: str,
    ):
        """
        Record business rules validation metrics.

        Args:
            instance: Workflow instance
            step: Workflow step
            rule_name: Business rule name
            validation_type: Type of validation (workflow_state, step_input, etc.)
            validation_result: ValidationResult instance
            duration: Validation duration in seconds
            cached: Whether result was from cache
            tenant_id_str: Tenant ID string for metrics
        """
        try:
            status = "valid" if validation_result.is_valid else "invalid"

            # Record validation counter
            workflow_business_rules_validations_total.labels(
                workflow_name=instance.workflow_name,
                workflow_version=instance.workflow_version,
                step_name=step.step_name,
                rule_name=rule_name,
                status=status,
                tenant_id=tenant_id_str,
            ).inc()

            # Record validation duration
            workflow_business_rules_validation_duration_seconds.labels(
                workflow_name=instance.workflow_name,
                workflow_version=instance.workflow_version,
                step_name=step.step_name,
                rule_name=rule_name,
                tenant_id=tenant_id_str,
            ).observe(duration)

            # Record cache hit/miss
            if cached:
                workflow_business_rules_validation_cache_hits_total.labels(
                    workflow_name=instance.workflow_name,
                    workflow_version=instance.workflow_version,
                    step_name=step.step_name,
                    rule_name=rule_name,
                    tenant_id=tenant_id_str,
                ).inc()
            else:
                workflow_business_rules_validation_cache_misses_total.labels(
                    workflow_name=instance.workflow_name,
                    workflow_version=instance.workflow_version,
                    step_name=step.step_name,
                    rule_name=rule_name,
                    tenant_id=tenant_id_str,
                ).inc()
        except Exception as e:
            logger.warning(
                "Failed to record validation metrics",
                error=str(e),
                workflow_instance_id=str(instance.id),
                step_name=step.step_name,
                rule_name=rule_name,
                validation_type=validation_type,
                exc_info=True,
            )

    def _format_validation_error(
        self,
        validation_type: str,
        validation_result: Any,
        instance: WorkflowInstance,
        step: WorkflowStep,
    ) -> str:
        """
        Format validation error message with context.

        Args:
            validation_type: Type of validation that failed
            validation_result: ValidationResult with errors
            instance: WorkflowInstance context
            step: WorkflowStep context

        Returns:
            Formatted error message with validation context
        """
        rule_name = "OrchestrationBusinessRules"
        tenant_id_str = get_tenant_id(str(instance.tenant_id) if instance.tenant_id else None)

        # Log validation error with structured logging
        logger.error(
            "Workflow validation failed",
            workflow_instance_id=str(instance.id),
            workflow_name=instance.workflow_name,
            workflow_version=instance.workflow_version,
            step_name=step.step_name,
            step_index=step.step_index,
            rule_name=rule_name,
            validation_type=validation_type,
            errors=validation_result.errors,
            warnings=validation_result.warnings,
            validation_details=validation_result.details,
            tenant_id=tenant_id_str,
        )

        error_parts = [
            f"Business rules validation failed ({validation_type})",
            f"Rule: {rule_name}",
            f"Workflow: {instance.workflow_name} (id: {instance.id})",
            f"Step: {step.step_name} (index: {step.step_index})",
        ]

        if validation_result.errors:
            error_parts.append(f"Errors: {', '.join(validation_result.errors)}")

        if validation_result.warnings:
            error_parts.append(f"Warnings: {', '.join(validation_result.warnings)}")

        return " | ".join(error_parts)

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
                        "step_name": then_step_def.get("name", "then_step"),
                        "step_type": then_step_def.get("type", "task"),
                        "status": StepStatus.PENDING,
                    },
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
                        "step_name": else_step_def.get("name", "else_step"),
                        "step_type": else_step_def.get("type", "task"),
                        "status": StepStatus.PENDING,
                    },
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
            # Add item to state for loop steps (don't save here - will be saved in main loop)
            instance.state_data["loop_item"] = item

            for sub_index, loop_step_def in enumerate(loop_steps):
                # Use a unique sub-index to avoid unique constraint violations
                # Use step_index * 10000 + loop_index * 100 + sub_index to ensure uniqueness
                temp_step_index = step.step_index * 10000 + loop_index * 100 + sub_index
                # Check if step already exists (e.g., from a retry)
                temp_step, created = WorkflowStep.objects.get_or_create(
                    workflow_instance=instance,
                    step_index=temp_step_index,
                    defaults={
                        "step_name": loop_step_def.get("name", "loop_step"),
                        "step_type": loop_step_def.get("type", "task"),
                        "status": StepStatus.PENDING,
                    },
                )
                # If step already exists and is completed/failed, skip it
                if not created and temp_step.is_terminal():
                    continue

                def _run_loop_step_compensation_and_break(error_msg: str) -> None:
                    """Run compensation for failed loop step and break to next item."""
                    if instance.state_data is None:
                        instance.state_data = {}
                    instance.state_data["last_error"] = error_msg
                    comp_def = loop_step_def.get("compensation", {})
                    comp_task_name = comp_def.get("task") if isinstance(comp_def, dict) else None
                    if comp_task_name and self.task_registry:
                        task_func = self.task_registry.get(comp_task_name)
                        if task_func:
                            task_input = {
                                **instance.input_data,
                                **instance.state_data,
                                **temp_step.input_data,
                                **comp_def.get("input", {}),
                            }
                            loop_item = task_input.get("loop_item") or item
                            if isinstance(loop_item, str) and "file_path" not in task_input:
                                task_input["file_path"] = loop_item
                                task_input["loop_item"] = loop_item
                            elif isinstance(loop_item, dict):
                                if "file_path" not in task_input:
                                    task_input["file_path"] = loop_item.get("file_path")
                                task_input["loop_item"] = loop_item
                            if "scheduled_ingestion_id" not in task_input and instance.input_data:
                                sid = instance.input_data.get("scheduled_ingestion_id")
                                if sid:
                                    task_input["scheduled_ingestion_id"] = sid
                            task_input["last_error"] = error_msg
                            try:
                                comp_result = task_func(task_input, instance, temp_step)
                                if isinstance(comp_result, dict):
                                    for key, value in comp_result.items():
                                        if key not in ("state", "output"):
                                            instance.state_data[key] = value
                            except Exception as comp_e:
                                logger.warning(
                                    "Loop step compensation failed",
                                    step_name=temp_step.step_name,
                                    error=str(comp_e),
                                )
                    results.append({"error": error_msg, "step": temp_step.step_name})

                try:
                    result = self._execute_step(instance, temp_step, loop_step_def)
                except Exception as e:
                    _run_loop_step_compensation_and_break(str(e))
                    break  # Skip remaining steps for this item, continue to next iteration

                # When workflow has compensation enabled, _execute_step catches exceptions
                # and returns instead of re-raising. The step is marked FAILED. We must
                # detect that and break to avoid running subsequent steps with stale
                # state_data from the previous item (e.g. create_dataset for wrong file).
                temp_step.refresh_from_db()
                if temp_step.status == StepStatus.FAILED:
                    error_msg = temp_step.error_message or "Step failed"
                    _run_loop_step_compensation_and_break(error_msg)
                    break

                results.append(result)
                # Merge this inner step's output into state_data so next inner step
                # (e.g. validate_file after download_file) receives file_path, temp_path, etc.
                step_output = result if isinstance(result, dict) else {"result": result}
                step_state = step_output.get("state", {})
                if step_state:
                    instance.state_data.update(step_state)
                for key, value in step_output.items():
                    if key not in ("state", "output"):
                        instance.state_data[key] = value
                step_output_dict = step_output.get("output", {})
                if isinstance(step_output_dict, dict):
                    for key, value in step_output_dict.items():
                        instance.state_data[key] = value

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
                match = re.match(r"\{\{\s*(\w+)\s*==\s*(\w+)\s*\}\}", if_str)
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
                match = re.match(r"\{\{\s*(\w+)\s*!=\s*null\s*\}\}", if_str)
                if match:
                    field_name = match.group(1)
                    field_value = state_data.get(field_name)
                    return field_value is not None and field_value != ""

                # Pattern 3: Complex condition with &&: "{{ field1 != null && field2 != 'VALUE' }}"
                # Handle && conditions by extracting field names and operators from template syntax
                if "&&" in if_str:
                    # Remove outer {{ }} and split by &&
                    inner = if_str.strip()
                    if inner.startswith("{{"):
                        inner = inner[2:].strip()
                    if inner.endswith("}}"):
                        inner = inner[:-2].strip()

                    parts = [p.strip() for p in inner.split("&&")]
                    results = []
                    for part in parts:
                        # Check for != null (without {{ }} wrapper since we already removed it)
                        match = re.match(r"(\w+)\s*!=\s*null", part)
                        if match:
                            field_name = match.group(1)
                            field_value = state_data.get(field_name)
                            results.append(field_value is not None and field_value != "")
                            continue
                        # Check for == null
                        match = re.match(r"(\w+)\s*==\s*null", part)
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
                        match = re.match(r"(\w+)\s*==\s*(\w+)", part)
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
        # Use skip_locked to avoid blocking on concurrent access attempts
        instance = WorkflowInstance.objects.select_for_update(skip_locked=True).get(id=instance_id)

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

        # Reset failed and compensated steps so we re-run from the first affected step
        steps_to_reset = instance.steps.filter(
            status__in=(StepStatus.FAILED, StepStatus.COMPENSATED)
        )
        min_index = None
        for step in steps_to_reset:
            if min_index is None or step.step_index < min_index:
                min_index = step.step_index
        if min_index is not None:
            instance.current_step_index = min_index
            instance.save(update_fields=["current_step_index", "updated_at"])

        for step in steps_to_reset:
            step.status = StepStatus.PENDING
            step.error_message = None
            step.error_details = None
            step.compensation_data = None
            step.save(
                update_fields=[
                    "status",
                    "error_message",
                    "error_details",
                    "compensation_data",
                    "updated_at",
                ]
            )

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

    def _calculate_progress(self, instance: WorkflowInstance) -> float:
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
        self, instance: WorkflowInstance, event_type: str, **kwargs
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
        self, instance: WorkflowInstance, step: WorkflowStep, event_type: str, **kwargs
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
        self, instance: WorkflowInstance, progress_percentage: float
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
                current_step_name=(
                    instance.state_data.get("current_step_name") if instance.state_data else None
                ),
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
        status_message: Optional[str] = None,
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
            progress_percentage = (
                ((step_index + 1) / total_steps * 100.0) if total_steps > 0 else 0.0
            )

            # Get contract ID from state if available
            contract_id = None
            if instance.state_data:
                contract_id = instance.state_data.get(
                    "odps_contract_id"
                ) or instance.state_data.get("contract_id")

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
