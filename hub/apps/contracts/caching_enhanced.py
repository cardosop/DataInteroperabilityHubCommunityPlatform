"""
Enhanced Contract Caching

Provides enhanced caching capabilities for contracts:
- Cache tags for efficient invalidation
- Cache warming for frequently accessed contracts
- Cache hit/miss metrics
"""
import time
from typing import Any, Dict, List, Optional, Set

import structlog
import redis
from django.conf import settings
from django.core.cache import cache as django_cache

from hub.apps.contracts.caching import (
    cache_contract,
    get_contract_cache_key,
    get_cached_contract,
    CACHE_TTL_CONTRACT,
)
from hub.apps.contracts.models import Contract
from hub.apps.core.caching.cache import (
    invalidate_cache_pattern,
)
from hub.apps.observability.otel_metrics import (
    cache_hits_total,
    cache_misses_total,
)

logger = structlog.get_logger(__name__)


def get_redis_client() -> Optional[redis.Redis]:
    """
    Get Redis client for cache tag operations.

    Returns:
        Redis client instance or None if unavailable
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
        logger.warning(
            "contract_cache_redis_unavailable",
            error=str(e),
            redis_url=redis_url,
            message="Cache tags will use Django cache backend only"
        )
        return None


def _get_tag_key(tag: str) -> str:
    """
    Get Redis key for cache tag.

    Args:
        tag: Cache tag (e.g., "tenant:t1", "owner:user1")

    Returns:
        Redis key for tag
    """
    return f"cache_tag:contract:{tag}"


def _get_contract_tags_key(contract_id: str) -> str:
    """
    Get Redis key for contract's tags.

    Args:
        contract_id: Contract UUID

    Returns:
        Redis key for contract tags
    """
    return f"cache_tag:contract_tags:{contract_id}"


def cache_contract_with_tags(
    contract_id: str,
    contract_data: Dict[str, Any],
    tags: Optional[List[str]] = None,
    ttl: Optional[int] = None
) -> None:
    """
    Cache contract data with tags for efficient invalidation.

    Args:
        contract_id: Contract UUID
        contract_data: Contract data dictionary
        tags: List of cache tags (e.g., ["tenant:t1", "owner:user1"])
        ttl: Time-to-live in seconds (default: CACHE_TTL_CONTRACT)
    """
    # Cache contract data using existing function
    cache_contract(contract_id, contract_data, ttl=ttl)

    if tags:
        redis_client = get_redis_client()
        cache_ttl = ttl or CACHE_TTL_CONTRACT

        if redis_client:
            try:
                # Store tags for this contract
                tags_key = _get_contract_tags_key(contract_id)
                redis_client.setex(
                    tags_key,
                    cache_ttl,
                    ",".join(tags)
                )

                # Add contract ID to each tag's set
                for tag in tags:
                    tag_key = _get_tag_key(tag)
                    # Use Redis set to store contract IDs for this tag
                    redis_client.sadd(tag_key, contract_id)
                    # Set expiration on tag set
                    redis_client.expire(tag_key, cache_ttl)

                logger.debug(
                    "contract_cache_tagged",
                    contract_id=contract_id,
                    tags=tags,
                    message="Cached contract with tags"
                )
            except Exception as e:
                logger.warning(
                    "contract_cache_tag_error",
                    contract_id=contract_id,
                    tags=tags,
                    error=str(e),
                    message="Failed to store cache tags, contract still cached"
                )
        else:
            # Fallback: store tags in Django cache (limited pattern support)
            tags_key = _get_contract_tags_key(contract_id)
            django_cache.set(tags_key, tags, timeout=cache_ttl)
            logger.debug(
                "contract_cache_tagged_fallback",
                contract_id=contract_id,
                tags=tags,
                message="Cached contract with tags (Django cache fallback)"
            )


def get_cached_contract_with_metrics(
    contract_id: str
) -> Optional[Dict[str, Any]]:
    """
    Get cached contract data and record metrics.

    Args:
        contract_id: Contract UUID

    Returns:
        Cached contract data or None

    Records:
        - cache_hits_total metric on cache hit
        - cache_misses_total metric on cache miss
    """
    cached_data = get_cached_contract(contract_id)

    if cached_data is not None:
        # Cache hit
        try:
            cache_hits_total.labels(cache_key_prefix='contract').inc()
        except Exception as e:
            logger.warning(
                "contract_cache_metrics_error",
                contract_id=contract_id,
                error=str(e),
                message="Failed to record cache hit metric"
            )
        return cached_data
    else:
        # Cache miss
        try:
            cache_misses_total.labels(cache_key_prefix='contract').inc()
        except Exception as e:
            logger.warning(
                "contract_cache_metrics_error",
                contract_id=contract_id,
                error=str(e),
                message="Failed to record cache miss metric"
            )
        return None


def invalidate_contract_cache_by_tags(tags: List[str]) -> int:
    """
    Invalidate contract cache by tags.

    Uses Redis sets to efficiently find all contracts with given tags.

    Args:
        tags: List of cache tags to invalidate

    Returns:
        Number of contracts invalidated
    """
    redis_client = get_redis_client()
    invalidated_count = 0

    if redis_client:
        try:
            # Collect all contract IDs that match any of the tags
            contract_ids_to_invalidate: Set[str] = set()

            for tag in tags:
                tag_key = _get_tag_key(tag)
                # Get all contract IDs for this tag
                contract_ids = redis_client.smembers(tag_key)
                contract_ids_to_invalidate.update(contract_ids)

                # Remove tag set
                redis_client.delete(tag_key)

            # Invalidate all matching contracts
            for contract_id in contract_ids_to_invalidate:
                # Delete contract cache
                cache_key = get_contract_cache_key(contract_id)
                django_cache.delete(cache_key)

                # Delete contract tags
                tags_key = _get_contract_tags_key(contract_id)
                redis_client.delete(tags_key)

                invalidated_count += 1

            logger.info(
                "contract_cache_invalidated_by_tags",
                tags=tags,
                invalidated_count=invalidated_count,
                message="Invalidated contracts by tags"
            )
        except Exception as e:
            logger.warning(
                "contract_cache_invalidation_error",
                tags=tags,
                error=str(e),
                message="Failed to invalidate contracts by tags"
            )
    else:
        # Fallback: use pattern-based invalidation
        # This is less efficient but works without Redis
        for tag in tags:
            # Try to invalidate by pattern (limited support with LocMemCache)
            pattern = f"contract:*"  # Would need tag info in key for better pattern
            invalidated = invalidate_cache_pattern(pattern)
            invalidated_count += invalidated

        logger.debug(
            "contract_cache_invalidated_by_tags_fallback",
            tags=tags,
            invalidated_count=invalidated_count,
            message="Invalidated contracts by tags (fallback method)"
        )

    return invalidated_count


def warm_frequently_accessed_contracts(
    tenant_id: Optional[str] = None,
    limit: int = 100,
    min_access_count: int = 5
) -> int:
    """
    Warm cache with frequently accessed contracts.

    Identifies frequently accessed contracts and pre-populates cache.

    Args:
        tenant_id: Optional tenant ID to filter contracts
        limit: Maximum number of contracts to warm (default: 100)
        min_access_count: Minimum access count to consider (default: 5)

    Returns:
        Number of contracts warmed
    """
    try:
        # Query frequently accessed contracts
        # Note: This assumes there's an access tracking mechanism
        # For now, we'll use recently updated contracts as a proxy
        queryset = Contract.objects.filter(
            hub_contract_json__isnull=False
        ).select_related('tenant', 'asset')

        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)

        # Order by updated_at (recently updated = likely accessed)
        # In production, you'd use actual access tracking
        contracts = queryset.order_by('-updated_at')[:limit]

        warmed_count = 0
        for contract in contracts:
            try:
                # Generate tags based on contract properties
                tags = []
                if contract.tenant_id:
                    tags.append(f"tenant:{contract.tenant_id}")
                if hasattr(contract, 'created_by') and contract.created_by:
                    tags.append(f"owner:{contract.created_by.id}")
                if contract.status:
                    tags.append(f"status:{contract.status}")

                # Cache contract with tags
                contract_data = {
                    'id': str(contract.id),
                    'hub_contract_json': contract.hub_contract_json,
                    'status': contract.status,
                    'normalization_status': contract.normalization_status,
                    'tenant_id': str(contract.tenant_id) if contract.tenant_id else None,
                }

                cache_contract_with_tags(
                    str(contract.id),
                    contract_data,
                    tags=tags if tags else None
                )

                warmed_count += 1
            except Exception as e:
                logger.warning(
                    "contract_cache_warming_error",
                    contract_id=str(contract.id),
                    error=str(e),
                    message="Failed to warm cache for contract"
                )
                continue

        logger.info(
            "contract_cache_warmed",
            tenant_id=tenant_id,
            warmed_count=warmed_count,
            limit=limit,
            message="Warmed cache for frequently accessed contracts"
        )

        return warmed_count
    except Exception as e:
        logger.error(
            "contract_cache_warming_failed",
            tenant_id=tenant_id,
            error=str(e),
            message="Failed to warm contract cache"
        )
        return 0


def get_contract_cache_metrics() -> Dict[str, Any]:
    """
    Get contract cache metrics.

    Returns:
        Dictionary with cache metrics:
        - hits: Number of cache hits
        - misses: Number of cache misses
        - hit_rate: Cache hit rate (hits / (hits + misses))
    """
    try:
        hits_metric = cache_hits_total.labels(cache_key_prefix='contract')
        misses_metric = cache_misses_total.labels(cache_key_prefix='contract')

        hits = hits_metric._value.get() if hasattr(hits_metric, '_value') else 0
        misses = misses_metric._value.get() if hasattr(misses_metric, '_value') else 0

        total = hits + misses
        hit_rate = hits / total if total > 0 else 0.0

        return {
            'hits': hits,
            'misses': misses,
            'total': total,
            'hit_rate': hit_rate
        }
    except Exception as e:
        logger.warning(
            "contract_cache_metrics_error",
            error=str(e),
            message="Failed to get cache metrics"
        )
        return {
            'hits': 0,
            'misses': 0,
            'total': 0,
            'hit_rate': 0.0
        }

