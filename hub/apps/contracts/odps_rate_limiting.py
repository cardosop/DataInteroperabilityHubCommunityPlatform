"""
ODPS $ref Resolution Rate Limiting

Provides Redis-based rate limiting for ODPS $ref resolution to prevent abuse
and ensure fair resource usage across tenants and users.

Rate limiting is enforced at three levels:
1. Per-tenant: 100 requests per hour
2. Per-user: 50 requests per hour
3. Global: 1000 requests per hour

Uses sliding window algorithm with Redis sorted sets for accurate rate limiting.
"""

import time
from typing import Any

import structlog

# Import ODPSRefResolutionError from the error hierarchy
from hub.apps.contracts.odps_errors import ODPSRefResolutionError
from hub.apps.observability.otel_metrics import odps_rate_limit_violations_total

try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

logger = structlog.get_logger(__name__)

# Rate limit constants
RATE_LIMIT_PER_TENANT = 100  # requests per hour
RATE_LIMIT_PER_USER = 50  # requests per hour
RATE_LIMIT_GLOBAL = 1000  # requests per hour

# Time window: 1 hour in seconds
RATE_LIMIT_WINDOW = 3600  # 1 hour

# Redis key prefixes
REDIS_KEY_PREFIX_TENANT = "odps_ref_rate_limit:tenant"
REDIS_KEY_PREFIX_USER = "odps_ref_rate_limit:user"
REDIS_KEY_PREFIX_GLOBAL = "odps_ref_rate_limit:global"


def generate_rate_limit_key(
    tenant_id: str | None = None,
    user_id: str | None = None,
    level: str = "tenant",
    timestamp: int | None = None,
) -> str:
    """
    Generate Redis key for ODPS $ref rate limiting.

    Key format:
    - Per-tenant: `odps_ref_rate_limit:tenant:{tenant_id}:{hour}`
    - Per-user: `odps_ref_rate_limit:user:{tenant_id}:{user_id}:{hour}`
    - Global: `odps_ref_rate_limit:global:{hour}`

    The `{hour}` component is the current hour as Unix timestamp (rounded down to hour).
    This creates 1-hour windows that reset at the top of each hour.

    Args:
        tenant_id: Tenant UUID (required for tenant and user levels)
        user_id: User UUID (required for user level)
        level: Rate limit level - "tenant", "user", or "global"
        timestamp: Optional Unix timestamp for key generation (for testing). If None, uses time.time().

    Returns:
        Redis key string

    Raises:
        ValueError: If required parameters are missing

    Example:
        >>> key = generate_rate_limit_key(tenant_id="123", level="tenant")
        >>> print(key)
        'odps_ref_rate_limit:tenant:123:1704067200'

        >>> key = generate_rate_limit_key(tenant_id="123", user_id="456", level="user")
        >>> print(key)
        'odps_ref_rate_limit:user:123:456:1704067200'

        >>> key = generate_rate_limit_key(level="global")
        >>> print(key)
        'odps_ref_rate_limit:global:1704067200'
    """
    # Get current hour as Unix timestamp (rounded down to hour)
    current_time = int(timestamp if timestamp is not None else time.time())
    current_hour = (current_time // RATE_LIMIT_WINDOW) * RATE_LIMIT_WINDOW

    if level == "global":
        return f"{REDIS_KEY_PREFIX_GLOBAL}:{current_hour}"
    elif level == "tenant":
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant-level rate limiting")
        return f"{REDIS_KEY_PREFIX_TENANT}:{tenant_id}:{current_hour}"
    elif level == "user":
        if not tenant_id:
            raise ValueError("tenant_id is required for user-level rate limiting")
        if not user_id:
            raise ValueError("user_id is required for user-level rate limiting")
        return f"{REDIS_KEY_PREFIX_USER}:{tenant_id}:{user_id}:{current_hour}"
    else:
        raise ValueError(
            f"Invalid rate limit level: {level}. Must be 'tenant', 'user', or 'global'"
        )


def get_rate_limit(level: str) -> int:
    """
    Get rate limit for a given level.

    Args:
        level: Rate limit level - "tenant", "user", or "global"

    Returns:
        Rate limit (requests per hour)

    Raises:
        ValueError: If level is invalid
    """
    if level == "tenant":
        return RATE_LIMIT_PER_TENANT
    elif level == "user":
        return RATE_LIMIT_PER_USER
    elif level == "global":
        return RATE_LIMIT_GLOBAL
    else:
        raise ValueError(f"Invalid rate limit level: {level}")


def check_rate_limit(
    tenant_id: str | None = None, user_id: str | None = None, redis_client: Any | None = None
) -> tuple[bool, ODPSRefResolutionError | None]:
    """
    Check if ODPS $ref resolution request is within rate limits.

    Checks rate limits at three levels:
    1. Global limit (1000/hour)
    2. Tenant limit (100/hour)
    3. User limit (50/hour)

    All three limits must pass for the request to be allowed.

    Args:
        tenant_id: Tenant UUID (required for tenant and user checks)
        user_id: User UUID (optional, for user-level checks)
        redis_client: Optional Redis client. If None, creates a new connection.

    Returns:
        Tuple of (is_allowed, error)
        - is_allowed: True if request is allowed, False if rate limit exceeded
        - error: ODPSRefResolutionError if rate limit exceeded, None otherwise

    Example:
        >>> is_allowed, error = check_rate_limit(tenant_id="123", user_id="456")
        >>> if not is_allowed:
        ...     print(f"Rate limit exceeded: {error.message}")
        ...     print(f"Retry after: {error.get_retry_after_header()} seconds")
    """
    if not REDIS_AVAILABLE:
        # If Redis is not available, allow request (fail open)
        logger.warning("Redis not available for rate limiting, allowing request")
        return True, None

    # Reject None or empty tenant_id for security: unauthenticated/unscoped requests must be denied.
    # CI/CLI contexts should pass a sentinel (e.g. "system") if they need to bypass tenant checks.
    if tenant_id is None or (isinstance(tenant_id, str) and not tenant_id.strip()):
        error = ODPSRefResolutionError(
            message="tenant_id is required for ODPS $ref rate limiting",
            error_code=ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED,
        )
        return False, error

    # Get Redis client
    if redis_client is None:
        try:
            from django.conf import settings

            redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
            redis_client = redis.from_url(
                redis_url, decode_responses=False, socket_connect_timeout=0.1
            )
        except (redis.RedisError, ValueError) as e:
            logger.warning("rate_limit_redis_connection_error", error=str(e))
            # Fail open if Redis is unavailable
            return True, None

    current_time = time.time()

    # Check limits in order: global (most restrictive), tenant, then user.
    levels: list[tuple[str, str, int]] = [
        ("global", generate_rate_limit_key(level="global"), get_rate_limit("global")),
    ]
    if tenant_id:
        levels.append(
            (
                "tenant",
                generate_rate_limit_key(tenant_id=tenant_id, level="tenant"),
                get_rate_limit("tenant"),
            )
        )
    if tenant_id and user_id:
        levels.append(
            (
                "user",
                generate_rate_limit_key(tenant_id=tenant_id, user_id=user_id, level="user"),
                get_rate_limit("user"),
            )
        )

    for level, key, limit in levels:
        is_allowed, error = _check_rate_limit_level(
            level=level,
            key=key,
            limit=limit,
            current_time=current_time,
            tenant_id=tenant_id,
            user_id=user_id,
            redis_client=redis_client,
        )
        if not is_allowed:
            return False, error

    # All checks passed
    return True, None

    # Tenant-level check runs below via the shared per-level helper
    # (skipped when no tenant context, e.g. ref resolution in CI/CLI).

    # User-level check runs below via the shared per-level helper
    # (skipped when no tenant/user context).


def _check_rate_limit_level(
    level: str,
    key: str,
    limit: int,
    current_time: float,
    tenant_id: str | None,
    user_id: str | None,
    redis_client: Any,
) -> tuple[bool, ODPSRefResolutionError | None]:
    """
    Check a single rate-limit level.

    Returns (True, None) when the request is allowed at this level or when
    the Redis check fails (fail open), and (False, error) when the limit
    is exceeded.

    Args:
        level: Rate limit level - "tenant", "user", or "global"
        key: Redis key for this level
        limit: Maximum number of requests allowed per window
        current_time: Current timestamp
        tenant_id: Tenant UUID (None for global checks)
        user_id: User UUID (None for global and tenant checks)
        redis_client: Redis client

    Returns:
        Tuple of (is_allowed, error)
    """
    try:
        is_allowed, count, reset_time = _check_single_limit(redis_client, key, limit, current_time)
    except (redis.RedisError, ValueError) as e:
        logger.warning("rate_limit_check_error", level=level, error=str(e))
        # Fail open on errors
        return True, None

    if is_allowed:
        return True, None

    retry_seconds = max(0, int(reset_time - current_time))
    retry_after_minutes = (retry_seconds + 59) // 60  # Round up to minutes
    error = ODPSRefResolutionError(
        message=(
            f"{level.capitalize()} ODPS $ref resolution rate limit exceeded: "
            f"{count}/{limit} requests per hour. Please retry after "
            f"{retry_after_minutes} minute(s) (at {reset_time})"
        ),
        retry_after=reset_time,
        error_code=ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED,
        tenant_id=tenant_id if level in ("tenant", "user") else None,
        user_id=user_id if level == "user" else None,
    )
    log_kwargs: dict[str, Any] = {
        "level": level,
        "count": count,
        "limit": limit,
        "reset_time": reset_time,
    }
    if level in ("tenant", "user"):
        log_kwargs["tenant_id"] = tenant_id
    if level == "user":
        log_kwargs["user_id"] = user_id
    logger.warning("odps_ref_rate_limit_exceeded", **log_kwargs)
    # Track rate limit violation metrics
    try:
        odps_rate_limit_violations_total.labels(
            level=level,
            tenant_id=tenant_id or "unknown",
            user_id=(user_id or "") if level == "user" else "",
        ).inc()
    except Exception as metrics_err:
        logger.debug(
            "odps_rate_limit_metrics_failed",
            extra={
                "error_type": type(metrics_err).__name__,
                "error": str(metrics_err),
                "level": level,
            },
        )
    return False, error


def _check_single_limit(
    redis_client: Any, key: str, limit: int, current_time: float
) -> tuple[bool, int, int]:
    """
    Check a single rate limit using sliding window algorithm.

    Uses Redis sorted sets to track request timestamps within the window.
    This prevents bursts at window boundaries (unlike fixed window).

    Args:
        redis_client: Redis client
        key: Rate limit key
        limit: Maximum number of requests allowed
        current_time: Current timestamp

    Returns:
        Tuple of (is_allowed, current_count, reset_time)
        - is_allowed: True if request is allowed, False if rate limit exceeded
        - current_count: Current number of requests in window
        - reset_time: Unix timestamp when window resets
    """
    window_start = current_time - RATE_LIMIT_WINDOW

    try:
        # Remove expired entries (outside window) - Atomic operation
        redis_client.zremrangebyscore(key, 0, window_start)

        # Count current requests in window - Atomic operation
        current_count = redis_client.zcard(key)

        if current_count >= limit:
            # Rate limit exceeded
            # Get oldest request timestamp to calculate reset time
            oldest = redis_client.zrange(key, 0, 0, withscores=True)
            if oldest:
                oldest_timestamp = oldest[0][1]
                reset_time = int(oldest_timestamp + RATE_LIMIT_WINDOW)
            else:
                # No requests in window (shouldn't happen, but handle gracefully)
                reset_time = int(current_time + RATE_LIMIT_WINDOW)

            return False, current_count, reset_time

        # Add current request to sorted set - Atomic operation
        request_id = f"{current_time}:{time.time_ns()}"  # Unique request ID
        redis_client.zadd(key, {request_id: current_time})

        # Set TTL to window duration + 1 hour (cleanup after window expires)
        # This ensures keys are cleaned up even if requests stop
        redis_client.expire(key, RATE_LIMIT_WINDOW + 3600)

        # Get reset time (oldest request + window, or current time + window if this is first)
        oldest = redis_client.zrange(key, 0, 0, withscores=True)
        if oldest:
            oldest_timestamp = oldest[0][1]
            reset_time = int(oldest_timestamp + RATE_LIMIT_WINDOW)
        else:
            reset_time = int(current_time + RATE_LIMIT_WINDOW)

        return True, current_count + 1, reset_time

    except (redis.RedisError, ValueError) as e:
        logger.warning("rate_limit_redis_error", key=key, error=str(e))
        # Fail open on Redis errors
        return True, 0, int(current_time + RATE_LIMIT_WINDOW)


def get_rate_limit_info(
    tenant_id: str | None = None, user_id: str | None = None, redis_client: Any | None = None
) -> dict[str, Any]:
    """
    Get rate limit information without incrementing counters.

    Useful for checking current usage before making requests.

    Args:
        tenant_id: Tenant UUID (optional)
        user_id: User UUID (optional)
        redis_client: Optional Redis client. If None, creates a new connection.

    Returns:
        Dictionary with rate limit information:
        - global: {count, limit, remaining, reset_time}
        - tenant: {count, limit, remaining, reset_time} (if tenant_id provided)
        - user: {count, limit, remaining, reset_time} (if tenant_id and user_id provided)
    """
    if not REDIS_AVAILABLE:
        return {}

    # Get Redis client
    if redis_client is None:
        try:
            from django.conf import settings

            redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
            redis_client = redis.from_url(
                redis_url, decode_responses=False, socket_connect_timeout=0.1
            )
        except (redis.RedisError, ValueError) as e:
            logger.warning(
                "rate_limit_info_redis_connection_error",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            return {}

    current_time = time.time()
    result = {}

    # Get global limit info
    try:
        global_key = generate_rate_limit_key(level="global")
        global_limit = get_rate_limit("global")
        global_info = _get_limit_info(redis_client, global_key, global_limit, current_time)
        result["global"] = global_info
    except (redis.RedisError, ValueError, TypeError) as e:
        logger.debug(
            "rate_limit_info_global_failed", extra={"error_type": type(e).__name__, "error": str(e)}
        )

    # Get tenant limit info
    if tenant_id:
        try:
            tenant_key = generate_rate_limit_key(tenant_id=tenant_id, level="tenant")
            tenant_limit = get_rate_limit("tenant")
            tenant_info = _get_limit_info(redis_client, tenant_key, tenant_limit, current_time)
            result["tenant"] = tenant_info
        except (redis.RedisError, ValueError, TypeError) as e:
            logger.debug(
                "rate_limit_info_tenant_failed",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )

    # Get user limit info
    if tenant_id and user_id:
        try:
            user_key = generate_rate_limit_key(tenant_id=tenant_id, user_id=user_id, level="user")
            user_limit = get_rate_limit("user")
            user_info = _get_limit_info(redis_client, user_key, user_limit, current_time)
            result["user"] = user_info
        except (redis.RedisError, ValueError, TypeError) as e:
            logger.debug(
                "rate_limit_info_user_failed",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )

    return result


def _get_limit_info(redis_client: Any, key: str, limit: int, current_time: float) -> dict[str, int]:
    """
    Get rate limit information for a single limit.

    Args:
        redis_client: Redis client
        key: Rate limit key
        limit: Maximum number of requests allowed
        current_time: Current timestamp

    Returns:
        Dictionary with count, limit, remaining, and reset_time
    """
    window_start = current_time - RATE_LIMIT_WINDOW

    try:
        # Remove expired entries
        redis_client.zremrangebyscore(key, 0, window_start)

        # Get current count
        count = redis_client.zcard(key)

        # Get reset time
        oldest = redis_client.zrange(key, 0, 0, withscores=True)
        if oldest:
            oldest_timestamp = oldest[0][1]
            reset_time = int(oldest_timestamp + RATE_LIMIT_WINDOW)
        else:
            reset_time = int(current_time + RATE_LIMIT_WINDOW)

        return {
            "count": count,
            "limit": limit,
            "remaining": max(0, limit - count),
            "reset_time": reset_time,
        }
    except (redis.RedisError, ValueError) as e:
        logger.debug(
            "rate_limit_get_limit_info_failed",
            extra={"error_type": type(e).__name__, "error": str(e), "key": key},
        )
        return {
            "count": 0,
            "limit": limit,
            "remaining": limit,
            "reset_time": int(current_time + RATE_LIMIT_WINDOW),
        }
