"""
Unit tests for Search Engine

Tests for full-text search, ranking, suggestions, and analytics.
"""
import pytest
from django.test import TestCase
from django.utils import timezone

from hub.apps.search.models import SearchIndex, SearchAnalytics
from hub.apps.search.search_engine import SearchEngine
from hub.apps.search.indexing import SearchIndexer
from hub.apps.contracts.models import Contract
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus


pytestmark = pytest.mark.django_db(transaction=True)


class SearchEngineTest(TestCase):
    """Test SearchEngine"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            description="Test asset description",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )
        
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1000,
            status=FileStatus.ACTIVE,
            storage_path="test/test.csv",
            content_sha256="abc123",
            created_by=self.user
        )
        
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            name="Test Dataset",
            description="Test dataset description",
            schema_json={
                "fields": [
                    {"name": "email", "type": "string"}
                ]
            },
            format="CSV",
            version=1,
            created_by=self.user
        )
        
        # Index resources
        SearchIndexer.index_asset(self.asset)
        SearchIndexer.index_dataset(self.dataset)
    
    def test_search_basic(self):
        """Test basic search"""
        results, total = SearchEngine.search(
            tenant_id=str(self.tenant.id),
            query="test"
        )
        
        self.assertGreater(total, 0)
        self.assertGreater(len(results), 0)
    
    def test_search_with_filters(self):
        """Test search with filters"""
        results, total = SearchEngine.search(
            tenant_id=str(self.tenant.id),
            query="test",
            resource_type="ASSET"
        )
        
        self.assertGreater(total, 0)
        for result in results:
            self.assertEqual(result["type"], "ASSET")
    
    def test_search_pagination(self):
        """Test search pagination"""
        results_page1, total = SearchEngine.search(
            tenant_id=str(self.tenant.id),
            query="test",
            limit=1,
            offset=0
        )
        
        results_page2, _ = SearchEngine.search(
            tenant_id=str(self.tenant.id),
            query="test",
            limit=1,
            offset=1
        )
        
        self.assertEqual(len(results_page1), 1)
        self.assertEqual(len(results_page2), 1)
        self.assertNotEqual(results_page1[0]["id"], results_page2[0]["id"])
    
    def test_search_sorting(self):
        """Test search sorting"""
        results, total = SearchEngine.search(
            tenant_id=str(self.tenant.id),
            query="test",
            sort_by="indexed_at",
            sort_order="desc"
        )
        
        self.assertGreater(len(results), 0)
        # Results should be sorted by indexed_at descending
    
    def test_get_suggestions(self):
        """Test search suggestions"""
        suggestions = SearchEngine.get_suggestions(
            tenant_id=str(self.tenant.id),
            query="test"
        )
        
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
            user_id=str(self.user.id)
        )
        
        self.assertIsNotNone(analytics)
        self.assertEqual(analytics.query, "test query")
        self.assertEqual(analytics.result_count, 5)
        self.assertEqual(analytics.user_id, self.user.id)
    
    def test_track_click(self):
        """Test tracking click"""
        # Create analytics
        analytics = SearchEngine.track_search(
            tenant_id=str(self.tenant.id),
            query="test",
            result_count=1
        )
        
        # Track click
        SearchEngine.track_click(
            analytics_id=str(analytics.id),
            result_id=str(self.asset.id),
            result_type="ASSET"
        )
        
        # Verify click tracked
        analytics.refresh_from_db()
        self.assertEqual(str(analytics.clicked_result_id), str(self.asset.id))
        self.assertEqual(analytics.clicked_result_type, "ASSET")
        self.assertIsNotNone(analytics.clicked_at)

