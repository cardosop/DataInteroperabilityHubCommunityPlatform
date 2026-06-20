"""
Post-Deployment Metrics Collector (Task 5.3)

Collects workflow and validation metrics from the database for post-deployment
monitoring. Tracks validation success/failure rates, workflow execution rates,
durations, and error rates. Produces optimization recommendations.

No mocks: uses real WorkflowInstance and WorkflowStep data.
"""

import logging
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F
from django.utils import timezone

from .models import StepStatus, WorkflowInstance, WorkflowStatus, WorkflowStep

logger = logging.getLogger(__name__)


# Performance criteria (Phase 5 DoD-5.5)
VALIDATION_FAILURE_RATE_THRESHOLD = Decimal("0.10")  # 10% invalid -> review
VALIDATION_FAILURE_RATE_CRITICAL = Decimal("0.25")  # 25% -> critical
WORKFLOW_SUCCESS_RATE_MIN = Decimal("0.95")  # 95% success target
WORKFLOW_ERROR_RATE_MAX = Decimal("0.05")  # 5% error rate max
STEP_FAILURE_RATE_MAX = Decimal("0.10")  # 10% step failure max


@dataclass
class WorkflowExecutionStats:
    """Aggregated workflow execution statistics for one workflow name."""

    workflow_name: str
    started_count: int
    completed_count: int
    failed_count: int
    cancelled_count: int
    rolled_back_count: int
    avg_duration_seconds: float | None
    validation_failure_count: int  # instances/steps failed with validation in error

    @property
    def total_terminal(self) -> int:
        return (
            self.completed_count + self.failed_count + self.cancelled_count + self.rolled_back_count
        )

    @property
    def success_rate(self) -> Decimal | None:
        if self.started_count == 0:
            return None
        return Decimal(self.completed_count) / Decimal(self.started_count)

    @property
    def failure_rate(self) -> Decimal | None:
        if self.started_count == 0:
            return None
        return Decimal(self.failed_count) / Decimal(self.started_count)

    @property
    def validation_failure_rate(self) -> Decimal | None:
        total = self.started_count
        if total == 0 or self.validation_failure_count == 0:
            return None
        return Decimal(self.validation_failure_count) / Decimal(total)


@dataclass
class StepExecutionStats:
    """Aggregated step execution statistics."""

    workflow_name: str
    step_name: str
    started_count: int
    completed_count: int
    failed_count: int
    avg_duration_seconds: float | None
    validation_failure_count: int

    @property
    def total_terminal(self) -> int:
        return self.completed_count + self.failed_count

    @property
    def success_rate(self) -> Decimal | None:
        if self.started_count == 0:
            return None
        return Decimal(self.completed_count) / Decimal(self.started_count)

    @property
    def failure_rate(self) -> Decimal | None:
        if self.started_count == 0:
            return None
        return Decimal(self.failed_count) / Decimal(self.started_count)


@dataclass
class PostDeploymentReport:
    """Full post-deployment metrics report."""

    window_minutes: int
    window_start: Any
    window_end: Any
    workflow_stats: list[WorkflowExecutionStats] = field(default_factory=list)
    step_stats: list[StepExecutionStats] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


def _is_validation_failure(error_message: str | None, error_details: dict | None) -> bool:
    """Return True if the failure appears to be validation-related."""
    if error_message and (
        "validation" in error_message.lower()
        or "WorkflowExecutionError" in error_message
        or "business rules" in error_message.lower()
        or "validate_workflow" in error_message.lower()
    ):
        return True
    if error_details:
        msg = error_details.get("error_message") or error_details.get("message") or ""
        if "validation" in msg.lower() or "business rules" in msg.lower():
            return True
        if error_details.get("validation_errors") or error_details.get("validation_failed"):
            return True
    return False


class PostDeploymentMetricsCollector:
    """
    Collects workflow and validation metrics from the database for
    post-deployment monitoring (Task 5.3.1, 5.3.2, 5.3.3).

    Tracks:
    - Validation success/failure rates (via DB: workflows/steps that failed with validation context)
    - Workflow success/failure rates and duration
    - Error rates
    - Produces optimization recommendations
    """

    def __init__(self, time_window_minutes: int = 60):
        self.time_window_minutes = time_window_minutes
        self.window_end = timezone.now()
        self.window_start = self.window_end - timedelta(minutes=time_window_minutes)

    def collect(self) -> PostDeploymentReport:
        """Collect metrics and build report with recommendations."""
        report = PostDeploymentReport(
            window_minutes=self.time_window_minutes,
            window_start=self.window_start,
            window_end=self.window_end,
        )
        self._collect_workflow_stats(report)
        self._collect_step_stats(report)
        self._add_recommendations(report)
        return report

    def _collect_workflow_stats(self, report: PostDeploymentReport) -> None:
        """Aggregate workflow instance stats in the time window."""
        # Instances that started in the window
        started = (
            WorkflowInstance.objects.filter(
                started_at__gte=self.window_start,
                started_at__lte=self.window_end,
            )
            .values("workflow_name")
            .annotate(count=Count("id"))
        )
        by_name: dict[str, dict[str, Any]] = {}
        for row in started:
            by_name[row["workflow_name"]] = {
                "started_count": row["count"],
                "completed_count": 0,
                "failed_count": 0,
                "cancelled_count": 0,
                "rolled_back_count": 0,
                "validation_failure_count": 0,
                "durations": [],
            }
        if not by_name:
            report.workflow_stats = []
            return

        # Completed
        completed = (
            WorkflowInstance.objects.filter(
                status=WorkflowStatus.COMPLETED,
                completed_at__gte=self.window_start,
                completed_at__lte=self.window_end,
            )
            .values("workflow_name")
            .annotate(count=Count("id"))
        )
        for row in completed:
            if row["workflow_name"] in by_name:
                by_name[row["workflow_name"]]["completed_count"] = row["count"]

        # Failed
        failed_qs = WorkflowInstance.objects.filter(
            status=WorkflowStatus.FAILED,
            completed_at__gte=self.window_start,
            completed_at__lte=self.window_end,
        )
        failed_counts = failed_qs.values("workflow_name").annotate(count=Count("id"))
        for row in failed_counts:
            if row["workflow_name"] in by_name:
                by_name[row["workflow_name"]]["failed_count"] = row["count"]

        # Validation failures among failed instances
        for inst in WorkflowInstance.objects.filter(
            status=WorkflowStatus.FAILED,
            completed_at__gte=self.window_start,
            completed_at__lte=self.window_end,
        ).only("workflow_name", "error_message", "error_details"):
            if inst.workflow_name not in by_name:
                continue
            if _is_validation_failure(inst.error_message, inst.error_details):
                by_name[inst.workflow_name]["validation_failure_count"] = (
                    by_name[inst.workflow_name].get("validation_failure_count", 0) + 1
                )

        # Cancelled / Rolled back
        cancelled = (
            WorkflowInstance.objects.filter(
                status=WorkflowStatus.CANCELLED,
                completed_at__gte=self.window_start,
                completed_at__lte=self.window_end,
            )
            .values("workflow_name")
            .annotate(count=Count("id"))
        )
        for row in cancelled:
            if row["workflow_name"] in by_name:
                by_name[row["workflow_name"]]["cancelled_count"] = row["count"]

        rolled = (
            WorkflowInstance.objects.filter(
                status=WorkflowStatus.ROLLED_BACK,
                completed_at__gte=self.window_start,
                completed_at__lte=self.window_end,
            )
            .values("workflow_name")
            .annotate(count=Count("id"))
        )
        for row in rolled:
            if row["workflow_name"] in by_name:
                by_name[row["workflow_name"]]["rolled_back_count"] = row["count"]

        # Average duration (completed only) via ExpressionWrapper
        duration_agg = (
            WorkflowInstance.objects.filter(
                status=WorkflowStatus.COMPLETED,
                started_at__isnull=False,
                completed_at__isnull=False,
                completed_at__gte=self.window_start,
                completed_at__lte=self.window_end,
            )
            .annotate(
                duration=ExpressionWrapper(
                    F("completed_at") - F("started_at"),
                    output_field=DurationField(),
                )
            )
            .values("workflow_name")
            .annotate(avg_duration=Avg("duration"))
        )
        for row in duration_agg:
            name = row["workflow_name"]
            if name in by_name and row.get("avg_duration"):
                td = row["avg_duration"]
                by_name[name]["avg_duration_seconds"] = td.total_seconds()
        for name, data in by_name.items():
            if "avg_duration_seconds" not in data:
                data["avg_duration_seconds"] = None

        report.workflow_stats = [
            WorkflowExecutionStats(
                workflow_name=name,
                started_count=data["started_count"],
                completed_count=data["completed_count"],
                failed_count=data["failed_count"],
                cancelled_count=data["cancelled_count"],
                rolled_back_count=data["rolled_back_count"],
                avg_duration_seconds=data.get("avg_duration_seconds"),
                validation_failure_count=data.get("validation_failure_count", 0),
            )
            for name, data in by_name.items()
        ]

    def _collect_step_stats(self, report: PostDeploymentReport) -> None:
        """Aggregate step execution stats in the time window."""
        steps_started = (
            WorkflowStep.objects.filter(
                workflow_instance__started_at__gte=self.window_start,
                workflow_instance__started_at__lte=self.window_end,
                started_at__isnull=False,
            )
            .values("workflow_instance__workflow_name", "step_name")
            .annotate(count=Count("id"))
        )
        by_step: dict[tuple, dict[str, Any]] = {}
        for row in steps_started:
            key = (row["workflow_instance__workflow_name"], row["step_name"])
            by_step[key] = {
                "started_count": row["count"],
                "completed_count": 0,
                "failed_count": 0,
                "validation_failure_count": 0,
                "avg_duration_seconds": None,
            }
        if not by_step:
            report.step_stats = []
            return

        completed = (
            WorkflowStep.objects.filter(
                status=StepStatus.COMPLETED,
                workflow_instance__started_at__gte=self.window_start,
                completed_at__gte=self.window_start,
                completed_at__lte=self.window_end,
            )
            .values("workflow_instance__workflow_name", "step_name")
            .annotate(count=Count("id"))
        )
        for row in completed:
            key = (row["workflow_instance__workflow_name"], row["step_name"])
            if key in by_step:
                by_step[key]["completed_count"] = row["count"]

        failed_steps_qs = WorkflowStep.objects.filter(
            status=StepStatus.FAILED,
            completed_at__gte=self.window_start,
            completed_at__lte=self.window_end,
        ).select_related("workflow_instance")
        failed_step_counts = failed_steps_qs.values(
            "workflow_instance__workflow_name", "step_name"
        ).annotate(count=Count("id"))
        for row in failed_step_counts:
            key = (row["workflow_instance__workflow_name"], row["step_name"])
            if key in by_step:
                by_step[key]["failed_count"] = row["count"]
        for step in failed_steps_qs.only(
            "workflow_instance__workflow_name", "step_name", "error_message", "error_details"
        ):
            key = (step.workflow_instance.workflow_name, step.step_name)
            if key in by_step and _is_validation_failure(step.error_message, step.error_details):
                by_step[key]["validation_failure_count"] = (
                    by_step[key].get("validation_failure_count", 0) + 1
                )

        duration_agg = (
            WorkflowStep.objects.filter(
                status=StepStatus.COMPLETED,
                started_at__isnull=False,
                completed_at__isnull=False,
                completed_at__gte=self.window_start,
                completed_at__lte=self.window_end,
            )
            .annotate(
                duration=ExpressionWrapper(
                    F("completed_at") - F("started_at"),
                    output_field=DurationField(),
                )
            )
            .values("workflow_instance__workflow_name", "step_name")
            .annotate(avg_duration=Avg("duration"))
        )
        for row in duration_agg:
            key = (
                row["workflow_instance__workflow_name"],
                row["step_name"],
            )
            if key in by_step and row.get("avg_duration"):
                td = row["avg_duration"]
                by_step[key]["avg_duration_seconds"] = td.total_seconds()

        report.step_stats = [
            StepExecutionStats(
                workflow_name=wf,
                step_name=step,
                started_count=data["started_count"],
                completed_count=data["completed_count"],
                failed_count=data["failed_count"],
                avg_duration_seconds=data.get("avg_duration_seconds"),
                validation_failure_count=data.get("validation_failure_count", 0),
            )
            for (wf, step), data in by_step.items()
        ]

    def _add_recommendations(self, report: PostDeploymentReport) -> None:
        """Add optimization recommendations based on thresholds (Task 5.3.3)."""
        for ws in report.workflow_stats:
            if ws.started_count == 0:
                continue
            # Success rate below target
            if ws.success_rate is not None and ws.success_rate < WORKFLOW_SUCCESS_RATE_MIN:
                report.recommendations.append(
                    f"Workflow '{ws.workflow_name}': success rate {ws.success_rate:.1%} is below "
                    f"target {WORKFLOW_SUCCESS_RATE_MIN:.0%}. Review recent failures and error logs."
                )
            # Error rate high
            if ws.failure_rate is not None and ws.failure_rate > WORKFLOW_ERROR_RATE_MAX:
                report.recommendations.append(
                    f"Workflow '{ws.workflow_name}': failure rate {ws.failure_rate:.1%} exceeds "
                    f"max {WORKFLOW_ERROR_RATE_MAX:.0%}. Identify root cause and consider rollback or fix."
                )
            # Validation failure rate high
            vf = ws.validation_failure_rate
            if vf is not None and vf > VALIDATION_FAILURE_RATE_CRITICAL:
                report.recommendations.append(
                    f"Workflow '{ws.workflow_name}': validation-related failure rate {vf:.1%} is critical "
                    f"(>{VALIDATION_FAILURE_RATE_CRITICAL:.0%}). Review business rules and input data."
                )
            elif vf is not None and vf > VALIDATION_FAILURE_RATE_THRESHOLD:
                report.recommendations.append(
                    f"Workflow '{ws.workflow_name}': validation-related failure rate {vf:.1%} exceeds "
                    f"threshold {VALIDATION_FAILURE_RATE_THRESHOLD:.0%}. Consider tuning rules or caching."
                )

        for ss in report.step_stats:
            if ss.started_count == 0:
                continue
            if ss.failure_rate is not None and ss.failure_rate > STEP_FAILURE_RATE_MAX:
                report.recommendations.append(
                    f"Step '{ss.workflow_name}.{ss.step_name}': failure rate {ss.failure_rate:.1%} "
                    f"exceeds {STEP_FAILURE_RATE_MAX:.0%}. Check step logic and dependencies."
                )

        # Generic recommendations
        report.recommendations.append(
            "Validation and cache hit rates: use Grafana dashboard 'Workflow Orchestration' "
            "(panels Business Rules Validation Success Rate, Cache Hit Rate) for live metrics."
        )
        report.recommendations.append(
            "If validation duration P95 is high: consider optimizing rule logic or increasing cache TTL."
        )
