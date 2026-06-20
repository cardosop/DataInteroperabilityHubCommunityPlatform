"""
Redis Connection Pool Utilities

Provides connection pools for each Redis instance (cache, queue, events, channels)
with proper configuration and health checks.

This module implements per-instance connection pooling as specified in the
Redis Instance Separation Design.
"""

import logging

import redis
from django.conf import settings

logger = logging.getLogger(__name__)

# Global connection pools (lazy initialization)
_redis_cache_pool: redis.ConnectionPool | None = None
_redis_queue_pool: redis.ConnectionPool | None = None
_redis_events_pool: redis.ConnectionPool | None = None
_redis_channels_pool: redis.ConnectionPool | None = None


def _get_redis_url_with_fallback(
    env_var: str, default_port: int, fallback_env_var: str = "REDIS_URL"
) -> str:
    """
    Get Redis URL from environment variable with fallback to REDIS_URL.

    Args:
        env_var: Primary environment variable name (e.g., "REDIS_CACHE_URL")
        default_port: Default port if not specified in URL
        fallback_env_var: Fallback environment variable (default: "REDIS_URL")

    Returns:
        Redis URL string
    """
    # Try primary environment variable first
    redis_url = getattr(settings, env_var, None)
    if redis_url:
        return redis_url

    # Fallback to REDIS_URL for backward compatibility
    fallback_url = getattr(settings, fallback_env_var, None)
    if fallback_url:
        logger.info(
            f"Using {fallback_env_var} as fallback for {env_var}",
            extra={"env_var": env_var, "fallback_env_var": fallback_env_var},
        )
        return fallback_url

    # Default fallback
    return f"redis://localhost:{default_port}/0"


def get_redis_cache_pool() -> redis.ConnectionPool:
    """
    Get or create Redis cache connection pool.

    Returns:
        Redis connection pool configured for cache instance
    """
    global _redis_cache_pool

    if _redis_cache_pool is None:
        redis_url = _get_redis_url_with_fallback("REDIS_CACHE_URL", 6379)

        # Cache pool configuration (read-heavy workload)
        max_connections = getattr(settings, "REDIS_CACHE_MAX_CONNECTIONS", 50)
        socket_timeout = getattr(settings, "REDIS_CACHE_SOCKET_TIMEOUT", 5)
        socket_connect_timeout = getattr(settings, "REDIS_CACHE_SOCKET_CONNECT_TIMEOUT", 5)
        health_check_interval = getattr(settings, "REDIS_CACHE_HEALTH_CHECK_INTERVAL", 30)

        _redis_cache_pool = redis.ConnectionPool.from_url(
            redis_url,
            max_connections=max_connections,
            socket_timeout=socket_timeout,
            socket_connect_timeout=socket_connect_timeout,
            retry_on_timeout=True,
            socket_keepalive=True,
            health_check_interval=health_check_interval,
            decode_responses=True,
        )

        logger.info(
            "redis_cache_pool_created",
            extra={"redis_url": redis_url, "max_connections": max_connections},
        )

    return _redis_cache_pool


def get_redis_queue_pool() -> redis.ConnectionPool:
    """
    Get or create Redis queue connection pool.

    Returns:
        Redis connection pool configured for queue instance
    """
    global _redis_queue_pool

    if _redis_queue_pool is None:
        redis_url = _get_redis_url_with_fallback("REDIS_QUEUE_URL", 6380)

        # Queue pool configuration (write-heavy workload)
        max_connections = getattr(settings, "REDIS_QUEUE_MAX_CONNECTIONS", 20)
        socket_timeout = getattr(settings, "REDIS_QUEUE_SOCKET_TIMEOUT", 10)
        socket_connect_timeout = getattr(settings, "REDIS_QUEUE_SOCKET_CONNECT_TIMEOUT", 5)
        health_check_interval = getattr(settings, "REDIS_QUEUE_HEALTH_CHECK_INTERVAL", 60)

        _redis_queue_pool = redis.ConnectionPool.from_url(
            redis_url,
            max_connections=max_connections,
            socket_timeout=socket_timeout,
            socket_connect_timeout=socket_connect_timeout,
            retry_on_timeout=True,
            socket_keepalive=True,
            health_check_interval=health_check_interval,
            decode_responses=True,
        )

        logger.info(
            "redis_queue_pool_created",
            extra={"redis_url": redis_url, "max_connections": max_connections},
        )

    return _redis_queue_pool


def get_redis_events_pool() -> redis.ConnectionPool:
    """
    Get or create Redis events connection pool.

    Returns:
        Redis connection pool configured for events instance
    """
    global _redis_events_pool

    if _redis_events_pool is None:
        redis_url = _get_redis_url_with_fallback("REDIS_EVENTS_URL", 6381)

        # Events pool configuration (high throughput)
        max_connections = getattr(settings, "REDIS_EVENTS_MAX_CONNECTIONS", 30)
        socket_timeout = getattr(settings, "REDIS_EVENTS_SOCKET_TIMEOUT", 5)
        socket_connect_timeout = getattr(settings, "REDIS_EVENTS_SOCKET_CONNECT_TIMEOUT", 5)
        health_check_interval = getattr(settings, "REDIS_EVENTS_HEALTH_CHECK_INTERVAL", 30)

        _redis_events_pool = redis.ConnectionPool.from_url(
            redis_url,
            max_connections=max_connections,
            socket_timeout=socket_timeout,
            socket_connect_timeout=socket_connect_timeout,
            retry_on_timeout=True,
            socket_keepalive=True,
            health_check_interval=health_check_interval,
            decode_responses=True,
        )

        logger.info(
            "redis_events_pool_created",
            extra={"redis_url": redis_url, "max_connections": max_connections},
        )

    return _redis_events_pool


def get_redis_channels_pool() -> redis.ConnectionPool:
    """
    Get or create Redis channels connection pool.

    Returns:
        Redis connection pool configured for channels instance
    """
    global _redis_channels_pool

    if _redis_channels_pool is None:
        redis_url = _get_redis_url_with_fallback("REDIS_CHANNELS_URL", 6382)

        # Channels pool configuration (WebSocket connections)
        max_connections = getattr(settings, "REDIS_CHANNELS_MAX_CONNECTIONS", 40)
        socket_timeout = getattr(settings, "REDIS_CHANNELS_SOCKET_TIMEOUT", 3)
        socket_connect_timeout = getattr(settings, "REDIS_CHANNELS_SOCKET_CONNECT_TIMEOUT", 5)
        health_check_interval = getattr(settings, "REDIS_CHANNELS_HEALTH_CHECK_INTERVAL", 30)

        _redis_channels_pool = redis.ConnectionPool.from_url(
            redis_url,
            max_connections=max_connections,
            socket_timeout=socket_timeout,
            socket_connect_timeout=socket_connect_timeout,
            retry_on_timeout=True,
            socket_keepalive=True,
            health_check_interval=health_check_interval,
            decode_responses=True,
        )

        logger.info(
            "redis_channels_pool_created",
            extra={"redis_url": redis_url, "max_connections": max_connections},
        )

    return _redis_channels_pool


def get_redis_cache_client() -> redis.Redis:
    """
    Get Redis client for cache instance.

    Returns:
        Redis client connected to cache instance
    """
    pool = get_redis_cache_pool()
    return redis.Redis(connection_pool=pool, decode_responses=True)


def get_redis_queue_client() -> redis.Redis:
    """
    Get Redis client for queue instance.

    Returns:
        Redis client connected to queue instance
    """
    pool = get_redis_queue_pool()
    return redis.Redis(connection_pool=pool, decode_responses=True)


def get_redis_events_client() -> redis.Redis:
    """
    Get Redis client for events instance.

    Returns:
        Redis client connected to events instance
    """
    pool = get_redis_events_pool()
    return redis.Redis(connection_pool=pool, decode_responses=True)


def get_redis_channels_client() -> redis.Redis:
    """
    Get Redis client for channels instance.

    Returns:
        Redis client connected to channels instance
    """
    pool = get_redis_channels_pool()
    return redis.Redis(connection_pool=pool, decode_responses=True)


def parse_redis_url(redis_url: str) -> tuple:
    """
    Parse Redis URL into (host, port) tuple.

    Args:
        redis_url: Redis URL in format redis://host:port/db

    Returns:
        Tuple of (host, port). Falls back to (localhost, 6379) for invalid format.
    """
    if not redis_url or not isinstance(redis_url, str):
        return ("localhost", 6379)
    if not redis_url.startswith("redis://"):
        return ("localhost", 6379)
    try:
        # Remove redis:// prefix
        url = redis_url.replace("redis://", "", 1)
        # Split on / to separate host:port from db
        parts = url.split("/")
        host_port = parts[0].split(":")
        host = host_port[0].strip()
        if not host:
            return ("localhost", 6379)
        port = int(host_port[1]) if len(host_port) > 1 else 6379
        return (host, port)
    except (ValueError, IndexError):
        return ("localhost", 6379)


def health_check_all_redis_instances() -> dict:
    """
    Perform health check on all Redis instances.

    Returns:
        Dictionary with health status for each instance
    """
    results = {
        "cache": {"status": "unknown", "error": None},
        "queue": {"status": "unknown", "error": None},
        "events": {"status": "unknown", "error": None},
        "channels": {"status": "unknown", "error": None},
    }

    # Check cache
    try:
        client = get_redis_cache_client()
        client.ping()
        results["cache"]["status"] = "healthy"
    except Exception as e:
        results["cache"]["status"] = "unhealthy"
        results["cache"]["error"] = str(e)

    # Check queue
    try:
        client = get_redis_queue_client()
        client.ping()
        results["queue"]["status"] = "healthy"
    except Exception as e:
        results["queue"]["status"] = "unhealthy"
        results["queue"]["error"] = str(e)

    # Check events
    try:
        client = get_redis_events_client()
        client.ping()
        results["events"]["status"] = "healthy"
    except Exception as e:
        results["events"]["status"] = "unhealthy"
        results["events"]["error"] = str(e)

    # Check channels
    try:
        client = get_redis_channels_client()
        client.ping()
        results["channels"]["status"] = "healthy"
    except Exception as e:
        results["channels"]["status"] = "unhealthy"
        results["channels"]["error"] = str(e)

    return results
