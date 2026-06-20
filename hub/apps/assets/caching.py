"""
Asset Caching Utilities

Caching utilities for asset queries with efficient invalidation.
Implements multi-level caching strategy for optimal performance.

Features:
- List query caching with filter-based keys
- Detail caching per asset
- Cache invalidation on mutations
- Cache tags for efficient bulk invalidation (Redis)
"""

import hashlib
import json
from typing import Any

import structlog
from django.conf import settings
from django.core.cache import cache

logger = structlog.get_logger(__name__)

# Cache operations are best-effort.  These exception types represent
# transient infrastructure failures (network blip, Redis restart, DNS
# flap) that should NOT crash the caller.  Programming errors
# (AttributeError, TypeError, etc.) are NOT in this tuple — they are
# caught separately and logged at ERROR so SRE can see them without
# the caller crashing.
_CACHE_INFRA_EXCEPTIONS = (ConnectionError, TimeoutError, OSError)

# Cache TTLs (in seconds)
CACHE_TTL_ASSET_LIST = getattr(settings, "CACHE_TTL_ASSET_LIST", 300)  # 5 minutes
CACHE_TTL_ASSET_DETAIL = getattr(settings, "CACHE_TTL_ASSET_DETAIL", 600)  # 10 minutes

# Cache key prefixes
CACHE_PREFIX_ASSET_LIST = "asset:list"
CACHE_PREFIX_ASSET_DETAIL = "asset:detail"
CACHE_TAG_ASSET_LIST = "asset:list"  # Tag for bulk invalidation
CACHE_TAG_ASSET_DETAIL = "asset:detail"  # Tag for bulk invalidation
# Registry key for non-Redis: track list cache keys per tenant so we can invalidate on create/update/delete
ASSET_LIST_REGISTRY_PREFIX = "asset:list:registry"


def get_tenant_id_from_request(request) -> str | None:
    """
    Extract tenant ID from request (Phase 16: delegates to central helper).

    See hub.apps.tenants.request_tenant.get_request_tenant_id and docs/TENANT_ISOLATION.md.
    """
    from hub.apps.tenants.request_tenant import get_request_tenant_id

    return get_request_tenant_id(request)


def hash_filters(query_params: dict[str, Any]) -> str:
    """
    Generate hash from query parameters for cache key.

    Args:
        query_params: Query parameters dictionary

    Returns:
        MD5 hash string
    """
    # Normalize query parameters
    # Remove None values and sort for deterministic hashing
    normalized_params = {k: v for k, v in sorted(query_params.items()) if v is not None and v != ""}

    # Convert to JSON string for hashing
    params_str = json.dumps(normalized_params, sort_keys=True, default=str)
    params_hash = hashlib.md5(params_str.encode()).hexdigest()

    return params_hash


def get_asset_list_cache_key(tenant_id: str, filters_hash: str) -> str:
    """
    Generate cache key for asset list query.

    Args:
        tenant_id: Tenant UUID string
        filters_hash: Hash of query filters

    Returns:
        Cache key string
    """
    return f"{CACHE_PREFIX_ASSET_LIST}:{tenant_id}:{filters_hash}"


def get_asset_detail_cache_key(asset_id: str) -> str:
    """
    Generate cache key for asset detail.

    Args:
        asset_id: Asset UUID string

    Returns:
        Cache key string
    """
    return f"{CACHE_PREFIX_ASSET_DETAIL}:{asset_id}"


def cache_asset_list(
    tenant_id: str,
    filters_hash: str,
    results: list[dict[str, Any]],
    total_count: int,
    ttl: int | None = None,
) -> None:
    """
    Cache asset list query results.

    Args:
        tenant_id: Tenant UUID string
        filters_hash: Hash of query filters
        results: List of asset data dictionaries
        total_count: Total count of results
        ttl: Time-to-live in seconds (default: CACHE_TTL_ASSET_LIST)
    """
    # Validate tenant_id is not None or empty
    if not tenant_id:
        logger.warning("cache_asset_list_skipped", reason="Invalid tenant_id")
        return

    cache_key = get_asset_list_cache_key(tenant_id, filters_hash)
    ttl = ttl or CACHE_TTL_ASSET_LIST

    cache_data = {"results": results, "total_count": total_count}

    try:
        cache_backend = getattr(settings, "CACHES", {}).get("default", {}).get("BACKEND", "")
        use_redis = "redis" in cache_backend.lower() or "RedisCache" in cache_backend

        if use_redis:
            # Use cache tags for efficient invalidation
            cache.set(cache_key, cache_data, timeout=ttl)
            tag_key = f"{CACHE_TAG_ASSET_LIST}:{tenant_id}"
            tag_set = cache.get(tag_key, set())
            if not isinstance(tag_set, set):
                tag_set = set()
            tag_set.add(cache_key)
            cache.set(tag_key, tag_set, timeout=ttl + 3600)  # Tag set expires later
        else:
            # Standard Django cache (LocMem etc.): register key for invalidation by tenant
            cache.set(cache_key, cache_data, timeout=ttl)
            registry_key = f"{ASSET_LIST_REGISTRY_PREFIX}:{tenant_id}"
            keys_for_tenant = list(cache.get(registry_key) or [])
            if cache_key not in keys_for_tenant:
                keys_for_tenant.append(cache_key)
                cache.set(registry_key, keys_for_tenant, timeout=ttl + 3600)

        logger.debug(
            "asset_list_cached",
            tenant_id=tenant_id,
            filters_hash=filters_hash,
            result_count=len(results),
            total_count=total_count,
            ttl=ttl,
        )
    except _CACHE_INFRA_EXCEPTIONS as e:
        logger.warning(
            "asset_list_cache_error",
            error=str(e),
            tenant_id=tenant_id,
            filters_hash=filters_hash,
            message="Failed to cache asset list — transient infrastructure error",
        )
    except Exception:
        # Programming error in the cache layer — log at ERROR so it
        # surfaces in Sentry/DataDog but DON'T crash the caller.
        # Cache is best-effort by design.
        logger.error(
            "asset_list_cache_unexpected_error",
            tenant_id=tenant_id,
            filters_hash=filters_hash,
            message="Unexpected error caching asset list",
            exc_info=True,
        )


def get_cached_asset_list(
    tenant_id: str, filters_hash: str
) -> tuple[list[dict[str, Any]], int] | None:
    """
    Get cached asset list query results.

    Args:
        tenant_id: Tenant UUID string
        filters_hash: Hash of query filters

    Returns:
        Tuple of (results list, total_count) or None
    """
    cache_key = get_asset_list_cache_key(tenant_id, filters_hash)

    try:
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.debug(
                "asset_list_cache_hit",
                tenant_id=tenant_id,
                filters_hash=filters_hash,
                result_count=len(cached_data.get("results", [])),
                total_count=cached_data.get("total_count", 0),
            )
            return cached_data.get("results"), cached_data.get("total_count")
        return None
    except _CACHE_INFRA_EXCEPTIONS as e:
        logger.warning(
            "asset_list_cache_get_error",
            error=str(e),
            tenant_id=tenant_id,
            filters_hash=filters_hash,
            message="Failed to get cached asset list — transient infrastructure error",
        )
        return None  # cache miss — caller falls back to DB query
    except Exception:
        logger.error(
            "asset_list_cache_get_unexpected_error",
            tenant_id=tenant_id,
            filters_hash=filters_hash,
            message="Unexpected error reading asset list cache",
            exc_info=True,
        )
        return None  # cache miss — caller falls back to DB query


def cache_asset_detail(asset_id: str, asset_data: dict[str, Any], ttl: int | None = None) -> None:
    """
    Cache asset detail data.

    Args:
        asset_id: Asset UUID string
        asset_data: Asset data dictionary
        ttl: Time-to-live in seconds (default: CACHE_TTL_ASSET_DETAIL)
    """
    # Validate asset_id is not None or empty
    if not asset_id:
        logger.warning("cache_asset_detail_skipped", reason="Invalid asset_id")
        return

    cache_key = get_asset_detail_cache_key(asset_id)
    ttl = ttl or CACHE_TTL_ASSET_DETAIL

    try:
        cache.set(cache_key, asset_data, timeout=ttl)

        logger.debug("asset_detail_cached", asset_id=asset_id, ttl=ttl)
    except _CACHE_INFRA_EXCEPTIONS as e:
        logger.warning(
            "asset_detail_cache_error",
            error=str(e),
            asset_id=asset_id,
            message="Failed to cache asset detail — transient infrastructure error",
        )
    except Exception:
        logger.error(
            "asset_detail_cache_unexpected_error",
            asset_id=asset_id,
            message="Unexpected error caching asset detail",
            exc_info=True,
        )


def get_cached_asset_detail(asset_id: str) -> dict[str, Any] | None:
    """
    Get cached asset detail data.

    Args:
        asset_id: Asset UUID string

    Returns:
        Cached asset data dictionary or None
    """
    cache_key = get_asset_detail_cache_key(asset_id)

    try:
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.debug("asset_detail_cache_hit", asset_id=asset_id)
        return cached_data
    except _CACHE_INFRA_EXCEPTIONS as e:
        logger.warning(
            "asset_detail_cache_get_error",
            error=str(e),
            asset_id=asset_id,
            message="Failed to get cached asset detail — transient infrastructure error",
        )
        return None  # cache miss — caller falls back to DB query
    except Exception:
        logger.error(
            "asset_detail_cache_get_unexpected_error",
            asset_id=asset_id,
            message="Unexpected error reading asset detail cache",
            exc_info=True,
        )
        return None  # cache miss — caller falls back to DB query


def invalidate_asset_list_cache(tenant_id: str | None = None) -> None:
    """
    Invalidate asset list cache.

    Args:
        tenant_id: Optional tenant UUID string (if None, invalidates all)
    """
    try:
        if tenant_id:
            cache_backend = getattr(settings, "CACHES", {}).get("default", {}).get("BACKEND", "")
            use_redis = "redis" in cache_backend.lower() or "RedisCache" in cache_backend

            if use_redis:
                tag_key = f"{CACHE_TAG_ASSET_LIST}:{tenant_id}"
                tag_set = cache.get(tag_key, set())
                if isinstance(tag_set, set) and tag_set:
                    cache.delete_many(list(tag_set))
                    cache.delete(tag_key)
                    logger.info(
                        "asset_list_cache_invalidated",
                        tenant_id=tenant_id,
                        keys_invalidated=len(tag_set),
                    )
                else:
                    logger.debug(
                        "asset_list_cache_invalidation_skipped",
                        tenant_id=tenant_id,
                        reason="No tag set found",
                    )
            else:
                # Non-Redis: delete keys from per-tenant registry (set in cache_asset_list)
                registry_key = f"{ASSET_LIST_REGISTRY_PREFIX}:{tenant_id}"
                keys_for_tenant = cache.get(registry_key)
                if keys_for_tenant:
                    for key in keys_for_tenant:
                        cache.delete(key)
                    cache.delete(registry_key)
                    logger.info(
                        "asset_list_cache_invalidated",
                        tenant_id=tenant_id,
                        keys_invalidated=len(keys_for_tenant),
                    )
                else:
                    logger.debug(
                        "asset_list_cache_invalidation_skipped",
                        tenant_id=tenant_id,
                        reason="No registry found",
                    )
        else:
            # Invalidate all list caches
            # This is expensive - use sparingly
            logger.warning(
                "asset_list_cache_invalidation_all",
                message="Invalidating all asset list caches - this may be expensive",
            )
    except _CACHE_INFRA_EXCEPTIONS as e:
        logger.error(
            "asset_list_cache_invalidation_error",
            error=str(e),
            tenant_id=tenant_id,
            message="Failed to invalidate asset list cache — transient infrastructure error",
        )
    except Exception:
        logger.error(
            "asset_list_cache_invalidation_unexpected_error",
            tenant_id=tenant_id,
            message="Unexpected error invalidating asset list cache",
            exc_info=True,
        )


def invalidate_asset_detail_cache(asset_id: str) -> None:
    """
    Invalidate asset detail cache.

    Args:
        asset_id: Asset UUID string
    """
    try:
        cache_key = get_asset_detail_cache_key(asset_id)
        cache.delete(cache_key)

        logger.debug("asset_detail_cache_invalidated", asset_id=asset_id)
    except _CACHE_INFRA_EXCEPTIONS as e:
        logger.error(
            "asset_detail_cache_invalidation_error",
            error=str(e),
            asset_id=asset_id,
            message="Failed to invalidate asset detail cache — transient infrastructure error",
        )
    except Exception:
        logger.error(
            "asset_detail_cache_invalidation_unexpected_error",
            asset_id=asset_id,
            message="Unexpected error invalidating asset detail cache",
            exc_info=True,
        )


def invalidate_asset_caches(asset_id: str, tenant_id: str | None = None) -> None:
    """
    Invalidate all caches for an asset (detail and list).

    Args:
        asset_id: Asset UUID string
        tenant_id: Optional tenant UUID string (for list cache invalidation)
    """
    # Invalidate detail cache
    invalidate_asset_detail_cache(asset_id)

    # Invalidate list cache (all queries for this tenant)
    if tenant_id:
        invalidate_asset_list_cache(tenant_id)
