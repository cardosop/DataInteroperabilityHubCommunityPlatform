"""
DQ Models

Data Quality Run model for tracking DQ executions.
"""
import uuid
from django.db import models
from django.core.exceptions import ValidationError


class DQRunStatus(models.TextChoices):
    """DQ Run status enumeration"""
    PENDING = "PENDING", "Pending"
    RUNNING = "RUNNING", "Running"
    SUCCEEDED = "SUCCEEDED", "Succeeded"
    FAILED = "FAILED", "Failed"


class DQEngine(models.TextChoices):
    """DQ Engine enumeration"""
    GREAT_EXPECTATIONS = "GREAT_EXPECTATIONS", "Great Expectations"
    SODA = "SODA", "Soda"


class DQRun(models.Model):
    """
    DQ Run model representing a data quality check execution.
    
    Tracks DQ runs for assets, datasets, or files.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="dq_runs",
        help_text="Tenant this DQ run belongs to"
    )
    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.CASCADE,
        related_name="dq_runs",
        null=True,
        blank=True,
        help_text="Asset this DQ run is for (nullable)"
    )
    dataset = models.ForeignKey(
        "datasets.Dataset",
        on_delete=models.CASCADE,
        related_name="dq_runs",
        null=True,
        blank=True,
        help_text="Dataset this DQ run is for (nullable)"
    )
    file = models.ForeignKey(
        "files.File",
        on_delete=models.CASCADE,
        related_name="dq_runs",
        null=True,
        blank=True,
        help_text="File this DQ run is for (scan-only, nullable)"
    )
    job = models.ForeignKey(
        "jobs.Job",
        on_delete=models.CASCADE,
        related_name="dq_runs",
        help_text="Job that orchestrates this DQ run"
    )
    profile_key = models.CharField(
        max_length=100,
        help_text="DQ profile key (e.g., intake_basic_gx, intake_basic_soda)"
    )
    engine = models.CharField(
        max_length=50,
        choices=DQEngine.choices,
        help_text="DQ engine used: GREAT_EXPECTATIONS or SODA"
    )
    status = models.CharField(
        max_length=20,
        choices=DQRunStatus.choices,
        default=DQRunStatus.PENDING,
        help_text="DQ run status: PENDING, RUNNING, SUCCEEDED, FAILED"
    )
    overall_status = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Overall DQ status: PASS, FAIL, WARN, UNKNOWN (from result)"
    )
    quality_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Quality score (0-100)"
    )
    checks_json = models.JSONField(
        null=True,
        blank=True,
        help_text="List of DQ checks with results"
    )
    details_json = models.JSONField(
        null=True,
        blank=True,
        help_text="Detailed DQ results and metadata"
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When DQ run started"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When DQ run completed"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "dq_runs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "asset"]),
            models.Index(fields=["tenant", "dataset"]),
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "file"]),
            models.Index(fields=["job"]),
        ]
    
    def __str__(self):
        return f"DQ Run {self.id} ({self.profile_key})"
    
    def clean(self):
        """Validate that at least one of asset_id, dataset_id, or file_id is set"""
        super().clean()
        
        if not self.asset and not self.dataset and not self.file:
            raise ValidationError(
                "At least one of asset, dataset, or file must be set"
            )
    
    def save(self, *args, **kwargs):
        """Override save to validate before saving"""
        self.full_clean()
        super().save(*args, **kwargs)

