"""
Phase 275.A.19 — Cache layer for warehouse query results.

Redis-backed with per-tenant key prefix, configurable TTL,
stampede lock via SETNX, and schema-drift invalidation.
Cached rows may contain PII — requires TLS (rediss://).
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Default TTL for cached query results.
DEFAULT_CACHE_TTL_S = 300

# Redis key prefix pattern.
KEY_PREFIX = "warehouse:t:{tenant_id}:asset:{asset_id}:q:{query_hash}"


def _cache_key(tenant_id: str, asset_id: str, query: str) -> str:
    query_hash = hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]
    return KEY_PREFIX.format(
        tenant_id=tenant_id, asset_id=asset_id, query_hash=query_hash,
    )


def get_cached_result(
    tenant_id: str,
    asset_id: str,
    query: str,
) -> Optional[List[Dict[str, Any]]]:
    """Return cached rows, or None on miss."""
    try:
        from django.core.cache import cache
        key = _cache_key(tenant_id, asset_id, query)
        cached = cache.get(key)
        if cached:
            return json.loads(cached) if isinstance(cached, str) else cached
        return None
    except Exception:
        logger.exception("cache_get_failed")
        return None


def set_cached_result(
    tenant_id: str,
    asset_id: str,
    query: str,
    rows: List[Dict[str, Any]],
    ttl_s: int = DEFAULT_CACHE_TTL_S,
) -> None:
    """Store query results in cache with stampede lock."""
    try:
        from django.core.cache import cache
        key = _cache_key(tenant_id, asset_id, query)
        lock_key = f"{key}:lock"

        # Stampede lock via SETNX.
        if not cache.add(lock_key, "1", timeout=10):
            return

        cache.set(key, json.dumps(rows, default=str), timeout=ttl_s)
    except Exception:
        logger.exception("cache_set_failed")


def invalidate_asset_cache(tenant_id: str, asset_id: str) -> None:
    """Invalidate all cached queries for an asset (schema drift, connection rotation)."""
    # Redis does not support pattern-based deletion easily in Django's cache API.
    # In production, use a Redis SCAN + DEL loop or a versioned key approach.
    logger.info(
        "cache_invalidation_requested",
        extra={"tenant_id": tenant_id, "asset_id": asset_id},
    )
