"""
Phase 91.14 — Cache invalidation integration test.

Verifies: create dataset → cache set → update dataset → cache cleared → read returns fresh data.
"""
import pytest
from django.core.cache import cache
from django.test import TestCase

from hub.apps.datasets.caching import (
    cache_dataset_detail,
    get_dataset_detail_cache_key,
)
from hub.apps.datasets.models import Dataset


@pytest.mark.django_db(transaction=True)
class TestDatasetCacheInvalidation(TestCase):
    """
    End-to-end: write → cache → mutate → verify cache evicted.
    """

    def setUp(self):
        from hub.apps.tenants.models import Tenant

        self.tenant = Tenant.objects.create(
            name="cache-test-tenant",
            slug="cache-test-tenant",
        )

    def test_save_invalidates_detail_cache(self):
        """Create dataset, prime cache, update dataset, assert cache cleared."""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            format="CSV",
        )

        # Prime the cache with stale data
        cache_key = get_dataset_detail_cache_key(str(dataset.pk))
        cache.set(cache_key, {"format": "stale-value"}, timeout=300)
        self.assertIsNotNone(cache.get(cache_key), "Cache should be primed")

        # Update the dataset — post_save signal should invalidate cache
        dataset.format = "JSON"
        dataset.save()

        # Cache should now be empty
        cached = cache.get(cache_key)
        self.assertIsNone(
            cached,
            f"Cache should be invalidated after save, but got: {cached}",
        )

    def test_delete_invalidates_detail_cache(self):
        """Create dataset, prime cache, delete dataset, assert cache cleared."""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            format="JSON",
        )

        cache_key = get_dataset_detail_cache_key(str(dataset.pk))
        cache.set(cache_key, {"format": "will-be-deleted"}, timeout=300)
        self.assertIsNotNone(cache.get(cache_key))

        dataset.delete()

        cached = cache.get(cache_key)
        self.assertIsNone(
            cached,
            f"Cache should be invalidated after delete, got: {cached}",
        )

    def test_fresh_read_after_invalidation(self):
        """Full cycle: create → cache → update → read returns fresh data."""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            format="PARQUET",
        )

        # Simulate a cached read
        cache_key = get_dataset_detail_cache_key(str(dataset.pk))
        cache_dataset_detail(str(dataset.pk), {
            "id": str(dataset.pk),
            "format": "PARQUET",
        })
        self.assertIsNotNone(cache.get(cache_key))

        # Mutate
        dataset.row_count = 42
        dataset.save()

        # Cache should be invalidated
        self.assertIsNone(cache.get(cache_key))

        # Fresh DB read returns the updated value
        refreshed = Dataset.objects.get(pk=dataset.pk)
        self.assertEqual(refreshed.row_count, 42)
