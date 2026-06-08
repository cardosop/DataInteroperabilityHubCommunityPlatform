"""
Transformation Models

Models for data transformation pipelines.
"""
import uuid
from typing import Dict, Any, Optional, List
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

from hub.apps.integrations.encryption import (
    decrypt_json_field,
    encrypt_json_field,
    EncryptionError,
)


class PipelineStatus(models.TextChoices):
    """Pipeline status enumeration"""
    DRAFT = "DRAFT", "Draft"
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"
    ARCHIVED = "ARCHIVED", "Archived"


class ExecutionStatus(models.TextChoices):
    """Pipeline execution status enumeration"""
    PENDING = "PENDING", "Pending"
    RUNNING = "RUNNING", "Running"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"
    CANCELLED = "CANCELLED", "Cancelled"


class ExecutionMode(models.TextChoices):
    """Pipeline execution mode enumeration"""
    SYNC = "SYNC", "Synchronous"
    ASYNC = "ASYNC", "Asynchronous"
    SCHEDULED = "SCHEDULED", "Scheduled"
    MANUAL = "MANUAL", "Manual"
    AUTOMATED = "AUTOMATED", "Automated"


class TransformationPipeline(models.Model):
    """
    Transformation Pipeline model.

    Represents a data transformation pipeline definition that can be executed
    to transform data from source to target format.

    The pipeline_definition field stores the complete pipeline configuration
    as JSON, including nodes, connections, transformations, and execution logic.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the pipeline"
    )
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="transformation_pipelines",
        help_text="Tenant this pipeline belongs to"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_transformation_pipelines",
        null=True,
        blank=True,
        help_text="User who created the pipeline"
    )
    name = models.CharField(
        max_length=255,
        help_text="Pipeline name (e.g., 'Customer Data Enrichment', 'Sales Aggregation')"
    )
    description = models.TextField(
        null=True,
        blank=True,
        help_text="Pipeline description and purpose"
    )
    pipeline_definition = models.JSONField(
        help_text="Complete pipeline definition (JSON format) including nodes, connections, transformations"
    )
    version = models.CharField(
        max_length=50,
        default="1.0.0",
        help_text="Pipeline version (semantic versioning: major.minor.patch)"
    )
    status = models.CharField(
        max_length=20,
        choices=PipelineStatus.choices,
        default=PipelineStatus.DRAFT,
        help_text="Pipeline status: DRAFT, ACTIVE, INACTIVE, ARCHIVED"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the pipeline was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the pipeline was last updated"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata (tags, categories, source/target assets, etc.)"
    )

    # ── dbt-native fields (Phase 285.9) ──────────────────────────────

    warehouse_credential_ref = models.CharField(
        max_length=2048,
        null=True,
        blank=True,
        help_text="AWS Secrets Manager ARN for warehouse credentials (required for dbt-native pipelines).",
    )
    git_credential_ref = models.CharField(
        max_length=2048,
        null=True,
        blank=True,
        help_text="AWS Secrets Manager ARN for git credentials (dbt project clone).",
    )
    git_repository_url = models.CharField(
        max_length=2048,
        null=True,
        blank=True,
        help_text="Git repository URL for the dbt project (e.g., https://github.com/org/repo.git).",
    )

    class Meta:
        db_table = "transformation_pipelines"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["created_by"]),
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name", "version"],
                name="unique_pipeline_name_version_per_tenant"
            )
        ]

    def __str__(self):
        return f"{self.name} v{self.version} ({self.status})"

    def clean(self):
        """
        Validate the pipeline model.

        Raises:
            ValidationError: If validation fails
        """
        super().clean()

        # Validate name is not empty
        if not self.name or not self.name.strip():
            raise ValidationError({"name": "Pipeline name cannot be empty"})

        # Validate pipeline_definition is a dictionary
        if not isinstance(self.pipeline_definition, dict):
            raise ValidationError({
                "pipeline_definition": "Pipeline definition must be a JSON object"
            })

        # Skip structural validation if already encrypted
        if "_encrypted" in self.pipeline_definition:
            return

        # Validate pipeline_definition has required structure
        required_fields = ["version", "steps"]
        for field in required_fields:
            if field not in self.pipeline_definition:
                raise ValidationError({
                    "pipeline_definition": f"Pipeline definition must contain '{field}' field"
                })

        # Validate version format (basic semantic versioning check)
        version_str = self.pipeline_definition.get("version", "")
        if not isinstance(version_str, str) or not version_str:
            raise ValidationError({
                "pipeline_definition": "Pipeline definition 'version' must be a non-empty string"
            })

        # Validate steps is a list
        steps = self.pipeline_definition.get("steps", [])
        if not isinstance(steps, list):
            raise ValidationError({
                "pipeline_definition": "Pipeline definition 'steps' must be a list"
            })

        if len(steps) == 0:
            raise ValidationError({
                "pipeline_definition": "Pipeline definition must have at least one step"
            })

        # Validate each step has required fields
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                raise ValidationError({
                    "pipeline_definition": f"Step {i} must be a JSON object"
                })

            if "name" not in step:
                raise ValidationError({
                    "pipeline_definition": f"Step {i} must have a 'name' field"
                })

            if "type" not in step:
                raise ValidationError({
                    "pipeline_definition": f"Step {i} must have a 'type' field"
                })

    def save(self, *args, **kwargs):
        """
        Save the pipeline with validation and encryption.

        Raises:
            ValidationError: If validation fails
        """
        self.full_clean()

        # Encrypt pipeline_definition if plaintext dict
        if (
            isinstance(self.pipeline_definition, dict)
            and self.pipeline_definition
            and not self.pipeline_definition.get("_encrypted")
        ):
            try:
                encrypted = encrypt_json_field(
                    self.pipeline_definition
                )
                self.pipeline_definition = {
                    "_encrypted": encrypted,
                }
            except EncryptionError as e:
                raise ValidationError(
                    {"pipeline_definition": f"Failed to encrypt: {e}"}
                ) from e

        super().save(*args, **kwargs)

    def get_pipeline_definition(self) -> dict:
        """
        Get decrypted pipeline definition.

        Returns:
            Decrypted pipeline definition dictionary.
            Legacy plaintext dicts (pre-migration) returned as-is.
        """
        if not self.pipeline_definition:
            return {}
        if isinstance(self.pipeline_definition, dict):
            if "_encrypted" in self.pipeline_definition:
                return decrypt_json_field(
                    self.pipeline_definition["_encrypted"]
                )
            return self.pipeline_definition
        return {}

    def is_active(self) -> bool:
        """Check if pipeline is active"""
        return self.status == PipelineStatus.ACTIVE

    def is_draft(self) -> bool:
        """Check if pipeline is in draft status"""
        return self.status == PipelineStatus.DRAFT

    def can_execute(self) -> bool:
        """Check if pipeline can be executed"""
        return self.status == PipelineStatus.ACTIVE

    def activate(self):
        """Activate the pipeline"""
        if self.status == PipelineStatus.DRAFT:
            self.status = PipelineStatus.ACTIVE
            self.save(update_fields=['status', 'updated_at'])

    def deactivate(self):
        """Deactivate the pipeline"""
        if self.status == PipelineStatus.ACTIVE:
            self.status = PipelineStatus.INACTIVE
            self.save(update_fields=['status', 'updated_at'])

    def archive(self):
        """Archive the pipeline"""
        self.status = PipelineStatus.ARCHIVED
        self.save(update_fields=['status', 'updated_at'])

    def get_step_count(self) -> int:
        """Get the number of steps in the pipeline"""
        defn = self.get_pipeline_definition()
        steps = defn.get("steps", [])
        return len(steps) if isinstance(steps, list) else 0

    def get_pipeline_version(self) -> str:
        """Get the pipeline definition version"""
        defn = self.get_pipeline_definition()
        return defn.get("version", "unknown")


class NodeType(models.TextChoices):
    """Transformation node type enumeration"""
    FILTER = "filter", "Filter"
    JOIN = "join", "Join"
    AGGREGATE = "aggregate", "Aggregate"
    TRANSFORM = "transform", "Transform"
    OUTPUT = "output", "Output"


class TransformationNode(models.Model):
    """
    Transformation Node model.

    Represents a single node in a transformation pipeline. Each node performs
    a specific transformation operation (filter, join, aggregate, transform, output).

    Nodes are connected together to form a complete transformation pipeline.
    The order field determines the execution sequence of nodes within a pipeline.

    Attributes:
        id: Unique identifier for the node (UUID)
        pipeline: Foreign key to the TransformationPipeline this node belongs to
        node_type: Type of transformation node (filter, join, aggregate, transform, output)
        node_config: JSON configuration for the node (filter expressions, join keys, etc.)
        position: JSON object with x, y coordinates for visual representation
        order: Integer indicating the execution order within the pipeline
        created_at: Timestamp when the node was created
        updated_at: Timestamp when the node was last updated
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the node"
    )
    pipeline = models.ForeignKey(
        TransformationPipeline,
        on_delete=models.CASCADE,
        related_name="transformation_nodes",
        help_text="Pipeline this node belongs to"
    )
    node_type = models.CharField(
        max_length=50,
        help_text="Type of transformation node (filter, join, aggregate, transform, output)"
    )
    node_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Node configuration (JSON format) - filter expressions, join keys, aggregation functions, etc."
    )
    position = models.JSONField(
        default=dict,
        blank=True,
        help_text="Visual position coordinates (JSON format: {'x': number, 'y': number})"
    )
    order = models.IntegerField(
        help_text="Execution order within the pipeline (1-based, lower numbers execute first)"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the node was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the node was last updated"
    )

    class Meta:
        db_table = "transformation_nodes"
        ordering = ["pipeline", "order"]
        indexes = [
            models.Index(fields=["pipeline"]),
            models.Index(fields=["node_type"]),
            models.Index(fields=["order"]),
            models.Index(fields=["pipeline", "order"]),
        ]

    def __str__(self):
        """String representation of the node"""
        return f"{self.node_type} (order: {self.order}) - {self.pipeline.name}"

    def clean(self):
        """
        Validate the transformation node model.

        Raises:
            ValidationError: If validation fails
        """
        super().clean()

        # Validate node_type is not empty
        if not self.node_type or not self.node_type.strip():
            raise ValidationError({
                "node_type": "Node type cannot be empty"
            })

        # Validate node_config is a dictionary
        if not isinstance(self.node_config, dict):
            raise ValidationError({
                "node_config": "Node configuration must be a JSON object"
            })

        # Validate position is a dictionary
        if not isinstance(self.position, dict):
            raise ValidationError({
                "position": "Position must be a JSON object"
            })

        # Validate order is non-negative
        if self.order is None:
            raise ValidationError({
                "order": "Order is required"
            })

        if self.order < 0:
            raise ValidationError({
                "order": "Order must be non-negative"
            })

    def save(self, *args, **kwargs):
        """
        Save the node with validation and encryption.

        Raises:
            ValidationError: If validation fails
        """
        self.full_clean()

        # Encrypt node_config if plaintext dict
        if (
            isinstance(self.node_config, dict)
            and self.node_config
            and not self.node_config.get("_encrypted")
        ):
            try:
                encrypted = encrypt_json_field(self.node_config)
                self.node_config = {"_encrypted": encrypted}
            except EncryptionError as e:
                raise ValidationError(
                    {"node_config": f"Failed to encrypt: {e}"}
                ) from e

        super().save(*args, **kwargs)

    def get_node_config(self) -> dict:
        """
        Get decrypted node configuration.

        Returns:
            Decrypted node config dictionary.
            Legacy plaintext dicts (pre-migration) returned as-is.
        """
        if not self.node_config:
            return {}
        if isinstance(self.node_config, dict):
            if "_encrypted" in self.node_config:
                return decrypt_json_field(
                    self.node_config["_encrypted"]
                )
            return self.node_config
        return {}


class PipelineExecution(models.Model):
    """
    Pipeline Execution model.

    Tracks individual executions of transformation pipelines, including
    source assets, result assets, execution logs, and performance metrics.

    Each execution represents a single run of a transformation pipeline
    that transforms data from a source asset to a result asset.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the execution"
    )
    pipeline = models.ForeignKey(
        TransformationPipeline,
        on_delete=models.CASCADE,
        related_name="executions",
        help_text="Transformation pipeline that was executed"
    )
    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.CASCADE,
        related_name="transformation_executions",
        help_text="Source asset that was transformed"
    )
    execution_mode = models.CharField(
        max_length=20,
        choices=ExecutionMode.choices,
        default=ExecutionMode.MANUAL,
        help_text="Execution mode: SYNC, ASYNC, SCHEDULED, MANUAL, AUTOMATED"
    )
    status = models.CharField(
        max_length=20,
        choices=ExecutionStatus.choices,
        default=ExecutionStatus.PENDING,
        help_text="Execution status: PENDING, RUNNING, COMPLETED, FAILED, CANCELLED"
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the execution started"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the execution completed"
    )
    result_asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.SET_NULL,
        related_name="transformation_result_executions",
        null=True,
        blank=True,
        help_text="Result asset created by the transformation (null if execution failed or not yet completed)"
    )
    job = models.ForeignKey(
        "jobs.Job",
        on_delete=models.SET_NULL,
        related_name="pipeline_executions",
        null=True,
        blank=True,
        help_text="Job record for async execution (null for sync executions)"
    )
    workflow_instance = models.ForeignKey(
        "orchestration.WorkflowInstance",
        on_delete=models.SET_NULL,
        related_name="pipeline_executions",
        null=True,
        blank=True,
        help_text="Workflow instance that orchestrates this execution (null if not using workflow)"
    )
    execution_log = models.JSONField(
        default=list,
        blank=True,
        help_text="Execution log entries (JSON array of log messages, errors, warnings)"
    )
    metrics = models.JSONField(
        default=dict,
        blank=True,
        help_text="Execution metrics (duration, throughput, items processed, etc.)"
    )
    idempotency_key = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        unique=True,
        db_index=True,
        help_text="Idempotency key for retry safety (uses execution_id by default)"
    )
    prefect_flow_run_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        help_text="Prefect flow run ID for this execution. Set after Prefect flow run creation.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the execution record was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the execution record was last updated"
    )

    class Meta:
        db_table = "transformation_pipeline_executions"
        ordering = ["-started_at", "-created_at"]
        indexes = [
            models.Index(fields=["pipeline"]),
            models.Index(fields=["asset"]),
            models.Index(fields=["status"]),
            models.Index(fields=["started_at"]),
            models.Index(fields=["pipeline", "status"]),
            models.Index(fields=["pipeline", "started_at"]),
            models.Index(fields=["asset", "status"]),
            models.Index(fields=["idempotency_key"]),
            models.Index(fields=["workflow_instance"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["idempotency_key"],
                condition=models.Q(idempotency_key__isnull=False),
                name="unique_idempotency_key_when_set"
            ),
        ]

    def __str__(self):
        return f"Execution of {self.pipeline.name} on {self.asset.name} ({self.status})"

    def clean(self):
        """
        Validate the pipeline execution model.

        Raises:
            ValidationError: If validation fails
        """
        super().clean()

        # Validate execution_log is a list
        if not isinstance(self.execution_log, list):
            raise ValidationError({
                "execution_log": "Execution log must be a JSON array"
            })

        # Validate metrics is a dictionary
        if not isinstance(self.metrics, dict):
            raise ValidationError({
                "metrics": "Metrics must be a JSON object"
            })

        # Validate completed_at is after started_at if both are set
        if self.started_at and self.completed_at:
            if self.completed_at < self.started_at:
                raise ValidationError({
                    "completed_at": "Completed at must be after started at"
                })

        # Validate result_asset is set when status is COMPLETED
        if self.status == ExecutionStatus.COMPLETED and not self.result_asset:
            raise ValidationError({
                "result_asset": "Result asset must be set when execution is completed"
            })

    def save(self, *args, **kwargs):
        """
        Save the pipeline execution with validation.

        Raises:
            ValidationError: If validation fails
        """
        self.full_clean()
        super().save(*args, **kwargs)

    def is_pending(self) -> bool:
        """Check if execution is pending"""
        return self.status == ExecutionStatus.PENDING

    def is_running(self) -> bool:
        """Check if execution is running"""
        return self.status == ExecutionStatus.RUNNING

    def is_completed(self) -> bool:
        """Check if execution is completed"""
        return self.status == ExecutionStatus.COMPLETED

    def is_failed(self) -> bool:
        """Check if execution failed"""
        return self.status == ExecutionStatus.FAILED

    def is_terminal(self) -> bool:
        """Check if execution is in a terminal state"""
        # Handle both enum values and string values
        status_value = self.status.value if hasattr(self.status, 'value') else self.status
        terminal_values = [
            ExecutionStatus.COMPLETED.value if hasattr(ExecutionStatus.COMPLETED, 'value') else ExecutionStatus.COMPLETED,
            ExecutionStatus.FAILED.value if hasattr(ExecutionStatus.FAILED, 'value') else ExecutionStatus.FAILED,
            ExecutionStatus.CANCELLED.value if hasattr(ExecutionStatus.CANCELLED, 'value') else ExecutionStatus.CANCELLED
        ]
        return status_value in terminal_values

    def can_cancel(self) -> bool:
        """Check if execution can be cancelled"""
        return self.status in [ExecutionStatus.PENDING, ExecutionStatus.RUNNING]

    def mark_started(self):
        """Mark execution as started"""
        if self.status == ExecutionStatus.PENDING:
            self.status = ExecutionStatus.RUNNING
            self.started_at = timezone.now()
            self.save(update_fields=['status', 'started_at', 'updated_at'])

    def mark_completed(self, result_asset=None, metrics=None):
        """
        Mark execution as completed.

        Args:
            result_asset: Optional result asset created by the transformation
            metrics: Optional metrics dictionary to update
        """
        if self.status == ExecutionStatus.RUNNING:
            self.status = ExecutionStatus.COMPLETED
            self.completed_at = timezone.now()
            if result_asset:
                self.result_asset = result_asset
            if metrics:
                if isinstance(self.metrics, dict):
                    self.metrics.update(metrics)
                else:
                    self.metrics = metrics
            self.save(update_fields=['status', 'completed_at', 'result_asset', 'metrics', 'updated_at'])

    def mark_failed(self, error_message=None, execution_log_entry=None):
        """
        Mark execution as failed.

        Args:
            error_message: Optional error message
            execution_log_entry: Optional log entry to add to execution_log
        """
        if self.status in [ExecutionStatus.PENDING, ExecutionStatus.RUNNING]:
            self.status = ExecutionStatus.FAILED
            self.completed_at = timezone.now()

            # Add error to execution log
            if execution_log_entry:
                if isinstance(self.execution_log, list):
                    log_entry = {
                        "timestamp": timezone.now().isoformat(),
                        "level": "ERROR",
                        "message": execution_log_entry
                    }
                    self.execution_log.append(log_entry)
                else:
                    self.execution_log = [{
                        "timestamp": timezone.now().isoformat(),
                        "level": "ERROR",
                        "message": execution_log_entry
                    }]
            elif error_message:
                if isinstance(self.execution_log, list):
                    log_entry = {
                        "timestamp": timezone.now().isoformat(),
                        "level": "ERROR",
                        "message": error_message
                    }
                    self.execution_log.append(log_entry)
                else:
                    self.execution_log = [{
                        "timestamp": timezone.now().isoformat(),
                        "level": "ERROR",
                        "message": error_message
                    }]

            self.save(update_fields=['status', 'completed_at', 'execution_log', 'updated_at'])

    def mark_cancelled(self):
        """Mark execution as cancelled"""
        if self.can_cancel():
            self.status = ExecutionStatus.CANCELLED
            self.completed_at = timezone.now()
            self.add_log_entry("Execution cancelled", "INFO")
            self.save(update_fields=['status', 'completed_at', 'execution_log', 'updated_at'])

    def sync_status_from_job(self):
        """
        Synchronize execution status from linked job status.

        Updates execution status based on job status:
        - PENDING -> PENDING
        - RUNNING -> RUNNING
        - COMPLETED -> COMPLETED
        - FAILED -> FAILED
        - CANCELLED -> CANCELLED

        Returns:
            bool: True if status was updated, False otherwise
        """
        if not self.job:
            return False

        from hub.apps.jobs.models import JobStatus

        job_status = self.job.status
        updated = False

        # Don't update if execution is already in a terminal state and job is not terminal
        # This prevents overwriting terminal execution states with non-terminal job states
        if self.is_terminal():
            if job_status not in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                # Execution is terminal but job is not - don't update
                return False
            # If both are terminal, allow sync to ensure consistency (but only if statuses match)
            # For example, if execution is COMPLETED and job is COMPLETED, no update needed
            if (self.status == ExecutionStatus.COMPLETED and job_status == JobStatus.COMPLETED) or \
               (self.status == ExecutionStatus.FAILED and job_status == JobStatus.FAILED) or \
               (self.status == ExecutionStatus.CANCELLED and job_status == JobStatus.CANCELLED):
                return False  # Already in sync

        # Map job status to execution status
        if job_status == JobStatus.PENDING and self.status != ExecutionStatus.PENDING:
            # Job is pending, execution should be pending
            if self.status not in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED]:
                self.status = ExecutionStatus.PENDING
                updated = True
        elif job_status == JobStatus.RUNNING and self.status != ExecutionStatus.RUNNING:
            # Job is running, execution should be running
            if not self.started_at:
                self.started_at = timezone.now()
            if self.status == ExecutionStatus.PENDING:
                self.status = ExecutionStatus.RUNNING
                updated = True
        elif job_status == JobStatus.COMPLETED and self.status != ExecutionStatus.COMPLETED:
            # Job completed, execution should be completed
            # Only update if execution is in a non-terminal state
            if self.status in [ExecutionStatus.PENDING, ExecutionStatus.RUNNING]:
                self.status = ExecutionStatus.COMPLETED
                if not self.completed_at:
                    self.completed_at = timezone.now()
                # Note: result_asset may not be set when syncing from job
                # This is acceptable as the job handler should set it
                updated = True
        elif job_status == JobStatus.FAILED and self.status != ExecutionStatus.FAILED:
            # Job failed, execution should be failed
            if self.status in [ExecutionStatus.PENDING, ExecutionStatus.RUNNING]:
                self.status = ExecutionStatus.FAILED
                if not self.completed_at:
                    self.completed_at = timezone.now()
                error_msg = self.job.error_message or "Job execution failed"
                self.add_log_entry(f"Job failed: {error_msg}", "ERROR")
                updated = True
        elif job_status == JobStatus.CANCELLED and self.status != ExecutionStatus.CANCELLED:
            # Job cancelled, execution should be cancelled
            if self.status in [ExecutionStatus.PENDING, ExecutionStatus.RUNNING]:
                self.status = ExecutionStatus.CANCELLED
                if not self.completed_at:
                    self.completed_at = timezone.now()
                self.add_log_entry("Execution cancelled via job cancellation", "INFO")
                updated = True

        if updated:
            self.save(update_fields=['status', 'started_at', 'completed_at', 'execution_log', 'updated_at'])

        return updated

    def add_log_entry(self, message: str, level: str = "INFO"):
        """
        Add an entry to the execution log.

        Args:
            message: Log message
            level: Log level (INFO, WARNING, ERROR, DEBUG)
        """
        if not isinstance(self.execution_log, list):
            self.execution_log = []

        log_entry = {
            "timestamp": timezone.now().isoformat(),
            "level": level.upper(),
            "message": message
        }
        self.execution_log.append(log_entry)
        self.save(update_fields=['execution_log', 'updated_at'])

    def get_duration_seconds(self) -> float:
        """
        Get execution duration in seconds.

        Returns:
            Duration in seconds, or None if execution hasn't completed
        """
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def update_metrics(self, **kwargs):
        """
        Update execution metrics.

        Args:
            **kwargs: Metric key-value pairs to update
        """
        if not isinstance(self.metrics, dict):
            self.metrics = {}

        self.metrics.update(kwargs)
        self.save(update_fields=['metrics', 'updated_at'])

    def get_workflow_instance(self):
        """
        Get the workflow instance associated with this execution.

        Returns:
            WorkflowInstance or None
        """
        return self.workflow_instance

    def set_workflow_instance(self, workflow_instance):
        """
        Set the workflow instance for this execution.

        Args:
            workflow_instance: WorkflowInstance instance
        """
        self.workflow_instance = workflow_instance
        self.save(update_fields=['workflow_instance', 'updated_at'])

    def sync_status_from_workflow(self):
        """
        Synchronize execution status from linked workflow instance status.

        Updates execution status based on workflow status:
        - RUNNING -> RUNNING
        - COMPLETED -> COMPLETED
        - FAILED -> FAILED
        - CANCELLED -> CANCELLED
        - ROLLED_BACK -> FAILED

        Returns:
            bool: True if status was updated, False otherwise
        """
        if not self.workflow_instance:
            return False

        from hub.apps.orchestration.models import WorkflowStatus

        workflow_status = self.workflow_instance.status
        updated = False

        # Don't update if execution is already in a terminal state and workflow is not terminal
        if self.is_terminal():
            if workflow_status not in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, WorkflowStatus.CANCELLED, WorkflowStatus.ROLLED_BACK]:
                return False
            # If both are terminal, allow sync to ensure consistency
            if (self.status == ExecutionStatus.COMPLETED and workflow_status == WorkflowStatus.COMPLETED) or \
               (self.status == ExecutionStatus.FAILED and workflow_status in [WorkflowStatus.FAILED, WorkflowStatus.ROLLED_BACK]) or \
               (self.status == ExecutionStatus.CANCELLED and workflow_status == WorkflowStatus.CANCELLED):
                return False  # Already in sync

        # Map workflow status to execution status
        if workflow_status == WorkflowStatus.RUNNING and self.status != ExecutionStatus.RUNNING:
            if self.status == ExecutionStatus.PENDING:
                self.status = ExecutionStatus.RUNNING
                if not self.started_at:
                    self.started_at = timezone.now()
                updated = True
        elif workflow_status == WorkflowStatus.COMPLETED and self.status != ExecutionStatus.COMPLETED:
            if self.status in [ExecutionStatus.PENDING, ExecutionStatus.RUNNING]:
                self.status = ExecutionStatus.COMPLETED
                if not self.completed_at:
                    self.completed_at = timezone.now()
                # Get result_asset_id from workflow state_data if available
                if self.workflow_instance.state_data and "result_asset_id" in self.workflow_instance.state_data:
                    from hub.apps.assets.models import Asset
                    try:
                        result_asset_id = self.workflow_instance.state_data["result_asset_id"]
                        if result_asset_id:
                            result_asset = Asset.objects.get(id=result_asset_id)
                            self.result_asset = result_asset
                    except Asset.DoesNotExist:
                        pass
                updated = True
        elif workflow_status == WorkflowStatus.FAILED and self.status != ExecutionStatus.FAILED:
            if self.status in [ExecutionStatus.PENDING, ExecutionStatus.RUNNING]:
                self.status = ExecutionStatus.FAILED
                if not self.completed_at:
                    self.completed_at = timezone.now()
                error_msg = self.workflow_instance.error_message or "Workflow execution failed"
                self.add_log_entry(f"Workflow failed: {error_msg}", "ERROR")
                updated = True
        elif workflow_status == WorkflowStatus.ROLLED_BACK and self.status != ExecutionStatus.FAILED:
            if self.status in [ExecutionStatus.PENDING, ExecutionStatus.RUNNING]:
                self.status = ExecutionStatus.FAILED
                if not self.completed_at:
                    self.completed_at = timezone.now()
                self.add_log_entry("Workflow rolled back", "ERROR")
                updated = True
        elif workflow_status == WorkflowStatus.CANCELLED and self.status != ExecutionStatus.CANCELLED:
            if self.status in [ExecutionStatus.PENDING, ExecutionStatus.RUNNING]:
                self.status = ExecutionStatus.CANCELLED
                if not self.completed_at:
                    self.completed_at = timezone.now()
                self.add_log_entry("Execution cancelled via workflow cancellation", "INFO")
                updated = True

        if updated:
            self.save(update_fields=['status', 'started_at', 'completed_at', 'result_asset', 'execution_log', 'updated_at'])

        return updated

    def get_workflow_progress(self) -> Optional[float]:
        """
        Get workflow execution progress percentage.

        Returns:
            Progress percentage (0.0-100.0) or None if no workflow instance
        """
        if not self.workflow_instance:
            return None

        from hub.apps.orchestration.models import WorkflowInstance
        from hub.apps.orchestration.workflow_engine import WorkflowEngine

        engine = WorkflowEngine()
        progress = engine._calculate_progress(self.workflow_instance)
        return progress

    def get_workflow_state(self) -> Optional[Dict[str, Any]]:
        """
        Get workflow state data.

        Returns:
            Workflow state data dictionary or None if no workflow instance
        """
        if not self.workflow_instance:
            return None

        return self.workflow_instance.state_data if self.workflow_instance.state_data else {}


class WranglingOperationType(models.TextChoices):
    """Wrangling operation type enumeration"""
    FILTER = "FILTER", "Filter"
    SORT = "SORT", "Sort"
    TRANSFORM = "TRANSFORM", "Transform"
    AGGREGATE = "AGGREGATE", "Aggregate"
    JOIN = "JOIN", "Join"
    GROUP = "GROUP", "Group"
    PIVOT = "PIVOT", "Pivot"
    UNPIVOT = "UNPIVOT", "Unpivot"
    RENAME_COLUMN = "RENAME_COLUMN", "Rename Column"
    DROP_COLUMN = "DROP_COLUMN", "Drop Column"
    ADD_COLUMN = "ADD_COLUMN", "Add Column"
    SPLIT_COLUMN = "SPLIT_COLUMN", "Split Column"
    MERGE_COLUMNS = "MERGE_COLUMNS", "Merge Columns"
    DEDUPLICATE = "DEDUPLICATE", "Deduplicate"
    FILL_NULLS = "FILL_NULLS", "Fill Nulls"
    REMOVE_NULLS = "REMOVE_NULLS", "Remove Nulls"
    TYPE_CONVERSION = "TYPE_CONVERSION", "Type Conversion"


class WranglingSession(models.Model):
    """
    Data Wrangling Session model.

    Represents an interactive data wrangling session where users can
    perform operations on data with undo/redo support.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the wrangling session"
    )
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="wrangling_sessions",
        help_text="Tenant this session belongs to"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_wrangling_sessions",
        null=True,
        blank=True,
        help_text="User who created the session"
    )
    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.CASCADE,
        related_name="wrangling_sessions",
        help_text="Source asset being wrangled"
    )
    name = models.CharField(
        max_length=255,
        help_text="Session name"
    )
    description = models.TextField(
        null=True,
        blank=True,
        help_text="Session description"
    )
    # Current state snapshot (JSON representation of current data state)
    current_state = models.JSONField(
        null=True,
        blank=True,
        help_text="Current state snapshot after all operations"
    )
    # Operation history (list of operations with undo/redo support)
    operation_history = models.JSONField(
        default=list,
        help_text="List of operations performed in this session"
    )
    # Current position in history (for undo/redo)
    history_position = models.IntegerField(
        default=-1,
        help_text="Current position in operation history (-1 = at end)"
    )
    # Generated wrangling script
    wrangling_script = models.TextField(
        null=True,
        blank=True,
        help_text="Generated script representation of operations"
    )
    # Metadata
    metadata = models.JSONField(
        null=True,
        blank=True,
        default=dict,
        help_text="Additional metadata"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the session was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the session was last updated"
    )

    class Meta:
        db_table = 'wrangling_sessions'
        indexes = [
            models.Index(fields=['tenant', 'asset']),
            models.Index(fields=['created_by', 'created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"Wrangling Session: {self.name} ({self.id})"

    def add_operation(self, operation: Dict[str, Any]) -> int:
        """
        Add an operation to the history.

        Args:
            operation: Operation dictionary with type, parameters, etc.

        Returns:
            Index of the added operation
        """
        if not isinstance(self.operation_history, list):
            self.operation_history = []

        # If we're not at the end of history, truncate future operations (redo is lost)
        if self.history_position < len(self.operation_history) - 1:
            self.operation_history = self.operation_history[:self.history_position + 1]

        # Add operation
        operation_with_metadata = {
            **operation,
            "timestamp": timezone.now().isoformat(),
            "index": len(self.operation_history)
        }
        self.operation_history.append(operation_with_metadata)
        self.history_position = len(self.operation_history) - 1
        self.save(update_fields=['operation_history', 'history_position', 'updated_at'])

        return self.history_position

    def can_undo(self) -> bool:
        """Check if undo is possible"""
        return self.history_position >= 0

    def can_redo(self) -> bool:
        """Check if redo is possible"""
        return (
            isinstance(self.operation_history, list) and
            self.history_position < len(self.operation_history) - 1
        )

    def undo(self) -> Optional[Dict[str, Any]]:
        """
        Undo the last operation.

        Returns:
            The operation that was undone, or None if no operation to undo
        """
        if not self.can_undo():
            return None

        undone_operation = self.operation_history[self.history_position]
        self.history_position -= 1
        self.save(update_fields=['history_position', 'updated_at'])

        return undone_operation

    def redo(self) -> Optional[Dict[str, Any]]:
        """
        Redo the next operation.

        Returns:
            The operation that was redone, or None if no operation to redo
        """
        if not self.can_redo():
            return None

        self.history_position += 1
        redone_operation = self.operation_history[self.history_position]
        self.save(update_fields=['history_position', 'updated_at'])

        return redone_operation

    def get_applied_operations(self) -> List[Dict[str, Any]]:
        """
        Get all operations that are currently applied (up to history_position).

        Returns:
            List of applied operations
        """
        if not isinstance(self.operation_history, list):
            return []

        return self.operation_history[:self.history_position + 1]

    def generate_script(self, script_format: str = "python") -> str:
        """
        Generate a script representation of the applied operations.

        Args:
            script_format: Script format ("python", "sql", "json")

        Returns:
            Generated script as string
        """
        applied_ops = self.get_applied_operations()

        if script_format == "python":
            return self._generate_python_script(applied_ops)
        elif script_format == "sql":
            return self._generate_sql_script(applied_ops)
        elif script_format == "json":
            import json
            return json.dumps(applied_ops, indent=2)
        else:
            raise ValueError(f"Unsupported script format: {script_format}")

    def _generate_python_script(self, operations: List[Dict[str, Any]]) -> str:
        """Generate Python script from operations"""
        lines = ["# Data Wrangling Script", "import pandas as pd", "", "df = pd.read_csv('input.csv')  # Load your data", ""]

        for op in operations:
            op_type = op.get("type")
            params = op.get("parameters", {})

            if op_type == "FILTER":
                condition = params.get("condition", "")
                lines.append(f"df = df[{condition}]")
            elif op_type == "SORT":
                columns = params.get("columns", [])
                ascending = params.get("ascending", True)
                lines.append(f"df = df.sort_values({columns}, ascending={ascending})")
            elif op_type == "TRANSFORM":
                column = params.get("column", "")
                expression = params.get("expression", "")
                lines.append(f"df['{column}'] = {expression}")
            elif op_type == "RENAME_COLUMN":
                old_name = params.get("old_name", "")
                new_name = params.get("new_name", "")
                lines.append(f"df = df.rename(columns={{'{old_name}': '{new_name}'}})")
            elif op_type == "DROP_COLUMN":
                columns = params.get("columns", [])
                lines.append(f"df = df.drop(columns={columns})")
            # Add more operation types as needed

        lines.append("")
        lines.append("df.to_csv('output.csv', index=False)  # Save result")
        return "\n".join(lines)

    def _generate_sql_script(self, operations: List[Dict[str, Any]]) -> str:
        """Generate SQL script from operations"""
        # Simplified SQL generation - would need more complex logic for full SQL
        lines = ["-- Data Wrangling SQL Script", "SELECT * FROM input_table"]

        for op in operations:
            op_type = op.get("type")
            params = op.get("parameters", {})

            if op_type == "FILTER":
                condition = params.get("condition", "")
                lines.append(f"WHERE {condition}")
            elif op_type == "SORT":
                columns = params.get("columns", [])
                ascending = params.get("ascending", True)
                order = "ASC" if ascending else "DESC"
                lines.append(f"ORDER BY {', '.join(columns)} {order}")

        return "\n".join(lines)


class WranglingOperation(models.Model):
    """
    Individual Wrangling Operation model.

    Represents a single data wrangling operation with its parameters and result.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the operation"
    )
    session = models.ForeignKey(
        WranglingSession,
        on_delete=models.CASCADE,
        related_name="operations",
        help_text="Wrangling session this operation belongs to"
    )
    operation_type = models.CharField(
        max_length=50,
        choices=WranglingOperationType.choices,
        help_text="Type of operation"
    )
    parameters = models.JSONField(
        help_text="Operation parameters (operation-specific)"
    )
    # Result snapshot (optional, for large results we might not store)
    result_snapshot = models.JSONField(
        null=True,
        blank=True,
        help_text="Result snapshot after operation (optional)"
    )
    # Metadata
    metadata = models.JSONField(
        null=True,
        blank=True,
        default=dict,
        help_text="Additional operation metadata"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the operation was created"
    )

    class Meta:
        db_table = 'wrangling_operations'
        indexes = [
            models.Index(fields=['session', 'created_at']),
            models.Index(fields=['operation_type']),
        ]
        ordering = ['created_at']

    def __str__(self):
        return f"{self.get_operation_type_display()}: {self.id}"


class PreviewResult(models.Model):
    """
    Preview Result model.

    Stores preview results for transformation pipelines to enable retrieval by preview_id.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the preview result"
    )
    preview_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Preview ID (hash-based identifier)"
    )
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="preview_results",
        help_text="Tenant this preview belongs to"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_preview_results",
        null=True,
        blank=True,
        help_text="User who created the preview"
    )
    pipeline = models.ForeignKey(
        TransformationPipeline,
        on_delete=models.CASCADE,
        related_name="preview_results",
        help_text="Pipeline that was previewed"
    )
    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.CASCADE,
        related_name="preview_results",
        help_text="Source asset that was previewed"
    )
    # Preview result data
    preview_data = models.JSONField(
        help_text="Complete preview result data (input_sample, output_sample, analysis, etc.)"
    )
    # Cache key for reference
    cache_key = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Cache key used to store the preview result"
    )
    # Metadata
    sample_size = models.IntegerField(
        help_text="Number of rows sampled"
    )
    sampling_method = models.CharField(
        max_length=50,
        help_text="Sampling method used (first_n, random)"
    )
    generated_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the preview was generated"
    )
    expires_at = models.DateTimeField(
        help_text="When the preview expires (typically 1 hour after generation)"
    )

    class Meta:
        db_table = 'preview_results'
        ordering = ['-generated_at']
        indexes = [
            models.Index(fields=['preview_id']),
            models.Index(fields=['tenant', 'generated_at']),
            models.Index(fields=['pipeline', 'generated_at']),
            models.Index(fields=['asset', 'generated_at']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"Preview {self.preview_id} for {self.pipeline.name}"

    def is_expired(self) -> bool:
        """Check if preview has expired"""
        from django.utils import timezone
        return timezone.now() > self.expires_at

