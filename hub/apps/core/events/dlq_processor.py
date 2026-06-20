"""
Dead Letter Queue Processor

Handles retry logic for events in the dead letter queue with exponential backoff.
"""

import time
from datetime import timedelta
from typing import Any

import structlog
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .bus import EventBusError, get_event_bus
from .metrics import (
    event_dlq_processing_duration_seconds,
    event_dlq_replayed_total,
    get_tenant_id,
)
from .models import DeadLetterQueue

logger = structlog.get_logger(__name__)

# Default retry configuration
DEFAULT_MAX_RETRIES = getattr(settings, "DLQ_MAX_RETRIES", 5)
DEFAULT_BASE_DELAY_SECONDS = getattr(settings, "DLQ_BASE_DELAY_SECONDS", 60)  # 1 minute
DEFAULT_MAX_DELAY_SECONDS = getattr(settings, "DLQ_MAX_DELAY_SECONDS", 3600)  # 1 hour


def calculate_retry_delay(
    retry_count: int, base_delay: float | None = None, max_delay: float | None = None
) -> float:
    """
    Calculate exponential backoff delay for retry.

    Args:
        retry_count: Current retry count (0-indexed)
        base_delay: Base delay in seconds (default: DEFAULT_BASE_DELAY_SECONDS)
        max_delay: Maximum delay in seconds (default: DEFAULT_MAX_DELAY_SECONDS)

    Returns:
        Delay in seconds
    """
    if base_delay is None:
        base_delay = DEFAULT_BASE_DELAY_SECONDS
    if max_delay is None:
        max_delay = DEFAULT_MAX_DELAY_SECONDS

    # Exponential backoff: base_delay * 2^retry_count
    delay = base_delay * (2**retry_count)

    # Cap at max_delay
    return min(delay, max_delay)


def should_retry_dlq_entry(dlq_entry: DeadLetterQueue, max_retries: int | None = None) -> bool:
    """
    Check if a DLQ entry should be retried.

    Args:
        dlq_entry: DeadLetterQueue entry
        max_retries: Maximum retries allowed (default: DEFAULT_MAX_RETRIES)

    Returns:
        True if entry should be retried, False otherwise
    """
    if max_retries is None:
        max_retries = DEFAULT_MAX_RETRIES

    # Don't retry if already resolved
    if dlq_entry.resolved_at is not None:
        return False

    # Don't retry if max retries exceeded
    if dlq_entry.retry_count >= max_retries:
        return False

    # Check if enough time has passed since last attempt (exponential backoff)
    # If last_attempt_at is None, allow retry (first attempt or entry was just created)
    if dlq_entry.last_attempt_at is not None:
        delay = calculate_retry_delay(dlq_entry.retry_count)
        next_retry_time = dlq_entry.last_attempt_at + timedelta(seconds=delay)
        if timezone.now() < next_retry_time:
            return False

    return True


def retry_dlq_entry(
    dlq_entry_id: str, user_id: str | None = None, max_retries: int | None = None
) -> tuple[bool, str | None]:
    """
    Retry processing a DLQ entry by republishing the event.

    Args:
        dlq_entry_id: DeadLetterQueue entry ID
        user_id: Optional user ID who initiated retry
        max_retries: Maximum retries allowed (default: DEFAULT_MAX_RETRIES)

    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    if max_retries is None:
        max_retries = DEFAULT_MAX_RETRIES

    start_time = time.time()

    try:
        with transaction.atomic():
            # Lock the DLQ entry for update
            dlq_entry = DeadLetterQueue.objects.select_for_update().get(id=dlq_entry_id)

            # Check if entry should be retried
            if not should_retry_dlq_entry(dlq_entry, max_retries):
                if dlq_entry.resolved_at:
                    return False, "DLQ entry already resolved"
                if dlq_entry.retry_count >= max_retries:
                    return False, f"Max retries ({max_retries}) exceeded"
                # Check backoff delay
                delay = calculate_retry_delay(dlq_entry.retry_count)
                next_retry_time = dlq_entry.last_attempt_at + timedelta(seconds=delay)
                if timezone.now() < next_retry_time:
                    wait_seconds = (next_retry_time - timezone.now()).total_seconds()
                    return False, f"Retry too soon. Wait {wait_seconds:.0f} seconds"

            # Extract event data
            event_data = dlq_entry.event
            if not isinstance(event_data, dict):
                return False, "Invalid event data format"

            # Get event bus instance
            event_bus = get_event_bus()

            # Extract event fields
            event_type = event_data.get("event_type") or dlq_entry.event_type
            event_data_payload = event_data.get("data", {})
            tenant_id = event_data.get("source", {}).get("tenant_id")
            user_id_from_event = event_data.get("source", {}).get("user_id")
            request_id = event_data.get("source", {}).get("request_id")
            correlation_id = event_data.get("metadata", {}).get("correlation_id")
            causation_id = event_data.get("metadata", {}).get("causation_id")
            tags = event_data.get("metadata", {}).get("tags", [])
            event_version = event_data.get("event_version", "1.0.0")

            # Republish event
            try:
                event_bus.publish(
                    event_type=event_type,
                    data=event_data_payload,
                    tenant_id=tenant_id,
                    user_id=user_id_from_event,
                    request_id=request_id,
                    correlation_id=correlation_id,
                    causation_id=causation_id,
                    tags=tags,
                    event_version=event_version,
                )

                # Update DLQ entry
                dlq_entry.retry_count += 1
                dlq_entry.last_attempt_at = timezone.now()
                if user_id:
                    dlq_entry.resolved_by = user_id
                dlq_entry.save(update_fields=["retry_count", "last_attempt_at", "resolved_by"])

                # Record metrics
                tenant_label = get_tenant_id(tenant_id)
                event_dlq_replayed_total.labels(
                    event_type=event_type,
                    subscriber_name=dlq_entry.subscriber,
                    status="success",
                    tenant_id=tenant_label,
                ).inc()

                processing_duration = time.time() - start_time
                event_dlq_processing_duration_seconds.labels(
                    event_type=event_type,
                    subscriber_name=dlq_entry.subscriber,
                    tenant_id=tenant_label,
                ).observe(processing_duration)

                logger.info(
                    "dlq_entry_retried",
                    dlq_entry_id=str(dlq_entry_id),
                    event_type=event_type,
                    subscriber=dlq_entry.subscriber,
                    retry_count=dlq_entry.retry_count,
                    tenant_id=tenant_id,
                )

                return True, None

            except EventBusError as e:
                error_msg = f"Failed to republish event: {e!s}"
                logger.error(
                    "dlq_entry_retry_failed",
                    dlq_entry_id=str(dlq_entry_id),
                    event_type=event_type,
                    subscriber=dlq_entry.subscriber,
                    error=str(e),
                    exc_info=True,
                )

                # Update DLQ entry with failure
                dlq_entry.retry_count += 1
                dlq_entry.last_attempt_at = timezone.now()
                dlq_entry.error_message = error_msg
                if user_id:
                    dlq_entry.resolved_by = user_id
                dlq_entry.save(
                    update_fields=["retry_count", "last_attempt_at", "error_message", "resolved_by"]
                )

                # Record metrics
                tenant_label = get_tenant_id(tenant_id)
                event_dlq_replayed_total.labels(
                    event_type=event_type,
                    subscriber_name=dlq_entry.subscriber,
                    status="failed",
                    tenant_id=tenant_label,
                ).inc()

                processing_duration = time.time() - start_time
                event_dlq_processing_duration_seconds.labels(
                    event_type=event_type,
                    subscriber_name=dlq_entry.subscriber,
                    tenant_id=tenant_label,
                ).observe(processing_duration)

                return False, error_msg

    except DeadLetterQueue.DoesNotExist:
        return False, "DLQ entry not found"
    except Exception as e:
        logger.error(
            "dlq_entry_retry_error", dlq_entry_id=str(dlq_entry_id), error=str(e), exc_info=True
        )
        return False, f"Unexpected error: {e!s}"


def resolve_dlq_entry(
    dlq_entry_id: str, user_id: str | None = None, resolution_notes: str | None = None
) -> tuple[bool, str | None]:
    """
    Resolve a DLQ entry (mark as resolved without retrying).

    Args:
        dlq_entry_id: DeadLetterQueue entry ID
        user_id: Optional user ID who resolved the entry
        resolution_notes: Optional notes about resolution

    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    try:
        with transaction.atomic():
            dlq_entry = DeadLetterQueue.objects.select_for_update().get(id=dlq_entry_id)

            if dlq_entry.resolved_at:
                return False, "DLQ entry already resolved"

            # Mark as resolved
            dlq_entry.resolved_at = timezone.now()
            if user_id:
                dlq_entry.resolved_by = user_id
            if resolution_notes:
                # Store resolution notes in error_details
                if not dlq_entry.error_details:
                    dlq_entry.error_details = {}
                dlq_entry.error_details["resolution_notes"] = resolution_notes
            dlq_entry.save(update_fields=["resolved_at", "resolved_by", "error_details"])

            logger.info(
                "dlq_entry_resolved",
                dlq_entry_id=str(dlq_entry_id),
                event_type=dlq_entry.event_type,
                subscriber=dlq_entry.subscriber,
                user_id=user_id,
            )

            return True, None

    except DeadLetterQueue.DoesNotExist:
        return False, "DLQ entry not found"
    except Exception as e:
        logger.error(
            "dlq_entry_resolve_error", dlq_entry_id=str(dlq_entry_id), error=str(e), exc_info=True
        )
        return False, f"Unexpected error: {e!s}"


def process_dlq_entries(
    event_type: str | None = None,
    subscriber: str | None = None,
    max_entries: int = 100,
    max_retries: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Process multiple DLQ entries automatically.

    Args:
        event_type: Optional event type filter
        subscriber: Optional subscriber filter
        max_entries: Maximum number of entries to process
        max_retries: Maximum retries allowed (default: DEFAULT_MAX_RETRIES)
        dry_run: If True, only report what would be done without actually retrying

    Returns:
        Dictionary with processing results
    """
    if max_retries is None:
        max_retries = DEFAULT_MAX_RETRIES

    # Build query
    queryset = DeadLetterQueue.objects.filter(resolved_at__isnull=True)

    if event_type:
        queryset = queryset.filter(event_type=event_type)

    if subscriber:
        queryset = queryset.filter(subscriber=subscriber)

    # Order by oldest first (oldest failures should be retried first)
    queryset = queryset.order_by("created_at")

    # Get entries to process
    entries = list(queryset[:max_entries])

    results = {
        "total_found": len(entries),
        "processed": 0,
        "succeeded": 0,
        "failed": 0,
        "skipped": 0,
        "errors": [],
    }

    for entry in entries:
        if not should_retry_dlq_entry(entry, max_retries):
            results["skipped"] += 1
            continue

        if dry_run:
            results["processed"] += 1
            logger.debug(
                "dlq_entry_dry_run",
                dlq_entry_id=str(entry.id),
                event_type=entry.event_type,
                subscriber=entry.subscriber,
            )
            continue

        # Retry entry
        success, error_msg = retry_dlq_entry(str(entry.id), max_retries=max_retries)

        results["processed"] += 1
        if success:
            results["succeeded"] += 1
        else:
            results["failed"] += 1
            if error_msg:
                results["errors"].append({"dlq_entry_id": str(entry.id), "error": error_msg})

    logger.info(
        "dlq_entries_processed",
        total_found=results["total_found"],
        processed=results["processed"],
        succeeded=results["succeeded"],
        failed=results["failed"],
        skipped=results["skipped"],
        dry_run=dry_run,
    )

    return results
