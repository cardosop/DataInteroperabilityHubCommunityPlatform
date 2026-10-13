"""
Caching utilities for contract queries and lineage resolution.

Implements multi-level caching strategy for optimal performance.

Enhanced caching features (tags, warming, metrics) are available in
hub.apps.contracts.caching_enhanced module.
"""

import hashlib
import json
import logging
from typing import Any

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Cache TTLs (in seconds)
CACHE_TTL_CONTRACT = getattr(settings, "CACHE_TTL_CONTRACT", 300)  # 5 minutes
CACHE_TTL_LINEAGE = getattr(settings, "CACHE_TTL_LINEAGE", 600)  # 10 minutes
CACHE_TTL_QUERY_RESULT = getattr(settings, "CACHE_TTL_QUERY_RESULT", 300)  # 5 minutes
CACHE_TTL_LINEAGE_RESOLUTION = getattr(
    settings, "CACHE_TTL_LINEAGE_RESOLUTION", 3600
)  # 1 hour


def get_contract_cache_key(contract_id: str) -> str:
    """Generate cache key for contract."""
    return f"contract:{contract_id}"


def get_lineage_cache_key(
    contract_id: str, model_name: str | None = None, field_name: str | None = None
) -> str:
    """Generate cache key for lineage data."""
    if field_name:
        return f"lineage:{contract_id}:model:{model_name}:field:{field_name}"
    elif model_name:
        return f"lineage:{contract_id}:model:{model_name}"
    else:
        return f"lineage:{contract_id}"


def get_lineage_resolution_cache_key(
    namespace: str, name: str, model_name: str | None = None, field: str | None = None
) -> str:
    """Generate cache key for lineage reference resolution."""
    parts = [f"lineage:resolve:{namespace}:{name}"]
    if model_name:
        parts.append(f"model:{model_name}")
    if field:
        parts.append(f"field:{field}")
    return ":".join(parts)


def get_query_result_cache_key(query_params: dict[str, Any], tenant_id: str) -> str:
    """Generate cache key for query results."""
    # Create deterministic key from query parameters
    sorted_params = sorted(query_params.items())
    params_str = json.dumps(sorted_params, sort_keys=True)
    params_hash = hashlib.md5(params_str.encode()).hexdigest()
    return f"query_result:{tenant_id}:{params_hash}"


def cache_contract(
    contract_id: str, contract_data: dict[str, Any], ttl: int | None = None
) -> None:
    """
    Cache contract data.

    Args:
        contract_id: Contract UUID
        contract_data: Contract data dictionary
        ttl: Time-to-live in seconds (default: CACHE_TTL_CONTRACT)
    """
    cache_key = get_contract_cache_key(contract_id)
    ttl = ttl or CACHE_TTL_CONTRACT
    cache.set(cache_key, contract_data, timeout=ttl)


def get_cached_contract(contract_id: str) -> dict[str, Any] | None:
    """
    Get cached contract data.

    Args:
        contract_id: Contract UUID

    Returns:
        Cached contract data or None
    """
    cache_key = get_contract_cache_key(contract_id)
    return cache.get(cache_key)


def cache_lineage(
    contract_id: str,
    lineage_data: dict[str, Any],
    model_name: str | None = None,
    field_name: str | None = None,
    ttl: int | None = None,
) -> None:
    """
    Cache lineage data.

    Args:
        contract_id: Contract UUID
        lineage_data: Lineage data dictionary
        model_name: Optional model name
        field_name: Optional field name
        ttl: Time-to-live in seconds (default: CACHE_TTL_LINEAGE)
    """
    cache_key = get_lineage_cache_key(contract_id, model_name, field_name)
    ttl = ttl or CACHE_TTL_LINEAGE
    cache.set(cache_key, lineage_data, timeout=ttl)


def get_cached_lineage(
    contract_id: str, model_name: str | None = None, field_name: str | None = None
) -> dict[str, Any] | None:
    """
    Get cached lineage data.

    Args:
        contract_id: Contract UUID
        model_name: Optional model name
        field_name: Optional field name

    Returns:
        Cached lineage data or None
    """
    cache_key = get_lineage_cache_key(contract_id, model_name, field_name)
    return cache.get(cache_key)


def cache_lineage_resolution(
    namespace: str,
    name: str,
    resolution_result: dict[str, Any],
    model_name: str | None = None,
    field: str | None = None,
    ttl: int | None = None,
) -> None:
    """
    Cache lineage reference resolution result.

    Args:
        namespace: Contract namespace
        name: Contract name
        resolution_result: Resolution result dictionary
        model_name: Optional model name
        field: Optional field name
        ttl: Time-to-live in seconds (default: CACHE_TTL_LINEAGE_RESOLUTION)
    """
    cache_key = get_lineage_resolution_cache_key(namespace, name, model_name, field)
    ttl = ttl or CACHE_TTL_LINEAGE_RESOLUTION
    cache.set(cache_key, resolution_result, timeout=ttl)


def get_cached_lineage_resolution(
    namespace: str, name: str, model_name: str | None = None, field: str | None = None
) -> dict[str, Any] | None:
    """
    Get cached lineage reference resolution result.

    Args:
        namespace: Contract namespace
        name: Contract name
        model_name: Optional model name
        field: Optional field name

    Returns:
        Cached resolution result or None
    """
    cache_key = get_lineage_resolution_cache_key(namespace, name, model_name, field)
    return cache.get(cache_key)


def cache_query_result(
    query_params: dict[str, Any],
    tenant_id: str,
    results: list[dict[str, Any]],
    total_count: int,
    ttl: int | None = None,
) -> None:
    """
    Cache query result.

    Args:
        query_params: Query parameters dictionary
        tenant_id: Tenant UUID
        results: Query results list
        total_count: Total count of results
        ttl: Time-to-live in seconds (default: CACHE_TTL_QUERY_RESULT)
    """
    cache_key = get_query_result_cache_key(query_params, tenant_id)
    ttl = ttl or CACHE_TTL_QUERY_RESULT
    cache_data = {"results": results, "total_count": total_count}
    cache.set(cache_key, cache_data, timeout=ttl)


def get_cached_query_result(
    query_params: dict[str, Any], tenant_id: str
) -> tuple[list[dict[str, Any]], int] | None:
    """
    Get cached query result.

    Args:
        query_params: Query parameters dictionary
        tenant_id: Tenant UUID

    Returns:
        Tuple of (results list, total_count) or None
    """
    cache_key = get_query_result_cache_key(query_params, tenant_id)
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data.get("results"), cached_data.get("total_count")
    return None


def invalidate_contract_cache(contract_id: str) -> None:
    """
    Invalidate contract cache.

    Args:
        contract_id: Contract UUID
    """
    cache_key = get_contract_cache_key(contract_id)
    cache.delete(cache_key)

    # Also invalidate related lineage caches
    # Pattern: lineage:{contract_id}:*
    # Note: Django cache doesn't support pattern deletion natively
    # In production, use Redis with pattern deletion or maintain a cache key registry


def invalidate_lineage_cache(
    contract_id: str, model_name: str | None = None, field_name: str | None = None
) -> int:
    """
    Invalidate lineage cache.

    Args:
        contract_id: Contract UUID
        model_name: Optional model name
        field_name: Optional field name

    Returns:
        Number of keys invalidated (0 on non-pattern-capable backends,
        e.g. LocMem — staleness is then bounded by ``CACHE_TTL_LINEAGE``).
        Never raises: a cache outage must not block contract writes.

    W4.5 (R2-I2) — the contract-level call now pattern-deletes the WHOLE
    ``lineage:{contract_id}`` namespace: pre-fix the model- and
    field-scoped keys written by the field-level lineage reads were
    never deletable (the branch was literally ``pass`` with a "maintain
    a key registry" TODO) and served stale lineage until TTL after every
    edit. Uses the same backend-native ``delete_pattern`` +
    ``invalidate_cache_pattern`` path as
    :func:`invalidate_query_result_cache` (the bare-raw-KEYS generic
    scan misses the ``hub`` KEY_PREFIX — measured, not assumed).
    """
    cache_key = get_lineage_cache_key(contract_id, model_name, field_name)
    cache.delete(cache_key)

    if model_name or field_name:
        # Scoped call: the exact key is the whole scope.
        return 1

    pattern = f"lineage:{contract_id}*"
    try:
        if hasattr(cache, "delete_pattern"):
            return cache.delete_pattern(pattern)
        from hub.apps.core.caching.cache import invalidate_cache_pattern

        return invalidate_cache_pattern(pattern)
    except (
        Exception
    ) as exc:  # noqa: BLE001 - fail-soft: cache outage must not block writes
        logger.warning(
            "lineage_cache_invalidation_failed contract_id=%s error=%s",
            contract_id,
            exc,
        )
        return 0


def invalidate_lineage_resolution_cache(namespace: str, name: str) -> int:
    """Invalidate every lineage-resolution cache entry for
    ``namespace``/``name`` (all model/field scopes).

    W4.5 (R2-I2) — pre-fix the resolution entries (``lineage:resolve:...``)
    were never invalidated anywhere: a contract rename or structure edit
    left downstream reference resolution serving stale results until the
    1-hour ``CACHE_TTL_LINEAGE_RESOLUTION`` expired.

    Returns the number of keys invalidated; never raises.
    """
    pattern = f"lineage:resolve:{namespace}:{name}*"
    try:
        if hasattr(cache, "delete_pattern"):
            return cache.delete_pattern(pattern)
        from hub.apps.core.caching.cache import invalidate_cache_pattern

        return invalidate_cache_pattern(pattern)
    except (
        Exception
    ) as exc:  # noqa: BLE001 - fail-soft: cache outage must not block writes
        logger.warning(
            "lineage_resolution_cache_invalidation_failed "
            "namespace=%s name=%s error=%s",
            namespace,
            name,
            exc,
        )
        return 0


def invalidate_query_result_cache(tenant_id: str | None = None) -> int:
    """
    Invalidate the tenant's contract list query-result cache.

    The list endpoint (``ContractCRUDMixin.list`` in views_crud.py)
    caches every query-params combination under
    ``query_result:{tenant_id}:{hash}`` for ``CACHE_TTL_QUERY_RESULT``
    seconds — including the ``?asset_id=<id>`` queries the asset
    detail page issues. Without invalidation, a freshly created (or
    re-linked) contract stays invisible on the asset page and the
    contracts list until the TTL expires. This helper pattern-deletes
    the tenant's whole ``query_result`` namespace so the next list
    fetch re-hits the DB.

    Args:
        tenant_id: Tenant UUID string. ``None`` (or falsy) is a no-op —
            a cross-tenant wipe would be over-broad and unsafe.

    Returns:
        Number of cache keys invalidated (0 on non-pattern-capable
        backends, e.g. LocMem — staleness is then bounded by
        ``CACHE_TTL_QUERY_RESULT``). Never raises: a cache outage
        must not block contract writes.
    """
    if not tenant_id:
        return 0
    pattern = f"query_result:{tenant_id}:*"
    try:
        # Prefer the backend-native delete_pattern (django_redis): it
        # applies the configured KEY_PREFIX + versioning itself. The
        # generic core invalidator's raw KEYS scan does NOT — under
        # KEY_PREFIX="hub" the stored key is ``hub:1:query_result:...``
        # and the bare pattern never matches, making invalidation a
        # silent no-op (measured: fresh contracts stayed invisible on
        # the asset page past the 300s TTL).
        if hasattr(cache, "delete_pattern"):
            return cache.delete_pattern(pattern)
        from hub.apps.core.caching.cache import invalidate_cache_pattern

        return invalidate_cache_pattern(pattern)
    except Exception as exc:
        logger.warning(
            "query_result_cache_invalidation_failed tenant_id=%s error=%s",
            tenant_id,
            exc,
        )
        return 0


def warm_contract_cache(contract_ids: list[str]) -> None:
    """
    Warm cache with frequently accessed contracts.

    Args:
        contract_ids: List of contract UUIDs to warm
    """
    from hub.apps.contracts.models import Contract

    contracts = Contract.objects.filter(id__in=contract_ids).select_related(
        "tenant", "asset"
    )

    for contract in contracts:
        if contract.hub_contract_json:
            cache_contract(
                str(contract.id),
                {
                    "id": str(contract.id),
                    "hub_contract_json": contract.hub_contract_json,
                    "status": contract.status,
                    "normalization_status": contract.normalization_status,
                },
            )


def get_cache_stats() -> dict[str, Any]:
    """
    Get cache statistics (if supported by cache backend).

    Returns:
        Dictionary with cache statistics
    """
    # This is a placeholder - actual implementation depends on cache backend
    # Redis supports INFO stats, Django cache doesn't have a standard API
    return {
        "backend": getattr(settings, "CACHES", {})
        .get("default", {})
        .get("BACKEND", "unknown"),
        "note": "Cache statistics not available for this backend",
    }
