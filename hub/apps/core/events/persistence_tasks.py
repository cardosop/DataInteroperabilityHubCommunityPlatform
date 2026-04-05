"""
Event Persistence Tasks

Background tasks for async event persistence to PostgreSQL.

Uses django-rq for async job processing to avoid blocking event publishing.
Includes retry logic, consistency validation, and write-behind pattern support.
"""
import json
import time
import structlog
from django_rq import job
from django.db import transaction
from django.utils import timezone
from datetime import datetime
from typing import Dict, Any, List, Optional

from .models import Event
from .metrics import (
    event_persistence_duration_seconds,
    get_tenant_id,
)

logger = structlog.get_logger(__name__)

# Configuration defaults
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY_SECONDS = 1.0
DEFAULT_RETRY_BACKOFF_FACTOR = 2.0


@job('job_default', timeout=30)
def persist_event_async(
    event_data: Dict[str, Any],
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_delay_seconds: float = DEFAULT_RETRY_DELAY_SECONDS,
    retry_backoff_factor: float = DEFAULT_RETRY_BACKOFF_FACTOR
) -> str:
    """
    Persist event to PostgreSQL asynchronously with retry logic.

    Args:
        event_data: Event dictionary with all fields
        max_retries: Maximum number of retry attempts
        retry_delay_seconds: Initial delay between retries
        retry_backoff_factor: Multiplier for exponential backoff

    Returns:
        Event ID (UUID string)

    Raises:
        Exception: If persistence fails after all retries
    """
    start_time = timezone.now().timestamp()
    event_id = event_data.get("event_id")
    event_type = event_data.get("event_type", "unknown")
    tenant_id = event_data.get("source", {}).get("tenant_id")
    tenant_label = get_tenant_id(tenant_id)
    status = "success"
    retry_count = 0

    while retry_count <= max_retries:
        try:
            with transaction.atomic():
                event_obj = Event.objects.create(
                    event_id=event_id,
                    event_type=event_type,
                    event_version=event_data.get("event_version", "1.0.0"),
                    timestamp=datetime.fromisoformat(
                        event_data.get("timestamp", "").replace('Z', '+00:00')
                    ),
                    source_service=event_data.get("source", {}).get("service", "hub"),
                    tenant_id=tenant_id,
                    user_id=event_data.get("source", {}).get("user_id"),
                    request_id=event_data.get("source", {}).get("request_id"),
                    data=event_data.get("data", {}),
                    metadata=event_data.get("metadata", {})
                )

                # Validate consistency
                if event_id:
                    _validate_event_persistence(str(event_id), event_data)

                duration = timezone.now().timestamp() - start_time
                event_persistence_duration_seconds.labels(
                    event_type=event_type,
                    status=status,
                    tenant_id=tenant_label
                ).observe(duration)

                logger.info(
                    "event_persisted_async",
                    event_id=event_id,
                    event_type=event_type,
                    tenant_id=tenant_id,
                    duration=duration,
                    retry_count=retry_count
                )

                return str(event_id)

        except Exception as e:
            retry_count += 1
            duration = timezone.now().timestamp() - start_time

            if retry_count <= max_retries:
                delay = retry_delay_seconds * (retry_backoff_factor ** (retry_count - 1))
                logger.warning(
                    "event_persistence_async_retry",
                    event_id=event_id,
                    event_type=event_type,
                    error=str(e),
                    retry_count=retry_count,
                    max_retries=max_retries,
                    delay=delay,
                    duration=duration
                )
                time.sleep(delay)
            else:
                status = "failed"
                event_persistence_duration_seconds.labels(
                    event_type=event_type,
                    status=status,
                    tenant_id=tenant_label
                ).observe(duration)

                logger.error(
                    "event_persistence_async_error",
                    event_id=event_id,
                    event_type=event_type,
                    error=str(e),
                    retry_count=retry_count,
                    duration=duration,
                    exc_info=True
                )
                raise


@job('job_default', timeout=60)
def persist_events_batch_async(
    events_data: List[Dict[str, Any]],
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_delay_seconds: float = DEFAULT_RETRY_DELAY_SECONDS,
    retry_backoff_factor: float = DEFAULT_RETRY_BACKOFF_FACTOR
) -> int:
    """
    Persist multiple events to PostgreSQL asynchronously in batch with retry logic.

    Args:
        events_data: List of event dictionaries
        max_retries: Maximum number of retry attempts
        retry_delay_seconds: Initial delay between retries
        retry_backoff_factor: Multiplier for exponential backoff

    Returns:
        Number of events persisted

    Raises:
        Exception: If batch persistence fails after all retries
    """
    start_time = timezone.now().timestamp()
    persisted_count = 0
    retry_count = 0

    while retry_count <= max_retries:
        try:
            with transaction.atomic():
                events_to_create = []
                for event_data in events_data:
                    event_id = event_data.get("event_id")
                    event_type = event_data.get("event_type", "unknown")

                    try:
                        timestamp_str = event_data.get("timestamp", "")
                        if isinstance(timestamp_str, str):
                            timestamp = datetime.fromisoformat(
                                timestamp_str.replace('Z', '+00:00')
                            )
                        else:
                            timestamp = timezone.now()
                    except Exception:
                        timestamp = timezone.now()

                    event_obj = Event(
                        event_id=event_id,
                        event_type=event_type,
                        event_version=event_data.get("event_version", "1.0.0"),
                        timestamp=timestamp,
                        source_service=event_data.get("source", {}).get("service", "hub"),
                        tenant_id=event_data.get("source", {}).get("tenant_id"),
                        user_id=event_data.get("source", {}).get("user_id"),
                        request_id=event_data.get("source", {}).get("request_id"),
                        data=event_data.get("data", {}),
                        metadata=event_data.get("metadata", {})
                    )
                    events_to_create.append(event_obj)

                # Bulk create events
                Event.objects.bulk_create(events_to_create, ignore_conflicts=True)
                persisted_count = len(events_to_create)

                # Validate consistency
                _validate_batch_persistence(events_data, persisted_count)

                duration = timezone.now().timestamp() - start_time
                logger.info(
                    "events_persisted_batch_async",
                    count=persisted_count,
                    total=len(events_data),
                    duration=duration,
                    retry_count=retry_count
                )

                return persisted_count

        except Exception as e:
            retry_count += 1
            duration = timezone.now().timestamp() - start_time

            if retry_count <= max_retries:
                delay = retry_delay_seconds * (retry_backoff_factor ** (retry_count - 1))
                logger.warning(
                    "event_persistence_batch_async_retry",
                    error=str(e),
                    retry_count=retry_count,
                    max_retries=max_retries,
                    delay=delay,
                    count=len(events_data),
                    duration=duration
                )
                time.sleep(delay)
            else:
                logger.error(
                    "event_persistence_batch_async_error",
                    count=len(events_data),
                    persisted=persisted_count,
                    error=str(e),
                    retry_count=retry_count,
                    duration=duration,
                    exc_info=True
                )
                raise


def _validate_event_persistence(event_id: str, event_data: Dict[str, Any]):
    """
    Validate that an event was persisted correctly.

    Args:
        event_id: Event ID to validate
        event_data: Original event data

    Raises:
        Exception: If validation fails
    """
    try:
        persisted_event = Event.objects.get(event_id=event_id)

        # Validate key fields
        if persisted_event.event_type != event_data.get("event_type"):
            raise ValueError(
                f"Event type mismatch: expected {event_data.get('event_type')}, "
                f"got {persisted_event.event_type}"
            )

        if str(persisted_event.tenant_id) != str(event_data.get("source", {}).get("tenant_id")):
            logger.warning(
                "event_persistence_validation_tenant_mismatch",
                event_id=event_id,
                expected=event_data.get("source", {}).get("tenant_id"),
                got=str(persisted_event.tenant_id)
            )

        logger.debug(
            "event_persistence_validated",
            event_id=event_id,
            event_type=persisted_event.event_type
        )

    except Event.DoesNotExist:
        raise ValueError(f"Event {event_id} was not persisted")
    except Exception as e:
        logger.error(
            "event_persistence_validation_error",
            event_id=event_id,
            error=str(e),
            exc_info=True
        )
        raise


def _validate_batch_persistence(events_data: List[Dict[str, Any]], persisted_count: int):
    """
    Validate that batch events were persisted correctly.

    Args:
        events_data: Original event data list
        persisted_count: Number of events persisted
    """
    if persisted_count != len(events_data):
        logger.warning(
            "event_persistence_batch_validation_warning",
            expected=len(events_data),
            persisted=persisted_count,
            difference=len(events_data) - persisted_count
        )

    # Sample validation: check a few events exist
    sample_size = min(5, len(events_data))
    validated_count = 0

    for i in range(sample_size):
        event_data = events_data[i]
        event_id = event_data.get("event_id")
        if event_id:
            try:
                Event.objects.get(event_id=event_id)
                validated_count += 1
            except Event.DoesNotExist:
                logger.warning(
                    "event_persistence_batch_validation_failed",
                    event_id=event_id,
                    event_type=event_data.get("event_type")
                )

    logger.debug(
        "event_persistence_batch_validated",
        sample_size=sample_size,
        validated=validated_count,
        persisted=persisted_count
    )

