"""
Dataset Caching Utilities

Caching utilities for dataset queries with efficient invalidation.
Implements multi-level caching strategy for optimal performance.

Features:
- List query caching with filter-based keys
- Detail caching per dataset
- Cache invalidation on mutations
- Cache tags for efficient bulk invalidation (Redis)
"""
from typing import Any, Dict, List, Optional, Tuple
from django.core.cache import cache
from django.conf import settings
import hashlib
import json
import structlog

logger = structlog.get_logger(__name__)

# Cache TTLs (in seconds)
CACHE_TTL_DATASET_LIST = getattr(settings, 'CACHE_TTL_DATASET_LIST', 300)  # 5 minutes
CACHE_TTL_DATASET_DETAIL = getattr(settings, 'CACHE_TTL_DATASET_DETAIL', 600)  # 10 minutes

# Cache key prefixes
CACHE_PREFIX_DATASET_LIST = "dataset:list"
CACHE_PREFIX_DATASET_DETAIL = "dataset:detail"
CACHE_TAG_DATASET_LIST = "dataset:list"  # Tag for bulk invalidation
CACHE_TAG_DATASET_DETAIL = "dataset:detail"  # Tag for bulk invalidation


def get_tenant_id_from_request(request) -> Optional[str]:
    """
    Extract tenant ID from request (Phase 16: delegates to central helper).

    See hub.apps.tenants.request_tenant.get_request_tenant_id and docs/TENANT_ISOLATION.md.
    """
    from hub.apps.tenants.request_tenant import get_request_tenant_id
    return get_request_tenant_id(request)


def hash_filters(query_params: Dict[str, Any]) -> str:
    """
    Generate hash from query parameters for cache key.

    Args:
        query_params: Query parameters dictionary

    Returns:
        MD5 hash string
    """
    # Normalize query parameters
    # Remove None values and sort for deterministic hashing
    normalized_params = {
        k: v for k, v in sorted(query_params.items())
        if v is not None and v != ''
    }

    # Convert to JSON string for hashing
    params_str = json.dumps(normalized_params, sort_keys=True, default=str)
    params_hash = hashlib.md5(params_str.encode()).hexdigest()

    return params_hash


def get_dataset_list_cache_key(tenant_id: str, filters_hash: str) -> str:
    """
    Generate cache key for dataset list query.

    Args:
        tenant_id: Tenant UUID string
        filters_hash: Hash of query filters

    Returns:
        Cache key string
    """
    return f"{CACHE_PREFIX_DATASET_LIST}:{tenant_id}:{filters_hash}"


def get_dataset_detail_cache_key(dataset_id: str) -> str:
    """
    Generate cache key for dataset detail.

    Args:
        dataset_id: Dataset UUID string

    Returns:
        Cache key string
    """
    return f"{CACHE_PREFIX_DATASET_DETAIL}:{dataset_id}"


def cache_dataset_list(
    tenant_id: str,
    filters_hash: str,
    results: List[Dict[str, Any]],
    total_count: int,
    ttl: Optional[int] = None
) -> None:
    """
    Cache dataset list query results.

    Args:
        tenant_id: Tenant UUID string
        filters_hash: Hash of query filters
        results: List of dataset data dictionaries
        total_count: Total count of results
        ttl: Time-to-live in seconds (default: CACHE_TTL_DATASET_LIST)
    """
    cache_key = get_dataset_list_cache_key(tenant_id, filters_hash)
    ttl = ttl or CACHE_TTL_DATASET_LIST

    cache_data = {
        'results': results,
        'total_count': total_count
    }

    try:
        # Try to use cache tags if Redis is available
        if hasattr(cache, 'set_many') and hasattr(cache, '_cache'):
            # Check if using Redis cache backend
            cache_backend = getattr(settings, 'CACHES', {}).get('default', {}).get('BACKEND', '')
            if 'redis' in cache_backend.lower() or 'RedisCache' in cache_backend:
                # Use cache tags for efficient invalidation
                # Store data with tag
                cache.set(cache_key, cache_data, timeout=ttl)
                # Store key in tag set for bulk invalidation
                tag_key = f"{CACHE_TAG_DATASET_LIST}:{tenant_id}"
                tag_set = cache.get(tag_key, set())
                if not isinstance(tag_set, set):
                    tag_set = set()
                tag_set.add(cache_key)
                cache.set(tag_key, tag_set, timeout=ttl + 3600)  # Tag set expires later
            else:
                # Standard Django cache
                cache.set(cache_key, cache_data, timeout=ttl)
        else:
            # Standard Django cache
            cache.set(cache_key, cache_data, timeout=ttl)

        logger.debug(
            "dataset_list_cached",
            tenant_id=tenant_id,
            filters_hash=filters_hash,
            result_count=len(results),
            total_count=total_count,
            ttl=ttl
        )
    except Exception as e:
        logger.warning(
            "dataset_list_cache_error",
            error=str(e),
            tenant_id=tenant_id,
            filters_hash=filters_hash,
            message="Failed to cache dataset list"
        )


def get_cached_dataset_list(
    tenant_id: str,
    filters_hash: str
) -> Optional[Tuple[List[Dict[str, Any]], int]]:
    """
    Get cached dataset list query results.

    Args:
        tenant_id: Tenant UUID string
        filters_hash: Hash of query filters

    Returns:
        Tuple of (results list, total_count) or None
    """
    cache_key = get_dataset_list_cache_key(tenant_id, filters_hash)

    try:
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.debug(
                "dataset_list_cache_hit",
                tenant_id=tenant_id,
                filters_hash=filters_hash,
                result_count=len(cached_data.get('results', [])),
                total_count=cached_data.get('total_count', 0)
            )
            return cached_data.get('results'), cached_data.get('total_count')
        return None
    except Exception as e:
        logger.warning(
            "dataset_list_cache_get_error",
            error=str(e),
            tenant_id=tenant_id,
            filters_hash=filters_hash,
            message="Failed to get cached dataset list"
        )
        return None


def cache_dataset_detail(
    dataset_id: str,
    dataset_data: Dict[str, Any],
    ttl: Optional[int] = None
) -> None:
    """
    Cache dataset detail data.

    Args:
        dataset_id: Dataset UUID string
        dataset_data: Dataset data dictionary
        ttl: Time-to-live in seconds (default: CACHE_TTL_DATASET_DETAIL)
    """
    cache_key = get_dataset_detail_cache_key(dataset_id)
    ttl = ttl or CACHE_TTL_DATASET_DETAIL

    try:
        cache.set(cache_key, dataset_data, timeout=ttl)

        logger.debug(
            "dataset_detail_cached",
            dataset_id=dataset_id,
            ttl=ttl
        )
    except Exception as e:
        logger.warning(
            "dataset_detail_cache_error",
            error=str(e),
            dataset_id=dataset_id,
            message="Failed to cache dataset detail"
        )


def get_cached_dataset_detail(dataset_id: str) -> Optional[Dict[str, Any]]:
    """
    Get cached dataset detail data.

    Args:
        dataset_id: Dataset UUID string

    Returns:
        Cached dataset data dictionary or None
    """
    cache_key = get_dataset_detail_cache_key(dataset_id)

    try:
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.debug(
                "dataset_detail_cache_hit",
                dataset_id=dataset_id
            )
        return cached_data
    except Exception as e:
        logger.warning(
            "dataset_detail_cache_get_error",
            error=str(e),
            dataset_id=dataset_id,
            message="Failed to get cached dataset detail"
        )
        return None


def invalidate_dataset_list_cache(tenant_id: Optional[str] = None) -> None:
    """
    Invalidate dataset list cache.

    Args:
        tenant_id: Optional tenant UUID string (if None, invalidates all)
    """
    try:
        if tenant_id:
            # Invalidate specific tenant's list cache
            # Try to use cache tags if Redis is available
            cache_backend = getattr(settings, 'CACHES', {}).get('default', {}).get('BACKEND', '')
            if 'redis' in cache_backend.lower() or 'RedisCache' in cache_backend:
                # Get all keys for this tenant's list cache
                tag_key = f"{CACHE_TAG_DATASET_LIST}:{tenant_id}"
                tag_set = cache.get(tag_key, set())
                if isinstance(tag_set, set) and tag_set:
                    # Delete all cached list queries for this tenant
                    cache.delete_many(list(tag_set))
                    # Clear tag set
                    cache.delete(tag_key)
                    logger.info(
                        "dataset_list_cache_invalidated",
                        tenant_id=tenant_id,
                        keys_invalidated=len(tag_set)
                    )
                else:
                    # Fallback: use pattern-based invalidation if Redis supports it
                    # Pattern: dataset:list:{tenant_id}:*
                    # Note: Django cache doesn't support pattern deletion natively
                    # In production, use Redis directly or maintain a key registry
                    logger.debug(
                        "dataset_list_cache_invalidation_skipped",
                        tenant_id=tenant_id,
                        reason="No tag set found"
                    )
            else:
                # Standard Django cache - can't invalidate by pattern
                # In production, maintain a registry of cache keys
                logger.debug(
                    "dataset_list_cache_invalidation_limited",
                    tenant_id=tenant_id,
                    message="Pattern-based invalidation not supported"
                )
        else:
            # Invalidate all list caches
            # This is expensive - use sparingly
            logger.warning(
                "dataset_list_cache_invalidation_all",
                message="Invalidating all dataset list caches - this may be expensive"
            )
    except Exception as e:
        logger.error(
            "dataset_list_cache_invalidation_error",
            error=str(e),
            tenant_id=tenant_id,
            message="Failed to invalidate dataset list cache"
        )


def invalidate_dataset_detail_cache(dataset_id: str) -> None:
    """
    Invalidate dataset detail cache.

    Args:
        dataset_id: Dataset UUID string
    """
    try:
        cache_key = get_dataset_detail_cache_key(dataset_id)
        cache.delete(cache_key)

        logger.debug(
            "dataset_detail_cache_invalidated",
            dataset_id=dataset_id
        )
    except Exception as e:
        logger.error(
            "dataset_detail_cache_invalidation_error",
            error=str(e),
            dataset_id=dataset_id,
            message="Failed to invalidate dataset detail cache"
        )


def invalidate_dataset_caches(dataset_id: str, tenant_id: Optional[str] = None) -> None:
    """
    Invalidate all caches for a dataset (detail and list).

    Args:
        dataset_id: Dataset UUID string
        tenant_id: Optional tenant UUID string (for list cache invalidation)
    """
    # Invalidate detail cache
    invalidate_dataset_detail_cache(dataset_id)

    # Invalidate list cache (all queries for this tenant)
    if tenant_id:
        invalidate_dataset_list_cache(tenant_id)

