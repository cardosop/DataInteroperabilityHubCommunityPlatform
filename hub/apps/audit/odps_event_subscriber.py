"""
ODPS Event Subscriber for Audit Logging

Subscribes to ODPS events from the event bus and creates audit log entries.
Includes retry logic and dead letter queue handling.
"""

import time
import traceback
from typing import Any

import structlog
from django.contrib.auth import get_user_model

from hub.apps.audit.utils import create_audit_event
from hub.apps.core.events.models import DeadLetterQueue
from hub.apps.core.events.subscriber import EventSubscriber
from hub.apps.tenants.models import Tenant

User = get_user_model()
logger = structlog.get_logger(__name__)


class ODPSAuditSubscriber(EventSubscriber):
    """
    Event subscriber for ODPS events that creates audit log entries.

    Listens to all ODPS events and creates audit log entries for compliance
    and security purposes.
    """

    def __init__(self):
        """Initialize ODPS audit subscriber."""
        super().__init__(subscriber_name="audit_service_odps")
        self._register_handlers()

    def _register_handlers(self):
        """Register handlers for all ODPS event types."""
        # Subscribe to all ODPS events using wildcard pattern
        self.subscribe(event_type_pattern="odps.*", handler=self._handle_odps_event, is_active=True)

        logger.info("odps_audit_subscriber_initialized", subscriber_name=self.subscriber_name)

    def _handle_odps_event(self, event: dict[str, Any]) -> None:
        """
        Handle ODPS event and create audit log entry with retry logic and DLQ handling.

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
                    "odps_audit_missing_tenant_id", event_type=event_type, event_id=event_id
                )
                return

            if not event_type:
                logger.warning("odps_audit_missing_event_type", event_id=event_id)
                return

            # Extract contract ID from event data
            contract_id = event_data.get("contract_id") or event_data.get("odps_contract_id")
            if not contract_id:
                logger.warning(
                    "odps_audit_missing_contract_id",
                    event_type=event_type,
                    event_id=event_id,
                    event_data_keys=list(event_data.keys()),
                )
                return

            # Create audit log entry with retry logic
            self._create_audit_log_with_retry(
                event=event,
                event_type=event_type,
                contract_id=contract_id,
                tenant_id=tenant_id,
                user_id=user_id,
                event_data=event_data,
            )

        except Exception as e:
            logger.error(
                "odps_audit_handler_error",
                event_id=event_id,
                event_type=event_type,
                error=str(e),
                exc_info=True,
            )
            # Send to DLQ after handler-level error
            self._send_to_dlq(event, str(e), retry_count=0)

    def _create_audit_log_with_retry(
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
        Create audit log entry with retry logic and DLQ handling.

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
                # Map event type to audit action
                action = self._map_event_type_to_action(event_type)

                # Get tenant object
                try:
                    tenant = Tenant.objects.get(id=tenant_id)
                except Tenant.DoesNotExist:
                    logger.warning(
                        "odps_audit_tenant_not_found",
                        tenant_id=tenant_id,
                        event_type=event_type,
                        event_id=event.get("event_id"),
                    )
                    return

                # Get user object if user_id provided
                actor_user = None
                if user_id:
                    try:
                        actor_user = User.objects.get(id=user_id)
                    except User.DoesNotExist:
                        logger.warning(
                            "odps_audit_user_not_found",
                            user_id=user_id,
                            event_type=event_type,
                            event_id=event.get("event_id"),
                        )
                        # Continue without user - audit log can still be created

                # Determine result based on event type
                result = "SUCCESS"
                if "failed" in event_type.lower() or "error" in str(event_data).lower():
                    result = "FAILURE"
                elif "warning" in str(event_data).lower():
                    result = "WARNING"

                # Prepare audit details
                audit_details = {
                    "event_id": str(event.get("event_id")),
                    "event_type": event_type,
                    "contract_id": contract_id,
                    "odps_version": event_data.get("odps_version"),
                    "original_format": event_data.get("original_format"),
                }

                # Add event-specific details
                if event_type == "odps.updated":
                    audit_details["changes"] = event_data.get("changes", {})
                    audit_details["previous_status"] = event_data.get("previous_status")
                    audit_details["new_status"] = event_data.get("new_status")
                elif event_type == "odps.normalized":
                    audit_details["normalization_status"] = event_data.get("normalization_status")
                    audit_details["normalization_errors"] = event_data.get("normalization_errors")
                elif event_type in ["odps.linked", "odps.unlinked"]:
                    audit_details["odps_contract_id"] = event_data.get("odps_contract_id")
                    audit_details["odcs_contract_id"] = event_data.get("odcs_contract_id")
                    audit_details["link_type"] = event_data.get("link_type")
                elif event_type.startswith("odps.workflow"):
                    audit_details["workflow_instance_id"] = event_data.get("workflow_instance_id")
                    audit_details["workflow_name"] = event_data.get("workflow_name")
                elif event_type.startswith("odps.export"):
                    audit_details["export_format"] = event_data.get("export_format")
                    audit_details["file_size"] = event_data.get("file_size")
                    audit_details["duration_ms"] = event_data.get("duration_ms")
                elif event_type.startswith("odps.ref"):
                    audit_details["ref_path"] = event_data.get("ref_path")
                    audit_details["ref_type"] = event_data.get("ref_type")
                    audit_details["ref_count"] = event_data.get("ref_count")

                # Create audit event
                audit_event = create_audit_event(
                    resource_type="ODPS_CONTRACT",
                    action=action,
                    actor_user=actor_user,
                    tenant=tenant,
                    resource_id=contract_id,
                    result=result,
                    details=audit_details,
                )

                # Log success on retry
                if retry_count > 0:
                    logger.info(
                        "odps_audit_retry_success",
                        event_type=event_type,
                        event_id=event.get("event_id"),
                        contract_id=contract_id,
                        tenant_id=tenant_id,
                        retry_count=retry_count,
                        audit_event_id=str(audit_event.id),
                    )
                else:
                    logger.info(
                        "odps_audit_log_created",
                        event_type=event_type,
                        event_id=event.get("event_id"),
                        contract_id=contract_id,
                        tenant_id=tenant_id,
                        action=action,
                        result=result,
                        audit_event_id=str(audit_event.id),
                    )

                return  # Success

            except Exception as e:
                last_error = e
                is_transient = self._is_transient_failure(e)

                if not is_transient:
                    # Non-transient error - don't retry, send to DLQ
                    logger.error(
                        "odps_audit_non_transient_error",
                        event_type=event_type,
                        event_id=event.get("event_id"),
                        contract_id=contract_id,
                        tenant_id=tenant_id,
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                    self._send_to_dlq(event, str(e), retry_count=retry_count)
                    return

                # Transient error - check if we should retry
                if retry_count >= max_retries:
                    # Max retries exceeded - send to DLQ
                    logger.error(
                        "odps_audit_retry_exhausted",
                        event_type=event_type,
                        event_id=event.get("event_id"),
                        contract_id=contract_id,
                        tenant_id=tenant_id,
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
                    "odps_audit_retry_attempt",
                    event_type=event_type,
                    event_id=event.get("event_id"),
                    contract_id=contract_id,
                    tenant_id=tenant_id,
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

    def _map_event_type_to_action(self, event_type: str) -> str:
        """
        Map ODPS event type to audit action.

        Args:
            event_type: Event type string

        Returns:
            Audit action string
        """
        # Map common patterns
        if event_type == "odps.created":
            return "ODPS_CREATED"
        elif event_type == "odps.updated":
            return "ODPS_UPDATED"
        elif event_type == "odps.deleted":
            return "ODPS_DELETED"
        elif event_type == "odps.normalized":
            return "ODPS_NORMALIZED"
        elif event_type == "odps.linked":
            return "ODPS_LINKED"
        elif event_type == "odps.unlinked":
            return "ODPS_UNLINKED"
        elif event_type.startswith("odps.workflow"):
            if "completed" in event_type:
                return "ODPS_WORKFLOW_COMPLETED"
            elif "failed" in event_type:
                return "ODPS_WORKFLOW_FAILED"
            else:
                return "ODPS_WORKFLOW_STARTED"
        elif event_type.startswith("odps.export"):
            if "completed" in event_type:
                return "ODPS_EXPORT_COMPLETED"
            elif "failed" in event_type:
                return "ODPS_EXPORT_FAILED"
            else:
                return "ODPS_EXPORT_STARTED"
        elif event_type.startswith("odps.ref"):
            if "resolved" in event_type:
                return "ODPS_REF_RESOLVED"
            elif "failed" in event_type:
                return "ODPS_REF_FAILED"
            else:
                return "ODPS_REF_PROGRESS"
        else:
            # Default: convert event type to action format
            return event_type.replace(".", "_").upper()

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
            "deadlock",
            "serialization",
            "transaction",
        ]

        # Non-retryable error types
        non_retryable_errors = [
            "ValidationError",
            "PermissionDenied",
            "AuthenticationFailed",
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
                "odps_audit_sent_to_dlq",
                event_type=event_type,
                event_id=event.get("event_id"),
                subscriber=self.subscriber_name,
                retry_count=retry_count,
                error_message=error_message,
            )
        except Exception as dlq_error:
            # Log but don't raise - DLQ failure shouldn't break event processing
            logger.error(
                "odps_audit_dlq_failed",
                event_type=event.get("event_type"),
                event_id=event.get("event_id"),
                subscriber=self.subscriber_name,
                dlq_error=str(dlq_error),
                exc_info=True,
            )


# Global subscriber instance
_odps_audit_subscriber: ODPSAuditSubscriber | None = None


def get_odps_audit_subscriber() -> ODPSAuditSubscriber:
    """
    Get or create the global ODPS audit subscriber instance.

    Returns:
        ODPSAuditSubscriber instance
    """
    global _odps_audit_subscriber
    if _odps_audit_subscriber is None:
        _odps_audit_subscriber = ODPSAuditSubscriber()
    return _odps_audit_subscriber


def initialize_odps_audit_subscriber() -> ODPSAuditSubscriber:
    """
    Initialize the ODPS audit subscriber.

    This should be called during application startup to register
    the subscriber with the event bus.

    Returns:
        ODPSAuditSubscriber instance
    """
    subscriber = get_odps_audit_subscriber()
    logger.info("odps_audit_subscriber_initialized", subscriber_name=subscriber.subscriber_name)
    return subscriber
