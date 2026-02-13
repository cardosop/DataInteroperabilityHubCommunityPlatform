"""
Workflow Orchestration Models

PostgreSQL models for workflow state persistence, versioning, and execution tracking.
"""

import uuid
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class WorkflowStatus(models.TextChoices):
    """Workflow instance status enumeration"""

    DRAFT = "DRAFT", "Draft"
    RUNNING = "RUNNING", "Running"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"
    CANCELLED = "CANCELLED", "Cancelled"
    PAUSED = "PAUSED", "Paused"
    ROLLING_BACK = "ROLLING_BACK", "Rolling Back"
    ROLLED_BACK = "ROLLED_BACK", "Rolled Back"


class StepStatus(models.TextChoices):
    """Workflow step status enumeration"""

    PENDING = "PENDING", "Pending"
    RUNNING = "RUNNING", "Running"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"
    SKIPPED = "SKIPPED", "Skipped"
    COMPENSATED = "COMPENSATED", "Compensated"


class WorkflowDefinition(models.Model):
    """
    Workflow definition model.

    Stores workflow definitions (DSL) with versioning support.
    Each workflow definition can have multiple versions.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Workflow name (e.g., 'contract_creation', 'scheduled_ingestion')",
    )
    version = models.CharField(
        max_length=50,
        default="1.0.0",
        help_text="Workflow version (semantic versioning: major.minor.patch)",
    )
    description = models.TextField(null=True, blank=True, help_text="Workflow description")
    dsl_json = models.JSONField(help_text="Workflow DSL definition (JSON format)")
    dsl_yaml = models.TextField(
        null=True, blank=True, help_text="Workflow DSL definition (YAML format, optional)"
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this workflow version is active (new instances use active version)",
    )
    dependencies = models.JSONField(
        default=list, blank=True, help_text="List of workflow names this workflow depends on"
    )
    metadata = models.JSONField(
        default=dict, blank=True, help_text="Workflow metadata (tags, categories, etc.)"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_workflow_definitions",
        null=True,
        blank=True,
        help_text="User who created the workflow definition",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "workflow_definitions"
        ordering = ["name", "-version"]
        unique_together = [["name", "version"]]
        indexes = [
            models.Index(fields=["name", "is_active"]),
            models.Index(fields=["name", "version"]),
            models.Index(fields=["is_active", "created_at"]),
        ]

    def __str__(self):
        return f"{self.name} v{self.version}"

    def clean(self):
        """Validate workflow definition"""
        super().clean()

        # Validate DSL JSON structure
        if not isinstance(self.dsl_json, dict):
            raise ValidationError("dsl_json must be a dictionary")

        # Validate required DSL fields
        required_fields = ["steps", "version"]
        for field in required_fields:
            if field not in self.dsl_json:
                raise ValidationError(f"dsl_json must contain '{field}' field")

        # Validate steps is a list
        if not isinstance(self.dsl_json.get("steps"), list):
            raise ValidationError("dsl_json.steps must be a list")

        # Validate at least one step
        if len(self.dsl_json.get("steps", [])) == 0:
            raise ValidationError("dsl_json.steps must contain at least one step")

    def save(self, *args, **kwargs):
        """Override save to validate before saving"""
        self.full_clean()
        super().save(*args, **kwargs)


class WorkflowInstance(models.Model):
    """
    Workflow instance model.

    Represents a single execution of a workflow definition.
    Tracks workflow state, execution history, and results.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workflow_definition = models.ForeignKey(
        WorkflowDefinition,
        on_delete=models.PROTECT,
        related_name="instances",
        help_text="Workflow definition this instance belongs to",
    )
    workflow_name = models.CharField(
        max_length=255, db_index=True, help_text="Workflow name (denormalized for performance)"
    )
    workflow_version = models.CharField(
        max_length=50, db_index=True, help_text="Workflow version (denormalized for performance)"
    )
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="workflow_instances",
        null=True,
        blank=True,
        help_text="Tenant this workflow instance belongs to (nullable for system workflows)",
    )
    status = models.CharField(
        max_length=20,
        choices=WorkflowStatus.choices,
        default=WorkflowStatus.DRAFT,
        db_index=True,
        help_text="Workflow instance status",
    )
    current_step_index = models.IntegerField(default=0, help_text="Current step index (0-based)")
    input_data = models.JSONField(default=dict, help_text="Workflow input data")
    output_data = models.JSONField(
        null=True,
        blank=True,
        default=dict,
        help_text="Workflow output data (populated on completion)",
    )
    state_data = models.JSONField(
        default=dict, help_text="Workflow state data (shared state between steps)"
    )
    error_message = models.TextField(
        null=True, blank=True, help_text="Error message if workflow failed"
    )
    error_details = models.JSONField(
        null=True, blank=True, help_text="Detailed error information (stack trace, context, etc.)"
    )
    retry_count = models.IntegerField(default=0, help_text="Number of retries attempted")
    max_retries = models.IntegerField(default=3, help_text="Maximum number of retries allowed")
    timeout_seconds = models.IntegerField(
        null=True, blank=True, help_text="Workflow timeout in seconds"
    )
    started_at = models.DateTimeField(
        null=True, blank=True, help_text="When workflow execution started"
    )
    completed_at = models.DateTimeField(
        null=True, blank=True, help_text="When workflow execution completed (success or failure)"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_workflow_instances",
        null=True,
        blank=True,
        help_text="User who created the workflow instance",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "workflow_instances"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "workflow_name", "status"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["workflow_name", "status", "created_at"]),
            models.Index(fields=["status", "started_at"]),
        ]

    def __str__(self):
        return f"{self.workflow_name} instance {self.id} ({self.status})"

    def is_terminal(self) -> bool:
        """Check if workflow is in a terminal state"""
        return self.status in [
            WorkflowStatus.COMPLETED,
            WorkflowStatus.FAILED,
            WorkflowStatus.CANCELLED,
            WorkflowStatus.ROLLED_BACK,
        ]

    def is_running(self) -> bool:
        """Check if workflow is currently running"""
        return self.status == WorkflowStatus.RUNNING

    def can_retry(self) -> bool:
        """Check if workflow can be retried (failed or rolled back)."""
        return (
            self.status in (WorkflowStatus.FAILED, WorkflowStatus.ROLLED_BACK)
            and self.retry_count < self.max_retries
        )

    def mark_started(self):
        """Mark workflow as started"""
        self.status = WorkflowStatus.RUNNING
        self.started_at = timezone.now()
        self.save(update_fields=["status", "started_at", "updated_at"])

    def mark_completed(self, output_data: Optional[Dict[str, Any]] = None):
        """Mark workflow as completed"""
        self.status = WorkflowStatus.COMPLETED
        self.completed_at = timezone.now()
        if output_data is not None:
            self.output_data = output_data
        self.save(update_fields=["status", "completed_at", "output_data", "updated_at"])

    def mark_failed(self, error_message: str, error_details: Optional[Dict[str, Any]] = None):
        """Mark workflow as failed"""
        self.status = WorkflowStatus.FAILED
        self.completed_at = timezone.now()
        self.error_message = error_message
        if error_details is not None:
            self.error_details = error_details
        self.save(
            update_fields=["status", "completed_at", "error_message", "error_details", "updated_at"]
        )

    def mark_cancelled(self):
        """Mark workflow as cancelled"""
        self.status = WorkflowStatus.CANCELLED
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "completed_at", "updated_at"])


class WorkflowStep(models.Model):
    """
    Workflow step model.

    Represents a single step execution within a workflow instance.
    Tracks step state, execution history, and compensation logic.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workflow_instance = models.ForeignKey(
        WorkflowInstance,
        on_delete=models.CASCADE,
        related_name="steps",
        help_text="Workflow instance this step belongs to",
    )
    step_index = models.IntegerField(
        db_index=True, help_text="Step index within workflow (0-based)"
    )
    step_name = models.CharField(
        max_length=255, db_index=True, help_text="Step name (from workflow definition)"
    )
    step_type = models.CharField(
        max_length=50, help_text="Step type (task, parallel, conditional, etc.)"
    )
    status = models.CharField(
        max_length=20,
        choices=StepStatus.choices,
        default=StepStatus.PENDING,
        db_index=True,
        help_text="Step status",
    )
    input_data = models.JSONField(null=True, blank=True, default=dict, help_text="Step input data")
    output_data = models.JSONField(
        null=True, blank=True, default=dict, help_text="Step output data"
    )
    error_message = models.TextField(
        null=True, blank=True, help_text="Error message if step failed"
    )
    error_details = models.JSONField(null=True, blank=True, help_text="Detailed error information")
    retry_count = models.IntegerField(
        default=0, help_text="Number of retries attempted for this step"
    )
    compensation_data = models.JSONField(
        null=True, blank=True, default=dict, help_text="Compensation data (for rollback)"
    )
    started_at = models.DateTimeField(
        null=True, blank=True, help_text="When step execution started"
    )
    completed_at = models.DateTimeField(
        null=True, blank=True, help_text="When step execution completed"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "workflow_steps"
        ordering = ["workflow_instance", "step_index"]
        unique_together = [["workflow_instance", "step_index"]]
        indexes = [
            models.Index(fields=["workflow_instance", "status"]),
            models.Index(fields=["workflow_instance", "step_index"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self):
        return f"{self.workflow_instance.workflow_name} step {self.step_index}: {self.step_name} ({self.status})"

    def is_terminal(self) -> bool:
        """Check if step is in a terminal state"""
        return self.status in [
            StepStatus.COMPLETED,
            StepStatus.FAILED,
            StepStatus.SKIPPED,
            StepStatus.COMPENSATED,
        ]

    def mark_started(self):
        """Mark step as started"""
        self.status = StepStatus.RUNNING
        self.started_at = timezone.now()
        self.save(update_fields=["status", "started_at", "updated_at"])

    def mark_completed(self, output_data: Optional[Dict[str, Any]] = None):
        """Mark step as completed"""
        self.status = StepStatus.COMPLETED
        self.completed_at = timezone.now()
        if output_data is not None:
            self.output_data = output_data
        self.save(update_fields=["status", "completed_at", "output_data", "updated_at"])

    def mark_failed(self, error_message: str, error_details: Optional[Dict[str, Any]] = None):
        """Mark step as failed"""
        self.status = StepStatus.FAILED
        self.completed_at = timezone.now()
        self.error_message = error_message
        if error_details is not None:
            self.error_details = error_details
        self.save(
            update_fields=["status", "completed_at", "error_message", "error_details", "updated_at"]
        )

    def mark_compensated(self, compensation_data: Optional[Dict[str, Any]] = None):
        """Mark step as compensated (rolled back)"""
        self.status = StepStatus.COMPENSATED
        if compensation_data is not None:
            self.compensation_data = compensation_data
        self.save(update_fields=["status", "compensation_data", "updated_at"])

    def mark_skipped(self, reason: Optional[str] = None):
        """Mark step as skipped (condition evaluated to False)"""
        self.status = StepStatus.SKIPPED
        self.completed_at = timezone.now()
        if reason:
            self.error_message = reason
        self.save(update_fields=["status", "completed_at", "error_message", "updated_at"])


class WorkflowState(models.Model):
    """
    Workflow state model.

    Stores workflow execution state snapshots for recovery and debugging.
    Used for workflow state persistence and recovery.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workflow_instance = models.ForeignKey(
        WorkflowInstance,
        on_delete=models.CASCADE,
        related_name="state_snapshots",
        help_text="Workflow instance this state snapshot belongs to",
    )
    snapshot_type = models.CharField(
        max_length=50, db_index=True, help_text="Snapshot type (checkpoint, recovery, debug, etc.)"
    )
    state_data = models.JSONField(help_text="Complete workflow state snapshot")
    step_states = models.JSONField(default=list, help_text="Step states snapshot")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "workflow_states"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["workflow_instance", "snapshot_type", "-created_at"]),
            models.Index(fields=["snapshot_type", "created_at"]),
        ]

    def __str__(self):
        return f"State snapshot for {self.workflow_instance.id} ({self.snapshot_type})"
