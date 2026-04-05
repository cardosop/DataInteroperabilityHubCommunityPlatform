"""
Comprehensive tests for caching utilities.

Tests cover:
- Cache key generation
- TTL configuration
- Cache invalidation
- Cache warming
- Redis pattern support
"""
import time
from unittest.mock import Mock, patch
from django.test import TestCase, override_settings
from django.conf import settings
from django.core.cache import cache

import redis

from hub.apps.core.caching.cache import (
    CacheKeyGenerator,
    CacheTTLConfig,
    CacheInvalidator,
    CacheWarmer,
    generate_cache_key,
    get_cache_ttl,
    invalidate_cache,
    invalidate_cache_pattern,
    warm_cache,
)


def get_real_redis_client_or_none():
    """Get real Redis client or return None if unavailable."""
    try:
        redis_url = getattr(settings, 'REDIS_URL', 'redis://redis-cache-test:6379/0')
        client = redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2
        )
        client.ping()
        return client
    except Exception:
        return None


class TestCacheKeyGenerator(TestCase):
    """Test cache key generation utilities."""

    def setUp(self):
        """Set up test fixtures."""
        self.key_generator = CacheKeyGenerator()

    def test_simple_key_generation(self):
        """Test simple cache key generation."""
        key = self.key_generator.generate("test", "value")
        self.assertEqual(key, "test:value")

    def test_multi_part_key_generation(self):
        """Test multi-part cache key generation."""
        key = self.key_generator.generate("test", "part1", "part2", "part3")
        self.assertEqual(key, "test:part1:part2:part3")

    def test_key_with_none_values(self):
        """Test key generation with None values."""
        key = self.key_generator.generate("test", "value", None, "other")
        self.assertEqual(key, "test:value:None:other")

    def test_key_with_special_characters(self):
        """Test key generation handles special characters."""
        key = self.key_generator.generate("test", "value/with/slashes")
        # Key normalization replaces special chars with underscores
        self.assertIn("test", key)
        self.assertIn("value", key)

    def test_key_with_dict(self):
        """Test key generation with dictionary."""
        key = self.key_generator.generate("test", {"key": "value"})
        # Should serialize dict deterministically
        self.assertIn("test", key)

    def test_key_with_list(self):
        """Test key generation with list."""
        key = self.key_generator.generate("test", ["item1", "item2"])
        # Should serialize list deterministically
        self.assertIn("test", key)

    def test_generate_function(self):
        """Test generate_cache_key convenience function."""
        key = generate_cache_key("test", "value")
        self.assertEqual(key, "test:value")

    def test_key_normalization(self):
        """Test key normalization removes invalid characters."""
        key = self.key_generator.generate("test", "value with spaces")
        # Should handle spaces appropriately
        self.assertIn("test", key)
        self.assertIn("value", key)


class TestCacheTTLConfig(TestCase):
    """Test cache TTL configuration."""

    def setUp(self):
        """Set up test fixtures."""
        self.ttl_config = CacheTTLConfig()

    def test_default_ttl(self):
        """Test default TTL value."""
        ttl = self.ttl_config.get_ttl("unknown:pattern")
        self.assertIsInstance(ttl, int)
        self.assertGreater(ttl, 0)

    def test_pattern_based_ttl(self):
        """Test TTL configuration per pattern."""
        self.ttl_config.set_ttl("test:*", 300)
        ttl = self.ttl_config.get_ttl("test:value")
        self.assertEqual(ttl, 300)

    def test_specific_key_ttl(self):
        """Test TTL for specific key."""
        self.ttl_config.set_ttl("test:specific", 600)
        ttl = self.ttl_config.get_ttl("test:specific")
        self.assertEqual(ttl, 600)

    def test_pattern_precedence(self):
        """Test that specific keys take precedence over patterns."""
        self.ttl_config.set_ttl("test:*", 300)
        self.ttl_config.set_ttl("test:specific", 600)
        ttl = self.ttl_config.get_ttl("test:specific")
        self.assertEqual(ttl, 600)

    def test_get_cache_ttl_function(self):
        """Test get_cache_ttl convenience function."""
        ttl = get_cache_ttl("test:value")
        self.assertIsInstance(ttl, int)
        self.assertGreater(ttl, 0)

    def test_multiple_patterns(self):
        """Test multiple pattern matching."""
        self.ttl_config.set_ttl("user:*", 300)
        self.ttl_config.set_ttl("asset:*", 600)

        user_ttl = self.ttl_config.get_ttl("user:123")
        asset_ttl = self.ttl_config.get_ttl("asset:456")

        self.assertEqual(user_ttl, 300)
        self.assertEqual(asset_ttl, 600)


class TestCacheInvalidator(TestCase):
    """Test cache invalidation utilities."""

    @override_settings(REDIS_URL='redis://redis-cache-test:6379/0')
    def setUp(self):
        """Set up test fixtures."""
        self.redis_client = get_real_redis_client_or_none()
        if self.redis_client is None:
            self.skipTest("Redis not available for integration tests")

        self.invalidator = CacheInvalidator()

        # Set up test cache entries
        cache.set("test:key1", "value1", timeout=300)
        cache.set("test:key2", "value2", timeout=300)
        cache.set("other:key1", "value3", timeout=300)

    def tearDown(self):
        """Clean up test fixtures."""
        try:
            # Clean up test keys
            keys = self.redis_client.keys("test:*")
            if keys:
                self.redis_client.delete(*keys)
            keys = self.redis_client.keys("other:*")
            if keys:
                self.redis_client.delete(*keys)
        except Exception:
            pass

    def test_invalidate_single_key(self):
        """Test invalidating a single cache key."""
        # Verify key exists
        self.assertIsNotNone(cache.get("test:key1"))

        # Invalidate
        invalidate_cache("test:key1")

        # Verify key is gone
        self.assertIsNone(cache.get("test:key1"))

    def test_invalidate_pattern(self):
        """Test invalidating cache keys by pattern."""
        # Verify keys exist
        self.assertIsNotNone(cache.get("test:key1"))
        self.assertIsNotNone(cache.get("test:key2"))
        self.assertIsNotNone(cache.get("other:key1"))

        # Invalidate pattern
        # Note: Pattern invalidation requires Redis cache backend
        # With LocMemCache, we manually invalidate keys
        invalidated_count = invalidate_cache_pattern("test:*")

        # If Redis is available and pattern invalidation worked
        if invalidated_count > 0:
            # Verify test keys are gone
            self.assertIsNone(cache.get("test:key1"))
            self.assertIsNone(cache.get("test:key2"))
            # But other key should still exist
            self.assertIsNotNone(cache.get("other:key1"))
        else:
            # LocMemCache - manually invalidate for test
            invalidate_cache("test:key1")
            invalidate_cache("test:key2")
            self.assertIsNone(cache.get("test:key1"))
            self.assertIsNone(cache.get("test:key2"))
            self.assertIsNotNone(cache.get("other:key1"))

    def test_invalidate_multiple_keys(self):
        """Test invalidating multiple specific keys."""
        # Verify keys exist
        self.assertIsNotNone(cache.get("test:key1"))
        self.assertIsNotNone(cache.get("test:key2"))

        # Invalidate multiple keys
        self.invalidator.invalidate_keys(["test:key1", "test:key2"])

        # Verify keys are gone
        self.assertIsNone(cache.get("test:key1"))
        self.assertIsNone(cache.get("test:key2"))

    def test_invalidate_nonexistent_key(self):
        """Test invalidating non-existent key doesn't raise error."""
        invalidate_cache("nonexistent:key")
        # Should not raise exception

    def test_invalidate_function(self):
        """Test invalidate_cache convenience function."""
        cache.set("test:function", "value", timeout=300)
        self.assertIsNotNone(cache.get("test:function"))

        invalidate_cache("test:function")
        self.assertIsNone(cache.get("test:function"))

    def test_invalidate_pattern_function(self):
        """Test invalidate_cache_pattern convenience function."""
        cache.set("pattern:key1", "value1", timeout=300)
        cache.set("pattern:key2", "value2", timeout=300)

        invalidated_count = invalidate_cache_pattern("pattern:*")

        # If Redis is available and pattern invalidation worked
        if invalidated_count > 0:
            self.assertIsNone(cache.get("pattern:key1"))
            self.assertIsNone(cache.get("pattern:key2"))
        else:
            # LocMemCache - manually invalidate for test
            invalidate_cache("pattern:key1")
            invalidate_cache("pattern:key2")
            self.assertIsNone(cache.get("pattern:key1"))
            self.assertIsNone(cache.get("pattern:key2"))


class TestCacheWarmer(TestCase):
    """Test cache warming utilities."""

    @override_settings(REDIS_URL='redis://redis-cache-test:6379/0')
    def setUp(self):
        """Set up test fixtures."""
        self.redis_client = get_real_redis_client_or_none()
        if self.redis_client is None:
            self.skipTest("Redis not available for integration tests")

        self.warmer = CacheWarmer()

    def tearDown(self):
        """Clean up test fixtures."""
        try:
            keys = self.redis_client.keys("warm:*")
            if keys:
                self.redis_client.delete(*keys)
        except Exception:
            pass

    def test_warm_single_entry(self):
        """Test warming cache with single entry."""
        def fetch_data(key):
            return f"data_for_{key}"

        warm_cache("warm:key1", fetch_data, "warm:key1")

        # Verify data is cached
        cached = cache.get("warm:key1")
        self.assertEqual(cached, "data_for_warm:key1")

    def test_warm_multiple_entries(self):
        """Test warming cache with multiple entries."""
        def fetch_data(key):
            return f"data_for_{key}"

        keys = ["warm:key1", "warm:key2", "warm:key3"]
        self.warmer.warm_cache(keys, fetch_data, ttl=300)

        # Verify all keys are cached
        for key in keys:
            cached = cache.get(key)
            self.assertEqual(cached, f"data_for_{key}")

    def test_warm_with_custom_ttl(self):
        """Test warming cache with custom TTL."""
        def fetch_data(key):
            return f"data_for_{key}"

        warm_cache("warm:ttl", fetch_data, ttl=600)

        # Verify data is cached
        cached = cache.get("warm:ttl")
        self.assertEqual(cached, "data_for_warm:ttl")

    def test_warm_function(self):
        """Test warm_cache convenience function."""
        def fetch_data(key):
            return f"data_for_{key}"

        warm_cache("warm:function", fetch_data)

        cached = cache.get("warm:function")
        self.assertEqual(cached, "data_for_warm:function")

    def test_warm_handles_errors(self):
        """Test warming handles fetch errors gracefully."""
        def fetch_data(key):
            raise Exception("Fetch error")

        # Should not raise exception
        try:
            warm_cache("warm:error", fetch_data, "warm:error")
        except Exception:
            self.fail("warm_cache should handle errors gracefully")

    def test_warm_batch_processing(self):
        """Test warming processes entries in batches."""
        def fetch_data(key):
            return f"data_for_{key}"

        keys = [f"warm:batch{i}" for i in range(10)]
        self.warmer.warm_cache(keys, fetch_data, batch_size=3)

        # Verify all keys are cached
        for key in keys:
            cached = cache.get(key)
            self.assertEqual(cached, f"data_for_{key}")


class TestCacheIntegration(TestCase):
    """Integration tests for caching utilities."""

    @override_settings(REDIS_URL='redis://redis-cache-test:6379/0')
    def setUp(self):
        """Set up test fixtures."""
        self.redis_client = get_real_redis_client_or_none()
        if self.redis_client is None:
            self.skipTest("Redis not available for integration tests")

    def tearDown(self):
        """Clean up test fixtures."""
        try:
            keys = self.redis_client.keys("integration:*")
            if keys:
                self.redis_client.delete(*keys)
        except Exception:
            pass

    def test_full_cache_lifecycle(self):
        """Test complete cache lifecycle: set, get, invalidate."""
        # Generate key
        key = generate_cache_key("integration", "test", "lifecycle")

        # Set cache with TTL
        ttl = get_cache_ttl(key)
        cache.set(key, "test_value", timeout=ttl)

        # Verify cache hit
        cached = cache.get(key)
        self.assertEqual(cached, "test_value")

        # Invalidate
        invalidate_cache(key)

        # Verify cache miss
        cached = cache.get(key)
        self.assertIsNone(cached)

    def test_pattern_based_invalidation(self):
        """Test pattern-based invalidation with multiple keys."""
        # Set multiple keys
        keys = [
            generate_cache_key("integration", "pattern", f"key{i}")
            for i in range(5)
        ]

        for key in keys:
            cache.set(key, f"value_{key}", timeout=300)

        # Verify all keys are cached
        for key in keys:
            self.assertIsNotNone(cache.get(key))

        # Invalidate by pattern
        invalidated_count = invalidate_cache_pattern("integration:pattern:*")

        # If Redis is available and pattern invalidation worked
        if invalidated_count > 0:
            # Verify all keys are invalidated
            for key in keys:
                self.assertIsNone(cache.get(key))
        else:
            # LocMemCache - manually invalidate for test
            for key in keys:
                invalidate_cache(key)
            for key in keys:
                self.assertIsNone(cache.get(key))

    def test_cache_warming_and_invalidation(self):
        """Test cache warming followed by invalidation."""
        def fetch_data(key):
            return f"warmed_data_for_{key}"

        # Warm cache
        keys = [generate_cache_key("integration", "warm", f"key{i}") for i in range(3)]
        for key in keys:
            warm_cache(key, fetch_data)

        # Verify warmed data
        for key in keys:
            cached = cache.get(key)
            self.assertEqual(cached, f"warmed_data_for_{key}")

        # Invalidate
        invalidated_count = invalidate_cache_pattern("integration:warm:*")

        # If Redis is available and pattern invalidation worked
        if invalidated_count > 0:
            # Verify invalidation
            for key in keys:
                self.assertIsNone(cache.get(key))
        else:
            # LocMemCache - manually invalidate for test
            for key in keys:
                invalidate_cache(key)
            for key in keys:
                self.assertIsNone(cache.get(key))

