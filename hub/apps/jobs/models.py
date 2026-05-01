"""
Job Models

Generic job model for long-running operations (DQ, compliance, validation, etc.).
"""
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class JobType(models.TextChoices):
    """Job type enumeration"""
    DQ_RUN = "DQ_RUN", "Data Quality Run"
    COMPLIANCE_RUN = "COMPLIANCE_RUN", "Compliance Run"
    CONTRACT_VALIDATION = "CONTRACT_VALIDATION", "Contract Validation"
    SEMANTIC_MAPPING = "SEMANTIC_MAPPING", "Semantic Mapping"
    CONTRACT_MIGRATION = "CONTRACT_MIGRATION", "Contract Migration"
    SCHEDULED_INGESTION = "SCHEDULED_INGESTION", "Scheduled Ingestion"
    RETENTION_POLICY_ENFORCEMENT = "RETENTION_POLICY_ENFORCEMENT", "Retention Policy Enforcement"
    SEARCH_INDEX_UPDATE = "SEARCH_INDEX_UPDATE", "Search Index Update"
    ODPS_NORMALIZATION = "ODPS_NORMALIZATION", "ODPS Normalization"
    ODPS_REF_RESOLUTION = "ODPS_REF_RESOLUTION", "ODPS $ref Resolution"
    ODPS_EXPORT = "ODPS_EXPORT", "ODPS Export"
    ODPS_SEMANTIC_MAPPING = "ODPS_SEMANTIC_MAPPING", "ODPS Semantic Mapping"
    ODPS_LINKING = "ODPS_LINKING", "ODPS Linking"
    VIRTUAL_QUERY_EXECUTION = "VIRTUAL_QUERY_EXECUTION", "Virtual Query Execution"
    MARKETPLACE_SYNC = "MARKETPLACE_SYNC", "Marketplace Sync"
    ML_TRAINING = "ML_TRAINING", "ML Training"
    ML_INFERENCE = "ML_INFERENCE", "ML Inference"
    TRANSFORMATION = "TRANSFORMATION", "Transformation Pipeline"
    # Phase 230.2.4 — exports >100 MB are queued asynchronously
    # to avoid holding a request thread for tens of minutes; the
    # Job row carries the result S3 URI + an emailed download link
    # when it completes. Inline streaming is the synchronous path
    # (rdf_export view at hub/apps/semantic/views.py).
    SEMANTIC_EXPORT_LARGE = "SEMANTIC_EXPORT_LARGE", "Semantic Export (large)"
    # Phase 230.4 (REQ-SEM-MEMENTO-001) — async snapshot job. Triggered
    # by the debounced post-save signal on Asset / Contract / Dataset;
    # fetches the resource's RDF + computes a SHA-256 over a canonical
    # serialisation; persists into ``SemanticResourceVersion`` if the
    # hash differs from the latest row (the UniqueConstraint on
    # (resource, content_hash) gives us the dedupe primitive).
    SEMANTIC_SNAPSHOT = "SEMANTIC_SNAPSHOT", "Semantic Snapshot"


class JobStatus(models.TextChoices):
    """Job status enumeration"""
    PENDING = "PENDING", "Pending"
    RUNNING = "RUNNING", "Running"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"
    CANCELLED = "CANCELLED", "Cancelled"


class JobPriority(models.TextChoices):
    """Job priority enumeration"""
    LOW = "LOW", "Low"
    NORMAL = "NORMAL", "Normal"
    HIGH = "HIGH", "High"
    CRITICAL = "CRITICAL", "Critical"


class Job(models.Model):
    """
    Generic job model for long-running operations.

    Tracks DQ runs, compliance checks, contract validation, semantic mapping, etc.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="jobs",
        null=True,
        blank=True,
        help_text="Tenant this job belongs to (nullable for system jobs)"
    )
    type = models.CharField(
        max_length=50,
        choices=JobType.choices,
        help_text="Job type: DQ_RUN, COMPLIANCE_RUN, CONTRACT_VALIDATION, etc."
    )
    status = models.CharField(
        max_length=20,
        choices=JobStatus.choices,
        default=JobStatus.PENDING,
        help_text="Job status: PENDING, RUNNING, COMPLETED, FAILED, CANCELLED"
    )
    priority = models.CharField(
        max_length=20,
        choices=JobPriority.choices,
        default=JobPriority.NORMAL,
        help_text="Job priority: HIGH, NORMAL, LOW"
    )
    resource_type = models.CharField(
        max_length=50,
        help_text="Resource type: CONTRACT, DATASET, FILE, ASSET, etc."
    )
    resource_id = models.UUIDField(
        help_text="ID of the resource this job operates on"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_jobs",
        null=True,
        blank=True,
        help_text="User who created the job"
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When job started running"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When job completed (success or failure)"
    )
    error_message = models.TextField(
        null=True,
        blank=True,
        help_text="Error message if job failed"
    )
    result_json = models.JSONField(
        null=True,
        blank=True,
        default=dict,
        help_text="Job result data (partial results supported)"
    )
    details_json = models.JSONField(
        null=True,
        blank=True,
        default=dict,
        help_text="Job details (engine versions, progress, etc.)"
    )
    timeout_seconds = models.IntegerField(
        null=True,
        blank=True,
        help_text="Job timeout in seconds (configurable per job type)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "jobs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "type", "status"]),
            models.Index(fields=["resource_type", "resource_id"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["priority", "status"]),
            models.Index(fields=["tenant", "priority", "status"]),
        ]

    def __str__(self):
        return f"{self.type} - {self.status} ({self.resource_type}:{self.resource_id})"

    def is_terminal(self) -> bool:
        """Check if job is in a terminal state"""
        return self.status in [
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.CANCELLED
        ]

    def is_running(self) -> bool:
        """Check if job is currently running"""
        return self.status == JobStatus.RUNNING

    def can_cancel(self) -> bool:
        """Check if job can be cancelled"""
        return self.status in [JobStatus.PENDING, JobStatus.RUNNING]

    def mark_started(self):
        """Mark job as started"""
        self.status = JobStatus.RUNNING
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at', 'updated_at'])

        # Track metrics
        try:
            from hub.apps.observability.otel_metrics import jobs_started_total
            tenant_id = str(self.tenant.id) if self.tenant else 'system'
            jobs_started_total.labels(
                job_type=self.type,
                tenant_id=tenant_id
            ).inc()
        except Exception:
            pass  # Metrics may not be available

    def mark_completed(self, result_json=None):
        """Mark job as completed"""
        self.status = JobStatus.COMPLETED
        self.completed_at = timezone.now()
        if result_json is not None:
            self.result_json = result_json
        self.save(update_fields=['status', 'completed_at', 'result_json', 'updated_at'])

        # Track metrics
        try:
            from hub.apps.observability.otel_metrics import (
                jobs_completed_total,
                job_duration_seconds
            )
            tenant_id = str(self.tenant.id) if self.tenant else 'system'

            jobs_completed_total.labels(
                job_type=self.type,
                status='COMPLETED',
                tenant_id=tenant_id
            ).inc()

            # Track duration
            if self.started_at:
                duration = (self.completed_at - self.started_at).total_seconds()
                job_duration_seconds.labels(
                    job_type=self.type,
                    status='COMPLETED'
                ).observe(duration)
        except Exception:
            pass  # Metrics may not be available

    def mark_failed(self, error_message: str, result_json=None):
        """Mark job as failed"""
        self.status = JobStatus.FAILED
        self.completed_at = timezone.now()
        self.error_message = error_message
        if result_json is not None:
            self.result_json = result_json
        self.save(update_fields=['status', 'completed_at', 'error_message', 'result_json', 'updated_at'])

        # Track metrics
        try:
            from hub.apps.observability.otel_metrics import (
                jobs_failed_total,
                job_duration_seconds,
                job_retry_failures_total,
            )
            tenant_id = str(self.tenant.id) if self.tenant else 'system'

            # Extract error code from error message
            error_code = 'UNKNOWN_ERROR'
            error_type = 'UNKNOWN_ERROR'
            if 'timeout' in error_message.lower():
                error_code = 'TIMEOUT'
                error_type = 'TIMEOUT'
            elif 'validation' in error_message.lower():
                error_code = 'VALIDATION_ERROR'
                error_type = 'VALIDATION_ERROR'
            elif 'connection' in error_message.lower():
                error_type = 'CONNECTION_ERROR'
            elif 'permission' in error_message.lower():
                error_type = 'PERMISSION_ERROR'

            jobs_failed_total.labels(
                job_type=self.type,
                error_code=error_code,
                tenant_id=tenant_id
            ).inc()

            # Track retry failures (if job was retried)
            retry_count = 0
            if self.details_json:
                retry_count = self.details_json.get('retry_count', 0)
            if retry_count > 0:
                job_retry_failures_total.labels(
                    job_type=self.type,
                    error_type=error_type
                ).inc()

            # Track duration
            if self.started_at:
                duration = (self.completed_at - self.started_at).total_seconds()
                job_duration_seconds.labels(
                    job_type=self.type,
                    status='FAILED'
                ).observe(duration)
        except Exception:
            pass  # Metrics may not be available

    def mark_cancelled(self):
        """Mark job as cancelled"""
        self.status = JobStatus.CANCELLED
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at', 'updated_at'])


class SideEffectType(models.TextChoices):
    COST_TRACKING = "COST_TRACKING", "Cost Tracking"
    DLQ_SYNC = "DLQ_SYNC", "DLQ Sync"
    NOTIFICATION = "NOTIFICATION", "Notification"
    AUDIT_EVENT = "AUDIT_EVENT", "Audit Event"


class SideEffectStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"


class SideEffect(models.Model):
    """Outbox for side effects that must be applied after a run completes."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run_content_type = models.ForeignKey(
        "contenttypes.ContentType",
        on_delete=models.CASCADE,
        help_text="ContentType of the related run model",
    )
    run_object_id = models.UUIDField(help_text="Primary key of the related run instance")
    effect_type = models.CharField(
        max_length=20,
        choices=SideEffectType.choices,
        help_text="Side-effect type",
    )
    status = models.CharField(
        max_length=20,
        choices=SideEffectStatus.choices,
        default=SideEffectStatus.PENDING,
    )
    error_message = models.TextField(blank=True, null=True)
    attempt_count = models.PositiveIntegerField(default=0)
    context_json = models.JSONField(blank=True, null=True, default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "side_effects"
        ordering = ["-created_at"]

    def __str__(self):
        return f"SideEffect:{self.effect_type} ({self.status})"


class FailedJobDLQ(models.Model):
    """Dead-letter queue for jobs that failed after exhausting all retries."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job_id = models.UUIDField(db_index=True, help_text="Original Job UUID that failed")
    queue = models.CharField(max_length=100, help_text="RQ queue name the job was on")
    func_name = models.CharField(max_length=255, help_text="Fully-qualified function name")
    args_json = models.JSONField(default=dict, help_text="Serialised positional and keyword arguments")
    error_message = models.TextField(help_text="Final error message")
    traceback = models.TextField(blank=True, null=True, help_text="Full traceback at time of final failure")
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.SET_NULL,
        related_name="failed_job_dlq_entries",
        null=True,
        blank=True,
        help_text="Tenant the job belonged to",
    )
    retry_count = models.PositiveIntegerField(default=0, help_text="Number of times retried")
    resolved_at = models.DateTimeField(blank=True, null=True, help_text="When resolved")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "failed_job_dlq"
        ordering = ["-created_at"]

    def __str__(self):
        return f"DLQ:{self.job_id} ({self.func_name})"

