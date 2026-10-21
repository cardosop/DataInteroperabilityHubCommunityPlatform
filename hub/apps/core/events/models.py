"""
Event Persistence Models

PostgreSQL models for event persistence, replay, and dead letter queue.
"""

import uuid

from django.db import models
from django.db.models import JSONField


class Event(models.Model):
    """
    Event persistence model.

    Stores all events for replay, debugging, and audit purposes.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_id = models.UUIDField(unique=True, db_index=True, help_text="Event UUID")
    event_type = models.CharField(
        max_length=255, db_index=True, help_text="Event type (e.g., 'contract.created')"
    )
    event_version = models.CharField(max_length=20, help_text="Schema version")
    timestamp = models.DateTimeField(db_index=True, help_text="Event timestamp")
    source_service = models.CharField(max_length=100, help_text="Service that generated the event")
    tenant_id = models.UUIDField(null=True, blank=True, db_index=True, help_text="Tenant UUID")
    user_id = models.UUIDField(null=True, blank=True, help_text="User UUID")
    request_id = models.CharField(max_length=255, null=True, blank=True, help_text="Request ID")
    data = JSONField(help_text="Event data payload")
    metadata = JSONField(default=dict, blank=True, help_text="Additional metadata")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = "core"
        db_table = "events"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["event_type", "-timestamp"]),
            models.Index(fields=["tenant_id", "-timestamp"]),
            models.Index(fields=["source_service", "-timestamp"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.event_type} ({self.event_id})"


class DeadLetterQueue(models.Model):
    """
    Dead Letter Queue model.

    Stores events that failed to be processed after all retries.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = JSONField(help_text="Failed event payload")
    event_type = models.CharField(max_length=255, db_index=True, help_text="Event type")
    subscriber = models.CharField(max_length=255, db_index=True, help_text="Subscriber that failed")
    error_message = models.TextField(help_text="Error message")
    error_details = JSONField(
        default=dict, blank=True, help_text="Error details (stack trace, etc.)"
    )
    retry_count = models.IntegerField(default=0, help_text="Number of retries attempted")
    last_attempt_at = models.DateTimeField(auto_now=True, help_text="Last retry attempt timestamp")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True, help_text="When issue was resolved")
    resolved_by = models.UUIDField(null=True, blank=True, help_text="User who resolved")

    class Meta:
        app_label = "core"
        db_table = "dead_letter_queue"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["event_type", "-created_at"]),
            models.Index(fields=["subscriber", "-created_at"]),
            models.Index(fields=["resolved_at"]),
        ]

    def __str__(self):
        return f"{self.event_type} -> {self.subscriber} (retries: {self.retry_count})"


class EventSubscription(models.Model):
    """
    Event subscription model.

    Tracks active event subscriptions for subscribers.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscriber_name = models.CharField(
        max_length=255, db_index=True, help_text="Subscriber identifier"
    )
    event_type_pattern = models.CharField(
        max_length=255, db_index=True, help_text="Event type pattern (supports wildcards)"
    )
    is_active = models.BooleanField(
        default=True, db_index=True, help_text="Whether subscription is active"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "core"
        db_table = "event_subscriptions"
        unique_together = [["subscriber_name", "event_type_pattern"]]
        indexes = [
            models.Index(fields=["subscriber_name", "is_active"]),
            models.Index(fields=["event_type_pattern", "is_active"]),
        ]

    def __str__(self):
        return f"{self.subscriber_name} -> {self.event_type_pattern}"
