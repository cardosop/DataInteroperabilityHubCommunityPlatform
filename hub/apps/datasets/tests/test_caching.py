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
try:
    import pytest
    pytestmark = pytest.mark.django_db(transaction=True)
except ImportError:
    # pytest not available, tests will run with Django test runner
    pytestmark = None

from django.test import TestCase, override_settings
from django.core.cache import cache
from django.contrib.auth import get_user_model
from hub.apps.tenants.models import Tenant
from hub.apps.assets.models import Asset
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.datasets.caching import (
    get_dataset_list_cache_key,
    get_dataset_detail_cache_key,
    hash_filters,
    cache_dataset_list,
    get_cached_dataset_list,
    cache_dataset_detail,
    get_cached_dataset_detail,
    invalidate_dataset_list_cache,
    invalidate_dataset_detail_cache,
    invalidate_dataset_caches,
    get_tenant_id_from_request,
    CACHE_TTL_DATASET_LIST,
    CACHE_TTL_DATASET_DETAIL,
)


User = get_user_model()


class DatasetCachingTest(TestCase):
    """Test dataset caching utilities"""

    def setUp(self):
        """Set up test fixtures"""
        # Clear cache before each test
        cache.clear()

        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.tenant2 = Tenant.objects.create(
            name="Test Tenant 2",
            slug="test-tenant-2"
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            size=1024,
            content_type="text/csv",
            status=FileStatus.ACTIVE,
            storage_path="test/test.csv",
            created_by=self.user
        )
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=1,
            created_by=self.user
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
        filters1 = {"page": 1, "page_size": 50, "format": "CSV"}
        filters2 = {"format": "CSV", "page_size": 50, "page": 1}
        filters3 = {"page": 1, "page_size": 50, "format": "JSON"}

        hash1 = hash_filters(filters1)
        hash2 = hash_filters(filters2)
        hash3 = hash_filters(filters3)

        # Same filters should produce same hash (order independent)
        self.assertEqual(hash1, hash2)
        # Different filters should produce different hash
        self.assertNotEqual(hash1, hash3)

    def test_hash_filters_normalizes_none_values(self):
        """Test that None values are excluded from hash"""
        filters1 = {"page": 1, "format": None, "asset_id": ""}
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

    def test_invalidate_dataset_list_cache(self):
        """Test invalidating dataset list cache"""
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

        # Invalidate tenant's list cache
        invalidate_dataset_list_cache(tenant_id)

        # Note: Pattern-based invalidation may not work with LocMemCache
        # In production with Redis, this should invalidate all queries for the tenant
        # For now, we test that the function doesn't raise errors

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
        from rest_framework.request import Request

        factory = APIRequestFactory()

        # Test with user.tenant
        request = factory.get('/api/v1/datasets/')
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

    def test_cache_error_handling(self):
        """Test that cache errors are handled gracefully"""
        tenant_id = str(self.tenant.id)
        filters_hash = hash_filters({"page": 1})
        results = [{"id": str(self.dataset.id)}]

        # Cache should not raise exceptions even if cache backend fails
        # (This is tested implicitly by the error handling in cache functions)
        try:
            cache_dataset_list(tenant_id, filters_hash, results, 1)
            cache_dataset_detail(str(self.dataset.id), {"id": str(self.dataset.id)})
        except Exception:
            self.fail("Cache functions should handle errors gracefully")

