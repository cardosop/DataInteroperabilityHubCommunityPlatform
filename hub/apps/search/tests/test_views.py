"""
Integration tests for Search API Views

Tests for search endpoints, suggestions, analytics, and index rebuild.
"""
import pytest
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.search.models import SearchIndex, SearchAnalytics
from hub.apps.search.indexing import SearchIndexer
from hub.apps.contracts.models import Contract
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus


pytestmark = pytest.mark.django_db(transaction=True)


class SearchViewSetTest(TestCase):
    """Test SearchViewSet"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        
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
            schema_json={"fields": [{"name": "email", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user
        )
        
        # Index resources
        SearchIndexer.index_asset(self.asset)
        SearchIndexer.index_dataset(self.dataset)
        
        # Authenticate
        self.client.force_authenticate(user=self.user)
    
    def test_search_endpoint(self):
        """Test search endpoint"""
        url = reverse('search-search')
        response = self.client.get(url, {'q': 'test'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('total', response.data)
        self.assertIn('query', response.data)
    
    def test_search_with_filters(self):
        """Test search with filters"""
        url = reverse('search-search')
        response = self.client.get(url, {
            'q': 'test',
            'type': 'ASSET',
            'limit': 10
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for result in response.data['results']:
            self.assertEqual(result['type'], 'ASSET')
    
    def test_suggestions_endpoint(self):
        """Test suggestions endpoint"""
        url = reverse('search-suggestions')
        response = self.client.get(url, {'q': 'test'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
    
    def test_suggestions_short_query(self):
        """Test suggestions with short query"""
        url = reverse('search-suggestions')
        response = self.client.get(url, {'q': 't'})
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_track_click_endpoint(self):
        """Test track click endpoint"""
        # Create analytics first
        from hub.apps.search.search_engine import SearchEngine
        analytics = SearchEngine.track_search(
            tenant_id=str(self.tenant.id),
            query="test",
            result_count=1
        )
        
        url = reverse('search-track-click')
        response = self.client.post(url, {
            'analytics_id': str(analytics.id),
            'result_id': str(self.asset.id),
            'result_type': 'ASSET'
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify click tracked
        analytics.refresh_from_db()
        self.assertIsNotNone(analytics.clicked_at)

