"""
Caching utilities for contract queries and lineage resolution.

Implements multi-level caching strategy for optimal performance.
"""
from typing import Any, Dict, List, Optional, Tuple
from django.core.cache import cache
from django.conf import settings
import hashlib
import json


# Cache TTLs (in seconds)
CACHE_TTL_CONTRACT = getattr(settings, 'CACHE_TTL_CONTRACT', 300)  # 5 minutes
CACHE_TTL_LINEAGE = getattr(settings, 'CACHE_TTL_LINEAGE', 600)  # 10 minutes
CACHE_TTL_QUERY_RESULT = getattr(settings, 'CACHE_TTL_QUERY_RESULT', 300)  # 5 minutes
CACHE_TTL_LINEAGE_RESOLUTION = getattr(settings, 'CACHE_TTL_LINEAGE_RESOLUTION', 3600)  # 1 hour


def get_contract_cache_key(contract_id: str) -> str:
    """Generate cache key for contract."""
    return f"contract:{contract_id}"


def get_lineage_cache_key(contract_id: str, model_name: Optional[str] = None, field_name: Optional[str] = None) -> str:
    """Generate cache key for lineage data."""
    if field_name:
        return f"lineage:{contract_id}:model:{model_name}:field:{field_name}"
    elif model_name:
        return f"lineage:{contract_id}:model:{model_name}"
    else:
        return f"lineage:{contract_id}"


def get_lineage_resolution_cache_key(namespace: str, name: str, model_name: Optional[str] = None, field: Optional[str] = None) -> str:
    """Generate cache key for lineage reference resolution."""
    parts = [f"lineage:resolve:{namespace}:{name}"]
    if model_name:
        parts.append(f"model:{model_name}")
    if field:
        parts.append(f"field:{field}")
    return ":".join(parts)


def get_query_result_cache_key(query_params: Dict[str, Any], tenant_id: str) -> str:
    """Generate cache key for query results."""
    # Create deterministic key from query parameters
    sorted_params = sorted(query_params.items())
    params_str = json.dumps(sorted_params, sort_keys=True)
    params_hash = hashlib.md5(params_str.encode()).hexdigest()
    return f"query_result:{tenant_id}:{params_hash}"


def cache_contract(contract_id: str, contract_data: Dict[str, Any], ttl: Optional[int] = None) -> None:
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


def get_cached_contract(contract_id: str) -> Optional[Dict[str, Any]]:
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
    lineage_data: Dict[str, Any],
    model_name: Optional[str] = None,
    field_name: Optional[str] = None,
    ttl: Optional[int] = None
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
    contract_id: str,
    model_name: Optional[str] = None,
    field_name: Optional[str] = None
) -> Optional[Dict[str, Any]]:
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
    resolution_result: Dict[str, Any],
    model_name: Optional[str] = None,
    field: Optional[str] = None,
    ttl: Optional[int] = None
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
    namespace: str,
    name: str,
    model_name: Optional[str] = None,
    field: Optional[str] = None
) -> Optional[Dict[str, Any]]:
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
    query_params: Dict[str, Any],
    tenant_id: str,
    results: List[Dict[str, Any]],
    total_count: int,
    ttl: Optional[int] = None
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
    cache_data = {
        'results': results,
        'total_count': total_count
    }
    cache.set(cache_key, cache_data, timeout=ttl)


def get_cached_query_result(
    query_params: Dict[str, Any],
    tenant_id: str
) -> Optional[Tuple[List[Dict[str, Any]], int]]:
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
        return cached_data.get('results'), cached_data.get('total_count')
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


def invalidate_lineage_cache(contract_id: str, model_name: Optional[str] = None, field_name: Optional[str] = None) -> None:
    """
    Invalidate lineage cache.
    
    Args:
        contract_id: Contract UUID
        model_name: Optional model name
        field_name: Optional field name
    """
    cache_key = get_lineage_cache_key(contract_id, model_name, field_name)
    cache.delete(cache_key)
    
    # If invalidating contract-level lineage, also invalidate model and field level
    if not model_name and not field_name:
        # Invalidate all lineage caches for this contract
        # In production, use Redis pattern deletion or maintain key registry
        pass


def invalidate_query_result_cache(tenant_id: Optional[str] = None) -> None:
    """
    Invalidate query result cache.
    
    Args:
        tenant_id: Optional tenant UUID (if None, invalidates all)
    """
    # In production, use Redis pattern deletion: query_result:{tenant_id}:*
    # For now, this is a placeholder
    # In Django cache, we'd need to maintain a registry of cache keys
    pass


def warm_contract_cache(contract_ids: List[str]) -> None:
    """
    Warm cache with frequently accessed contracts.
    
    Args:
        contract_ids: List of contract UUIDs to warm
    """
    from hub.apps.contracts.models import Contract
    
    contracts = Contract.objects.filter(id__in=contract_ids).select_related('tenant', 'asset')
    
    for contract in contracts:
        if contract.hub_contract_json:
            cache_contract(
                str(contract.id),
                {
                    'id': str(contract.id),
                    'hub_contract_json': contract.hub_contract_json,
                    'status': contract.status,
                    'normalization_status': contract.normalization_status,
                }
            )


def get_cache_stats() -> Dict[str, Any]:
    """
    Get cache statistics (if supported by cache backend).
    
    Returns:
        Dictionary with cache statistics
    """
    # This is a placeholder - actual implementation depends on cache backend
    # Redis supports INFO stats, Django cache doesn't have a standard API
    return {
        'backend': getattr(settings, 'CACHES', {}).get('default', {}).get('BACKEND', 'unknown'),
        'note': 'Cache statistics not available for this backend'
    }

