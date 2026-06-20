"""
ODPS Event Subscriber for Notifications

Subscribes to ODPS events from the event bus and triggers notification emails.
Includes retry logic and dead letter queue handling.
"""

import time
import traceback
from typing import Any

import structlog
from django.contrib.auth import get_user_model

from hub.apps.core.events.models import DeadLetterQueue
from hub.apps.core.events.subscriber import EventSubscriber
from hub.apps.notifications.tasks import (
    send_odps_creation_completion_email,
    send_odps_normalization_failure_email,
)

User = get_user_model()
logger = structlog.get_logger(__name__)


class ODPSNotificationSubscriber(EventSubscriber):
    """
    Event subscriber for ODPS events that triggers notifications.

    Listens to ODPS lifecycle, workflow, and normalization events and sends
    appropriate notification emails to users.
    """

    # ODPS event types that trigger notifications
    LIFECYCLE_EVENTS = ["odps.created", "odps.updated", "odps.deleted"]

    WORKFLOW_EVENTS = ["odps.workflow.started", "odps.workflow.completed", "odps.workflow.failed"]

    NORMALIZATION_EVENTS = [
        "odps.normalized",
        "odps.ref.failed",  # Can indicate normalization issues
    ]

    def __init__(self):
        """Initialize ODPS notification subscriber."""
        super().__init__(subscriber_name="notification_service_odps")
        self._register_handlers()

    def _register_handlers(self):
        """Register handlers for ODPS event types that require notifications."""
        # Subscribe to lifecycle events
        for event_type in self.LIFECYCLE_EVENTS:
            self.subscribe(
                event_type_pattern=event_type, handler=self._handle_odps_event, is_active=True
            )

        # Subscribe to workflow events
        for event_type in self.WORKFLOW_EVENTS:
            self.subscribe(
                event_type_pattern=event_type, handler=self._handle_odps_event, is_active=True
            )

        # Subscribe to normalization events
        for event_type in self.NORMALIZATION_EVENTS:
            self.subscribe(
                event_type_pattern=event_type, handler=self._handle_odps_event, is_active=True
            )

        logger.info(
            "odps_notification_subscriber_initialized",
            lifecycle_events=len(self.LIFECYCLE_EVENTS),
            workflow_events=len(self.WORKFLOW_EVENTS),
            normalization_events=len(self.NORMALIZATION_EVENTS),
        )

    def _handle_odps_event(self, event: dict[str, Any]) -> None:
        """
        Handle ODPS event and trigger notification with retry logic and DLQ handling.

        Args:
            event: Event dictionary from event bus
        """
        event_id = event.get("event_id")
        event_type = event.get("event_type")

        try:
            event_data = event.get("data", {})
            source = event.get("source", {})
            tenant_id = source.get("tenant_id")
            user_id = source.get("user_id")

            if not tenant_id:
                logger.warning(
                    "odps_notification_missing_tenant_id", event_type=event_type, event_id=event_id
                )
                return

            if not event_type:
                logger.warning("odps_notification_missing_event_type", event_id=event_id)
                return

            # Extract contract ID from event data
            contract_id = event_data.get("contract_id") or event_data.get("odps_contract_id")
            if not contract_id:
                logger.warning(
                    "odps_notification_missing_contract_id",
                    event_type=event_type,
                    event_id=event_id,
                    event_data_keys=list(event_data.keys()),
                )
                return

            # Trigger notification with retry logic
            self._send_notification_with_retry(
                event=event,
                event_type=event_type,
                contract_id=contract_id,
                tenant_id=tenant_id,
                user_id=user_id,
                event_data=event_data,
            )

        except Exception as e:
            logger.error(
                "odps_notification_handler_error",
                event_id=event_id,
                event_type=event_type,
                error=str(e),
                exc_info=True,
            )
            # Send to DLQ after handler-level error
            self._send_to_dlq(event, str(e), retry_count=0)

    def _send_notification_with_retry(
        self,
        event: dict[str, Any],
        event_type: str,
        contract_id: str,
        tenant_id: str,
        user_id: str | None,
        event_data: dict[str, Any],
        max_retries: int = 3,
        base_delay: float = 1.0,
    ) -> None:
        """
        Send notification with retry logic and DLQ handling.

        Args:
            event: Full event dictionary
            event_type: Event type
            contract_id: Contract ID
            tenant_id: Tenant ID
            user_id: User ID (optional)
            event_data: Event data
            max_retries: Maximum retry attempts
            base_delay: Base delay in seconds for exponential backoff
        """
        retry_count = 0
        last_error = None

        while retry_count <= max_retries:
            try:
                # Determine notification type based on event type
                if event_type == "odps.created":
                    # Send creation completion notification
                    send_odps_creation_completion_email.delay(contract_id)
                    logger.info(
                        "odps_notification_sent",
                        event_type=event_type,
                        event_id=event.get("event_id"),
                        contract_id=contract_id,
                        notification_type="creation_completion",
                        retry_count=retry_count,
                    )
                    return

                elif event_type == "odps.normalized":
                    # Check normalization status
                    normalization_status = event_data.get("normalization_status")
                    if normalization_status and "FAILED" in str(normalization_status).upper():
                        # Send normalization failure notification
                        error_message = event_data.get("normalization_errors", [])
                        if isinstance(error_message, list):
                            error_message = (
                                "; ".join(error_message)
                                if error_message
                                else "ODPS normalization failed"
                            )
                        else:
                            error_message = (
                                str(error_message) if error_message else "ODPS normalization failed"
                            )

                        send_odps_normalization_failure_email.delay(
                            contract_id=contract_id,
                            error_message=error_message,
                            error_code="ODPS_NORMALIZATION_ERROR",
                            errors=event_data.get("normalization_errors", []),
                            field_path=None,
                        )
                        logger.info(
                            "odps_notification_sent",
                            event_type=event_type,
                            event_id=event.get("event_id"),
                            contract_id=contract_id,
                            notification_type="normalization_failure",
                            retry_count=retry_count,
                        )
                    else:
                        # Normalization succeeded - send completion notification
                        send_odps_creation_completion_email.delay(contract_id)
                        logger.info(
                            "odps_notification_sent",
                            event_type=event_type,
                            event_id=event.get("event_id"),
                            contract_id=contract_id,
                            notification_type="normalization_success",
                            retry_count=retry_count,
                        )
                    return

                elif event_type == "odps.ref.failed":
                    # Reference resolution failure - send notification
                    error_message = event_data.get(
                        "error_message", "ODPS reference resolution failed"
                    )
                    send_odps_normalization_failure_email.delay(
                        contract_id=contract_id,
                        error_message=error_message,
                        error_code=event_data.get("error_code", "ODPS_REF_RESOLUTION_ERROR"),
                        errors=[error_message],
                        field_path=event_data.get("ref_path"),
                    )
                    logger.info(
                        "odps_notification_sent",
                        event_type=event_type,
                        event_id=event.get("event_id"),
                        contract_id=contract_id,
                        notification_type="ref_resolution_failure",
                        retry_count=retry_count,
                    )
                    return

                elif event_type in self.WORKFLOW_EVENTS:
                    # Workflow events - log but don't send email (can be extended later)
                    logger.info(
                        "odps_workflow_event_received",
                        event_type=event_type,
                        event_id=event.get("event_id"),
                        contract_id=contract_id,
                        workflow_instance_id=event_data.get("workflow_instance_id"),
                    )
                    return

                else:
                    # Other lifecycle events - log but don't send email (can be extended later)
                    logger.info(
                        "odps_lifecycle_event_received",
                        event_type=event_type,
                        event_id=event.get("event_id"),
                        contract_id=contract_id,
                    )
                    return

            except Exception as e:
                last_error = e
                is_transient = self._is_transient_failure(e)

                if not is_transient:
                    # Non-transient error - don't retry, send to DLQ
                    logger.error(
                        "odps_notification_non_transient_error",
                        event_type=event_type,
                        event_id=event.get("event_id"),
                        contract_id=contract_id,
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                    self._send_to_dlq(event, str(e), retry_count=retry_count)
                    return

                # Transient error - check if we should retry
                if retry_count >= max_retries:
                    # Max retries exceeded - send to DLQ
                    logger.error(
                        "odps_notification_retry_exhausted",
                        event_type=event_type,
                        event_id=event.get("event_id"),
                        contract_id=contract_id,
                        retry_count=retry_count,
                        max_retries=max_retries,
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                    self._send_to_dlq(event, str(e), retry_count=retry_count)
                    return

                # Retry with exponential backoff
                delay = base_delay * (2**retry_count)
                logger.warning(
                    "odps_notification_retry_attempt",
                    event_type=event_type,
                    event_id=event.get("event_id"),
                    contract_id=contract_id,
                    retry_count=retry_count + 1,
                    max_retries=max_retries,
                    delay=delay,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                time.sleep(delay)
                retry_count += 1

        # Should not reach here, but handle just in case
        if last_error:
            self._send_to_dlq(event, str(last_error), retry_count=retry_count)

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
            "timeout",
            "timed out",
            "connection",
            "unavailable",
            "network",
            "temporary",
            "retry",
            "service unavailable",
            "503",
            "502",
            "504",
            "connection refused",
            "connection reset",
            "broken pipe",
            "connection pool",
            "socket",
            "errno",
            "database",
            "lock",
        ]

        # Non-retryable error types
        non_retryable_errors = [
            "ValidationError",
            "PermissionDenied",
            "AuthenticationFailed",
            "NotFound",
            "ValueError",
            "TypeError",
            "AttributeError",
        ]

        # Don't retry on non-retryable error types
        if any(non_retryable in error_type for non_retryable in non_retryable_errors):
            return False

        # Check for transient keywords in error message
        return any(keyword in error_str for keyword in transient_keywords)

    def _send_to_dlq(self, event: dict[str, Any], error_message: str, retry_count: int = 0) -> None:
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
                    "retry_count": retry_count,
                },
                retry_count=retry_count,
            )
            logger.warning(
                "odps_notification_sent_to_dlq",
                event_type=event_type,
                event_id=event.get("event_id"),
                subscriber=self.subscriber_name,
                retry_count=retry_count,
                error_message=error_message,
            )
        except Exception as dlq_error:
            # Log but don't raise - DLQ failure shouldn't break event processing
            logger.error(
                "odps_notification_dlq_failed",
                event_type=event.get("event_type"),
                event_id=event.get("event_id"),
                subscriber=self.subscriber_name,
                dlq_error=str(dlq_error),
                exc_info=True,
            )


# Global subscriber instance
_odps_notification_subscriber: ODPSNotificationSubscriber | None = None


def get_odps_notification_subscriber() -> ODPSNotificationSubscriber:
    """
    Get or create the global ODPS notification subscriber instance.

    Returns:
        ODPSNotificationSubscriber instance
    """
    global _odps_notification_subscriber
    if _odps_notification_subscriber is None:
        _odps_notification_subscriber = ODPSNotificationSubscriber()
    return _odps_notification_subscriber


def initialize_odps_notification_subscriber() -> ODPSNotificationSubscriber:
    """
    Initialize the ODPS notification subscriber.

    This should be called during application startup to register
    the subscriber with the event bus.

    Returns:
        ODPSNotificationSubscriber instance
    """
    subscriber = get_odps_notification_subscriber()
    logger.info(
        "odps_notification_subscriber_initialized", subscriber_name=subscriber.subscriber_name
    )
    return subscriber
