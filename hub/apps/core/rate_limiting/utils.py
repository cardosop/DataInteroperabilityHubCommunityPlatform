"""
Rate Limiting Utilities

Core utilities for rate limiting with sliding window algorithm.
"""

import time

import structlog
from django.core.cache import cache

logger = structlog.get_logger(__name__)


# Endpoint categories for rate limiting
class EndpointCategory:
    """Endpoint categories for rate limiting"""

    AUTH = "auth"  # Authentication endpoints (login, register, etc.)
    ASSET = "asset"  # Asset management endpoints (create, update, delete)
    CONTRACT = "contract"  # Contract management endpoints (create, update, delete)
    SEARCH = "search"  # Search endpoints
    DQ_RUN = "dq_run"
    COMPLIANCE_RUN = "compliance_run"
    FILE_UPLOAD = "file_upload"
    FILE_DOWNLOAD = "file_download"
    CONTRACT_VALIDATION = "contract_validation"
    CATALOG_READ = "catalog_read"
    SPARQL_QUERY = "sparql_query"
    GENERAL = "general"  # Default category for uncategorized endpoints


# Time windows for rate limiting (in seconds)
class TimeWindow:
    """Time windows for rate limiting"""

    BURST = 10  # 10 seconds
    SUSTAINED = 60  # 1 minute
    DAILY = 86400  # 24 hours


def get_endpoint_category(path: str, method: str) -> str:
    """
    Determine endpoint category from request path and method.

    Args:
        path: Request path (e.g., '/api/v1/dq/runs/')
        method: HTTP method (e.g., 'POST', 'GET')

    Returns:
        Endpoint category string
    """
    path_lower = path.lower()

    # Authentication endpoints (login, register, password reset, etc.)
    if "/api/v1/auth/" in path_lower or path_lower.startswith("/auth/"):
        return EndpointCategory.AUTH

    # Search endpoints
    if "/api/v1/search/" in path_lower or path_lower.startswith("/search/"):
        return EndpointCategory.SEARCH

    # DQ runs - POST creates runs, GET lists/retrieves runs
    if "/dq/runs" in path_lower:
        if method == "POST":
            return EndpointCategory.DQ_RUN
        elif method == "GET":
            # GET requests for listing/retrieving runs are catalog reads
            return EndpointCategory.CATALOG_READ

    # Compliance runs - POST creates runs, GET lists/retrieves runs
    if "/compliance/runs" in path_lower:
        if method == "POST":
            return EndpointCategory.COMPLIANCE_RUN
        elif method == "GET":
            # GET requests for listing/retrieving runs are catalog reads
            return EndpointCategory.CATALOG_READ

    # File uploads
    if "/files" in path_lower and method in ("POST", "PUT"):
        return EndpointCategory.FILE_UPLOAD

    # File downloads
    if "/files" in path_lower and method == "GET" and "/download" in path_lower:
        return EndpointCategory.FILE_DOWNLOAD

    # Contract validation
    if "/contracts" in path_lower and "/validate" in path_lower:
        return EndpointCategory.CONTRACT_VALIDATION

    # Asset management endpoints (create, update, delete)
    if "/api/v1/assets/" in path_lower:
        if method in ("POST", "PUT", "PATCH", "DELETE"):
            return EndpointCategory.ASSET
        elif method == "GET":
            # GET requests are catalog reads
            return EndpointCategory.CATALOG_READ

    # Contract management endpoints (create, update, delete)
    if "/api/v1/contracts/" in path_lower:
        if method in ("POST", "PUT", "PATCH", "DELETE"):
            return EndpointCategory.CONTRACT
        elif method == "GET":
            # GET requests are catalog reads
            return EndpointCategory.CATALOG_READ

    # Catalog reads (GET requests for assets, contracts, etc.)
    if ("/catalog" in path_lower or "/assets" in path_lower) and method == "GET":
        return EndpointCategory.CATALOG_READ

    # SPARQL queries
    if ("/sparql" in path_lower or "/semantic" in path_lower) and method in ("POST", "GET"):
        return EndpointCategory.SPARQL_QUERY

    # Default to general category
    return EndpointCategory.GENERAL


def generate_rate_limit_key(
    tenant_id: str | None = None,
    user_id: str | None = None,
    api_key_id: str | None = None,
    endpoint_category: str = EndpointCategory.GENERAL,
    window: int = TimeWindow.SUSTAINED,
) -> str:
    """
    Generate rate limit key for Redis storage.

    Key hierarchy:
    - Tenant-level: `rate_limit:tenant:{tenant_id}:{category}:{window}`
    - User-level: `rate_limit:tenant:{tenant_id}:user:{user_id}:{category}:{window}`
    - API-key-level: `rate_limit:tenant:{tenant_id}:apikey:{api_key_id}:{category}:{window}`

    Args:
        tenant_id: Tenant UUID (required)
        user_id: User UUID (optional, for per-user limits)
        api_key_id: API key UUID (optional, for per-API-key limits)
        endpoint_category: Endpoint category
        window: Time window in seconds

    Returns:
        Rate limit key string
    """
    if not tenant_id:
        raise ValueError("tenant_id is required for rate limit key generation")

    if api_key_id:
        return f"rate_limit:tenant:{tenant_id}:apikey:{api_key_id}:{endpoint_category}:{window}"
    elif user_id:
        return f"rate_limit:tenant:{tenant_id}:user:{user_id}:{endpoint_category}:{window}"
    else:
        return f"rate_limit:tenant:{tenant_id}:{endpoint_category}:{window}"


def sliding_window_check(
    key: str, limit: int, window: int, current_time: float | None = None
) -> tuple[bool, int, int]:
    """
    Check rate limit using sliding window algorithm with Redis sorted sets.

    Uses Redis sorted sets to track request timestamps within the window.
    This prevents bursts at window boundaries (unlike fixed window).

    Implements caching (1 second) to reduce Redis calls for performance.

    Args:
        key: Rate limit key
        limit: Maximum number of requests allowed in window
        window: Time window in seconds
        current_time: Current timestamp (for testing, defaults to time.time())

    Returns:
        Tuple of (is_allowed, current_count, reset_time)
        - is_allowed: True if request is allowed, False if rate limit exceeded
        - current_count: Current number of requests in window
        - reset_time: Unix timestamp when window resets (oldest request + window)
    """
    if current_time is None:
        current_time = time.time()

    # Cache window counts briefly (1 second) to reduce Redis calls - Phase 4.1.2
    cache_key = f"rate_limit_cache:{key}"
    cache_ttl = 1  # 1 second cache
    cached_data = None
    try:
        cached_data = cache.get(cache_key)
    except Exception:
        # If cache is unavailable, continue without cache (fail open)
        pass

    if cached_data:
        cached_count, cached_time, cached_reset = cached_data
        # Use cached data if less than 1 second old
        if current_time - cached_time < cache_ttl:
            # Still need to check if limit exceeded
            if cached_count >= limit:
                return False, cached_count, cached_reset
            # If within limit, still need to add request (can't use cache for increment)
            # But we can use it to avoid the initial count check

    # Use Redis sorted set for sliding window
    # Key: rate limit key
    # Score: request timestamp
    # Value: request ID (unique per request)

    # Get Redis client from cache instance (rate limiting uses cache Redis)
    try:
        import redis

        from hub.apps.core.redis_pools import get_redis_cache_pool

        pool = get_redis_cache_pool()
        redis_client = redis.Redis(
            connection_pool=pool, decode_responses=False
        )  # Keep binary for sorted sets
    except (ImportError, Exception):
        # Fallback to direct connection if redis_pools not available
        try:
            from django.conf import settings

            redis_url = getattr(settings, "REDIS_CACHE_URL", None)
            if redis_url is None:
                redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
            redis_client = redis.from_url(
                redis_url, decode_responses=False, socket_connect_timeout=0.1
            )  # Keep binary for sorted sets, short timeout
        except Exception as e2:
            logger.warning("rate_limit_redis_error", error=str(e2))
            # If Redis is unavailable, allow request (fail open)
            return True, 0, int(current_time + window)

    # Try to use Redis - this will fail if connection is invalid
    try:
        # Remove expired entries (outside window) - Atomic operation
        window_start = current_time - window
        redis_client.zremrangebyscore(key, 0, window_start)
    except Exception as e:
        logger.warning("rate_limit_redis_error", error=str(e))
        # If Redis operations fail, allow request (fail open)
        return True, 0, int(current_time + window)

    # Count current requests in window - Atomic operation
    current_count = redis_client.zcard(key)

    if current_count >= limit:
        # Rate limit exceeded
        # Get oldest request timestamp to calculate reset time
        oldest = redis_client.zrange(key, 0, 0, withscores=True)
        if oldest:
            oldest_timestamp = oldest[0][1]
            reset_time = int(oldest_timestamp + window)
        else:
            reset_time = int(current_time + window)

        # Cache the result (fail silently if cache unavailable)
        try:
            cache.set(cache_key, (current_count, current_time, reset_time), cache_ttl)
        except Exception:
            pass  # Cache failure shouldn't break rate limiting

        return False, current_count, reset_time

    # Add current request to sorted set - Atomic operation
    request_id = f"{current_time}:{time.time_ns()}"  # Unique request ID
    redis_client.zadd(key, {request_id: current_time})

    # Set expiration on the sorted set (window + small buffer)
    redis_client.expire(key, window + 10)

    # Recalculate count after adding - Atomic operation
    current_count = redis_client.zcard(key)

    # Calculate reset time (oldest request + window)
    oldest = redis_client.zrange(key, 0, 0, withscores=True)
    if oldest:
        oldest_timestamp = oldest[0][1]
        reset_time = int(oldest_timestamp + window)
    else:
        reset_time = int(current_time + window)

    # Cache the result (1 second TTL) - Phase 4.1.2 (fail silently if cache unavailable)
    try:
        cache.set(cache_key, (current_count, current_time, reset_time), cache_ttl)
    except Exception:
        pass  # Cache failure shouldn't break rate limiting

    return True, current_count, reset_time


def get_rate_limit_info(key: str, window: int, current_time: float | None = None) -> dict[str, int]:
    """
    Get rate limit information without incrementing counter.

    Args:
        key: Rate limit key
        window: Time window in seconds
        current_time: Current timestamp (for testing)

    Returns:
        Dictionary with 'count', 'reset_time', and 'remaining' (if limit is known)
    """
    if current_time is None:
        current_time = time.time()

    # Get Redis client from cache instance (rate limiting uses cache Redis)
    try:
        import redis

        from hub.apps.core.redis_pools import get_redis_cache_pool

        pool = get_redis_cache_pool()
        redis_client = redis.Redis(
            connection_pool=pool, decode_responses=False
        )  # Keep binary for sorted sets
    except (ImportError, Exception):
        # Fallback to direct connection if redis_pools not available
        try:
            import redis
            from django.conf import settings

            redis_url = getattr(settings, "REDIS_CACHE_URL", None)
            if redis_url is None:
                redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
            redis_client = redis.from_url(
                redis_url, decode_responses=False
            )  # Keep binary for sorted sets
        except Exception:
            # If Redis is unavailable, return default values
            return {
                "count": 0,
                "reset_time": int(current_time + window),
            }

    # Remove expired entries
    window_start = current_time - window
    redis_client.zremrangebyscore(key, 0, window_start)

    # Get current count
    count = redis_client.zcard(key)

    # Get reset time
    oldest = redis_client.zrange(key, 0, 0, withscores=True)
    if oldest:
        oldest_timestamp = oldest[0][1]
        reset_time = int(oldest_timestamp + window)
    else:
        reset_time = int(current_time + window)

    return {
        "count": count,
        "reset_time": reset_time,
    }
