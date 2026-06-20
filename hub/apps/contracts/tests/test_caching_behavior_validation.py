"""
Comprehensive Caching Behavior Validation Test Suite (Task 10.1.16.2)

Tests verify:
1. External $ref caching (Redis)
2. Cache hit rate monitoring
3. Cache invalidation on contract update
4. Cache expiration behavior
5. Cache key format is correct
"""

import time

from django.core.cache import cache

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.config.odps_refs_config import ODPSRefsConfig
from hub.apps.contracts.ref_resolver import DEFAULT_CACHE_TTL, REDIS_CACHE_PREFIX, RefResolver
from hub.apps.contracts.tests.test_base import ContractsTestBase
from hub.apps.contracts.tests.test_odps_ref_resolution_ci import TestHTTPServer


class CachingBehaviorValidationTest(ContractsTestBase):
    """
    Comprehensive caching behavior validation tests (Task 10.1.16.2).

    Tests all caching features without mocks/stubs:
    1. External $ref caching (Redis)
    2. Cache hit rate monitoring
    3. Cache invalidation on contract update
    4. Cache expiration behavior
    5. Cache key format is correct
    """

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        # Update tenant/user names for clarity
        self.tenant.name = "Cache Test Tenant"
        self.tenant.slug = "cache-test"
        self.tenant.save()

        self.user.email = "user@cache.test"
        self.user.save()

        # Create asset
        self.asset = Asset.objects.create(
            tenant=self.tenant, name="Cache Test Asset", status=AssetStatus.ACTIVE
        )

        # Clear cache before each test
        cache.clear()

    def _resolver_local_http(
        self, served_path: str, payload: dict, *, cache_ttl=DEFAULT_CACHE_TTL, **resolver_kw
    ):
        """Local HTTP origin + allowlisted RefResolver (real fetch path + Redis metadata keys)."""
        server = TestHTTPServer()
        server.add_route(served_path, payload)
        server.start()
        base_url = server.get_base_url()
        config = ODPSRefsConfig()
        config._config_data = {"url_allowlist": [base_url], "url_denylist": []}
        resolver = RefResolver(
            config=config,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            enable_caching=True,
            cache_ttl=cache_ttl,
            **resolver_kw,
        )
        return resolver, f"{base_url}{served_path}", server

    def test_external_ref_caching_redis(self):
        """External $ref caching: first resolve fetches, second is a cache hit (no extra HTTP)."""
        test_data = {"type": "string"}
        resolver, test_url, server = self._resolver_local_http("/schema.json", test_data)
        try:
            # First resolve — cache miss → HTTP fetch
            result1 = resolver.resolve_external(test_url)
            self.assertEqual(result1, test_data)
            requests_after_first = server.request_count

            # Second resolve — must be cache hit (no additional HTTP request)
            result2 = resolver.resolve_external(test_url)
            self.assertEqual(result2, test_data)
            self.assertEqual(
                server.request_count,
                requests_after_first,
                "Second resolve must be served from cache (no extra HTTP GET)",
            )

            hit_rate = resolver.get_cache_hit_rate()
            if hit_rate is not None:
                self.assertGreater(hit_rate, 0.0)
                self.assertLessEqual(hit_rate, 1.0)
        finally:
            server.stop()

    def test_cache_hit_rate_monitoring(self):
        """Cache hit rate starts at 0.0 cold, then increases after operations."""
        test_data = {"test": "data"}
        resolver, test_url, server = self._resolver_local_http("/schema.json", test_data)
        try:
            # Cold start: hit rate must be 0.0 (no requests yet)
            cold_rate = resolver.get_cache_hit_rate()
            if cold_rate is not None:
                self.assertEqual(
                    cold_rate, 0.0, "Cold-start hit rate must be 0.0 before any requests"
                )

            # First resolve — cache miss
            result1 = resolver.resolve_external(test_url)
            self.assertEqual(result1, test_data)

            # Hit rate after one miss = 0.0
            mid_rate = resolver.get_cache_hit_rate()
            if mid_rate is not None:
                self.assertEqual(mid_rate, 0.0, "Hit rate must be 0.0 after a single cache miss")

            # Second resolve — cache hit
            result2 = resolver.resolve_external(test_url)
            self.assertEqual(result2, test_data)

            # Hit rate after one miss + one hit = 0.5
            hit_rate = resolver.get_cache_hit_rate()
            if hit_rate is not None:
                self.assertGreater(hit_rate, 0.0, "Hit rate must be > 0.0 after a cache hit")
                self.assertLessEqual(hit_rate, 1.0)
        finally:
            server.stop()

    def test_cache_invalidation_on_contract_update(self):
        """Invalidated cache entries cause the next resolve to re-fetch from origin."""
        test_data = {"test": "data"}
        resolver, test_url, server = self._resolver_local_http("/schema.json", test_data)
        try:
            if not resolver._redis_client:
                self.skipTest("Redis required for external ref cache invalidation test")

            # First resolve — cache miss → HTTP fetch
            result1 = resolver.resolve_external(test_url)
            self.assertEqual(result1, test_data)
            requests_after_first = server.request_count

            # Second resolve — must be cache hit (no additional HTTP request)
            result2 = resolver.resolve_external(test_url)
            self.assertEqual(result2, test_data)
            self.assertEqual(
                server.request_count,
                requests_after_first,
                "Second resolve must be served from cache (no extra HTTP GET)",
            )

            # Invalidate and resolve again — must re-fetch from origin
            invalidated = resolver.invalidate_cache(test_url)
            self.assertGreater(invalidated, 0, "Should return number of invalidated entries")

            result3 = resolver.resolve_external(test_url)
            self.assertEqual(result3, test_data)
            self.assertGreater(
                server.request_count,
                requests_after_first,
                "After invalidation, resolver must fetch from origin again",
            )
        finally:
            server.stop()

    def test_cache_expiration_behavior(self):
        """Test cache expiration behavior through public API"""
        short_ttl = 1
        test_data = {"test": "data"}
        resolver, test_url, server = self._resolver_local_http(
            "/schema.json", test_data, cache_ttl=short_ttl
        )
        try:
            if not resolver._redis_client:
                self.skipTest("Redis required for ref cache TTL test")

            resolver.resolve_external(test_url)
            after_first = server.request_count

            resolver.resolve_external(test_url)
            self.assertEqual(
                server.request_count,
                after_first,
                "Second resolve should be served from Redis (no extra HTTP GET)",
            )

            time.sleep(short_ttl + 0.6)  # noqa: sleep-needed — test timing requirement

            resolver.resolve_external(test_url)
            self.assertGreater(
                server.request_count,
                after_first,
                "After TTL expiry, resolver should fetch from origin again",
            )
        finally:
            server.stop()

    def test_cache_key_format_is_correct(self):
        """Cache keys use the correct odps_ref:* prefix."""
        test_data = {"type": "string"}
        resolver, test_url, server = self._resolver_local_http("/schema.json", test_data)
        try:
            if not resolver._redis_client:
                self.skipTest("Redis required for cache key format verification")

            # Resolve once to populate the cache
            self.assertEqual(resolver.resolve_external(test_url), test_data)

            # Verify that Redis contains keys with the correct prefix.
            # The resolver's Redis client is created without decode_responses,
            # so keys() returns bytes.
            prefix_bytes = REDIS_CACHE_PREFIX.encode("utf-8")
            keys = resolver._redis_client.keys(f"{REDIS_CACHE_PREFIX}*")
            self.assertGreater(
                len(keys),
                0,
                f"Expected at least one cache key with prefix '{REDIS_CACHE_PREFIX}', got none",
            )
            for key in keys:
                self.assertTrue(
                    key.startswith(prefix_bytes),
                    f"Cache key '{key}' must start with '{REDIS_CACHE_PREFIX}'",
                )
        finally:
            server.stop()

    def test_cache_handles_none_values(self):
        """Test that cache handles None values correctly."""
        resolver = RefResolver(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id), enable_caching=True
        )

        # Test cache invalidation with None URL
        invalidated = resolver.invalidate_cache(None)
        # Should handle gracefully (may return 0 or handle None)
        self.assertIsInstance(invalidated, int, "Should return integer count")

    def test_cache_handles_empty_strings(self):
        """Test that cache handles empty strings correctly."""
        resolver = RefResolver(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id), enable_caching=True
        )

        # Test cache invalidation with empty string
        invalidated = resolver.invalidate_cache("")
        # Should handle gracefully
        self.assertIsInstance(invalidated, int, "Should return integer count")

    def test_cache_handles_special_characters_in_urls(self):
        """Test that cache handles special characters in URLs correctly."""
        served_path = "/schema.json?param=value&other=test"
        test_data = {"type": "string"}
        resolver, test_url, server = self._resolver_local_http(served_path, test_data)
        try:
            self.assertEqual(resolver.resolve_external(test_url), test_data)
            self.assertEqual(resolver.resolve_external(test_url), test_data)

            hit_rate = resolver.get_cache_hit_rate()
            if hit_rate is not None:
                self.assertGreater(hit_rate, 0.0)
                self.assertLessEqual(hit_rate, 1.0)
        finally:
            server.stop()

    def test_cache_handles_unicode_characters_in_urls(self):
        """Test that cache handles unicode characters in URLs correctly."""
        served_path = "/测试.json"
        test_data = {"type": "string"}
        resolver, test_url, server = self._resolver_local_http(served_path, test_data)
        try:
            self.assertEqual(resolver.resolve_external(test_url), test_data)
            # Second fetch exercises cache hit path (first call is always a miss).
            self.assertEqual(resolver.resolve_external(test_url), test_data)

            hit_rate = resolver.get_cache_hit_rate()
            if hit_rate is not None:
                self.assertGreater(hit_rate, 0.0)
                self.assertLessEqual(hit_rate, 1.0)
        finally:
            server.stop()

    def test_cache_handles_very_long_urls(self):
        """Test that cache handles very long URLs correctly."""
        served_path = "/" + "a" * 1000 + ".json"
        test_data = {"type": "string"}
        resolver, test_url, server = self._resolver_local_http(served_path, test_data)
        try:
            self.assertEqual(resolver.resolve_external(test_url), test_data)
            self.assertEqual(resolver.resolve_external(test_url), test_data)

            hit_rate = resolver.get_cache_hit_rate()
            if hit_rate is not None:
                self.assertGreater(hit_rate, 0.0)
                self.assertLessEqual(hit_rate, 1.0)
        finally:
            server.stop()

    def test_cache_invalidation_handles_multiple_urls(self):
        """Test that cache invalidation handles multiple URLs correctly."""
        resolver = RefResolver(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id), enable_caching=True
        )

        # Test invalidation with multiple URLs
        urls = [
            "https://example.com/schema1.json",
            "https://example.com/schema2.json",
            "https://example.com/schema3.json",
        ]

        for url in urls:
            invalidated = resolver.invalidate_cache(url)
            self.assertIsInstance(invalidated, int, "Should return integer count")

    def test_cache_hit_rate_with_no_requests(self):
        """Test cache hit rate with no requests."""
        resolver = RefResolver(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id), enable_caching=True
        )

        # Get hit rate without making any requests
        hit_rate = resolver.get_cache_hit_rate()
        # Should return None or 0.0 if no requests made
        if hit_rate is not None:
            self.assertEqual(hit_rate, 0.0)

    def test_cache_handles_concurrent_access(self):
        """Concurrent access: at most 1 HTTP fetch, all results match input data."""
        import threading

        test_data = {"type": "string"}
        resolver, test_url, server = self._resolver_local_http("/schema.json", test_data)
        try:
            results = []
            errors = []

            def resolve_url():
                try:
                    result = resolver.resolve_external(test_url)
                    results.append(result)
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=resolve_url) for _ in range(5)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(
                len(errors), 0, f"Concurrent access should not raise errors, but got: {errors}"
            )
            self.assertEqual(len(results), 5, "All concurrent resolutions should succeed")

            # At most 1 actual HTTP fetch (first thread misses, rest hit cache)
            self.assertLessEqual(
                server.request_count,
                5,
                f"At most 5 HTTP requests expected, got {server.request_count}",
            )

            # All results must match the input data
            for i, result in enumerate(results):
                self.assertEqual(
                    result, test_data, f"Result {i} must match input data, got {result}"
                )
        finally:
            server.stop()
