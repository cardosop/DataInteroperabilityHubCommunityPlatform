"""
Marketplace Connection Models

Models for managing marketplace connections, sync jobs, and mappings.
"""
import uuid
import json
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.conf import settings

from hub.apps.integrations.base import MarketplaceType, SyncDirection, SyncStatus
from hub.apps.integrations.encryption import encrypt_json_field, decrypt_json_field, EncryptionError


class MarketplaceConnection(models.Model):
    """
    Marketplace connection configuration model.

    Stores connection credentials and configuration for external marketplace
    integrations. The config field is encrypted at rest for security.

    Each tenant can have multiple marketplace connections, but connection
    names must be unique within a tenant.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the marketplace connection"
    )
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="marketplace_connections",
        help_text="Tenant this connection belongs to"
    )
    marketplace_type = models.CharField(
        max_length=50,
        choices=[(mt.value, mt.name.replace("_", " ").title()) for mt in MarketplaceType],
        help_text="Type of marketplace (e.g., SNOWFLAKE_DATA_MARKETPLACE, AWS_DATA_EXCHANGE)"
    )
    name = models.CharField(
        max_length=255,
        help_text="Human-readable name for this connection (unique per tenant)"
    )
    config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Encrypted connection configuration (API keys, endpoints, etc.)"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this connection is active and can be used"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "marketplace_connections"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "marketplace_type"]),
            models.Index(fields=["tenant", "is_active"]),
            models.Index(fields=["marketplace_type", "is_active"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name"],
                name="unique_tenant_connection_name"
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.get_marketplace_type_display()}) - {self.tenant.name}"

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self.name} ({self.id})>"

    def clean(self):
        """
        Validate model fields before saving.

        Raises:
            ValidationError: If validation fails
        """
        super().clean()

        # Validate marketplace_type is a valid enum value
        valid_types = [mt.value for mt in MarketplaceType]
        if self.marketplace_type not in valid_types:
            raise ValidationError({
                'marketplace_type': f"Invalid marketplace type. Must be one of: {', '.join(valid_types)}"
            })

        # Validate name is not empty
        if not self.name or not self.name.strip():
            raise ValidationError({
                'name': "Connection name cannot be empty"
            })

        # Validate config is a dictionary (allow empty dict)
        if not isinstance(self.config, dict):
            raise ValidationError({
                'config': "Configuration must be a dictionary"
            })

    def save(self, *args, **kwargs):
        """
        Save the model instance, encrypting the config field before storage.

        The config field is encrypted using Fernet encryption before being
        stored in the database. On retrieval, it's automatically decrypted.
        """
        # Run validation
        self.full_clean()

        # Encrypt config if it's a dictionary and not already encrypted
        # Allow empty dicts (they won't be encrypted but will be stored as {})
        if isinstance(self.config, dict) and self.config and not self.config.get("_encrypted"):
            try:
                # Check if config is already encrypted (starts with base64 pattern)
                # If it's a plain dict, encrypt it
                encrypted_config = encrypt_json_field(self.config)
                # Store encrypted data in a special format
                # We'll store it as {"_encrypted": "<encrypted_string>"}
                # to distinguish from plain JSON
                self.config = {"_encrypted": encrypted_config}
            except EncryptionError as e:
                raise ValidationError({
                    'config': f"Failed to encrypt configuration: {str(e)}"
                }) from e

        super().save(*args, **kwargs)

    def get_config(self) -> dict:
        """
        Get decrypted configuration.

        Returns:
            Decrypted configuration dictionary

        Raises:
            EncryptionError: If decryption fails
        """
        if not self.config:
            return {}

        # Check if config is encrypted
        if isinstance(self.config, dict) and "_encrypted" in self.config:
            try:
                encrypted_str = self.config["_encrypted"]
                return decrypt_json_field(encrypted_str)
            except EncryptionError as e:
                raise EncryptionError(f"Failed to decrypt configuration for connection {self.id}: {str(e)}") from e

        # If not encrypted (legacy data or plain dict), return as-is
        return self.config if isinstance(self.config, dict) else {}

    def set_config(self, config: dict):
        """
        Set configuration (will be encrypted on save).

        Args:
            config: Configuration dictionary to set
        """
        if not isinstance(config, dict):
            raise ValueError("Configuration must be a dictionary")
        self.config = config


class MarketplaceSyncJob(models.Model):
    """
    Marketplace synchronization job model.

    Tracks synchronization operations between the Hub and external marketplaces.
    Records progress, errors, and metadata for each sync operation.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the sync job"
    )
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="marketplace_sync_jobs",
        help_text="Tenant this sync job belongs to"
    )
    connection = models.ForeignKey(
        MarketplaceConnection,
        on_delete=models.CASCADE,
        related_name="sync_jobs",
        help_text="Marketplace connection used for this sync"
    )
    direction = models.CharField(
        max_length=20,
        choices=[(sd.value, sd.name.replace("_", " ").title()) for sd in SyncDirection],
        help_text="Sync direction: PUSH, PULL, or BIDIRECTIONAL"
    )
    status = models.CharField(
        max_length=20,
        choices=[(ss.value, ss.name.replace("_", " ").title()) for ss in SyncStatus],
        default=SyncStatus.PENDING.value,
        help_text="Sync job status: PENDING, RUNNING, COMPLETED, FAILED, PARTIAL"
    )
    items_synced = models.IntegerField(
        default=0,
        help_text="Number of items successfully synced"
    )
    items_failed = models.IntegerField(
        default=0,
        help_text="Number of items that failed to sync"
    )
    errors = models.JSONField(
        default=list,
        blank=True,
        help_text="List of error messages encountered during sync"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata about the sync operation"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the sync job completed (success or failure)"
    )

    class Meta:
        db_table = "marketplace_sync_jobs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "connection"]),
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["connection", "status"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self):
        return f"Sync {self.direction} - {self.status} ({self.connection.name})"

    def __repr__(self):
        return f"<MarketplaceSyncJob {self.id}: {self!s}>"

    def clean(self):
        """
        Validate model fields before saving.

        Raises:
            ValidationError: If validation fails
        """
        super().clean()

        # Validate direction is a valid enum value
        valid_directions = [sd.value for sd in SyncDirection]
        if self.direction not in valid_directions:
            raise ValidationError({
                'direction': f"Invalid sync direction. Must be one of: {', '.join(valid_directions)}"
            })

        # Validate status is a valid enum value
        valid_statuses = [ss.value for ss in SyncStatus]
        if self.status not in valid_statuses:
            raise ValidationError({
                'status': f"Invalid sync status. Must be one of: {', '.join(valid_statuses)}"
            })

        # Validate items_synced and items_failed are non-negative
        if self.items_synced < 0:
            raise ValidationError({
                'items_synced': "Items synced cannot be negative"
            })

        if self.items_failed < 0:
            raise ValidationError({
                'items_failed': "Items failed cannot be negative"
            })

        # Validate errors is a list
        if not isinstance(self.errors, list):
            raise ValidationError({
                'errors': "Errors must be a list"
            })

        # Validate metadata is a dictionary
        if not isinstance(self.metadata, dict):
            raise ValidationError({
                'metadata': "Metadata must be a dictionary"
            })

    def save(self, *args, **kwargs):
        """
        Save the model instance with validation.
        """
        self.full_clean()
        super().save(*args, **kwargs)

    def is_terminal(self) -> bool:
        """
        Check if sync job is in a terminal state.

        Returns:
            True if status is COMPLETED, FAILED, or PARTIAL
        """
        return self.status in [
            SyncStatus.COMPLETED.value,
            SyncStatus.FAILED.value,
            SyncStatus.PARTIAL.value
        ]

    def is_running(self) -> bool:
        """
        Check if sync job is currently running.

        Returns:
            True if status is RUNNING
        """
        return self.status == SyncStatus.RUNNING.value

    def mark_completed(self, items_synced: int = None, metadata: dict = None):
        """
        Mark sync job as completed.

        Args:
            items_synced: Optional number of items synced (if None, keeps current value)
            metadata: Optional metadata to merge with existing metadata
        """
        self.status = SyncStatus.COMPLETED.value
        self.completed_at = timezone.now()

        if items_synced is not None:
            self.items_synced = items_synced

        if metadata is not None:
            if not isinstance(metadata, dict):
                raise ValueError("Metadata must be a dictionary")
            # Merge with existing metadata
            current_metadata = self.metadata or {}
            current_metadata.update(metadata)
            self.metadata = current_metadata

        self.save(update_fields=['status', 'completed_at', 'items_synced', 'metadata', 'updated_at'])

    def mark_failed(self, error_message: str = None, items_synced: int = None, items_failed: int = None, metadata: dict = None):
        """
        Mark sync job as failed.

        Args:
            error_message: Error message to add to errors list
            items_synced: Optional number of items synced before failure
            items_failed: Optional number of items that failed
            metadata: Optional metadata to merge with existing metadata
        """
        self.status = SyncStatus.FAILED.value
        self.completed_at = timezone.now()

        if error_message:
            self.add_error(error_message, save=False)

        if items_synced is not None:
            self.items_synced = items_synced

        if items_failed is not None:
            self.items_failed = items_failed

        if metadata is not None:
            if not isinstance(metadata, dict):
                raise ValueError("Metadata must be a dictionary")
            # Merge with existing metadata
            current_metadata = self.metadata or {}
            current_metadata.update(metadata)
            self.metadata = current_metadata

        self.save(update_fields=['status', 'completed_at', 'items_synced', 'items_failed', 'errors', 'metadata', 'updated_at'])

    def add_error(self, error_message: str, save: bool = True):
        """
        Add an error message to the errors list.

        Args:
            error_message: Error message to add
            save: Whether to save the model after adding error (default: True)
        """
        if not isinstance(error_message, str):
            raise ValueError("Error message must be a string")

        if not error_message.strip():
            raise ValueError("Error message cannot be empty")

        # Ensure errors is a list
        if not isinstance(self.errors, list):
            self.errors = []

        # Add error with timestamp
        error_entry = {
            "message": error_message,
            "timestamp": timezone.now().isoformat()
        }

        self.errors.append(error_entry)

        if save:
            self.save(update_fields=['errors', 'updated_at'])

    def mark_running(self):
        """
        Mark sync job as running.
        """
        if self.status != SyncStatus.RUNNING.value:
            self.status = SyncStatus.RUNNING.value
            self.save(update_fields=['status', 'updated_at'])

    def mark_partial(self, items_synced: int, items_failed: int, metadata: dict = None):
        """
        Mark sync job as partially completed (some items succeeded, some failed).

        Args:
            items_synced: Number of items successfully synced
            items_failed: Number of items that failed
            metadata: Optional metadata to merge with existing metadata
        """
        self.status = SyncStatus.PARTIAL.value
        self.completed_at = timezone.now()
        self.items_synced = items_synced
        self.items_failed = items_failed

        if metadata is not None:
            if not isinstance(metadata, dict):
                raise ValueError("Metadata must be a dictionary")
            # Merge with existing metadata
            current_metadata = self.metadata or {}
            current_metadata.update(metadata)
            self.metadata = current_metadata

        self.save(update_fields=['status', 'completed_at', 'items_synced', 'items_failed', 'metadata', 'updated_at'])


class MarketplaceMapping(models.Model):
    """
    Marketplace mapping model.

    Maps Hub assets to external marketplace listings and resources.
    Tracks synchronization metadata and external identifiers for bidirectional
    synchronization between the Hub and external marketplaces.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the mapping"
    )
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="marketplace_mappings",
        help_text="Tenant this mapping belongs to"
    )
    connection = models.ForeignKey(
        MarketplaceConnection,
        on_delete=models.CASCADE,
        related_name="mappings",
        help_text="Marketplace connection this mapping is associated with"
    )
    hub_asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.CASCADE,
        related_name="marketplace_mappings",
        help_text="Hub asset being mapped to external marketplace"
    )
    external_listing_id = models.CharField(
        max_length=255,
        help_text="External marketplace listing identifier"
    )
    external_resource_ids = models.JSONField(
        default=list,
        blank=True,
        help_text="List of external resource identifiers (e.g., dataset IDs, file IDs)"
    )
    sync_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Metadata about the synchronization (last sync status, errors, etc.)"
    )
    last_synced_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last successful synchronization"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "marketplace_mappings"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "connection"]),
            models.Index(fields=["connection", "hub_asset"]),
            models.Index(fields=["tenant", "hub_asset"]),
            models.Index(fields=["external_listing_id"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["connection", "hub_asset"],
                name="unique_connection_asset_mapping"
            )
        ]

    def __str__(self):
        return f"{self.hub_asset.name} -> {self.connection.name} ({self.external_listing_id})"

    def __repr__(self):
        return f"<MarketplaceMapping {self.id}: {self!s}>"

    def clean(self):
        """
        Validate model fields before saving.

        Raises:
            ValidationError: If validation fails
        """
        super().clean()

        # Validate external_listing_id is not empty
        if not self.external_listing_id or not self.external_listing_id.strip():
            raise ValidationError({
                'external_listing_id': "External listing ID cannot be empty"
            })

        # Validate external_resource_ids is a list
        if not isinstance(self.external_resource_ids, list):
            raise ValidationError({
                'external_resource_ids': "External resource IDs must be a list"
            })

        # Validate sync_metadata is a dictionary
        if not isinstance(self.sync_metadata, dict):
            raise ValidationError({
                'sync_metadata': "Sync metadata must be a dictionary"
            })

        # Check for unique constraint violation manually for better error message
        if self.pk:
            # Updating existing instance
            if MarketplaceMapping.objects.filter(
                connection=self.connection,
                hub_asset=self.hub_asset
            ).exclude(pk=self.pk).exists():
                raise ValidationError({
                    '__all__': "A mapping already exists for this connection and asset."
                })
        else:
            # Creating new instance
            if MarketplaceMapping.objects.filter(
                connection=self.connection,
                hub_asset=self.hub_asset
            ).exists():
                raise ValidationError({
                    '__all__': "A mapping already exists for this connection and asset."
                })

    def save(self, *args, **kwargs):
        """
        Save the model instance with validation.
        """
        self.full_clean()
        super().save(*args, **kwargs)

    def update_sync_metadata(self, metadata: dict, last_synced_at=None):
        """
        Update synchronization metadata.

        Merges the provided metadata with existing sync_metadata and optionally
        updates the last_synced_at timestamp.

        Args:
            metadata: Dictionary of metadata to merge with existing sync_metadata
            last_synced_at: Optional datetime to set as last_synced_at (defaults to now)

        Raises:
            ValueError: If metadata is not a dictionary
        """
        if not isinstance(metadata, dict):
            raise ValueError("Metadata must be a dictionary")

        # Merge with existing metadata
        current_metadata = self.sync_metadata or {}
        current_metadata.update(metadata)
        self.sync_metadata = current_metadata

        # Update last_synced_at if provided or use current time
        if last_synced_at is not None:
            self.last_synced_at = last_synced_at
        else:
            self.last_synced_at = timezone.now()

        self.save(update_fields=['sync_metadata', 'last_synced_at', 'updated_at'])


class ScheduleType(models.TextChoices):
    """Schedule type enumeration for marketplace sync"""
    DAILY = "DAILY", "Daily"
    WEEKLY = "WEEKLY", "Weekly"
    MONTHLY = "MONTHLY", "Monthly"
    CUSTOM_CRON = "CUSTOM_CRON", "Custom Cron"


class ScheduledMarketplaceSyncStatus(models.TextChoices):
    """Scheduled marketplace sync status enumeration"""
    ACTIVE = "ACTIVE", "Active"
    PAUSED = "PAUSED", "Paused"
    ERROR = "ERROR", "Error"


class ScheduledMarketplaceSync(models.Model):
    """
    Scheduled marketplace sync model for recurring synchronization operations.

    Stores schedule configuration for marketplace sync operations that should
    run automatically on a recurring basis (daily, weekly, monthly, or custom cron).
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the scheduled sync"
    )
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="scheduled_marketplace_syncs",
        help_text="Tenant this scheduled sync belongs to"
    )
    connection = models.ForeignKey(
        MarketplaceConnection,
        on_delete=models.CASCADE,
        related_name="scheduled_syncs",
        help_text="Marketplace connection to use for sync"
    )
    name = models.CharField(
        max_length=255,
        help_text="Scheduled sync name (unique per tenant)"
    )
    description = models.TextField(
        null=True,
        blank=True,
        help_text="Optional description"
    )
    direction = models.CharField(
        max_length=20,
        choices=[(sd.value, sd.name.replace("_", " ").title()) for sd in SyncDirection],
        help_text="Sync direction: PUSH, PULL, or BIDIRECTIONAL"
    )
    schedule_type = models.CharField(
        max_length=20,
        choices=ScheduleType.choices,
        default=ScheduleType.DAILY,
        help_text="Schedule type: DAILY, WEEKLY, MONTHLY, CUSTOM_CRON"
    )
    schedule_config = models.JSONField(
        default=dict,
        help_text="Schedule configuration (cron expression, timezone, days of week, time)"
    )
    sync_options = models.JSONField(
        default=dict,
        blank=True,
        help_text="Sync options (asset_ids, listing_ids, filters, options) to use for each sync"
    )
    status = models.CharField(
        max_length=20,
        choices=ScheduledMarketplaceSyncStatus.choices,
        default=ScheduledMarketplaceSyncStatus.ACTIVE,
        help_text="Status: ACTIVE, PAUSED, ERROR"
    )
    next_run_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Next scheduled run time (calculated based on schedule)"
    )
    last_run_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last run time"
    )
    last_sync_job_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="ID of the last sync job created"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_scheduled_marketplace_syncs",
        null=True,
        blank=True,
        help_text="User who created this scheduled sync"
    )

    class Meta:
        db_table = "scheduled_marketplace_syncs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "connection"]),
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["status", "next_run_at"]),
            models.Index(fields=["connection", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name"],
                name="unique_scheduled_sync_name_per_tenant"
            )
        ]

    def __str__(self):
        return f"Scheduled Sync: {self.name} ({self.direction}) - {self.connection.name}"

    def clean(self):
        """Validate model fields before saving"""
        super().clean()

        # Validate schedule_config based on schedule_type
        if self.schedule_type == ScheduleType.CUSTOM_CRON:
            cron_expr = self.schedule_config.get("cron")
            if not cron_expr:
                raise ValidationError({
                    'schedule_config': 'Cron expression is required for CUSTOM_CRON schedule type'
                })
            # Validate cron expression
            try:
                from croniter import croniter
                croniter(cron_expr)
            except Exception as e:
                raise ValidationError({
                    'schedule_config': f'Invalid cron expression: {str(e)}'
                })

    def save(self, *args, **kwargs):
        """Override save to validate and calculate next_run_at"""
        self.full_clean()

        # Calculate next_run_at if not set or if schedule changed
        # Skip calculation if next_run_at is explicitly provided in update_fields
        update_fields = kwargs.get('update_fields')
        if update_fields and 'next_run_at' in update_fields:
            # next_run_at is being explicitly updated, don't recalculate
            pass
        elif not self.next_run_at or self._state.adding:
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

    def is_due(self) -> bool:
        """Check if scheduled sync is due to run"""
        if self.status != ScheduledMarketplaceSyncStatus.ACTIVE:
            return False
        if not self.next_run_at:
            return False
        return timezone.now() >= self.next_run_at

    def mark_run(self, sync_job_id: uuid.UUID):
        """Mark scheduled sync as run"""
        self.last_run_at = timezone.now()
        self.last_sync_job_id = sync_job_id
        self.next_run_at = self._calculate_next_run_at()
        self.save(update_fields=['last_run_at', 'last_sync_job_id', 'next_run_at', 'updated_at'])

