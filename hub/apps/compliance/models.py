"""
Compliance Models

Compliance Run model for tracking compliance checks.
"""
import uuid
from django.db import models
from django.core.exceptions import ValidationError


class ComplianceRunStatus(models.TextChoices):
    """Compliance Run status enumeration"""
    PENDING = "PENDING", "Pending"
    RUNNING = "RUNNING", "Running"
    SUCCEEDED = "SUCCEEDED", "Succeeded"
    FAILED = "FAILED", "Failed"


class RiskLevel(models.TextChoices):
    """Risk level enumeration"""
    NONE = "NONE", "None"
    LOW = "LOW", "Low"
    MEDIUM = "MEDIUM", "Medium"
    HIGH = "HIGH", "High"
    CRITICAL = "CRITICAL", "Critical"
    UNKNOWN = "UNKNOWN", "Unknown"  # Service unavailable/indeterminate (fail-closed)


class ComplianceRun(models.Model):
    """
    Compliance Run model representing a compliance check execution.
    
    Tracks compliance runs for assets, datasets, or files.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="compliance_runs",
        help_text="Tenant this compliance run belongs to"
    )
    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.CASCADE,
        related_name="compliance_runs",
        null=True,
        blank=True,
        help_text="Asset this compliance run is for (nullable)"
    )
    dataset = models.ForeignKey(
        "datasets.Dataset",
        on_delete=models.CASCADE,
        related_name="compliance_runs",
        null=True,
        blank=True,
        help_text="Dataset this compliance run is for (nullable)"
    )
    file = models.ForeignKey(
        "files.File",
        on_delete=models.CASCADE,
        related_name="compliance_runs",
        null=True,
        blank=True,
        help_text="File this compliance run is for (scan-only, nullable)"
    )
    job = models.ForeignKey(
        "jobs.Job",
        on_delete=models.CASCADE,
        related_name="compliance_runs",
        help_text="Job that orchestrates this compliance run"
    )
    regulations = models.JSONField(
        null=True,
        blank=True,
        help_text="List of applicable regulations (e.g., ['GDPR', 'LGPD'])"
    )
    status = models.CharField(
        max_length=20,
        choices=ComplianceRunStatus.choices,
        default=ComplianceRunStatus.PENDING,
        help_text="Compliance run status: PENDING, RUNNING, SUCCEEDED, FAILED"
    )
    overall_status = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Overall compliance status: PASS, WARN, FAIL (from result)"
    )
    risk_level = models.CharField(
        max_length=20,
        choices=RiskLevel.choices,
        null=True,
        blank=True,
        help_text="Risk level: NONE, LOW, MEDIUM, HIGH, CRITICAL"
    )
    allowed_to_store = models.BooleanField(
        null=True,
        blank=True,
        help_text="Whether data is allowed to be stored (NULL if check not completed)"
    )
    detected_categories_json = models.JSONField(
        null=True,
        blank=True,
        help_text="Summary of detected PII categories and counts"
    )
    column_findings_json = models.JSONField(
        null=True,
        blank=True,
        help_text="Per-column PII detection findings"
    )
    regulation_mapping_json = models.JSONField(
        null=True,
        blank=True,
        help_text="Regulatory mapping details (GDPR, LGPD, CCPA, HIPAA, SOX)"
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When compliance run started"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When compliance run completed"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "compliance_runs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "asset"]),
            models.Index(fields=["tenant", "dataset"]),
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "file"]),
            models.Index(fields=["job"]),
        ]
    
    def __str__(self):
        return f"Compliance Run {self.id}"
    
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

