"""
Idempotency Utilities

Utility functions for idempotency key validation, Redis operations,
and request/response serialization.
"""
import hashlib
import json
import re
import uuid
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, timezone

import structlog
import redis
from django.conf import settings
from django.http import HttpRequest, HttpResponse

logger = structlog.get_logger(__name__)


class IdempotencyKeyError(Exception):
    """Base exception for idempotency key errors."""
    pass


class IdempotencyKeyFormatError(IdempotencyKeyError):
    """Raised when idempotency key format is invalid."""
    pass


class IdempotencyConflictError(IdempotencyKeyError):
    """Raised when idempotency key conflicts with existing request."""
    pass


def validate_idempotency_key(key: str) -> bool:
    """
    Validate idempotency key format.

    Supports:
    - UUID format (e.g., "550e8400-e29b-41d4-a716-446655440000")
    - Custom format: 8-256 characters, alphanumeric, hyphens, underscores, forward slashes

    Args:
        key: Idempotency key to validate

    Returns:
        True if valid, False otherwise
    """
    if not key or not isinstance(key, str):
        return False

    # Check UUID format first
    try:
        uuid.UUID(key)
        return True
    except (ValueError, AttributeError):
        pass

    # Check custom format: 8-256 characters, alphanumeric, hyphens, underscores, forward slashes
    if len(key) < 8 or len(key) > 256:
        return False

    # Pattern: alphanumeric, hyphens, underscores, forward slashes
    pattern = re.compile(r'^[a-zA-Z0-9\-_/]+$')
    return bool(pattern.match(key))


def normalize_idempotency_key(key: str) -> str:
    """
    Normalize idempotency key for consistent storage.

    Strips whitespace before validation to allow keys with leading/trailing spaces.

    Args:
        key: Idempotency key to normalize

    Returns:
        Normalized key string

    Raises:
        IdempotencyKeyFormatError: If key format is invalid
    """
    # Strip whitespace first
    normalized = key.strip() if isinstance(key, str) else str(key).strip()

    # Then validate the normalized key
    if not validate_idempotency_key(normalized):
        raise IdempotencyKeyFormatError(
            f"Invalid idempotency key format. Key must be UUID or 8-256 characters "
            f"containing only alphanumeric characters, hyphens, underscores, and forward slashes."
        )

    return normalized


def get_redis_client() -> redis.Redis:
    """
    Get Redis client for idempotency operations.

    Returns:
        Redis client instance

    Raises:
        redis.ConnectionError: If Redis connection fails
    """
    redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')
    try:
        client = redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )
        # Test connection
        client.ping()
        return client
    except Exception as e:
        logger.error(
            "idempotency_redis_connection_error",
            error=str(e),
            redis_url=redis_url
        )
        raise redis.ConnectionError(f"Failed to connect to Redis: {e}") from e


def build_idempotency_key(
    idempotency_key: str,
    endpoint: str,
    method: str,
    tenant_id: Optional[str] = None
) -> str:
    """
    Build Redis key for idempotency storage.

    Format: idempotency:{normalized_key}:{method}:{endpoint}:{tenant_id}

    Args:
        idempotency_key: User-provided idempotency key
        endpoint: API endpoint path
        method: HTTP method
        tenant_id: Optional tenant ID for multi-tenancy

    Returns:
        Redis key string
    """
    normalized_key = normalize_idempotency_key(idempotency_key)

    # Normalize endpoint (remove trailing slashes, normalize path)
    normalized_endpoint = endpoint.rstrip('/')

    # Build key components
    key_parts = ['idempotency', normalized_key, method.upper(), normalized_endpoint]

    if tenant_id:
        key_parts.append(str(tenant_id))

    return ':'.join(key_parts)


def build_lock_key(idempotency_redis_key: str) -> str:
    """
    Build Redis lock key for concurrent request handling.

    Args:
        idempotency_redis_key: Base idempotency Redis key

    Returns:
        Lock key string
    """
    return f"{idempotency_redis_key}:lock"


def hash_request_body(body: Any) -> str:
    """
    Generate hash of request body for idempotency validation.

    Args:
        body: Request body (dict, list, or string)

    Returns:
        SHA256 hash of serialized body
    """
    if body is None:
        body_str = ""
    elif isinstance(body, (dict, list)):
        # Sort keys for consistent hashing
        body_str = json.dumps(body, sort_keys=True, separators=(',', ':'))
    elif isinstance(body, str):
        body_str = body
    else:
        body_str = str(body)

    return hashlib.sha256(body_str.encode('utf-8')).hexdigest()


def serialize_response(response: HttpResponse) -> Dict[str, Any]:
    """
    Serialize HTTP response for storage in Redis.

    Args:
        response: Django HttpResponse object

    Returns:
        Dictionary with serialized response data
    """
    # Get response body
    if hasattr(response, 'content'):
        try:
            # Try to decode JSON response
            body = json.loads(response.content.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Fallback to string
            body = response.content.decode('utf-8', errors='replace')
    else:
        body = None

    # Get headers (exclude sensitive headers)
    excluded_headers = {
        'content-length', 'content-encoding', 'transfer-encoding',
        'connection', 'server', 'date'
    }
    headers = {
        k: v for k, v in response.items()
        if k.lower() not in excluded_headers
    }

    return {
        'status_code': response.status_code,
        'body': body,
        'headers': headers,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }


def deserialize_response(data: Dict[str, Any]) -> Tuple[int, Dict[str, Any], Dict[str, str]]:
    """
    Deserialize stored response data.

    Args:
        data: Serialized response data from Redis

    Returns:
        Tuple of (status_code, body, headers)
    """
    status_code = data.get('status_code', 200)
    body = data.get('body', {})
    headers = data.get('headers', {})

    return status_code, body, headers


def store_idempotency_record(
    redis_client: redis.Redis,
    redis_key: str,
    request_hash: str,
    response_data: Dict[str, Any],
    ttl: int = 86400  # 24 hours default
) -> None:
    """
    Store idempotency record in Redis.

    Args:
        redis_client: Redis client instance
        redis_key: Redis key for storage
        request_hash: Hash of request body
        response_data: Serialized response data
        ttl: Time to live in seconds (default: 24 hours)
    """
    record = {
        'request_hash': request_hash,
        'response': response_data,
        'created_at': datetime.now(timezone.utc).isoformat()
    }

    redis_client.setex(
        redis_key,
        ttl,
        json.dumps(record)
    )


def get_idempotency_record(
    redis_client: redis.Redis,
    redis_key: str
) -> Optional[Dict[str, Any]]:
    """
    Retrieve idempotency record from Redis.

    Args:
        redis_client: Redis client instance
        redis_key: Redis key to retrieve

    Returns:
        Idempotency record dictionary or None if not found
    """
    data = redis_client.get(redis_key)
    if not data:
        return None

    try:
        record = json.loads(data)
        # Check if record has expired based on created_at timestamp
        # (Redis TTL handles automatic expiration, but we check timestamp for explicit 410 Gone)
        if 'created_at' in record:
            created_at_str = record['created_at']
            try:
                created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                ttl = get_idempotency_ttl()
                age_seconds = (datetime.now(timezone.utc) - created_at).total_seconds()

                if age_seconds > ttl:
                    # Record has expired based on timestamp
                    return None
            except (ValueError, TypeError):
                # Invalid timestamp format - treat as valid record
                pass

        return record
    except json.JSONDecodeError as e:
        logger.error(
            "idempotency_record_decode_error",
            error=str(e),
            redis_key=redis_key
        )
        return None


def check_idempotency_key_expired(
    redis_client: redis.Redis,
    redis_key: str
) -> bool:
    """
    Check if an idempotency key has expired.

    This checks if a key was previously used but has now expired.
    Since Redis automatically deletes expired keys, we check the TTL.

    Args:
        redis_client: Redis client instance
        redis_key: Redis key to check

    Returns:
        True if key exists but has expired (TTL <= 0), False otherwise
    """
    try:
        ttl = redis_client.ttl(redis_key)
        # TTL: -2 = key doesn't exist, -1 = key exists but no expiry, 0+ = seconds until expiry
        # If TTL is -2, key doesn't exist (could be new or expired)
        # If TTL is 0, key exists but has expired (shouldn't happen as Redis deletes it)
        # If TTL is -1, key exists with no expiry (shouldn't happen with our implementation)
        # If TTL > 0, key exists and hasn't expired

        # Check if key exists but TTL indicates it's expired or about to expire
        if ttl == 0:
            # Key exists but TTL is 0 (expired but not yet deleted)
            return True

        # Also check if record exists but created_at timestamp indicates expiration
        record = get_idempotency_record(redis_client, redis_key)
        if record and 'created_at' in record:
            try:
                created_at_str = record['created_at']
                created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                ttl_seconds = get_idempotency_ttl()
                age_seconds = (datetime.now(timezone.utc) - created_at).total_seconds()

                if age_seconds > ttl_seconds:
                    return True
            except (ValueError, TypeError):
                pass

        return False
    except Exception as e:
        logger.error(
            "idempotency_ttl_check_error",
            error=str(e),
            redis_key=redis_key
        )
        return False


def acquire_lock(
    redis_client: redis.Redis,
    lock_key: str,
    timeout: int = 10,
    expire: int = 30
) -> bool:
    """
    Acquire distributed lock for concurrent request handling.

    Uses Redis SETNX with expiration for atomic lock acquisition.

    Args:
        redis_client: Redis client instance
        lock_key: Lock key
        timeout: Maximum time to wait for lock (seconds)
        expire: Lock expiration time (seconds)

    Returns:
        True if lock acquired, False otherwise
    """
    import time

    end_time = time.time() + timeout
    while time.time() < end_time:
        # Try to acquire lock using SETNX with expiration
        if redis_client.set(lock_key, "locked", nx=True, ex=expire):
            return True
        time.sleep(0.1)  # Small delay before retry

    return False


def release_lock(redis_client: redis.Redis, lock_key: str) -> None:
    """
    Release distributed lock.

    Args:
        redis_client: Redis client instance
        lock_key: Lock key to release
    """
    redis_client.delete(lock_key)


def get_idempotency_ttl() -> int:
    """
    Get idempotency TTL from settings.

    Returns:
        TTL in seconds (default: 24 hours)
    """
    return getattr(settings, 'IDEMPOTENCY_TTL_SECONDS', 86400)  # 24 hours


def is_idempotency_enabled() -> bool:
    """
    Check if idempotency is enabled in settings.

    Returns:
        True if enabled, False otherwise
    """
    return getattr(settings, 'IDEMPOTENCY_ENABLED', True)


def should_process_idempotency(request: HttpRequest) -> bool:
    """
    Determine if request should be processed for idempotency.

    Only processes:
    - POST, PUT, PATCH methods
    - API endpoints (/api/v1/)
    - Requests with Idempotency-Key header

    Args:
        request: HTTP request object

    Returns:
        True if should process, False otherwise
    """
    # Check if idempotency is enabled
    if not is_idempotency_enabled():
        return False

    # Only process API endpoints
    if not request.path.startswith('/api/v1/'):
        return False

    # Only process state-changing methods
    if request.method not in ('POST', 'PUT', 'PATCH'):
        return False

    # Must have Idempotency-Key header
    if not request.headers.get('Idempotency-Key'):
        return False

    return True


def get_endpoint_pattern(path: str) -> str:
    """
    Normalize endpoint path for idempotency key matching.

    Removes resource IDs from path to allow same idempotency key
    for different resources (e.g., /api/v1/assets/{id}/ -> /api/v1/assets/{id}/)

    Args:
        path: Request path

    Returns:
        Normalized endpoint pattern
    """
    # For now, use exact path matching
    # In future, could normalize UUIDs to {id} pattern
    return path.rstrip('/')

