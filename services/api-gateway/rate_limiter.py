"""
Rate Limiter for API Gateway

Implements Redis-based rate limiting using sliding window algorithm.
Supports per-tier, per-tenant, and per-user/API-key rate limits.
"""
import time
import os
from typing import Optional, Tuple, Dict
import redis
import structlog

logger = structlog.get_logger(__name__)


class RateLimitTier:
    """API tier rate limits (requests per hour)"""
    FREE = 1000
    PRO = 10000
    ENTERPRISE = None  # Unlimited (None means no limit)


class RateLimiter:
    """
    Redis-based rate limiter using sliding window algorithm.

    Uses Redis sorted sets to track request timestamps within the window.
    This prevents bursts at window boundaries (unlike fixed window).
    """

    def __init__(self, redis_url: Optional[str] = None):
        """
        Initialize rate limiter with Redis connection.

        Args:
            redis_url: Redis connection URL (defaults to REDIS_CACHE_URL or REDIS_URL env var)
        """
        if redis_url is None:
            redis_url = os.getenv('REDIS_CACHE_URL') or os.getenv('REDIS_URL', 'redis://localhost:6379/0')

        try:
            self.redis_client = redis.from_url(
                redis_url,
                decode_responses=False,  # Keep binary for sorted sets
                socket_connect_timeout=2,
                socket_timeout=2,
                retry_on_timeout=True
            )
            # Test connection
            self.redis_client.ping()
            logger.info("rate_limiter_redis_connected", redis_url=redis_url)
        except Exception as e:
            logger.error("rate_limiter_redis_connection_failed", error=str(e))
            self.redis_client = None

    def check_rate_limit(
        self,
        key: str,
        limit: Optional[int],
        window: int = 3600,  # 1 hour in seconds
        current_time: Optional[float] = None
    ) -> Tuple[bool, int, int]:
        """
        Check rate limit using sliding window algorithm.

        Args:
            key: Rate limit key (e.g., 'rate_limit:tier:free:tenant:123')
            limit: Maximum number of requests allowed in window (None = unlimited)
            window: Time window in seconds (default: 3600 = 1 hour)
            current_time: Current timestamp (for testing, defaults to time.time())

        Returns:
            Tuple of (is_allowed, current_count, reset_time)
            - is_allowed: True if request is allowed, False if rate limit exceeded
            - current_count: Current number of requests in window
            - reset_time: Unix timestamp when window resets (oldest request + window)
        """
        if limit is None:
            # Unlimited tier
            return True, 0, int((current_time or time.time()) + window)

        if self.redis_client is None:
            # If Redis is unavailable, allow request (fail open)
            logger.warning("rate_limiter_redis_unavailable", key=key)
            return True, 0, int((current_time or time.time()) + window)

        if current_time is None:
            current_time = time.time()

        try:
            # Remove expired entries (outside window) - Atomic operation
            window_start = current_time - window
            self.redis_client.zremrangebyscore(key, 0, window_start)

            # Count current requests in window - Atomic operation
            current_count = self.redis_client.zcard(key)

            if current_count >= limit:
                # Rate limit exceeded
                # Get oldest request timestamp to calculate reset time
                oldest = self.redis_client.zrange(key, 0, 0, withscores=True)
                if oldest:
                    oldest_timestamp = oldest[0][1]
                    reset_time = int(oldest_timestamp + window)
                else:
                    # No requests in window (shouldn't happen, but handle gracefully)
                    reset_time = int(current_time + window)

                return False, current_count, reset_time

            # Add current request to sorted set - Atomic operation
            request_id = f"{current_time}:{time.time_ns()}"  # Unique request ID
            self.redis_client.zadd(key, {request_id: current_time})

            # Set TTL to window duration + 1 hour (cleanup after window expires)
            # This ensures keys are cleaned up even if requests stop
            self.redis_client.expire(key, window + 3600)

            # Get reset time (oldest request + window, or current time + window if this is first)
            oldest = self.redis_client.zrange(key, 0, 0, withscores=True)
            if oldest:
                oldest_timestamp = oldest[0][1]
                reset_time = int(oldest_timestamp + window)
            else:
                reset_time = int(current_time + window)

            return True, current_count + 1, reset_time

        except Exception as e:
            logger.error("rate_limiter_redis_error", key=key, error=str(e))
            # Fail open on Redis errors
            return True, 0, int(current_time + window)

    def check_tier_limit(
        self,
        tier: str,
        current_time: Optional[float] = None
    ) -> Tuple[bool, int, int]:
        """
        Check rate limit for a tier.

        Args:
            tier: Tier name ('FREE', 'PRO', 'ENTERPRISE')
            current_time: Current timestamp (for testing)

        Returns:
            Tuple of (is_allowed, current_count, reset_time)
        """
        tier_upper = tier.upper()
        if tier_upper == 'FREE':
            limit = RateLimitTier.FREE
        elif tier_upper == 'PRO':
            limit = RateLimitTier.PRO
        elif tier_upper == 'ENTERPRISE':
            limit = RateLimitTier.ENTERPRISE
        else:
            # Default to FREE tier
            limit = RateLimitTier.FREE

        key = f"rate_limit:tier:{tier_upper.lower()}"
        return self.check_rate_limit(key, limit, window=3600, current_time=current_time)

    def check_tenant_limit(
        self,
        tenant_id: str,
        limit: Optional[int] = None,
        current_time: Optional[float] = None
    ) -> Tuple[bool, int, int]:
        """
        Check rate limit for a tenant.

        Args:
            tenant_id: Tenant UUID
            limit: Custom limit (if None, uses tier limit)
            current_time: Current timestamp (for testing)

        Returns:
            Tuple of (is_allowed, current_count, reset_time)
        """
        if limit is None:
            # No custom limit, skip tenant-level check
            return True, 0, int((current_time or time.time()) + 3600)

        key = f"rate_limit:tenant:{tenant_id}"
        return self.check_rate_limit(key, limit, window=3600, current_time=current_time)

    def check_api_key_limit(
        self,
        api_key_id: str,
        limit: Optional[int] = None,
        current_time: Optional[float] = None
    ) -> Tuple[bool, int, int]:
        """
        Check rate limit for an API key.

        Args:
            api_key_id: API key UUID
            limit: Custom limit (if None, uses tier limit)
            current_time: Current timestamp (for testing)

        Returns:
            Tuple of (is_allowed, current_count, reset_time)
        """
        if limit is None:
            # No custom limit, skip API key-level check
            return True, 0, int((current_time or time.time()) + 3600)

        key = f"rate_limit:api_key:{api_key_id}"
        return self.check_rate_limit(key, limit, window=3600, current_time=current_time)

    def get_rate_limit_info(
        self,
        key: str,
        window: int = 3600,
        current_time: Optional[float] = None
    ) -> Dict[str, int]:
        """
        Get rate limit information without incrementing counter.

        Args:
            key: Rate limit key
            window: Time window in seconds
            current_time: Current timestamp (for testing)

        Returns:
            Dictionary with 'count' and 'reset_time'
        """
        if self.redis_client is None:
            return {
                'count': 0,
                'reset_time': int((current_time or time.time()) + window),
            }

        if current_time is None:
            current_time = time.time()

        try:
            # Remove expired entries
            window_start = current_time - window
            self.redis_client.zremrangebyscore(key, 0, window_start)

            # Get current count
            count = self.redis_client.zcard(key)

            # Get reset time
            oldest = self.redis_client.zrange(key, 0, 0, withscores=True)
            if oldest:
                oldest_timestamp = oldest[0][1]
                reset_time = int(oldest_timestamp + window)
            else:
                reset_time = int(current_time + window)

            return {
                'count': count,
                'reset_time': reset_time,
            }
        except Exception as e:
            logger.error("rate_limiter_info_error", key=key, error=str(e))
            return {
                'count': 0,
                'reset_time': int(current_time + window),
            }
