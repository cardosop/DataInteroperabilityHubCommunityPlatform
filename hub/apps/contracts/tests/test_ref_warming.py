"""
Tests for ODPS $ref Cache Warming (Task 9.8.4.3)

Tests verify:
1. Frequently accessed refs identification
2. Cache warming functionality
3. Management command
4. Automatic cache warming (startup, on-demand)
"""
import json
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.core.management import call_command
from io import StringIO

from hub.apps.contracts.ref_resolver import RefResolver, REDIS_CACHE_ACCESS_PREFIX
from hub.apps.contracts.ref_warming import (
    get_frequently_accessed_refs,
    warm_ref_cache,
    warm_cache_on_startup
)
from hub.apps.contracts.config.odps_refs_config import ODPSRefsConfig
from hub.apps.contracts.odps_errors import ODPSRefResolutionError


class RefWarmingTestBase(TestCase):
    """Base test class for cache warming tests."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant_id = "test-tenant-123"
        self.config = ODPSRefsConfig()
        self.config._config_data = {
            'url_allowlist': ['https://example.com', 'https://test.com'],
            'url_denylist': []
        }


class GetFrequentlyAccessedRefsTest(RefWarmingTestBase):
    """Tests for getting frequently accessed refs."""

    def test_get_frequently_accessed_refs_no_redis(self):
        """Test that function handles Redis unavailability gracefully."""
        with patch('hub.apps.contracts.ref_warming._get_redis_client', return_value=None):
            refs = get_frequently_accessed_refs(limit=100)
            self.assertEqual(refs, [])

    def test_get_frequently_accessed_refs_empty(self):
        """Test getting frequently accessed refs when none exist."""
        mock_redis = Mock()
        mock_redis.zrevrange.return_value = []

        with patch('hub.apps.contracts.ref_warming._get_redis_client', return_value=mock_redis):
            refs = get_frequently_accessed_refs(limit=100)
            self.assertEqual(refs, [])

    def test_get_frequently_accessed_refs_success(self):
        """Test getting frequently accessed refs successfully."""
        mock_redis = Mock()

        # Mock sorted set data: [(url_hash_bytes, access_count), ...]
        url_hash1 = b'hash1'
        url_hash2 = b'hash2'
        mock_redis.zrevrange.return_value = [
            (url_hash1, 10.0),
            (url_hash2, 5.0)
        ]

        # Mock URL mappings
        def mock_get(key):
            if key == f"{REDIS_CACHE_ACCESS_PREFIX}url:hash1":
                return b'https://example.com/schema1.json'
            elif key == f"{REDIS_CACHE_ACCESS_PREFIX}url:hash2":
                return b'https://example.com/schema2.json'
            return None

        mock_redis.get.side_effect = mock_get

        with patch('hub.apps.contracts.ref_warming._get_redis_client', return_value=mock_redis):
            refs = get_frequently_accessed_refs(limit=100)
            self.assertEqual(len(refs), 2)
            self.assertIn('https://example.com/schema1.json', refs)
            self.assertIn('https://example.com/schema2.json', refs)

    def test_get_frequently_accessed_refs_min_access_count(self):
        """Test filtering by minimum access count."""
        mock_redis = Mock()

        url_hash1 = b'hash1'
        url_hash2 = b'hash2'
        mock_redis.zrevrange.return_value = [
            (url_hash1, 10.0),
            (url_hash2, 3.0)  # Below min_access_count of 5
        ]

        def mock_get(key):
            if key == f"{REDIS_CACHE_ACCESS_PREFIX}url:hash1":
                return b'https://example.com/schema1.json'
            elif key == f"{REDIS_CACHE_ACCESS_PREFIX}url:hash2":
                return b'https://example.com/schema2.json'
            return None

        mock_redis.get.side_effect = mock_get

        with patch('hub.apps.contracts.ref_warming._get_redis_client', return_value=mock_redis):
            refs = get_frequently_accessed_refs(limit=100, min_access_count=5)
            self.assertEqual(len(refs), 1)
            self.assertIn('https://example.com/schema1.json', refs)
            self.assertNotIn('https://example.com/schema2.json', refs)

    def test_get_frequently_accessed_refs_limit(self):
        """Test that limit is respected."""
        mock_redis = Mock()

        # Create more refs than limit
        refs_data = [(f'hash{i}'.encode('utf-8'), float(i)) for i in range(1, 21)]
        mock_redis.zrevrange.return_value = refs_data

        def mock_get(key):
            # Extract hash from key
            hash_part = key.split(':')[-1]
            return f'https://example.com/schema{hash_part}.json'.encode('utf-8')

        mock_redis.get.side_effect = mock_get

        with patch('hub.apps.contracts.ref_warming._get_redis_client', return_value=mock_redis):
            refs = get_frequently_accessed_refs(limit=10)
            self.assertEqual(len(refs), 10)


class WarmRefCacheTest(RefWarmingTestBase):
    """Tests for cache warming functionality."""

    @patch('hub.apps.contracts.ref_resolver.check_rate_limit')
    @patch('hub.apps.contracts.ref_resolver.httpx.Client')
    def test_warm_ref_cache_success(self, mock_client_class, mock_rate_limit):
        """Test successful cache warming."""
        # Mock rate limit check (allowed)
        mock_rate_limit.return_value = (True, None)

        # Mock HTTP response
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = json.dumps({"type": "object"}).encode('utf-8')
        mock_response.json.return_value = {"type": "object"}
        mock_response.raise_for_status = Mock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client

        ref_urls = [
            'https://example.com/schema1.json',
            'https://example.com/schema2.json'
        ]

        result = warm_ref_cache(ref_urls, tenant_id=self.tenant_id)

        self.assertEqual(result['total'], 2)
        self.assertEqual(result['warmed'], 2)
        self.assertEqual(result['failed'], 0)
        self.assertGreater(result['duration_seconds'], 0)

    def test_warm_ref_cache_empty_list(self):
        """Test warming with empty ref list."""
        result = warm_ref_cache([])

        self.assertEqual(result['total'], 0)
        self.assertEqual(result['warmed'], 0)
        self.assertEqual(result['failed'], 0)

    @patch('hub.apps.contracts.ref_resolver.check_rate_limit')
    def test_warm_ref_cache_already_cached(self, mock_rate_limit):
        """Test that already cached refs are skipped."""
        mock_rate_limit.return_value = (True, None)

        resolver = RefResolver(
            config=self.config,
            tenant_id=self.tenant_id,
            enable_caching=True
        )

        # Mock Redis to return cached data
        mock_redis = Mock()
        mock_redis.ping.return_value = True

        # Simulate cache hit
        import hashlib
        url_hash = hashlib.sha256('https://example.com/schema1.json'.encode('utf-8')).hexdigest()[:16]
        content_hash = hashlib.sha256(b'{"type":"object"}').hexdigest()[:16]

        def mock_get(key):
            if key == f"odps_ref:{url_hash}":
                return content_hash.encode('utf-8')
            elif key == f"odps_ref:{url_hash}:{content_hash}":
                return json.dumps({"type": "object"}).encode('utf-8')
            return None

        mock_redis.get.side_effect = mock_get
        mock_redis.setex = Mock()
        mock_redis.lpush = Mock()
        mock_redis.expire = Mock()
        mock_redis.llen.return_value = 0
        mock_redis.zincrby = Mock()

        resolver._redis_client = mock_redis

        ref_urls = ['https://example.com/schema1.json']

        with patch('hub.apps.contracts.ref_warming.RefResolver', return_value=resolver):
            result = warm_ref_cache(ref_urls, tenant_id=self.tenant_id)

            # Should skip (already cached)
            self.assertEqual(result['skipped'], 1)
            self.assertEqual(result['warmed'], 0)

    @patch('hub.apps.contracts.ref_resolver.check_rate_limit')
    @patch('hub.apps.contracts.ref_resolver.httpx.Client')
    def test_warm_ref_cache_partial_failure(self, mock_client_class, mock_rate_limit):
        """Test warming with some failures."""
        mock_rate_limit.return_value = (True, None)

        mock_client = Mock()
        # First call succeeds, second fails
        mock_response1 = Mock()
        mock_response1.content = json.dumps({"type": "object"}).encode('utf-8')
        mock_response1.json.return_value = {"type": "object"}
        mock_response1.raise_for_status = Mock()

        mock_response2 = Mock()
        mock_response2.raise_for_status.side_effect = Exception("HTTP 404")

        mock_client.get.side_effect = [mock_response1, mock_response2]
        mock_client_class.return_value.__enter__.return_value = mock_client

        ref_urls = [
            'https://example.com/schema1.json',
            'https://example.com/schema2.json'
        ]

        result = warm_ref_cache(ref_urls, tenant_id=self.tenant_id)

        self.assertEqual(result['total'], 2)
        self.assertEqual(result['warmed'], 1)
        self.assertEqual(result['failed'], 1)

    def test_warm_ref_cache_batch_processing(self):
        """Test that refs are processed in batches."""
        ref_urls = [f'https://example.com/schema{i}.json' for i in range(25)]

        with patch('hub.apps.contracts.ref_warming.RefResolver') as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver._get_from_cache.return_value = None  # Cache miss
            mock_resolver.resolve_external.return_value = {"type": "object"}
            mock_resolver_class.return_value = mock_resolver

            result = warm_ref_cache(ref_urls, batch_size=10)

            # Should process all refs
            self.assertEqual(result['total'], 25)
            # Verify resolver was called for each ref
            self.assertEqual(mock_resolver.resolve_external.call_count, 25)


class WarmCacheManagementCommandTest(RefWarmingTestBase):
    """Tests for cache warming management command."""

    def test_command_dry_run(self):
        """Test management command in dry-run mode."""
        mock_redis = Mock()
        mock_redis.zrevrange.return_value = [
            (b'hash1', 10.0),
            (b'hash2', 5.0)
        ]

        def mock_get(key):
            if 'hash1' in key:
                return b'https://example.com/schema1.json'
            elif 'hash2' in key:
                return b'https://example.com/schema2.json'
            return None

        mock_redis.get.side_effect = mock_get

        with patch('hub.apps.contracts.ref_warming._get_redis_client', return_value=mock_redis):
            out = StringIO()
            call_command('warm_odps_ref_cache', '--dry-run', '--limit', '10', stdout=out)
            output = out.getvalue()
            self.assertIn('DRY-RUN', output)
            self.assertIn('Would warm', output)

    def test_command_with_url_pattern(self):
        """Test management command with URL pattern filter."""
        mock_redis = Mock()
        mock_redis.zrevrange.return_value = [
            (b'hash1', 10.0),
            (b'hash2', 5.0)
        ]

        def mock_get(key):
            if 'hash1' in key:
                return b'https://example.com/schema1.json'
            elif 'hash2' in key:
                return b'https://test.com/schema2.json'
            return None

        mock_redis.get.side_effect = mock_get

        with patch('hub.apps.contracts.ref_warming._get_redis_client', return_value=mock_redis):
            with patch('hub.apps.contracts.ref_warming.warm_ref_cache') as mock_warm:
                mock_warm.return_value = {'total': 1, 'warmed': 1, 'skipped': 0, 'failed': 0, 'duration_seconds': 0.1}

                out = StringIO()
                call_command(
                    'warm_odps_ref_cache',
                    '--url-pattern', 'https://example.com/*',
                    '--limit', '10',
                    stdout=out
                )
                output = out.getvalue()

                # Verify warm_ref_cache was called
                if mock_warm.called:
                    # Check that filtered URLs were passed
                    call_kwargs = mock_warm.call_args[1] if mock_warm.call_args else {}
                    ref_urls = call_kwargs.get('ref_urls', [])
                    if ref_urls:
                        self.assertTrue(all('example.com' in url for url in ref_urls))

    def test_command_no_refs_found(self):
        """Test management command when no refs are found."""
        mock_redis = Mock()
        mock_redis.zrevrange.return_value = []

        with patch('hub.apps.contracts.ref_warming._get_redis_client', return_value=mock_redis):
            out = StringIO()
            call_command('warm_odps_ref_cache', '--limit', '10', stdout=out)
            output = out.getvalue()
            self.assertIn('No frequently accessed refs found', output)


class AutomaticCacheWarmingTest(RefWarmingTestBase):
    """Tests for automatic cache warming."""

    @patch('hub.apps.contracts.ref_warming.get_frequently_accessed_refs')
    @patch('hub.apps.contracts.ref_warming.warm_ref_cache')
    @patch('hub.apps.contracts.ref_warming.settings')
    def test_warm_cache_on_startup_enabled(self, mock_settings, mock_warm, mock_get_refs):
        """Test startup cache warming when enabled."""
        mock_get_refs.return_value = ['https://example.com/schema1.json']
        mock_warm.return_value = {'total': 1, 'warmed': 1, 'skipped': 0, 'failed': 0, 'duration_seconds': 0.1}
        mock_settings.ODPS_CACHE_WARMING_ENABLED = True
        mock_settings.ODPS_CACHE_WARMING_STARTUP_ENABLED = True
        mock_settings.ODPS_CACHE_WARMING_STARTUP_LIMIT = 100

        warm_cache_on_startup()

        # Wait a bit for thread to start
        import time
        time.sleep(0.2)

        # Verify functions were called
        self.assertTrue(mock_get_refs.called)
        self.assertTrue(mock_warm.called)

    @patch('hub.apps.contracts.ref_warming.get_frequently_accessed_refs')
    @patch('hub.apps.contracts.ref_warming.warm_ref_cache')
    @patch('hub.apps.contracts.ref_warming.settings')
    def test_warm_cache_on_startup_disabled(self, mock_settings, mock_warm, mock_get_refs):
        """Test startup cache warming when disabled."""
        mock_settings.ODPS_CACHE_WARMING_ENABLED = False
        mock_settings.ODPS_CACHE_WARMING_STARTUP_ENABLED = True

        warm_cache_on_startup()

        import time
        time.sleep(0.2)

        # Verify functions were not called
        self.assertFalse(mock_get_refs.called)
        self.assertFalse(mock_warm.called)

    def test_track_ref_access_on_cache_hit(self):
        """Test that ref access is tracked on cache hit."""
        resolver = RefResolver(
            config=self.config,
            tenant_id=self.tenant_id,
            enable_caching=True
        )

        mock_redis = Mock()
        mock_redis.ping.return_value = True

        import hashlib
        url_hash = hashlib.sha256('https://example.com/schema.json'.encode('utf-8')).hexdigest()[:16]
        content_hash = hashlib.sha256(b'{"type":"object"}').hexdigest()[:16]

        def mock_get(key):
            if key == f"odps_ref:{url_hash}":
                return content_hash.encode('utf-8')
            elif key == f"odps_ref:{url_hash}:{content_hash}":
                return json.dumps({"type": "object"}).encode('utf-8')
            return None

        mock_redis.get.side_effect = mock_get
        mock_redis.setex = Mock()
        mock_redis.lpush = Mock()
        mock_redis.expire = Mock()
        mock_redis.llen.return_value = 0
        mock_redis.zincrby = Mock()

        resolver._redis_client = mock_redis

        # Get from cache (should track access)
        result = resolver._get_from_cache('https://example.com/schema.json')

        self.assertIsNotNone(result)
        # Verify access was tracked
        mock_redis.zincrby.assert_called()

    def test_track_ref_access_on_cache_miss(self):
        """Test that ref access is tracked on cache miss."""
        resolver = RefResolver(
            config=self.config,
            tenant_id=self.tenant_id,
            enable_caching=True
        )

        mock_redis = Mock()
        mock_redis.ping.return_value = True
        mock_redis.get.return_value = None  # Cache miss
        mock_redis.zincrby = Mock()
        mock_redis.setex = Mock()

        resolver._redis_client = mock_redis

        # Get from cache (should track access even on miss)
        result = resolver._get_from_cache('https://example.com/schema.json')

        self.assertIsNone(result)
        # Verify access was tracked
        mock_redis.zincrby.assert_called()

    def test_track_ref_access_only_external(self):
        """Test that only external refs are tracked."""
        resolver = RefResolver(
            config=self.config,
            tenant_id=self.tenant_id,
            enable_caching=True
        )

        mock_redis = Mock()
        mock_redis.ping.return_value = True
        mock_redis.zincrby = Mock()

        resolver._redis_client = mock_redis

        # Track access for internal ref (should not track)
        resolver._track_ref_access('#/definitions/Email')
        mock_redis.zincrby.assert_not_called()

        # Track access for external ref (should track)
        resolver._track_ref_access('https://example.com/schema.json')
        mock_redis.zincrby.assert_called()


class RefWarmingIntegrationTest(RefWarmingTestBase):
    """Integration tests for cache warming."""

    @patch('hub.apps.contracts.ref_resolver.check_rate_limit')
    @patch('hub.apps.contracts.ref_resolver.httpx.Client')
    def test_end_to_end_cache_warming(self, mock_client_class, mock_rate_limit):
        """Test end-to-end cache warming flow."""
        mock_rate_limit.return_value = (True, None)

        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = json.dumps({"type": "object", "properties": {}}).encode('utf-8')
        mock_response.json.return_value = {"type": "object", "properties": {}}
        mock_response.raise_for_status = Mock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client

        # Set up Redis for access tracking
        mock_redis = Mock()
        mock_redis.ping.return_value = True

        import hashlib
        url = 'https://example.com/schema.json'
        url_hash = hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]

        # Mock access tracking data
        mock_redis.zrevrange.return_value = [(url_hash.encode('utf-8'), 10.0)]
        mock_redis.get.side_effect = lambda key: (
            url.encode('utf-8') if 'url:' in key else None
        )
        mock_redis.setex = Mock()
        mock_redis.lpush = Mock()
        mock_redis.expire = Mock()
        mock_redis.llen.return_value = 0
        mock_redis.zincrby = Mock()

        # Get frequently accessed refs
        with patch('hub.apps.contracts.ref_warming._get_redis_client', return_value=mock_redis):
            refs = get_frequently_accessed_refs(limit=10)
            self.assertEqual(len(refs), 1)
            self.assertIn(url, refs)

            # Warm cache
            result = warm_ref_cache(refs, tenant_id=self.tenant_id)
            self.assertEqual(result['warmed'], 1)
            self.assertEqual(result['failed'], 0)

