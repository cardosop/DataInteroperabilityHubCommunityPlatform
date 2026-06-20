"""
Workflow State Machine

Implements workflow state transitions with validation and error handling.
"""

from django.core.exceptions import ValidationError

from .models import WorkflowStatus


class WorkflowStateMachine:
    """
    Workflow state machine implementation.

    Manages valid state transitions:
    - DRAFT → RUNNING
    - RUNNING → COMPLETED | FAILED | CANCELLED | PAUSED | ROLLING_BACK
    - PAUSED → RUNNING | CANCELLED
    - ROLLING_BACK → ROLLED_BACK | FAILED
    - COMPLETED, FAILED, CANCELLED, ROLLED_BACK are terminal states
    """

    # Valid state transitions
    VALID_TRANSITIONS: dict[WorkflowStatus, set[WorkflowStatus]] = {
        WorkflowStatus.DRAFT: {WorkflowStatus.RUNNING, WorkflowStatus.CANCELLED},
        WorkflowStatus.RUNNING: {
            WorkflowStatus.COMPLETED,
            WorkflowStatus.FAILED,
            WorkflowStatus.CANCELLED,
            WorkflowStatus.PAUSED,
            WorkflowStatus.ROLLING_BACK,
        },
        WorkflowStatus.PAUSED: {WorkflowStatus.RUNNING, WorkflowStatus.CANCELLED},
        WorkflowStatus.ROLLING_BACK: {WorkflowStatus.ROLLED_BACK, WorkflowStatus.FAILED},
        WorkflowStatus.COMPLETED: set(),  # Terminal state
        WorkflowStatus.FAILED: set(),  # Terminal state
        WorkflowStatus.CANCELLED: set(),  # Terminal state
        WorkflowStatus.ROLLED_BACK: set(),  # Terminal state
    }

    # Terminal states
    TERMINAL_STATES: set[WorkflowStatus] = {
        WorkflowStatus.COMPLETED,
        WorkflowStatus.FAILED,
        WorkflowStatus.CANCELLED,
        WorkflowStatus.ROLLED_BACK,
    }

    @classmethod
    def can_transition(cls, from_status: WorkflowStatus, to_status: WorkflowStatus) -> bool:
        """
        Check if a state transition is valid.

        Args:
            from_status: Current workflow status
            to_status: Desired workflow status

        Returns:
            True if transition is valid, False otherwise
        """
        if from_status not in cls.VALID_TRANSITIONS:
            return False

        return to_status in cls.VALID_TRANSITIONS[from_status]

    @classmethod
    def validate_transition(cls, from_status: WorkflowStatus, to_status: WorkflowStatus) -> None:
        """
        Validate a state transition.

        Args:
            from_status: Current workflow status
            to_status: Desired workflow status

        Raises:
            ValidationError: If transition is invalid
        """
        if not cls.can_transition(from_status, to_status):
            raise ValidationError(
                f"Invalid state transition: {from_status.value} → {to_status.value}. "
                f"Valid transitions from {from_status.value}: "
                f"{[s.value for s in cls.VALID_TRANSITIONS.get(from_status, set())]}"
            )

    @classmethod
    def is_terminal(cls, status: WorkflowStatus) -> bool:
        """
        Check if a status is terminal.

        Args:
            status: Workflow status to check

        Returns:
            True if status is terminal, False otherwise
        """
        return status in cls.TERMINAL_STATES

    @classmethod
    def get_valid_transitions(cls, from_status: WorkflowStatus) -> set[WorkflowStatus]:
        """
        Get all valid transitions from a status.

        Args:
            from_status: Current workflow status

        Returns:
            Set of valid target statuses
        """
        return cls.VALID_TRANSITIONS.get(from_status, set())
