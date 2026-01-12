"""
Webhook Service

Service for webhook delivery with retry logic and authentication.
"""
from __future__ import annotations

import json
import hmac
import hashlib
from typing import Any, Dict, Optional
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
import structlog

from .models import Webhook, WebhookDelivery, WebhookStatus, DeliveryStatus, WebhookEventType
from .service_client import WebhookDeliveryClient
from .odps_webhook_errors import (
    ODPSWebhookError,
    ODPSWebhookDeliveryError,
    ODPSWebhookValidationError,
    ODPSWebhookPayloadError,
)
from .odps_webhook_validators import validate_odps_webhook_payload
from .transformation_webhook_validators import validate_transformation_webhook_payload
from hub.apps.contracts.odps_errors import RecoveryStrategy

logger = structlog.get_logger(__name__)


class WebhookDeliveryService:
    """
    Service for delivering webhooks with retry logic.
    """

    DEFAULT_RETRY_INTERVALS = [1, 5, 30, 300, 1800]  # 1s, 5s, 30s, 5m, 30m
    REQUEST_TIMEOUT = 30  # seconds

    @staticmethod
    def trigger_webhook(
        tenant_id: str,
        event_type: str,
        resource_type: str,
        resource_id: str,
        event_data: Dict[str, Any]
    ) -> int:
        """
        Trigger webhook delivery for matching subscriptions.

        Args:
            tenant_id: Tenant UUID
            event_type: Event type (e.g., "contract.created")
            resource_type: Resource type (e.g., "CONTRACT", "ASSET")
            resource_id: Resource UUID
            event_data: Event data payload

        Returns:
            Number of webhooks triggered
        """
        # Find active webhooks for this event type
        # For JSONField arrays, __contains checks if the array contains the value (not a list)
        webhooks = Webhook.objects.filter(
            tenant_id=tenant_id,
            status=WebhookStatus.ACTIVE,
            event_types__contains=event_type
        )

        count = 0
        for webhook in webhooks:
            WebhookDeliveryService._deliver_webhook(
                webhook,
                event_type,
                resource_type,
                resource_id,
                event_data
            )
            count += 1

        logger.info(
            "webhooks_triggered",
            tenant_id=tenant_id,
            event_type=event_type,
            count=count
        )

        return count

    @staticmethod
    def _deliver_webhook(
        webhook: Webhook,
        event_type: str,
        resource_type: str,
        resource_id: str,
        event_data: Dict[str, Any]
    ):
        """
        Create and deliver a webhook with validation and error handling.

        Args:
            webhook: Webhook subscription
            event_type: Event type
            resource_type: Resource type
            resource_id: Resource ID
            event_data: Event data payload

        Raises:
            ODPSWebhookPayloadError: If payload validation fails
            ODPSWebhookValidationError: If webhook validation fails
        """
        # Validate webhook is active
        if webhook.status != WebhookStatus.ACTIVE:
            raise ODPSWebhookValidationError(
                message=f"Webhook {webhook.id} is not active (status: {webhook.status})",
                error_code=ODPSWebhookValidationError.ERROR_CODE_WEBHOOK_INACTIVE,
                user_message=f"Webhook '{webhook.name}' is not active and cannot receive deliveries",
                tenant_id=str(webhook.tenant_id),
                webhook_id=str(webhook.id),
                event_type=event_type,
            )

        # Validate event type is subscribed
        if not webhook.subscribes_to_event_type(event_type):
            raise ODPSWebhookValidationError(
                message=f"Webhook {webhook.id} does not subscribe to event type {event_type}",
                error_code=ODPSWebhookValidationError.ERROR_CODE_INVALID_EVENT_TYPE,
                user_message=f"Webhook '{webhook.name}' does not subscribe to event type '{event_type}'",
                tenant_id=str(webhook.tenant_id),
                webhook_id=str(webhook.id),
                event_type=event_type,
            )

        # Build payload
        payload = {
            "event_type": event_type,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "timestamp": timezone.now().isoformat(),
            "data": event_data
        }

        # Validate payload for ODPS events
        if WebhookEventType.is_odps_event_type(event_type):
            try:
                validate_odps_webhook_payload(
                    payload=payload,
                    event_type=event_type,
                    tenant_id=str(webhook.tenant_id),
                    webhook_id=str(webhook.id),
                )
            except ODPSWebhookPayloadError as e:
                # Log validation error
                logger.error(
                    "odps_webhook_payload_validation_failed",
                    webhook_id=str(webhook.id),
                    event_type=event_type,
                    error_code=e.error_code,
                    error_message=e.message,
                )
                raise

        # Validate payload for transformation events
        if WebhookEventType.is_transformation_event_type(event_type):
            try:
                validate_transformation_webhook_payload(
                    payload=payload,
                    event_type=event_type,
                    tenant_id=str(webhook.tenant_id),
                    webhook_id=str(webhook.id),
                )
            except ODPSWebhookPayloadError as e:
                # Log validation error
                logger.error(
                    "transformation_webhook_payload_validation_failed",
                    webhook_id=str(webhook.id),
                    event_type=event_type,
                    error_code=e.error_code,
                    error_message=e.message,
                )
                raise

        # Validate payload for virtualization events
        # Note: Virtualization events use the same payload structure as other events
        # No special validation needed beyond standard webhook payload validation
        if WebhookEventType.is_virtualization_event_type(event_type):
            # Virtualization events follow standard webhook payload structure
            # Additional validation can be added here if needed in the future
            pass

        try:
            payload_json = json.dumps(payload, sort_keys=True)
        except (TypeError, ValueError) as e:
            raise ODPSWebhookPayloadError(
                message=f"Failed to serialize webhook payload: {str(e)}",
                error_code=ODPSWebhookPayloadError.ERROR_CODE_INVALID_PAYLOAD_STRUCTURE,
                user_message="Webhook payload cannot be serialized to JSON",
                tenant_id=str(webhook.tenant_id),
                webhook_id=str(webhook.id),
                event_type=event_type,
                cause=e,
            )

        # Generate signature
        try:
            signature = webhook.generate_signature(payload_json)
        except Exception as e:
            raise ODPSWebhookError(
                message=f"Failed to generate webhook signature: {str(e)}",
                error_code=ODPSWebhookError.ERROR_CODE_WEBHOOK_UNKNOWN,
                user_message="Failed to generate webhook signature",
                tenant_id=str(webhook.tenant_id),
                webhook_id=str(webhook.id),
                event_type=event_type,
                cause=e,
            )

        # Create delivery record
        try:
            delivery = WebhookDelivery.objects.create(
                webhook=webhook,
                event_type=event_type,
                payload=payload,
                signature=signature,
                status=DeliveryStatus.PENDING,
                attempt_number=0
            )
        except Exception as e:
            raise ODPSWebhookError(
                message=f"Failed to create webhook delivery record: {str(e)}",
                error_code=ODPSWebhookError.ERROR_CODE_WEBHOOK_UNKNOWN,
                user_message="Failed to create webhook delivery record",
                tenant_id=str(webhook.tenant_id),
                webhook_id=str(webhook.id),
                event_type=event_type,
                cause=e,
            )

        # Schedule delivery (async via job queue in production)
        WebhookDeliveryService._attempt_delivery(delivery)

    @staticmethod
    def _attempt_delivery(delivery: WebhookDelivery):
        """
        Attempt to deliver a webhook with comprehensive error handling.

        Handles various error scenarios:
        - Network errors (connection, timeout, SSL)
        - HTTP errors (4xx, 5xx)
        - Rate limiting
        - Invalid responses

        Args:
            delivery: Webhook delivery record
        """
        webhook = delivery.webhook

        # Check if webhook is still active
        if webhook.status != WebhookStatus.ACTIVE:
            error_msg = f"Webhook is {webhook.status}"
            delivery.status = DeliveryStatus.FAILED
            delivery.error_message = error_msg
            delivery.save()

            logger.warning(
                "webhook_delivery_skipped_inactive",
                delivery_id=str(delivery.id),
                webhook_id=str(webhook.id),
                status=webhook.status,
            )
            return

        # Build payload JSON
        try:
            payload_json = json.dumps(delivery.payload, sort_keys=True)
        except (TypeError, ValueError) as e:
            error = ODPSWebhookPayloadError(
                message=f"Failed to serialize delivery payload: {str(e)}",
                error_code=ODPSWebhookPayloadError.ERROR_CODE_INVALID_PAYLOAD_STRUCTURE,
                user_message="Failed to serialize webhook payload for delivery",
                tenant_id=str(webhook.tenant_id),
                webhook_id=str(webhook.id),
                delivery_id=str(delivery.id),
                event_type=delivery.event_type,
                cause=e,
            )
            WebhookDeliveryService._handle_delivery_error(delivery, error)
            return

        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": delivery.signature,
            "X-Webhook-Event-Type": delivery.event_type,
            "User-Agent": "DataInteroperabilityHub/1.0"
        }

        # Use WebhookDeliveryClient for circuit breaker and retry logic
        webhook_client = WebhookDeliveryClient(timeout=WebhookDeliveryService.REQUEST_TIMEOUT)

        try:
            # Make HTTP request using service client
            status_code, response_text = webhook_client.deliver_webhook(
                url=webhook.url,
                data=payload_json,
                headers=headers
            )

            # Update delivery record
            delivery.http_status_code = status_code
            delivery.response_body = response_text

            if 200 <= status_code < 300:
                # Success
                delivery.status = DeliveryStatus.SUCCESS
                delivery.delivered_at = timezone.now()
                delivery.next_retry_at = None
                delivery.error_message = None
                delivery.save()

                logger.info(
                    "webhook_delivered",
                    delivery_id=str(delivery.id),
                    webhook_id=str(webhook.id),
                    event_type=delivery.event_type,
                    status_code=status_code
                )
            else:
                # HTTP error - create structured error
                error = WebhookDeliveryService._create_http_error(
                    delivery=delivery,
                    status_code=status_code,
                    response_body=response_text,
                )
                WebhookDeliveryService._handle_delivery_error(delivery, error)

        except Exception as e:
            # Handle various error types from httpx
            import httpx

            if isinstance(e, httpx.TimeoutException):
                error = ODPSWebhookDeliveryError(
                    message=f"Webhook delivery timeout: {str(e)}",
                    error_code=ODPSWebhookDeliveryError.ERROR_CODE_TIMEOUT,
                    user_message=f"Webhook delivery to '{webhook.url}' timed out after {WebhookDeliveryService.REQUEST_TIMEOUT} seconds",
                    tenant_id=str(webhook.tenant_id),
                    webhook_id=str(webhook.id),
                    delivery_id=str(delivery.id),
                    event_type=delivery.event_type,
                    url=webhook.url,
                    cause=e,
                )
            elif isinstance(e, httpx.ConnectError):
                error = ODPSWebhookDeliveryError(
                    message=f"Webhook delivery connection error: {str(e)}",
                    error_code=ODPSWebhookDeliveryError.ERROR_CODE_CONNECTION_ERROR,
                    user_message=f"Failed to connect to webhook URL '{webhook.url}': {str(e)}",
                    tenant_id=str(webhook.tenant_id),
                    webhook_id=str(webhook.id),
                    delivery_id=str(delivery.id),
                    event_type=delivery.event_type,
                    url=webhook.url,
                    cause=e,
                )
            elif isinstance(e, httpx.HTTPStatusError):
                # HTTP error - already handled above, but catch here for safety
                error = WebhookDeliveryService._create_http_error(
                    delivery=delivery,
                    status_code=e.response.status_code if e.response else 0,
                    response_body=e.response.text[:1000] if e.response else "",
                )
            else:
                # Generic network error or unexpected error
                error = ODPSWebhookDeliveryError(
                    message=f"Webhook delivery error: {str(e)}",
                    error_code=ODPSWebhookDeliveryError.ERROR_CODE_NETWORK_ERROR,
                    user_message=f"Error when delivering webhook to '{webhook.url}': {str(e)}",
                    tenant_id=str(webhook.tenant_id),
                    webhook_id=str(webhook.id),
                    delivery_id=str(delivery.id),
                    event_type=delivery.event_type,
                    url=webhook.url,
                    cause=e,
                )

            WebhookDeliveryService._handle_delivery_error(delivery, error)

    @staticmethod
    def _create_http_error(
        delivery: WebhookDelivery,
        status_code: int,
        response_body: str,
    ) -> ODPSWebhookDeliveryError:
        """
        Create a structured HTTP error for webhook delivery.

        Args:
            delivery: Webhook delivery record
            status_code: HTTP status code
            response_body: Response body

        Returns:
            ODPSWebhookDeliveryError with appropriate error code
        """
        webhook = delivery.webhook

        # Initialize retry_after
        retry_after = None

        # Determine error code based on status code
        if status_code == 429:
            error_code = ODPSWebhookDeliveryError.ERROR_CODE_RATE_LIMITED
            user_message = f"Webhook delivery rate limited (HTTP {status_code})"
            # Try to extract Retry-After header if available (could be enhanced to parse response headers)
        elif 400 <= status_code < 500:
            if status_code == 401:
                error_code = ODPSWebhookDeliveryError.ERROR_CODE_AUTHENTICATION_FAILED
                user_message = f"Webhook authentication failed (HTTP {status_code})"
            else:
                error_code = ODPSWebhookDeliveryError.ERROR_CODE_HTTP_ERROR
                user_message = f"Webhook delivery failed with client error (HTTP {status_code})"
        elif 500 <= status_code < 600:
            error_code = ODPSWebhookDeliveryError.ERROR_CODE_HTTP_ERROR
            user_message = f"Webhook delivery failed with server error (HTTP {status_code})"
        else:
            error_code = ODPSWebhookDeliveryError.ERROR_CODE_INVALID_RESPONSE
            user_message = f"Webhook delivery received unexpected response (HTTP {status_code})"

        return ODPSWebhookDeliveryError(
            message=f"Webhook delivery failed with HTTP {status_code}",
            error_code=error_code,
            user_message=user_message,
            http_status_code=status_code,
            response_body=response_body,
            url=webhook.url,
            tenant_id=str(webhook.tenant_id),
            webhook_id=str(webhook.id),
            delivery_id=str(delivery.id),
            event_type=delivery.event_type,
            retry_after=retry_after,
        )

    @staticmethod
    def _handle_delivery_error(
        delivery: WebhookDelivery,
        error: ODPSWebhookError,
    ):
        """
        Handle a webhook delivery error by updating the delivery record
        and scheduling retry if applicable.

        Args:
            delivery: Webhook delivery record
            error: ODPS webhook error
        """
        # Update delivery record with error information
        delivery.error_message = error.user_message[:500]  # Limit error message size

        # Handle delivery-specific error attributes
        if isinstance(error, ODPSWebhookDeliveryError):
            delivery.http_status_code = error.http_status_code
            if error.response_body:
                delivery.response_body = error.response_body[:1000]  # Limit response body size
        else:
            delivery.http_status_code = None

        delivery.save()

        # Log error with structured context
        log_level = "error" if not error.recoverable else "warning"
        log_data = {
            "delivery_id": str(delivery.id),
            "webhook_id": str(delivery.webhook.id),
            "event_type": delivery.event_type,
            "error_code": error.error_code,
            "error_message": error.message,
            "recoverable": error.recoverable,
            "recovery_strategy": error.recovery_strategy.value if error.recovery_strategy else None,
        }

        # Add delivery-specific context
        if isinstance(error, ODPSWebhookDeliveryError):
            if error.http_status_code:
                log_data["http_status_code"] = error.http_status_code
            if error.url:
                log_data["url"] = error.url

        getattr(logger, log_level)(
            "odps_webhook_delivery_error",
            **log_data,
        )

        # Schedule retry if error is recoverable
        if error.recoverable and error.recovery_strategy == RecoveryStrategy.RETRY:
            WebhookDeliveryService._schedule_retry(delivery)
        else:
            # Non-recoverable error - mark as failed
            delivery.status = DeliveryStatus.FAILED
            delivery.save()

    @staticmethod
    def _schedule_retry(delivery: WebhookDelivery):
        """Schedule a retry for failed delivery"""
        webhook = delivery.webhook

        # Check if max retries exceeded
        if delivery.attempt_number >= webhook.max_retries:
            delivery.status = DeliveryStatus.DEAD_LETTER
            delivery.next_retry_at = None
            delivery.save()

            logger.warning(
                "webhook_dead_letter",
                delivery_id=str(delivery.id),
                webhook_id=str(webhook.id),
                attempts=delivery.attempt_number
            )
            return

        # Calculate next retry time using current attempt_number (before incrementing)
        retry_intervals = webhook.retry_intervals or WebhookDeliveryService.DEFAULT_RETRY_INTERVALS
        attempt_index = min(delivery.attempt_number, len(retry_intervals) - 1)
        retry_interval = retry_intervals[attempt_index]

        next_retry_at = timezone.now() + timedelta(seconds=retry_interval)

        # Update delivery (increment attempt_number after calculating interval)
        delivery.status = DeliveryStatus.FAILED
        delivery.attempt_number += 1
        delivery.next_retry_at = next_retry_at
        delivery.save()

    @staticmethod
    def retry_delivery(delivery_id: str) -> bool:
        """
        Manually retry a failed delivery.

        Args:
            delivery_id: Delivery UUID

        Returns:
            True if retry was scheduled, False otherwise
        """
        try:
            delivery = WebhookDelivery.objects.get(id=delivery_id)
        except WebhookDelivery.DoesNotExist:
            return False

        if delivery.status == DeliveryStatus.SUCCESS:
            return False  # Already succeeded

        if delivery.status == DeliveryStatus.DEAD_LETTER:
            # Reset for retry
            delivery.status = DeliveryStatus.PENDING
            delivery.attempt_number = 0
            delivery.next_retry_at = None
            delivery.save()

        WebhookDeliveryService._attempt_delivery(delivery)
        return True

    @staticmethod
    def process_pending_deliveries(limit: int = 100) -> int:
        """
        Process pending webhook deliveries.

        Args:
            limit: Maximum number of deliveries to process

        Returns:
            Number of deliveries processed
        """
        now = timezone.now()

        # Get pending deliveries ready for retry
        pending_deliveries = WebhookDelivery.objects.filter(
            status__in=[DeliveryStatus.PENDING, DeliveryStatus.FAILED],
            next_retry_at__lte=now
        )[:limit]

        count = 0
        for delivery in pending_deliveries:
            WebhookDeliveryService._attempt_delivery(delivery)
            count += 1

        return count

    @staticmethod
    def trigger_odps_webhook(
        tenant_id: str,
        event_type: str,
        resource_type: str,
        resource_id: str,
        event_data: Dict[str, Any]
    ) -> int:
        """
        Trigger webhook delivery for ODPS events with validation and error handling.

        This is a convenience method that validates the event type is an ODPS event
        and validates the payload before triggering webhook delivery.

        Args:
            tenant_id: Tenant UUID
            event_type: ODPS event type (e.g., "odps.created" or WebhookEventType enum value)
            resource_type: Resource type (e.g., "ODPS", "CONTRACT")
            resource_id: Resource UUID
            event_data: Event data payload

        Returns:
            Number of webhooks triggered

        Raises:
            ODPSWebhookValidationError: If event_type is not an ODPS event type
            ODPSWebhookPayloadError: If payload validation fails
        """
        # Extract string value if event_type is a tuple (enum value)
        if isinstance(event_type, (tuple, list)) and len(event_type) > 0:
            event_type = event_type[0]

        if not WebhookEventType.is_odps_event_type(event_type):
            raise ODPSWebhookValidationError(
                message=f"Event type '{event_type}' is not an ODPS event type",
                error_code=ODPSWebhookValidationError.ERROR_CODE_INVALID_EVENT_TYPE,
                user_message=f"Invalid event type: '{event_type}' is not a valid ODPS event type",
                tenant_id=tenant_id,
                event_type=event_type,
            )

        # Validate payload before triggering
        payload = {
            "event_type": event_type,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "timestamp": timezone.now().isoformat(),
            "data": event_data
        }

        try:
            validate_odps_webhook_payload(
                payload=payload,
                event_type=event_type,
                tenant_id=tenant_id,
            )
        except ODPSWebhookPayloadError as e:
            logger.error(
                "odps_webhook_payload_validation_failed",
                tenant_id=tenant_id,
                event_type=event_type,
                error_code=e.error_code,
                error_message=e.message,
            )
            raise

        return WebhookDeliveryService.trigger_webhook(
            tenant_id=tenant_id,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=resource_id,
            event_data=event_data
        )

    @staticmethod
    def get_webhooks_for_odps_events(tenant_id: str) -> list[Webhook]:
        """
        Get all active webhooks for a tenant that subscribe to ODPS events.

        Args:
            tenant_id: Tenant UUID

        Returns:
            List of webhooks that subscribe to at least one ODPS event
        """
        return list(
            Webhook.filter_by_odps_events(
                Webhook.objects.filter(
                    tenant_id=tenant_id,
                    status=WebhookStatus.ACTIVE
                )
            )
        )

    @staticmethod
    def get_webhooks_for_event_type(tenant_id: str, event_type: str) -> list[Webhook]:
        """
        Get all active webhooks for a tenant that subscribe to a specific event type.

        Args:
            tenant_id: Tenant UUID
            event_type: Event type string

        Returns:
            List of webhooks that subscribe to the specified event type
        """
        return list(
            Webhook.filter_by_event_type(
                event_type,
                Webhook.objects.filter(
                    tenant_id=tenant_id,
                    status=WebhookStatus.ACTIVE
                )
            )
        )

    @staticmethod
    def trigger_transformation_webhook(
        tenant_id: str,
        event_type: str,
        resource_type: str,
        resource_id: str,
        event_data: Dict[str, Any]
    ) -> int:
        """
        Trigger webhook delivery for transformation events with validation and error handling.

        This is a convenience method that validates the event type is a transformation event
        and validates the payload before triggering webhook delivery.

        Args:
            tenant_id: Tenant UUID
            event_type: Transformation event type (e.g., "pipeline.created" or WebhookEventType enum value)
            resource_type: Resource type (e.g., "PIPELINE", "EXECUTION")
            resource_id: Resource UUID
            event_data: Event data payload

        Returns:
            Number of webhooks triggered

        Raises:
            ODPSWebhookValidationError: If event_type is not a transformation event type
            ODPSWebhookPayloadError: If payload validation fails
        """
        # Extract string value if event_type is a tuple (enum value)
        if isinstance(event_type, (tuple, list)) and len(event_type) > 0:
            event_type = event_type[0]

        if not WebhookEventType.is_transformation_event_type(event_type):
            raise ODPSWebhookValidationError(
                message=f"Event type '{event_type}' is not a transformation event type",
                error_code=ODPSWebhookValidationError.ERROR_CODE_INVALID_EVENT_TYPE,
                user_message=f"Invalid event type: '{event_type}' is not a valid transformation event type",
                tenant_id=tenant_id,
                event_type=event_type,
            )

        # Validate payload before triggering
        payload = {
            "event_type": event_type,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "timestamp": timezone.now().isoformat(),
            "data": event_data
        }

        try:
            validate_transformation_webhook_payload(
                payload=payload,
                event_type=event_type,
                tenant_id=tenant_id,
            )
        except ODPSWebhookPayloadError as e:
            logger.error(
                "transformation_webhook_payload_validation_failed",
                tenant_id=tenant_id,
                event_type=event_type,
                error_code=e.error_code,
                error_message=e.message,
            )
            raise

        return WebhookDeliveryService.trigger_webhook(
            tenant_id=tenant_id,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=resource_id,
            event_data=event_data
        )

