"""
ODPS $ref Cache Warming

Provides cache warming functionality for external $ref resolution.
Pre-populates Redis cache with frequently accessed external references.

Usage:
    from hub.apps.contracts.ref_warming import warm_ref_cache, get_frequently_accessed_refs

    # Get frequently accessed refs
    refs = get_frequently_accessed_refs(limit=100)

    # Warm cache for refs
    result = warm_ref_cache(refs)
"""

import time
from typing import Any

import structlog
from django.conf import settings

from hub.apps.contracts.odps_errors import ODPSRefResolutionError
from hub.apps.contracts.ref_resolver import REDIS_CACHE_ACCESS_PREFIX, RefResolver

try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

logger = structlog.get_logger(__name__)


def _get_redis_client() -> Any | None:
    """Get Redis client for cache warming."""
    if not REDIS_AVAILABLE:
        return None

    try:
        redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
        client = redis.from_url(
            redis_url, decode_responses=False, socket_connect_timeout=5, socket_timeout=5
        )
        client.ping()
        return client
    except Exception as e:
        logger.warning(
            "ref_warming_redis_unavailable",
            error=str(e),
            message="Redis unavailable for cache warming",
        )
        return None


def get_frequently_accessed_refs(
    limit: int = 100, min_access_count: int = 1, tenant_id: str | None = None
) -> list[str]:
    """
    Get list of frequently accessed external $ref URLs.

    Queries Redis sorted set to identify refs with highest access counts.

    Args:
        limit: Maximum number of refs to return (default: 100)
        min_access_count: Minimum access count to include (default: 1)
        tenant_id: Optional tenant ID to filter (not currently supported, reserved for future)

    Returns:
        List of ref URLs sorted by access count (descending)
    """
    redis_client = _get_redis_client()
    if not redis_client:
        logger.warning(
            "ref_warming_no_redis", message="Redis unavailable, cannot get frequently accessed refs"
        )
        return []

    try:
        # Get top N refs by access count from sorted set
        access_set_key = REDIS_CACHE_ACCESS_PREFIX + "all"

        # Get top N members with highest scores (access counts)
        # ZREVRANGE returns members with scores in descending order
        # Get more than limit to account for filtering
        effective_limit = limit if limit is not None else 100
        top_refs = redis_client.zrevrange(
            access_set_key,
            0,
            (effective_limit * 2) - 1,  # Get more to account for filtering
            withscores=True,
        )

        ref_urls = []
        for url_hash_bytes, access_count in top_refs:
            # Filter by minimum access count
            if access_count < min_access_count:
                continue

            # Decode URL hash
            if isinstance(url_hash_bytes, bytes):
                url_hash = url_hash_bytes.decode("utf-8")
            else:
                url_hash = url_hash_bytes

            # Get actual URL from mapping
            url_mapping_key = f"{REDIS_CACHE_ACCESS_PREFIX}url:{url_hash}"
            url_bytes = redis_client.get(url_mapping_key)

            if url_bytes:
                ref_url = url_bytes.decode("utf-8")
                ref_urls.append(ref_url)

                # Stop when we have enough refs
                if len(ref_urls) >= limit:
                    break
            else:
                # URL mapping expired or missing, skip
                logger.debug(
                    "ref_warming_url_mapping_missing",
                    url_hash=url_hash,
                    message="URL mapping missing for hash",
                )

        logger.info(
            "ref_warming_frequently_accessed_refs",
            count=len(ref_urls),
            limit=limit,
            min_access_count=min_access_count,
            message=f"Found {len(ref_urls)} frequently accessed refs",
        )

        return ref_urls

    except Exception as e:
        logger.warning(
            "ref_warming_get_refs_failed",
            error=str(e),
            message="Failed to get frequently accessed refs",
        )
        return []


def warm_ref_cache(
    ref_urls: list[str],
    tenant_id: str | None = None,
    batch_size: int = 10,
    *,
    resolver: RefResolver | None = None,
) -> dict[str, Any]:
    """
    Warm cache for list of external $ref URLs.

    Resolves each ref URL and caches the result. Processes refs in batches
    to avoid overwhelming Redis or external APIs.

    Args:
        ref_urls: List of ref URLs to warm
        tenant_id: Optional tenant ID for rate limiting and audit logging
        batch_size: Number of refs to process per batch (default: 10)

    Returns:
        Dictionary with warming results:
        {
            'total': int,           # Total refs attempted
            'warmed': int,           # Successfully warmed
            'skipped': int,          # Skipped (already cached)
            'failed': int,           # Failed to warm
            'duration_seconds': float # Total time taken
        }
    """
    start_time = time.time()
    result = {
        "total": len(ref_urls),
        "warmed": 0,
        "skipped": 0,
        "failed": 0,
        "duration_seconds": 0.0,
    }

    if not ref_urls:
        logger.info("ref_warming_no_refs", message="No refs to warm")
        return result

    logger.info(
        "ref_warming_start",
        total_refs=len(ref_urls),
        batch_size=batch_size,
        tenant_id=tenant_id,
        message=f"Starting cache warming for {len(ref_urls)} refs",
    )

    # Resolver: caller may inject (e.g. tests with transport-bound resolve_external);
    # production/management command use the default RefResolver.
    if resolver is None:
        resolver = RefResolver(
            tenant_id=tenant_id,
            enable_caching=True,
        )

    # Process refs in batches
    for i in range(0, len(ref_urls), batch_size):
        batch = ref_urls[i : i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (len(ref_urls) + batch_size - 1) // batch_size

        logger.debug(
            "ref_warming_batch_start",
            batch_num=batch_num,
            total_batches=total_batches,
            batch_size=len(batch),
            message=f"Processing batch {batch_num}/{total_batches}",
        )

        for ref_url in batch:
            try:
                # Check if already cached
                cached = resolver._get_from_cache(ref_url)
                if cached is not None:
                    result["skipped"] += 1
                    logger.debug(
                        "ref_warming_skipped",
                        ref_url=ref_url,
                        message="Ref already cached, skipping",
                    )
                    continue

                # Resolve and cache ref
                resolved = resolver.resolve_external(ref_url)
                if resolved:
                    result["warmed"] += 1
                    logger.debug(
                        "ref_warming_success", ref_url=ref_url, message="Successfully warmed ref"
                    )
                else:
                    result["failed"] += 1
                    logger.warning(
                        "ref_warming_failed",
                        ref_url=ref_url,
                        message="Failed to resolve ref (returned None)",
                    )

            except ODPSRefResolutionError as e:
                result["failed"] += 1
                logger.warning(
                    "ref_warming_resolution_error",
                    ref_url=ref_url,
                    error=str(e),
                    error_code=e.error_code,
                    message="Ref resolution error during warming",
                )
            except Exception as e:
                result["failed"] += 1
                logger.warning(
                    "ref_warming_unexpected_error",
                    ref_url=ref_url,
                    error=str(e),
                    message="Unexpected error during cache warming",
                )

        # Log progress every batch
        if batch_num % 10 == 0 or batch_num == total_batches:
            logger.info(
                "ref_warming_progress",
                batch_num=batch_num,
                total_batches=total_batches,
                warmed=result["warmed"],
                skipped=result["skipped"],
                failed=result["failed"],
                message=f"Cache warming progress: {batch_num}/{total_batches} batches",
            )

    duration = time.time() - start_time
    result["duration_seconds"] = duration

    logger.info(
        "ref_warming_complete",
        total=result["total"],
        warmed=result["warmed"],
        skipped=result["skipped"],
        failed=result["failed"],
        duration_seconds=duration,
        tenant_id=tenant_id,
        message=f"Cache warming complete: {result['warmed']} warmed, {result['skipped']} skipped, {result['failed']} failed",
    )

    return result


def warm_cache_on_startup() -> None:
    """
    Warm cache on application startup.

    Called from AppConfig.ready() to pre-populate cache with frequently accessed refs.
    Runs asynchronously to avoid blocking application startup.
    """
    warming_enabled = getattr(settings, "ODPS_CACHE_WARMING_ENABLED", True)
    startup_enabled = getattr(settings, "ODPS_CACHE_WARMING_STARTUP_ENABLED", True)
    startup_limit = getattr(settings, "ODPS_CACHE_WARMING_STARTUP_LIMIT", 100)

    if not warming_enabled or not startup_enabled:
        logger.debug("ref_warming_startup_disabled", message="Cache warming disabled in settings")
        return

    # Run in background thread to avoid blocking startup
    import threading

    def warm_async():
        try:
            logger.info(
                "ref_warming_startup_start",
                limit=startup_limit,
                message="Starting startup cache warming",
            )

            # Get frequently accessed refs
            refs = get_frequently_accessed_refs(limit=startup_limit)

            if refs:
                # Warm cache
                result = warm_ref_cache(refs)
                logger.info(
                    "ref_warming_startup_complete",
                    warmed=result["warmed"],
                    skipped=result["skipped"],
                    failed=result["failed"],
                    duration_seconds=result["duration_seconds"],
                    message="Startup cache warming complete",
                )
            else:
                logger.info(
                    "ref_warming_startup_no_refs",
                    message="No frequently accessed refs found for startup warming",
                )
        except Exception as e:
            logger.warning(
                "ref_warming_startup_error",
                error=str(e),
                message="Error during startup cache warming",
            )

    # Start background thread
    thread = threading.Thread(target=warm_async, daemon=True)
    thread.start()
    logger.info(
        "ref_warming_startup_thread_started",
        message="Started background thread for startup cache warming",
    )
