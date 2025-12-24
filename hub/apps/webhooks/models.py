"""
Webhook Models

Models for webhook subscriptions and delivery tracking.
"""
import uuid
import hmac
import hashlib
import json
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError


class WebhookStatus(models.TextChoices):
    """Webhook subscription status"""
    ACTIVE = "ACTIVE", "Active"
    PAUSED = "PAUSED", "Paused"
    DISABLED = "DISABLED", "Disabled"


class WebhookEventType(models.TextChoices):
    """Webhook event types"""
    # Contract events
    CONTRACT_CREATED = "contract.created", "Contract Created"
    CONTRACT_UPDATED = "contract.updated", "Contract Updated"
    CONTRACT_DELETED = "contract.deleted", "Contract Deleted"

    # Asset events
    ASSET_CREATED = "asset.created", "Asset Created"
    ASSET_UPDATED = "asset.updated", "Asset Updated"
    ASSET_ACTIVATED = "asset.activated", "Asset Activated"

    # Ingestion events
    INGESTION_COMPLETED = "ingestion.completed", "Ingestion Completed"
    INGESTION_FAILED = "ingestion.failed", "Ingestion Failed"

    # Quality events
    QUALITY_CHECK_COMPLETED = "quality.check.completed", "Quality Check Completed"
    COMPLIANCE_CHECK_COMPLETED = "compliance.check.completed", "Compliance Check Completed"

    # Version events
    VERSION_CREATED = "version.created", "Version Created"
    VERSION_UPDATED = "version.updated", "Version Updated"

    # ODPS events
    ODPS_CREATED = "odps.created", "ODPS Created"
    ODPS_UPDATED = "odps.updated", "ODPS Updated"
    ODPS_DELETED = "odps.deleted", "ODPS Deleted"
    ODPS_NORMALIZED = "odps.normalized", "ODPS Normalized"
    ODPS_LINKED = "odps.linked", "ODPS Linked"
    ODPS_UNLINKED = "odps.unlinked", "ODPS Unlinked"
    ODPS_EXPORT_STARTED = "odps.export.started", "ODPS Export Started"
    ODPS_EXPORT_COMPLETED = "odps.export.completed", "ODPS Export Completed"
    ODPS_EXPORT_FAILED = "odps.export.failed", "ODPS Export Failed"

    @classmethod
    def get_odps_event_types(cls) -> list[str]:
        """
        Get all ODPS event type values.

        Returns:
            List of ODPS event type string values
        """
        # For TextChoices, we need to get the actual string values
        # The enum members can be converted to strings, or we can use the choices
        return [
            str(cls.ODPS_CREATED),  # Convert enum member to string
            str(cls.ODPS_UPDATED),
            str(cls.ODPS_DELETED),
            str(cls.ODPS_NORMALIZED),
            str(cls.ODPS_LINKED),
            str(cls.ODPS_UNLINKED),
            str(cls.ODPS_EXPORT_STARTED),
            str(cls.ODPS_EXPORT_COMPLETED),
            str(cls.ODPS_EXPORT_FAILED),
        ]

    @classmethod
    def is_odps_event_type(cls, event_type: str | tuple) -> bool:
        """
        Check if an event type is an ODPS event.

        Args:
            event_type: Event type string, tuple, or enum value to check

        Returns:
            True if the event type is an ODPS event, False otherwise
        """
        # Extract string value if event_type is a tuple (enum choice tuple)
        if isinstance(event_type, (tuple, list)) and len(event_type) > 0:
            event_type = event_type[0]
        # Extract string value if event_type is an enum
        elif hasattr(event_type, 'value'):
            event_type = event_type.value
        return event_type in cls.get_odps_event_types()


class DeliveryStatus(models.TextChoices):
    """Webhook delivery status"""
    PENDING = "PENDING", "Pending"
    SUCCESS = "SUCCESS", "Success"
    FAILED = "FAILED", "Failed"
    DEAD_LETTER = "DEAD_LETTER", "Dead Letter"


class Webhook(models.Model):
    """
    Webhook subscription model.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="webhooks",
        help_text="Tenant this webhook belongs to"
    )
    name = models.CharField(
        max_length=255,
        help_text="Webhook name/description"
    )
    url = models.URLField(
        max_length=2048,
        help_text="Webhook delivery URL"
    )
    secret = models.CharField(
        max_length=255,
        help_text="Webhook secret for HMAC signature (encrypted)"
    )
    event_types = models.JSONField(
        default=list,
        help_text="List of event types to subscribe to"
    )
    status = models.CharField(
        max_length=20,
        choices=WebhookStatus.choices,
        default=WebhookStatus.ACTIVE,
        help_text="Webhook status"
    )
    max_retries = models.IntegerField(
        default=5,
        help_text="Maximum number of delivery retries"
    )
    retry_intervals = models.JSONField(
        default=list,
        help_text="Retry intervals in seconds: [1, 5, 30, 300, 1800]"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_webhooks",
        null=True,
        blank=True,
        help_text="User who created the webhook"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "webhooks"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "event_types"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.url})"

    def clean(self):
        """Validate webhook configuration"""
        super().clean()

        # Normalize event types - convert enum tuples to string values
        if self.event_types:
            normalized_event_types = []
            valid_event_types = [choice[0] for choice in WebhookEventType.choices]
        normalized_event_types = []
        for event_type in self.event_types:
            # Extract string value from different input types
            if isinstance(event_type, (tuple, list)) and len(event_type) > 0:
                # Tuple/list: extract first element
                event_type_value = event_type[0]
            elif isinstance(event_type, WebhookEventType):
                # Enum: get the value attribute or convert to string
                event_type_value = getattr(event_type, 'value', str(event_type))
            else:
                # Already a string or other type
                event_type_value = str(event_type)

            # Validate
            if event_type_value not in valid_event_types:
                raise ValidationError(f"Invalid event type: {event_type_value}")

            normalized_event_types.append(event_type_value)

        self.event_types = normalized_event_types

        # Validate event types
        if not self.event_types:
            raise ValidationError("At least one event type must be specified")

        # Validate retry intervals
        if not self.retry_intervals:
            self.retry_intervals = [1, 5, 30, 300, 1800]  # Default: 1s, 5s, 30s, 5m, 30m

        if len(self.retry_intervals) != self.max_retries:
            raise ValidationError(
                f"Number of retry intervals ({len(self.retry_intervals)}) "
                f"must match max_retries ({self.max_retries})"
            )

    def save(self, *args, **kwargs):
        """Override save to ensure event_types are normalized and defaults are set"""
        # Set defaults before normalization
        if not self.retry_intervals:
            self.retry_intervals = [1, 5, 30, 300, 1800]  # Default: 1s, 5s, 30s, 5m, 30m

        if not self.max_retries:
            self.max_retries = 5

        # Normalize event types before saving
        if self.event_types:
            normalized_event_types = []
            valid_event_types = [choice[0] for choice in WebhookEventType.choices]
            for event_type in self.event_types:
                # Extract string value from different input types
                if isinstance(event_type, (tuple, list)) and len(event_type) > 0:
                    # Tuple/list: extract first element
                    event_type_value = event_type[0]
                elif isinstance(event_type, WebhookEventType):
                    # Enum: get the value attribute or convert to string
                    event_type_value = getattr(event_type, 'value', str(event_type))
                else:
                    # Already a string or other type
                    event_type_value = str(event_type)

                # Only add if it's a valid event type
                if event_type_value in valid_event_types:
                    normalized_event_types.append(event_type_value)

            # Only update if normalization changed something
            if normalized_event_types != self.event_types:
                self.event_types = normalized_event_types

        # Call full_clean to ensure validation (after setting defaults)
        self.full_clean()
        super().save(*args, **kwargs)

    def generate_signature(self, payload: str) -> str:
        """Generate HMAC signature for webhook payload"""
        return hmac.new(
            self.secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    def subscribes_to_odps_events(self) -> bool:
        """
        Check if this webhook subscribes to any ODPS events.

        Returns:
            True if webhook subscribes to at least one ODPS event, False otherwise
        """
        odps_event_types = WebhookEventType.get_odps_event_types()
        # event_types should be normalized to strings in clean(), but handle both cases
        for event_type in self.event_types:
            # Extract string value from different input types
            if isinstance(event_type, (tuple, list)) and len(event_type) > 0:
                event_type_value = event_type[0]
            elif isinstance(event_type, WebhookEventType):
                event_type_value = getattr(event_type, 'value', str(event_type))
            else:
                event_type_value = str(event_type)

            if event_type_value in odps_event_types:
                return True
        return False

    def subscribes_to_event_type(self, event_type: str) -> bool:
        """
        Check if this webhook subscribes to a specific event type.

        Args:
            event_type: Event type string to check (or tuple to extract value from)

        Returns:
            True if webhook subscribes to the event type, False otherwise
        """
        # Extract string value from different input types
        if isinstance(event_type, (tuple, list)) and len(event_type) > 0:
            event_type_value = event_type[0]
        elif isinstance(event_type, WebhookEventType):
            event_type_value = getattr(event_type, 'value', str(event_type))
        else:
            event_type_value = str(event_type)

        # event_types should be normalized to strings in clean(), but handle both cases
        # Also check if stored values are enums and normalize them
        for stored_type in self.event_types:
            if isinstance(stored_type, WebhookEventType):
                stored_value = getattr(stored_type, 'value', str(stored_type))
            else:
                stored_value = str(stored_type)

            if stored_value == event_type_value:
                return True

        return False

    @classmethod
    def filter_by_odps_events(cls, queryset=None):
        """
        Filter webhooks that subscribe to ODPS events.

        Args:
            queryset: Optional queryset to filter (defaults to all webhooks)

        Returns:
            QuerySet of webhooks that subscribe to at least one ODPS event
        """
        from django.db.models import Q

        if queryset is None:
            queryset = cls.objects.all()

        odps_event_types = WebhookEventType.get_odps_event_types()

        # Build query to check if any ODPS event type is in the event_types JSON field
        # For JSONField arrays, __contains checks if the array contains the value (not a list)
        query = Q()
        for event_type in odps_event_types:
            query |= Q(event_types__contains=event_type)

        return queryset.filter(query)

    @classmethod
    def filter_by_event_type(cls, event_type: str | tuple, queryset=None):
        """
        Filter webhooks that subscribe to a specific event type.

        Args:
            event_type: Event type string or tuple to filter by
            queryset: Optional queryset to filter (defaults to all webhooks)

        Returns:
            QuerySet of webhooks that subscribe to the specified event type
        """
        if queryset is None:
            queryset = cls.objects.all()

        # Extract string value if it's a tuple (enum value)
        if isinstance(event_type, (tuple, list)) and len(event_type) > 0:
            event_type = event_type[0]

        # For JSONField arrays, __contains checks if the array contains the value (not a list)
        return queryset.filter(event_types__contains=event_type)


class WebhookDelivery(models.Model):
    """
    Webhook delivery tracking model.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    webhook = models.ForeignKey(
        Webhook,
        on_delete=models.CASCADE,
        related_name="deliveries",
        help_text="Webhook subscription"
    )
    event_type = models.CharField(
        max_length=100,
        help_text="Event type that triggered the delivery"
    )
    payload = models.JSONField(
        help_text="Webhook payload (event data)"
    )
    signature = models.CharField(
        max_length=64,
        help_text="HMAC signature of the payload"
    )
    status = models.CharField(
        max_length=20,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.PENDING,
        help_text="Delivery status"
    )
    attempt_number = models.IntegerField(
        default=0,
        help_text="Current attempt number (0-indexed)"
    )
    http_status_code = models.IntegerField(
        null=True,
        blank=True,
        help_text="HTTP status code from delivery attempt"
    )
    response_body = models.TextField(
        null=True,
        blank=True,
        help_text="Response body from delivery attempt"
    )
    error_message = models.TextField(
        null=True,
        blank=True,
        help_text="Error message if delivery failed"
    )
    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When delivery succeeded"
    )
    next_retry_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When to retry delivery (if failed)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "webhook_deliveries"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["webhook", "status"]),
            models.Index(fields=["webhook", "next_retry_at"]),
            models.Index(fields=["status", "next_retry_at"]),
        ]

    def __str__(self):
        return f"{self.webhook.name} - {self.event_type} ({self.status})"

