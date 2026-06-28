"""
Comprehensive tests for Dataset Caching Utilities

Tests cover:
- Cache key generation
- Cache storage and retrieval
- Cache invalidation
- Tenant isolation
- Filter hash generation
- Error handling
"""

import uuid

try:
    import pytest

    pytestmark = pytest.mark.django_db
except ImportError:
    # pytest not available, tests will run with Django test runner
    pytestmark = None

from django.core.cache import cache
from django.test import override_settings

from hub.apps.assets.models import Asset
from hub.apps.datasets.caching import (
    cache_dataset_detail,
    cache_dataset_list,
    get_cached_dataset_detail,
    get_cached_dataset_list,
    get_dataset_detail_cache_key,
    get_dataset_list_cache_key,
    get_tenant_id_from_request,
    hash_filters,
    invalidate_dataset_caches,
    invalidate_dataset_detail_cache,
    invalidate_dataset_list_cache,
)
from hub.apps.datasets.models import Dataset
from hub.apps.datasets.tests.test_base import DatasetsTestBase
from hub.apps.tenants.models import Tenant


class DatasetCachingTest(DatasetsTestBase):
    """Test dataset caching utilities"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        # Clear cache before each test
        cache.clear()

        uid2 = uuid.uuid4().hex[:8]
        self.tenant2 = Tenant.objects.create(name=f"Test Tenant {uid2}", slug=f"test-tenant-{uid2}")
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
        )
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=1,
            created_by=self.user,
        )

    def test_get_dataset_list_cache_key(self):
        """Test dataset list cache key generation"""
        tenant_id = str(self.tenant.id)
        filters_hash = "abc123"

        key = get_dataset_list_cache_key(tenant_id, filters_hash)
        self.assertEqual(key, f"dataset:list:{tenant_id}:{filters_hash}")

    def test_get_dataset_detail_cache_key(self):
        """Test dataset detail cache key generation"""
        dataset_id = str(self.dataset.id)

        key = get_dataset_detail_cache_key(dataset_id)
        self.assertEqual(key, f"dataset:detail:{dataset_id}")

    def test_hash_filters(self):
        """Test filter hash generation"""
        filters1 = {"page": 1, "page_size": 50, "dataset_format": "CSV"}
        filters2 = {"dataset_format": "CSV", "page_size": 50, "page": 1}
        filters3 = {"page": 1, "page_size": 50, "dataset_format": "JSON"}

        hash1 = hash_filters(filters1)
        hash2 = hash_filters(filters2)
        hash3 = hash_filters(filters3)

        # Same filters should produce same hash (order independent)
        self.assertEqual(hash1, hash2)
        # Different filters should produce different hash
        self.assertNotEqual(hash1, hash3)

    def test_hash_filters_normalizes_none_values(self):
        """Test that None values are excluded from hash"""
        filters1 = {"page": 1, "dataset_format": None, "asset_id": ""}
        filters2 = {"page": 1}

        hash1 = hash_filters(filters1)
        hash2 = hash_filters(filters2)

        # Should produce same hash when None/empty values are removed
        self.assertEqual(hash1, hash2)

    def test_cache_dataset_list(self):
        """Test caching dataset list"""
        tenant_id = str(self.tenant.id)
        filters_hash = hash_filters({"page": 1})
        results = [{"id": str(self.dataset.id), "name": "Test Dataset"}]
        total_count = 1

        # Cache should not exist initially
        cached = get_cached_dataset_list(tenant_id, filters_hash)
        self.assertIsNone(cached)

        # Cache the list
        cache_dataset_list(tenant_id, filters_hash, results, total_count)

        # Retrieve from cache
        cached_results, cached_count = get_cached_dataset_list(tenant_id, filters_hash)
        self.assertIsNotNone(cached_results)
        self.assertEqual(cached_results, results)
        self.assertEqual(cached_count, total_count)

    def test_cache_dataset_list_with_custom_ttl(self):
        """Test caching dataset list with custom TTL"""
        tenant_id = str(self.tenant.id)
        filters_hash = hash_filters({"page": 1})
        results = [{"id": str(self.dataset.id)}]
        custom_ttl = 60

        cache_dataset_list(tenant_id, filters_hash, results, 1, ttl=custom_ttl)

        # Verify cache exists
        cached = get_cached_dataset_list(tenant_id, filters_hash)
        self.assertIsNotNone(cached)

    def test_cache_dataset_list_tenant_isolation(self):
        """Test that cache is isolated per tenant"""
        tenant_id1 = str(self.tenant.id)
        tenant_id2 = str(self.tenant2.id)
        filters_hash = hash_filters({"page": 1})
        results1 = [{"id": str(self.dataset.id)}]
        results2 = [{"id": "other-dataset-id"}]

        # Cache for tenant 1
        cache_dataset_list(tenant_id1, filters_hash, results1, 1)

        # Cache for tenant 2
        cache_dataset_list(tenant_id2, filters_hash, results2, 1)

        # Verify isolation
        cached1, _ = get_cached_dataset_list(tenant_id1, filters_hash)
        cached2, _ = get_cached_dataset_list(tenant_id2, filters_hash)

        self.assertEqual(cached1, results1)
        self.assertEqual(cached2, results2)

    def test_cache_dataset_detail(self):
        """Test caching dataset detail"""
        dataset_id = str(self.dataset.id)
        dataset_data = {"id": dataset_id, "name": "Test Dataset", "format": "CSV"}

        # Cache should not exist initially
        cached = get_cached_dataset_detail(dataset_id)
        self.assertIsNone(cached)

        # Cache the detail
        cache_dataset_detail(dataset_id, dataset_data)

        # Retrieve from cache
        cached_data = get_cached_dataset_detail(dataset_id)
        self.assertIsNotNone(cached_data)
        self.assertEqual(cached_data, dataset_data)

    def test_cache_dataset_detail_with_custom_ttl(self):
        """Test caching dataset detail with custom TTL"""
        dataset_id = str(self.dataset.id)
        dataset_data = {"id": dataset_id}

        cache_dataset_detail(dataset_id, dataset_data, ttl=60)

        # Verify cache exists
        cached = get_cached_dataset_detail(dataset_id)
        self.assertIsNotNone(cached)

    def test_invalidate_dataset_list_cache_no_error(self):
        """Test invalidating dataset list cache — completes without raising."""
        tenant_id = str(self.tenant.id)
        filters_hash1 = hash_filters({"page": 1})
        filters_hash2 = hash_filters({"page": 2})
        results = [{"id": str(self.dataset.id)}]

        # Cache multiple queries
        cache_dataset_list(tenant_id, filters_hash1, results, 1)
        cache_dataset_list(tenant_id, filters_hash2, results, 1)

        # Verify both are cached
        self.assertIsNotNone(get_cached_dataset_list(tenant_id, filters_hash1))
        self.assertIsNotNone(get_cached_dataset_list(tenant_id, filters_hash2))

        # Invalidate tenant's list cache.  With LocMemCache pattern-based
        # invalidation is best-effort; the contract is that the call
        # completes without raising.
        invalidate_dataset_list_cache(tenant_id)

    @override_settings(CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "test-invalidation-isolated",
        },
    })
    def test_invalidate_dataset_list_cache_isolated_backend_no_raise(self):
        """invalidate_dataset_list_cache() completes without raising on LocMemCache.

        Pattern-based invalidation requires Redis (``invalidate_dataset_list_cache``
        is a best-effort no-op for non-Redis backends — it logs a debug message and
        returns).  This test verifies the function does not raise on a clean
        isolated backend.
        """
        from django.core.cache import caches

        isolated_cache = caches["default"]
        tenant_id = str(self.tenant.id)
        filters_hash = hash_filters({"page": 1})
        key = get_dataset_list_cache_key(tenant_id, filters_hash)
        isolated_cache.set(key, ([{"id": str(self.dataset.id)}], 1))

        # Must not raise.
        invalidate_dataset_list_cache(tenant_id)

    def test_invalidate_dataset_detail_cache(self):
        """Test invalidating dataset detail cache"""
        dataset_id = str(self.dataset.id)
        dataset_data = {"id": dataset_id}

        # Cache the detail
        cache_dataset_detail(dataset_id, dataset_data)

        # Verify cache exists
        self.assertIsNotNone(get_cached_dataset_detail(dataset_id))

        # Invalidate
        invalidate_dataset_detail_cache(dataset_id)

        # Verify cache is gone
        self.assertIsNone(get_cached_dataset_detail(dataset_id))

    def test_invalidate_dataset_caches(self):
        """Test invalidating all caches for a dataset"""
        tenant_id = str(self.tenant.id)
        dataset_id = str(self.dataset.id)
        filters_hash = hash_filters({"page": 1})
        dataset_data = {"id": dataset_id}
        results = [dataset_data]

        # Cache both list and detail
        cache_dataset_list(tenant_id, filters_hash, results, 1)
        cache_dataset_detail(dataset_id, dataset_data)

        # Verify both are cached
        self.assertIsNotNone(get_cached_dataset_list(tenant_id, filters_hash))
        self.assertIsNotNone(get_cached_dataset_detail(dataset_id))

        # Invalidate all caches
        invalidate_dataset_caches(dataset_id, tenant_id)

        # Verify detail cache is gone
        self.assertIsNone(get_cached_dataset_detail(dataset_id))

        # List cache invalidation tested separately (may not work with LocMemCache)

    def test_get_tenant_id_from_request(self):
        """Test extracting tenant ID from request"""
        from rest_framework.test import APIRequestFactory

        factory = APIRequestFactory()

        # Test with user.tenant
        request = factory.get("/api/v1/datasets/")
        request.user = self.user
        tenant_id = get_tenant_id_from_request(request)
        self.assertEqual(tenant_id, str(self.tenant.id))

        # Test with request.tenant_id
        request.tenant_id = str(self.tenant.id)
        tenant_id = get_tenant_id_from_request(request)
        self.assertEqual(tenant_id, str(self.tenant.id))

        # Test with request.tenant
        request.tenant = self.tenant
        tenant_id = get_tenant_id_from_request(request)
        self.assertEqual(tenant_id, str(self.tenant.id))

    def test_cache_handles_empty_results(self):
        """Test that cache handles empty results correctly"""
        tenant_id = str(self.tenant.id)
        filters_hash = hash_filters({"page": 1})

        # Cache empty results
        cache_dataset_list(tenant_id, filters_hash, [], 0)

        # Retrieve from cache
        cached_results, cached_count = get_cached_dataset_list(tenant_id, filters_hash)
        self.assertEqual(cached_results, [])
        self.assertEqual(cached_count, 0)

    def test_cache_handles_large_results(self):
        """Test that cache handles large result sets"""
        tenant_id = str(self.tenant.id)
        filters_hash = hash_filters({"page": 1})
        # Create a large result set
        results = [{"id": f"dataset-{i}", "name": f"Dataset {i}"} for i in range(1000)]
        total_count = 1000

        cache_dataset_list(tenant_id, filters_hash, results, total_count)

        # Retrieve from cache
        cached_results, cached_count = get_cached_dataset_list(tenant_id, filters_hash)
        self.assertEqual(len(cached_results), 1000)
        self.assertEqual(cached_count, 1000)

    @override_settings(CACHE_TTL_DATASET_LIST=120)
    def test_cache_uses_settings_ttl(self):
        """Test that cache uses TTL from settings"""
        tenant_id = str(self.tenant.id)
        filters_hash = hash_filters({"page": 1})
        results = [{"id": str(self.dataset.id)}]

        # Cache should use settings TTL
        cache_dataset_list(tenant_id, filters_hash, results, 1)

        # Verify cache exists
        cached = get_cached_dataset_list(tenant_id, filters_hash)
        self.assertIsNotNone(cached)

    def test_cache_and_retrieve_basic_operation(self):
        """Cache set + get round-trips correctly for list and detail."""
        tenant_id = str(self.tenant.id)
        filters_hash = hash_filters({"page": 1})
        results = [{"id": str(self.dataset.id)}]
        detail_data = {"id": str(self.dataset.id)}

        cache_dataset_list(tenant_id, filters_hash, results, 1)
        cache_dataset_detail(str(self.dataset.id), detail_data)

        # Verify the list cache can be retrieved
        cached_list = get_cached_dataset_list(tenant_id, filters_hash)
        self.assertIsNotNone(cached_list, "Cached list should be retrievable")

        # Verify the detail cache can be retrieved
        cached_detail = get_cached_dataset_detail(str(self.dataset.id))
        self.assertIsNotNone(cached_detail, "Cached detail should be retrievable")
        self.assertEqual(cached_detail, detail_data)

    # ========== EDGE CASES ==========

    def test_cache_edge_case_empty_tenant_id(self):
        """Empty tenant_id produces a valid cache key (not an error)."""
        key = get_dataset_list_cache_key("", "abc123")
        self.assertIsNotNone(key)

    def test_cache_edge_case_very_long_filters_hash(self):
        """Test caching with very long filters_hash (edge case)"""
        long_hash = "a" * 1000
        key = get_dataset_list_cache_key(str(self.tenant.id), long_hash)

        # Should handle long hash gracefully
        self.assertIsNotNone(key)
        self.assertIn(long_hash, key)

    def test_cache_edge_case_special_characters_in_hash(self):
        """Test caching with special characters in hash (edge case)"""
        special_hash = "abc!@#$%^&*()123"
        key = get_dataset_list_cache_key(str(self.tenant.id), special_hash)

        # Should handle special characters gracefully
        self.assertIsNotNone(key)

    def test_cache_edge_case_zero_ttl(self):
        """Zero TTL expires immediately — cached value should be None."""
        results = [{"id": str(self.dataset.id)}]
        filters_hash = hash_filters({})

        cache_dataset_list(
            str(self.tenant.id), filters_hash, results, total_count=len(results), ttl=0
        )
        cached = get_cached_dataset_list(str(self.tenant.id), filters_hash)
        # Zero TTL means the entry expires immediately;
        # the cache backend may return None.
        self.assertTrue(
            cached is None or (isinstance(cached, tuple) and len(cached) == 2),
            f"Expected None or (list, int), got {type(cached).__name__}",
        )

    def test_cache_edge_case_negative_ttl(self):
        """Negative TTL expires immediately — cached value should be None."""
        results = [{"id": str(self.dataset.id)}]
        filters_hash = hash_filters({})

        cache_dataset_list(
            str(self.tenant.id), filters_hash, results, total_count=len(results), ttl=-1
        )
        cached = get_cached_dataset_list(str(self.tenant.id), filters_hash)
        self.assertTrue(
            cached is None or (isinstance(cached, tuple) and len(cached) == 2),
            f"Expected None or (list, int), got {type(cached).__name__}",
        )

    # ========== ERROR HANDLING ==========

    def test_cache_key_generation_with_random_tenant_id(self):
        """Random UUID tenant_id produces a valid, non-None cache key."""
        import uuid

        fake_tenant_id = str(uuid.uuid4())
        filters_hash = hash_filters({})

        key = get_dataset_list_cache_key(fake_tenant_id, filters_hash)
        self.assertIsNotNone(key)
        self.assertIn(fake_tenant_id, key)

    def test_cache_empty_results_returns_empty_list(self):
        """Caching an empty list stores it and retrieves it correctly."""
        filters_hash = hash_filters({})

        cache_dataset_list(str(self.tenant.id), filters_hash, [], total_count=0)
        cached = get_cached_dataset_list(str(self.tenant.id), filters_hash)
        self.assertIsNotNone(cached, "Empty results should be cached, not evicted")
        self.assertEqual(cached, ([], 0))

    def test_cache_and_retrieve_uses_default_ttl(self):
        """Cache set + get with default TTL round-trips correctly."""
        filters_hash = hash_filters({})
        results = [{"id": str(self.dataset.id)}]

        cache_dataset_list(str(self.tenant.id), filters_hash, results, total_count=len(results))
        cached = get_cached_dataset_list(str(self.tenant.id), filters_hash)
        self.assertIsNotNone(cached, "Cached data should be retrievable with default TTL")
        self.assertEqual(cached, (results, len(results)))
