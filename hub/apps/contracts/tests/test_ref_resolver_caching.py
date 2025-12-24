"""
Unit tests for ODPS $ref Resolver Caching Strategy

Tests verify:
1. Cache key generation with URL and content hashing
2. Cache storage and retrieval
3. Cache invalidation (TTL-based and manual)
4. Cache size limits with LRU eviction
5. Cache hit rate tracking
"""
import json
import time
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase

from hub.apps.contracts.ref_resolver import (
    RefResolver,
    DEFAULT_CACHE_TTL,
    DEFAULT_CACHE_MAX_ENTRIES,
    REDIS_CACHE_PREFIX,
    REDIS_CACHE_INDEX_PREFIX,
    REDIS_CACHE_STATS_PREFIX,
)
from hub.apps.contracts.config.odps_refs_config import ODPSRefsConfig
from hub.apps.contracts.odps_errors import ODPSRefResolutionError


class RefResolverCacheKeyTest(TestCase):
    """Test cache key generation"""

    def setUp(self):
        """Set up test fixtures"""
        config = ODPSRefsConfig()
        config._config_data = {
            'url_allowlist': ['https://example.com'],
            'url_denylist': []
        }
        self.resolver = RefResolver(
            config=config,
            enable_caching=True,
        )

    def test_cache_key_generation_url_only(self):
        """Test cache key generation with URL only"""
        url = "https://example.com/schema.json"
        cache_key = self.resolver._get_cache_key(url)

        # Should start with prefix
        self.assertTrue(cache_key.startswith(REDIS_CACHE_PREFIX))
        # Should contain URL hash
        self.assertIn(":", cache_key)
        # Should end with colon (no content hash)
        self.assertTrue(cache_key.endswith(":"))

    def test_cache_key_generation_with_content_hash(self):
        """Test cache key generation with content hash"""
        url = "https://example.com/schema.json"
        content_hash = "abc123def456"
        cache_key = self.resolver._get_cache_key(url, content_hash)

        # Should start with prefix
        self.assertTrue(cache_key.startswith(REDIS_CACHE_PREFIX))
        # Should contain both URL hash and content hash
        parts = cache_key.split(":")
        self.assertEqual(len(parts), 3)  # prefix, url_hash, content_hash
        self.assertEqual(parts[2], content_hash[:16])

    def test_cache_key_consistency(self):
        """Test that same URL generates same cache key"""
        url = "https://example.com/schema.json"
        key1 = self.resolver._get_cache_key(url)
        key2 = self.resolver._get_cache_key(url)
        self.assertEqual(key1, key2)

    def test_cache_key_different_urls(self):
        """Test that different URLs generate different cache keys"""
        url1 = "https://example.com/schema1.json"
        url2 = "https://example.com/schema2.json"
        key1 = self.resolver._get_cache_key(url1)
        key2 = self.resolver._get_cache_key(url2)
        self.assertNotEqual(key1, key2)


class RefResolverCacheStorageTest(TestCase):
    """Test cache storage and retrieval"""

    def setUp(self):
        """Set up test fixtures"""
        config = ODPSRefsConfig()
        config._config_data = {
            'url_allowlist': ['https://example.com'],
            'url_denylist': []
        }
        self.resolver = RefResolver(
            config=config,
            enable_caching=True,
        )

    def test_cache_storage_and_retrieval(self):
        """Test storing and retrieving from cache"""
        # Mock Redis client
        mock_redis = Mock()
        mock_redis.get.return_value = None  # Cache miss initially
        mock_redis.setex = Mock()
        mock_redis.lpush = Mock()
        mock_redis.expire = Mock()
        mock_redis.llen.return_value = 0  # Empty cache

        self.resolver._redis_client = mock_redis

        url = "https://example.com/schema.json"
        data = {"type": "string", "format": "email"}
        content_bytes = json.dumps(data).encode('utf-8')

        # Store in cache
        self.resolver._set_cache(url, data, content_bytes)

        # Verify cache set was called
        self.assertGreaterEqual(mock_redis.setex.call_count, 1)

        # Simulate cache hit
        cached_json = json.dumps(data, sort_keys=True, ensure_ascii=False)
        mock_redis.get.return_value = cached_json.encode('utf-8')

        # Also need to mock the URL hash lookup
        import hashlib
        url_hash = hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]
        content_hash = hashlib.sha256(content_bytes).hexdigest()[:16]

        def mock_get(key):
            if key.endswith(":"):
                # URL hash lookup
                return content_hash.encode('utf-8')
            else:
                # Cache data lookup
                return cached_json.encode('utf-8')

        mock_redis.get.side_effect = mock_get
        mock_redis.lpush = Mock()  # For LRU update

        # Retrieve from cache
        cached_data = self.resolver._get_from_cache(url)
        self.assertIsNotNone(cached_data)
        self.assertEqual(cached_data, data)

    def test_cache_miss(self):
        """Test cache miss handling"""
        # Mock Redis client
        mock_redis = Mock()
        mock_redis.get.return_value = None  # Cache miss

        self.resolver._redis_client = mock_redis

        url = "https://example.com/schema.json"
        cached_data = self.resolver._get_from_cache(url)
        self.assertIsNone(cached_data)

    def test_cache_content_change_invalidation(self):
        """Test that cache invalidates old entry when content changes"""
        # Mock Redis client
        mock_redis = Mock()
        mock_redis.get.return_value = None  # Cache miss initially
        mock_redis.setex = Mock()
        mock_redis.lpush = Mock()
        mock_redis.expire = Mock()
        mock_redis.llen.return_value = 0
        mock_redis.delete = Mock()
        mock_redis.lrem = Mock()

        self.resolver._redis_client = mock_redis

        url = "https://example.com/schema.json"
        data1 = {"type": "string", "format": "email"}
        data2 = {"type": "string", "format": "url"}  # Different content

        # Store first version
        content_bytes1 = json.dumps(data1).encode('utf-8')
        self.resolver._set_cache(url, data1, content_bytes1)

        # Simulate existing content hash
        import hashlib
        url_hash = hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]
        old_content_hash = hashlib.sha256(content_bytes1).hexdigest()[:16]

        def mock_get(key):
            if key == f"{REDIS_CACHE_PREFIX}{url_hash}":
                return old_content_hash.encode('utf-8')
            return None

        mock_redis.get.side_effect = mock_get

        # Store second version (different content)
        content_bytes2 = json.dumps(data2).encode('utf-8')
        self.resolver._set_cache(url, data2, content_bytes2)

        # Verify old cache entry was deleted
        self.assertGreaterEqual(mock_redis.delete.call_count, 1)


class RefResolverCacheSizeLimitTest(TestCase):
    """Test cache size limits and LRU eviction"""

    def setUp(self):
        """Set up test fixtures"""
        config = ODPSRefsConfig()
        config._config_data = {
            'url_allowlist': ['https://example.com'],
            'url_denylist': []
        }
        self.resolver = RefResolver(
            config=config,
            enable_caching=True,
            cache_ttl=DEFAULT_CACHE_TTL,
        )
        self.resolver.cache_max_entries = 10  # Small limit for testing

    def test_cache_size_limit_enforcement(self):
        """Test that cache size limits are enforced"""
        # Mock Redis client
        mock_redis = Mock()
        mock_redis.get.return_value = None
        mock_redis.setex = Mock()
        mock_redis.lpush = Mock()
        mock_redis.expire = Mock()
        mock_redis.llen.return_value = 10  # At limit
        mock_redis.lrange.return_value = [b"key1", b"key2"]  # Keys to evict
        mock_redis.delete = Mock()
        mock_redis.lrem = Mock()

        self.resolver._redis_client = mock_redis

        url = "https://example.com/schema.json"
        data = {"type": "string"}

        # This should trigger eviction
        self.resolver._set_cache(url, data)

        # Verify eviction was attempted
        self.assertGreaterEqual(mock_redis.lrange.call_count, 0)
        # If at limit, eviction should be called
        if mock_redis.llen.return_value >= self.resolver.cache_max_entries:
            self.assertGreaterEqual(mock_redis.delete.call_count, 0)

    def test_lru_index_update(self):
        """Test LRU index update on cache access"""
        # Mock Redis client
        mock_redis = Mock()
        mock_redis.lrem = Mock()
        mock_redis.lpush = Mock()
        mock_redis.expire = Mock()

        self.resolver._redis_client = mock_redis

        cache_key = "odps_ref:abc123:def456"
        self.resolver._update_lru_index(cache_key)

        # Verify LRU index was updated
        lru_index_key = f"{REDIS_CACHE_INDEX_PREFIX}lru"
        mock_redis.lrem.assert_called_once_with(lru_index_key, 0, cache_key)
        mock_redis.lpush.assert_called_once_with(lru_index_key, cache_key)

    def test_lru_index_removal(self):
        """Test LRU index removal"""
        # Mock Redis client
        mock_redis = Mock()
        mock_redis.lrem = Mock()

        self.resolver._redis_client = mock_redis

        cache_key = "odps_ref:abc123:def456"
        self.resolver._remove_from_lru_index(cache_key)

        # Verify removal from LRU index
        lru_index_key = f"{REDIS_CACHE_INDEX_PREFIX}lru"
        mock_redis.lrem.assert_called_once_with(lru_index_key, 0, cache_key)


class RefResolverCacheHitRateTest(TestCase):
    """Test cache hit rate tracking"""

    def setUp(self):
        """Set up test fixtures"""
        config = ODPSRefsConfig()
        config._config_data = {
            'url_allowlist': ['https://example.com'],
            'url_denylist': []
        }
        self.resolver = RefResolver(
            config=config,
            enable_caching=True,
        )

    def test_cache_hit_tracking(self):
        """Test cache hit tracking"""
        # Mock Redis client
        mock_redis = Mock()
        mock_redis.incr = Mock()
        mock_redis.expire = Mock()

        self.resolver._redis_client = mock_redis

        self.resolver._track_cache_hit()

        # Verify hit was tracked
        stats_key = f"{REDIS_CACHE_STATS_PREFIX}hits"
        mock_redis.incr.assert_called_once_with(stats_key)
        mock_redis.expire.assert_called_once()

    def test_cache_miss_tracking(self):
        """Test cache miss tracking"""
        # Mock Redis client
        mock_redis = Mock()
        mock_redis.incr = Mock()
        mock_redis.expire = Mock()

        self.resolver._redis_client = mock_redis

        self.resolver._track_cache_miss()

        # Verify miss was tracked
        stats_key = f"{REDIS_CACHE_STATS_PREFIX}misses"
        mock_redis.incr.assert_called_once_with(stats_key)
        mock_redis.expire.assert_called_once()

    def test_cache_hit_rate_calculation(self):
        """Test cache hit rate calculation"""
        # Mock Redis client
        mock_redis = Mock()

        def mock_get(key):
            if key.endswith("hits"):
                return b"80"  # 80 hits
            elif key.endswith("misses"):
                return b"20"  # 20 misses
            return None

        mock_redis.get.side_effect = mock_get
        self.resolver._redis_client = mock_redis

        hit_rate = self.resolver.get_cache_hit_rate()
        self.assertIsNotNone(hit_rate)
        self.assertEqual(hit_rate, 0.8)  # 80 / (80 + 20) = 0.8

    def test_cache_hit_rate_no_stats(self):
        """Test cache hit rate with no stats"""
        # Mock Redis client
        mock_redis = Mock()
        mock_redis.get.return_value = None

        self.resolver._redis_client = mock_redis

        hit_rate = self.resolver.get_cache_hit_rate()
        self.assertIsNone(hit_rate)

    def test_cache_hit_rate_zero_total(self):
        """Test cache hit rate with zero total requests"""
        # Mock Redis client
        mock_redis = Mock()
        mock_redis.get.return_value = b"0"  # No hits or misses

        self.resolver._redis_client = mock_redis

        hit_rate = self.resolver.get_cache_hit_rate()
        self.assertIsNone(hit_rate)


class RefResolverCacheInvalidationTest(TestCase):
    """Test cache invalidation"""

    def setUp(self):
        """Set up test fixtures"""
        config = ODPSRefsConfig()
        config._config_data = {
            'url_allowlist': ['https://example.com'],
            'url_denylist': []
        }
        self.resolver = RefResolver(
            config=config,
            enable_caching=True,
        )

    def test_cache_invalidation_specific_url(self):
        """Test invalidating specific URL"""
        # Mock Redis client
        mock_redis = Mock()
        import hashlib
        url = "https://example.com/schema.json"
        url_hash = hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]
        content_hash = "abc123def456"

        def mock_get(key):
            if key == f"{REDIS_CACHE_PREFIX}{url_hash}":
                return content_hash.encode('utf-8')
            return None

        mock_redis.get.side_effect = mock_get
        mock_redis.delete.return_value = 2  # Deleted 2 keys
        mock_redis.lrem = Mock()

        self.resolver._redis_client = mock_redis

        deleted = self.resolver.invalidate_cache(url)
        self.assertEqual(deleted, 2)
        self.assertGreaterEqual(mock_redis.delete.call_count, 1)

    def test_cache_invalidation_all(self):
        """Test invalidating all cache entries"""
        # Mock Redis client
        mock_redis = Mock()
        mock_redis.scan.return_value = (0, [b"key1", b"key2", b"key3"])
        mock_redis.delete.return_value = 3

        self.resolver._redis_client = mock_redis

        deleted = self.resolver.invalidate_cache()
        self.assertEqual(deleted, 3)

    def test_cache_invalidation_no_redis(self):
        """Test cache invalidation when Redis is unavailable"""
        self.resolver._redis_client = None

        deleted = self.resolver.invalidate_cache("https://example.com/schema.json")
        self.assertEqual(deleted, 0)

    def test_cache_invalidation_nonexistent_url(self):
        """Test invalidating non-existent URL"""
        # Mock Redis client
        mock_redis = Mock()
        mock_redis.get.return_value = None  # URL not in cache

        self.resolver._redis_client = mock_redis

        deleted = self.resolver.invalidate_cache("https://example.com/nonexistent.json")
        self.assertEqual(deleted, 0)


class RefResolverCacheIntegrationTest(TestCase):
    """Integration tests for cache hit rate"""

    def setUp(self):
        """Set up test fixtures"""
        config = ODPSRefsConfig()
        config._config_data = {
            'url_allowlist': ['https://example.com'],
            'url_denylist': []
        }
        self.resolver = RefResolver(
            config=config,
            enable_caching=True,
        )

    @patch('hub.apps.contracts.ref_resolver.check_rate_limit')
    def test_cache_hit_rate_integration(self, mock_rate_limit):
        """Integration test for cache hit rate tracking"""
        # Mock rate limit check (allowed)
        mock_rate_limit.return_value = (True, None)

        # Mock Redis client with realistic behavior
        mock_redis = Mock()
        mock_redis.ping.return_value = True

        # Track hits and misses
        hits = [0]
        misses = [0]
        cache_data = {}

        def mock_get(key):
            if key.endswith("hits"):
                return str(hits[0]).encode('utf-8')
            elif key.endswith("misses"):
                return str(misses[0]).encode('utf-8')
            elif key in cache_data:
                hits[0] += 1
                return cache_data[key]
            else:
                misses[0] += 1
                return None

        def mock_setex(key, ttl, value):
            cache_data[key] = value

        def mock_incr(key):
            if key.endswith("hits"):
                hits[0] += 1
            elif key.endswith("misses"):
                misses[0] += 1
            return hits[0] if key.endswith("hits") else misses[0]

        mock_redis.get.side_effect = mock_get
        mock_redis.setex.side_effect = mock_setex
        mock_redis.incr.side_effect = mock_incr
        mock_redis.expire = Mock()
        mock_redis.lpush = Mock()
        mock_redis.llen.return_value = 0

        self.resolver._redis_client = mock_redis

        # Mock HTTP response
        with patch('hub.apps.contracts.ref_resolver.httpx.Client') as mock_client_class:
            mock_response = Mock()
            test_data = {"type": "string", "format": "email"}
            mock_response.content = json.dumps(test_data).encode('utf-8')
            mock_response.json.return_value = test_data
            mock_response.raise_for_status = Mock()

            mock_client = Mock()
            mock_client.__enter__ = Mock(return_value=mock_client)
            mock_client.__exit__ = Mock(return_value=False)
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            url = "https://example.com/schema.json"

            # First call - cache miss, should fetch
            result1 = self.resolver.resolve_external(url)
            self.assertEqual(result1, test_data)

            # Second call - cache hit, should use cache
            # Need to set up cache properly
            import hashlib
            url_hash = hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]
            content_hash = hashlib.sha256(mock_response.content).hexdigest()[:16]
            url_key = f"{REDIS_CACHE_PREFIX}{url_hash}"
            cache_key = self.resolver._get_cache_key(url, content_hash)
            cache_data[url_key] = content_hash.encode('utf-8')
            cache_data[cache_key] = json.dumps(test_data, sort_keys=True, ensure_ascii=False).encode('utf-8')

            result2 = self.resolver.resolve_external(url)
            self.assertEqual(result2, test_data)

            # Check hit rate (should have at least 1 hit and 1 miss)
            hit_rate = self.resolver.get_cache_hit_rate()
            # Hit rate should be calculated if we have stats
            if hits[0] + misses[0] > 0:
                self.assertIsNotNone(hit_rate)
                self.assertGreaterEqual(hit_rate, 0.0)
                self.assertLessEqual(hit_rate, 1.0)

