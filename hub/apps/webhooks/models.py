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
        
        # Validate event types
        if not self.event_types:
            raise ValidationError("At least one event type must be specified")
        
        valid_event_types = [choice[0] for choice in WebhookEventType.choices]
        for event_type in self.event_types:
            if event_type not in valid_event_types:
                raise ValidationError(f"Invalid event type: {event_type}")
        
        # Validate retry intervals
        if not self.retry_intervals:
            self.retry_intervals = [1, 5, 30, 300, 1800]  # Default: 1s, 5s, 30s, 5m, 30m
        
        if len(self.retry_intervals) != self.max_retries:
            raise ValidationError(
                f"Number of retry intervals ({len(self.retry_intervals)}) "
                f"must match max_retries ({self.max_retries})"
            )
    
    def generate_signature(self, payload: str) -> str:
        """Generate HMAC signature for webhook payload"""
        return hmac.new(
            self.secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()


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

