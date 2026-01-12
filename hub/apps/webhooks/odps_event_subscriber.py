"""
ODPS Event Subscriber

Subscribes to ODPS events from the event bus and triggers webhook deliveries.
Includes retry logic and dead letter queue handling.
"""

import time
import traceback
from typing import Dict, Any, Optional
import structlog
from django.utils import timezone

from hub.apps.core.events.subscriber import EventSubscriber
from hub.apps.core.events.models import DeadLetterQueue
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
        Handle ODPS event and trigger webhook delivery with retry logic and DLQ handling.

        Args:
            event: Event dictionary from event bus
        """
        event_id = event.get("event_id")
        event_type = event.get("event_type")

        try:
            event_data = event.get("data", {})
            source = event.get("source", {})
            tenant_id = source.get("tenant_id")

            if not tenant_id:
                logger.warning(
                    "odps_event_missing_tenant_id",
                    event_type=event_type,
                    event_id=event_id
                )
                return

            if not event_type:
                logger.warning(
                    "odps_event_missing_event_type",
                    event_id=event_id
                )
                return

            # Extract resource information from event data
            # ODPS events typically have contract_id, but linked events have odps_contract_id
            contract_id = event_data.get("contract_id") or event_data.get("odps_contract_id")
            if not contract_id:
                logger.warning(
                    "odps_event_missing_contract_id",
                    event_type=event_type,
                    event_id=event_id,
                    event_data_keys=list(event_data.keys())
                )
                return

            # Determine resource type based on event type
            resource_type = "ODPS"

            # Trigger webhook delivery with retry logic
            self._trigger_webhook_with_retry(
                event=event,
                event_type=event_type,
                tenant_id=tenant_id,
                contract_id=contract_id,
                resource_type=resource_type,
                event_data=event_data
            )

        except Exception as e:
            logger.error(
                "odps_event_handler_error",
                event_id=event_id,
                event_type=event_type,
                error=str(e),
                exc_info=True
            )
            # Send to DLQ after handler-level error
            self._send_to_dlq(event, str(e), retry_count=0)

    def _is_transient_failure(self, error: Exception) -> bool:
        """
        Check if an exception represents a transient failure that should be retried.

        Args:
            error: Exception instance

        Returns:
            True if exception is transient and should be retried
        """
        error_str = str(error).lower()
        error_type = type(error).__name__

        # Transient error indicators
        transient_keywords = [
            'timeout', 'timed out', 'connection', 'unavailable', 'network',
            'temporary', 'retry', 'service unavailable', '503', '502', '504',
            'connection refused', 'connection reset', 'broken pipe',
            'connection pool', 'socket', 'errno'
        ]

        # Non-retryable error types
        non_retryable_errors = [
            'ValidationError',
            'PermissionDenied',
            'AuthenticationFailed',
            'NotFound',
            'ValueError',
            'TypeError',
            'AttributeError',
        ]

        # Don't retry on non-retryable error types
        if any(non_retryable in error_type for non_retryable in non_retryable_errors):
            return False

        # Check for transient keywords in error message
        return any(keyword in error_str for keyword in transient_keywords)

    def _trigger_webhook_with_retry(
        self,
        event: Dict[str, Any],
        event_type: str,
        tenant_id: str,
        contract_id: str,
        resource_type: str,
        event_data: Dict[str, Any],
        max_retries: int = 3,
        base_delay: float = 1.0
    ) -> None:
        """
        Trigger webhook delivery with retry logic and DLQ handling.

        Args:
            event: Full event dictionary
            event_type: Event type
            tenant_id: Tenant ID
            contract_id: Contract ID
            resource_type: Resource type
            event_data: Event data
            max_retries: Maximum retry attempts
            base_delay: Base delay in seconds for exponential backoff
        """
        retry_count = 0
        last_error = None

        while retry_count <= max_retries:
            try:
                count = WebhookDeliveryService.trigger_odps_webhook(
                    tenant_id=tenant_id,
                    event_type=event_type,
                    resource_type=resource_type,
                    resource_id=contract_id,
                    event_data=event_data
                )

                # Log success on retry
                if retry_count > 0:
                    logger.info(
                        "odps_webhook_retry_success",
                        event_type=event_type,
                        event_id=event.get("event_id"),
                        contract_id=contract_id,
                        tenant_id=tenant_id,
                        retry_count=retry_count,
                        webhooks_triggered=count
                    )
                else:
                    logger.info(
                        "odps_webhook_triggered_from_event",
                        event_type=event_type,
                        event_id=event.get("event_id"),
                        contract_id=contract_id,
                        tenant_id=tenant_id,
                        webhooks_triggered=count
                    )

                return  # Success

            except Exception as e:
                last_error = e
                is_transient = self._is_transient_failure(e)

                if not is_transient:
                    # Non-transient error - don't retry, send to DLQ
                    logger.error(
                        "odps_webhook_non_transient_error",
                        event_type=event_type,
                        event_id=event.get("event_id"),
                        contract_id=contract_id,
                        tenant_id=tenant_id,
                        error=str(e),
                        error_type=type(e).__name__
                    )
                    self._send_to_dlq(event, str(e), retry_count=retry_count)
                    return

                # Transient error - check if we should retry
                if retry_count >= max_retries:
                    # Max retries exceeded - send to DLQ
                    logger.error(
                        "odps_webhook_retry_exhausted",
                        event_type=event_type,
                        event_id=event.get("event_id"),
                        contract_id=contract_id,
                        tenant_id=tenant_id,
                        retry_count=retry_count,
                        max_retries=max_retries,
                        error=str(e),
                        error_type=type(e).__name__
                    )
                    self._send_to_dlq(event, str(e), retry_count=retry_count)
                    return

                # Retry with exponential backoff
                delay = base_delay * (2 ** retry_count)
                logger.warning(
                    "odps_webhook_retry_attempt",
                    event_type=event_type,
                    event_id=event.get("event_id"),
                    contract_id=contract_id,
                    tenant_id=tenant_id,
                    retry_count=retry_count + 1,
                    max_retries=max_retries,
                    delay=delay,
                    error=str(e),
                    error_type=type(e).__name__
                )
                time.sleep(delay)
                retry_count += 1

        # Should not reach here, but handle just in case
        if last_error:
            self._send_to_dlq(event, str(last_error), retry_count=retry_count)

    def _send_to_dlq(
        self,
        event: Dict[str, Any],
        error_message: str,
        retry_count: int = 0
    ) -> None:
        """
        Send failed event to dead letter queue.

        Args:
            event: Event dictionary
            error_message: Error message
            retry_count: Number of retries attempted
        """
        try:
            event_type = event.get("event_type", "unknown")
            DeadLetterQueue.objects.create(
                event=event,
                event_type=event_type,
                subscriber=self.subscriber_name,
                error_message=error_message,
                error_details={
                    "traceback": traceback.format_exc(),
                    "event_id": event.get("event_id"),
                    "retry_count": retry_count
                },
                retry_count=retry_count
            )
            logger.warning(
                "odps_event_sent_to_dlq",
                event_type=event_type,
                event_id=event.get("event_id"),
                subscriber=self.subscriber_name,
                retry_count=retry_count,
                error_message=error_message
            )
        except Exception as dlq_error:
            # Log but don't raise - DLQ failure shouldn't break event processing
            logger.error(
                "odps_event_dlq_failed",
                event_type=event.get("event_type"),
                event_id=event.get("event_id"),
                subscriber=self.subscriber_name,
                dlq_error=str(dlq_error),
                exc_info=True
            )


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

