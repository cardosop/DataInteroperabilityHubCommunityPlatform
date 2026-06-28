"""
Journey Testing Framework

Provides comprehensive journey tracking, completion rate monitoring,
error handling validation, and performance metrics.
"""

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class JourneyStatus(Enum):
    """Journey execution status."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ERROR = "error"
    TIMEOUT = "timeout"


class StepStatus(Enum):
    """Step execution status."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class StepMetrics:
    """Metrics for a single journey step."""

    step_name: str
    status: StepStatus
    start_time: float | None = None
    end_time: float | None = None
    duration: float | None = None
    error_message: str | None = None
    error_type: str | None = None
    retry_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def start(self):
        """Mark step as started."""
        self.start_time = time.time()
        self.status = StepStatus.IN_PROGRESS

    def complete(self, metadata: dict[str, Any] | None = None):
        """Mark step as completed."""
        self.end_time = time.time()
        self.status = StepStatus.COMPLETED
        if self.start_time:
            self.duration = self.end_time - self.start_time
        if metadata:
            self.metadata.update(metadata)

    def fail(self, error: Exception, metadata: dict[str, Any] | None = None):
        """Mark step as failed."""
        self.end_time = time.time()
        self.status = StepStatus.FAILED
        if self.start_time:
            self.duration = self.end_time - self.start_time
        self.error_message = str(error)
        self.error_type = type(error).__name__
        if metadata:
            self.metadata.update(metadata)

    def skip(self, reason: str | None = None):
        """Mark step as skipped."""
        self.status = StepStatus.SKIPPED
        if reason:
            self.metadata["skip_reason"] = reason


@dataclass
class JourneyMetrics:
    """Metrics for a complete user journey."""

    journey_id: str
    journey_name: str
    persona: str
    status: JourneyStatus
    start_time: float | None = None
    end_time: float | None = None
    duration: float | None = None
    steps: list[StepMetrics] = field(default_factory=list)
    error_message: str | None = None
    error_type: str | None = None
    completion_rate: float = 0.0
    success_rate: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def start(self):
        """Mark journey as started."""
        self.start_time = time.time()
        self.status = JourneyStatus.IN_PROGRESS

    def complete(self, metadata: dict[str, Any] | None = None):
        """Mark journey as completed."""
        self.end_time = time.time()
        self.status = JourneyStatus.COMPLETED
        if self.start_time:
            self.duration = self.end_time - self.start_time
        self._calculate_metrics()
        if metadata:
            self.metadata.update(metadata)

    def fail(self, error: Exception, metadata: dict[str, Any] | None = None):
        """Mark journey as failed."""
        self.end_time = time.time()
        self.status = JourneyStatus.FAILED
        if self.start_time:
            self.duration = self.end_time - self.start_time
        self.error_message = str(error)
        self.error_type = type(error).__name__
        self._calculate_metrics()
        if metadata:
            self.metadata.update(metadata)

    def _calculate_metrics(self):
        """Calculate completion and success rates."""
        if not self.steps:
            self.completion_rate = 0.0
            self.success_rate = 0.0
            return

        total_steps = len(self.steps)
        completed_steps = sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)
        # successful_steps counts non-failure terminal states (COMPLETED + SKIPPED).
        # SKIPPED is an intentional omission, not a failure — a journey can succeed
        # even when some optional steps are skipped.
        successful_steps = sum(
            1 for s in self.steps
            if s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED)
        )

        self.completion_rate = (completed_steps / total_steps) * 100.0
        self.success_rate = (successful_steps / total_steps) * 100.0

    def add_step(self, step: StepMetrics):
        """Add a step to the journey."""
        self.steps.append(step)
        self._calculate_metrics()

    def get_step(self, step_name: str) -> StepMetrics | None:
        """Get a step by name."""
        for step in self.steps:
            if step.step_name == step_name:
                return step
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "journey_id": self.journey_id,
            "journey_name": self.journey_name,
            "persona": self.persona,
            "status": self.status.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "completion_rate": self.completion_rate,
            "success_rate": self.success_rate,
            "error_message": self.error_message,
            "error_type": self.error_type,
            "steps": [asdict(step) for step in self.steps],
            "metadata": self.metadata,
        }


class JourneyTracker:
    """
    Tracks user journey execution with metrics, error handling, and performance monitoring.
    """

    def __init__(self):
        """Initialize journey tracker."""
        self.journeys: dict[str, JourneyMetrics] = {}
        self.current_journey: JourneyMetrics | None = None
        self.current_step: StepMetrics | None = None

    def start_journey(
        self,
        journey_id: str,
        journey_name: str,
        persona: str,
        metadata: dict[str, Any] | None = None,
    ) -> JourneyMetrics:
        """
        Start tracking a new journey.

        Args:
            journey_id: Unique journey identifier
            journey_name: Human-readable journey name
            persona: Persona name
            metadata: Optional metadata

        Returns:
            JourneyMetrics instance
        """
        journey = JourneyMetrics(
            journey_id=journey_id,
            journey_name=journey_name,
            persona=persona,
            status=JourneyStatus.NOT_STARTED,
            metadata=metadata or {},
        )
        journey.start()
        self.journeys[journey_id] = journey
        self.current_journey = journey
        return journey

    def start_step(self, step_name: str, metadata: dict[str, Any] | None = None) -> StepMetrics:
        """
        Start tracking a journey step.

        Args:
            step_name: Step name
            metadata: Optional metadata

        Returns:
            StepMetrics instance
        """
        if not self.current_journey:
            raise RuntimeError("No active journey. Call start_journey() first.")

        step = StepMetrics(
            step_name=step_name, status=StepStatus.NOT_STARTED, metadata=metadata or {}
        )
        step.start()
        self.current_journey.add_step(step)
        self.current_step = step
        return step

    def complete_step(self, step_name: str | None = None, metadata: dict[str, Any] | None = None):
        """
        Mark a step as completed.

        Args:
            step_name: Step name (uses current step if not provided)
            metadata: Optional metadata
        """
        step = self._get_step(step_name)
        step.complete(metadata=metadata)
        self.current_step = None

    def fail_step(
        self, error: Exception, step_name: str | None = None, metadata: dict[str, Any] | None = None
    ):
        """
        Mark a step as failed.

        Args:
            error: Exception that caused the failure
            step_name: Step name (uses current step if not provided)
            metadata: Optional metadata
        """
        step = self._get_step(step_name)
        step.fail(error, metadata=metadata)
        self.current_step = None
        # Any failed step must cascade to journey failure so a journey
        # with failed steps can never be reported as COMPLETED.
        if self.current_journey is not None:
            self.current_journey.status = JourneyStatus.FAILED

    def skip_step(self, step_name: str | None = None, reason: str | None = None):
        """
        Mark a step as skipped.

        Args:
            step_name: Step name (uses current step if not provided)
            reason: Skip reason
        """
        step = self._get_step(step_name)
        step.skip(reason=reason)
        self.current_step = None

    def complete_journey(
        self, journey_id: str | None = None, metadata: dict[str, Any] | None = None
    ):
        """
        Mark a journey as completed.

        Args:
            journey_id: Journey ID (uses current journey if not provided)
            metadata: Optional metadata
        """
        journey = self._get_journey(journey_id)
        # Guard: reject completion when any step is still IN_PROGRESS.
        in_progress = [
            s for s in journey.steps if s.status == StepStatus.IN_PROGRESS
        ]
        if in_progress:
            raise RuntimeError(
                f"Cannot complete journey '{journey.journey_id}': "
                f"steps still in progress — "
                f"{[(s.step_name, s.status.value) for s in in_progress]}"
            )
        journey.complete(metadata=metadata)
        self.current_journey = None

    def fail_journey(
        self,
        error: Exception,
        journey_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        """
        Mark a journey as failed.

        Args:
            error: Exception that caused the failure
            journey_id: Journey ID (uses current journey if not provided)
            metadata: Optional metadata
        """
        journey = self._get_journey(journey_id)
        journey.fail(error, metadata=metadata)
        self.current_journey = None

    def _get_step(self, step_name: str | None = None) -> StepMetrics:
        """Get step by name or current step."""
        if step_name:
            step = self.current_journey.get_step(step_name)
            if not step:
                raise ValueError(
                    f"Step '{step_name}' not found in journey '{self.current_journey.journey_id}'"
                )
            return step
        elif self.current_step:
            return self.current_step
        else:
            raise RuntimeError("No active step. Call start_step() first.")

    def _get_journey(self, journey_id: str | None = None) -> JourneyMetrics:
        """Get journey by ID or current journey."""
        if journey_id:
            journey = self.journeys.get(journey_id)
            if not journey:
                raise ValueError(f"Journey '{journey_id}' not found")
            return journey
        elif self.current_journey:
            return self.current_journey
        else:
            raise RuntimeError("No active journey. Call start_journey() first.")

    def get_journey(self, journey_id: str) -> JourneyMetrics | None:
        """Get journey by ID."""
        return self.journeys.get(journey_id)

    def get_all_journeys(self) -> list[JourneyMetrics]:
        """Get all tracked journeys."""
        return list(self.journeys.values())

    def get_journey_summary(self) -> dict[str, Any]:
        """
        Get summary statistics for all journeys.

        Returns:
            Dictionary with summary statistics
        """
        if not self.journeys:
            return {
                "total_journeys": 0,
                "completed": 0,
                "failed": 0,
                "in_progress": 0,
                "average_completion_rate": 0.0,
                "average_success_rate": 0.0,
                "average_duration": 0.0,
            }

        total = len(self.journeys)
        completed = sum(1 for j in self.journeys.values() if j.status == JourneyStatus.COMPLETED)
        failed = sum(1 for j in self.journeys.values() if j.status == JourneyStatus.FAILED)
        in_progress = sum(
            1 for j in self.journeys.values() if j.status == JourneyStatus.IN_PROGRESS
        )

        completed_journeys = [
            j for j in self.journeys.values() if j.status == JourneyStatus.COMPLETED
        ]
        avg_completion_rate = (
            sum(j.completion_rate for j in completed_journeys) / len(completed_journeys)
            if completed_journeys
            else 0.0
        )
        avg_success_rate = (
            sum(j.success_rate for j in completed_journeys) / len(completed_journeys)
            if completed_journeys
            else 0.0
        )
        avg_duration = (
            sum(j.duration for j in completed_journeys if j.duration)
            / len([j for j in completed_journeys if j.duration])
            if completed_journeys
            else 0.0
        )

        return {
            "total_journeys": total,
            "completed": completed,
            "failed": failed,
            "in_progress": in_progress,
            "average_completion_rate": avg_completion_rate,
            "average_success_rate": avg_success_rate,
            "average_duration": avg_duration,
        }

    def export_results(self, filepath: str):
        """
        Export journey results to JSON file.

        Args:
            filepath: Path to output file
        """
        results = {
            "summary": self.get_journey_summary(),
            "journeys": [journey.to_dict() for journey in self.journeys.values()],
            "exported_at": datetime.now().isoformat(),
        }

        with open(filepath, "w") as f:
            json.dump(results, f, indent=2, default=str)

    def clear(self):
        """Clear all tracked journeys."""
        self.journeys.clear()
        self.current_journey = None
        self.current_step = None


# Global journey tracker instance
_global_tracker = JourneyTracker()


def get_journey_tracker() -> JourneyTracker:
    """Get global journey tracker instance."""
    return _global_tracker
