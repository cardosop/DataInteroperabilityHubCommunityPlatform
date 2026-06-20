"""
Event Outbox Pattern

Implements the outbox pattern for reliable event publishing in microservices.
Ensures events are published even if the service crashes after database commit.
"""

import uuid

import structlog
from django.db import models, transaction
from django.utils import timezone

from hub.apps.core.events.bus import EventBus

logger = structlog.get_logger(__name__)


class EventOutbox(models.Model):
    """
    Event outbox table for reliable event publishing.

    Events are stored here before being published to the event bus.
    A background job processes the outbox and publishes events.

    This model is defined here to keep it close to the outbox logic.
    The migration is in hub/apps/core/migrations/0002_create_event_outbox.py
    """

    """
    Event outbox table for reliable event publishing.
    
    Events are stored here before being published to the event bus.
    A background job processes the outbox and publishes events.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_id = models.UUIDField(
        null=True, blank=True, db_index=True, help_text="Tenant ID for tenant isolation"
    )
    event_type = models.CharField(
        max_length=255, db_index=True, help_text="Event type (e.g., 'asset.created')"
    )
    event_data = models.JSONField(help_text="Event payload (JSON)")
    status = models.CharField(
        max_length=50,
        choices=[
            ("PENDING", "Pending"),
            ("PUBLISHED", "Published"),
            ("FAILED", "Failed"),
        ],
        default="PENDING",
        db_index=True,
        help_text="Event status",
    )
    retry_count = models.IntegerField(default=0, help_text="Number of retry attempts")
    max_retries = models.IntegerField(default=5, help_text="Maximum number of retries")
    error_message = models.TextField(
        null=True, blank=True, help_text="Error message if publishing failed"
    )
    created_at = models.DateTimeField(
        auto_now_add=True, db_index=True, help_text="When event was created"
    )
    published_at = models.DateTimeField(null=True, blank=True, help_text="When event was published")

    class Meta:
        db_table = "event_outbox"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["tenant_id", "status"]),
        ]

    def __str__(self):
        return f"{self.event_type} ({self.status})"


class OutboxPublisher:
    """
    Publisher for event outbox pattern.

    Stores events in outbox table within the same transaction as business logic.
    """

    def __init__(self, event_bus: EventBus):
        """
        Initialize outbox publisher.

        Args:
            event_bus: Event bus instance for publishing
        """
        self.event_bus = event_bus

    @transaction.atomic
    def publish(
        self, event_type: str, event_data: dict, tenant_id: str | None = None
    ) -> EventOutbox:
        """
        Store event in outbox for later publishing.

        This method should be called within the same transaction as the business logic
        that triggers the event. The event will be published by a background job.

        Args:
            event_type: Event type (e.g., 'asset.created')
            event_data: Event payload
            tenant_id: Optional tenant ID

        Returns:
            EventOutbox instance
        """
        outbox_event = EventOutbox.objects.create(
            tenant_id=tenant_id, event_type=event_type, event_data=event_data, status="PENDING"
        )

        logger.debug(
            "Event stored in outbox",
            event_type=event_type,
            outbox_id=str(outbox_event.id),
            tenant_id=tenant_id,
        )

        return outbox_event

    def process_outbox(self, batch_size: int = 100) -> int:
        """
        Process pending events from outbox.

        This method should be called by a background job (e.g., cron, celery).

        Args:
            batch_size: Number of events to process per batch

        Returns:
            Number of events processed
        """
        pending_events = EventOutbox.objects.filter(
            status="PENDING", retry_count__lt=models.F("max_retries")
        ).order_by("created_at")[:batch_size]

        processed_count = 0

        for event in pending_events:
            try:
                # Publish event
                self.event_bus.publish(
                    event.event_type,
                    event.event_data,
                    tenant_id=str(event.tenant_id) if event.tenant_id else None,
                )

                # Mark as published
                event.status = "PUBLISHED"
                event.published_at = timezone.now()
                event.save(update_fields=["status", "published_at"])

                processed_count += 1

                logger.debug(
                    "Event published from outbox",
                    event_type=event.event_type,
                    outbox_id=str(event.id),
                )

            except Exception as e:
                # Increment retry count
                event.retry_count += 1
                event.error_message = str(e)

                if event.retry_count >= event.max_retries:
                    event.status = "FAILED"
                    logger.error(
                        "Event failed after max retries",
                        event_type=event.event_type,
                        outbox_id=str(event.id),
                        error=str(e),
                    )
                else:
                    logger.warning(
                        "Event publish failed, will retry",
                        event_type=event.event_type,
                        outbox_id=str(event.id),
                        retry_count=event.retry_count,
                        error=str(e),
                    )

                event.save(update_fields=["retry_count", "error_message", "status"])

        return processed_count

    def cleanup_old_events(self, days: int = 7) -> int:
        """
        Clean up old published events from outbox.

        Args:
            days: Number of days to keep published events

        Returns:
            Number of events deleted
        """
        cutoff_date = timezone.now() - timezone.timedelta(days=days)

        deleted_count, _ = EventOutbox.objects.filter(
            status="PUBLISHED", published_at__lt=cutoff_date
        ).delete()

        logger.info(
            "Cleaned up old outbox events", deleted_count=deleted_count, cutoff_date=cutoff_date
        )

        return deleted_count


# Global outbox publisher instance
_outbox_publisher = None


def get_outbox_publisher() -> OutboxPublisher:
    """Get global outbox publisher instance."""
    global _outbox_publisher
    if _outbox_publisher is None:
        from hub.apps.core.events.bus import get_event_bus

        event_bus = get_event_bus()
        _outbox_publisher = OutboxPublisher(event_bus)
    return _outbox_publisher
