"""
ODPS Event Subscriber

Subscribes to ODPS events from the event bus and triggers webhook deliveries.
"""

from typing import Dict, Any
import structlog

from hub.apps.core.events.subscriber import EventSubscriber
from hub.apps.webhooks.service import WebhookDeliveryService
from hub.apps.webhooks.models import WebhookEventType

logger = structlog.get_logger(__name__)


class ODPSEventSubscriber(EventSubscriber):
    """
    Event subscriber for ODPS events.

    Listens to ODPS events from the event bus and triggers webhook deliveries
    for webhooks subscribed to ODPS event types.
    """

    def __init__(self):
        """Initialize ODPS event subscriber."""
        super().__init__(subscriber_name="webhook_service_odps")
        self._register_handlers()

    def _register_handlers(self):
        """Register handlers for all ODPS event types."""
        # Subscribe to all ODPS event types
        odps_event_types = WebhookEventType.get_odps_event_types()

        for event_type in odps_event_types:
            self.subscribe(
                event_type_pattern=event_type,
                handler=self._handle_odps_event,
                is_active=True
            )

        logger.info(
            "odps_event_subscriber_initialized",
            event_types_count=len(odps_event_types),
            event_types=odps_event_types
        )

    def _handle_odps_event(self, event: Dict[str, Any]) -> None:
        """
        Handle ODPS event and trigger webhook delivery.

        Args:
            event: Event dictionary from event bus
        """
        try:
            event_type = event.get("event_type")
            event_data = event.get("data", {})
            source = event.get("source", {})
            tenant_id = source.get("tenant_id")

            if not tenant_id:
                logger.warning(
                    "odps_event_missing_tenant_id",
                    event_type=event_type,
                    event_id=event.get("event_id")
                )
                return

            if not event_type:
                logger.warning(
                    "odps_event_missing_event_type",
                    event_id=event.get("event_id")
                )
                return

            # Extract resource information from event data
            # ODPS events typically have contract_id, but linked events have odps_contract_id
            contract_id = event_data.get("contract_id") or event_data.get("odps_contract_id")
            if not contract_id:
                logger.warning(
                    "odps_event_missing_contract_id",
                    event_type=event_type,
                    event_id=event.get("event_id"),
                    event_data_keys=list(event_data.keys())
                )
                return

            # Determine resource type based on event type
            resource_type = "ODPS"

            # Trigger webhook delivery
            try:
                count = WebhookDeliveryService.trigger_odps_webhook(
                    tenant_id=tenant_id,
                    event_type=event_type,
                    resource_type=resource_type,
                    resource_id=contract_id,
                    event_data=event_data
                )

                logger.info(
                    "odps_webhook_triggered_from_event",
                    event_type=event_type,
                    event_id=event.get("event_id"),
                    contract_id=contract_id,
                    tenant_id=tenant_id,
                    webhooks_triggered=count
                )
            except Exception as e:
                logger.error(
                    "odps_webhook_trigger_failed",
                    event_type=event_type,
                    event_id=event.get("event_id"),
                    contract_id=contract_id,
                    tenant_id=tenant_id,
                    error=str(e),
                    exc_info=True
                )
                # Don't raise - we want to continue processing other events
                # The error is logged for monitoring

        except Exception as e:
            logger.error(
                "odps_event_handler_error",
                event_id=event.get("event_id"),
                error=str(e),
                exc_info=True
            )
            # Don't raise - we want to continue processing other events
            # The error is logged for monitoring


# Global subscriber instance
_odps_event_subscriber: ODPSEventSubscriber | None = None


def get_odps_event_subscriber() -> ODPSEventSubscriber:
    """
    Get or create the global ODPS event subscriber instance.

    Returns:
        ODPSEventSubscriber instance
    """
    global _odps_event_subscriber
    if _odps_event_subscriber is None:
        _odps_event_subscriber = ODPSEventSubscriber()
    return _odps_event_subscriber


def initialize_odps_event_subscriber() -> ODPSEventSubscriber:
    """
    Initialize the ODPS event subscriber.

    This should be called during application startup to register
    the subscriber with the event bus.

    Returns:
        ODPSEventSubscriber instance
    """
    subscriber = get_odps_event_subscriber()
    logger.info(
        "odps_event_subscriber_initialized",
        subscriber_name=subscriber.subscriber_name
    )
    return subscriber

