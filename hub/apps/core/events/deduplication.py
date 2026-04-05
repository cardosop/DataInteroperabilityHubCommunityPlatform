"""
Event Deduplication Utilities

Provides Redis-backed event deduplication to prevent duplicate event processing.
Uses event_type + data hash to generate deduplication keys.

Features:
- Generate deduplication keys from event type and data
- Check Redis for existing events (within TTL window)
- Store event IDs in Redis with configurable TTL
- Default TTL: 24 hours (configurable)
"""
from typing import Dict, Any, Optional, Tuple
import json
import hashlib
import structlog
import redis

logger = structlog.get_logger(__name__)

# Default TTL for deduplication keys (72 hours in seconds)
# Extended from 24h to 72h to support long-running workflows (Phase 96.16)
DEFAULT_DEDUPLICATION_TTL = 72 * 60 * 60  # 259200 seconds

# Redis key prefix for deduplication keys
DEDUPLICATION_KEY_PREFIX = "event:dedup"


def get_redis_client() -> Optional[redis.Redis]:
    """
    Get Redis client for deduplication operations.

    Uses the shared events connection pool to avoid per-call connection leaks.

    Returns:
        Redis client instance or None if unavailable

    Note:
        Returns None if Redis is unavailable to allow graceful degradation.
        Callers should handle None return value appropriately.
    """
    try:
        from hub.apps.core.redis_pools import get_redis_events_client
        client = get_redis_events_client()
        client.ping()
        return client
    except Exception as e:
        logger.warning(
            "event_deduplication_redis_unavailable",
            error=str(e),
            message="Event deduplication will not be enforced when Redis is unavailable"
        )
        return None


# Keys to exclude from deduplication hash (set at publish time, differ per call)
_VOLATILE_DEDUP_KEYS = frozenset({
    "created_at", "updated_at", "deleted_at", "failed_at", "completed_at",
    "tested_at", "started_at", "finished_at",
})


def _normalize_event_data(data: Dict[str, Any]) -> str:
    """
    Normalize event data for consistent hashing.

    Excludes volatile timestamp fields so two publishes with the same logical
    payload (e.g. same connection_id, marketplace_type, name) produce the same
    key and deduplicate correctly.

    Args:
        data: Event data dictionary

    Returns:
        Normalized JSON string

    Note:
        Sorts keys to ensure consistent hashing regardless of key order.
    """
    try:
        # Exclude volatile fields so same logical event deduplicates
        stable = {k: v for k, v in data.items() if k not in _VOLATILE_DEDUP_KEYS}
        normalized = json.dumps(stable, sort_keys=True, separators=(',', ':'))
        return normalized
    except (TypeError, ValueError) as e:
        logger.warning(
            "event_deduplication_normalization_error",
            error=str(e),
            message="Failed to normalize event data, using string representation"
        )
        # Fallback to string representation
        return str(data)


def generate_deduplication_key(event_type: str, event_data: Dict[str, Any]) -> str:
    """
    Generate deduplication key from event type and data.

    Args:
        event_type: Event type (e.g., 'contract.created')
        event_data: Event data payload dictionary

    Returns:
        Redis key for deduplication (format: event:dedup:{event_type}:{hash})

    Example:
        >>> generate_deduplication_key("contract.created", {"contract_id": "123"})
        'event:dedup:contract.created:abc123def456...'
    """
    # Normalize event data for consistent hashing
    normalized_data = _normalize_event_data(event_data)

    # Generate hash of normalized data
    data_hash = hashlib.sha256(normalized_data.encode('utf-8')).hexdigest()

    # Generate deduplication key: event:dedup:{event_type}:{hash}
    # Using colon separator for Redis key naming convention
    key = f"{DEDUPLICATION_KEY_PREFIX}:{event_type}:{data_hash}"

    return key


def check_event_duplicate(
    deduplication_key: str,
    redis_client: Optional[redis.Redis] = None
) -> Tuple[bool, Optional[str]]:
    """
    Check if event is duplicate by checking Redis for existing event ID.

    Args:
        deduplication_key: Deduplication key generated from event
        redis_client: Optional Redis client (creates new if not provided)

    Returns:
        Tuple of (is_duplicate: bool, existing_event_id: Optional[str])
        - is_duplicate: True if event already exists, False otherwise
        - existing_event_id: Event ID if duplicate found, None otherwise

    Note:
        Returns (False, None) if Redis is unavailable (fail open).
        This allows events to proceed when deduplication infrastructure is down.
    """
    if redis_client is None:
        redis_client = get_redis_client()

    if redis_client is None:
        # Redis unavailable - fail open (allow event to proceed)
        logger.debug(
            "event_deduplication_check_skipped",
            reason="redis_unavailable",
            deduplication_key=deduplication_key
        )
        return False, None

    try:
        existing_event_id = redis_client.get(deduplication_key)
        if existing_event_id:
            logger.debug(
                "event_duplicate_detected",
                deduplication_key=deduplication_key,
                existing_event_id=existing_event_id
            )
            return True, existing_event_id
        else:
            return False, None
    except Exception as e:
        # Redis error - fail open (allow event to proceed)
        logger.error(
            "event_deduplication_check_error",
            deduplication_key=deduplication_key,
            error=str(e),
            exc_info=True
        )
        return False, None


def store_event_id(
    deduplication_key: str,
    event_id: str,
    ttl: int = DEFAULT_DEDUPLICATION_TTL,
    redis_client: Optional[redis.Redis] = None
) -> bool:
    """
    Store event ID in Redis for deduplication.

    Args:
        deduplication_key: Deduplication key generated from event
        event_id: Event ID (UUID string) to store
        ttl: Time-to-live in seconds (default: 24 hours)
        redis_client: Optional Redis client (creates new if not provided)

    Returns:
        True if successfully stored, False otherwise

    Note:
        Returns False if Redis is unavailable (fail open).
        This allows events to proceed when deduplication infrastructure is down.
    """
    if redis_client is None:
        redis_client = get_redis_client()

    if redis_client is None:
        # Redis unavailable - fail open (log warning but don't block)
        logger.warning(
            "event_deduplication_store_skipped",
            reason="redis_unavailable",
            deduplication_key=deduplication_key,
            event_id=event_id
        )
        return False

    try:
        # Store event ID with TTL
        # Using setex to atomically set value and TTL
        redis_client.setex(deduplication_key, ttl, event_id)

        logger.debug(
            "event_deduplication_stored",
            deduplication_key=deduplication_key,
            event_id=event_id,
            ttl=ttl
        )
        return True
    except Exception as e:
        # Redis error - fail open (log error but don't block)
        logger.error(
            "event_deduplication_store_error",
            deduplication_key=deduplication_key,
            event_id=event_id,
            error=str(e),
            exc_info=True
        )
        return False


def check_and_store_event(
    deduplication_key: str,
    event_id: str,
    ttl: int = DEFAULT_DEDUPLICATION_TTL,
    redis_client: Optional[redis.Redis] = None,
) -> Tuple[bool, str]:
    """Atomically check-and-store an event ID for deduplication.

    Uses ``SET key value NX EX ttl`` — a single atomic Redis command.
    If the key does NOT exist, it is set and ``(False, event_id)`` is
    returned (new event).  If the key already exists, the existing
    value is returned as ``(True, existing_event_id)`` (duplicate).

    Returns:
        Tuple of (is_duplicate, event_id_stored_or_existing).
    """
    if redis_client is None:
        redis_client = get_redis_client()

    if redis_client is None:
        # Fail open — allow event through
        return False, event_id

    try:
        # SET NX EX is atomic: only sets if key doesn't exist
        was_set = redis_client.set(
            deduplication_key, event_id, nx=True, ex=ttl,
        )
        if was_set:
            return False, event_id  # New event — we stored it

        # Key existed — retrieve the existing event_id
        existing = redis_client.get(deduplication_key)
        if existing is not None:
            if isinstance(existing, bytes):
                existing = existing.decode("utf-8")
            return True, existing
        # Key expired between SET and GET — treat as new
        return False, event_id
    except Exception as e:
        logger.warning(
            "deduplication_atomic_check_failed",
            key=deduplication_key,
            error=str(e),
        )
        return False, event_id


def is_event_duplicate(
    event_type: str,
    event_data: Dict[str, Any],
    redis_client: Optional[redis.Redis] = None
) -> bool:
    """
    Convenience function to check if event is duplicate.

    Args:
        event_type: Event type (e.g., 'contract.created')
        event_data: Event data payload dictionary
        redis_client: Optional Redis client (creates new if not provided)

    Returns:
        True if event is duplicate, False otherwise

    Example:
        >>> is_event_duplicate("contract.created", {"contract_id": "123"})
        False
    """
    deduplication_key = generate_deduplication_key(event_type, event_data)
    is_dup, _ = check_event_duplicate(deduplication_key, redis_client=redis_client)
    return is_dup

