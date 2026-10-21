"""
Tests for Cache Warming Utilities

Tests cover:
- Asset list cache warming
- Contract list cache warming
- Marketplace listings cache warming
- Tenant cache warming
- All tenants cache warming

All tests use real cache connections - no mocks or stubs.
"""

import uuid

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus, AssetVisibility
from hub.apps.core.caching.warming import (
    warm_all_tenants_cache,
    warm_asset_list_cache,
    warm_contract_list_cache,
    warm_marketplace_listings_cache,
    warm_tenant_cache,
)
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus


def _uid():
    return uuid.uuid4().hex[:8]


class TestCacheWarmingUtilities(TestCase):
    """Test cache warming utility functions."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear cache before each test
        cache.clear()

        # Create test tenant
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {_uid()}",
            slug=f"test-tenant-{_uid()}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )

        # Create test user
        User = get_user_model()
        self.user = User.objects.create_user(
            email=f"test-{_uid()}@example.com", password="testpass123", tenant=self.tenant
        )

        # Create test assets
        self.asset1 = Asset.objects.create(
            tenant=self.tenant,
            key="asset-1",
            name="Asset 1",
            status=AssetStatus.ACTIVE,
            visibility=AssetVisibility.INTERNAL,
            created_by=self.user,
        )

        self.asset2 = Asset.objects.create(
            tenant=self.tenant,
            key="asset-2",
            name="Asset 2",
            status=AssetStatus.DRAFT,
            visibility=AssetVisibility.INTERNAL,
            created_by=self.user,
        )

    def tearDown(self):
        """Clean up test fixtures."""
        cache.clear()

    def test_warm_asset_list_cache(self):
        """Test warming asset list cache."""
        tenant_id = str(self.tenant.id)

        # Warm cache
        count = warm_asset_list_cache(tenant_id)

        # Should have warmed at least one cache entry
        self.assertGreater(count, 0)

    def test_warm_asset_list_cache_with_filters(self):
        """Test warming asset list cache with specific filters."""
        tenant_id = str(self.tenant.id)
        filters = [{"status": "ACTIVE"}]

        # Warm cache
        count = warm_asset_list_cache(tenant_id, common_filters=filters)

        # Should have warmed cache entry
        self.assertEqual(count, 1)

    def test_warm_contract_list_cache(self):
        """Test warming contract list cache."""
        tenant_id = str(self.tenant.id)

        # Warm cache (may return 0 if no contracts exist)
        count = warm_contract_list_cache(tenant_id)

        # Should not raise exception
        self.assertIsInstance(count, int)
        self.assertGreaterEqual(count, 0)

    def test_warm_marketplace_listings_cache(self):
        """Test warming marketplace listings cache."""
        # Warm cache (may return 0 if no listings exist)
        count = warm_marketplace_listings_cache()

        # Should not raise exception
        self.assertIsInstance(count, int)
        self.assertGreaterEqual(count, 0)

    def test_warm_tenant_cache(self):
        """Test warming all caches for a tenant."""
        tenant_id = str(self.tenant.id)

        # Warm cache
        results = warm_tenant_cache(tenant_id)

        # Should return results dictionary
        self.assertIsInstance(results, dict)
        self.assertIn("assets", results)
        self.assertIn("contracts", results)
        self.assertIn("marketplace", results)
        self.assertGreaterEqual(results["assets"], 0)
        self.assertGreaterEqual(results["contracts"], 0)
        self.assertGreaterEqual(results["marketplace"], 0)

    def test_warm_all_tenants_cache(self):
        """Test warming cache for all tenants (capped at 5 for test speed).

        With ``--reuse-db`` the test database accumulates thousands of
        tenants from prior runs, making a full scan impractical under
        the 300 s timeout.  The ``max_tenants`` parameter caps warming
        to a representative subset.
        """
        summary = warm_all_tenants_cache(max_tenants=5)

        # Should return summary dictionary
        self.assertIsInstance(summary, dict)
        self.assertIn("total_tenants", summary)
        self.assertIn("successful", summary)
        self.assertIn("failed", summary)
        self.assertIn("results_by_tenant", summary)
        self.assertGreaterEqual(summary["total_tenants"], 1)
        self.assertGreaterEqual(summary["successful"], 0)
        self.assertGreaterEqual(summary["failed"], 0)
