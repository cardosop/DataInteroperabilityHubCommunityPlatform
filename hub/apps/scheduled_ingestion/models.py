"""
Scheduled Ingestion Models

Models for managing scheduled/recurring data ingestion from external sources.
"""
import uuid
import re
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from croniter import croniter


class SourceType(models.TextChoices):
    """Source type enumeration"""
    S3 = "S3", "Amazon S3"
    GCS = "GCS", "Google Cloud Storage"
    AZURE_BLOB = "AZURE_BLOB", "Azure Blob Storage"
    HTTP = "HTTP", "HTTP"
    HTTPS = "HTTPS", "HTTPS"
    FTP = "FTP", "FTP"
    SFTP = "SFTP", "SFTP"
    DATABASE = "DATABASE", "Database"


class ScheduleType(models.TextChoices):
    """Schedule type enumeration"""
    DAILY = "DAILY", "Daily"
    WEEKLY = "WEEKLY", "Weekly"
    MONTHLY = "MONTHLY", "Monthly"
    CUSTOM_CRON = "CUSTOM_CRON", "Custom Cron"


class ScheduledIngestionStatus(models.TextChoices):
    """Scheduled ingestion status enumeration"""
    ACTIVE = "ACTIVE", "Active"
    PAUSED = "PAUSED", "Paused"
    ERROR = "ERROR", "Error"


class ScheduledIngestionRunStatus(models.TextChoices):
    """Scheduled ingestion run status enumeration"""
    PENDING = "PENDING", "Pending"
    RUNNING = "RUNNING", "Running"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"
    CANCELLED = "CANCELLED", "Cancelled"


class ScheduledIngestion(models.Model):
    """
    Scheduled ingestion model for recurring data ingestion from external sources.
    
    Orchestrated using Prefect workflows that create SCHEDULED_INGESTION jobs
    in django-rq queues for processing by the worker service.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="scheduled_ingestions",
        help_text="Tenant this scheduled ingestion belongs to"
    )
    name = models.CharField(
        max_length=255,
        help_text="Scheduled ingestion name (unique per tenant)"
    )
    description = models.TextField(
        null=True,
        blank=True,
        help_text="Optional description"
    )
    source_type = models.CharField(
        max_length=50,
        choices=SourceType.choices,
        help_text="Source type: S3, GCS, AZURE_BLOB, HTTP, FTP, SFTP, DATABASE"
    )
    source_config = models.JSONField(
        blank=True,
        default=dict,
        help_text="Source configuration (connection details, credentials, paths) stored securely"
    )
    schedule_type = models.CharField(
        max_length=20,
        choices=ScheduleType.choices,
        default=ScheduleType.DAILY,
        help_text="Schedule type: DAILY, WEEKLY, MONTHLY, CUSTOM_CRON"
    )
    schedule_config = models.JSONField(
        help_text="Schedule configuration (cron expression, timezone, days of week)"
    )
    file_pattern = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="File pattern (regex for matching files). Omit or leave blank to match all files (.*)."
    )
    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.SET_NULL,
        related_name="scheduled_ingestions",
        null=True,
        blank=True,
        help_text="Asset to associate ingested data with (optional)"
    )
    contract = models.ForeignKey(
        "contracts.Contract",
        on_delete=models.SET_NULL,
        related_name="scheduled_ingestions",
        null=True,
        blank=True,
        help_text="Contract to use for ingested data (optional - can create new contract per ingestion)"
    )
    auto_create_asset = models.BooleanField(
        default=False,
        help_text="Create asset if it doesn't exist"
    )
    auto_activate = models.BooleanField(
        default=False,
        help_text="Auto-activate asset after ingestion"
    )
    status = models.CharField(
        max_length=20,
        choices=ScheduledIngestionStatus.choices,
        default=ScheduledIngestionStatus.ACTIVE,
        help_text="Status: ACTIVE, PAUSED, ERROR"
    )
    next_run_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Next scheduled run time (calculated based on schedule)"
    )
    prefect_deployment_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Prefect deployment ID (format: {tenant_id}-{scheduled_ingestion_id})"
    )
    prefect_work_pool_name = models.CharField(
        max_length=255,
        default="default",
        help_text="Prefect work pool name"
    )
    last_processed_file = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        help_text="Last processed file path/key (for incremental ingestion)"
    )
    last_processed_timestamp = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last processed file timestamp (for incremental ingestion)"
    )
    ingestion_state = models.JSONField(
        null=True,
        blank=True,
        default=dict,
        help_text="Ingestion state (processed files list, incremental state, etc.)"
    )
    error_message = models.TextField(
        null=True,
        blank=True,
        help_text="Error message if status is ERROR"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_scheduled_ingestions",
        null=True,
        blank=True,
        help_text="User who created the scheduled ingestion"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "scheduled_ingestions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "name"]),
            models.Index(fields=["tenant", "source_type"]),
            models.Index(fields=["next_run_at"]),
            models.Index(fields=["status", "next_run_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name"],
                name="unique_scheduled_ingestion_name_per_tenant"
            )
        ]
    
    def __str__(self):
        return f"{self.name} ({self.tenant.name})"
    
    def clean(self):
        """Validate scheduled ingestion"""
        # Validate file pattern is a valid regex when set (None means match-all in processor)
        if self.file_pattern:
            try:
                re.compile(self.file_pattern)
            except re.error as e:
                raise ValidationError(f"Invalid file pattern regex: {str(e)}")
        
        # Validate cron expression if schedule_type is CUSTOM_CRON
        if self.schedule_type == ScheduleType.CUSTOM_CRON:
            cron_expr = self.schedule_config.get("cron")
            if not cron_expr:
                raise ValidationError("Cron expression is required for CUSTOM_CRON schedule type")
            
            try:
                croniter(cron_expr)
            except Exception as e:
                raise ValidationError(f"Invalid cron expression: {str(e)}")
    
    def save(self, *args, **kwargs):
        """Override save to validate and calculate next_run_at"""
        self.full_clean()
        
        # Calculate next_run_at if not set or if schedule changed
        if not self.next_run_at or self._state.adding:
            self.next_run_at = self._calculate_next_run_at()
        
        super().save(*args, **kwargs)
    
    def _calculate_next_run_at(self):
        """Calculate next run time based on schedule"""
        from datetime import datetime, timedelta
        
        now = timezone.now()
        
        if self.schedule_type == ScheduleType.DAILY:
            # Daily at time specified in schedule_config (default: midnight)
            time_str = self.schedule_config.get("time", "00:00")
            hour, minute = map(int, time_str.split(":"))
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            return next_run
        
        elif self.schedule_type == ScheduleType.WEEKLY:
            # Weekly on specified day(s) of week
            days_of_week = self.schedule_config.get("days_of_week", [0])  # Default: Monday
            time_str = self.schedule_config.get("time", "00:00")
            hour, minute = map(int, time_str.split(":"))
            
            # Find next matching day
            for i in range(7):
                candidate = now + timedelta(days=i)
                if candidate.weekday() in days_of_week:
                    next_run = candidate.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if next_run > now:
                        return next_run
            
            # If no match found in next 7 days, use first day of next week
            next_run = now + timedelta(days=7)
            return next_run.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        elif self.schedule_type == ScheduleType.MONTHLY:
            # Monthly on specified day of month
            day_of_month = self.schedule_config.get("day_of_month", 1)
            time_str = self.schedule_config.get("time", "00:00")
            hour, minute = map(int, time_str.split(":"))
            
            # Find next matching day
            next_run = now.replace(day=day_of_month, hour=hour, minute=minute, second=0, microsecond=0)
            if next_run <= now:
                # Move to next month
                if next_run.month == 12:
                    next_run = next_run.replace(year=next_run.year + 1, month=1)
                else:
                    next_run = next_run.replace(month=next_run.month + 1)
            return next_run
        
        elif self.schedule_type == ScheduleType.CUSTOM_CRON:
            # Use cron expression
            cron_expr = self.schedule_config.get("cron")
            timezone_str = self.schedule_config.get("timezone", "UTC")
            
            try:
                from croniter import croniter
                from pytz import timezone as pytz_timezone
                
                tz = pytz_timezone(timezone_str)
                cron = croniter(cron_expr, now.astimezone(tz))
                next_run = cron.get_next(datetime)
                return timezone.make_aware(next_run)
            except Exception:
                # Fallback to tomorrow if cron parsing fails
                return now + timedelta(days=1)
        
        # Default: tomorrow at midnight
        return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)


class ScheduledIngestionRun(models.Model):
    """
    Scheduled ingestion run model for tracking individual ingestion executions.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scheduled_ingestion = models.ForeignKey(
        ScheduledIngestion,
        on_delete=models.CASCADE,
        related_name="runs",
        help_text="Scheduled ingestion this run belongs to"
    )
    status = models.CharField(
        max_length=20,
        choices=ScheduledIngestionRunStatus.choices,
        default=ScheduledIngestionRunStatus.PENDING,
        help_text="Run status: PENDING, RUNNING, COMPLETED, FAILED, CANCELLED"
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When run started"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When run completed (success or failure)"
    )
    prefect_flow_run_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Prefect flow run ID"
    )
    job_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="Job ID (FK to jobs table)"
    )
    files_found = models.IntegerField(
        default=0,
        help_text="Number of files found"
    )
    files_processed = models.IntegerField(
        default=0,
        help_text="Number of files successfully processed"
    )
    files_failed = models.IntegerField(
        default=0,
        help_text="Number of files that failed to process"
    )
    datasets_created = models.IntegerField(
        default=0,
        help_text="Number of datasets created"
    )
    error_message = models.TextField(
        null=True,
        blank=True,
        help_text="Error message if run failed"
    )
    result_json = models.JSONField(
        null=True,
        blank=True,
        default=dict,
        help_text="Run result data (files processed, datasets created, etc.)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "scheduled_ingestion_runs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["scheduled_ingestion", "status"]),
            models.Index(fields=["scheduled_ingestion", "created_at"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["prefect_flow_run_id"]),
            models.Index(fields=["job_id"]),
        ]
    
    def __str__(self):
        return f"Run {self.id} for {self.scheduled_ingestion.name}"


class DeadLetterQueueItem(models.Model):
    """
    Dead Letter Queue item for permanently failed files.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scheduled_ingestion = models.ForeignKey(
        ScheduledIngestion,
        on_delete=models.CASCADE,
        related_name="dlq_items",
        help_text="Scheduled ingestion this DLQ item belongs to"
    )
    file_path = models.CharField(
        max_length=500,
        help_text="File path/key that failed"
    )
    error_message = models.TextField(
        help_text="Error message from last failure"
    )
    error_code = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Error code for categorization"
    )
    retry_count = models.IntegerField(
        default=0,
        help_text="Number of retry attempts"
    )
    first_failed_at = models.DateTimeField(
        help_text="When file first failed"
    )
    last_failed_at = models.DateTimeField(
        help_text="When file last failed"
    )
    permanently_failed_at = models.DateTimeField(
        help_text="When file was marked as permanently failed"
    )
    resolution_status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending'),
            ('RETRYING', 'Retrying'),
            ('RESOLVED', 'Resolved'),
            ('IGNORED', 'Ignored')
        ],
        default='PENDING',
        help_text="Resolution status"
    )
    resolution_notes = models.TextField(
        null=True,
        blank=True,
        help_text="Notes about resolution"
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_dlq_items",
        help_text="User who resolved this item"
    )
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When item was resolved"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "scheduled_ingestion_dlq"
        ordering = ["-permanently_failed_at"]
        indexes = [
            models.Index(fields=["scheduled_ingestion", "resolution_status"]),
            models.Index(fields=["scheduled_ingestion", "permanently_failed_at"]),
            models.Index(fields=["resolution_status", "permanently_failed_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["scheduled_ingestion", "file_path"],
                name="unique_dlq_item_per_file"
            )
        ]
    
    def __str__(self):
        return f"DLQ Item: {self.file_path} ({self.scheduled_ingestion.name})"


class IngestionCost(models.Model):
    """
    Cost tracking for scheduled ingestion runs.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scheduled_ingestion = models.ForeignKey(
        ScheduledIngestion,
        on_delete=models.CASCADE,
        related_name="costs",
        help_text="Scheduled ingestion this cost belongs to"
    )
    run = models.ForeignKey(
        ScheduledIngestionRun,
        on_delete=models.CASCADE,
        related_name="costs",
        null=True,
        blank=True,
        help_text="Associated ingestion run (if applicable)"
    )
    storage_cost_usd = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=0.0,
        help_text="Storage cost in USD"
    )
    compute_cost_usd = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=0.0,
        help_text="Compute cost in USD"
    )
    network_cost_usd = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=0.0,
        help_text="Network/transfer cost in USD"
    )
    total_cost_usd = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=0.0,
        help_text="Total cost in USD"
    )
    cost_breakdown_json = models.JSONField(
        null=True,
        blank=True,
        default=dict,
        help_text="Detailed cost breakdown"
    )
    period_start = models.DateTimeField(
        help_text="Start of cost period"
    )
    period_end = models.DateTimeField(
        help_text="End of cost period"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "scheduled_ingestion_costs"
        ordering = ["-period_start"]
        indexes = [
            models.Index(fields=["scheduled_ingestion", "period_start"]),
            models.Index(fields=["scheduled_ingestion", "period_end"]),
            models.Index(fields=["run"]),
        ]
    
    def __str__(self):
        return f"Cost: ${self.total_cost_usd} for {self.scheduled_ingestion.name}"
    
    def save(self, *args, **kwargs):
        """Override save to calculate total cost"""
        self.total_cost_usd = (
            self.storage_cost_usd +
            self.compute_cost_usd +
            self.network_cost_usd
        )
        super().save(*args, **kwargs)

