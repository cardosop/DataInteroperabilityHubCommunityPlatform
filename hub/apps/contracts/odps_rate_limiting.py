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
from typing import Optional, Tuple, Dict, Any
from datetime import datetime, timedelta
import structlog

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

logger = structlog.get_logger(__name__)

# Rate limit constants
RATE_LIMIT_PER_TENANT = 100  # requests per hour
RATE_LIMIT_PER_USER = 50     # requests per hour
RATE_LIMIT_GLOBAL = 1000     # requests per hour

# Time window: 1 hour in seconds
RATE_LIMIT_WINDOW = 3600  # 1 hour

# Redis key prefixes
REDIS_KEY_PREFIX_TENANT = "odps_ref_rate_limit:tenant"
REDIS_KEY_PREFIX_USER = "odps_ref_rate_limit:user"
REDIS_KEY_PREFIX_GLOBAL = "odps_ref_rate_limit:global"


class ODPSRefResolutionError(Exception):
    """
    Exception raised when ODPS $ref resolution fails due to rate limiting or other errors.

    Attributes:
        message: Error message
        retry_after: Unix timestamp when the rate limit resets (for rate limit errors)
        error_code: Error code for programmatic handling
        tenant_id: Tenant ID (if applicable)
        user_id: User ID (if applicable)
    """

    ERROR_CODE_RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    ERROR_CODE_RESOLUTION_FAILED = "RESOLUTION_FAILED"
    ERROR_CODE_INVALID_REF = "INVALID_REF"
    ERROR_CODE_SECURITY_VIOLATION = "SECURITY_VIOLATION"

    def __init__(
        self,
        message: str,
        retry_after: Optional[int] = None,
        error_code: str = ERROR_CODE_RESOLUTION_FAILED,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None
    ):
        """
        Initialize ODPS ref resolution error.

        Args:
            message: Error message
            retry_after: Unix timestamp when rate limit resets (for rate limit errors)
            error_code: Error code for programmatic handling
            tenant_id: Tenant ID (if applicable)
            user_id: User ID (if applicable)
        """
        super().__init__(message)
        self.message = message
        self.retry_after = retry_after
        self.error_code = error_code
        self.tenant_id = tenant_id
        self.user_id = user_id

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert error to dictionary for API responses.

        Returns:
            Dictionary with error details including retry_after header value
        """
        result = {
            "error": self.error_code,
            "message": self.message,
        }

        if self.tenant_id:
            result["tenant_id"] = self.tenant_id
        if self.user_id:
            result["user_id"] = self.user_id
        if self.retry_after:
            # Calculate seconds until retry
            current_time = int(time.time())
            retry_seconds = max(0, self.retry_after - current_time)
            result["retry_after"] = retry_seconds
            result["retry_after_timestamp"] = self.retry_after

        return result

    def get_retry_after_header(self) -> Optional[str]:
        """
        Get Retry-After header value (seconds until retry).

        Returns:
            Retry-After header value as string (seconds), or None if not applicable
        """
        if self.retry_after is None:
            return None

        current_time = int(time.time())
        retry_seconds = max(0, self.retry_after - current_time)
        return str(retry_seconds)


def generate_rate_limit_key(
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    level: str = "tenant"
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
    current_time = int(time.time())
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
        raise ValueError(f"Invalid rate limit level: {level}. Must be 'tenant', 'user', or 'global'")


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
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    redis_client: Optional[Any] = None
) -> Tuple[bool, Optional[ODPSRefResolutionError]]:
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

    # Get Redis client
    if redis_client is None:
        try:
            from django.conf import settings
            redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')
            redis_client = redis.from_url(redis_url, decode_responses=False, socket_connect_timeout=0.1)
        except Exception as e:
            logger.error("rate_limit_redis_connection_error", error=str(e))
            # Fail open if Redis is unavailable
            return True, None

    current_time = time.time()

    # Check global limit first (most restrictive)
    try:
        global_key = generate_rate_limit_key(level="global")
        global_limit = get_rate_limit("global")
        is_allowed, count, reset_time = _check_single_limit(
            redis_client, global_key, global_limit, current_time
        )
        if not is_allowed:
            error = ODPSRefResolutionError(
                message=f"Global ODPS $ref resolution rate limit exceeded: {count}/{global_limit} requests per hour",
                retry_after=reset_time,
                error_code=ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED
            )
            logger.warning(
                "odps_ref_rate_limit_exceeded",
                level="global",
                count=count,
                limit=global_limit,
                reset_time=reset_time
            )
            return False, error
    except Exception as e:
        logger.error("rate_limit_check_error", level="global", error=str(e))
        # Fail open on errors
        pass

    # Check tenant limit
    if tenant_id:
        try:
            tenant_key = generate_rate_limit_key(tenant_id=tenant_id, level="tenant")
            tenant_limit = get_rate_limit("tenant")
            is_allowed, count, reset_time = _check_single_limit(
                redis_client, tenant_key, tenant_limit, current_time
            )
            if not is_allowed:
                error = ODPSRefResolutionError(
                    message=f"Tenant ODPS $ref resolution rate limit exceeded: {count}/{tenant_limit} requests per hour",
                    retry_after=reset_time,
                    error_code=ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED,
                    tenant_id=tenant_id
                )
                logger.warning(
                    "odps_ref_rate_limit_exceeded",
                    level="tenant",
                    tenant_id=tenant_id,
                    count=count,
                    limit=tenant_limit,
                    reset_time=reset_time
                )
                return False, error
        except Exception as e:
            logger.error("rate_limit_check_error", level="tenant", error=str(e))
            # Fail open on errors
            pass

    # Check user limit
    if tenant_id and user_id:
        try:
            user_key = generate_rate_limit_key(tenant_id=tenant_id, user_id=user_id, level="user")
            user_limit = get_rate_limit("user")
            is_allowed, count, reset_time = _check_single_limit(
                redis_client, user_key, user_limit, current_time
            )
            if not is_allowed:
                error = ODPSRefResolutionError(
                    message=f"User ODPS $ref resolution rate limit exceeded: {count}/{user_limit} requests per hour",
                    retry_after=reset_time,
                    error_code=ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED,
                    tenant_id=tenant_id,
                    user_id=user_id
                )
                logger.warning(
                    "odps_ref_rate_limit_exceeded",
                    level="user",
                    tenant_id=tenant_id,
                    user_id=user_id,
                    count=count,
                    limit=user_limit,
                    reset_time=reset_time
                )
                return False, error
        except Exception as e:
            logger.error("rate_limit_check_error", level="user", error=str(e))
            # Fail open on errors
            pass

    # All checks passed
    return True, None


def _check_single_limit(
    redis_client: Any,
    key: str,
    limit: int,
    current_time: float
) -> Tuple[bool, int, int]:
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

    except Exception as e:
        logger.error("rate_limit_redis_error", key=key, error=str(e))
        # Fail open on Redis errors
        return True, 0, int(current_time + RATE_LIMIT_WINDOW)


def get_rate_limit_info(
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    redis_client: Optional[Any] = None
) -> Dict[str, Any]:
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
            redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')
            redis_client = redis.from_url(redis_url, decode_responses=False, socket_connect_timeout=0.1)
        except Exception:
            return {}

    current_time = time.time()
    result = {}

    # Get global limit info
    try:
        global_key = generate_rate_limit_key(level="global")
        global_limit = get_rate_limit("global")
        global_info = _get_limit_info(redis_client, global_key, global_limit, current_time)
        result["global"] = global_info
    except Exception:
        pass

    # Get tenant limit info
    if tenant_id:
        try:
            tenant_key = generate_rate_limit_key(tenant_id=tenant_id, level="tenant")
            tenant_limit = get_rate_limit("tenant")
            tenant_info = _get_limit_info(redis_client, tenant_key, tenant_limit, current_time)
            result["tenant"] = tenant_info
        except Exception:
            pass

    # Get user limit info
    if tenant_id and user_id:
        try:
            user_key = generate_rate_limit_key(tenant_id=tenant_id, user_id=user_id, level="user")
            user_limit = get_rate_limit("user")
            user_info = _get_limit_info(redis_client, user_key, user_limit, current_time)
            result["user"] = user_info
        except Exception:
            pass

    return result


def _get_limit_info(
    redis_client: Any,
    key: str,
    limit: int,
    current_time: float
) -> Dict[str, int]:
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
            "reset_time": reset_time
        }
    except Exception:
        return {
            "count": 0,
            "limit": limit,
            "remaining": limit,
            "reset_time": int(current_time + RATE_LIMIT_WINDOW)
        }

