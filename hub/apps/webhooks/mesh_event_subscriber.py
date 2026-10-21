"""
Mesh Event Subscriber

Subscribes to mesh events from the event bus and triggers webhook deliveries.
"""

from typing import Any

import structlog

from hub.apps.core.events.subscriber import EventSubscriber
from hub.apps.webhooks.models import WebhookEventType
from hub.apps.webhooks.service import WebhookDeliveryService

logger = structlog.get_logger(__name__)


class MeshEventSubscriber(EventSubscriber):
    """
    Event subscriber for mesh events.

    Listens to mesh events from the event bus and triggers webhook deliveries
    for webhooks subscribed to mesh event types.
    """

    def __init__(self):
        """Initialize mesh event subscriber."""
        super().__init__(subscriber_name="webhook_service_mesh")
        self._register_handlers()

    def _register_handlers(self):
        """Register handlers for all mesh event types."""
        # Subscribe to all mesh event types
        mesh_event_types = WebhookEventType.get_mesh_event_types()

        for event_type in mesh_event_types:
            self.subscribe(
                event_type_pattern=event_type, handler=self._handle_mesh_event, is_active=True
            )

        logger.info(
            "mesh_event_subscriber_initialized",
            event_types_count=len(mesh_event_types),
            event_types=mesh_event_types,
        )

    def _handle_mesh_event(self, event: dict[str, Any]) -> None:
        """
        Handle mesh event and trigger webhook delivery.

        Args:
            event: Event dictionary
        """
        try:
            event_type = event.get("event_type")
            if not event_type:
                logger.warning("mesh_event_missing_event_type", event_id=event.get("event_id"))
                return

            event_data = event.get("data", {})
            event_source = event.get("source", {})
            tenant_id = event_source.get("tenant_id")

            if not tenant_id:
                logger.warning(
                    "mesh_event_missing_tenant_id",
                    event_type=event_type,
                    event_id=event.get("event_id"),
                )
                return

            # Determine resource type and ID based on event type
            resource_type = "DATA_MESH_DOMAIN"
            resource_id = (
                event_data.get("domain_id") or event_data.get("policy_application_id") or tenant_id
            )

            if not resource_id:
                logger.warning(
                    "mesh_event_missing_resource_id",
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
                    "mesh_webhook_triggered_from_event",
                    event_type=event_type,
                    event_id=event.get("event_id"),
                    resource_id=resource_id,
                    tenant_id=tenant_id,
                    webhooks_triggered=count,
                )
            except Exception as e:
                logger.error(
                    "mesh_webhook_trigger_failed",
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
                "mesh_event_handler_error",
                event_id=event.get("event_id"),
                error=str(e),
                exc_info=True,
            )
            # Don't raise - we want to continue processing other events
            # The error is logged for monitoring


# Global subscriber instance
_mesh_event_subscriber: MeshEventSubscriber | None = None


def get_mesh_event_subscriber() -> MeshEventSubscriber:
    """
    Get or create the global mesh event subscriber instance.

    Returns:
        MeshEventSubscriber instance
    """
    global _mesh_event_subscriber
    if _mesh_event_subscriber is None:
        _mesh_event_subscriber = MeshEventSubscriber()
    return _mesh_event_subscriber


def initialize_mesh_event_subscriber() -> MeshEventSubscriber:
    """
    Initialize the mesh event subscriber.

    This function should be called during app startup to ensure
    the subscriber is registered and listening for mesh events.

    Returns:
        MeshEventSubscriber instance
    """
    subscriber = get_mesh_event_subscriber()
    logger.info("mesh_event_subscriber_initialized", subscriber_name=subscriber.subscriber_name)
    return subscriber
