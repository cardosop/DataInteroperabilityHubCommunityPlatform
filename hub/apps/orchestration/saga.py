"""
Saga Pattern Base Implementation

Implements the Saga pattern for distributed transaction management.
A Saga is a sequence of local transactions, each with a compensating transaction.
If any step fails, all previous steps are compensated in reverse order.

This provides a clean, focused API for implementing Saga-based workflows.
"""
import logging
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class SagaStepStatus(Enum):
    """Saga step execution status"""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    COMPENSATED = "COMPENSATED"
    COMPENSATION_FAILED = "COMPENSATION_FAILED"


class SagaStatus(Enum):
    """Saga execution status"""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    COMPENSATING = "COMPENSATING"
    COMPENSATED = "COMPENSATED"
    COMPENSATION_FAILED = "COMPENSATION_FAILED"


@dataclass
class SagaStepResult:
    """Result of executing a saga step"""
    success: bool
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None

    @classmethod
    def success_result(cls, output: Optional[Dict[str, Any]] = None) -> "SagaStepResult":
        """Create a success result"""
        return cls(success=True, output=output or {})

    @classmethod
    def failure_result(cls, error: str, error_details: Optional[Dict[str, Any]] = None) -> "SagaStepResult":
        """Create a failure result"""
        return cls(success=False, error=error, error_details=error_details or {})


@dataclass
class SagaStep:
    """
    Saga step definition.

    Each step has:
    - A forward action (the main operation)
    - A compensation action (to undo the forward action)
    - Optional input data
    """
    name: str
    forward_action: Callable[[Dict[str, Any]], SagaStepResult]
    compensation_action: Optional[Callable[[Dict[str, Any], Dict[str, Any]], SagaStepResult]] = None
    input_data: Dict[str, Any] = field(default_factory=dict)
    description: Optional[str] = None

    def __post_init__(self):
        """Validate step definition"""
        if not self.name:
            raise ValueError("Saga step name is required")
        if not callable(self.forward_action):
            raise ValueError("Saga step forward_action must be callable")
        if self.compensation_action is not None and not callable(self.compensation_action):
            raise ValueError("Saga step compensation_action must be callable or None")


@dataclass
class SagaExecutionContext:
    """Context for saga execution"""
    saga_id: str
    step_results: List[Tuple[SagaStep, SagaStepResult]] = field(default_factory=list)
    state: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[timezone.datetime] = None
    completed_at: Optional[timezone.datetime] = None

    def add_step_result(self, step: SagaStep, result: SagaStepResult):
        """Add a step result to the context"""
        self.step_results.append((step, result))

    def get_completed_steps(self) -> List[Tuple[SagaStep, SagaStepResult]]:
        """Get all completed steps in execution order"""
        return [
            (step, result) for step, result in self.step_results
            if result.success
        ]

    def get_failed_step(self) -> Optional[Tuple[SagaStep, SagaStepResult]]:
        """Get the first failed step"""
        for step, result in self.step_results:
            if not result.success:
                return (step, result)
        return None


class SagaExecutionError(Exception):
    """Saga execution error"""
    pass


class SagaCompensationError(Exception):
    """Saga compensation error"""
    pass


class SagaOrchestrator:
    """
    Saga orchestrator for executing saga workflows.

    Coordinates the execution of saga steps and handles rollback on failure.
    Implements the Saga pattern for distributed transaction management.
    """

    def __init__(self, saga_id: Optional[str] = None):
        """
        Initialize saga orchestrator.

        Args:
            saga_id: Optional saga identifier (generated if not provided)
        """
        self.saga_id = saga_id or str(uuid.uuid4())
        self.context = SagaExecutionContext(saga_id=self.saga_id)
        self.status = SagaStatus.PENDING

    def execute(
        self,
        steps: List[SagaStep],
        initial_state: Optional[Dict[str, Any]] = None
    ) -> SagaExecutionContext:
        """
        Execute saga steps sequentially.

        If any step fails, all previous steps are compensated in reverse order.

        Args:
            steps: List of saga steps to execute
            initial_state: Optional initial state data

        Returns:
            SagaExecutionContext with execution results

        Raises:
            SagaExecutionError: If execution fails
            SagaCompensationError: If compensation fails
        """
        if not steps:
            raise ValueError("Saga steps list cannot be empty")

        self.status = SagaStatus.RUNNING
        self.context.started_at = timezone.now()
        self.context.state = initial_state or {}

        logger.info(
            f"Saga {self.saga_id} started with {len(steps)} steps",
            extra={
                "saga_id": self.saga_id,
                "step_count": len(steps),
                "step_names": [step.name for step in steps]
            }
        )

        try:
            # Execute steps sequentially
            for step_index, step in enumerate(steps):
                logger.info(
                    f"Saga {self.saga_id} executing step {step_index + 1}/{len(steps)}: {step.name}",
                    extra={
                        "saga_id": self.saga_id,
                        "step_name": step.name,
                        "step_index": step_index
                    }
                )

                # Prepare step input (merge initial state, previous step outputs, and step-specific input)
                step_input = self._prepare_step_input(step)

                # Execute forward action
                step_failed = False
                step_error = None

                try:
                    result = step.forward_action(step_input)

                    if not isinstance(result, SagaStepResult):
                        raise ValueError(
                            f"Step {step.name} forward_action must return SagaStepResult, "
                            f"got {type(result)}"
                        )

                    self.context.add_step_result(step, result)

                    if not result.success:
                        # Step failed - mark for compensation
                        step_failed = True
                        step_error = result.error
                        logger.warning(
                            f"Saga {self.saga_id} step {step.name} failed: {result.error}",
                            extra={
                                "saga_id": self.saga_id,
                                "step_name": step.name,
                                "error": result.error,
                                "error_details": result.error_details
                            }
                        )
                    else:
                        # Step succeeded - merge output into state
                        if result.output:
                            self.context.state.update(result.output)

                        logger.info(
                            f"Saga {self.saga_id} step {step.name} completed successfully",
                            extra={
                                "saga_id": self.saga_id,
                                "step_name": step.name,
                                "output_keys": list(result.output.keys()) if result.output else []
                            }
                        )

                except Exception as e:
                    # Unexpected exception in forward action
                    logger.exception(
                        f"Saga {self.saga_id} step {step.name} raised exception",
                        extra={
                            "saga_id": self.saga_id,
                            "step_name": step.name,
                            "exception_type": type(e).__name__,
                            "exception_message": str(e)
                        }
                    )

                    # Create failure result
                    failure_result = SagaStepResult.failure_result(
                        error=str(e),
                        error_details={"exception_type": type(e).__name__}
                    )
                    self.context.add_step_result(step, failure_result)

                    step_failed = True
                    step_error = str(e)

                # Handle step failure (outside try-except to avoid double compensation)
                if step_failed:
                    # Compensate all previous steps
                    self._compensate_steps(steps[:step_index])

                    self.status = SagaStatus.COMPENSATED
                    self.context.completed_at = timezone.now()

                    # Raise execution error (compensation already handled)
                    raise SagaExecutionError(
                        f"Saga execution failed at step '{step.name}': {step_error}"
                    )

            # All steps completed successfully
            self.status = SagaStatus.COMPLETED
            self.context.completed_at = timezone.now()

            logger.info(
                f"Saga {self.saga_id} completed successfully",
                extra={
                    "saga_id": self.saga_id,
                    "step_count": len(steps),
                    "duration_seconds": (
                        (self.context.completed_at - self.context.started_at).total_seconds()
                        if self.context.completed_at and self.context.started_at
                        else None
                    )
                }
            )

            return self.context

        except SagaExecutionError:
            # Re-raise execution errors (compensation already handled)
            # Don't try to compensate again in the outer exception handler
            raise
        except Exception as e:
            # Unexpected error - try to compensate
            logger.exception(
                f"Saga {self.saga_id} unexpected error during execution",
                extra={
                    "saga_id": self.saga_id,
                    "exception_type": type(e).__name__,
                    "exception_message": str(e)
                }
            )

            # Try to compensate all completed steps
            completed_steps = [step for step, _ in self.context.get_completed_steps()]
            if completed_steps:
                try:
                    self._compensate_steps(completed_steps)
                except Exception as comp_error:
                    logger.exception(
                        f"Saga {self.saga_id} compensation failed after unexpected error",
                        extra={
                            "saga_id": self.saga_id,
                            "compensation_error": str(comp_error)
                        }
                    )
                    self.status = SagaStatus.COMPENSATION_FAILED
                    raise SagaCompensationError(
                        f"Compensation failed after unexpected error: {str(comp_error)}"
                    ) from comp_error

            self.status = SagaStatus.FAILED
            self.context.completed_at = timezone.now()
            raise SagaExecutionError(f"Saga execution failed: {str(e)}") from e

    def _prepare_step_input(self, step: SagaStep) -> Dict[str, Any]:
        """
        Prepare input for a step by merging state and step-specific input.

        Args:
            step: Saga step

        Returns:
            Merged input data
        """
        # Start with current state
        step_input = self.context.state.copy()

        # Merge step-specific input (step input takes precedence)
        step_input.update(step.input_data)

        return step_input

    def _compensate_steps(self, steps: List[SagaStep]) -> None:
        """
        Compensate completed steps in reverse order.

        Args:
            steps: List of steps to compensate (in execution order)

        Raises:
            SagaCompensationError: If compensation fails
        """
        if not steps:
            return

        self.status = SagaStatus.COMPENSATING

        logger.info(
            f"Saga {self.saga_id} starting compensation for {len(steps)} steps",
            extra={
                "saga_id": self.saga_id,
                "step_count": len(steps),
                "step_names": [step.name for step in steps]
            }
        )

        # Compensate in reverse order
        compensation_results = []
        for step in reversed(steps):
            if step.compensation_action is None:
                logger.warning(
                    f"Saga {self.saga_id} step {step.name} has no compensation action, skipping",
                    extra={
                        "saga_id": self.saga_id,
                        "step_name": step.name
                    }
                )
                compensation_results.append({
                    "step": step.name,
                    "status": "skipped",
                    "reason": "no_compensation_action"
                })
                continue

            logger.info(
                f"Saga {self.saga_id} compensating step {step.name}",
                extra={
                    "saga_id": self.saga_id,
                    "step_name": step.name
                }
            )

            try:
                # Get step result to access output data
                step_result = None
                for s, result in self.context.step_results:
                    if s == step:
                        step_result = result
                        break

                if step_result is None:
                    logger.warning(
                        f"Saga {self.saga_id} step {step.name} has no result, skipping compensation",
                        extra={
                            "saga_id": self.saga_id,
                            "step_name": step.name
                        }
                    )
                    compensation_results.append({
                        "step": step.name,
                        "status": "skipped",
                        "reason": "no_step_result"
                    })
                    continue

                # Prepare compensation input (step output + current state)
                step_output = step_result.output or {}
                compensation_input = {
                    **self.context.state,
                    **step_output,
                    "step_output": step_output
                }

                # Execute compensation action
                compensation_result = step.compensation_action(compensation_input)

                if not isinstance(compensation_result, SagaStepResult):
                    raise ValueError(
                        f"Step {step.name} compensation_action must return SagaStepResult, "
                        f"got {type(compensation_result)}"
                    )

                if not compensation_result.success:
                    # Compensation failed
                    logger.error(
                        f"Saga {self.saga_id} step {step.name} compensation failed: {compensation_result.error}",
                        extra={
                            "saga_id": self.saga_id,
                            "step_name": step.name,
                            "error": compensation_result.error,
                            "error_details": compensation_result.error_details
                        }
                    )

                    compensation_results.append({
                        "step": step.name,
                        "status": "failed",
                        "error": compensation_result.error,
                        "error_details": compensation_result.error_details
                    })

                    # Continue compensating other steps even if one fails
                    # This is important for partial rollback
                    continue

                # Compensation succeeded
                logger.info(
                    f"Saga {self.saga_id} step {step.name} compensated successfully",
                    extra={
                        "saga_id": self.saga_id,
                        "step_name": step.name
                    }
                )

                compensation_results.append({
                    "step": step.name,
                    "status": "compensated",
                    "result": compensation_result.output
                })

            except Exception as e:
                # Unexpected exception in compensation
                logger.exception(
                    f"Saga {self.saga_id} step {step.name} compensation raised exception",
                    extra={
                        "saga_id": self.saga_id,
                        "step_name": step.name,
                        "exception_type": type(e).__name__,
                        "exception_message": str(e)
                    }
                )

                compensation_results.append({
                    "step": step.name,
                    "status": "failed",
                    "error": str(e),
                    "error_details": {"exception_type": type(e).__name__}
                })

                # Continue compensating other steps
                continue

        # Check if any compensations failed
        failed_compensations = [
            r for r in compensation_results
            if r.get("status") == "failed"
        ]

        if failed_compensations:
            self.status = SagaStatus.COMPENSATION_FAILED
            error_message = (
                f"Compensation failed for {len(failed_compensations)} step(s): "
                f"{', '.join(r['step'] for r in failed_compensations)}"
            )
            logger.error(
                f"Saga {self.saga_id} compensation completed with failures",
                extra={
                    "saga_id": self.saga_id,
                    "failed_steps": [r["step"] for r in failed_compensations],
                    "compensation_results": compensation_results
                }
            )
            raise SagaCompensationError(error_message)

        self.status = SagaStatus.COMPENSATED

        logger.info(
            f"Saga {self.saga_id} compensation completed successfully",
            extra={
                "saga_id": self.saga_id,
                "compensated_steps": len(steps),
                "compensation_results": compensation_results
            }
        )

    def get_status(self) -> SagaStatus:
        """Get current saga status"""
        return self.status

    def get_context(self) -> SagaExecutionContext:
        """Get saga execution context"""
        return self.context

