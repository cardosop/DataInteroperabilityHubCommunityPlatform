"""
Integration tests for Search API Views

Tests for search endpoints, suggestions, analytics, and index rebuild.
"""

import uuid
import pytest
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.search.indexing import SearchIndexer
from hub.apps.search.models import SearchAnalytics, SearchIndex
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class SearchViewSetTest(TestCase):
    """Test SearchViewSet"""

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

        self.client = APIClient()

        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", status="ACTIVE", kyc_status="VERIFIED"
        )
        ensure_tenant_has_active_subscription(self.tenant)

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

        # Index resources
        SearchIndexer.index_asset(self.asset)
        SearchIndexer.index_dataset(self.dataset)

        # Authenticate
        self.client.force_authenticate(user=self.user)

    def test_search_endpoint(self):
        """Test search endpoint"""
        url = reverse("search-search")
        response = self.client.get(url, {"q": "test"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertIn("total", response.data)
        self.assertIn("query", response.data)

    def test_search_with_filters(self):
        """Test search with filters"""
        url = reverse("search-search")
        response = self.client.get(url, {"q": "test", "type": "ASSET", "limit": 10})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for result in response.data["results"]:
            self.assertEqual(result["type"], "ASSET")

    def test_suggestions_endpoint(self):
        """Test suggestions endpoint"""
        url = reverse("search-suggestions")
        response = self.client.get(url, {"q": "test"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)

    def test_suggestions_short_query(self):
        """Test suggestions with short query"""
        url = reverse("search-suggestions")
        response = self.client.get(url, {"q": "t"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_track_click_endpoint(self):
        """Test track click endpoint"""
        # Create analytics first
        from hub.apps.search.models import SearchAnalytics
        from hub.apps.search.search_engine import SearchEngine

        analytics = SearchEngine.track_search(
            tenant_id=str(self.tenant.id), query="test", result_count=1
        )

        # Verify analytics was created and saved
        self.assertIsNotNone(analytics.id)
        # Refresh to ensure it's in the database
        analytics.refresh_from_db()

        # Verify analytics exists in database
        self.assertTrue(SearchAnalytics.objects.filter(id=analytics.id).exists())

        url = reverse("search-track-click")
        response = self.client.post(
            url,
            {
                "analytics_id": str(analytics.id),
                "result_id": str(self.asset.id),
                "result_type": "ASSET",
            },
            format="json",
        )

        # Debug: Print response if failed
        if response.status_code != status.HTTP_200_OK:
            print(f"Response status: {response.status_code}")
            print(f"Response data: {response.data if hasattr(response, 'data') else 'N/A'}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("status", response.data)
        self.assertEqual(response.data["status"], "click tracked")

        # Verify click tracked
        analytics.refresh_from_db()
        self.assertIsNotNone(analytics.clicked_at)

    # --- Edge cases and error_handling (TDD: assert status codes and response body) ---

    def test_search_without_tenant_returns_400(self):
        """Search when user has no tenant returns 400 with error message."""
        user_no_tenant = User.objects.create_user(
            email=f"notenant-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=None,
            status=UserStatus.ACTIVE,
        )
        self.client.force_authenticate(user=user_no_tenant)
        url = reverse("search-search")
        response = self.client.get(url, {"q": "test"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("tenant", response.data["error"].lower())

    def test_search_unauthenticated_returns_401(self):
        """Search without authentication returns 401."""
        self.client.force_authenticate(user=None)
        self.client.credentials()
        url = reverse("search-search")
        response = self.client.get(url, {"q": "test"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_search_limit_zero_returns_400(self):
        """Search with limit=0 returns 400."""
        url = reverse("search-search")
        response = self.client.get(url, {"q": "test", "limit": "0"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("limit", response.data["error"].lower())

    def test_search_negative_offset_clamped_returns_200(self):
        """Search with negative offset is clamped to 0 and returns 200."""
        url = reverse("search-search")
        response = self.client.get(url, {"q": "test", "offset": "-1"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertIn("offset", response.data)
        self.assertEqual(response.data["offset"], 0)

    def test_suggestions_without_tenant_returns_400(self):
        """Suggestions when user has no tenant returns 400."""
        user_no_tenant = User.objects.create_user(
            email=f"notenant2-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=None,
            status=UserStatus.ACTIVE,
        )
        self.client.force_authenticate(user=user_no_tenant)
        url = reverse("search-suggestions")
        response = self.client.get(url, {"q": "te"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("tenant", response.data["error"].lower())

    def test_track_click_missing_fields_returns_400(self):
        """Track click without analytics_id, result_id, or result_type returns 400."""
        url = reverse("search-track-click")
        response = self.client.post(url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("analytics_id", response.data["error"])

    def test_track_click_analytics_not_found_returns_400(self):
        """Track click with non-existent analytics_id returns 400 with message."""
        import uuid

        url = reverse("search-track-click")
        fake_id = uuid.uuid4()
        response = self.client.post(
            url,
            {
                "analytics_id": str(fake_id),
                "result_id": str(self.asset.id),
                "result_type": "ASSET",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("not found", response.data["error"].lower())

    def test_analytics_without_tenant_returns_error(self):
        """Analytics endpoint when user has no tenant returns 403 (no auditor role)."""
        user_no_tenant = User.objects.create_user(
            email=f"notenant3-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=None,
            status=UserStatus.ACTIVE,
        )
        self.client.force_authenticate(user=user_no_tenant)
        url = reverse("search-analytics")
        response = self.client.get(url)
        # Analytics requires IsAuditor permission; tenant-less user has no roles → 403
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_search_response_structure_tdd(self):
        """TDD: Search response contains required keys and types."""
        url = reverse("search-search")
        response = self.client.get(url, {"q": "test"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertIn("total", response.data)
        self.assertIn("limit", response.data)
        self.assertIn("offset", response.data)
        self.assertIn("query", response.data)
        self.assertIsInstance(response.data["results"], list)
        self.assertIsInstance(response.data["total"], int)
        self.assertGreaterEqual(response.data["total"], 0)

    def tearDown(self):
        """Reconnect signals after test"""
        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            post_save.connect(contract_saved, sender=Contract, weak=False)
            post_save.connect(asset_saved, sender=Asset, weak=False)
        except (ImportError, AttributeError):
            pass
