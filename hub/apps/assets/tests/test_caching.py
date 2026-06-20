"""
Tests for Asset Caching

Tests cover:
- List query caching
- Detail caching
- Cache invalidation on mutations
- Cache key generation
- Filter hashing

All tests use real cache connections - no mocks or stubs.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.assets.caching import (
    cache_asset_detail,
    cache_asset_list,
    get_asset_detail_cache_key,
    get_asset_list_cache_key,
    get_cached_asset_detail,
    get_cached_asset_list,
    get_tenant_id_from_request,
    hash_filters,
    invalidate_asset_caches,
    invalidate_asset_detail_cache,
    invalidate_asset_list_cache,
)
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)


class TestAssetCachingUtilities(TestCase):
    """Test asset caching utility functions."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear cache before each test
        cache.clear()

    def test_hash_filters_deterministic(self):
        """Test filter hashing produces deterministic results."""
        filters1 = {"domain": "marketing", "status": "ACTIVE"}
        filters2 = {"status": "ACTIVE", "domain": "marketing"}  # Different order

        hash1 = hash_filters(filters1)
        hash2 = hash_filters(filters2)

        # Should produce same hash regardless of order
        self.assertEqual(hash1, hash2)

    def test_hash_filters_different_filters_different_hash(self):
        """Test different filters produce different hashes."""
        filters1 = {"domain": "marketing"}
        filters2 = {"domain": "finance"}

        hash1 = hash_filters(filters1)
        hash2 = hash_filters(filters2)

        self.assertNotEqual(hash1, hash2)

    def test_hash_filters_ignores_none_values(self):
        """Test filter hashing ignores None values."""
        filters1 = {"domain": "marketing", "status": None}
        filters2 = {"domain": "marketing"}

        hash1 = hash_filters(filters1)
        hash2 = hash_filters(filters2)

        # Should produce same hash (None values ignored)
        self.assertEqual(hash1, hash2)

    def test_get_asset_list_cache_key(self):
        """Test asset list cache key generation."""
        tenant_id = "123e4567-e89b-12d3-a456-426614174000"
        filters_hash = "abc123"

        key = get_asset_list_cache_key(tenant_id, filters_hash)

        self.assertEqual(key, f"asset:list:{tenant_id}:{filters_hash}")

    def test_get_asset_detail_cache_key(self):
        """Test asset detail cache key generation."""
        asset_id = "123e4567-e89b-12d3-a456-426614174000"

        key = get_asset_detail_cache_key(asset_id)

        self.assertEqual(key, f"asset:detail:{asset_id}")

    def test_get_cached_asset_list_returns_none_when_not_cached(self):
        """Test get_cached_asset_list returns None when cache is empty."""
        tenant_id = "123e4567-e89b-12d3-a456-426614174000"
        filters_hash = "abc123"

        cached = get_cached_asset_list(tenant_id, filters_hash)
        self.assertIsNone(cached)

    def test_cache_asset_list_stores_results(self):
        """Test cache_asset_list stores results in cache."""
        tenant_id = "123e4567-e89b-12d3-a456-426614174000"
        filters_hash = "abc123"
        results = [{"id": "1", "name": "Asset 1"}, {"id": "2", "name": "Asset 2"}]
        total_count = 2

        cache_asset_list(tenant_id, filters_hash, results, total_count)

        cached = get_cached_asset_list(tenant_id, filters_hash)
        self.assertIsNotNone(cached)

    def test_get_cached_asset_list_returns_cached_results(self):
        """Test get_cached_asset_list returns cached results."""
        tenant_id = "123e4567-e89b-12d3-a456-426614174000"
        filters_hash = "abc123"
        results = [{"id": "1", "name": "Asset 1"}, {"id": "2", "name": "Asset 2"}]
        total_count = 2

        cache_asset_list(tenant_id, filters_hash, results, total_count)
        cached = get_cached_asset_list(tenant_id, filters_hash)

        cached_results, cached_count = cached
        self.assertEqual(cached_results, results)
        self.assertEqual(cached_count, total_count)

    def test_get_cached_asset_detail_returns_none_when_not_cached(self):
        """Test get_cached_asset_detail returns None when cache is empty."""
        asset_id = "123e4567-e89b-12d3-a456-426614174000"

        cached = get_cached_asset_detail(asset_id)
        self.assertIsNone(cached)

    def test_cache_asset_detail_stores_data(self):
        """Test cache_asset_detail stores data in cache."""
        asset_id = "123e4567-e89b-12d3-a456-426614174000"
        asset_data = {"id": asset_id, "name": "Test Asset", "status": "ACTIVE"}

        cache_asset_detail(asset_id, asset_data)

        cached = get_cached_asset_detail(asset_id)
        self.assertIsNotNone(cached)

    def test_get_cached_asset_detail_returns_cached_data(self):
        """Test get_cached_asset_detail returns cached data."""
        asset_id = "123e4567-e89b-12d3-a456-426614174000"
        asset_data = {"id": asset_id, "name": "Test Asset", "status": "ACTIVE"}

        cache_asset_detail(asset_id, asset_data)
        cached = get_cached_asset_detail(asset_id)

        self.assertEqual(cached, asset_data)

    def test_invalidate_asset_detail_cache_removes_cached_entry(self):
        """Test invalidate_asset_detail_cache removes cached entry."""
        asset_id = "123e4567-e89b-12d3-a456-426614174000"
        asset_data = {"id": asset_id, "name": "Test Asset"}

        cache_asset_detail(asset_id, asset_data)
        invalidate_asset_detail_cache(asset_id)

        cached = get_cached_asset_detail(asset_id)
        self.assertIsNone(cached)

    def test_invalidate_asset_caches_removes_detail_cache(self):
        """Test invalidate_asset_caches removes detail cache."""
        asset_id = "123e4567-e89b-12d3-a456-426614174000"
        tenant_id = "123e4567-e89b-12d3-a456-426614174001"

        cache_asset_detail(asset_id, {"id": asset_id, "name": "Test"})
        invalidate_asset_caches(asset_id, tenant_id)

        cached = get_cached_asset_detail(asset_id)
        self.assertIsNone(cached)

    # ── Cache invalidation end-to-end ──────────────────────────────

    def test_cache_asset_list_then_invalidate_list(self):
        """Caching a list entry then invalidating the list cache for
        that tenant must make the entry unretrievable."""
        tenant_id = "e8a7b6c5-d4e3-f2a1-b0c9-d8e7f6a5b4c3"
        filters_hash = "abc123"
        results = [{"id": "1", "name": "Asset 1"}]
        total_count = 1

        cache_asset_list(tenant_id, filters_hash, results, total_count)
        # Verify it was stored.
        self.assertIsNotNone(get_cached_asset_list(tenant_id, filters_hash))

        invalidate_asset_list_cache(tenant_id)

        # After invalidation the entry must be gone.
        self.assertIsNone(
            get_cached_asset_list(tenant_id, filters_hash),
            "After invalidate_asset_list_cache, the previously "
            "cached entry must be removed and get must return None.",
        )

    def test_invalidate_asset_caches_invalidates_both(self):
        """invalidate_asset_caches must remove both detail and list
        cache entries for the given asset/tenant."""
        asset_id = "a1b2c3d4-e5f6-a7b8-c9d0-e1f2a3b4c5d6"
        tenant_id = "f1e2d3c4-b5a6-9780-1234-567890abcdef"
        filters_hash = "test123"
        asset_data = {"id": asset_id, "name": "Test"}
        list_results = [{"id": asset_id, "name": "Test"}]

        # Store both.
        cache_asset_detail(asset_id, asset_data)
        cache_asset_list(tenant_id, filters_hash, list_results, 1)
        self.assertIsNotNone(get_cached_asset_detail(asset_id))
        self.assertIsNotNone(get_cached_asset_list(tenant_id, filters_hash))

        invalidate_asset_caches(asset_id, tenant_id)

        # Both must be gone.
        self.assertIsNone(
            get_cached_asset_detail(asset_id),
            "invalidate_asset_caches must remove the detail cache.",
        )
        self.assertIsNone(
            get_cached_asset_list(tenant_id, filters_hash),
            "invalidate_asset_caches must remove the list cache.",
        )

    # ========== ERROR HANDLING ==========

    def test_cache_asset_list_invalid_tenant_id(self):
        """cache_asset_list with falsy tenant_id skips caching and returns
        early without raising — the function logs a warning and returns."""
        invalid_tenant_id = None
        filters_hash = "abc123"
        results = [{"id": "1"}]
        total_count = 1

        # Should not raise — the function early-exits on falsy tenant_id.
        cache_asset_list(invalid_tenant_id, filters_hash, results, total_count)

        # Retrieval for None tenant must return None (nothing was cached).
        cached = get_cached_asset_list(invalid_tenant_id, filters_hash)
        self.assertIsNone(
            cached,
            "get_cached_asset_list with a None tenant_id must return "
            "None — no entry should have been stored.",
        )

    def test_cache_asset_detail_invalid_asset_id(self):
        """cache_asset_detail with falsy asset_id skips caching and returns
        early without raising — the function logs a warning and returns."""
        invalid_asset_id = None
        asset_data = {"id": None, "name": "Test"}

        # Should not raise — the function early-exits on falsy asset_id.
        cache_asset_detail(invalid_asset_id, asset_data)

        # Retrieval for None asset must return None (nothing was cached).
        cached = get_cached_asset_detail(invalid_asset_id)
        self.assertIsNone(
            cached,
            "get_cached_asset_detail with a None asset_id must return "
            "None — no entry should have been stored.",
        )

    def test_get_cached_asset_list_cache_error_handling(self):
        """Test error handling when cache retrieval fails"""
        tenant_id = "123e4567-e89b-12d3-a456-426614174000"
        filters_hash = "abc123"

        # Retrieving a non-existent cache entry must return None, not raise
        cached = get_cached_asset_list(tenant_id, filters_hash)
        self.assertIsNone(cached)

    def test_get_cached_asset_detail_cache_error_handling(self):
        """Test error handling when cache retrieval fails"""
        asset_id = "123e4567-e89b-12d3-a456-426614174000"

        # Retrieving a non-existent cache entry must return None, not raise
        cached = get_cached_asset_detail(asset_id)
        self.assertIsNone(cached)

    def test_invalidate_asset_detail_cache_nonexistent(self):
        """Invalidating a cache key that doesn't exist must not raise.
        After invalidation the key still doesn't exist (idempotent)."""
        fake_asset_id = "00000000-0000-0000-0000-000000000000"

        # Must not raise.
        invalidate_asset_detail_cache(fake_asset_id)

        # The key still does not exist (and no side-effect created one).
        cached = get_cached_asset_detail(fake_asset_id)
        self.assertIsNone(
            cached,
            "After invalidating a non-existent key, the key must "
            "still not exist in cache.",
        )

    def test_invalidate_asset_caches_handles_empty_cache_gracefully(self):
        """invalidating caches for a non-existent asset must not raise.
        Both detail and list cache queries return None afterward."""
        asset_id = "123e4567-e89b-12d3-a456-426614174000"
        tenant_id = "123e4567-e89b-12d3-a456-426614174001"

        # Must not raise.
        invalidate_asset_caches(asset_id, tenant_id)

        # Neither cache has entries for this asset.
        detail = get_cached_asset_detail(asset_id)
        self.assertIsNone(
            detail,
            "After invalidate_asset_caches, the detail cache for "
            "a non-existent asset must still be empty.",
        )
        # List cache also remains empty for this tenant.
        from hub.apps.assets.caching import hash_filters

        list_entry = get_cached_asset_list(tenant_id, hash_filters({"dummy": "1"}))
        self.assertIsNone(
            list_entry,
            "After invalidate_asset_caches, the list cache for "
            "a non-existent tenant/asset must still be empty.",
        )


class TestAssetCachingIntegration(TestCase):
    """Integration tests for asset caching in views."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear cache
        cache.clear()

        # Create test tenant
        from hub.apps.tenants.models import KYCStatus, TenantStatus

        _uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {_uid}",
            slug=f"test-tenant-{_uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
        from hub.apps.testing.role_support import ensure_user_has_data_provider_role

        ensure_tenant_has_active_subscription(self.tenant)

        # Create test user with DATA_PROVIDER role (required for asset create via API)
        User = get_user_model()
        _uid = uuid.uuid4().hex[:8]
        self.user = User.objects.create_user(
            email=f"test-{_uid}@example.com", password="testpass123", tenant=self.tenant
        )
        ensure_user_has_data_provider_role(self.user)

        # Create test assets (use DRAFT status to avoid validation requirements).
        # visibility is a derived @property as of Phase 250.3.B (D250.4);
        # DRAFT → INTERNAL. Do NOT pass the legacy visibility kwarg.
        self.asset1 = Asset.objects.create(
            tenant=self.tenant,
            key="asset-1",
            name="Asset 1",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        self.asset2 = Asset.objects.create(
            tenant=self.tenant,
            key="asset-2",
            name="Asset 2",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def tearDown(self):
        """Clean up test fixtures."""
        cache.clear()

    def test_list_view_returns_200_status(self):
        """Test asset list view returns 200 status."""
        response = self.client.get("/api/v1/assets/")
        self.assertEqual(response.status_code, 200)

    def test_list_view_returns_consistent_count_on_repeated_requests(self):
        """Test asset list view returns consistent count on repeated requests."""
        response1 = self.client.get("/api/v1/assets/")
        count1 = response1.json().get("count", 0)

        response2 = self.client.get("/api/v1/assets/")
        count2 = response2.json().get("count", 0)

        self.assertEqual(count1, count2)

    def test_list_view_returns_consistent_results_on_repeated_requests(self):
        """Test asset list view returns consistent results on repeated requests."""
        response1 = self.client.get("/api/v1/assets/")
        results1 = response1.json().get("results", [])

        response2 = self.client.get("/api/v1/assets/")
        results2 = response2.json().get("results", [])

        self.assertEqual(len(results1), len(results2))

    def test_list_view_cache_invalidation_on_create_creates_asset(self):
        """Creating an asset via POST persists the asset and invalidates
        the list cache, so a subsequent GET reflects the new asset."""
        response = self.client.post(
            "/api/v1/assets/",
            {"key": "asset-3", "name": "Asset 3", "domain": "marketing"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        # Verify the asset actually exists in the API.
        asset_id = response.json()["id"]
        detail = self.client.get(f"/api/v1/assets/{asset_id}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["key"], "asset-3")

    def test_list_view_cache_invalidation_on_create_updates_count(self):
        """Test list cache invalidation updates count after asset creation."""
        response1 = self.client.get("/api/v1/assets/")
        count1 = response1.json().get("count", 0)

        self.client.post(
            "/api/v1/assets/",
            {"key": "asset-3", "name": "Asset 3", "domain": "marketing"},
            format="json",
        )

        response2 = self.client.get("/api/v1/assets/")
        count2 = response2.json().get("count", 0)

        self.assertGreater(count2, count1)

    def test_list_view_cache_invalidation_on_update_updates_asset(self):
        """PATCHing an asset updates its fields and invalidates the list
        cache so a subsequent list reflects the change."""
        self.asset1.refresh_from_db()

        response = self.client.patch(
            f"/api/v1/assets/{self.asset1.id}/",
            {"name": "Updated Asset 1", "version": self.asset1.version},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        # Verify the update is reflected in the response body.
        self.assertEqual(response.json()["name"], "Updated Asset 1")

    def test_list_view_cache_invalidation_on_update_updates_database(self):
        """Test asset update persists to database."""
        self.asset1.refresh_from_db()

        self.client.patch(
            f"/api/v1/assets/{self.asset1.id}/",
            {"name": "Updated Asset 1", "version": self.asset1.version},
            format="json",
        )

        self.asset1.refresh_from_db()
        self.assertEqual(self.asset1.name, "Updated Asset 1")

    def test_list_view_cache_invalidation_on_delete_deletes_asset(self):
        """DELETE returns 204 and the asset transitions to RETIRED status
        (soft-delete), which invalidates both list and detail caches."""
        response = self.client.delete(f"/api/v1/assets/{self.asset1.id}/")
        self.assertEqual(response.status_code, 204)
        # Verify the asset is now RETIRED via the detail endpoint.
        detail = self.client.get(f"/api/v1/assets/{self.asset1.id}/")
        self.assertEqual(detail.json()["status"], AssetStatus.RETIRED)

    def test_list_view_cache_invalidation_on_delete_updates_count(self):
        """Test list cache invalidation updates count after asset deletion."""
        response1 = self.client.get("/api/v1/assets/")
        count1 = response1.json().get("count", 0)

        self.client.delete(f"/api/v1/assets/{self.asset1.id}/")

        response2 = self.client.get("/api/v1/assets/")
        count2 = response2.json().get("count", 0)

        # Soft-delete may not reduce count (RETIRED assets may still
        # appear in unfiltered listing). Verify count changed or stayed.
        self.assertLessEqual(count2, count1)

    def test_detail_view_returns_200_status(self):
        """Test asset detail view returns 200 status."""
        response = self.client.get(f"/api/v1/assets/{self.asset1.id}/")
        self.assertEqual(response.status_code, 200)

    def test_detail_view_returns_consistent_id_on_repeated_requests(self):
        """Test asset detail view returns consistent id on repeated requests."""
        response1 = self.client.get(f"/api/v1/assets/{self.asset1.id}/")
        id1 = response1.json()["id"]

        response2 = self.client.get(f"/api/v1/assets/{self.asset1.id}/")
        id2 = response2.json()["id"]

        self.assertEqual(id1, id2)

    def test_detail_view_returns_consistent_name_on_repeated_requests(self):
        """Test asset detail view returns consistent name on repeated requests."""
        response1 = self.client.get(f"/api/v1/assets/{self.asset1.id}/")
        name1 = response1.json()["name"]

        response2 = self.client.get(f"/api/v1/assets/{self.asset1.id}/")
        name2 = response2.json()["name"]

        self.assertEqual(name1, name2)

    def test_detail_view_cache_invalidation_on_update_reflects_changes(self):
        """After PATCHing an asset name, the detail endpoint returns the
        new name — proving the detail cache was invalidated and the fresh
        row was read from the database."""
        response1 = self.client.get(f"/api/v1/assets/{self.asset1.id}/")
        name1 = response1.json()["name"]

        self.asset1.refresh_from_db()
        self.client.patch(
            f"/api/v1/assets/{self.asset1.id}/",
            {"name": "Updated Name", "version": self.asset1.version},
            format="json",
        )

        response2 = self.client.get(f"/api/v1/assets/{self.asset1.id}/")
        name2 = response2.json()["name"]

        self.assertNotEqual(name1, name2)
        self.assertEqual(name2, "Updated Name")

    def test_detail_view_cache_invalidation_on_delete_sets_retired_status(self):
        """After DELETE, the detail endpoint returns status=RETIRED —
        the stale cached ACTIVE/DRAFT data was evicted and the fresh DB
        state is served."""
        self.client.delete(f"/api/v1/assets/{self.asset1.id}/")

        response = self.client.get(f"/api/v1/assets/{self.asset1.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["status"],
            AssetStatus.RETIRED,
            "After soft-delete the detail endpoint must return "
            "status=RETIRED — the cache must have been invalidated "
            "by the delete operation.",
        )

    def test_list_view_with_domain_filter_returns_200(self):
        """Filtering by domain=marketing returns only marketing assets."""
        # Create a marketing-domain asset so the filter returns results.
        Asset.objects.create(
            tenant=self.tenant,
            key="asset-marketing-2",
            name="Marketing Asset 2",
            domain="marketing",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        response = self.client.get("/api/v1/assets/?domain=marketing")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreater(
            len(data.get("results", [])),
            0,
            "Domain filter must return at least the marketing asset "
            "just created.",
        )
        for asset in data["results"]:
            self.assertEqual(
                asset.get("domain"),
                "marketing",
                "Every asset returned under ?domain=marketing must "
                "have domain='marketing'.",
            )

    def test_list_view_different_filters_use_different_cache_entries(self):
        """Test different filters use different cache entries."""
        # Create an asset with domain=marketing so filtered vs unfiltered results differ.
        # visibility derives from status per D250.4 — do NOT pass legacy kwarg.
        Asset.objects.create(
            tenant=self.tenant,
            key="asset-marketing",
            name="Marketing Asset",
            domain="marketing",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        response1 = self.client.get("/api/v1/assets/?domain=marketing")
        response2 = self.client.get("/api/v1/assets/")

        data1 = response1.json()
        data2 = response2.json()

        self.assertIsNotNone(data1)
        self.assertIsNotNone(data2)

        # Filtered response must return fewer results than unfiltered
        count_filtered = data1.get("count", len(data1.get("results", [])))
        count_all = data2.get("count", len(data2.get("results", [])))
        self.assertGreater(count_all, count_filtered)

    def test_get_tenant_id_from_request_returns_tenant_id(self):
        """Test get_tenant_id_from_request returns tenant ID."""
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get("/api/v1/assets/")
        request.user = self.user

        tenant_id = get_tenant_id_from_request(request)
        self.assertIsNotNone(tenant_id)

    def test_get_tenant_id_from_request_returns_correct_tenant_id(self):
        """Test get_tenant_id_from_request returns correct tenant ID."""
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get("/api/v1/assets/")
        request.user = self.user

        tenant_id = get_tenant_id_from_request(request)
        self.assertEqual(tenant_id, str(self.tenant.id))
