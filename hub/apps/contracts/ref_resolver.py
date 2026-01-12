"""
ODPS $ref Resolver

Provides secure resolution of $ref references in ODPS documents with support for:
- Internal references (#/definitions/...)
- Local references (./path/to/file.json)
- External references (https://example.com/schema.json)

Security Features:
- URL validation (allowlist/denylist)
- Path traversal prevention
- Size limits
- Timeout controls
- Redis caching for external refs (TTL: 1 hour)
"""
import json
import os
import time
import uuid
import hashlib
import copy
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Set, List
from urllib.parse import urlparse, urljoin
import structlog

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    yaml = None

import httpx
from django.conf import settings
from django.core.cache import cache as django_cache

from hub.apps.contracts.config.odps_refs_config import (
    get_odps_refs_config,
    ODPSRefsConfig,
)
from hub.apps.contracts.odps_security_logging import (
    SecurityEventType,
    SecuritySeverity,
    get_security_logger,
)
from hub.apps.contracts.odps_rate_limiting import check_rate_limit
from hub.apps.contracts.odps_errors import ODPSRefResolutionError
from hub.apps.contracts.source_paths import resolve_json_pointer
from hub.apps.observability.otel_metrics import (
    odps_ref_resolution_total,
    odps_ref_resolution_failures_total,
    odps_external_fetch_failures_total,
    odps_ref_resolution_duration_seconds,
    odps_ref_cache_hits_total,
    odps_ref_cache_misses_total,
    odps_ref_cache_hit_rate,
    odps_ref_cache_miss_rate,
    odps_ref_cache_size,
    odps_ref_cache_size_limit,
    odps_ref_cache_eviction_rate,
)

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

logger = structlog.get_logger(__name__)

# Default configuration values
DEFAULT_TIMEOUT_PER_REF = 5  # seconds
DEFAULT_TIMEOUT_TOTAL = 30  # seconds
DEFAULT_MAX_REF_SIZE = 1048576  # 1MB in bytes
DEFAULT_MAX_TOTAL_SIZE = 10485760  # 10MB in bytes
DEFAULT_CACHE_TTL = 3600  # 1 hour in seconds
DEFAULT_CACHE_MAX_ENTRIES = 1000  # Maximum number of cached refs

# Redis cache key prefix
REDIS_CACHE_PREFIX = "odps_ref:"
REDIS_CACHE_INDEX_PREFIX = "odps_ref_index:"  # For LRU tracking
REDIS_CACHE_STATS_PREFIX = "odps_ref_stats:"  # For hit rate tracking
REDIS_CACHE_ACCESS_PREFIX = "odps_ref_access:"  # For per-URL access tracking
# Maximum URL length for external $ref (2048 characters)
MAX_URL_LENGTH = 2048


class RefMode(str, Enum):
    """$ref resolution modes"""
    INTERNAL = "internal"  # #/definitions/...
    LOCAL = "local"  # ./path/to/file.json
    EXTERNAL = "external"  # https://example.com/schema.json


class ExternalRefHandling(str, Enum):
    """External $ref handling modes"""
    RESOLVE = "resolve"  # Resolve external refs (default behavior)
    REMOVE = "remove"  # Remove external refs (delete the $ref key)
    REPLACE = "replace"  # Replace external refs with resolved content
    DISABLE = "disable"  # Disable external refs (raise error if found)


class RefResolver:
    """
    Secure $ref resolver for ODPS documents.

    Supports three modes:
    - Internal: References within the same document (#/definitions/...)
    - Local: References to local files (./path/to/file.json)
    - External: References to external URLs (https://example.com/schema.json)

    Security Features:
    - URL validation (allowlist/denylist)
    - Path traversal prevention
    - Size limits (per-ref and total)
    - Timeout controls (per-ref and total)
    - Redis caching for external refs (TTL: 1 hour)
    """

    def __init__(
        self,
        config: Optional[ODPSRefsConfig] = None,
        base_path: Optional[Path] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        timeout_per_ref: int = DEFAULT_TIMEOUT_PER_REF,
        timeout_total: int = DEFAULT_TIMEOUT_TOTAL,
        max_ref_size: int = DEFAULT_MAX_REF_SIZE,
        max_total_size: int = DEFAULT_MAX_TOTAL_SIZE,
        cache_ttl: int = DEFAULT_CACHE_TTL,
        enable_caching: bool = True,
    ):
        """
        Initialize RefResolver.

        Args:
            config: ODPS refs configuration instance. If None, uses global config.
            base_path: Base path for resolving local $ref paths. If None, uses current working directory.
            tenant_id: Tenant ID for rate limiting and audit logging.
            user_id: User ID for rate limiting and audit logging.
            timeout_per_ref: Timeout per $ref fetch in seconds.
            timeout_total: Total timeout for all $ref resolution in seconds.
            max_ref_size: Maximum size per $ref file in bytes.
            max_total_size: Maximum total size for all resolved refs in bytes.
            cache_ttl: Cache TTL in seconds for external refs.
            enable_caching: Whether to enable Redis caching for external refs.
        """
        self.config = config or get_odps_refs_config()
        self.base_path = base_path or Path.cwd()
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.timeout_per_ref = timeout_per_ref
        self.timeout_total = timeout_total
        self.max_ref_size = max_ref_size
        self.max_total_size = max_total_size
        self.cache_ttl = cache_ttl
        self.enable_caching = enable_caching

        # Track total size of resolved refs
        self._total_size = 0
        self._start_time = None

        # Track refs being resolved (for circular reference detection)
        self._resolving_refs: Set[str] = set()

        # Get security logger
        self._security_logger = get_security_logger()

        # Cache configuration
        self.cache_max_entries = DEFAULT_CACHE_MAX_ENTRIES

        # Get Redis client for caching
        self._redis_client = None
        if self.enable_caching and REDIS_AVAILABLE:
            self._redis_client = self._get_redis_client()

    def _get_redis_client(self) -> Optional[Any]:
        """Get Redis client for caching."""
        if not REDIS_AVAILABLE:
            return None

        redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')
        try:
            client = redis.from_url(
                redis_url,
                decode_responses=False,  # Keep binary for JSON storage
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            client.ping()
            return client
        except Exception as e:
            logger.warning(
                "ref_resolver_redis_unavailable",
                error=str(e),
                redis_url=redis_url,
                message="External ref caching will be disabled"
            )
            return None

    def _get_cache_key(self, ref_path: str, content_hash: Optional[str] = None) -> str:
        """
        Generate cache key for a $ref path.

        Cache key format: `odps_ref:{url_hash}:{content_hash}`
        - url_hash: SHA-256 hash of the URL
        - content_hash: SHA-256 hash of the content (optional, for content-based caching)

        Args:
            ref_path: $ref path/URL
            content_hash: Optional content hash for content-based caching

        Returns:
            Cache key string
        """
        # Hash the URL for cache key
        url_hash = hashlib.sha256(ref_path.encode('utf-8')).hexdigest()[:16]  # Use first 16 chars for brevity

        if content_hash:
            # Content-based cache key (for invalidation when content changes)
            return f"{REDIS_CACHE_PREFIX}{url_hash}:{content_hash[:16]}"
        else:
            # URL-based cache key (for initial lookup)
            return f"{REDIS_CACHE_PREFIX}{url_hash}:"

    def _get_from_cache(self, ref_path: str) -> Optional[Dict[str, Any]]:
        """
        Get resolved $ref from Redis cache.

        Cache key format: `odps_ref:{url_hash}:{content_hash}`

        Uses a two-level cache strategy:
        1. Look up content hash from URL hash mapping: `odps_ref:{url_hash}` -> `{content_hash}`
        2. Retrieve data using full key: `odps_ref:{url_hash}:{content_hash}` -> `{data}`

        Args:
            ref_path: $ref URL

        Returns:
            Cached data if found, None otherwise
        """
        if not self._redis_client:
            return None

        try:
            # Calculate URL hash
            url_hash = hashlib.sha256(ref_path.encode('utf-8')).hexdigest()[:16]

            # First, get the content hash from the URL hash mapping
            # Format: odps_ref:{url_hash} -> {content_hash}
            url_key = f"{REDIS_CACHE_PREFIX}{url_hash}"
            content_hash_bytes = self._redis_client.get(url_key)

            if content_hash_bytes:
                # Decode content hash
                content_hash = content_hash_bytes.decode('utf-8')

                # Get the actual data using the full cache key
                # Format: odps_ref:{url_hash}:{content_hash} -> {data}
                cache_key = self._get_cache_key(ref_path, content_hash)
                cached_data = self._redis_client.get(cache_key)

                if cached_data:
                    # Decode JSON from bytes
                    data = json.loads(cached_data.decode('utf-8'))
                    # Update LRU index (mark as recently used)
                    self._update_lru_index(cache_key)
                    # Track cache hit
                    self._track_cache_hit()
                    # Track per-URL access for cache warming
                    self._track_ref_access(ref_path)
                    return data
            else:
                # Cache miss
                self._track_cache_miss()
                # Track per-URL access even on miss (for warming)
                self._track_ref_access(ref_path)
        except Exception as e:
            logger.debug(
                "ref_resolver_cache_get_failed",
                ref_path=ref_path,
                error=str(e),
                message="Cache get failed, will fetch from source"
            )
        return None

    def _set_cache(self, ref_path: str, data: Dict[str, Any], content_bytes: Optional[bytes] = None) -> None:
        """
        Store resolved $ref in Redis cache with LRU eviction and size limits.

        Cache key format: `odps_ref:{url_hash}:{content_hash}`

        Implements:
        - Content-based caching (invalidates on content change)
        - LRU eviction when cache exceeds max_entries
        - Cache size limits (max 1000 refs)

        Args:
            ref_path: $ref URL
            data: Resolved data to cache
            content_bytes: Optional raw content bytes for content hash calculation
        """
        if not self._redis_client:
            return

        try:
            # Calculate content hash from data or content_bytes
            if content_bytes:
                content_hash = hashlib.sha256(content_bytes).hexdigest()[:16]
            else:
                # Calculate hash from JSON representation
                json_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
                content_hash = hashlib.sha256(json_str.encode('utf-8')).hexdigest()[:16]

            # Generate cache key with content hash (primary storage)
            # Format: odps_ref:{url_hash}:{content_hash}
            cache_key = self._get_cache_key(ref_path, content_hash)

            # Calculate URL hash
            url_hash = hashlib.sha256(ref_path.encode('utf-8')).hexdigest()[:16]

            # Store URL hash -> content hash mapping for quick lookup
            # Format: odps_ref:{url_hash} -> {content_hash}
            url_key = f"{REDIS_CACHE_PREFIX}{url_hash}"

            # Check if this URL already has a cached entry with different content hash
            existing_content_hash_bytes = self._redis_client.get(url_key)
            if existing_content_hash_bytes:
                existing_content_hash = existing_content_hash_bytes.decode('utf-8')
                if existing_content_hash != content_hash:
                    # Content changed - invalidate old cache entry
                    old_cache_key = self._get_cache_key(ref_path, existing_content_hash)
                    deleted = self._redis_client.delete(old_cache_key)
                    # Remove from LRU index
                    self._remove_from_lru_index(old_cache_key)

                    # Track eviction metrics
                    if deleted:
                        tenant_id = self.tenant_id or 'unknown'
                        eviction_reason = 'content_changed'
                        odps_ref_cache_eviction_rate.labels(
                            eviction_reason=eviction_reason,
                            tenant_id=tenant_id
                        ).inc()
                        # Log cache eviction
                        self._security_logger.log_cache_operation(
                            operation="eviction",
                            cache_key=old_cache_key,
                            eviction_reason=eviction_reason,
                            tenant_id=self.tenant_id,
                            user_id=self.user_id,
                        )
                        # Update cache size gauge
                        self._update_cache_size_gauge(tenant_id)

            # Encode JSON to bytes
            json_data = json.dumps(data, sort_keys=True, ensure_ascii=False)
            json_bytes = json_data.encode('utf-8')

            # Enforce cache size limits with LRU eviction
            self._enforce_cache_size_limits()

            # Store data with content-hashed key (primary storage)
            # Format: odps_ref:{url_hash}:{content_hash} -> {data}
            self._redis_client.setex(
                cache_key,
                self.cache_ttl,
                json_bytes
            )

            # Store URL hash -> content hash mapping for quick lookup
            # Format: odps_ref:{url_hash} -> {content_hash}
            self._redis_client.setex(
                url_key,
                self.cache_ttl,
                content_hash.encode('utf-8')
            )

            # Update LRU index (add to front of list)
            self._update_lru_index(cache_key)

            # Track cache write (this also updates cache size gauge)
            self._track_cache_write()
        except Exception as e:
            logger.debug(
                "ref_resolver_cache_set_failed",
                ref_path=ref_path,
                error=str(e),
                message="Cache set failed, continuing without cache"
            )

    def _update_lru_index(self, cache_key: str) -> None:
        """
        Update LRU index by moving cache_key to the front (most recently used).

        Uses Redis list to track access order for LRU eviction.

        Args:
            cache_key: Cache key to update in LRU index
        """
        if not self._redis_client:
            return

        try:
            lru_index_key = f"{REDIS_CACHE_INDEX_PREFIX}lru"
            # Remove key if it exists (to avoid duplicates)
            self._redis_client.lrem(lru_index_key, 0, cache_key)
            # Add to front (most recently used)
            self._redis_client.lpush(lru_index_key, cache_key)
            # Set TTL on index (same as cache entries)
            self._redis_client.expire(lru_index_key, self.cache_ttl)
        except Exception as e:
            logger.debug(
                "ref_resolver_lru_update_failed",
                cache_key=cache_key,
                error=str(e),
                message="LRU index update failed"
            )

    def _remove_from_lru_index(self, cache_key: str) -> None:
        """
        Remove cache key from LRU index.

        Args:
            cache_key: Cache key to remove from LRU index
        """
        if not self._redis_client:
            return

        try:
            lru_index_key = f"{REDIS_CACHE_INDEX_PREFIX}lru"
            self._redis_client.lrem(lru_index_key, 0, cache_key)
        except Exception as e:
            logger.debug(
                "ref_resolver_lru_remove_failed",
                cache_key=cache_key,
                error=str(e),
                message="LRU index removal failed"
            )

    def _enforce_cache_size_limits(self) -> None:
        """
        Enforce cache size limits by evicting least recently used entries.

        Evicts entries when cache exceeds max_entries limit using LRU algorithm.
        """
        if not self._redis_client:
            return

        try:
            lru_index_key = f"{REDIS_CACHE_INDEX_PREFIX}lru"
            current_size = self._redis_client.llen(lru_index_key)

            if current_size >= self.cache_max_entries:
                # Calculate how many entries to evict (evict 10% or at least 1)
                evict_count = max(1, int(self.cache_max_entries * 0.1))
                evict_count = min(evict_count, current_size - int(self.cache_max_entries * 0.9))

                # Get least recently used keys (from end of list)
                keys_to_evict = self._redis_client.lrange(
                    lru_index_key,
                    -evict_count,
                    -1
                )

                # Evict keys
                for key_bytes in keys_to_evict:
                    key = key_bytes.decode('utf-8') if isinstance(key_bytes, bytes) else key_bytes
                    # Delete cache entry
                    self._redis_client.delete(key)
                    # Remove from LRU index
                    self._redis_client.lrem(lru_index_key, 0, key)

                # Track eviction metrics
                tenant_id = self.tenant_id or 'unknown'
                eviction_reason = 'size_limit'
                odps_ref_cache_eviction_rate.labels(
                    eviction_reason=eviction_reason,
                    tenant_id=tenant_id
                ).inc(evict_count)

                # Log cache evictions
                for key_bytes in keys_to_evict:
                    key = key_bytes.decode('utf-8') if isinstance(key_bytes, bytes) else key_bytes
                    self._security_logger.log_cache_operation(
                        operation="eviction",
                        cache_key=key,
                        eviction_reason=eviction_reason,
                        tenant_id=self.tenant_id,
                        user_id=self.user_id,
                    )

                # Update cache size gauge
                new_size = current_size - evict_count
                ref_type = 'external'  # Cache is only for external refs
                odps_ref_cache_size.labels(
                    tenant_id=tenant_id,
                    ref_type=ref_type
                ).set(new_size)

                logger.debug(
                    "ref_resolver_cache_eviction",
                    evicted_count=evict_count,
                    cache_size_before=current_size,
                    cache_size_after=new_size,
                    message=f"Evicted {evict_count} cache entries due to size limit"
                )
        except Exception as e:
            logger.debug(
                "ref_resolver_cache_size_limit_failed",
                error=str(e),
                message="Cache size limit enforcement failed"
            )

    def _track_cache_write(self) -> None:
        """Track cache write for statistics."""
        if not self._redis_client:
            return

        try:
            stats_key = f"{REDIS_CACHE_STATS_PREFIX}writes"
            self._redis_client.incr(stats_key)
            self._redis_client.expire(stats_key, self.cache_ttl * 24)  # Keep stats for 24 hours

            # Update cache size gauge
            tenant_id = self.tenant_id or 'unknown'
            self._update_cache_size_gauge(tenant_id)
        except Exception:
            pass  # Stats tracking failure should not affect caching

    def _update_cache_rate_gauges(self, tenant_id: str, ref_type: str) -> None:
        """
        Update cache hit/miss rate gauges from Redis stats.

        Args:
            tenant_id: Tenant ID
            ref_type: Reference type (always 'external' for cache)
        """
        if not self._redis_client:
            return

        try:
            hits_key = f"{REDIS_CACHE_STATS_PREFIX}hits"
            misses_key = f"{REDIS_CACHE_STATS_PREFIX}misses"

            hits_bytes = self._redis_client.get(hits_key)
            misses_bytes = self._redis_client.get(misses_key)

            hits_count = int(hits_bytes.decode('utf-8')) if hits_bytes else 0
            misses_count = int(misses_bytes.decode('utf-8')) if misses_bytes else 0

            total = hits_count + misses_count
            if total > 0:
                hit_rate = hits_count / total
                miss_rate = misses_count / total

                # Update gauges
                odps_ref_cache_hit_rate.labels(
                    ref_type=ref_type,
                    tenant_id=tenant_id
                ).set(hit_rate)

                odps_ref_cache_miss_rate.labels(
                    ref_type=ref_type,
                    tenant_id=tenant_id
                ).set(miss_rate)
        except Exception:
            pass  # Metrics failure should not affect caching

    def _update_cache_size_gauge(self, tenant_id: str) -> None:
        """
        Update cache size gauge from Redis LRU index.

        Tracks:
        - Current cache size (number of entries)
        - Cache size limit (1000 entries)
        - Cache size by ref_type (always 'external' for cache)

        Args:
            tenant_id: Tenant ID
        """
        if not self._redis_client:
            return

        try:
            lru_index_key = f"{REDIS_CACHE_INDEX_PREFIX}lru"
            current_size = self._redis_client.llen(lru_index_key)
            ref_type = 'external'  # Cache is only for external refs

            # Update cache size gauge (current number of entries)
            odps_ref_cache_size.labels(
                tenant_id=tenant_id,
                ref_type=ref_type
            ).set(current_size)

            # Update cache size limit gauge (constant limit)
            odps_ref_cache_size_limit.labels(
                tenant_id=tenant_id,
                ref_type=ref_type
            ).set(self.cache_max_entries)
        except Exception:
            pass  # Metrics failure should not affect caching

    def _track_ref_access(self, ref_path: str) -> None:
        """
        Track per-URL access for cache warming identification.

        Stores access count per URL in Redis sorted set for frequency analysis.

        Args:
            ref_path: $ref URL being accessed
        """
        if not self._redis_client:
            return

        try:
            # Only track external refs (cache warming is only for external refs)
            if not ref_path.startswith(('http://', 'https://')):
                return

            # Use URL hash as key for access tracking
            url_hash = hashlib.sha256(ref_path.encode('utf-8')).hexdigest()[:16]
            access_key = f"{REDIS_CACHE_ACCESS_PREFIX}{url_hash}"

            # Increment access count (using sorted set score)
            # Score represents access count, member is the URL hash
            # zincrby(key, increment, member) - increment score by 1
            self._redis_client.zincrby(REDIS_CACHE_ACCESS_PREFIX + "all", 1, url_hash.encode('utf-8'))

            # Store URL mapping (hash -> URL) for later retrieval
            url_mapping_key = f"{REDIS_CACHE_ACCESS_PREFIX}url:{url_hash}"
            self._redis_client.setex(url_mapping_key, self.cache_ttl * 24, ref_path.encode('utf-8'))

            # Set expiration on sorted set (24 hours)
            self._redis_client.expire(REDIS_CACHE_ACCESS_PREFIX + "all", self.cache_ttl * 24)
        except Exception:
            pass  # Access tracking failure should not affect caching

    def _track_cache_hit(self) -> None:
        """Track cache hit for statistics."""
        if not self._redis_client:
            return

        try:
            stats_key = f"{REDIS_CACHE_STATS_PREFIX}hits"
            self._redis_client.incr(stats_key)
            self._redis_client.expire(stats_key, self.cache_ttl * 24)  # Keep stats for 24 hours
        except Exception:
            pass  # Stats tracking failure should not affect caching

        # Track cache hit in Prometheus metrics
        try:
            tenant_id = self.tenant_id or 'unknown'
            ref_type = 'external'  # Cache is only for external refs
            odps_ref_cache_hits_total.labels(tenant_id=tenant_id).inc()

            # Update hit rate gauge (calculate from Redis stats)
            self._update_cache_rate_gauges(tenant_id, ref_type)
        except Exception:
            pass  # Metrics failure should not affect caching

    def _track_cache_miss(self) -> None:
        """Track cache miss for statistics."""
        if not self._redis_client:
            return

        try:
            stats_key = f"{REDIS_CACHE_STATS_PREFIX}misses"
            self._redis_client.incr(stats_key)
            self._redis_client.expire(stats_key, self.cache_ttl * 24)  # Keep stats for 24 hours
        except Exception:
            pass  # Stats tracking failure should not affect caching

        # Track cache miss in Prometheus metrics
        try:
            tenant_id = self.tenant_id or 'unknown'
            ref_type = 'external'  # Cache is only for external refs
            odps_ref_cache_misses_total.labels(tenant_id=tenant_id).inc()

            # Update miss rate gauge (calculate from Redis stats)
            self._update_cache_rate_gauges(tenant_id, ref_type)
        except Exception:
            pass  # Metrics failure should not affect caching

    def get_cache_hit_rate(self) -> Optional[float]:
        """
        Get cache hit rate (hits / (hits + misses)).

        Returns:
            Hit rate as float between 0.0 and 1.0, or None if stats unavailable
        """
        if not self._redis_client:
            return None

        try:
            hits_key = f"{REDIS_CACHE_STATS_PREFIX}hits"
            misses_key = f"{REDIS_CACHE_STATS_PREFIX}misses"

            hits = self._redis_client.get(hits_key)
            misses = self._redis_client.get(misses_key)

            hits_count = int(hits.decode('utf-8')) if hits else 0
            misses_count = int(misses.decode('utf-8')) if misses else 0

            total = hits_count + misses_count
            if total == 0:
                return None

            return hits_count / total
        except Exception as e:
            logger.debug(
                "ref_resolver_cache_stats_failed",
                error=str(e),
                message="Cache hit rate calculation failed"
            )
            return None

    def invalidate_cache(self, ref_path: Optional[str] = None) -> int:
        """
        Invalidate cache entries.

        Args:
            ref_path: Optional specific URL to invalidate. If None, invalidates all cache entries.

        Returns:
            Number of cache entries invalidated
        """
        if not self._redis_client:
            return 0

        try:
            if ref_path:
                # Invalidate specific URL
                url_hash = hashlib.sha256(ref_path.encode('utf-8')).hexdigest()[:16]
                url_key = f"{REDIS_CACHE_PREFIX}{url_hash}"

                # Get content hash
                content_hash_bytes = self._redis_client.get(url_key)
                if content_hash_bytes:
                    content_hash = content_hash_bytes.decode('utf-8')
                    cache_key = self._get_cache_key(ref_path, content_hash)

                    # Delete cache entry and URL mapping
                    deleted = 0
                    if self._redis_client.delete(cache_key):
                        deleted += 1
                    if self._redis_client.delete(url_key):
                        deleted += 1

                    # Remove from LRU index
                    self._remove_from_lru_index(cache_key)

                    # Track eviction metrics
                    tenant_id = self.tenant_id or 'unknown'
                    eviction_reason = 'manual_invalidation'
                    if deleted > 0:
                        odps_ref_cache_eviction_rate.labels(
                            eviction_reason=eviction_reason,
                            tenant_id=tenant_id
                        ).inc(deleted)
                        # Update cache size gauge
                        self._update_cache_size_gauge(tenant_id)

                    return deleted
                return 0
            else:
                # Invalidate all cache entries
                pattern = f"{REDIS_CACHE_PREFIX}*"
                keys = []
                cursor = 0
                while True:
                    cursor, batch = self._redis_client.scan(cursor, match=pattern, count=100)
                    keys.extend(batch)
                    if cursor == 0:
                        break

                # Also get LRU index keys
                lru_pattern = f"{REDIS_CACHE_INDEX_PREFIX}*"
                cursor = 0
                while True:
                    cursor, batch = self._redis_client.scan(cursor, match=lru_pattern, count=100)
                    keys.extend(batch)
                    if cursor == 0:
                        break

                if keys:
                    deleted = self._redis_client.delete(*keys)

                    # Track eviction metrics
                    tenant_id = self.tenant_id or 'unknown'
                    eviction_reason = 'manual_invalidation_all'
                    if deleted > 0:
                        odps_ref_cache_eviction_rate.labels(
                            eviction_reason=eviction_reason,
                            tenant_id=tenant_id
                        ).inc(deleted)
                        # Update cache size gauge
                        self._update_cache_size_gauge(tenant_id)

                    return deleted
                return 0
        except Exception as e:
            logger.warning(
                "ref_resolver_cache_invalidation_failed",
                ref_path=ref_path,
                error=str(e),
                message="Cache invalidation failed"
            )
            return 0

    def _validate_external_url(self, url: str) -> None:
        """
        Validate external $ref URL.

        Validates:
        - URL length (max 2048 characters)
        - Scheme (http/https only)
        - Host presence and format
        - Basic URL structure

        Args:
            url: URL to validate

        Raises:
            ODPSRefResolutionError: If URL validation fails
        """
        # Check URL length
        if len(url) > MAX_URL_LENGTH:
            self._security_logger.log_security_violation(
                event_type=SecurityEventType.INVALID_URL,
                severity=SecuritySeverity.MEDIUM,
                violation_type="URL too long",
                description=f"External $ref URL length {len(url)} exceeds maximum {MAX_URL_LENGTH} characters",
                attempted_url=url,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
            )
            raise ODPSRefResolutionError(
                message=f"External $ref URL length {len(url)} exceeds maximum {MAX_URL_LENGTH} characters",
                error_code=ODPSRefResolutionError.ERROR_CODE_INVALID_REF,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
            )

        # Parse URL
        try:
            parsed = urlparse(url)
        except Exception as e:
            self._security_logger.log_security_violation(
                event_type=SecurityEventType.INVALID_URL,
                severity=SecuritySeverity.MEDIUM,
                violation_type="Invalid URL format",
                description=f"External $ref URL '{url}' is not a valid URL: {str(e)}",
                attempted_url=url,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
            )
            raise ODPSRefResolutionError(
                message=f"External $ref URL '{url}' is not a valid URL: {str(e)}",
                error_code=ODPSRefResolutionError.ERROR_CODE_INVALID_REF,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
            ) from e

        # Validate scheme (http/https only)
        if parsed.scheme not in ('http', 'https'):
            self._security_logger.log_security_violation(
                event_type=SecurityEventType.INVALID_URL,
                severity=SecuritySeverity.HIGH,
                violation_type="Invalid URL scheme",
                description=f"External $ref URL '{url}' has invalid scheme '{parsed.scheme}'. Only http and https are allowed",
                attempted_url=url,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
            )
            raise ODPSRefResolutionError(
                message=f"External $ref URL '{url}' has invalid scheme '{parsed.scheme}'. Only http and https are allowed",
                error_code=ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
            )

        # Validate host (netloc) is present
        if not parsed.netloc:
            self._security_logger.log_security_violation(
                event_type=SecurityEventType.INVALID_URL,
                severity=SecuritySeverity.MEDIUM,
                violation_type="Missing URL host",
                description=f"External $ref URL '{url}' is missing host (netloc)",
                attempted_url=url,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
            )
            raise ODPSRefResolutionError(
                message=f"External $ref URL '{url}' is missing host",
                error_code=ODPSRefResolutionError.ERROR_CODE_INVALID_REF,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
            )

        # Validate host format (basic check)
        # Host should not contain invalid characters or be empty
        if not parsed.netloc or len(parsed.netloc) == 0:
            self._security_logger.log_security_violation(
                event_type=SecurityEventType.INVALID_URL,
                severity=SecuritySeverity.MEDIUM,
                violation_type="Invalid URL host",
                description=f"External $ref URL '{url}' has invalid or empty host",
                attempted_url=url,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
            )
            raise ODPSRefResolutionError(
                message=f"External $ref URL '{url}' has invalid or empty host",
                error_code=ODPSRefResolutionError.ERROR_CODE_INVALID_REF,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
            )

        # Additional host validation: check for suspicious patterns
        # Reject localhost/private IPs unless explicitly allowed (security measure)
        host_lower = parsed.netloc.lower()
        if host_lower.startswith('localhost') or host_lower.startswith('127.') or host_lower.startswith('0.0.0.0'):
            # This is a security measure - localhost URLs could be used for SSRF attacks
            # In production, you might want to allow this based on configuration
            logger.warning(
                "ref_resolver_localhost_url",
                url=url,
                host=parsed.netloc,
                message="External $ref URL points to localhost - potential SSRF risk"
            )

    def _detect_mode(self, ref_path: str) -> RefMode:
        """
        Detect $ref resolution mode from path.

        Args:
            ref_path: $ref path/value

        Returns:
            RefMode enum value
        """
        if not ref_path:
            raise ValueError("$ref path cannot be empty")

        # Internal reference: starts with #
        if ref_path.startswith('#'):
            return RefMode.INTERNAL

        # External reference: starts with http:// or https://
        if ref_path.startswith(('http://', 'https://')):
            return RefMode.EXTERNAL

        # Local reference: starts with ./ or ../ or is a relative path
        if ref_path.startswith(('./', '../')) or not Path(ref_path).is_absolute():
            return RefMode.LOCAL

        # Default to local for relative paths
        return RefMode.LOCAL

    def _check_timeout(self) -> None:
        """Check if total timeout has been exceeded."""
        if self._start_time is None:
            self._start_time = time.time()
            return

        elapsed = time.time() - self._start_time
        if elapsed > self.timeout_total:
            self._security_logger.log_security_violation(
                event_type=SecurityEventType.TIMEOUT,
                severity=SecuritySeverity.MEDIUM,
                violation_type="Total timeout exceeded",
                description=f"Total $ref resolution timeout exceeded: {elapsed:.2f}s > {self.timeout_total}s",
                tenant_id=self.tenant_id,
                user_id=self.user_id,
            )
            raise ODPSRefResolutionError(
                message=f"Total $ref resolution timeout exceeded: {elapsed:.2f}s > {self.timeout_total}s",
                error_code=ODPSRefResolutionError.ERROR_CODE_RESOLUTION_FAILED,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
            )

    def _check_size_limit(self, size: int) -> None:
        """
        Check if size limit would be exceeded.

        Args:
            size: Size in bytes to add

        Raises:
            ODPSRefResolutionError: If size limit would be exceeded
        """
        if size > self.max_ref_size:
            self._security_logger.log_security_violation(
                event_type=SecurityEventType.SIZE_LIMIT_EXCEEDED,
                severity=SecuritySeverity.MEDIUM,
                violation_type="Per-ref size limit exceeded",
                description=f"$ref size {size} bytes exceeds limit {self.max_ref_size} bytes",
                tenant_id=self.tenant_id,
                user_id=self.user_id,
            )
            raise ODPSRefResolutionError(
                message=f"$ref size {size} bytes exceeds limit {self.max_ref_size} bytes",
                error_code=ODPSRefResolutionError.ERROR_CODE_RESOLUTION_FAILED,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
            )

        if self._total_size + size > self.max_total_size:
            self._security_logger.log_security_violation(
                event_type=SecurityEventType.SIZE_LIMIT_EXCEEDED,
                severity=SecuritySeverity.MEDIUM,
                violation_type="Total size limit exceeded",
                description=f"Total size {self._total_size + size} bytes exceeds limit {self.max_total_size} bytes",
                tenant_id=self.tenant_id,
                user_id=self.user_id,
            )
            raise ODPSRefResolutionError(
                message=f"Total size {self._total_size + size} bytes exceeds limit {self.max_total_size} bytes",
                error_code=ODPSRefResolutionError.ERROR_CODE_RESOLUTION_FAILED,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
            )

        self._total_size += size

    def resolve_internal(self, ref_path: str, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve internal $ref (within the same document) using JSON Pointer syntax.

        Supports RFC 6901 JSON Pointer specification:
        - Path segments separated by '/'
        - Escaping: '~0' represents '~', '~1' represents '/'
        - Array indices: numeric strings for array access
        - Root reference: '#' or '#/' refers to the entire document

        Args:
            ref_path: Internal $ref path (e.g., "#/definitions/Email", "#/product/dataQuality")
            document: The document containing the reference

        Returns:
            Resolved reference data (must be a dict for ODPS compatibility)

        Raises:
            ValueError: If ref_path format is invalid
            ODPSRefResolutionError: If reference cannot be resolved
        """
        # Track ODPS reference resolution metrics
        start_time = time.time()
        tenant_id = self.tenant_id or 'unknown'
        ref_type = RefMode.INTERNAL.value

        try:
            # Validate ref_path format
            if not ref_path.startswith('#'):
                raise ValueError(f"Internal $ref must start with '#': {ref_path}")

            # Extract JSON Pointer path (remove leading '#')
            json_pointer = ref_path[1:]

            # Handle root reference
            if not json_pointer or json_pointer == '/':
                # Root reference - return entire document (must be dict)
                if not isinstance(document, dict):
                    raise ODPSRefResolutionError(
                        message=f"Cannot resolve internal $ref '{ref_path}': root document must be an object",
                        error_code=ODPSRefResolutionError.ERROR_CODE_INVALID_REF,
                        tenant_id=self.tenant_id,
                        user_id=self.user_id,
                    )

                duration = time.time() - start_time
                self._security_logger.log_ref_resolution_audit(
                    operation_id=str(uuid.uuid4()),
                    ref_type=ref_type,
                    ref_path=ref_path,
                    success=True,
                    duration_ms=duration * 1000,
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                )

                # Track metrics
                odps_ref_resolution_total.labels(ref_type=ref_type, status='success', tenant_id=tenant_id).inc()
                odps_ref_resolution_duration_seconds.labels(ref_type=ref_type, tenant_id=tenant_id).observe(duration)

                return document

            # Validate JSON Pointer starts with '/'
            if not json_pointer.startswith('/'):
                raise ValueError(f"Internal $ref JSON Pointer must start with '/': {ref_path}")

            # Use proper JSON Pointer resolution (handles escaping and array indices)
            resolved_value = resolve_json_pointer(document, json_pointer)

            # Check if resolution failed
            if resolved_value is None:
                # Provide detailed error message by attempting to resolve path segments
                # to identify where resolution failed
                current = document
                pointer_path = json_pointer.lstrip('/')

                if pointer_path:
                    # Unescape segments to show user-friendly path
                    segments = []
                    for segment in pointer_path.split('/'):
                        unescaped = segment.replace('~1', '/').replace('~0', '~')
                        segments.append(unescaped)

                    # Try to identify where resolution fails
                    for i, segment in enumerate(segments):
                        if isinstance(current, dict):
                            if segment not in current:
                                # Missing key
                                partial_path = '/'.join(segments[:i]) if i > 0 else ''
                                raise ODPSRefResolutionError(
                                    message=f"Cannot resolve internal $ref '{ref_path}': key '{segment}' not found at path '/{partial_path}'",
                                    error_code=ODPSRefResolutionError.ERROR_CODE_INVALID_REF,
                                    tenant_id=self.tenant_id,
                                    user_id=self.user_id,
                                )
                            current = current[segment]
                        elif isinstance(current, list):
                            try:
                                index = int(segment)
                                if 0 <= index < len(current):
                                    current = current[index]
                                else:
                                    raise ODPSRefResolutionError(
                                        message=f"Cannot resolve internal $ref '{ref_path}': array index {index} out of bounds at path '/{'/'.join(segments[:i])}'",
                                        error_code=ODPSRefResolutionError.ERROR_CODE_INVALID_REF,
                                        tenant_id=self.tenant_id,
                                        user_id=self.user_id,
                                    )
                            except ValueError:
                                raise ODPSRefResolutionError(
                                    message=f"Cannot resolve internal $ref '{ref_path}': invalid array index '{segment}' at path '/{'/'.join(segments[:i])}'",
                                    error_code=ODPSRefResolutionError.ERROR_CODE_INVALID_REF,
                                    tenant_id=self.tenant_id,
                                    user_id=self.user_id,
                                )
                        else:
                            # Type mismatch
                            partial_path = '/'.join(segments[:i]) if i > 0 else ''
                            raise ODPSRefResolutionError(
                                message=f"Cannot resolve internal $ref '{ref_path}': path '/{partial_path}' is not an object or array (got {type(current).__name__})",
                                error_code=ODPSRefResolutionError.ERROR_CODE_INVALID_REF,
                                tenant_id=self.tenant_id,
                                user_id=self.user_id,
                            )

                # If we get here, resolution failed for unknown reason
                raise ODPSRefResolutionError(
                    message=f"Cannot resolve internal $ref '{ref_path}': reference not found",
                    error_code=ODPSRefResolutionError.ERROR_CODE_INVALID_REF,
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                )

            # Ensure resolved value is a dict (ODPS requirement)
            if not isinstance(resolved_value, dict):
                raise ODPSRefResolutionError(
                    message=f"Cannot resolve internal $ref '{ref_path}': resolved value must be an object, got {type(resolved_value).__name__}",
                    error_code=ODPSRefResolutionError.ERROR_CODE_INVALID_REF,
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                )

            # Log successful resolution
            duration = time.time() - start_time
            self._security_logger.log_ref_resolution_audit(
                operation_id=str(uuid.uuid4()),
                ref_type=ref_type,
                ref_path=ref_path,
                success=True,
                duration_ms=duration * 1000,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
            )

            # Track successful reference resolution metrics
            odps_ref_resolution_total.labels(ref_type=ref_type, status='success', tenant_id=tenant_id).inc()
            odps_ref_resolution_duration_seconds.labels(ref_type=ref_type, tenant_id=tenant_id).observe(duration)

            return resolved_value
        except (ODPSRefResolutionError, ValueError) as e:
            # Track reference resolution failure metrics
            duration = time.time() - start_time
            error_type = type(e).__name__
            odps_ref_resolution_total.labels(ref_type=ref_type, status='failure', tenant_id=tenant_id).inc()
            odps_ref_resolution_failures_total.labels(ref_type=ref_type, error_type=error_type, tenant_id=tenant_id).inc()
            odps_ref_resolution_duration_seconds.labels(ref_type=ref_type, tenant_id=tenant_id).observe(duration)
            raise

    def resolve_local(self, ref_path: str) -> Dict[str, Any]:
        """
        Resolve local $ref (file system path).

        Supports both JSON and YAML files with comprehensive security validation:
        - Path traversal prevention
        - File type validation (.json, .yaml, .yml only)
        - Symlink attack prevention
        - Size limit enforcement
        - Directory traversal prevention

        Args:
            ref_path: Local $ref path (e.g., "./schemas/email.json", "./sla-profiles/gold.yaml")

        Returns:
            Resolved reference data (dict)

        Raises:
            ODPSRefResolutionError: If reference cannot be resolved or security validation fails
        """
        # Track ODPS reference resolution metrics
        start_time = time.time()
        tenant_id = self.tenant_id or 'unknown'
        ref_type = RefMode.LOCAL.value

        try:
            # Check if absolute path was provided (security: reject absolute paths)
            # This check must happen first to fail fast on security violations
            if Path(ref_path).is_absolute():
                self._security_logger.log_security_violation(
                    event_type=SecurityEventType.PATH_TRAVERSAL,
                    severity=SecuritySeverity.HIGH,
                    violation_type="Absolute path rejection",
                    description=f"Local $ref path '{ref_path}' is an absolute path, which is not allowed",
                    attempted_path=str(ref_path),
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                )
                raise ODPSRefResolutionError(
                    message=f"Local $ref path '{ref_path}' is an absolute path, which is not allowed",
                    error_code=ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION,
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                )

            # Parse file path - handle relative paths starting with ./ or ../
            # Normalize by removing leading ./ if present
            normalized_ref_path = ref_path
            if normalized_ref_path.startswith('./'):
                normalized_ref_path = normalized_ref_path[2:]

            # Parse file path - handle relative paths starting with ./ or ../
            # Normalize by removing leading ./ if present
            normalized_ref_path = ref_path
            if normalized_ref_path.startswith('./'):
                normalized_ref_path = normalized_ref_path[2:]

            # Build the path before resolving (to check for symlinks)
            path_before_resolve = self.base_path / normalized_ref_path

            # Symlink attack prevention: Check if path is a symlink BEFORE resolving
            # This allows us to give a more specific error message for symlink attacks
            # We need to check before resolve() because resolve() follows symlinks
            is_symlink = path_before_resolve.exists() and path_before_resolve.is_symlink()
            if is_symlink:
                # Resolve the symlink to its actual target
                symlink_target = path_before_resolve.resolve(strict=True)

                # Validate the symlink target is also within allowed directories
                if not self.config.is_path_allowed(symlink_target, self.base_path):
                    self._security_logger.log_security_violation(
                        event_type=SecurityEventType.PATH_TRAVERSAL,
                        severity=SecuritySeverity.HIGH,
                        violation_type="Symlink attack prevention",
                        description=f"Local $ref symlink '{path_before_resolve}' points to '{symlink_target}' which is not in allowed directories",
                        attempted_path=str(path_before_resolve),
                        allowed_dirs=self.config.allowed_base_dirs,
                        tenant_id=self.tenant_id,
                        user_id=self.user_id,
                        metadata={"symlink_target": str(symlink_target)},
                    )
                    raise ODPSRefResolutionError(
                        message=f"Local $ref symlink '{ref_path}' points to '{symlink_target}' which is outside allowed directories",
                        error_code=ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION,
                        tenant_id=self.tenant_id,
                        user_id=self.user_id,
                    )
                # Use the resolved symlink target for further operations
                resolved_path = symlink_target
            else:
                # Resolve relative to base path using Path.resolve()
                # This normalizes the path and eliminates .. and . components
                resolved_path = path_before_resolve.resolve()

            # Check if path is a directory (must be a file) - do this after symlink resolution
            if resolved_path.exists() and resolved_path.is_dir():
                raise ODPSRefResolutionError(
                    message=f"Local $ref path '{resolved_path}' is a directory, not a file",
                    error_code=ODPSRefResolutionError.ERROR_CODE_INVALID_REF,
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                )

            # Validate path is within allowed base directories (whitelist)
            # This prevents path traversal attacks
            if not self.config.is_path_allowed(resolved_path, self.base_path):
                self._security_logger.log_security_violation(
                    event_type=SecurityEventType.PATH_TRAVERSAL,
                    severity=SecuritySeverity.HIGH,
                    violation_type="Path traversal attempt",
                    description=f"Local $ref path '{ref_path}' resolved to '{resolved_path}' is not in allowed directories",
                    attempted_path=str(resolved_path),
                    allowed_dirs=self.config.allowed_base_dirs,
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                )
                raise ODPSRefResolutionError(
                    message=f"Local $ref path '{ref_path}' is not in allowed directories",
                    error_code=ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION,
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                )

            # Validate file type (only .yaml, .yml, .json allowed)
            file_extension = resolved_path.suffix.lower()
            allowed_extensions = {'.json', '.yaml', '.yml'}
            if file_extension not in allowed_extensions:
                self._security_logger.log_security_violation(
                    event_type=SecurityEventType.INVALID_FILE_TYPE,
                    severity=SecuritySeverity.MEDIUM,
                    violation_type="Invalid file type",
                    description=f"Local $ref file '{resolved_path}' has invalid extension '{file_extension}'. Allowed: {allowed_extensions}",
                    attempted_path=str(resolved_path),
                    metadata={'file_extension': file_extension},
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                )
                raise ODPSRefResolutionError(
                    message=f"Local $ref file '{resolved_path}' has invalid file extension '{file_extension}'. Only .json, .yaml, and .yml files are allowed",
                    error_code=ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION,
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                )

            # Check if file exists
            if not resolved_path.exists():
                raise ODPSRefResolutionError(
                    message=f"Local $ref file not found: {resolved_path}",
                    error_code=ODPSRefResolutionError.ERROR_CODE_INVALID_REF,
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                )

            # Check if path is a file (not a directory) - after symlink resolution
            if not resolved_path.is_file():
                raise ODPSRefResolutionError(
                    message=f"Local $ref path '{resolved_path}' is not a file",
                    error_code=ODPSRefResolutionError.ERROR_CODE_INVALID_REF,
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                )

            # Check file size before reading
            try:
                file_size = resolved_path.stat().st_size
            except OSError as e:
                raise ODPSRefResolutionError(
                    message=f"Failed to get file size for local $ref: {resolved_path}",
                    error_code=ODPSRefResolutionError.ERROR_CODE_RESOLUTION_FAILED,
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                ) from e

            self._check_size_limit(file_size)

            # Read file content
            try:
                with open(resolved_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError as e:
                raise ODPSRefResolutionError(
                    message=f"Local $ref file '{resolved_path}' is not valid UTF-8",
                    error_code=ODPSRefResolutionError.ERROR_CODE_INVALID_REF,
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                ) from e
            except IOError as e:
                raise ODPSRefResolutionError(
                    message=f"Failed to read local $ref file: {resolved_path}",
                    error_code=ODPSRefResolutionError.ERROR_CODE_RESOLUTION_FAILED,
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                ) from e

            # Parse file content based on file extension
            try:
                if file_extension == '.json':
                    data = json.loads(content)
                elif file_extension in {'.yaml', '.yml'}:
                    # Check if YAML support is available
                    if not YAML_AVAILABLE or yaml is None:
                        raise ODPSRefResolutionError(
                            message=f"YAML support is not available. Install PyYAML to resolve .yaml/.yml files",
                            error_code=ODPSRefResolutionError.ERROR_CODE_RESOLUTION_FAILED,
                            tenant_id=self.tenant_id,
                            user_id=self.user_id,
                        )

                    try:
                        data = yaml.safe_load(content)
                    except yaml.YAMLError as e:
                        error_msg = str(e)
                        if hasattr(e, 'problem'):
                            error_msg = e.problem
                        raise ODPSRefResolutionError(
                            message=f"Local $ref file '{resolved_path}' is not valid YAML: {error_msg}",
                            error_code=ODPSRefResolutionError.ERROR_CODE_INVALID_REF,
                            tenant_id=self.tenant_id,
                            user_id=self.user_id,
                        ) from e
                else:
                    # This should not happen due to earlier validation, but include for safety
                    raise ODPSRefResolutionError(
                        message=f"Unsupported file extension '{file_extension}' for local $ref: {resolved_path}",
                        error_code=ODPSRefResolutionError.ERROR_CODE_INVALID_REF,
                        tenant_id=self.tenant_id,
                        user_id=self.user_id,
                    )
            except ODPSRefResolutionError:
                # Re-raise ODPSRefResolutionError as-is
                raise
            except json.JSONDecodeError as e:
                raise ODPSRefResolutionError(
                    message=f"Local $ref file '{resolved_path}' is not valid JSON: {str(e)}",
                    error_code=ODPSRefResolutionError.ERROR_CODE_INVALID_REF,
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                ) from e
            except Exception as e:
                raise ODPSRefResolutionError(
                    message=f"Failed to parse local $ref file '{resolved_path}': {str(e)}",
                    error_code=ODPSRefResolutionError.ERROR_CODE_RESOLUTION_FAILED,
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                ) from e

            # Validate parsed data is a dict (ODPS requirement)
            if not isinstance(data, dict):
                raise ODPSRefResolutionError(
                    message=f"Local $ref file '{resolved_path}' must contain a JSON/YAML object, got {type(data).__name__}",
                    error_code=ODPSRefResolutionError.ERROR_CODE_INVALID_REF,
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                )

            # Log successful resolution
            duration = time.time() - start_time
            self._security_logger.log_ref_resolution_audit(
                operation_id=str(uuid.uuid4()),
                ref_type=ref_type,
                ref_path=ref_path,
                success=True,
                duration_ms=duration * 1000,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                resolved_path=str(resolved_path),
                size_bytes=file_size,
                metadata={'file_extension': file_extension},
            )

            # Track successful reference resolution metrics
            odps_ref_resolution_total.labels(ref_type=ref_type, status='success', tenant_id=tenant_id).inc()
            odps_ref_resolution_duration_seconds.labels(ref_type=ref_type, tenant_id=tenant_id).observe(duration)

            return data
        except ODPSRefResolutionError as e:
            # Track reference resolution failure metrics
            duration = time.time() - start_time
            error_type = type(e).__name__
            odps_ref_resolution_total.labels(ref_type=ref_type, status='failure', tenant_id=tenant_id).inc()
            odps_ref_resolution_failures_total.labels(ref_type=ref_type, error_type=error_type, tenant_id=tenant_id).inc()
            odps_ref_resolution_duration_seconds.labels(ref_type=ref_type, tenant_id=tenant_id).observe(duration)
            raise

    def resolve_external(self, ref_path: str) -> Dict[str, Any]:
        """
        Resolve external $ref (HTTP/HTTPS URL).

        Implements comprehensive security controls:
        - URL validation (scheme, host, length)
        - Rate limiting (per-tenant, per-user, global)
        - URL allowlist/denylist checking
        - Timeout enforcement (5 seconds default)
        - Size limit enforcement (1MB per ref, 10MB total)
        - Redis caching (TTL: 1 hour, key format: odps_ref:{url_hash}:{content_hash})

        Args:
            ref_path: External $ref URL (e.g., "https://example.com/dq-rules.yaml")

        Returns:
            Resolved reference data (dict)

        Raises:
            ODPSRefResolutionError: If reference cannot be resolved or validation fails
        """
        # Track ODPS reference resolution metrics
        start_time = time.time()
        tenant_id = self.tenant_id or 'unknown'
        ref_type = RefMode.EXTERNAL.value

        try:
            # Validate URL format and security constraints
            self._validate_external_url(ref_path)

            # Check rate limit before fetching
            is_allowed, error = check_rate_limit(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
            )
            if not is_allowed and error:
                # Extract rate limit level from error message or metadata
                rate_limit_level = "unknown"
                if hasattr(error, 'context') and error.context:
                    rate_limit_level = error.context.get("level", "unknown")

                # Log rate limit violation explicitly
                self._security_logger.log_rate_limit_violation(
                    level=rate_limit_level,
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                    ref_path=ref_path,
                    retry_after=error.retry_after,
                    metadata={
                        "retry_after_seconds": error.context.get("retry_after_seconds") if hasattr(error, 'context') else None,
                        "error_code": error.error_code,
                    }
                )
                # Log rate limit violation as security event with full context
                self._security_logger.log_security_violation(
                    event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
                    severity=SecuritySeverity.MEDIUM,
                    violation_type="Rate limit exceeded",
                    description=f"ODPS $ref resolution rate limit exceeded for external URL '{ref_path}'. {error.message}",
                    attempted_url=ref_path,
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                    metadata={
                        "retry_after": error.retry_after,
                        "retry_after_seconds": error.context.get("retry_after_seconds") if hasattr(error, 'context') else None,
                        "error_code": error.error_code,
                        "level": rate_limit_level,
                    }
                )
                # Raise error with clear message including retry-after suggestion
                raise ODPSRefResolutionError(
                    message=error.message,
                    error_code=error.error_code,
                    retry_after=error.retry_after,
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                    ref_path=ref_path,
                    ref_type=RefMode.EXTERNAL.value,
                )

            # Check if URL is allowed
            if not self.config.is_url_allowed(ref_path):
                self._security_logger.log_security_violation(
                    event_type=SecurityEventType.URL_NOT_ALLOWED,
                    severity=SecuritySeverity.HIGH,
                    violation_type="External URL not allowed",
                    description=f"External $ref URL '{ref_path}' is not in allowlist or is in denylist",
                    attempted_url=ref_path,
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                )
                raise ODPSRefResolutionError(
                    message=f"External $ref URL '{ref_path}' is not allowed",
                    error_code=ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION,
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                )

            # Check cache first (only for external refs)
            operation_id = str(uuid.uuid4())
            cache_check_start = time.time()

            cached_data = self._get_from_cache(ref_path)
            if cached_data is None:
                # Log cache miss
                self._security_logger.log_cache_operation(
                    operation="miss",
                    ref_path=ref_path,
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                )
            if cached_data is not None:
                logger.debug(
                    "ref_resolver_cache_hit",
                    ref_path=ref_path,
                    message="Using cached external $ref"
                )
                # Log cache hit
                self._security_logger.log_cache_operation(
                    operation="hit",
                    ref_path=ref_path,
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                )
                duration = time.time() - start_time
                duration_ms = duration * 1000
                # Log external ref fetch (from cache)
                self._security_logger.log_external_ref_fetch(
                    ref_path=ref_path,
                    success=True,
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                    duration_ms=duration_ms,
                    size_bytes=len(json.dumps(cached_data)),
                    cache_hit=True,
                )
                self._security_logger.log_ref_resolution_audit(
                    operation_id=operation_id,
                    ref_type=ref_type,
                    ref_path=ref_path,
                    success=True,
                    duration_ms=duration_ms,
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                    resolved_path=ref_path,
                    cache_hit=True,
                    size_bytes=len(json.dumps(cached_data)),
                )
                # Track successful reference resolution metrics
                odps_ref_resolution_total.labels(ref_type=ref_type, status='success', tenant_id=tenant_id).inc()
                odps_ref_resolution_duration_seconds.labels(ref_type=ref_type, tenant_id=tenant_id).observe(duration)
                return cached_data

            # Fetch from URL
            fetch_start_time = time.time()
            with httpx.Client(timeout=self.timeout_per_ref) as client:
                response = client.get(ref_path)
                response.raise_for_status()

                # Check content size
                content_length = len(response.content)
                self._check_size_limit(content_length)

                # Parse JSON
                data = response.json()

                # Validate parsed data is a dict (ODPS requirement)
                if not isinstance(data, dict):
                    raise ODPSRefResolutionError(
                        message=f"External $ref URL '{ref_path}' returned data that is not a JSON object",
                        error_code=ODPSRefResolutionError.ERROR_CODE_INVALID_REF,
                        tenant_id=self.tenant_id,
                        user_id=self.user_id,
                    )

                # Store in cache with content hash
                self._set_cache(ref_path, data, content_bytes=response.content)
                # Track per-URL access for cache warming (on-demand warming)
                self._track_ref_access(ref_path)

                duration = time.time() - start_time
                duration_ms = duration * 1000
                # Log external ref fetch (from network)
                self._security_logger.log_external_ref_fetch(
                    ref_path=ref_path,
                    success=True,
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                    duration_ms=duration_ms,
                    size_bytes=content_length,
                    cache_hit=False,
                )
                self._security_logger.log_ref_resolution_audit(
                    operation_id=operation_id,
                    ref_type=ref_type,
                    ref_path=ref_path,
                    success=True,
                    duration_ms=duration_ms,
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                    resolved_path=ref_path,
                    cache_hit=False,
                    size_bytes=content_length,
                )

                # Track successful reference resolution metrics
                odps_ref_resolution_total.labels(ref_type=ref_type, status='success', tenant_id=tenant_id).inc()
                odps_ref_resolution_duration_seconds.labels(ref_type=ref_type, tenant_id=tenant_id).observe(duration)

                return data

        except httpx.TimeoutException as e:
            duration = time.time() - start_time
            duration_ms = duration * 1000
            self._security_logger.log_security_violation(
                event_type=SecurityEventType.TIMEOUT,
                severity=SecuritySeverity.MEDIUM,
                violation_type="External $ref timeout",
                description=f"External $ref URL '{ref_path}' timed out after {self.timeout_per_ref}s",
                attempted_url=ref_path,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
            )
            self._security_logger.log_ref_resolution_audit(
                operation_id=operation_id,
                ref_type=ref_type,
                ref_path=ref_path,
                success=False,
                duration_ms=duration_ms,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                error_type="TimeoutException",
                error_message=f"External $ref URL '{ref_path}' timed out after {self.timeout_per_ref}s",
            )
            # Track reference resolution failure metrics
            odps_ref_resolution_total.labels(ref_type=ref_type, status='failure', tenant_id=tenant_id).inc()
            odps_ref_resolution_failures_total.labels(ref_type=ref_type, error_type='TimeoutException', tenant_id=tenant_id).inc()
            odps_external_fetch_failures_total.labels(error_type='TimeoutException', tenant_id=tenant_id).inc()
            odps_ref_resolution_duration_seconds.labels(ref_type=ref_type, tenant_id=tenant_id).observe(duration)
            raise ODPSRefResolutionError(
                message=f"External $ref URL '{ref_path}' timed out after {self.timeout_per_ref}s",
                error_code=ODPSRefResolutionError.ERROR_CODE_RESOLUTION_FAILED,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
            ) from e
        except httpx.HTTPStatusError as e:
            duration = time.time() - start_time
            error_type = f'HTTPStatusError_{e.response.status_code}'
            # Track reference resolution failure metrics
            odps_ref_resolution_total.labels(ref_type=ref_type, status='failure', tenant_id=tenant_id).inc()
            odps_ref_resolution_failures_total.labels(ref_type=ref_type, error_type=error_type, tenant_id=tenant_id).inc()
            odps_external_fetch_failures_total.labels(error_type=error_type, tenant_id=tenant_id).inc()
            odps_ref_resolution_duration_seconds.labels(ref_type=ref_type, tenant_id=tenant_id).observe(duration)
            raise ODPSRefResolutionError(
                message=f"External $ref URL '{ref_path}' returned status {e.response.status_code}",
                error_code=ODPSRefResolutionError.ERROR_CODE_RESOLUTION_FAILED,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
            ) from e
        except httpx.RequestError as e:
            duration = time.time() - start_time
            error_type = 'RequestError'
            # Track reference resolution failure metrics
            odps_ref_resolution_total.labels(ref_type=ref_type, status='failure', tenant_id=tenant_id).inc()
            odps_ref_resolution_failures_total.labels(ref_type=ref_type, error_type=error_type, tenant_id=tenant_id).inc()
            odps_external_fetch_failures_total.labels(error_type=error_type, tenant_id=tenant_id).inc()
            odps_ref_resolution_duration_seconds.labels(ref_type=ref_type, tenant_id=tenant_id).observe(duration)
            raise ODPSRefResolutionError(
                message=f"Failed to fetch external $ref URL '{ref_path}': {str(e)}",
                error_code=ODPSRefResolutionError.ERROR_CODE_RESOLUTION_FAILED,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
            ) from e
        except json.JSONDecodeError as e:
            duration = time.time() - start_time
            error_type = 'JSONDecodeError'
            # Track reference resolution failure metrics
            odps_ref_resolution_total.labels(ref_type=ref_type, status='failure', tenant_id=tenant_id).inc()
            odps_ref_resolution_failures_total.labels(ref_type=ref_type, error_type=error_type, tenant_id=tenant_id).inc()
            odps_external_fetch_failures_total.labels(error_type=error_type, tenant_id=tenant_id).inc()
            odps_ref_resolution_duration_seconds.labels(ref_type=ref_type, tenant_id=tenant_id).observe(duration)
            raise ODPSRefResolutionError(
                message=f"External $ref URL '{ref_path}' returned invalid JSON",
                error_code=ODPSRefResolutionError.ERROR_CODE_INVALID_REF,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
            ) from e
        except ODPSRefResolutionError as e:
            # Re-raise ODPSRefResolutionError but track metrics
            duration = time.time() - start_time
            error_type = type(e).__name__
            odps_ref_resolution_total.labels(ref_type=ref_type, status='failure', tenant_id=tenant_id).inc()
            odps_ref_resolution_failures_total.labels(ref_type=ref_type, error_type=error_type, tenant_id=tenant_id).inc()
            if ref_type == RefMode.EXTERNAL.value:
                odps_external_fetch_failures_total.labels(error_type=error_type, tenant_id=tenant_id).inc()
            odps_ref_resolution_duration_seconds.labels(ref_type=ref_type, tenant_id=tenant_id).observe(duration)
            raise

    def resolve(self, ref_path: str, document: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Resolve $ref reference (auto-detect mode).

        Args:
            ref_path: $ref path/value
            document: The document containing the reference (required for internal refs)

        Returns:
            Resolved reference data

        Raises:
            ODPSRefResolutionError: If reference cannot be resolved
        """
        # Check total timeout
        self._check_timeout()

        # Detect mode
        mode = self._detect_mode(ref_path)

        # Resolve based on mode
        if mode == RefMode.INTERNAL:
            if document is None:
                raise ValueError("Document is required for internal $ref resolution")
            return self.resolve_internal(ref_path, document)
        elif mode == RefMode.LOCAL:
            return self.resolve_local(ref_path)
        elif mode == RefMode.EXTERNAL:
            return self.resolve_external(ref_path)
        else:
            raise ValueError(f"Unknown $ref mode: {mode}")

    def resolve_all_refs(
        self,
        document: Dict[str, Any],
        preserve_original: bool = True,
        external_ref_handling: ExternalRefHandling = ExternalRefHandling.RESOLVE
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Resolve all $ref references in a document recursively.

        This method orchestrates the resolution of all $ref references in a document,
        handling internal, local, and external references. It:
        - Recursively finds and resolves all $ref references
        - Detects and prevents circular references
        - Preserves the original document (deep copy)
        - Handles external refs according to external_ref_handling mode
        - Returns both original and resolved documents

        Args:
            document: The document containing $ref references to resolve
            preserve_original: If True, returns a deep copy of the original document.
                               If False, modifies the document in place (not recommended).
            external_ref_handling: How to handle external $refs:
                - RESOLVE: Resolve external refs (default behavior)
                - REMOVE: Remove external refs (delete the $ref key)
                - REPLACE: Replace external refs with resolved content
                - DISABLE: Disable external refs (raise error if found)

        Returns:
            Tuple of (original_document, resolved_document):
            - original_document: Deep copy of the original document (preserved)
            - resolved_document: Document with all $ref references resolved according to handling mode

        Raises:
            ODPSRefResolutionError: If circular reference detected, resolution fails, or external ref disabled
            ValueError: If document is not a dict

        Example:
            >>> resolver = RefResolver()
            >>> original, resolved = resolver.resolve_all_refs({
            ...     "product": {
            ...         "dataQuality": {"$ref": "#/definitions/quality"}
            ...     },
            ...     "definitions": {
            ...         "quality": {"score": 95}
            ...     }
            ... })
            >>> # resolved["product"]["dataQuality"] == {"score": 95}
        """
        if not isinstance(document, dict):
            raise ValueError(f"Document must be a dict, got {type(document).__name__}")

        # Reset resolution tracking for new document
        self._resolving_refs.clear()
        self._total_size = 0
        self._start_time = time.time()

        # Preserve original document (deep copy)
        if preserve_original:
            original_document = copy.deepcopy(document)
        else:
            original_document = document

        # Create resolved document (deep copy to avoid modifying original)
        resolved_document = copy.deepcopy(document)

        # Resolve all refs recursively
        try:
            self._resolve_refs_recursive(
                resolved_document,
                resolved_document,
                path="",
                external_ref_handling=external_ref_handling,
                parent=None,
                parent_key=None
            )

            # Clean up None values from lists (items marked for removal)
            self._cleanup_none_values(resolved_document)
        except ODPSRefResolutionError:
            # Re-raise ODPSRefResolutionError as-is
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise ODPSRefResolutionError(
                message=f"Unexpected error during $ref resolution: {str(e)}",
                error_code=ODPSRefResolutionError.ERROR_CODE_RESOLUTION_FAILED,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
            ) from e

        return original_document, resolved_document

    def _resolve_refs_recursive(
        self,
        obj: Any,
        root_document: Dict[str, Any],
        path: str = "",
        external_ref_handling: ExternalRefHandling = ExternalRefHandling.RESOLVE,
        parent: Optional[Any] = None,
        parent_key: Optional[Any] = None
    ) -> None:
        """
        Recursively resolve all $ref references in an object.

        This method traverses the object structure and resolves any $ref references
        it encounters. It handles:
        - Direct $ref keys ({"$ref": "#/path"})
        - Nested objects and arrays
        - Circular reference detection
        - External ref handling modes (resolve, remove, replace, disable)

        Args:
            obj: The object to process (dict, list, or primitive)
            root_document: The root document (for internal ref resolution)
            path: Current path in the document (for error messages)
            external_ref_handling: How to handle external $refs

        Raises:
            ODPSRefResolutionError: If circular reference detected, resolution fails, or external ref disabled
        """
        # Check timeout
        self._check_timeout()

        if isinstance(obj, dict):
            # Check if this dict has a $ref key
            if "$ref" in obj:
                ref_path = obj["$ref"]
                if not isinstance(ref_path, str):
                    raise ODPSRefResolutionError(
                        message=f"$ref value must be a string at path '{path}', got {type(ref_path).__name__}",
                        error_code=ODPSRefResolutionError.ERROR_CODE_INVALID_REF,
                        tenant_id=self.tenant_id,
                        user_id=self.user_id,
                    )

                # Detect ref mode
                ref_mode = self._detect_mode(ref_path)

                # Handle external refs according to external_ref_handling mode
                if ref_mode == RefMode.EXTERNAL:
                    if external_ref_handling == ExternalRefHandling.DISABLE:
                        raise ODPSRefResolutionError(
                            message=f"External $ref is disabled at path '{path}': {ref_path}",
                            error_code=ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION,
                            tenant_id=self.tenant_id,
                            user_id=self.user_id,
                            ref_path=ref_path,
                            ref_type=RefMode.EXTERNAL.value,
                        )
                    elif external_ref_handling == ExternalRefHandling.REMOVE:
                        # Remove the $ref by deleting the key from parent
                        if parent is not None and parent_key is not None:
                            if isinstance(parent, dict):
                                del parent[parent_key]
                            elif isinstance(parent, list):
                                # For lists, we can't easily delete by index during iteration
                                # So we'll mark it for removal by clearing and filtering later
                                # Actually, let's use a different approach - set to None and filter
                                parent[parent_key] = None
                        else:
                            # No parent, just clear the dict
                            obj.clear()
                        return
                    elif external_ref_handling == ExternalRefHandling.REPLACE:
                        # Replace with resolved content (fall through to normal resolution)
                        pass
                    # RESOLVE mode: continue with normal resolution

                # Check for circular reference
                if ref_path in self._resolving_refs:
                    # Build circular reference chain for error message
                    ref_chain = list(self._resolving_refs) + [ref_path]
                    raise ODPSRefResolutionError(
                        message=f"Circular reference detected: {' -> '.join(ref_chain)}",
                        error_code=ODPSRefResolutionError.ERROR_CODE_CIRCULAR_REF,
                        tenant_id=self.tenant_id,
                        user_id=self.user_id,
                    )

                # Add to resolving set
                self._resolving_refs.add(ref_path)

                try:
                    # Resolve the reference
                    resolved_value = self.resolve(ref_path, root_document)

                    # Resolve any refs within the resolved value (recursive)
                    self._resolve_refs_recursive(
                        resolved_value,
                        root_document,
                        path=f"{path}/$ref",
                        external_ref_handling=external_ref_handling,
                        parent=None,
                        parent_key=None
                    )

                    # Replace $ref with resolved value
                    # We need to replace the entire dict containing $ref
                    # This is tricky because we're modifying the parent object
                    # So we need to handle this at the caller level
                    obj.clear()
                    obj.update(resolved_value)

                finally:
                    # Remove from resolving set
                    self._resolving_refs.discard(ref_path)

            else:
                # Process all values in the dict
                # Create a list of keys to iterate over (to avoid modification during iteration)
                keys_to_process = list(obj.keys())
                for key in keys_to_process:
                    if key in obj:  # Check if key still exists (might have been deleted)
                        self._resolve_refs_recursive(
                            obj[key],
                            root_document,
                            path=f"{path}/{key}",
                            external_ref_handling=external_ref_handling,
                            parent=obj,
                            parent_key=key
                        )

        elif isinstance(obj, list):
            # Process all items in the list
            # Process in reverse order to avoid index issues when removing items
            for i in range(len(obj) - 1, -1, -1):
                item = obj[i]
                if item is not None:  # Skip items marked for removal
                    self._resolve_refs_recursive(
                        item,
                        root_document,
                        path=f"{path}[{i}]",
                        external_ref_handling=external_ref_handling,
                        parent=obj,
                        parent_key=i
                    )
                else:
                    # Remove None items (marked for removal)
                    obj.pop(i)

        # Primitives (str, int, float, bool, None) don't need processing

    def _cleanup_none_values(self, obj: Any) -> None:
        """
        Recursively remove None values from lists and dicts.

        This is used to clean up items marked for removal during $ref processing.

        Args:
            obj: The object to clean up (dict, list, or primitive)
        """
        if isinstance(obj, dict):
            # Remove None values from dict
            keys_to_remove = [k for k, v in obj.items() if v is None]
            for key in keys_to_remove:
                del obj[key]

            # Recursively clean up remaining values
            for value in obj.values():
                self._cleanup_none_values(value)
        elif isinstance(obj, list):
            # Remove None values from list
            obj[:] = [item for item in obj if item is not None]

            # Recursively clean up remaining items
            for item in obj:
                self._cleanup_none_values(item)

    def remove_external_refs(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove all external $ref references from a document.

        This method removes external $ref references by deleting the dict containing the $ref.
        Internal and local refs are preserved.

        Args:
            document: The document containing $ref references

        Returns:
            Document with external $refs removed

        Example:
            >>> resolver = RefResolver()
            >>> doc = {
            ...     "product": {
            ...         "schema": {"$ref": "https://example.com/schema.json"},
            ...         "quality": {"$ref": "#/definitions/quality"}
            ...     }
            ... }
            >>> result = resolver.remove_external_refs(doc)
            >>> # result["product"]["schema"] is removed
            >>> # result["product"]["quality"] still has $ref (internal)
        """
        if not isinstance(document, dict):
            raise ValueError(f"Document must be a dict, got {type(document).__name__}")

        # Use resolve_all_refs with REMOVE mode for external refs
        _, resolved = self.resolve_all_refs(
            document,
            preserve_original=True,
            external_ref_handling=ExternalRefHandling.REMOVE
        )
        return resolved


def resolve_odps_refs(
    document: Dict[str, Any],
    disable_external_refs: bool = False,
    remove_external_refs: bool = False,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    base_path: Optional[Path] = None
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Helper function to resolve $ref references in ODPS documents.

    This is a convenience function that creates a RefResolver and resolves all refs
    in an ODPS document according to the specified external ref handling mode.

    Args:
        document: The ODPS document containing $ref references
        disable_external_refs: If True, external refs are disabled (raises error)
        remove_external_refs: If True, external refs are removed; if False, they are resolved
        tenant_id: Optional tenant ID for rate limiting and audit logging
        user_id: Optional user ID for rate limiting and audit logging
        base_path: Optional base path for local ref resolution

    Returns:
        Tuple of (original_document, resolved_document)

    Raises:
        ODPSRefResolutionError: If resolution fails or external refs are disabled
    """
    # Determine external ref handling mode
    if disable_external_refs:
        external_ref_handling = ExternalRefHandling.DISABLE
    elif remove_external_refs:
        external_ref_handling = ExternalRefHandling.REMOVE
    else:
        external_ref_handling = ExternalRefHandling.RESOLVE

    # Create resolver
    resolver = RefResolver(
        tenant_id=tenant_id,
        user_id=user_id,
        base_path=base_path
    )

    # Resolve all refs
    return resolver.resolve_all_refs(
        document,
        preserve_original=True,
        external_ref_handling=external_ref_handling
    )

