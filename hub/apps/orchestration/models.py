"""
Workflow Orchestration Models

PostgreSQL models for workflow state persistence, versioning, and execution tracking.
"""

import uuid
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class WorkflowType(models.TextChoices):
    """Workflow type enumeration.

    Maps to the conceptual workflow category, used for reporting,
    alert routing, and business-rules dispatch.  Defined at module
    level so test suites and downstream consumers can import it
    directly from ``hub.apps.orchestration.models``.
    """

    ASSET_CREATION = "ASSET_CREATION", "Asset Creation"
    CONTRACT_CREATION = "CONTRACT_CREATION", "Contract Creation"
    DATASET_CREATION = "DATASET_CREATION", "Dataset Creation"
    MARKETPLACE_PUBLICATION = "MARKETPLACE_PUBLICATION", "Marketplace Publication"
    PRODUCT_CREATION = "PRODUCT_CREATION", "Product Creation"
    SCHEDULED_INGESTION = "SCHEDULED_INGESTION", "Scheduled Ingestion"
    SCHEDULED_EXPORT = "SCHEDULED_EXPORT", "Scheduled Export"
    TRANSFORMATION = "TRANSFORMATION", "Transformation"
    COMPLIANCE = "COMPLIANCE", "Compliance"
    DQ = "DQ", "Data Quality"
    ACCESS_REQUEST = "ACCESS_REQUEST", "Access Request"
    API_KEY_MANAGEMENT = "API_KEY_MANAGEMENT", "API Key Management"
    VERSION_CREATION = "VERSION_CREATION", "Version Creation"
    VIRTUALIZATION = "VIRTUALIZATION", "Virtualization"
    MODEL_INFERENCE = "MODEL_INFERENCE", "Model Inference"
    MODEL_TRAINING = "MODEL_TRAINING", "Model Training"


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
    COMPENSATION_INCOMPLETE = "COMPENSATION_INCOMPLETE", "Compensation Incomplete"


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
        constraints = [
            models.UniqueConstraint(
                fields=["name", "version"],
                name="unique_workflow_def_name_version",
            ),
        ]
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
        max_length=30,
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
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "DRAFT",
                        "RUNNING",
                        "COMPLETED",
                        "FAILED",
                        "CANCELLED",
                        "PAUSED",
                        "ROLLING_BACK",
                        "ROLLED_BACK",
                        "COMPENSATION_INCOMPLETE",
                    ]
                ),
                name="workflow_instance_status_valid",
            ),
        ]
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
            WorkflowStatus.COMPENSATION_INCOMPLETE,
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
        """Mark workflow as started and initialize step tracking in state_data."""
        self.status = WorkflowStatus.RUNNING
        self.started_at = timezone.now()
        if not self.state_data:
            self.state_data = {}
        if "current_step_index" not in self.state_data:
            self.state_data["current_step_index"] = self.current_step_index
        if "current_step_name" not in self.state_data:
            steps = self.workflow_definition.dsl_json.get("steps", [])
            idx = self.current_step_index
            if steps and idx < len(steps):
                self.state_data["current_step_name"] = steps[idx].get("name", "unknown")
            else:
                self.state_data["current_step_name"] = "unknown"
        self.save(update_fields=["status", "started_at", "state_data", "updated_at"])

    def mark_completed(self, output_data: dict[str, Any] | None = None):
        """Mark workflow as completed"""
        self.status = WorkflowStatus.COMPLETED
        self.completed_at = timezone.now()
        if output_data is not None:
            self.output_data = output_data
        self.save(update_fields=["status", "completed_at", "output_data", "updated_at"])

    def mark_failed(self, error_message: str, error_details: dict[str, Any] | None = None):
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
    compensation_attempt = models.PositiveIntegerField(
        default=0, help_text="Number of compensation attempts (Phase 68.2.3)"
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
        constraints = [
            models.UniqueConstraint(
                fields=["workflow_instance", "step_index"],
                name="unique_workflow_step_instance_index",
            ),
        ]
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

    def mark_completed(self, output_data: dict[str, Any] | None = None):
        """Mark step as completed"""
        self.status = StepStatus.COMPLETED
        self.completed_at = timezone.now()
        if output_data is not None:
            self.output_data = output_data
        self.save(update_fields=["status", "completed_at", "output_data", "updated_at"])

    def mark_failed(self, error_message: str, error_details: dict[str, Any] | None = None):
        """Mark step as failed"""
        self.status = StepStatus.FAILED
        self.completed_at = timezone.now()
        self.error_message = error_message
        if error_details is not None:
            self.error_details = error_details
        self.save(
            update_fields=["status", "completed_at", "error_message", "error_details", "updated_at"]
        )

    def mark_compensated(self, compensation_data: dict[str, Any] | None = None):
        """Mark step as compensated (rolled back)"""
        self.status = StepStatus.COMPENSATED
        if compensation_data is not None:
            self.compensation_data = compensation_data
        self.save(update_fields=["status", "compensation_data", "updated_at"])

    def mark_skipped(self, reason: str | None = None):
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


class PipelineDependency(models.Model):
    """Directed dependency between two pipeline instances.

    Declares that *pipeline_id* must complete successfully before
    *downstream_pipeline_id* executes.  Supports DATA, TRIGGER, and
    MANUAL dependency types and optional alert configuration.
    """

    class PipelineType(models.TextChoices):
        SCHEDULED_INGESTION = "scheduled_ingestion", "Scheduled Ingestion"
        SCHEDULED_EXPORT = "scheduled_export", "Scheduled Export"
        TRANSFORMATION = "transformation", "Transformation"
        DQ = "dq", "Data Quality"
        COMPLIANCE = "compliance", "Compliance"

    class DependencyType(models.TextChoices):
        DATA = "DATA", "Data"
        TRIGGER = "TRIGGER", "Trigger"
        MANUAL = "MANUAL", "Manual"

    class CreatedBy(models.TextChoices):
        AUTO = "AUTO", "Auto"
        MANUAL = "MANUAL", "Manual"
        LINEAGE_SYNC = "LINEAGE_SYNC", "Lineage Sync"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pipeline_type = models.CharField(
        max_length=50,
        blank=True,
        default="",
        choices=PipelineType.choices,
        help_text="Type of the upstream pipeline",
    )
    pipeline_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Identifier of the upstream pipeline instance",
    )
    dependency_type = models.CharField(
        max_length=50,
        blank=True,
        default="",
        choices=DependencyType.choices,
        help_text="Dependency relationship type",
    )
    downstream_pipeline_type = models.CharField(
        max_length=50,
        blank=True,
        default="",
        choices=PipelineType.choices,
        help_text="Type of the downstream pipeline",
    )
    downstream_pipeline_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Identifier of the downstream pipeline instance",
    )
    created_by = models.CharField(
        max_length=255,
        blank=True,
        default="",
        choices=CreatedBy.choices,
        help_text="How this dependency was created",
    )
    priority = models.IntegerField(
        default=0,
    )
    is_active = models.BooleanField(default=True)
    alert_email = models.EmailField(
        max_length=254,
        blank=True,
        default="",
        help_text="Email address for dependency-failure alerts",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="pipeline_dependencies",
        help_text="Tenant this dependency belongs to",
    )

    class Meta:
        db_table = "pipeline_dependencies"
        ordering = ["-priority", "-created_at"]
        indexes = [
            models.Index(
                fields=["tenant", "pipeline_type", "pipeline_id"],
                name="pipeline_de_tenant__2fe60d_idx",
            ),
            models.Index(
                fields=["tenant", "downstream_pipeline_type", "downstream_pipeline_id"],
                name="pipeline_de_tenant__9579b9_idx",
            ),
            models.Index(
                fields=["tenant", "is_active"],
                name="pipeline_de_tenant__5cbe50_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "tenant",
                    "pipeline_type",
                    "pipeline_id",
                    "dependency_type",
                    "downstream_pipeline_type",
                    "downstream_pipeline_id",
                ],
                name="uq_pipeline_dependency_scope",
            ),
        ]

    def __str__(self):
        return (
            f"{self.pipeline_type}/{self.pipeline_id} "
            f"→ {self.downstream_pipeline_type}/{self.downstream_pipeline_id}"
        )


class PipelineRunDependency(models.Model):
    """Record of a dependency resolution at run-time.

    Captures the terminal status of the upstream run at the moment the
    downstream run was created, providing an audit trail for dependency
    resolution decisions.
    """

    class RunType(models.TextChoices):
        SCHEDULED_INGESTION = "scheduled_ingestion", "Scheduled Ingestion"
        SCHEDULED_EXPORT = "scheduled_export", "Scheduled Export"
        TRANSFORMATION = "transformation", "Transformation"
        DQ = "dq", "Data Quality"
        COMPLIANCE = "compliance", "Compliance"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    upstream_run_type = models.CharField(
        max_length=50,
        blank=True,
        default="",
        choices=RunType.choices,
        help_text="Type of the upstream run",
    )
    upstream_run_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Identifier of the upstream run instance",
    )
    downstream_run_type = models.CharField(
        max_length=50,
        blank=True,
        default="",
        choices=RunType.choices,
        help_text="Type of the downstream run",
    )
    downstream_run_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Identifier of the downstream run instance",
    )
    upstream_status = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="Terminal status of the upstream run at resolution time",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    pipeline_dependency = models.ForeignKey(
        PipelineDependency,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="run_dependencies",
        help_text="Parent PipelineDependency definition",
    )
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="pipeline_run_dependencies",
        help_text="Tenant this run dependency belongs to",
    )

    class Meta:
        db_table = "pipeline_run_dependencies"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["tenant", "upstream_run_type", "upstream_run_id"],
                name="pipeline_ru_tenant__0bacbc_idx",
            ),
            models.Index(
                fields=["tenant", "downstream_run_type", "downstream_run_id"],
                name="pipeline_ru_tenant__b0c6e5_idx",
            ),
            models.Index(
                fields=["pipeline_dependency"],
                name="pipeline_ru_pipelin_42786d_idx",
            ),
        ]

    def __str__(self):
        return (
            f"RunDependency {self.upstream_run_type}/{self.upstream_run_id} "
            f"(status={self.upstream_status})"
        )


# ── Module-level re-exports ──────────────────────────────────────────
# Inner classes on PipelineDependency are the canonical home for these
# enumerations, but tests and non-model code (dependency_resolver,
# dependency_executor, trigger_engine, admin, management commands)
# import them directly from ``hub.apps.orchestration.models``.
# These aliases keep the public API stable.

DependencyType = PipelineDependency.DependencyType
"""Dependency relationship type (DATA, TRIGGER, MANUAL)."""

PipelineType = PipelineDependency.PipelineType
"""Pipeline run type (SCHEDULED_INGESTION, DQ, COMPLIANCE, …)."""

DependencySource = PipelineDependency.CreatedBy
"""How a pipeline dependency was created (AUTO, MANUAL, LINEAGE_SYNC).

Historically named ``DependencySource``; the model field was renamed to
``CreatedBy`` during Phase 285.11. This alias preserves backward
compatibility for all importers.
"""
