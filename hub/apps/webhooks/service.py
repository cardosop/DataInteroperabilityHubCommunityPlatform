"""
Webhook Service

Service for webhook delivery with retry logic and authentication.
"""

from __future__ import annotations

import json
import random
from datetime import timedelta
from typing import Any

import structlog
from django.conf import settings as django_settings
from django.db import transaction
from django.utils import timezone

from hub.apps.contracts.odps_errors import RecoveryStrategy

from .models import (
    DeliveryStatus,
    Webhook,
    WebhookDelivery,
    WebhookEventType,
    WebhookSigningKey,
    WebhookStatus,
)
from .odps_webhook_errors import (
    ODPSWebhookDeliveryError,
    ODPSWebhookError,
    ODPSWebhookPayloadError,
    ODPSWebhookValidationError,
)
from .odps_webhook_validators import validate_odps_webhook_payload
from .metrics import emit_outbound_attempt, observe_signature_duration
from .rate_limit import check_outbound_rate_limit, emit_rate_limit_block_metric
from .service_client import WebhookDeliveryClient
from .ssrf_guard import SSRFViolationError, is_safe_url, validate_webhook_url

logger = structlog.get_logger(__name__)


class WebhookDeliveryService:
    """
    Service for delivering webhooks with retry logic.
    """

    @staticmethod
    def _get_request_timeout() -> int:
        """Return configured webhook delivery timeout.

        Checks WEBHOOK_REQUEST_TIMEOUT first, falls back to legacy
        WEBHOOK_DELIVERY_TIMEOUT for backward compatibility.
        """
        timeout = getattr(django_settings, "WEBHOOK_REQUEST_TIMEOUT", None)
        if timeout is not None:
            return timeout
        return getattr(django_settings, "WEBHOOK_DELIVERY_TIMEOUT", 30)

    @staticmethod
    def _get_retry_intervals() -> list[int]:
        """Return configured webhook retry intervals."""
        return getattr(django_settings, "WEBHOOK_RETRY_INTERVALS", [1, 5, 30, 300, 1800])

    @staticmethod
    def trigger_webhook(
        tenant_id: str,
        event_type: str,
        resource_type: str,
        resource_id: str,
        event_data: dict[str, Any],
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
        # select_related("tenant") avoids N+1 queries when accessing webhook.tenant
        webhooks = Webhook.objects.select_related("tenant").filter(
            tenant_id=tenant_id, status=WebhookStatus.ACTIVE, event_types__contains=event_type
        )

        count = 0
        for webhook in webhooks:
            WebhookDeliveryService._deliver_webhook(
                webhook,
                event_type,
                resource_type,
                resource_id,
                event_data,
            )
            count += 1

        logger.info("webhooks_triggered", tenant_id=tenant_id, event_type=event_type, count=count)

        return count

    @staticmethod
    def _deliver_webhook(
        webhook: Webhook,
        event_type: str,
        resource_type: str,
        resource_id: str,
        event_data: dict[str, Any],
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
            "data": event_data,
        }

        # Promote event_id / id from event_data to top-level
        # ``event_id`` so the idempotency guard
        # (payload__event_id lookup) can match them.  Always
        # normalise to ``event_id`` for query consistency.
        _eid = event_data.get("event_id") or event_data.get("id")
        if _eid:
            payload["event_id"] = _eid

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
                message=f"Failed to serialize webhook payload: {e!s}",
                error_code=ODPSWebhookPayloadError.ERROR_CODE_INVALID_PAYLOAD_STRUCTURE,
                user_message="Webhook payload cannot be serialized to JSON",
                tenant_id=str(webhook.tenant_id),
                webhook_id=str(webhook.id),
                event_type=event_type,
                cause=e,
            )

        # ── Outbound rate limiting (REQ-WH-RL-002) ──────────────────
        # Check tenant's per-minute budget BEFORE creating the delivery row.
        allowed, observed_count, minute_bucket = check_outbound_rate_limit(webhook.tenant)

        if not allowed:
            # Persist the blocked delivery with RATE_LIMITED status so
            # the tenant can see it in their delivery log.  Do NOT
            # dispatch the HTTP request.
            delivery = WebhookDelivery.objects.create(
                webhook=webhook,
                event_type=event_type,
                payload=payload,
                signature="",
                status=DeliveryStatus.RATE_LIMITED,
                attempt_number=0,
                error_message=(
                    f"Rate limit exceeded: {observed_count} requests in "
                    f"minute bucket {minute_bucket} "
                    f"(limit: {webhook.tenant.webhook_outbound_rate_limit_per_minute})"
                )[:500],
            )

            # Emit audit event (REQ-WH-RL-004)
            try:
                from hub.apps.audit.utils import create_audit_event

                create_audit_event(
                    resource_type="WEBHOOK",
                    action="WEBHOOK_RATE_LIMIT_EXCEEDED",
                    tenant=webhook.tenant,
                    resource_id=str(webhook.id),
                    details={
                        "tenant_id": str(webhook.tenant_id),
                        "webhook_id": str(webhook.id),
                        "delivery_id": str(delivery.id),
                        "event_type": event_type,
                        "observed_count": observed_count,
                        "minute_bucket": minute_bucket,
                        "limit": webhook.tenant.webhook_outbound_rate_limit_per_minute,
                    },
                )
            except Exception:
                logger.warning(
                    "webhook_rate_limit_audit_failed",
                    delivery_id=str(delivery.id),
                    exc_info=True,
                )

            # Increment Prometheus counter (REQ-WH-RL-005)
            emit_rate_limit_block_metric(
                tenant_id=str(webhook.tenant_id),
                webhook_id=str(webhook.id),
                event_type=event_type,
            )
            # Emit outbound attempt metric (Phase 233.6)
            emit_outbound_attempt(
                tenant_id=str(webhook.tenant_id),
                webhook_id=str(webhook.id),
                event_type=event_type,
                outcome="rate_limited",
            )

            logger.warning(
                "webhook_rate_limited",
                tenant_id=str(webhook.tenant_id),
                webhook_id=str(webhook.id),
                event_type=event_type,
                observed_count=observed_count,
                minute_bucket=minute_bucket,
            )
            return

        # ── Signing key selection ────────────────────────────────────
        # Prefer the v2 signing key (WebhookSigningKey). Fall back to
        # the legacy webhook.secret column when no active key exists
        # (pre-backfill tenants).
        signing_key = WebhookSigningKey.active_for(webhook)

        # Generate signature
        try:
            if signing_key is not None:
                signature = signing_key.generate_signature(payload_json)
            else:
                signature = webhook.generate_signature(payload_json)
        except Exception as e:
            raise ODPSWebhookError(
                message=f"Failed to generate webhook signature: {e!s}",
                error_code=ODPSWebhookError.ERROR_CODE_WEBHOOK_UNKNOWN,
                user_message="Failed to generate webhook signature",
                tenant_id=str(webhook.tenant_id),
                webhook_id=str(webhook.id),
                event_type=event_type,
                cause=e,
            )

        # ── Idempotency check ────────────────────────────────────────
        # Phase 93.7: skip if this exact event was already successfully
        # delivered to this webhook.
        event_id = payload.get("event_id") or payload.get("id")
        if event_id:
            already_delivered = WebhookDelivery.objects.filter(
                webhook=webhook,
                status=DeliveryStatus.SUCCESS,
                payload__event_id=event_id,
            ).exists()
            if already_delivered:
                logger.info(
                    "webhook_delivery_skipped_duplicate",
                    webhook_id=str(webhook.id),
                    event_id=event_id,
                )
                emit_outbound_attempt(
                    tenant_id=str(webhook.tenant_id),
                    webhook_id=str(webhook.id),
                    event_type=event_type,
                    outcome="duplicate_skipped",
                )
                return

        # ── Create delivery record ───────────────────────────────────
        try:
            delivery = WebhookDelivery.objects.create(
                webhook=webhook,
                event_type=event_type,
                payload=payload,
                signature=signature,
                signing_key_uuid=signing_key.key_id if signing_key else None,
                status=DeliveryStatus.PENDING,
                attempt_number=0,
            )
        except Exception as e:
            raise ODPSWebhookError(
                message=f"Failed to create webhook delivery record: {e!s}",
                error_code=ODPSWebhookError.ERROR_CODE_WEBHOOK_UNKNOWN,
                user_message="Failed to create webhook delivery record",
                tenant_id=str(webhook.tenant_id),
                webhook_id=str(webhook.id),
                event_type=event_type,
                cause=e,
            )

        # Enqueue async delivery via RQ (13.6): decouples HTTP fan-out from
        # the request thread.  In tests WEBHOOK_ASYNC_DELIVERY=False falls
        # back to synchronous _attempt_delivery so existing test fixtures
        # don't need Redis.
        # Wrapped in on_commit so the delivery record is visible to the
        # worker — prevents the task racing a still-uncommitted row.
        from django.conf import settings as _s

        # Emit outbound attempt metric — triggered (Phase 233.6)
        emit_outbound_attempt(
            tenant_id=str(webhook.tenant_id),
            webhook_id=str(webhook.id),
            event_type=event_type,
            outcome="triggered",
        )

        if getattr(_s, "WEBHOOK_ASYNC_DELIVERY", True):
            from hub.apps.webhooks import tasks as _wh_tasks

            _did = str(delivery.id)
            transaction.on_commit(lambda: _wh_tasks.deliver_webhook.delay(_did))
        else:
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
                message=f"Failed to serialize delivery payload: {e!s}",
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
            "User-Agent": f"{getattr(django_settings, 'APP_NAME', 'Meshant').replace(' ', '')}/1.0",
        }

        # Use WebhookDeliveryClient for circuit breaker and retry logic
        webhook_client = WebhookDeliveryClient(
            timeout=WebhookDeliveryService._get_request_timeout()
        )

        # DNS-rebinding re-validation: check URL immediately before delivery so
        # that a hostname that resolved to a public IP at registration time but
        # has since been rebound to a private IP is caught before the request.
        # Runs outside the httpx exception handler so the error is NOT
        # double-wrapped as a generic network error.
        if getattr(django_settings, "WEBHOOK_SSRF_ENABLED", True):
            try:
                validate_webhook_url(webhook.url, raise_as_validation_error=False)
            except SSRFViolationError as ssrf_exc:
                ssrf_error = ODPSWebhookDeliveryError(
                    message=f"SSRF protection blocked delivery: {ssrf_exc}",
                    error_code=ODPSWebhookDeliveryError.ERROR_CODE_NETWORK_ERROR,
                    user_message=(
                        "SSRF protection: webhook URL targets a "
                        "private/reserved address and delivery was blocked."
                    ),
                    tenant_id=str(webhook.tenant_id),
                    webhook_id=str(webhook.id),
                    delivery_id=str(delivery.id),
                    event_type=delivery.event_type,
                    cause=ssrf_exc,
                )
                WebhookDeliveryService._handle_delivery_error(delivery, ssrf_error)
                return

        try:
            # ── Phase 1: initial request without redirect following ──────
            # Use deliver_webhook_with_response to get the full httpx
            # Response (including headers) so we can inspect the Location
            # header on a redirect for SSRF validation.
            initial_response = webhook_client.deliver_webhook_with_response(
                url=webhook.url,
                data=payload_json,
                headers=headers,
            )
            status_code = initial_response.status_code
            response_text = initial_response.text[:1000] if initial_response.text else ""

            # ── Redirect SSRF guard ──────────────────────────────────────
            # An attacker can register a public URL that returns 301/302 to
            # a private address (AWS IMDS, RFC-1918, localhost).  Validate
            # the Location header before following.
            if status_code in (301, 302, 307, 308):
                location = initial_response.headers.get("Location", "")

                if getattr(django_settings, "WEBHOOK_SSRF_ENABLED", True):
                    if location and not is_safe_url(location):
                        ssrf_redirect_error = ODPSWebhookDeliveryError(
                            message=(
                                f"SSRF protection blocked redirect: "
                                f"Location '{location}' targets a "
                                f"private/reserved address."
                            ),
                            error_code=ODPSWebhookDeliveryError.ERROR_CODE_NETWORK_ERROR,
                            user_message=(
                                "SSRF protection: webhook redirect target "
                                "is a private/reserved address and delivery "
                                "was blocked."
                            ),
                            tenant_id=str(webhook.tenant_id),
                            webhook_id=str(webhook.id),
                            delivery_id=str(delivery.id),
                            event_type=delivery.event_type,
                        )
                        WebhookDeliveryService._handle_delivery_error(delivery, ssrf_redirect_error)
                        return

                if location:
                    # Follow the redirect to the validated public URL.
                    status_code, response_text = webhook_client.deliver_webhook(
                        url=location,
                        data=payload_json,
                        headers=headers,
                    )
                # else: no Location header — treat body as final response

            # ── Standard response handling ───────────────────────────────
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
                    status_code=status_code,
                )
                emit_outbound_attempt(
                    tenant_id=str(webhook.tenant_id),
                    webhook_id=str(webhook.id),
                    event_type=delivery.event_type,
                    outcome="delivered_success",
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
                    message=f"Webhook delivery timeout: {e!s}",
                    error_code=ODPSWebhookDeliveryError.ERROR_CODE_TIMEOUT,
                    user_message=f"Webhook delivery to '{webhook.url}' timed out after {WebhookDeliveryService._get_request_timeout()} seconds",
                    tenant_id=str(webhook.tenant_id),
                    webhook_id=str(webhook.id),
                    delivery_id=str(delivery.id),
                    event_type=delivery.event_type,
                    url=webhook.url,
                    cause=e,
                )
            elif isinstance(e, httpx.ConnectError):
                error = ODPSWebhookDeliveryError(
                    message=f"Webhook delivery connection error: {e!s}",
                    error_code=ODPSWebhookDeliveryError.ERROR_CODE_CONNECTION_ERROR,
                    user_message=f"Failed to connect to webhook URL '{webhook.url}': {e!s}",
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
                    message=f"Webhook delivery error: {e!s}",
                    error_code=ODPSWebhookDeliveryError.ERROR_CODE_NETWORK_ERROR,
                    user_message=f"Error when delivering webhook to '{webhook.url}': {e!s}",
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
            emit_outbound_attempt(
                tenant_id=str(delivery.webhook.tenant_id),
                webhook_id=str(delivery.webhook.id),
                event_type=delivery.event_type,
                outcome="delivered_failed",
            )

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
                attempts=delivery.attempt_number,
            )
            emit_outbound_attempt(
                tenant_id=str(webhook.tenant_id),
                webhook_id=str(webhook.id),
                event_type=delivery.event_type,
                outcome="delivered_dead_letter",
            )
            return

        # Calculate next retry time using current attempt_number (before incrementing)
        retry_intervals = webhook.retry_intervals or WebhookDeliveryService._get_retry_intervals()
        attempt_index = min(delivery.attempt_number, len(retry_intervals) - 1)
        base_interval = retry_intervals[attempt_index]

        # Add ±25% jitter to prevent thundering herd
        jittered_interval = base_interval * (0.75 + random.random() * 0.5)

        next_retry_at = timezone.now() + timedelta(seconds=jittered_interval)

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

        if delivery.status == DeliveryStatus.RATE_LIMITED:
            return False  # Rate-limited deliveries are terminal — do not retry

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

        # Get pending deliveries ready for retry (RATE_LIMITED is terminal)
        pending_deliveries = WebhookDelivery.objects.filter(
            status__in=[DeliveryStatus.PENDING, DeliveryStatus.FAILED], next_retry_at__lte=now
        ).exclude(
            status=DeliveryStatus.RATE_LIMITED,
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
        event_data: dict[str, Any],
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
            "data": event_data,
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
            event_data=event_data,
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
                Webhook.objects.filter(tenant_id=tenant_id, status=WebhookStatus.ACTIVE)
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
                event_type, Webhook.objects.filter(tenant_id=tenant_id, status=WebhookStatus.ACTIVE)
            )
        )

    @staticmethod
    def deliver_test_event(webhook: Webhook) -> WebhookDelivery | None:
        """Deliver a synthetic test event to *webhook* (Phase 233.4).

        The test event uses ``event_type="webhook.test"`` and a spec-shaped
        payload so subscribers can verify their endpoint configuration
        without waiting for a real business event.

        Returns the created ``WebhookDelivery``, or ``None`` when the
        webhook is inactive or rate-limited.
        """
        import uuid as _uuid

        test_payload = {
            "event_id": str(_uuid.uuid4()),
            "event": "webhook.test",
            "tenant_id": str(webhook.tenant_id),
            "timestamp": timezone.now().isoformat(),
            "message": "Test webhook delivery",
        }

        WebhookDeliveryService._deliver_webhook(
            webhook=webhook,
            event_type="webhook.test",
            resource_type="WEBHOOK",
            resource_id=str(webhook.id),
            event_data=test_payload,
        )

        # Return the most recent delivery for this webhook + event_type.
        return (
            WebhookDelivery.objects.filter(
                webhook=webhook,
                event_type="webhook.test",
            )
            .order_by("-created_at")
            .first()
        )
