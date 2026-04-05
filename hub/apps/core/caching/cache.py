"""
Caching Utilities

Provides comprehensive caching infrastructure for application-wide caching.

Features:
- Cache key generation utilities
- TTL configuration per cache key pattern
- Cache invalidation utilities (with Redis pattern support)
- Cache warming utilities
"""
import hashlib
import json
import re
from typing import Any, Callable, Dict, List, Optional, Pattern
from functools import lru_cache

import structlog
import redis
from django.conf import settings
from django.core.cache import cache as django_cache

logger = structlog.get_logger(__name__)


def get_redis_client() -> Optional[redis.Redis]:
    """
    Get Redis client for cache operations.

    Uses the shared cache connection pool to avoid per-call connection leaks.

    Returns:
        Redis client instance or None if unavailable
    """
    try:
        from hub.apps.core.redis_pools import get_redis_cache_client
        client = get_redis_cache_client()
        client.ping()
        return client
    except Exception as e:
        logger.warning(
            "cache_redis_unavailable",
            error=str(e),
            message="Cache will use Django cache backend only (no pattern support)"
        )
        return None


class CacheKeyGenerator:
    """
    Cache key generation utility.

    Provides consistent cache key generation with normalization.
    """

    # Characters that should be normalized in cache keys
    KEY_NORMALIZATION_PATTERN = re.compile(r'[^\w\-:.]')

    def generate(self, *parts: Any, separator: str = ":") -> str:
        """
        Generate cache key from parts.

        Args:
            *parts: Key parts (will be converted to strings)
            separator: Separator between parts (default: ":")

        Returns:
            Generated cache key string
        """
        normalized_parts = []
        for part in parts:
            if part is None:
                normalized_parts.append("None")
            elif isinstance(part, (dict, list)):
                # Serialize complex types deterministically
                normalized_parts.append(self._serialize_complex(part))
            else:
                normalized_parts.append(str(part))

        key = separator.join(normalized_parts)
        return self._normalize_key(key)

    def _serialize_complex(self, obj: Any) -> str:
        """
        Serialize complex object deterministically.

        Args:
            obj: Object to serialize (dict, list, etc.)

        Returns:
            Serialized string representation
        """
        if isinstance(obj, dict):
            # Sort keys for deterministic output
            sorted_dict = json.dumps(obj, sort_keys=True)
            return hashlib.md5(sorted_dict.encode()).hexdigest()
        elif isinstance(obj, list):
            # Sort list for deterministic output (if all elements are comparable)
            try:
                sorted_list = sorted(obj)
                list_str = json.dumps(sorted_list)
                return hashlib.md5(list_str.encode()).hexdigest()
            except TypeError:
                # If elements aren't comparable, use original order
                list_str = json.dumps(obj)
                return hashlib.md5(list_str.encode()).hexdigest()
        else:
            return str(obj)

    def _normalize_key(self, key: str) -> str:
        """
        Normalize cache key by removing/replacing invalid characters.

        Args:
            key: Raw cache key

        Returns:
            Normalized cache key
        """
        # Replace invalid characters with underscores
        normalized = self.KEY_NORMALIZATION_PATTERN.sub('_', key)
        # Remove consecutive underscores
        normalized = re.sub(r'_+', '_', normalized)
        # Remove leading/trailing underscores
        normalized = normalized.strip('_')
        return normalized


class CacheTTLConfig:
    """
    Cache TTL configuration manager.

    Provides pattern-based TTL configuration for cache keys.
    """

    # Default TTL in seconds
    DEFAULT_TTL = 300  # 5 minutes

    # Common TTL patterns (in seconds)
    DEFAULT_PATTERNS = {
        'user:*': 300,           # 5 minutes
        'asset:*': 300,          # 5 minutes
        'contract:*': 300,       # 5 minutes
        'query:*': 60,           # 1 minute
        'search:*': 60,          # 1 minute
        'metrics:*': 300,        # 5 minutes
        'lineage:*': 600,        # 10 minutes
        'validation:*': 3600,    # 1 hour
    }

    def __init__(self):
        """Initialize TTL configuration."""
        self._patterns: Dict[str, int] = {}
        self._specific_keys: Dict[str, int] = {}

        # Load default patterns
        for pattern, ttl in self.DEFAULT_PATTERNS.items():
            self.set_ttl(pattern, ttl)

        # Load from settings
        cache_ttl_config = getattr(settings, 'CACHE_TTL_CONFIG', {})
        for pattern, ttl in cache_ttl_config.items():
            self.set_ttl(pattern, ttl)

    def set_ttl(self, pattern: str, ttl: int) -> None:
        """
        Set TTL for a cache key pattern.

        Args:
            pattern: Cache key pattern (supports * wildcard)
            ttl: Time-to-live in seconds
        """
        if '*' in pattern:
            self._patterns[pattern] = ttl
        else:
            self._specific_keys[pattern] = ttl

    def get_ttl(self, key: str) -> int:
        """
        Get TTL for a cache key.

        Checks specific keys first, then patterns.

        Args:
            key: Cache key

        Returns:
            TTL in seconds
        """
        # Check specific keys first
        if key in self._specific_keys:
            return self._specific_keys[key]

        # Check patterns
        for pattern, ttl in self._patterns.items():
            if self._match_pattern(pattern, key):
                return ttl

        # Return default TTL
        return getattr(settings, 'CACHE_DEFAULT_TTL', self.DEFAULT_TTL)

    def _match_pattern(self, pattern: str, key: str) -> bool:
        """
        Check if key matches pattern.

        Args:
            pattern: Pattern with * wildcard
            key: Cache key to match

        Returns:
            True if key matches pattern
        """
        # Convert pattern to regex
        regex_pattern = pattern.replace('*', '.*')
        return bool(re.match(regex_pattern, key))


class CacheInvalidator:
    """
    Cache invalidation utility.

    Provides cache invalidation with Redis pattern support.
    """

    def __init__(self):
        """Initialize cache invalidator."""
        self._redis_client = get_redis_client()
        self._key_generator = CacheKeyGenerator()

    def invalidate_key(self, key: str) -> bool:
        """
        Invalidate a single cache key.

        Args:
            key: Cache key to invalidate

        Returns:
            True if key was invalidated, False otherwise
        """
        try:
            # Use Django cache delete
            django_cache.delete(key)
            return True
        except Exception as e:
            logger.warning(
                "cache_invalidation_error",
                key=key,
                error=str(e),
                message="Failed to invalidate cache key"
            )
            return False

    def invalidate_keys(self, keys: List[str]) -> int:
        """
        Invalidate multiple cache keys.

        Args:
            keys: List of cache keys to invalidate

        Returns:
            Number of keys invalidated
        """
        count = 0
        for key in keys:
            if self.invalidate_key(key):
                count += 1
        return count

    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate cache keys matching a pattern.

        Uses Redis KEYS command if Redis is available, otherwise
        falls back to Django cache (which doesn't support patterns).

        Args:
            pattern: Cache key pattern (supports * wildcard)

        Returns:
            Number of keys invalidated
        """
        if self._redis_client:
            try:
                # Django cache may add version prefix (e.g., ":1:key")
                # Try multiple patterns to find keys
                patterns_to_try = [pattern]

                # Check if Django cache uses versioning
                cache_backend = getattr(settings, 'CACHES', {}).get('default', {}).get('BACKEND', '')
                if 'redis' in cache_backend.lower():
                    # Django Redis cache may add version prefix
                    # Try with version prefix patterns
                    for version in range(1, 10):  # Check versions 1-9
                        patterns_to_try.append(f":{version}:{pattern}")

                all_keys = []
                for pat in patterns_to_try:
                    keys = self._redis_client.keys(pat)
                    if keys:
                        all_keys.extend(keys)

                # Remove duplicates
                all_keys = list(set(all_keys))

                if all_keys:
                    # Extract Django cache keys (remove version prefix if present)
                    django_keys = []
                    for key in all_keys:
                        # Remove version prefix if present (format: ":1:key")
                        if key.startswith(":") and ":" in key[1:]:
                            parts = key.split(":", 2)
                            if len(parts) == 3:
                                django_keys.append(parts[2])
                            else:
                                django_keys.append(key)
                        else:
                            django_keys.append(key)

                    # Delete from Redis
                    self._redis_client.delete(*all_keys)
                    # Also delete from Django cache (using original keys)
                    django_cache.delete_many(django_keys)
                    return len(all_keys)
                return 0
            except Exception as e:
                logger.warning(
                    "cache_pattern_invalidation_error",
                    pattern=pattern,
                    error=str(e),
                    message="Failed to invalidate cache pattern, falling back to Django cache"
                )
                # Fallback: try Django cache (limited pattern support)
                return self._invalidate_pattern_django(pattern)
        else:
            # Fallback to Django cache (no pattern support)
            return self._invalidate_pattern_django(pattern)

    def _invalidate_pattern_django(self, pattern: str) -> int:
        """
        Invalidate pattern using Django cache (limited support).

        For LocMemCache, we can't easily pattern match, so this is a best-effort.
        In production with Redis cache backend, pattern matching should work.

        Args:
            pattern: Cache key pattern

        Returns:
            Number of keys invalidated
        """
        # Django cache doesn't support pattern deletion natively for LocMemCache
        # For Redis cache backend, pattern matching should work via Redis client
        # This fallback is mainly for LocMemCache or when Redis is unavailable
        logger.debug(
            "cache_pattern_invalidation_django_fallback",
            pattern=pattern,
            message="Using Django cache fallback for pattern invalidation"
        )
        # Return 0 to indicate limited support
        # In practice, with Redis cache backend, the main invalidate_pattern should work
        return 0


class CacheWarmer:
    """
    Cache warming utility.

    Provides utilities for pre-populating cache with frequently accessed data.
    """

    def __init__(self, batch_size: int = 100):
        """
        Initialize cache warmer.

        Args:
            batch_size: Number of entries to process in each batch
        """
        self._batch_size = batch_size
        self._ttl_config = CacheTTLConfig()

    def warm_cache(
        self,
        keys: List[str],
        fetch_func: Callable[[str], Any],
        ttl: Optional[int] = None,
        batch_size: Optional[int] = None
    ) -> int:
        """
        Warm cache with data from fetch function.

        Args:
            keys: List of cache keys to warm
            fetch_func: Function to fetch data for a key (takes key as argument)
            ttl: Time-to-live in seconds (default: from TTL config)
            batch_size: Batch size for processing (default: instance batch_size)

        Returns:
            Number of keys successfully warmed
        """
        batch_size = batch_size or self._batch_size
        warmed_count = 0

        # Process in batches
        for i in range(0, len(keys), batch_size):
            batch = keys[i:i + batch_size]
            for key in batch:
                try:
                    # Fetch data
                    data = fetch_func(key)

                    # Determine TTL
                    cache_ttl = ttl or self._ttl_config.get_ttl(key)

                    # Cache data
                    django_cache.set(key, data, timeout=cache_ttl)
                    warmed_count += 1
                except Exception as e:
                    logger.warning(
                        "cache_warming_error",
                        key=key,
                        error=str(e),
                        message="Failed to warm cache for key"
                    )
                    # Continue with next key
                    continue

        logger.info(
            "cache_warming_complete",
            total_keys=len(keys),
            warmed_count=warmed_count,
            message="Cache warming completed"
        )

        return warmed_count

    def warm_cache_single(
        self,
        key: str,
        fetch_func: Callable[[str], Any],
        ttl: Optional[int] = None
    ) -> bool:
        """
        Warm cache for a single key.

        Args:
            key: Cache key to warm
            fetch_func: Function to fetch data (takes key as argument)
            ttl: Time-to-live in seconds (default: from TTL config)

        Returns:
            True if cache was warmed successfully, False otherwise
        """
        try:
            data = fetch_func(key)
            cache_ttl = ttl or self._ttl_config.get_ttl(key)
            django_cache.set(key, data, timeout=cache_ttl)
            return True
        except Exception as e:
            logger.warning(
                "cache_warming_error",
                key=key,
                error=str(e),
                message="Failed to warm cache for key"
            )
            return False


# Global instances
_key_generator = CacheKeyGenerator()
_ttl_config = CacheTTLConfig()
_invalidator = CacheInvalidator()
_warmer = CacheWarmer()


# Convenience functions
def generate_cache_key(*parts: Any, separator: str = ":") -> str:
    """
    Generate cache key from parts.

    Args:
        *parts: Key parts (will be converted to strings)
        separator: Separator between parts (default: ":")

    Returns:
        Generated cache key string

    Example:
        >>> generate_cache_key("user", "123", "profile")
        'user:123:profile'
    """
    return _key_generator.generate(*parts, separator=separator)


def get_cache_ttl(key: str) -> int:
    """
    Get TTL for a cache key.

    Args:
        key: Cache key

    Returns:
        TTL in seconds

    Example:
        >>> get_cache_ttl("user:123")
        300
    """
    return _ttl_config.get_ttl(key)


def invalidate_cache(key: str) -> bool:
    """
    Invalidate a single cache key.

    Args:
        key: Cache key to invalidate

    Returns:
        True if key was invalidated, False otherwise

    Example:
        >>> invalidate_cache("user:123")
        True
    """
    return _invalidator.invalidate_key(key)


def invalidate_cache_pattern(pattern: str) -> int:
    """
    Invalidate cache keys matching a pattern.

    Args:
        pattern: Cache key pattern (supports * wildcard)

    Returns:
        Number of keys invalidated

    Example:
        >>> invalidate_cache_pattern("user:*")
        10
    """
    return _invalidator.invalidate_pattern(pattern)


def warm_cache(
    key: str,
    fetch_func: Callable[..., Any],
    *args: Any,
    ttl: Optional[int] = None
) -> bool:
    """
    Warm cache for a single key.

    Args:
        key: Cache key to warm
        fetch_func: Function to fetch data (takes key and optionally *args)
        *args: Additional arguments to pass to fetch_func
        ttl: Time-to-live in seconds (default: from TTL config)

    Returns:
        True if cache was warmed successfully, False otherwise

    Example:
        >>> def fetch_user_data(key):
        ...     return {"id": key, "name": "John"}
        >>> warm_cache("user:123", fetch_user_data)
        True
    """
    def wrapped_fetch(k: str) -> Any:
        if args:
            return fetch_func(k, *args)
        else:
            return fetch_func(k)

    return _warmer.warm_cache_single(key, wrapped_fetch, ttl=ttl)

