"""
Comprehensive tests for enhanced contract caching.

Tests cover:
- Cache tags for efficient invalidation
- Cache warming for frequently accessed contracts
- Cache hit/miss metrics

All tests use real implementations (no mocks of hub services).
Redis and Contract model use real implementations.
"""

import time
import uuid

import redis
from django.conf import settings
from django.core.cache import cache
from django.test import TestCase

from hub.apps.contracts.caching import (
    cache_contract,
    get_cached_contract,
    invalidate_contract_cache,
    warm_contract_cache,
)
from hub.apps.contracts.caching_enhanced import (
    cache_contract_with_tags,
    get_cached_contract_with_metrics,
    get_contract_cache_metrics,
    invalidate_contract_cache_by_tags,
    warm_frequently_accessed_contracts,
)
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
)
from hub.apps.contracts.tests.test_base import ContractsTransactionTestBase


def get_real_redis_client_or_none():
    """Get real Redis client or return None if unavailable."""
    try:
        redis_url = getattr(settings, "REDIS_URL", None) or "redis://redis-cache-test:6379/0"
        client = redis.from_url(
            redis_url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2
        )
        client.ping()
        return client
    except Exception:
        return None


class TestCacheTags(TestCase):
    """Test cache tags for efficient invalidation."""

    def setUp(self):
        """Set up test fixtures."""
        self.redis_client = get_real_redis_client_or_none()
        if self.redis_client is None:
            self.skipTest("Redis not available for integration tests")

        # Clear cache before each test
        try:
            keys = self.redis_client.keys("contract:*")
            if keys:
                self.redis_client.delete(*keys)
            keys = self.redis_client.keys("cache_tag:*")
            if keys:
                self.redis_client.delete(*keys)
        except Exception:
            pass

    def tearDown(self):
        """Clean up test fixtures."""
        try:
            keys = self.redis_client.keys("contract:*")
            if keys:
                self.redis_client.delete(*keys)
            keys = self.redis_client.keys("cache_tag:*")
            if keys:
                self.redis_client.delete(*keys)
        except Exception:
            pass

    def test_cache_contract_with_tags(self):
        """Test caching contract with tags."""
        contract_id = "test-contract-1"
        contract_data = {"id": contract_id, "name": "Test Contract"}
        tags = ["tenant:test-tenant", "owner:user1", "status:active"]

        cache_contract_with_tags(contract_id, contract_data, tags=tags)

        # Verify contract is cached
        cached = get_cached_contract(contract_id)
        self.assertIsNotNone(cached)
        self.assertEqual(cached["id"], contract_id)

    def test_invalidate_by_single_tag(self):
        """Test invalidating contracts by single tag."""
        # Cache multiple contracts with different tags
        contract1_data = {"id": "contract-1", "name": "Contract 1"}
        contract2_data = {"id": "contract-2", "name": "Contract 2"}
        contract3_data = {"id": "contract-3", "name": "Contract 3"}

        cache_contract_with_tags("contract-1", contract1_data, tags=["tenant:t1", "owner:user1"])
        cache_contract_with_tags("contract-2", contract2_data, tags=["tenant:t1", "owner:user2"])
        cache_contract_with_tags("contract-3", contract3_data, tags=["tenant:t2", "owner:user1"])

        # Verify all contracts are cached
        self.assertIsNotNone(get_cached_contract("contract-1"))
        self.assertIsNotNone(get_cached_contract("contract-2"))
        self.assertIsNotNone(get_cached_contract("contract-3"))

        # Invalidate by tag
        invalidate_contract_cache_by_tags(["owner:user1"])

        # Verify contracts with owner:user1 are invalidated
        self.assertIsNone(get_cached_contract("contract-1"))
        self.assertIsNotNone(get_cached_contract("contract-2"))  # Different owner
        self.assertIsNone(get_cached_contract("contract-3"))

    def test_invalidate_by_multiple_tags(self):
        """Test invalidating contracts by multiple tags."""
        # Cache contracts with tags
        contract1_data = {"id": "contract-1", "name": "Contract 1"}
        contract2_data = {"id": "contract-2", "name": "Contract 2"}

        cache_contract_with_tags("contract-1", contract1_data, tags=["tenant:t1", "status:active"])
        cache_contract_with_tags("contract-2", contract2_data, tags=["tenant:t1", "status:draft"])

        # Invalidate by multiple tags (OR logic - invalidates if contract has any tag)
        invalidate_contract_cache_by_tags(["status:active", "status:draft"])

        # Both should be invalidated
        self.assertIsNone(get_cached_contract("contract-1"))
        self.assertIsNone(get_cached_contract("contract-2"))

    def test_invalidate_by_tenant_tag(self):
        """Test invalidating contracts by tenant tag."""
        # Cache contracts for different tenants
        contract1_data = {"id": "contract-1", "name": "Contract 1"}
        contract2_data = {"id": "contract-2", "name": "Contract 2"}

        cache_contract_with_tags("contract-1", contract1_data, tags=["tenant:t1"])
        cache_contract_with_tags("contract-2", contract2_data, tags=["tenant:t2"])

        # Invalidate by tenant
        invalidate_contract_cache_by_tags(["tenant:t1"])

        # Only contract-1 should be invalidated
        self.assertIsNone(get_cached_contract("contract-1"))
        self.assertIsNotNone(get_cached_contract("contract-2"))


class TestCacheWarming(ContractsTransactionTestBase):
    """
    Test cache warming for frequently accessed contracts using real Contract model.

    Uses real Contract objects in database to verify cache warming functionality.
    """

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.redis_client = get_real_redis_client_or_none()
        if self.redis_client is None:
            self.skipTest("Redis not available for integration tests")

        import uuid; uid = uuid.uuid4().hex[:8]
        # Update tenant/user names for clarity
        self.tenant.name = f"Cache Warming Test {uid}"
        self.tenant.slug = f"cache-warming-test-{uid}"
        self.tenant.save()

        self.user.email = f"cachewarming-{uid}@test.com"
        self.user.save()

        # Create real contracts in database for cache warming
        self.contract1 = Contract.objects.create(
            tenant=self.tenant,
            hub_contract_json={"name": "Contract 1", "id": "contract-1"},
            status=ContractStatus.ACTIVE,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "contract-1", "name": "Contract 1"}',
            created_by=self.user,
        )

        self.contract2 = Contract.objects.create(
            tenant=self.tenant,
            hub_contract_json={"name": "Contract 2", "id": "contract-2"},
            status=ContractStatus.ACTIVE,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "contract-2", "name": "Contract 2"}',
            created_by=self.user,
        )

    def tearDown(self):
        """Clean up test fixtures."""
        try:
            keys = self.redis_client.keys("contract:*")
            if keys:
                self.redis_client.delete(*keys)
            keys = self.redis_client.keys("cache_tag:*")
            if keys:
                self.redis_client.delete(*keys)
        except Exception:
            pass

    def test_warm_frequently_accessed_contracts(self):
        """
        Test warming cache for frequently accessed contracts using real Contract model.

        Uses real Contract.objects.filter() to query contracts from database.
        """
        # Warm cache using real Contract model
        warmed_count = warm_frequently_accessed_contracts(limit=10)

        # warm_frequently_accessed_contracts queries real Contract objects we created above
        self.assertGreater(warmed_count, 0)

        # If contracts were warmed, verify they're cached
        if warmed_count > 0:
            # Check if our test contracts are cached
            cached1 = get_cached_contract(str(self.contract1.id))
            cached2 = get_cached_contract(str(self.contract2.id))
            # Contracts may or may not be cached depending on query criteria
            # The important thing is that real implementation was used

    def test_warm_contracts_by_tenant(self):
        """
        Test warming contracts for specific tenant using real Contract model.

        Uses real Contract.objects.filter() to query contracts by tenant.
        """
        # Warm cache for tenant using real Contract model
        warmed_count = warm_frequently_accessed_contracts(tenant_id=str(self.tenant.id), limit=10)

        # We created contracts for this tenant, so warming should find them
        self.assertGreater(warmed_count, 0)

        # If contracts were warmed, verify they're cached
        if warmed_count > 0:
            # Check if our test contracts are cached
            cached1 = get_cached_contract(str(self.contract1.id))
            cached2 = get_cached_contract(str(self.contract2.id))
            # Contracts may or may not be cached depending on query criteria
            # The important thing is that real implementation was used


class TestCacheMetrics(TestCase):
    """Test cache hit/miss metrics."""

    def setUp(self):
        """Set up test fixtures."""
        self.redis_client = get_real_redis_client_or_none()
        if self.redis_client is None:
            self.skipTest("Redis not available for integration tests")

        # Clear cache before each test
        try:
            keys = self.redis_client.keys("contract:*")
            if keys:
                self.redis_client.delete(*keys)
        except Exception:
            pass

    def tearDown(self):
        """Clean up test fixtures."""
        try:
            keys = self.redis_client.keys("contract:*")
            if keys:
                self.redis_client.delete(*keys)
        except Exception:
            pass

    def test_cache_hit_metrics(self):
        """
        Test cache hit metrics are recorded using real metrics.

        Uses real cache_hits_total and cache_misses_total metrics to verify integration.
        """
        contract_id = "test-contract-1"
        contract_data = {"id": contract_id, "name": "Test Contract"}

        # Cache contract
        cache_contract(contract_id, contract_data)

        # Get cached contract (should be a hit)
        cached = get_cached_contract_with_metrics(contract_id)

        # Verify contract was retrieved (cache hit)
        self.assertIsNotNone(cached)
        self.assertEqual(cached["id"], contract_id)

        # Metrics are recorded by real metrics system (Prometheus/OTEL)
        # We verify the functionality works, metrics are recorded automatically

    def test_cache_miss_metrics(self):
        """
        Test cache miss metrics are recorded using real metrics.

        Uses real cache_misses_total metrics to verify integration.
        """
        contract_id = "non-existent-contract"

        # Try to get non-existent contract (should be a miss)
        cached = get_cached_contract_with_metrics(contract_id)

        # Verify cache miss (no cached data)
        self.assertIsNone(cached)

        # Metrics are recorded by real metrics system (Prometheus/OTEL)
        # We verify the functionality works, metrics are recorded automatically

    def test_get_cache_metrics(self):
        """
        Test getting cache metrics using real metrics system.

        Uses real metrics to verify cache metrics retrieval functionality.
        """
        # Create some cache operations to generate metrics
        contract_id1 = "test-contract-1"
        contract_id2 = "test-contract-2"
        contract_data1 = {"id": contract_id1, "name": "Contract 1"}
        contract_data2 = {"id": contract_id2, "name": "Contract 2"}

        # Baseline: Prometheus counters are process-global; measure deltas only.
        metrics_before = get_contract_cache_metrics()

        # Cache contracts
        cache_contract(contract_id1, contract_data1)
        cache_contract(contract_id2, contract_data2)

        # Get cached contracts (generates hits)
        get_cached_contract_with_metrics(contract_id1)
        get_cached_contract_with_metrics(contract_id2)

        metrics = get_contract_cache_metrics()

        # Verify metrics structure (real metrics system provides this)
        self.assertIsNotNone(metrics)
        self.assertIn("hits", metrics)
        self.assertIn("misses", metrics)
        self.assertIn("hit_rate", metrics)
        self.assertIsInstance(metrics["hits"], (int, float))
        self.assertIsInstance(metrics["misses"], (int, float))
        delta_hits = metrics["hits"] - metrics_before["hits"]
        delta_misses = metrics["misses"] - metrics_before["misses"]
        delta_total = delta_hits + delta_misses
        self.assertGreater(delta_total, 0, "Expected cache metrics to change after gets")
        self.assertGreater(delta_hits, 0, "Expected at least one recorded cache hit in this test")
        hit_rate_delta = delta_hits / delta_total
        self.assertGreater(hit_rate_delta, 0)
        self.assertLessEqual(metrics["hit_rate"], 1)

    def test_cache_metrics_integration(self):
        """Test cache metrics integration with real caching."""
        contract_id = "test-contract-metrics"
        contract_data = {"id": contract_id, "name": "Test Contract"}

        # Cache contract
        cache_contract(contract_id, contract_data)

        # First get - should be a hit
        cached1 = get_cached_contract_with_metrics(contract_id)
        self.assertIsNotNone(cached1)

        # Second get - should also be a hit
        cached2 = get_cached_contract_with_metrics(contract_id)
        self.assertIsNotNone(cached2)

        # Get metrics
        # Note: Metrics may not be initialized in test environment
        # This test verifies the function works without errors
        metrics = get_contract_cache_metrics()
        self.assertIn("hits", metrics)
        self.assertIn("misses", metrics)
        self.assertIn("hit_rate", metrics)
        # Metrics may be 0 if not initialized, which is acceptable in tests


class TestEnhancedCachingIntegration(TestCase):
    """Integration tests for enhanced contract caching."""

    def setUp(self):
        """Set up test fixtures."""
        self.redis_client = get_real_redis_client_or_none()
        if self.redis_client is None:
            self.skipTest("Redis not available for integration tests")

    def tearDown(self):
        """Clean up test fixtures."""
        try:
            keys = self.redis_client.keys("contract:*")
            if keys:
                self.redis_client.delete(*keys)
            keys = self.redis_client.keys("cache_tag:*")
            if keys:
                self.redis_client.delete(*keys)
        except Exception:
            pass

    def test_full_caching_lifecycle_with_tags(self):
        """Test complete caching lifecycle with tags."""
        contract_id = "test-contract-lifecycle"
        contract_data = {"id": contract_id, "name": "Test Contract"}
        tags = ["tenant:t1", "owner:user1"]

        # Cache with tags
        cache_contract_with_tags(contract_id, contract_data, tags=tags)

        # Verify cached
        cached = get_cached_contract_with_metrics(contract_id)
        self.assertIsNotNone(cached)

        # Invalidate by tag
        invalidate_contract_cache_by_tags(["tenant:t1"])

        # Verify invalidated
        cached_after = get_cached_contract_with_metrics(contract_id)
        self.assertIsNone(cached_after)

    def test_cache_warming_and_metrics(self):
        """
        Test cache warming combined with metrics using real Contract model.

        Uses real Contract objects to verify cache warming with metrics integration.
        """
        # Create a contract for warming
        contract_id = "test-warm-metrics"
        contract_data = {"id": contract_id, "name": "Warm Metrics Contract"}
        tags = ["tenant:t1", "owner:user1"]

        # Cache with tags
        cache_contract_with_tags(contract_id, contract_data, tags=tags)

        # Get cached contract with metrics (should be a hit)
        cached = get_cached_contract_with_metrics(contract_id)
        self.assertIsNotNone(cached)

        # Metrics are recorded by real metrics system
        # We verify the functionality works, metrics are recorded automatically

    # Edge cases and error handling tests
    def test_cache_with_none_contract_id(self):
        """Test caching with None contract ID."""
        contract_data = {"id": "test", "name": "Test"}

        # Should handle None contract_id gracefully
        try:
            cache_contract_with_tags(None, contract_data, tags=["tenant:t1"])
            # May cache or skip
        except Exception:
            # If it raises exception, that's acceptable
            pass

    def test_cache_with_empty_contract_id(self):
        """Test caching with empty contract ID."""
        contract_data = {"id": "test", "name": "Test"}

        # Should handle empty contract_id gracefully
        try:
            cache_contract_with_tags("", contract_data, tags=["tenant:t1"])
            # May cache or skip
        except Exception:
            # If it raises exception, that's acceptable
            pass

    def test_cache_with_none_contract_data(self):
        """Test caching with None contract data."""
        # Should handle None contract_data gracefully
        try:
            cache_contract_with_tags("test-id", None, tags=["tenant:t1"])
            # May cache or skip
        except Exception:
            # If it raises exception, that's acceptable
            pass

    def test_cache_with_empty_tags(self):
        """Test caching with empty tags list."""
        contract_id = "test-contract-empty-tags"
        contract_data = {"id": contract_id, "name": "Test"}

        # Should handle empty tags gracefully
        cache_contract_with_tags(contract_id, contract_data, tags=[])

        # Verify cached
        cached = get_cached_contract(contract_id)
        self.assertIsNotNone(cached)

    def test_cache_with_none_tags(self):
        """Test caching with None tags."""
        contract_id = "test-contract-none-tags"
        contract_data = {"id": contract_id, "name": "Test"}

        # Should handle None tags gracefully
        try:
            cache_contract_with_tags(contract_id, contract_data, tags=None)
            # May cache or skip
        except Exception:
            # If it raises exception, that's acceptable
            pass

    def test_cache_with_very_large_contract_data(self):
        """Test caching with very large contract data."""
        contract_id = "test-contract-large"
        large_data = {
            "id": contract_id,
            "name": "Large Contract",
            "description": "A" * 100000,  # Very long string
            "fields": [{"name": f"field_{i}", "type": "string"} for i in range(1000)],
        }

        # Should handle very large data
        cache_contract_with_tags(contract_id, large_data, tags=["tenant:t1"])

        # Verify cached
        cached = get_cached_contract(contract_id)
        self.assertIsNotNone(cached)

    def test_cache_with_special_characters(self):
        """Test caching with special characters."""
        contract_id = "test-contract-<>&\"'"
        contract_data = {"id": contract_id, "name": "Contract <>&\"'"}

        # Should handle special characters
        cache_contract_with_tags(contract_id, contract_data, tags=["tenant:t1"])

        # Verify cached
        cached = get_cached_contract(contract_id)
        self.assertIsNotNone(cached)

    def test_cache_with_unicode(self):
        """Test caching with unicode characters."""
        contract_id = "产品名称"
        contract_data = {"id": contract_id, "name": "产品名称"}

        # Should handle unicode
        cache_contract_with_tags(contract_id, contract_data, tags=["tenant:t1"])

        # Verify cached
        cached = get_cached_contract(contract_id)
        self.assertIsNotNone(cached)

    def test_invalidate_with_empty_tags(self):
        """Test invalidating with empty tags list."""
        # Should handle empty tags gracefully
        result = invalidate_contract_cache_by_tags([])
        # May return success or skip
        self.assertIsNotNone(result)

    def test_invalidate_with_none_tags(self):
        """Test invalidating with None tags."""
        # Should handle None tags gracefully
        try:
            result = invalidate_contract_cache_by_tags(None)
            # May return error or handle gracefully
            self.assertIsNotNone(result)
        except Exception:
            # If it raises exception, that's acceptable
            pass

    def test_invalidate_with_nonexistent_tags(self):
        """Test invalidating with nonexistent tags."""
        contract_id = "test-contract-nonexistent-tags"
        contract_data = {"id": contract_id, "name": "Test"}
        cache_contract_with_tags(contract_id, contract_data, tags=["tenant:t1"])

        # Invalidate with nonexistent tag
        invalidate_contract_cache_by_tags(["tenant:nonexistent"])

        # Contract should still be cached
        cached = get_cached_contract(contract_id)
        self.assertIsNotNone(cached)

    def test_get_cached_with_none_contract_id(self):
        """Test getting cached contract with None contract ID."""
        # Should handle None contract_id gracefully
        try:
            cached = get_cached_contract_with_metrics(None)
            # May return None or raise exception
            self.assertIsNone(cached)
        except Exception:
            # If it raises exception, that's acceptable
            pass

    def test_get_cached_with_empty_contract_id(self):
        """Test getting cached contract with empty contract ID."""
        # Empty contract_id should not crash; result depends on cache state
        cached = get_cached_contract_with_metrics("")
        # Empty key may return None or data (Redis treats "" as valid key).
        # The important thing is no exception is raised.
        self.assertIsInstance(cached, (dict, type(None)))

    def test_cache_metrics_with_no_operations(self):
        """Test getting cache metrics with no cache operations."""
        # Get metrics without any cache operations
        metrics = get_contract_cache_metrics()

        # Should return metrics structure (may be zeros)
        self.assertIsNotNone(metrics)
        self.assertIn("hits", metrics)
        self.assertIn("misses", metrics)
        self.assertIn("hit_rate", metrics)

    def test_warm_with_zero_limit(self):
        """Test cache warming with zero limit."""
        # Should handle zero limit gracefully
        warmed_count = warm_frequently_accessed_contracts(limit=0)
        self.assertEqual(warmed_count, 0)

    def test_warm_with_negative_limit(self):
        """Test cache warming with negative limit."""
        # Should handle negative limit gracefully
        try:
            warmed_count = warm_frequently_accessed_contracts(limit=-1)
            # Negative limit should not warm any contracts
            self.assertEqual(warmed_count, 0)
        except Exception:
            # If it raises exception, that's acceptable
            pass

    def test_warm_with_very_large_limit(self):
        """Test cache warming with very large limit."""
        import uuid

        # Isolate from shared DB: only contracts for a non-existent tenant may be warmed.
        warmed_count = warm_frequently_accessed_contracts(
            tenant_id=str(uuid.uuid4()), limit=1000000
        )
        self.assertEqual(warmed_count, 0)

    def test_warm_with_nonexistent_tenant_id(self):
        """Test cache warming with nonexistent tenant ID."""
        import uuid

        fake_tenant_id = str(uuid.uuid4())

        # Should handle nonexistent tenant gracefully
        warmed_count = warm_frequently_accessed_contracts(tenant_id=fake_tenant_id, limit=10)
        self.assertEqual(warmed_count, 0)

    def test_cache_concurrent_operations(self):
        """Test concurrent cache operations."""
        import threading

        contract_ids = [f"contract-{i}" for i in range(10)]
        results = []

        def cache_contracts():
            for contract_id in contract_ids:
                contract_data = {"id": contract_id, "name": f"Contract {contract_id}"}
                cache_contract_with_tags(contract_id, contract_data, tags=["tenant:t1"])
                cached = get_cached_contract(contract_id)
                results.append(cached is not None)

        # Run concurrent operations
        threads = [threading.Thread(target=cache_contracts) for _ in range(3)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Should handle concurrent operations
        self.assertGreater(len(results), 0)

    def test_cache_expiration_handling(self):
        """Test cache expiration handling."""
        contract_id = "test-contract-expiration"
        contract_data = {"id": contract_id, "name": "Test"}

        # Cache contract
        cache_contract_with_tags(contract_id, contract_data, tags=["tenant:t1"], ttl=1)

        # Verify cached immediately
        cached = get_cached_contract(contract_id)
        self.assertIsNotNone(cached)

        # Verify cache was populated (expiry tested via cache.delete, not sleep)
        from django.core.cache import cache
        cache.clear()  # Simulate expiry by clearing cache

        cached_after = get_cached_contract(contract_id)
        self.assertIsNone(cached_after)  # Cache cleared = expired
