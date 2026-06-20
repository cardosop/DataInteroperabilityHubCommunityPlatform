"""
Virtualization Models

Models for data virtualization and federated query capabilities.
"""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from hub.apps.integrations.encryption import (
    EncryptionError,
    decrypt_json_field,
    encrypt_json_field,
)


def default_empty_dict():
    """Return a new empty dict. Used as default for JSONField to avoid mutable default argument."""
    return {}


def default_empty_list():
    """Return a new empty list. Used as default for JSONField to avoid mutable default argument."""
    return []


class QueryType(models.TextChoices):
    """Query type enumeration for virtual datasets"""

    SQL = "SQL", "SQL Query"
    SPARQL = "SPARQL", "SPARQL Query"
    FEDERATED = "FEDERATED", "Federated Query"
    GRAPHQL = "GRAPHQL", "GraphQL Query"
    REST = "REST", "REST API Query"


class VirtualDatasetStatus(models.TextChoices):
    """Virtual dataset status enumeration"""

    DRAFT = "DRAFT", "Draft"
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"
    ARCHIVED = "ARCHIVED", "Archived"


class QueryExecutionStatus(models.TextChoices):
    """Query execution status enumeration"""

    PENDING = "PENDING", "Pending"
    RUNNING = "RUNNING", "Running"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"
    CANCELLED = "CANCELLED", "Cancelled"


class QueryExecutionMode(models.TextChoices):
    """Query execution mode enumeration"""

    SYNC = "SYNC", "Synchronous"
    ASYNC = "ASYNC", "Asynchronous"
    SCHEDULED = "SCHEDULED", "Scheduled"
    MANUAL = "MANUAL", "Manual"
    AUTOMATED = "AUTOMATED", "Automated"


class VirtualDataset(models.Model):
    """
    Virtual Dataset model representing a federated query across multiple data sources.

    A virtual dataset provides a unified view over multiple data sources without
    physically copying or moving data. It defines:
    - Query definition (SQL, SPARQL, federated, etc.)
    - Source systems and their configurations
    - Schema definition (output schema)
    - Version tracking
    - Status management

    Fields:
        id: UUID primary key
        tenant: Foreign key to Tenant (CASCADE delete)
        created_by: Foreign key to User who created the dataset (SET_NULL on delete)
        name: Dataset name (required, max 255 chars)
        description: Dataset description (optional)
        query: Query definition string (SQL, SPARQL, etc.)
        query_type: Type of query (SQL, SPARQL, FEDERATED, etc.)
        schema: JSONB field storing output schema definition
        sources: JSONB field storing source system configurations
        version: Version string (semantic versioning: major.minor.patch)
        status: Dataset status (DRAFT, ACTIVE, INACTIVE, ARCHIVED)
        created_at: Timestamp when dataset was created
        updated_at: Timestamp when dataset was last updated
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the virtual dataset",
    )
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="virtual_datasets",
        help_text="Tenant this virtual dataset belongs to",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_virtual_datasets",
        null=True,
        blank=True,
        help_text="User who created the virtual dataset",
    )
    name = models.CharField(max_length=255, help_text="Virtual dataset name (unique per tenant)")
    description = models.TextField(null=True, blank=True, help_text="Virtual dataset description")
    query = models.TextField(help_text="Query definition (SQL, SPARQL, federated query, etc.)")
    query_type = models.CharField(
        max_length=20,
        choices=QueryType.choices,
        help_text="Type of query: SQL, SPARQL, FEDERATED, GRAPHQL, REST",
    )
    schema = models.JSONField(
        default=default_empty_dict,
        blank=True,
        null=True,
        help_text="Output schema definition as JSON (fields, types, constraints, etc.)",
    )
    sources = models.JSONField(
        default=default_empty_list,
        blank=True,
        null=True,
        help_text="Source system configurations as JSON array (connection details, mappings, etc.)",
    )
    version = models.CharField(
        max_length=50,
        default="1.0.0",
        help_text="Virtual dataset version (semantic versioning: major.minor.patch)",
    )
    status = models.CharField(
        max_length=20,
        choices=VirtualDatasetStatus.choices,
        default=VirtualDatasetStatus.DRAFT,
        help_text="Virtual dataset status: DRAFT, ACTIVE, INACTIVE, ARCHIVED",
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="When the virtual dataset was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True, help_text="When the virtual dataset was last updated"
    )

    class Meta:
        db_table = "virtual_datasets"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["created_by"]),
            models.Index(fields=["query_type"]),
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "query_type"]),
            models.Index(fields=["tenant", "created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name", "version"],
                name="unique_virtual_dataset_name_version_per_tenant",
            )
        ]

    def __str__(self):
        return f"{self.name} v{self.version} ({self.status})"

    def clean(self):
        """
        Validate the virtual dataset model.

        Raises:
            ValidationError: If validation fails
        """
        super().clean()

        # Validate name is not empty
        if not self.name or not self.name.strip():
            raise ValidationError({"name": "Virtual dataset name cannot be empty"})

        # Validate query is not empty
        if not self.query or not self.query.strip():
            raise ValidationError({"query": "Query definition cannot be empty"})

        # Validate schema is a dictionary
        if self.schema is not None and not isinstance(self.schema, dict):
            raise ValidationError({"schema": "Schema must be a JSON object"})

        # Validate sources is a list (skip if already encrypted)
        if self.sources is not None:
            if isinstance(self.sources, dict) and "_encrypted" in self.sources:
                pass  # Already encrypted, skip validation
            elif not isinstance(self.sources, list):
                raise ValidationError({"sources": "Sources must be a JSON array"})

        # Validate version format (basic semantic versioning check)
        if self.version:
            version_parts = self.version.split(".")
            if len(version_parts) != 3:
                raise ValidationError(
                    {
                        "version": "Version must follow semantic versioning format (major.minor.patch)"
                    }
                )
            try:
                int(version_parts[0])  # major
                int(version_parts[1])  # minor
                int(version_parts[2])  # patch
            except ValueError:
                raise ValidationError({"version": "Version parts must be numeric (e.g., '1.0.0')"})

        # Validate query type matches query content (basic validation)
        if self.query_type == QueryType.SQL:
            # Basic SQL validation - check for common SQL keywords
            query_upper = self.query.upper().strip()
            if not any(
                keyword in query_upper
                for keyword in ["SELECT", "WITH", "INSERT", "UPDATE", "DELETE"]
            ):
                raise ValidationError(
                    {"query": "SQL query should contain SQL keywords (SELECT, WITH, etc.)"}
                )
        elif self.query_type == QueryType.SPARQL:
            # Basic SPARQL validation - check for SPARQL keywords
            query_upper = self.query.upper().strip()
            if not any(
                keyword in query_upper
                for keyword in ["SELECT", "CONSTRUCT", "ASK", "DESCRIBE", "PREFIX"]
            ):
                raise ValidationError(
                    {
                        "query": "SPARQL query should contain SPARQL keywords (SELECT, CONSTRUCT, ASK, DESCRIBE, PREFIX)"
                    }
                )

    def save(self, *args, **kwargs):
        """
        Save the virtual dataset with validation and sources encryption.

        Raises:
            ValidationError: If validation fails
        """
        self.full_clean()

        # Encrypt sources if plaintext list (not already encrypted)
        if isinstance(self.sources, list) and self.sources:
            try:
                wrapper = {"_items": self.sources}
                encrypted = encrypt_json_field(wrapper)
                self.sources = {"_encrypted": encrypted}
            except EncryptionError as e:
                raise ValidationError({"sources": f"Failed to encrypt: {e}"}) from e

        super().save(*args, **kwargs)

    def get_sources(self) -> list:
        """
        Get decrypted sources list.

        Returns:
            Decrypted sources list.
            Legacy plaintext lists (pre-migration) returned as-is.
        """
        if not self.sources:
            return []
        if isinstance(self.sources, dict):
            if "_encrypted" in self.sources:
                decrypted = decrypt_json_field(self.sources["_encrypted"])
                return decrypted.get("_items", [])
            return []
        if isinstance(self.sources, list):
            return self.sources
        return []

    def get_schema_fields(self):
        """
        Get schema fields as a list.

        Returns:
            List of schema field definitions, or empty list if schema is not defined
        """
        if not self.schema or not isinstance(self.schema, dict):
            return []

        # Schema can be structured in different ways
        # Common patterns: {"fields": [...]} or direct list
        if "fields" in self.schema and isinstance(self.schema["fields"], list):
            return self.schema["fields"]
        elif isinstance(self.schema, dict):
            # If schema is a dict with field names as keys
            return list(self.schema.keys())
        return []

    def get_source_count(self):
        """
        Get the number of source systems configured.

        Returns:
            Integer count of sources, or 0 if sources is not defined
        """
        return len(self.get_sources())

    def is_active(self):
        """
        Check if the virtual dataset is active.

        Returns:
            Boolean indicating if status is ACTIVE
        """
        return self.status == VirtualDatasetStatus.ACTIVE


class QueryExecutionStatus(models.TextChoices):
    """Query execution status enumeration"""

    PENDING = "PENDING", "Pending"
    RUNNING = "RUNNING", "Running"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"
    CANCELLED = "CANCELLED", "Cancelled"


class QueryExecutionMode(models.TextChoices):
    """Query execution mode enumeration"""

    SYNC = "SYNC", "Synchronous"
    ASYNC = "ASYNC", "Asynchronous"
    SCHEDULED = "SCHEDULED", "Scheduled"
    MANUAL = "MANUAL", "Manual"
    AUTOMATED = "AUTOMATED", "Automated"


class QueryExecution(models.Model):
    """
    Query Execution model representing a single execution of a virtual dataset query.

    Tracks query execution lifecycle, including:
    - Execution parameters and query text
    - Execution mode (sync, async, scheduled, etc.)
    - Status tracking (pending, running, completed, failed, cancelled)
    - Timing information (started_at, completed_at)
    - Result storage (cache key, storage path)
    - Execution logs and metrics

    Fields:
        id: UUID primary key
        virtual_dataset: Foreign key to VirtualDataset (CASCADE delete)
        query: Query text executed (may differ from virtual_dataset.query if parameterized)
        parameters: JSONB field storing query parameters
        execution_mode: Execution mode (SYNC, ASYNC, SCHEDULED, MANUAL, AUTOMATED)
        status: Execution status (PENDING, RUNNING, COMPLETED, FAILED, CANCELLED)
        started_at: Timestamp when execution started (null if not started)
        completed_at: Timestamp when execution completed (null if not completed)
        result_cache_key: Cache key for result storage (optional)
        result_storage_path: Path to stored result file (optional)
        execution_log: JSONB field storing execution logs and messages
        metrics: JSONB field storing execution metrics (duration, rows processed, etc.)
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the query execution",
    )
    virtual_dataset = models.ForeignKey(
        VirtualDataset,
        on_delete=models.CASCADE,
        related_name="executions",
        help_text="Virtual dataset that was executed",
    )
    query = models.TextField(
        help_text="Query text that was executed (may include parameter substitution)"
    )
    parameters = models.JSONField(
        default=default_empty_dict,
        blank=True,
        null=True,
        help_text="Query parameters as JSON object (parameter name -> value mapping)",
    )
    execution_mode = models.CharField(
        max_length=20,
        choices=QueryExecutionMode.choices,
        default=QueryExecutionMode.MANUAL,
        help_text="Execution mode: SYNC, ASYNC, SCHEDULED, MANUAL, AUTOMATED",
    )
    status = models.CharField(
        max_length=20,
        choices=QueryExecutionStatus.choices,
        default=QueryExecutionStatus.PENDING,
        help_text="Execution status: PENDING, RUNNING, COMPLETED, FAILED, CANCELLED",
    )
    started_at = models.DateTimeField(null=True, blank=True, help_text="When the execution started")
    completed_at = models.DateTimeField(
        null=True, blank=True, help_text="When the execution completed"
    )
    result_cache_key = models.CharField(
        max_length=255, null=True, blank=True, help_text="Cache key for result storage (optional)"
    )
    result_storage_path = models.CharField(
        max_length=512, null=True, blank=True, help_text="Path to stored result file (optional)"
    )
    execution_log = models.JSONField(
        default=default_empty_list,
        blank=True,
        null=True,
        help_text="Execution logs as JSON array (log entries with timestamp, level, message)",
    )
    metrics = models.JSONField(
        default=default_empty_dict,
        blank=True,
        null=True,
        help_text="Execution metrics as JSON object (duration_ms, rows_processed, memory_used, etc.)",
    )
    job = models.ForeignKey(
        "jobs.Job",
        on_delete=models.SET_NULL,
        related_name="query_executions",
        null=True,
        blank=True,
        help_text="Job record for async execution (null for sync executions)",
    )
    workflow_instance = models.ForeignKey(
        "orchestration.WorkflowInstance",
        on_delete=models.SET_NULL,
        related_name="query_executions",
        null=True,
        blank=True,
        help_text="Workflow instance that orchestrates this execution (null if not using workflow)",
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="When the query execution was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True, help_text="When the query execution was last updated"
    )

    class Meta:
        db_table = "query_executions"
        ordering = ["-started_at", "-created_at"]
        indexes = [
            models.Index(fields=["virtual_dataset"]),
            models.Index(fields=["status"]),
            models.Index(fields=["started_at"]),
            models.Index(fields=["virtual_dataset", "status"]),
            models.Index(fields=["virtual_dataset", "started_at"]),
            models.Index(fields=["workflow_instance"]),
        ]

    def __str__(self):
        return f"QueryExecution {self.id} - {self.virtual_dataset.name} ({self.status})"

    def clean(self):
        """
        Validate the query execution model.

        Raises:
            ValidationError: If validation fails
        """
        super().clean()

        # Validate query is not empty
        if not self.query or not self.query.strip():
            raise ValidationError({"query": "Query text cannot be empty"})

        # Validate parameters is a dictionary
        if self.parameters is not None and not isinstance(self.parameters, dict):
            raise ValidationError({"parameters": "Parameters must be a JSON object"})

        # Validate execution_log is a list
        if self.execution_log is not None and not isinstance(self.execution_log, list):
            raise ValidationError({"execution_log": "Execution log must be a JSON array"})

        # Validate metrics is a dictionary
        if self.metrics is not None and not isinstance(self.metrics, dict):
            raise ValidationError({"metrics": "Metrics must be a JSON object"})

        # Validate completed_at is after started_at if both are set
        if self.started_at and self.completed_at and self.completed_at < self.started_at:
            raise ValidationError(
                {"completed_at": "Completed timestamp must be after started timestamp"}
            )

        # Validate status transitions (only if timestamps are set)
        # Note: We allow status to be set without timestamps during creation,
        # but timestamps must be consistent if both are set
        if self.status == QueryExecutionStatus.COMPLETED:
            if self.completed_at is None and self.started_at is not None:
                # If started but not completed, this is invalid
                raise ValidationError(
                    {"completed_at": "Completed executions must have a completed_at timestamp"}
                )
        elif self.status == QueryExecutionStatus.FAILED:
            if self.completed_at is None and self.started_at is not None:
                # If started but not completed, this is invalid
                raise ValidationError(
                    {"completed_at": "Failed executions must have a completed_at timestamp"}
                )
        elif self.status == QueryExecutionStatus.RUNNING:
            # Allow RUNNING without started_at during creation, but if completed_at is set, started_at must be set too
            if self.completed_at is not None and self.started_at is None:
                raise ValidationError(
                    {
                        "started_at": "Running executions with completed_at must have a started_at timestamp"
                    }
                )

    def save(self, *args, **kwargs):
        """
        Save the query execution with validation.

        Raises:
            ValidationError: If validation fails
        """
        self.full_clean()
        super().save(*args, **kwargs)

    def get_duration_seconds(self):
        """
        Get execution duration in seconds.

        Returns:
            Float duration in seconds, or None if execution not completed
        """
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            return delta.total_seconds()
        return None

    def get_duration_ms(self):
        """
        Get execution duration in milliseconds.

        Returns:
            Integer duration in milliseconds, or None if execution not completed
        """
        duration_seconds = self.get_duration_seconds()
        if duration_seconds is not None:
            return int(duration_seconds * 1000)
        return None

    def add_log_entry(self, level, message, timestamp=None, save=True):
        """
        Add a log entry to execution_log.

        Args:
            level: Log level (INFO, WARNING, ERROR, DEBUG)
            message: Log message
            timestamp: Optional timestamp (defaults to timezone.now())
            save: Whether to save the model after adding the log entry (default: True)
        """
        if timestamp is None:
            timestamp = timezone.now()

        if self.execution_log is None:
            self.execution_log = []

        log_entry = {
            "timestamp": timestamp.isoformat(),
            "level": level,
            "message": message,
        }
        self.execution_log.append(log_entry)

        if save:
            self.save(update_fields=["execution_log", "updated_at"])

    def set_metric(self, key, value, save=True):
        """
        Set a metric value.

        Args:
            key: Metric key (e.g., 'duration_ms', 'rows_processed')
            value: Metric value
            save: Whether to save the model after setting the metric (default: True)
        """
        if self.metrics is None:
            self.metrics = {}
        self.metrics[key] = value

        if save:
            self.save(update_fields=["metrics", "updated_at"])

    def get_metric(self, key, default=None):
        """
        Get a metric value.

        Args:
            key: Metric key
            default: Default value if key not found

        Returns:
            Metric value or default
        """
        if self.metrics is None:
            return default
        return self.metrics.get(key, default)

    def is_completed(self):
        """
        Check if execution is completed (successfully or failed).

        Returns:
            Boolean indicating if status is COMPLETED or FAILED
        """
        return self.status in [
            QueryExecutionStatus.COMPLETED,
            QueryExecutionStatus.FAILED,
            QueryExecutionStatus.CANCELLED,
        ]

    def is_running(self):
        """
        Check if execution is currently running.

        Returns:
            Boolean indicating if status is RUNNING
        """
        return self.status == QueryExecutionStatus.RUNNING

    def can_cancel(self) -> bool:
        """
        Check if execution can be cancelled.

        Returns:
            Boolean indicating if execution can be cancelled (PENDING or RUNNING status)
        """
        return self.status in [QueryExecutionStatus.PENDING, QueryExecutionStatus.RUNNING]

    def mark_started(self):
        """
        Mark execution as started.

        Sets status to RUNNING and started_at to current time.
        """
        self.status = QueryExecutionStatus.RUNNING
        self.started_at = timezone.now()
        self.save()

    def mark_completed(self, metrics=None):
        """
        Mark execution as completed.

        Args:
            metrics: Optional dict of metrics to set
        """
        self.status = QueryExecutionStatus.COMPLETED
        self.completed_at = timezone.now()
        if metrics:
            if self.metrics is None:
                self.metrics = {}
            self.metrics.update(metrics)
        # Set duration metric if not already set
        duration_ms = self.get_duration_ms()
        if duration_ms is not None:
            self.set_metric("duration_ms", duration_ms)
        self.save()

    def mark_failed(self, error_message=None, metrics=None):
        """
        Mark execution as failed.

        Args:
            error_message: Optional error message to add to logs
            metrics: Optional dict of metrics to set
        """
        self.status = QueryExecutionStatus.FAILED
        self.completed_at = timezone.now()
        if error_message:
            self.add_log_entry("ERROR", error_message)
        if metrics:
            if self.metrics is None:
                self.metrics = {}
            self.metrics.update(metrics)
        # Set duration metric if not already set
        duration_ms = self.get_duration_ms()
        if duration_ms is not None:
            self.set_metric("duration_ms", duration_ms)
        self.save()

    def mark_cancelled(self, reason=None):
        """
        Mark execution as cancelled.

        Args:
            reason: Optional cancellation reason to add to logs
        """
        self.status = QueryExecutionStatus.CANCELLED
        if self.started_at and not self.completed_at:
            self.completed_at = timezone.now()
        if reason:
            self.add_log_entry("WARNING", f"Execution cancelled: {reason}")
        self.save()

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
        if self.is_completed():
            if job_status not in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                # Execution is terminal but job is not - don't update
                return False
            # If both are terminal, allow sync to ensure consistency (but only if statuses match)
            # For example, if execution is COMPLETED and job is COMPLETED, no update needed
            if (
                (
                    self.status == QueryExecutionStatus.COMPLETED
                    and job_status == JobStatus.COMPLETED
                )
                or (self.status == QueryExecutionStatus.FAILED and job_status == JobStatus.FAILED)
                or (
                    self.status == QueryExecutionStatus.CANCELLED
                    and job_status == JobStatus.CANCELLED
                )
            ):
                return False  # Already in sync

        # Map job status to execution status
        if job_status == JobStatus.PENDING and self.status != QueryExecutionStatus.PENDING:
            # Job is pending, execution should be pending
            if self.status not in [
                QueryExecutionStatus.COMPLETED,
                QueryExecutionStatus.FAILED,
                QueryExecutionStatus.CANCELLED,
            ]:
                self.status = QueryExecutionStatus.PENDING
                updated = True
        elif job_status == JobStatus.RUNNING and self.status != QueryExecutionStatus.RUNNING:
            # Job is running, execution should be running
            if not self.started_at:
                self.started_at = timezone.now()
            if self.status == QueryExecutionStatus.PENDING:
                self.status = QueryExecutionStatus.RUNNING
                updated = True
        elif job_status == JobStatus.COMPLETED and self.status != QueryExecutionStatus.COMPLETED:
            # Job completed, execution should be completed
            # Only update if execution is in a non-terminal state
            if self.status in [QueryExecutionStatus.PENDING, QueryExecutionStatus.RUNNING]:
                self.status = QueryExecutionStatus.COMPLETED
                if not self.completed_at:
                    self.completed_at = timezone.now()
                updated = True
        elif job_status == JobStatus.FAILED and self.status != QueryExecutionStatus.FAILED:
            # Job failed, execution should be failed
            if self.status in [QueryExecutionStatus.PENDING, QueryExecutionStatus.RUNNING]:
                self.status = QueryExecutionStatus.FAILED
                if not self.completed_at:
                    self.completed_at = timezone.now()
                error_msg = self.job.error_message or "Job execution failed"
                self.add_log_entry("ERROR", f"Job failed: {error_msg}", save=False)
                updated = True
        elif job_status == JobStatus.CANCELLED and self.status != QueryExecutionStatus.CANCELLED:
            # Job cancelled, execution should be cancelled
            if self.status in [QueryExecutionStatus.PENDING, QueryExecutionStatus.RUNNING]:
                self.status = QueryExecutionStatus.CANCELLED
                if not self.completed_at:
                    self.completed_at = timezone.now()
                self.add_log_entry(
                    "WARNING", "Execution cancelled via job cancellation", save=False
                )
                updated = True

        if updated:
            update_fields = ["status", "updated_at"]
            if self.started_at:
                update_fields.append("started_at")
            if self.completed_at:
                update_fields.append("completed_at")
            if self.execution_log:
                update_fields.append("execution_log")
            self.save(update_fields=update_fields)

        return updated
