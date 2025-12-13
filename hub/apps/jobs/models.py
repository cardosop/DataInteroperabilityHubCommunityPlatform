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


class JobStatus(models.TextChoices):
    """Job status enumeration"""
    PENDING = "PENDING", "Pending"
    RUNNING = "RUNNING", "Running"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"
    CANCELLED = "CANCELLED", "Cancelled"


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
                job_duration_seconds
            )
            tenant_id = str(self.tenant.id) if self.tenant else 'system'
            
            # Extract error code from error message
            error_code = 'UNKNOWN_ERROR'
            if 'timeout' in error_message.lower():
                error_code = 'TIMEOUT'
            elif 'validation' in error_message.lower():
                error_code = 'VALIDATION_ERROR'
            
            jobs_failed_total.labels(
                job_type=self.type,
                error_code=error_code,
                tenant_id=tenant_id
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

