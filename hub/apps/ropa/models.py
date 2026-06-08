from __future__ import annotations
import uuid

from django.conf import settings
from django.db import models


class RopaOutputFormat(models.TextChoices):
    JSON = "json", "JSON"
    CSV = "csv", "CSV"
    PDF = "pdf", "PDF"
    DOCX = "docx", "DOCX"


class RopaGenerationStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    PROCESSING = "PROCESSING", "Processing"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"


class RopaGeneration(models.Model):
    """One generated RoPA artefact for a tenant."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="ropa_generations",
        db_index=True,
    )
    regulation = models.CharField(
        max_length=32,
        help_text="Uppercase regulation key (GDPR, LGPD, ...)",
    )
    output_format = models.CharField(
        max_length=16,
        choices=RopaOutputFormat.choices,
    )
    status = models.CharField(
        max_length=20,
        choices=RopaGenerationStatus.choices,
        default=RopaGenerationStatus.PENDING,
        db_index=True,
    )
    object_key = models.CharField(max_length=1024, blank=True, default="")
    content_sha256 = models.CharField(max_length=64, blank=True, default="")
    byte_size = models.PositiveBigIntegerField(default=0)
    cache_generation = models.PositiveIntegerField(
        default=0,
        help_text="Invalidation generation counter snapshot at build time.",
    )
    gaps_json = models.JSONField(default=list, blank=True)
    summary_json = models.JSONField(default=dict, blank=True)
    job = models.ForeignKey(
        "jobs.Job",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ropa_generations",
    )
    error_message = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ropa_generations_created",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "ropa_generations"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "created_at"]),
        ]
