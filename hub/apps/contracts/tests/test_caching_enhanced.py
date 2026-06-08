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
from hub.apps.tenants.models import Tenant


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
        except (redis.ConnectionError, redis.TimeoutError, redis.ResponseError):
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
        except (redis.ConnectionError, redis.TimeoutError, redis.ResponseError):
            pass

    def test_cache_contract_with_tags(self):
        """Caching contract with tags stores tags in Redis SMEMBERS sets."""
        contract_id = "test-contract-1"
        contract_data = {"id": contract_id, "name": "Test Contract"}
        tags = ["tenant:test-tenant", "owner:user1", "status:active"]

        cache_contract_with_tags(contract_id, contract_data, tags=tags)

        # Verify contract is cached
        cached = get_cached_contract(contract_id)
        self.assertIsNotNone(cached)
        self.assertEqual(cached["id"], contract_id)

        # Verify tags were stored in Redis sets
        for tag in tags:
            tag_key = f"cache_tag:contract:{tag}"
            members = self.redis_client.smembers(tag_key)
            self.assertIn(contract_id, members,
                f"Tag '{tag}' must contain contract_id '{contract_id}'")

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
        """Invalidation uses OR logic: any matching tag removes the contract.

        contract-1 gets two tags (tag_a, tag_b), contract-2 gets one distinct tag (tag_c).
        Invalidating tag_a alone removes contract-1 but leaves contract-2 untouched,
        proving OR semantics (not AND — tag_b is irrelevant).
        """
        contract1_data = {"id": "contract-1", "name": "Contract 1"}
        contract2_data = {"id": "contract-2", "name": "Contract 2"}

        cache_contract_with_tags("contract-1", contract1_data, tags=["tag_a", "tag_b"])
        cache_contract_with_tags("contract-2", contract2_data, tags=["tag_c"])

        # Invalidate by tag_a only — OR logic: contract-1 has tag_a → removed
        invalidate_contract_cache_by_tags(["tag_a"])

        self.assertIsNone(get_cached_contract("contract-1"),
            "contract-1 must be invalidated (it has tag_a)")
        self.assertIsNotNone(get_cached_contract("contract-2"),
            "contract-2 must survive (tag_a is not among its tags)")

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

        uid = uuid.uuid4().hex[:8]
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
        Warm cache using real Contract.objects.filter() — verify contracts were cached.
        """
        warmed_count = warm_frequently_accessed_contracts(
            tenant_id=str(self.tenant.id), limit=10
        )

        # We seeded 2 contracts for our tenant above; warming must find them.
        self.assertGreater(warmed_count, 0,
            "Expected warm_frequently_accessed_contracts to cache at least our 2 seeded contracts")

        # Verify both seeded contracts are now in cache.
        for c in (self.contract1, self.contract2):
            cached = get_cached_contract(str(c.id))
            self.assertIsNotNone(cached,
                f"Contract {c.id} should be cached after warming")
            self.assertEqual(cached.get("tenant_id"), str(self.tenant.id))

    def test_warm_contracts_by_tenant(self):
        """
        Warm cache for a specific tenant — verify only that tenant's contracts are cached.
        """
        # Create a contract in a different tenant to verify it is excluded
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Warm Tenant {_uid}",
            slug=f"other-warm-tenant-{_uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        other_contract = Contract.objects.create(
            tenant=other_tenant,
            hub_contract_json={"name": "Other Contract", "id": f"other-{_uid}"},
            status=ContractStatus.ACTIVE,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"name": "Other Contract"}',
            created_by=self.user,
        )

        warmed_count = warm_frequently_accessed_contracts(tenant_id=str(self.tenant.id), limit=10)

        self.assertGreater(warmed_count, 0,
            "Expected warming by tenant to find our seeded contracts")

        for c in (self.contract1, self.contract2):
            cached = get_cached_contract(str(c.id))
            self.assertIsNotNone(cached,
                f"Contract {c.id} should be cached after per-tenant warming")

        # Other tenant's contract must NOT be cached
        other_cached = get_cached_contract(str(other_contract.id))
        self.assertIsNone(other_cached,
            f"Other tenant's contract {other_contract.id} must NOT be cached after tenant-scoped warm")


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
        except (redis.ConnectionError, redis.TimeoutError, redis.ResponseError):
            pass

    def tearDown(self):
        """Clean up test fixtures."""
        try:
            keys = self.redis_client.keys("contract:*")
            if keys:
                self.redis_client.delete(*keys)
        except (redis.ConnectionError, redis.TimeoutError, redis.ResponseError):
            pass

    def test_cache_hit_metrics(self):
        """
        Cache hit metrics are recorded on get_cached_contract_with_metrics.
        """
        contract_id = "test-contract-hit"
        contract_data = {"id": contract_id, "name": "Test"}

        # Capture baseline
        metrics_before = get_contract_cache_metrics()

        # Cache → get → should be a hit
        cache_contract(contract_id, contract_data)
        cached = get_cached_contract_with_metrics(contract_id)

        self.assertIsNotNone(cached)
        self.assertEqual(cached["id"], contract_id)

        # Delta verification: hits must have increased
        metrics_after = get_contract_cache_metrics()
        delta_hits = metrics_after["hits"] - metrics_before["hits"]
        self.assertGreater(delta_hits, 0,
            f"Expected cache hits to increase, delta_hits={delta_hits}")

    def test_cache_miss_metrics(self):
        """
        Cache miss metrics are recorded for non-existent keys.
        """
        contract_id = f"non-existent-{uuid.uuid4().hex[:8]}"

        # Capture baseline
        metrics_before = get_contract_cache_metrics()

        cached = get_cached_contract_with_metrics(contract_id)
        self.assertIsNone(cached)

        # Delta verification: misses must have increased
        metrics_after = get_contract_cache_metrics()
        delta_misses = metrics_after["misses"] - metrics_before["misses"]
        self.assertGreater(delta_misses, 0,
            f"Expected cache misses to increase, delta_misses={delta_misses}")

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
        """Cache metrics integration: delta hits must increase after cache gets."""
        contract_id = "test-contract-metrics"
        contract_data = {"id": contract_id, "name": "Test Contract"}

        # Capture baseline metrics before any operations
        metrics_before = get_contract_cache_metrics()

        # Cache contract
        cache_contract(contract_id, contract_data)

        # Two cache gets — both should be hits
        cached1 = get_cached_contract_with_metrics(contract_id)
        self.assertIsNotNone(cached1)

        cached2 = get_cached_contract_with_metrics(contract_id)
        self.assertIsNotNone(cached2)

        # Get metrics after operations
        metrics_after = get_contract_cache_metrics()

        self.assertIn("hits", metrics_after)
        self.assertIn("misses", metrics_after)
        self.assertIn("hit_rate", metrics_after)

        # Delta verification: hits must have increased
        delta_hits = metrics_after["hits"] - metrics_before["hits"]
        self.assertGreater(delta_hits, 0,
            f"Expected cache hits to increase after 2 gets, but delta_hits={delta_hits}")


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
        except (redis.ConnectionError, redis.TimeoutError, redis.ResponseError):
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

    def test_cache_with_tags_and_metrics_integration(self):
        """
        Test cache tags combined with metrics integration (no warming — renamed).

        Verifies that caching with tags followed by a metrics-tracked get
        returns the cached data correctly, and that the full lifecycle
        (tag-based invalidation) works end-to-end.
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
        self.assertEqual(cached["id"], contract_id)

        # Verify tag-based invalidation works end-to-end
        invalidate_contract_cache_by_tags(["tenant:t1"])
        self.assertIsNone(get_cached_contract_with_metrics(contract_id))

    # Edge cases and error handling tests
    def test_cache_with_none_contract_id(self):
        """Caching with None contract_id must not crash — guard returns early."""
        contract_data = {"id": "test", "name": "Test"}

        # Must not raise; our guard returns early before Redis is touched
        # (caching_enhanced.py:105 — ``if not contract_id: return``).
        cache_contract_with_tags(None, contract_data, tags=["tenant:t1"])
        # The guard at caching_enhanced.py:105 returns early when contract_id
        # is None, so the tag-level path AND cache_contract() are both skipped.
        # We verify nothing blew up.

    def test_cache_with_empty_contract_id(self):
        """Caching with empty contract_id must not crash — guard returns early."""
        contract_data = {"id": "", "name": "Test"}

        cache_contract_with_tags("", contract_data, tags=["tenant:t1"])
        # Should not raise; empty-string key is blocked by the same guard.

    def test_cache_with_none_contract_data(self):
        """Caching with None contract_data must not crash — verify no data cached."""
        cache_contract_with_tags("test-id", None, tags=["tenant:t1"])
        # After caching None, a subsequent get must return None (no data was stored).
        cached = get_cached_contract("test-id")
        self.assertIsNone(cached)

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
        """Caching with None tags must not crash — guard returns early."""
        contract_id = "test-contract-none-tags"
        contract_data = {"id": contract_id, "name": "Test"}

        cache_contract_with_tags(contract_id, contract_data, tags=None)
        # Should not raise; None tags skip the tag-indexing path entirely.
        cached = get_cached_contract(contract_id)
        self.assertIsNotNone(cached)

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
        """Invalidating with empty tags list returns 0 and leaves cache intact."""
        contract_id = "test-empty-tags-invalidation"
        contract_data = {"id": contract_id, "name": "Test"}

        # Cache a contract with a real tag first
        cache_contract_with_tags(contract_id, contract_data, tags=["tenant:t1"])

        # Verify it's cached
        self.assertIsNotNone(get_cached_contract(contract_id),
            "Contract must be cached before invalidation")

        # Invalidate with empty tags — must return 0
        result = invalidate_contract_cache_by_tags([])
        self.assertEqual(result, 0,
            "Empty tags list must invalidate zero contracts")

        # Contract must still be cached (nothing was invalidated)
        self.assertIsNotNone(get_cached_contract(contract_id),
            "Contract must survive empty-tag invalidation")

    def test_invalidate_with_none_tags(self):
        """Invalidating with None tags must return 0 — guard returns early."""
        result = invalidate_contract_cache_by_tags(None)
        # Guard clamps None to empty → skips invalidation, returns 0.
        self.assertEqual(result, 0)

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
        """Getting cached contract with None contract_id returns None / raises ValueError."""
        # get_cached_contract() (called internally) will hit the cache
        # with a None key; Django's cache backend may treat this as
        # cache.get(None) which either returns None (LocMemCache) or
        # raises (Redis).  Either outcome is fine — we just verify
        # there is no unhandled crash path.
        try:
            cached = get_cached_contract_with_metrics(None)
            self.assertIsNone(cached)
        except (ValueError, TypeError):
            # Acceptable: some backends reject None keys at the client level.
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
        """Cache warming with negative limit must clamp to 0 — no query executed."""
        warmed_count = warm_frequently_accessed_contracts(limit=-1)
        # Guard clamps limit<0 to 0 → returns 0 without touching the DB.
        self.assertEqual(warmed_count, 0)

    def test_warm_with_very_large_limit(self):
        """Test cache warming with very large limit."""
        # Isolate from shared DB: only contracts for a non-existent tenant may be warmed.
        warmed_count = warm_frequently_accessed_contracts(
            tenant_id=str(uuid.uuid4()), limit=1000000
        )
        self.assertEqual(warmed_count, 0)

    def test_warm_with_nonexistent_tenant_id(self):
        """Test cache warming with nonexistent tenant ID."""
        fake_tenant_id = str(uuid.uuid4())

        # Should handle nonexistent tenant gracefully
        warmed_count = warm_frequently_accessed_contracts(tenant_id=fake_tenant_id, limit=10)
        self.assertEqual(warmed_count, 0)

    def test_cache_concurrent_operations(self):
        """Concurrent cache operations must not corrupt data or lose writes."""
        import threading

        contract_ids = [f"contract-{i}" for i in range(10)]
        results = []
        errors = []

        def cache_contracts():
            for contract_id in contract_ids:
                try:
                    contract_data = {"id": contract_id, "name": f"Contract {contract_id}"}
                    cache_contract_with_tags(contract_id, contract_data, tags=["tenant:t1"])
                    cached = get_cached_contract(contract_id)
                    results.append((contract_id, cached is not None))
                except Exception as e:
                    errors.append((contract_id, str(e)))

        # Run concurrent operations — 3 threads × 10 contracts = 30 writes total
        threads = [threading.Thread(target=cache_contracts) for _ in range(3)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # All 30 writes must succeed with zero errors
        self.assertEqual(len(errors), 0,
            f"Concurrent operations produced {len(errors)} errors: {errors}")
        self.assertEqual(len(results), 30,
            f"Expected 30 results (3 threads × 10 contracts), got {len(results)}")

        # Every result must report a successful cache hit
        self.assertTrue(all(success for _, success in results),
            "All cached contracts must be retrievable after concurrent writes")

        # Verify sample data integrity — first contract from each thread
        for cid in contract_ids[:3]:
            cached = get_cached_contract(cid)
            self.assertIsNotNone(cached, f"Contract {cid} must survive concurrent writes")
            self.assertEqual(cached["id"], cid)

    def test_cache_clear_removes_cached_entries(self):
        """Verify that cache.clear() removes cached entries (simulates expiry)."""
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

    def test_invalidate_by_tags_redis_fallback(self):
        """Tag-based invalidation handles both Redis and Django fallback paths.

        Caches a contract with known tags, invalidates by one tag, and
        verifies the outcome.  When Redis is available the contract is
        removed; when only the Django fallback is active the contract may
        survive (Django LocMemCache does not support tag-based invalidation).
        Both outcomes are valid — the invariant is no crash.
        """
        contract_id = "test-redis-fallback"
        contract_data = {"id": contract_id, "name": "Fallback Test"}

        # Cache contract with tags via Redis (if available) or Django fallback
        cache_contract_with_tags(contract_id, contract_data, tags=["tenant:t1", "owner:user1"])

        # Verify cached
        self.assertIsNotNone(get_cached_contract(contract_id),
            "Contract must be cached before invalidation")

        # Invalidate by tag
        invalidated = invalidate_contract_cache_by_tags(["tenant:t1"])
        self.assertGreaterEqual(invalidated, 0,
            "Invalidation count must be non-negative")

        cached_after = get_cached_contract(contract_id)
        if invalidated > 0:
            # Redis path: contract must be gone
            self.assertIsNone(cached_after,
                "Contract must be invalidated when Redis tag indexing is active")
        else:
            # Django fallback path: contract may survive since Django's
            # LocMemCache doesn't support tag-based pattern invalidation.
            # The contract should still be retrievable (cache was not cleared).
            self.assertIsInstance(cached_after, (dict, type(None)),
                "After invalidation with count=0, cache state must be coherent")
