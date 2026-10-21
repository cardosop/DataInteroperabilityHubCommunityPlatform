"""
Asset Event Subscriber

Subscribes to asset events from the event bus and triggers webhook
deliveries.

This is the bridge that makes the ``asset.*`` WebhookEventTypes
(``asset.created`` / ``asset.updated`` / ``asset.activated`` —
``WebhookEventType`` choices, so tenants can subscribe to them via
``POST /api/v1/webhooks/``) actually reach ``WebhookDeliveryService``.

The asset-creation workflow publishes ``asset.created`` (and the asset
service publishes the other asset events) through ``EventPublisher``
(hub/apps/orchestration/workflows/asset_creation.py:1643,
hub/apps/assets/services.py:645), but until this subscriber existed NO
subscriber covered the ``asset.*`` domain — the only ``asset.*``
registration (``asset_event_handler`` in core/events/subscribers.py)
just logs. Webhooks registered for ``asset.created`` therefore received
zero delivery rows (b7 #43/#44: webhook-delivery E2E timed out with
"Last: null" — the webhook rows existed, the delivery rows never did).

Mirrors the mesh/odps/virtualization subscribers: registered during
``WebhooksConfig.ready()``, handler extracts tenant/resource from the
event envelope and delegates to ``WebhookDeliveryService.trigger_webhook``.
"""

from typing import Any

import structlog

from hub.apps.core.events.subscriber import EventSubscriber
from hub.apps.webhooks.models import WebhookEventType
from hub.apps.webhooks.service import WebhookDeliveryService

logger = structlog.get_logger(__name__)

# The asset event types tenants can subscribe to (serializer validates
# against WebhookEventType.choices). asset.published / asset.retired
# exist on the bus registry but are not subscribable WebhookEventTypes,
# so they are intentionally absent here.
ASSET_WEBHOOK_EVENT_TYPES: list[str] = [
    str(WebhookEventType.ASSET_CREATED),
    str(WebhookEventType.ASSET_UPDATED),
    str(WebhookEventType.ASSET_ACTIVATED),
]


class AssetEventSubscriber(EventSubscriber):
    """
    Event subscriber for asset events.

    Listens to asset events from the event bus and triggers webhook
    deliveries for webhooks subscribed to asset event types.
    """

    def __init__(self):
        """Initialize asset event subscriber."""
        super().__init__(subscriber_name="webhook_service_assets")
        self._register_handlers()

    def _register_handlers(self):
        """Register handlers for all subscribable asset event types."""
        for event_type in ASSET_WEBHOOK_EVENT_TYPES:
            self.subscribe(
                event_type_pattern=event_type, handler=self._handle_asset_event, is_active=True
            )

        logger.info(
            "asset_event_subscriber_initialized",
            event_types_count=len(ASSET_WEBHOOK_EVENT_TYPES),
            event_types=ASSET_WEBHOOK_EVENT_TYPES,
        )

    def _handle_asset_event(self, event: dict[str, Any]) -> None:
        """
        Handle asset event and trigger webhook delivery.

        Args:
            event: Event dictionary
        """
        try:
            event_type = event.get("event_type")
            if not event_type:
                logger.warning("asset_event_missing_event_type", event_id=event.get("event_id"))
                return

            event_data = event.get("data", {})
            event_source = event.get("source", {})
            tenant_id = event_source.get("tenant_id")

            if not tenant_id:
                logger.warning(
                    "asset_event_missing_tenant_id",
                    event_type=event_type,
                    event_id=event.get("event_id"),
                )
                return

            # The asset.* event schemas (core/events/event_types.py)
            # require ``asset_id`` in the data payload.
            resource_id = event_data.get("asset_id")

            if not resource_id:
                logger.warning(
                    "asset_event_missing_resource_id",
                    event_type=event_type,
                    event_id=event.get("event_id"),
                )
                return

            count = WebhookDeliveryService.trigger_webhook(
                tenant_id=tenant_id,
                event_type=event_type,
                resource_type="ASSET",
                resource_id=resource_id,
                event_data=event_data,
            )

            logger.info(
                "asset_webhook_triggered_from_event",
                event_type=event_type,
                event_id=event.get("event_id"),
                resource_id=resource_id,
                tenant_id=tenant_id,
                webhooks_triggered=count,
            )
        except Exception as e:
            logger.error(
                "asset_webhook_trigger_failed",
                event_id=event.get("event_id"),
                error=str(e),
                exc_info=True,
            )
            # Don't raise - we want to continue processing other events.
            # The error is logged for monitoring.


# Global subscriber instance
_asset_event_subscriber: AssetEventSubscriber | None = None


def trigger_asset_webhook_event(
    *,
    event_type: str,
    asset_id: str,
    tenant_id: str,
    data_extra: dict[str, Any] | None = None,
) -> int:
    """Trigger webhook deliveries for an ``asset.*`` event IN-PROCESS.

    The bus-based :class:`AssetEventSubscriber` only receives events when
    a process runs ``EventBus.start_listening()`` (Redis pub/sub loop) —
    no process in the stack starts one, so bus-subscribed asset webhook
    delivery was structurally dead (webhook-delivery E2E timed out with
    "Last: null": the webhook row existed, delivery rows never did).
    Mirrors the mesh in-process pattern
    (``DataMeshEventPublisher._trigger_webhook_for_event``): the publish
    call sites invoke this helper right after ``EventPublisher.publish``
    so delivery no longer depends on a listener.

    Fail-open: a webhook outage must never fail the asset operation that
    published the event (same contract as the publish itself).

    Returns:
        Number of webhooks triggered (0 when the trigger raised).
    """
    # W4.1 (R2-B3/B4): when the deployment runs the worker bus listener,
    # delivery is the listener's job — firing the in-process fallback
    # too would DOUBLE-deliver (Phase 226 G11 fallback vs the live bus
    # path).  The flag is a deployment-wide contract: worker AND api
    # services set it together.
    from django.conf import settings

    if getattr(settings, "EVENT_BUS_LISTENER_ENABLED", False):
        logger.debug(
            "asset_webhook_in_process_trigger_skipped",
            reason="EVENT_BUS_LISTENER_ENABLED",
            event_type=event_type,
        )
        return 0
    try:
        event_data: dict[str, Any] = {"asset_id": asset_id}
        if data_extra:
            event_data.update({k: v for k, v in data_extra.items() if v is not None})
        return WebhookDeliveryService.trigger_webhook(
            tenant_id=tenant_id,
            event_type=event_type,
            resource_type="ASSET",
            resource_id=asset_id,
            event_data=event_data,
        )
    except Exception as exc:
        logger.error(
            "asset_webhook_trigger_failed_inline",
            event_type=event_type,
            asset_id=asset_id,
            error=str(exc),
            exc_info=True,
        )
        return 0


def get_asset_event_subscriber() -> AssetEventSubscriber:
    """
    Get or create the global asset event subscriber instance.

    Returns:
        AssetEventSubscriber instance
    """
    global _asset_event_subscriber  # noqa: PLW0603 — module-singleton lazy init (repo idiom, ratcheted)
    if _asset_event_subscriber is None:
        _asset_event_subscriber = AssetEventSubscriber()
    return _asset_event_subscriber


def initialize_asset_event_subscriber() -> AssetEventSubscriber:
    """
    Initialize the asset event subscriber.

    This function should be called during app startup to ensure
    the subscriber is registered and listening for asset events.

    Returns:
        AssetEventSubscriber instance
    """
    subscriber = get_asset_event_subscriber()
    logger.info("asset_event_subscriber_initialized", subscriber_name=subscriber.subscriber_name)
    return subscriber
