"""
Scheduled Export Models

Models for managing scheduled/recurring data exports to external destinations.
"""

import re
import uuid

from croniter import croniter
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from hub.apps.integrations.encryption import (
    decrypt_json_field,
    encrypt_json_field,
    EncryptionError,
)


class DestinationType(models.TextChoices):
    """Destination type enumeration"""

    S3 = "S3", "Amazon S3"
    GCS = "GCS", "Google Cloud Storage"
    AZURE_BLOB = "AZURE_BLOB", "Azure Blob Storage"
    # Phase 275.D.2 — warehouse destinations via dlt.
    SNOWFLAKE_TABLE = "SNOWFLAKE_TABLE", "Snowflake Table"
    BIGQUERY_TABLE = "BIGQUERY_TABLE", "BigQuery Table"
    DATABRICKS_TABLE = "DATABRICKS_TABLE", "Databricks Table"
    ATHENA_TABLE = "ATHENA_TABLE", "Athena Table"


class ScheduledExportStatus(models.TextChoices):
    """Scheduled export status enumeration"""

    ACTIVE = "ACTIVE", "Active"
    PAUSED = "PAUSED", "Paused"
    ERROR = "ERROR", "Error"
    DELETED = "DELETED", "Deleted"


class DeploymentSyncStatus(models.TextChoices):
    """Phase 25.4.4 — Prefect deployment sync status"""

    SYNCED = "SYNCED", "Synced"
    PENDING = "PENDING", "Pending"
    FAILED = "FAILED", "Failed"


class ScheduledExportRunStatus(models.TextChoices):
    """Scheduled export run status enumeration"""

    RUNNING = "RUNNING", "Running"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"
    CANCELLED = "CANCELLED", "Cancelled"


class ScheduledExport(models.Model):
    """
    Scheduled export model for recurring data exports to external destinations.

    Orchestrated using Prefect workflows that create SCHEDULED_EXPORT jobs
    in django-rq queues for processing by the worker service.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="scheduled_exports",
        help_text="Tenant this scheduled export belongs to",
    )
    name = models.CharField(max_length=255, help_text="Scheduled export name (unique per tenant)")
    schedule_config = models.JSONField(
        help_text="Schedule configuration (cron expression, timezone)"
    )
    destination_type = models.CharField(
        max_length=50,
        choices=DestinationType.choices,
        help_text="Destination type: S3, GCS, AZURE_BLOB",
    )
    destination_config = models.JSONField(
        help_text="Destination configuration (connection details, credentials, paths) stored securely. Credentials are masked in API and logs."
    )
    source_scope = models.JSONField(
        help_text="Source scope: asset_ids, dataset_ids, file_ids, or contract_id"
    )
    status = models.CharField(
        max_length=20,
        choices=ScheduledExportStatus.choices,
        default=ScheduledExportStatus.ACTIVE,
        help_text="Status: ACTIVE, PAUSED, ERROR",
    )
    next_run_at = models.DateTimeField(
        null=True, blank=True, help_text="Next scheduled run time (calculated based on schedule)"
    )
    last_run_at = models.DateTimeField(null=True, blank=True, help_text="Last run time")
    last_run_status = models.CharField(
        max_length=20,
        choices=ScheduledExportRunStatus.choices,
        null=True,
        blank=True,
        help_text="Status of last run: RUNNING, COMPLETED, FAILED, CANCELLED",
    )
    # Phase 25.4.1 — Persist Prefect deployment ID
    prefect_deployment_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Prefect deployment ID returned by integration service",
    )
    # Phase 25.4.4 — Deployment sync status
    deployment_sync_status = models.CharField(
        max_length=10,
        choices=DeploymentSyncStatus.choices,
        default=DeploymentSyncStatus.PENDING,
        help_text="Prefect deployment sync status: SYNCED, PENDING, FAILED",
    )
    consecutive_failure_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of consecutive failed runs (Phase 71 — auto-pause)",
    )
    last_error_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of the last failure (Phase 71)",
    )
    credential_ref = models.CharField(
        max_length=1024,
        null=True,
        blank=True,
        help_text=(
            "AWS SM ARN (arn:aws:secretsmanager:...) or "
            "prefect://block-slug for dlt credential resolution"
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "scheduled_exports"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "name"]),
            models.Index(fields=["tenant", "destination_type"]),
            models.Index(fields=["next_run_at"]),
            models.Index(fields=["status", "next_run_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name"], name="unique_scheduled_export_name_per_tenant"
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.tenant.name})"

    def clean(self):
        """Validate scheduled export"""
        # Validate cron expression in schedule_config
        cron_expr = self.schedule_config.get("cron")
        if not cron_expr:
            raise ValidationError("Cron expression is required in schedule_config")

        try:
            croniter(cron_expr)
        except Exception as e:
            raise ValidationError(f"Invalid cron expression: {str(e)}")

        # Validate source_scope structure
        if not isinstance(self.source_scope, dict):
            raise ValidationError("source_scope must be a dictionary")

        # Validate that at least one scope field is provided
        valid_scope_fields = ["asset_ids", "dataset_ids", "file_ids", "contract_id"]
        has_scope = any(
            field in self.source_scope and self.source_scope[field] for field in valid_scope_fields
        )
        if not has_scope:
            raise ValidationError(
                "source_scope must contain at least one of: asset_ids, dataset_ids, file_ids, contract_id"
            )

        # Validate destination_config structure
        if not isinstance(self.destination_config, dict):
            raise ValidationError("destination_config must be a dictionary")

    def save(self, *args, **kwargs):
        """Override save to validate, encrypt destination_config, and calculate next_run_at"""
        self.full_clean()

        # Encrypt destination_config if plaintext dict (not already encrypted)
        if (
            isinstance(self.destination_config, dict)
            and self.destination_config
            and not self.destination_config.get("_encrypted")
        ):
            try:
                encrypted = encrypt_json_field(self.destination_config)
                self.destination_config = {"_encrypted": encrypted}
            except EncryptionError as e:
                raise ValidationError(
                    {"destination_config": f"Failed to encrypt: {e}"}
                ) from e

        # Calculate next_run_at if not set or if schedule changed
        if not self.next_run_at or self._state.adding:
            self.next_run_at = self._calculate_next_run_at()

        super().save(*args, **kwargs)

    def get_destination_config(self) -> dict:
        """
        Get decrypted destination configuration.

        Returns:
            Decrypted destination config dictionary.
            Legacy plaintext dicts (pre-migration) returned as-is.
        """
        if not self.destination_config:
            return {}
        if isinstance(self.destination_config, dict):
            if "_encrypted" in self.destination_config:
                return decrypt_json_field(
                    self.destination_config["_encrypted"]
                )
            return self.destination_config
        return {}

    def _calculate_next_run_at(self):
        """Calculate next run time based on cron schedule."""
        from datetime import datetime, timedelta

        now = timezone.now()
        cron_expr = self.schedule_config.get("cron")
        timezone_str = self.schedule_config.get("timezone", "UTC")

        if not cron_expr:
            return (now + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0,
            )

        try:
            from pytz import timezone as pytz_timezone

            tz = pytz_timezone(timezone_str)
            cron = croniter(cron_expr, now.astimezone(tz))
            next_run = cron.get_next(datetime)
            # croniter returns aware datetime when seeded with aware;
            # ensure it's aware (UTC) for storage.
            if timezone.is_naive(next_run):
                next_run = timezone.make_aware(next_run, tz)
            return next_run
        except Exception:
            from datetime import timedelta

            return (now + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0,
            )


class ScheduledExportRun(models.Model):
    """
    Scheduled export run model for tracking individual export executions.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scheduled_export = models.ForeignKey(
        ScheduledExport,
        on_delete=models.CASCADE,
        related_name="runs",
        help_text="Scheduled export this run belongs to",
    )
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="scheduled_export_runs",
        help_text="Tenant this export run belongs to",
    )
    status = models.CharField(
        max_length=20,
        choices=ScheduledExportRunStatus.choices,
        default=ScheduledExportRunStatus.RUNNING,
        help_text="Run status: RUNNING, COMPLETED, FAILED, CANCELLED",
    )
    items_found = models.IntegerField(default=0, help_text="Number of items found for export")
    items_exported = models.IntegerField(
        default=0, help_text="Number of items successfully exported"
    )
    items_failed = models.IntegerField(default=0, help_text="Number of items that failed to export")
    result_json = models.JSONField(
        null=True,
        blank=True,
        default=dict,
        help_text="Run result data (items exported, errors, etc.)",
    )
    started_at = models.DateTimeField(null=True, blank=True, help_text="When run started")
    completed_at = models.DateTimeField(
        null=True, blank=True, help_text="When run completed (success or failure)"
    )
    prefect_flow_run_id = models.CharField(
        max_length=255, null=True, blank=True, help_text="Prefect flow run ID"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "scheduled_export_runs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["scheduled_export", "status"]),
            models.Index(fields=["scheduled_export", "created_at"]),
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "created_at"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["prefect_flow_run_id"]),
        ]

    def __str__(self):
        return f"Run {self.id} for {self.scheduled_export.name}"


class ExportRunCost(models.Model):
    """
    Cost tracking for scheduled export runs.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(
        ScheduledExportRun,
        on_delete=models.CASCADE,
        related_name="costs",
        help_text="Export run this cost belongs to",
    )
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="export_run_costs",
        help_text="Tenant this cost belongs to",
    )
    cost_components = models.JSONField(
        default=dict, help_text="Cost components breakdown (storage, compute, network, etc.)"
    )
    calculated_at = models.DateTimeField(auto_now_add=True, help_text="When cost was calculated")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "export_run_costs"
        ordering = ["-calculated_at"]
        indexes = [
            models.Index(fields=["run"]),
            models.Index(fields=["tenant", "calculated_at"]),
            models.Index(fields=["calculated_at"]),
        ]

    def __str__(self):
        return f"Cost for Run {self.run.id}"
