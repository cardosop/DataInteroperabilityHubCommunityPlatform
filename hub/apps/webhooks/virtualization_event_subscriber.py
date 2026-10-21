"""
Virtualization Event Subscriber

Subscribes to virtualization events from the event bus and triggers webhook deliveries.
"""

from typing import Any

import structlog

from hub.apps.core.events.subscriber import EventSubscriber
from hub.apps.webhooks.models import WebhookEventType
from hub.apps.webhooks.service import WebhookDeliveryService

logger = structlog.get_logger(__name__)


class VirtualizationEventSubscriber(EventSubscriber):
    """
    Event subscriber for virtualization events.

    Listens to virtualization events from the event bus and triggers webhook deliveries
    for webhooks subscribed to virtualization event types.
    """

    def __init__(self):
        """Initialize virtualization event subscriber."""
        super().__init__(subscriber_name="webhook_service_virtualization")
        self._register_handlers()

    def _register_handlers(self):
        """Register handlers for all virtualization event types."""
        # Subscribe to all virtualization event types
        virtualization_event_types = WebhookEventType.get_virtualization_event_types()

        for event_type in virtualization_event_types:
            self.subscribe(
                event_type_pattern=event_type,
                handler=self._handle_virtualization_event,
                is_active=True,
            )

        logger.info(
            "virtualization_event_subscriber_initialized",
            event_types_count=len(virtualization_event_types),
            event_types=virtualization_event_types,
        )

    def _handle_virtualization_event(self, event: dict[str, Any]) -> None:
        """
        Handle virtualization event and trigger webhook delivery.

        Args:
            event: Event dictionary
        """
        try:
            event_type = event.get("event_type")
            if not event_type:
                logger.warning(
                    "virtualization_event_missing_event_type", event_id=event.get("event_id")
                )
                return

            event_data = event.get("data", {})
            event_source = event.get("source", {})
            tenant_id = event_source.get("tenant_id")

            if not tenant_id:
                logger.warning(
                    "virtualization_event_missing_tenant_id",
                    event_type=event_type,
                    event_id=event.get("event_id"),
                )
                return

            # Determine resource type and ID based on event type
            if event_type.startswith("virtualization.dataset."):
                resource_type = "VIRTUAL_DATASET"
                resource_id = event_data.get("virtual_dataset_id")
            elif event_type.startswith("virtualization.query.execution."):
                resource_type = "QUERY_EXECUTION"
                resource_id = event_data.get("query_execution_id")
            else:
                # Fallback - try to find any ID in the event data
                resource_type = "VIRTUALIZATION_RESOURCE"
                resource_id = (
                    event_data.get("virtual_dataset_id")
                    or event_data.get("query_execution_id")
                    or event_data.get("id")
                )

            if not resource_id:
                logger.warning(
                    "virtualization_event_missing_resource_id",
                    event_type=event_type,
                    event_id=event.get("event_id"),
                )
                return

            # Trigger webhook delivery
            try:
                count = WebhookDeliveryService.trigger_webhook(
                    tenant_id=tenant_id,
                    event_type=event_type,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    event_data=event_data,
                )

                logger.info(
                    "virtualization_webhook_triggered_from_event",
                    event_type=event_type,
                    event_id=event.get("event_id"),
                    resource_id=resource_id,
                    tenant_id=tenant_id,
                    webhooks_triggered=count,
                )
            except Exception as e:
                logger.error(
                    "virtualization_webhook_trigger_failed",
                    event_type=event_type,
                    event_id=event.get("event_id"),
                    resource_id=resource_id,
                    tenant_id=tenant_id,
                    error=str(e),
                    exc_info=True,
                )
                # Don't raise - we want to continue processing other events
                # The error is logged for monitoring

        except Exception as e:
            logger.error(
                "virtualization_event_handler_error",
                event_id=event.get("event_id"),
                error=str(e),
                exc_info=True,
            )
            # Don't raise - we want to continue processing other events
            # The error is logged for monitoring


# Global subscriber instance
_virtualization_event_subscriber: VirtualizationEventSubscriber | None = None


def get_virtualization_event_subscriber() -> VirtualizationEventSubscriber:
    """
    Get or create the global virtualization event subscriber instance.

    Returns:
        VirtualizationEventSubscriber instance
    """
    global _virtualization_event_subscriber
    if _virtualization_event_subscriber is None:
        _virtualization_event_subscriber = VirtualizationEventSubscriber()
    return _virtualization_event_subscriber


def initialize_virtualization_event_subscriber() -> VirtualizationEventSubscriber:
    """
    Initialize the virtualization event subscriber.

    This function should be called during app startup to ensure
    the subscriber is registered and listening for virtualization events.

    Returns:
        VirtualizationEventSubscriber instance
    """
    subscriber = get_virtualization_event_subscriber()
    logger.info(
        "virtualization_event_subscriber_initialized", subscriber_name=subscriber.subscriber_name
    )
    return subscriber
