"""
Event Message Acknowledgment

Provides Redis-backed message acknowledgment tracking for Pub/Sub events.
Since Redis Pub/Sub doesn't have built-in acknowledgment, we implement
a pattern using Redis to track message processing status.

Features:
- Track message processing status (pending, processing, acknowledged, failed)
- Configurable acknowledgment timeout
- Automatic cleanup of stale acknowledgments
- Metrics for acknowledgment tracking
"""

import json
import time

import redis
import structlog

from .metrics import (
    event_acknowledged_total,
    event_acknowledgment_failed_total,
    event_acknowledgment_timeout_total,
)

logger = structlog.get_logger(__name__)

# Default acknowledgment timeout (5 minutes)
DEFAULT_ACK_TIMEOUT = 5 * 60  # 300 seconds

# Redis key prefix for acknowledgment tracking
ACK_KEY_PREFIX = "event:ack"
PENDING_KEY_PREFIX = "event:pending"
PROCESSING_KEY_PREFIX = "event:processing"

# Status values
STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_ACKNOWLEDGED = "acknowledged"
STATUS_FAILED = "failed"


def get_redis_client() -> redis.Redis | None:
    """
    Get Redis client for acknowledgment operations.

    Uses the shared events connection pool to avoid per-call connection leaks.

    Returns:
        Redis client instance or None if unavailable
    """
    try:
        from hub.apps.core.redis_pools import get_redis_events_client

        client = get_redis_events_client()
        client.ping()
        return client
    except Exception as e:
        logger.warning(
            "event_acknowledgment_redis_unavailable",
            error=str(e),
            message="Event acknowledgment tracking unavailable",
        )
        return None


def mark_event_pending(
    event_id: str,
    subscriber_name: str,
    event_type: str,
    redis_client: redis.Redis | None = None,
    timeout: int = DEFAULT_ACK_TIMEOUT,
) -> bool:
    """
    Mark event as pending acknowledgment.

    Args:
        event_id: Event ID (UUID string)
        subscriber_name: Subscriber identifier
        event_type: Event type
        redis_client: Optional Redis client
        timeout: Acknowledgment timeout in seconds

    Returns:
        True if successfully marked, False otherwise
    """
    if redis_client is None:
        redis_client = get_redis_client()

    if redis_client is None:
        return False

    try:
        # Create pending key: event:pending:{subscriber}:{event_id}
        pending_key = f"{PENDING_KEY_PREFIX}:{subscriber_name}:{event_id}"

        # Store pending status with metadata
        pending_data = {
            "event_id": event_id,
            "subscriber_name": subscriber_name,
            "event_type": event_type,
            "status": STATUS_PENDING,
            "created_at": time.time(),
            "timeout": timeout,
        }

        # Set with timeout
        redis_client.setex(pending_key, timeout, json.dumps(pending_data))

        logger.debug(
            "event_marked_pending",
            event_id=event_id,
            subscriber_name=subscriber_name,
            event_type=event_type,
            timeout=timeout,
        )
        return True
    except Exception as e:
        logger.error(
            "event_mark_pending_error",
            event_id=event_id,
            subscriber_name=subscriber_name,
            error=str(e),
            exc_info=True,
        )
        return False


def mark_event_processing(
    event_id: str, subscriber_name: str, redis_client: redis.Redis | None = None
) -> bool:
    """
    Mark event as being processed.

    Args:
        event_id: Event ID (UUID string)
        subscriber_name: Subscriber identifier
        redis_client: Optional Redis client

    Returns:
        True if successfully marked, False otherwise
    """
    if redis_client is None:
        redis_client = get_redis_client()

    if redis_client is None:
        return False

    try:
        # Move from pending to processing
        pending_key = f"{PENDING_KEY_PREFIX}:{subscriber_name}:{event_id}"
        processing_key = f"{PROCESSING_KEY_PREFIX}:{subscriber_name}:{event_id}"

        # Get pending data
        pending_data_str = redis_client.get(pending_key)
        if not pending_data_str:
            # Not in pending, might already be processing or acknowledged
            return False

        pending_data = json.loads(pending_data_str)
        pending_data["status"] = STATUS_PROCESSING
        pending_data["processing_started_at"] = time.time()

        # Set processing key with same timeout
        timeout = pending_data.get("timeout", DEFAULT_ACK_TIMEOUT)
        redis_client.setex(processing_key, timeout, json.dumps(pending_data))

        # Remove pending key
        redis_client.delete(pending_key)

        logger.debug("event_marked_processing", event_id=event_id, subscriber_name=subscriber_name)
        return True
    except Exception as e:
        logger.error(
            "event_mark_processing_error",
            event_id=event_id,
            subscriber_name=subscriber_name,
            error=str(e),
            exc_info=True,
        )
        return False


def acknowledge_event(
    event_id: str,
    subscriber_name: str,
    event_type: str,
    redis_client: redis.Redis | None = None,
    success: bool = True,
) -> bool:
    """
    Acknowledge event processing completion.

    Args:
        event_id: Event ID (UUID string)
        subscriber_name: Subscriber identifier
        event_type: Event type
        redis_client: Optional Redis client
        success: True if processing succeeded, False if failed

    Returns:
        True if successfully acknowledged, False otherwise
    """
    if redis_client is None:
        redis_client = get_redis_client()

    if redis_client is None:
        return False

    try:
        # Remove from pending or processing
        pending_key = f"{PENDING_KEY_PREFIX}:{subscriber_name}:{event_id}"
        processing_key = f"{PROCESSING_KEY_PREFIX}:{subscriber_name}:{event_id}"

        # Check if in processing
        processing_data_str = redis_client.get(processing_key)
        if processing_data_str:
            processing_data = json.loads(processing_data_str)
            redis_client.delete(processing_key)
        else:
            # Check if in pending
            pending_data_str = redis_client.get(pending_key)
            if pending_data_str:
                processing_data = json.loads(pending_data_str)
                redis_client.delete(pending_key)
            else:
                # Already acknowledged or timed out
                logger.debug(
                    "event_already_acknowledged_or_timeout",
                    event_id=event_id,
                    subscriber_name=subscriber_name,
                )
                return False

        # Store acknowledgment
        ack_key = f"{ACK_KEY_PREFIX}:{subscriber_name}:{event_id}"
        ack_data = {
            "event_id": event_id,
            "subscriber_name": subscriber_name,
            "event_type": event_type,
            "status": STATUS_ACKNOWLEDGED if success else STATUS_FAILED,
            "acknowledged_at": time.time(),
            "processing_duration": (
                time.time()
                - processing_data.get(
                    "processing_started_at", processing_data.get("created_at", time.time())
                )
            ),
        }

        # Store acknowledgment with longer TTL (24 hours for audit)
        redis_client.setex(
            ack_key,
            24 * 60 * 60,  # 24 hours
            json.dumps(ack_data),
        )

        # Record metrics
        if success:
            event_acknowledged_total.labels(
                event_type=event_type, subscriber_name=subscriber_name, status="success"
            ).inc()
        else:
            event_acknowledgment_failed_total.labels(
                event_type=event_type, subscriber_name=subscriber_name
            ).inc()

        logger.info(
            "event_acknowledged",
            event_id=event_id,
            subscriber_name=subscriber_name,
            event_type=event_type,
            success=success,
        )
        return True
    except Exception as e:
        logger.error(
            "event_acknowledgment_error",
            event_id=event_id,
            subscriber_name=subscriber_name,
            error=str(e),
            exc_info=True,
        )
        return False


def check_event_acknowledged(
    event_id: str, subscriber_name: str, redis_client: redis.Redis | None = None
) -> bool:
    """
    Check if event has been acknowledged.

    Args:
        event_id: Event ID (UUID string)
        subscriber_name: Subscriber identifier
        redis_client: Optional Redis client

    Returns:
        True if acknowledged, False otherwise
    """
    if redis_client is None:
        redis_client = get_redis_client()

    if redis_client is None:
        return False

    try:
        ack_key = f"{ACK_KEY_PREFIX}:{subscriber_name}:{event_id}"
        ack_data_str = redis_client.get(ack_key)
        return ack_data_str is not None
    except Exception:
        return False


def get_pending_events(subscriber_name: str, redis_client: redis.Redis | None = None) -> list:
    """
    Get list of pending events for subscriber.

    Args:
        subscriber_name: Subscriber identifier
        redis_client: Optional Redis client

    Returns:
        List of pending event IDs
    """
    if redis_client is None:
        redis_client = get_redis_client()

    if redis_client is None:
        return []

    try:
        pattern = f"{PENDING_KEY_PREFIX}:{subscriber_name}:*"
        keys = redis_client.keys(pattern)
        event_ids = []
        for key in keys:
            # Extract event_id from key: event:pending:{subscriber}:{event_id}
            parts = key.split(":")
            if len(parts) >= 4:
                event_id = ":".join(parts[3:])  # Handle UUIDs with colons
                event_ids.append(event_id)
        return event_ids
    except Exception as e:
        logger.error(
            "get_pending_events_error", subscriber_name=subscriber_name, error=str(e), exc_info=True
        )
        return []


def cleanup_timeout_events(subscriber_name: str, redis_client: redis.Redis | None = None) -> int:
    """
    Clean up timed-out events (events that exceeded acknowledgment timeout).

    Args:
        subscriber_name: Subscriber identifier
        redis_client: Optional Redis client

    Returns:
        Number of events cleaned up
    """
    if redis_client is None:
        redis_client = get_redis_client()

    if redis_client is None:
        return 0

    try:
        # Get all pending and processing keys
        pending_pattern = f"{PENDING_KEY_PREFIX}:{subscriber_name}:*"
        processing_pattern = f"{PROCESSING_KEY_PREFIX}:{subscriber_name}:*"

        pending_keys = redis_client.keys(pending_pattern)
        processing_keys = redis_client.keys(processing_pattern)

        cleaned = 0
        current_time = time.time()

        # Check pending events
        for key in pending_keys:
            try:
                data_str = redis_client.get(key)
                if data_str:
                    data = json.loads(data_str)
                    created_at = data.get("created_at", 0)
                    timeout = data.get("timeout", DEFAULT_ACK_TIMEOUT)

                    if current_time - created_at > timeout:
                        # Timed out
                        redis_client.delete(key)
                        cleaned += 1

                        # Record timeout metric
                        event_acknowledgment_timeout_total.labels(
                            event_type=data.get("event_type", "unknown"),
                            subscriber_name=subscriber_name,
                        ).inc()

                        logger.warning(
                            "event_acknowledgment_timeout",
                            event_id=data.get("event_id"),
                            subscriber_name=subscriber_name,
                            event_type=data.get("event_type"),
                            timeout=timeout,
                        )
            except Exception:
                pass

        # Check processing events
        for key in processing_keys:
            try:
                data_str = redis_client.get(key)
                if data_str:
                    data = json.loads(data_str)
                    processing_started_at = data.get(
                        "processing_started_at", data.get("created_at", 0)
                    )
                    timeout = data.get("timeout", DEFAULT_ACK_TIMEOUT)

                    if current_time - processing_started_at > timeout:
                        # Timed out
                        redis_client.delete(key)
                        cleaned += 1

                        # Record timeout metric
                        event_acknowledgment_timeout_total.labels(
                            event_type=data.get("event_type", "unknown"),
                            subscriber_name=subscriber_name,
                        ).inc()

                        logger.warning(
                            "event_processing_timeout",
                            event_id=data.get("event_id"),
                            subscriber_name=subscriber_name,
                            event_type=data.get("event_type"),
                            timeout=timeout,
                        )
            except Exception:
                pass

        return cleaned
    except Exception as e:
        logger.error(
            "cleanup_timeout_events_error",
            subscriber_name=subscriber_name,
            error=str(e),
            exc_info=True,
        )
        return 0
