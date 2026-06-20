"""
GDPR Models

Models for data portability and erasure requests.
"""

import uuid

from django.conf import settings
from django.db import models


class DataExportStatus(models.TextChoices):
    """Data export job status"""

    PENDING = "PENDING", "Pending"
    PROCESSING = "PROCESSING", "Processing"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"


class DataExportJob(models.Model):
    """
    Data export job for data portability (GDPR Article 20).

    Creates an archive of user's data for download.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="data_export_jobs",
        help_text="User requesting data export",
    )
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="data_export_jobs",
        help_text="Tenant this export belongs to",
    )
    status = models.CharField(
        max_length=20,
        choices=DataExportStatus.choices,
        default=DataExportStatus.PENDING,
        help_text="Export job status",
    )
    storage_path = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        help_text="Path in storage (S3/MinIO) for export archive",
    )
    download_url = models.URLField(
        max_length=4096,
        null=True,
        blank=True,
        help_text="Signed URL for downloading export (short-lived); presigned URLs can exceed 2KB",
    )
    download_url_expires_at = models.DateTimeField(
        null=True, blank=True, help_text="When download URL expires"
    )
    error_message = models.TextField(
        null=True, blank=True, help_text="Error message if status is FAILED"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(
        null=True, blank=True, help_text="When export was completed"
    )

    class Meta:
        db_table = "data_export_jobs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self):
        return f"Data export {self.id} for {self.user.email} ({self.status})"


class ErasureRequestStatus(models.TextChoices):
    """Erasure request status"""

    PENDING = "PENDING", "Pending"
    PROCESSING = "PROCESSING", "Processing"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"


class ErasureRequest(models.Model):
    """
    Erasure request for right to be forgotten (GDPR Article 17).

    Tracks user data erasure/anonymization requests.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="erasure_requests",
        help_text="User requesting erasure",
    )
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="erasure_requests",
        help_text="Tenant this erasure belongs to",
    )
    status = models.CharField(
        max_length=20,
        choices=ErasureRequestStatus.choices,
        default=ErasureRequestStatus.PENDING,
        help_text="Erasure request status",
    )
    requested_at = models.DateTimeField(auto_now_add=True, help_text="When erasure was requested")
    completed_at = models.DateTimeField(
        null=True, blank=True, help_text="When erasure was completed"
    )
    error_message = models.TextField(
        null=True, blank=True, help_text="Error message if status is FAILED"
    )
    anonymized_fields = models.JSONField(
        default=list, help_text="List of fields that were anonymized (not deleted)"
    )
    deleted_resources = models.JSONField(
        default=list, help_text="List of resource types that were deleted"
    )
    retention_exceptions = models.JSONField(
        default=list, help_text="List of resources retained due to legal/compliance requirements"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "erasure_requests"
        ordering = ["-requested_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["status", "requested_at"]),
        ]

    def __str__(self):
        return f"Erasure request {self.id} for {self.user.email} ({self.status})"
