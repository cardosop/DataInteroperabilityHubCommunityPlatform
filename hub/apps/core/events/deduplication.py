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

import hashlib
import json
from typing import Any

import redis
import structlog

logger = structlog.get_logger(__name__)

# Default TTL for deduplication keys (72 hours in seconds)
# Extended from 24h to 72h to support long-running workflows (Phase 96.16)
DEFAULT_DEDUPLICATION_TTL = 72 * 60 * 60  # 259200 seconds

# Redis key prefix for deduplication keys (legacy shared namespace)
DEDUPLICATION_KEY_PREFIX = "event:dedup"

# W4.1 (R2-B3) — publisher and consumer dedup live in SEPARATE Redis
# namespaces.  The shared namespace was the self-dedup root cause:
# ``EventPublisher`` stored ``event:dedup:<type>:<hash>`` after publishing
# and ``EventBus._handle_event`` checked the SAME key before processing —
# every event published through ``EventPublisher`` was skipped by every
# consumer as "already processed", and consumer A's consumption state
# suppressed delivery to consumer B.
#
#   * ``sent`` — publisher-side keys: ``event:sent:<type>:<hash>``.
#     Store only what THIS process published (duplicate-publish guard).
#   * ``cons`` — consumer-side keys:
#     ``event:cons:<subscriber>:<type>:<hash>``.  Scoped per subscriber:
#     each subscriber tracks its OWN consumption state.
DEFAULT_DEDUP_NAMESPACE = "dedup"  # legacy shared namespace (kept for old keys)
PUBLISHER_DEDUP_NAMESPACE = "sent"
CONSUMER_DEDUP_NAMESPACE = "cons"


def get_redis_client() -> redis.Redis | None:
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
    except redis.exceptions.RedisError as e:
        logger.warning(
            "event_deduplication_redis_unavailable",
            error=str(e),
            message="Event deduplication will not be enforced when Redis is unavailable",
        )
        return None
    else:
        return client


# Keys to exclude from deduplication hash (set at publish time, differ per call)
_VOLATILE_DEDUP_KEYS = frozenset(
    {
        "created_at",
        "updated_at",
        "deleted_at",
        "failed_at",
        "completed_at",
        "tested_at",
        "started_at",
        "finished_at",
    }
)


def _normalize_event_data(data: dict[str, Any]) -> str:
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
        normalized = json.dumps(stable, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as e:
        logger.warning(
            "event_deduplication_normalization_error",
            error=str(e),
            message="Failed to normalize event data, using string representation",
        )
        # Fallback to string representation
        return str(data)
    else:
        return normalized


def generate_deduplication_key(
    event_type: str,
    event_data: dict[str, Any],
    namespace: str = DEFAULT_DEDUP_NAMESPACE,
    subscriber: str | None = None,
) -> str:
    """
    Generate deduplication key from event type and data.

    W4.1 (R2-B3): the key carries a *namespace* — publisher-side dedup
    (``PUBLISHER_DEDUP_NAMESPACE``, ``event:sent:*``) and consumer-side
    dedup (``CONSUMER_DEDUP_NAMESPACE``, ``event:cons:*``) never share a
    key.  Consumer keys additionally carry the *subscriber* name so each
    subscriber tracks its own consumption state.

    Args:
        event_type: Event type (e.g., 'contract.created')
        event_data: Event data payload dictionary
        namespace: Dedup namespace (``sent`` / ``cons`` / legacy ``dedup``)
        subscriber: Consumer subscriber name (scopes the ``cons`` key)

    Returns:
        Redis key for deduplication (format:
        ``event:{namespace}:[{subscriber}:]{event_type}:{hash}``)

    Example:
        >>> generate_deduplication_key("contract.created", {"contract_id": "123"})
        'event:dedup:contract.created:abc123def456...'
        >>> generate_deduplication_key(
        ...     "contract.created", {"contract_id": "123"},
        ...     namespace=CONSUMER_DEDUP_NAMESPACE, subscriber="webhook_service",
        ... )
        'event:cons:webhook_service:contract.created:abc123def456...'
    """
    # Normalize event data for consistent hashing
    normalized_data = _normalize_event_data(event_data)

    # Generate hash of normalized data
    data_hash = hashlib.sha256(normalized_data.encode("utf-8")).hexdigest()

    # Generate deduplication key: event:{namespace}:[{subscriber}:]{event_type}:{hash}
    # Using colon separator for Redis key naming convention
    segments = ["event", namespace]
    if subscriber:
        segments.append(subscriber)
    segments.extend((event_type, data_hash))
    key = ":".join(segments)

    return key


def clear_all_dedup_namespaces(redis_client: redis.Redis | None = None) -> int:
    """Delete every dedup key across ALL namespaces (W4.1 test/ops hygiene).

    Scans the legacy ``event:dedup:*`` + publisher ``event:sent:*`` +
    consumer ``event:cons:*`` namespaces.  Test setups must start from a
    clean dedup state because Redis keys survive TestCase rollbacks — a
    stale ``sent`` key from a previous test otherwise suppresses the next
    identical publish and the deduped id points at a rolled-back row.

    Returns:
        Number of keys deleted (0 when Redis is unavailable).
    """
    if redis_client is None:
        redis_client = get_redis_client()
    if redis_client is None:
        return 0

    deleted = 0
    for namespace in (
        DEFAULT_DEDUP_NAMESPACE,
        PUBLISHER_DEDUP_NAMESPACE,
        CONSUMER_DEDUP_NAMESPACE,
    ):
        try:
            for key in redis_client.scan_iter(f"event:{namespace}:*"):
                redis_client.delete(key)
                deleted += 1
        except redis.exceptions.RedisError as e:
            logger.warning(
                "event_deduplication_clear_error",
                namespace=namespace,
                error=str(e),
            )
    return deleted


def check_event_duplicate(
    deduplication_key: str, redis_client: redis.Redis | None = None
) -> tuple[bool, str | None]:
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
            deduplication_key=deduplication_key,
        )
        return False, None

    try:
        existing_event_id = redis_client.get(deduplication_key)
        if existing_event_id:
            logger.debug(
                "event_duplicate_detected",
                deduplication_key=deduplication_key,
                existing_event_id=existing_event_id,
            )
            return True, existing_event_id
        else:
            return False, None
    except redis.exceptions.RedisError as e:
        # Redis error - fail open (allow event to proceed)
        logger.error(
            "event_deduplication_check_error",
            deduplication_key=deduplication_key,
            error=str(e),
            exc_info=True,
        )
        return False, None


def store_event_id(
    deduplication_key: str,
    event_id: str,
    ttl: int = DEFAULT_DEDUPLICATION_TTL,
    redis_client: redis.Redis | None = None,
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
            event_id=event_id,
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
            ttl=ttl,
        )
    except redis.exceptions.RedisError as e:
        # Redis error - fail open (log error but don't block)
        logger.error(
            "event_deduplication_store_error",
            deduplication_key=deduplication_key,
            event_id=event_id,
            error=str(e),
            exc_info=True,
        )
        return False
    else:
        return True


def check_and_store_event(
    deduplication_key: str,
    event_id: str,
    ttl: int = DEFAULT_DEDUPLICATION_TTL,
    redis_client: redis.Redis | None = None,
) -> tuple[bool, str]:
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
            deduplication_key,
            event_id,
            nx=True,
            ex=ttl,
        )
        if was_set:
            return False, event_id  # New event — we stored it

        # Key existed — retrieve the existing event_id
        existing = redis_client.get(deduplication_key)
        if existing is not None:
            if isinstance(existing, bytes):
                existing = existing.decode("utf-8")
            return True, existing
    except redis.exceptions.RedisError as e:
        logger.warning(
            "deduplication_atomic_check_failed",
            key=deduplication_key,
            error=str(e),
        )
        return False, event_id
    else:
        # Key expired between SET and GET — treat as new
        return False, event_id


def is_event_duplicate(
    event_type: str,
    event_data: dict[str, Any],
    namespace: str = DEFAULT_DEDUP_NAMESPACE,
    subscriber: str | None = None,
    redis_client: redis.Redis | None = None,
) -> bool:
    """
    Convenience function to check if event is duplicate.

    Args:
        event_type: Event type (e.g., 'contract.created')
        event_data: Event data payload dictionary
        namespace: Dedup namespace (``sent`` / ``cons`` / legacy ``dedup``)
        subscriber: Consumer subscriber name (scopes the ``cons`` key)
        redis_client: Optional Redis client (creates new if not provided)

    Returns:
        True if event is duplicate, False otherwise

    Example:
        >>> is_event_duplicate("contract.created", {"contract_id": "123"})
        False
    """
    deduplication_key = generate_deduplication_key(
        event_type, event_data, namespace=namespace, subscriber=subscriber
    )
    is_dup, _ = check_event_duplicate(deduplication_key, redis_client=redis_client)
    return is_dup


REPLAY_MARKER_TTL = 24 * 60 * 60  # 24 hours — the replay dedup window


def _replay_key(event_id: str) -> str:
    return f"event_replay:event_id:{event_id}"


def claim_event_replay(event_id: str) -> bool:
    """Atomically claim the replay marker (W12.8) — the ONE dedup
    implementation for event replay, shared by the replay management
    command and the replay API view.

    SETNX-style claim with a 24h TTL: the FIRST claimant gets True and
    may replay; every other caller (a concurrent replayer, a re-run
    inside the TTL window) gets False and skips.  A crash between the
    claim and the publish loses the replay until the marker expires —
    callers release the claim on a FAILED replay (see
    ``release_event_replay``) so retries can re-run at-least-once.

    Uses Redis if available, falls back to Django cache (``cache.add``
    has the same atomic NX semantics).

    Returns:
        True if this caller won the claim, False otherwise.
    """
    from django.core.cache import cache

    replay_key = _replay_key(event_id)

    redis_client = get_redis_client()
    if redis_client:
        try:
            claimed = bool(
                redis_client.set(
                    replay_key, "1", ex=REPLAY_MARKER_TTL, nx=True
                )
            )
        except redis.exceptions.RedisError as e:
            logger.warning(
                "event_replay_claim_redis_error",
                event_id=event_id,
                error=str(e),
                message="Redis error, falling back to Django cache",
            )
        else:
            return claimed

    try:
        claimed = bool(cache.add(replay_key, "1", REPLAY_MARKER_TTL))
    except Exception as e:  # noqa: BLE001 — cache boundary: any backend
        # error must degrade to "cannot claim" without raising.
        logger.warning(
            "event_replay_claim_cache_error",
            event_id=event_id,
            error=str(e),
            message="Cache unavailable, cannot claim replay marker",
        )
        return False
    else:
        return claimed


def release_event_replay(event_id: str) -> None:
    """Release the replay claim (best-effort) so a retry can re-run.

    Called on a FAILED replay — the claim must not stick when the event
    never actually replayed (at-least-once for failures).
    """
    from django.core.cache import cache

    replay_key = _replay_key(event_id)

    redis_client = get_redis_client()
    if redis_client:
        try:
            redis_client.delete(replay_key)
        except redis.exceptions.RedisError as e:
            logger.warning(
                "event_replay_release_redis_error",
                event_id=event_id,
                error=str(e),
                message="Redis error, falling back to Django cache",
            )
        else:
            return

    try:
        cache.delete(replay_key)
    except Exception as e:  # noqa: BLE001 — cache boundary: any backend
        # error must degrade to "cannot release" without raising.
        logger.warning(
            "event_replay_release_cache_error",
            event_id=event_id,
            error=str(e),
            message="Cache unavailable, cannot release replay marker",
        )
