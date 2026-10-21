"""
Unit tests for Search Engine

Tests for full-text search, ranking, suggestions, and analytics.
"""

import uuid

import pytest
from django.test import TestCase

from hub.apps.assets.models import AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.search.indexing import SearchIndexer
from hub.apps.search.models import SearchAnalytics
from hub.apps.search.search_engine import SearchEngine
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class SearchEngineTest(TestCase):
    """Test SearchEngine"""

    def setUp(self):
        """Set up test fixtures"""
        # CRITICAL: Disconnect semantic service signals to prevent timeouts
        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            post_save.disconnect(contract_saved, sender=Contract)
            post_save.disconnect(asset_saved, sender=Asset)
        except (ImportError, AttributeError):
            pass

        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            description="Test asset description",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1000,
            status=FileStatus.ACTIVE,
            storage_path="test/test.csv",
            content_sha256="abc123",
            created_by=self.user,
        )

        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "email", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user,
        )

        # Second asset to ensure pagination tests have 2+ results
        self.asset2 = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset-2",
            name="Test Report Asset",
            description="Another test asset for pagination",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        # Index resources
        SearchIndexer.index_asset(self.asset)
        SearchIndexer.index_asset(self.asset2)
        SearchIndexer.index_dataset(self.dataset)

    def test_search_basic(self):
        """Test basic search"""
        results, total = SearchEngine.search(tenant_id=str(self.tenant.id), query="test")

        self.assertGreater(total, 0)
        self.assertGreater(len(results), 0)

    def test_search_with_filters(self):
        """Test search with filters"""
        results, total = SearchEngine.search(
            tenant_id=str(self.tenant.id), query="test", resource_type="ASSET"
        )

        self.assertGreater(total, 0)
        for result in results:
            self.assertEqual(result["type"], "ASSET")

    def test_search_pagination(self):
        """Test search pagination"""
        _all_results, total = SearchEngine.search(
            tenant_id=str(self.tenant.id), query="test", limit=100, offset=0
        )
        self.assertGreaterEqual(total, 2, "setUp must create 2+ searchable resources")

        results_page1, total = SearchEngine.search(
            tenant_id=str(self.tenant.id), query="test", limit=1, offset=0
        )

        results_page2, _ = SearchEngine.search(
            tenant_id=str(self.tenant.id), query="test", limit=1, offset=1
        )

        self.assertEqual(len(results_page1), 1)
        # Page 2 should have results if total >= 2
        if total >= 2:
            self.assertGreater(
                len(results_page2),
                0,
                "Page 2 should have results when total >= 2",
            )
            self.assertNotEqual(
                results_page1[0]["id"],
                results_page2[0]["id"],
                "Pages should return different results",
            )

    def test_search_sorting(self):
        """Test search sorting"""
        results, _total = SearchEngine.search(
            tenant_id=str(self.tenant.id), query="test", sort_by="indexed_at", sort_order="desc"
        )

        self.assertGreater(len(results), 0)
        # Verify descending order by indexed_at
        if len(results) >= 2:
            for i in range(len(results) - 1):
                self.assertGreaterEqual(
                    results[i].get("indexed_at", ""),
                    results[i + 1].get("indexed_at", ""),
                    "Results should be sorted by indexed_at desc",
                )

    def test_get_suggestions(self):
        """Test search suggestions"""
        suggestions = SearchEngine.get_suggestions(tenant_id=str(self.tenant.id), query="test")

        self.assertIsInstance(suggestions, list)
        if suggestions:
            self.assertIn("text", suggestions[0])
            self.assertIn("type", suggestions[0])

    def test_track_search(self):
        """Test tracking search"""
        analytics = SearchEngine.track_search(
            tenant_id=str(self.tenant.id),
            query="test query",
            result_count=5,
            user_id=str(self.user.id),
        )

        self.assertIsNotNone(analytics)
        self.assertEqual(analytics.query, "test query")
        self.assertEqual(analytics.result_count, 5)
        # user_id might be stored as string, compare as strings
        self.assertEqual(str(analytics.user_id), str(self.user.id))

    def test_track_click(self):
        """Test tracking click"""
        # Create analytics
        analytics = SearchEngine.track_search(
            tenant_id=str(self.tenant.id), query="test", result_count=1
        )

        # Track click
        SearchEngine.track_click(
            analytics_id=str(analytics.id), result_id=str(self.asset.id), result_type="ASSET"
        )

        # Verify click tracked
        analytics.refresh_from_db()
        self.assertEqual(str(analytics.clicked_result_id), str(self.asset.id))
        self.assertEqual(analytics.clicked_result_type, "ASSET")
        self.assertIsNotNone(analytics.clicked_at)

    # --- Success: explicit result structure (TDD) ---

    def test_search_result_structure_success(self):
        """TDD: Search returns results with required keys and types."""
        results, total = SearchEngine.search(tenant_id=str(self.tenant.id), query="test", limit=5)
        self.assertIsInstance(results, list)
        self.assertIsInstance(total, int)
        self.assertGreaterEqual(total, 0)
        for item in results:
            self.assertIn("id", item)
            self.assertIn("type", item)
            self.assertIn("title", item)
            self.assertIn("description", item)
            self.assertIn("relevance_score", item)
            self.assertIn("classification", item)
            self.assertIn("indexed_at", item)
            self.assertIsInstance(item["tags"], list)

    # --- Failure and error_handling ---

    def test_track_click_analytics_not_found_raises(self):
        """track_click with non-existent analytics_id raises SearchAnalytics.DoesNotExist."""
        import uuid

        fake_id = uuid.uuid4()
        self.assertFalse(SearchAnalytics.objects.filter(id=fake_id).exists())
        with self.assertRaises(SearchAnalytics.DoesNotExist):
            SearchEngine.track_click(
                analytics_id=str(fake_id),
                result_id=str(self.asset.id),
                result_type="ASSET",
            )

    # --- Edge cases ---

    def test_search_empty_query_returns_filtered_results(self):
        """Empty query returns filtered list (filter_only) and total count."""
        results, total = SearchEngine.search(
            tenant_id=str(self.tenant.id), query="", limit=10, offset=0
        )
        self.assertIsInstance(results, list)
        self.assertIsInstance(total, int)
        self.assertGreaterEqual(total, 0)

    def test_search_limit_capped_at_100(self):
        """Search with limit > 100 returns at most 100 results."""
        results, total = SearchEngine.search(
            tenant_id=str(self.tenant.id), query="test", limit=500, offset=0
        )
        self.assertLessEqual(len(results), 100)
        self.assertIsInstance(total, int)

    def test_get_suggestions_short_query_returns_empty(self):
        """get_suggestions with query length < 2 returns empty list."""
        suggestions = SearchEngine.get_suggestions(
            tenant_id=str(self.tenant.id), query="t", limit=10
        )
        self.assertEqual(suggestions, [])

    def test_get_suggestions_empty_query_returns_empty(self):
        """get_suggestions with empty query returns empty list."""
        suggestions = SearchEngine.get_suggestions(
            tenant_id=str(self.tenant.id), query="", limit=10
        )
        self.assertEqual(suggestions, [])

    def test_track_search_persists_analytics_tdd(self):
        """TDD: track_search creates SearchAnalytics with correct fields."""
        analytics = SearchEngine.track_search(
            tenant_id=str(self.tenant.id),
            query="tdd query",
            query_type="SEARCH",
            result_count=0,
            user_id=str(self.user.id),
        )
        self.assertIsNotNone(analytics.id)
        self.assertEqual(analytics.query, "tdd query")
        self.assertEqual(analytics.result_count, 0)
        self.assertTrue(analytics.no_results)
        self.assertEqual(str(analytics.tenant_id), str(self.tenant.id))
