"""
Integration tests for Search API Views

Tests for search endpoints, suggestions, analytics, and index rebuild.
"""

import uuid

import pytest
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from hub.apps.assets.models import AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.search.indexing import SearchIndexer
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
            try:
                from hub.apps.semantic.signals import asset_saved, contract_saved
            except (RuntimeError, ModuleNotFoundError):
                pytest.skip("hub.apps.apps (paid layer not installed in core-only mode)")

            post_save.disconnect(contract_saved, sender=Contract)
            post_save.disconnect(asset_saved, sender=Asset)
        except (ImportError, AttributeError):
            pass

        self.client = APIClient()

        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="VERIFIED",
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

    def _assert_sunset(self, response):
        """P3-1 (sunset 2026-08-10): the deprecated /api/v1/search/
        surface 410s via APIVersionMiddleware BEFORE any view code —
        the pre-sunset behaviors (results/suggestions/track-click/
        edge-case envelopes) are dead with the surface. These tests pin
        the SUNSET contract per path; the behavioral coverage migrated
        to /api/search/ (UnifiedSearchView) — see test_fts_search.py /
        test_error_envelope.py; the remaining surface migration is
        recorded for the search owning lane."""
        self.assertEqual(response.status_code, 410, response.content)
        body = response.json()
        self.assertEqual(body.get("code"), "ENDPOINT_SUNSET", response.content)
        self.assertEqual(
            body.get("details", {}).get("replacement"), "/api/search/",
            response.content,
        )

    def test_search_endpoint_sunset(self):
        url = reverse("search-search")
        response = self.client.get(url, {"q": "test"})
        self._assert_sunset(response)

    def test_search_with_filters_sunset(self):
        url = reverse("search-search")
        response = self.client.get(url, {"q": "test", "type": "ASSET", "limit": 10})
        self._assert_sunset(response)

    def test_suggestions_endpoint_sunset(self):
        url = reverse("search-suggestions")
        response = self.client.get(url, {"q": "test"})
        self._assert_sunset(response)

    def test_suggestions_short_query_sunset(self):
        url = reverse("search-suggestions")
        response = self.client.get(url, {"q": "t"})
        self._assert_sunset(response)

    def test_track_click_endpoint_sunset(self):
        url = reverse("search-track-click")
        response = self.client.post(
            url,
            {
                "analytics_id": str(uuid.uuid4()),
                "result_id": str(self.asset.id),
                "result_type": "ASSET",
            },
            format="json",
        )
        self._assert_sunset(response)

    # --- Edge cases: the 410 fires BEFORE tenant/permission handling ---

    def test_search_without_tenant_sunset(self):
        user_no_tenant = User.objects.create_user(
            email=f"notenant-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=None,
            status=UserStatus.ACTIVE,
        )
        self.client.force_authenticate(user=user_no_tenant)
        url = reverse("search-search")
        response = self.client.get(url, {"q": "test"})
        self._assert_sunset(response)

    def test_search_unauthenticated_sunset(self):
        self.client.force_authenticate(user=None)
        self.client.credentials()
        url = reverse("search-search")
        response = self.client.get(url, {"q": "test"})
        self._assert_sunset(response)

    def test_search_limit_zero_sunset(self):
        url = reverse("search-search")
        response = self.client.get(url, {"q": "test", "limit": "0"})
        self._assert_sunset(response)

    def test_search_negative_offset_sunset(self):
        url = reverse("search-search")
        response = self.client.get(url, {"q": "test", "offset": "-1"})
        self._assert_sunset(response)

    def test_suggestions_without_tenant_sunset(self):
        user_no_tenant = User.objects.create_user(
            email=f"notenant2-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=None,
            status=UserStatus.ACTIVE,
        )
        self.client.force_authenticate(user=user_no_tenant)
        url = reverse("search-suggestions")
        response = self.client.get(url, {"q": "te"})
        self._assert_sunset(response)

    def test_track_click_missing_fields_sunset(self):
        url = reverse("search-track-click")
        response = self.client.post(url, {}, format="json")
        self._assert_sunset(response)

    def test_track_click_analytics_not_found_sunset(self):
        url = reverse("search-track-click")
        response = self.client.post(
            url,
            {
                "analytics_id": str(uuid.uuid4()),
                "result_id": str(self.asset.id),
                "result_type": "ASSET",
            },
            format="json",
        )
        self._assert_sunset(response)

    def test_analytics_sunset(self):
        url = reverse("search-analytics")
        response = self.client.get(url)
        self._assert_sunset(response)

    def test_search_response_structure_sunset(self):
        url = reverse("search-search")
        response = self.client.get(url, {"q": "test"})
        self._assert_sunset(response)

    def tearDown(self):
        """Reconnect signals after test"""
        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            try:
                from hub.apps.semantic.signals import asset_saved, contract_saved
            except (RuntimeError, ModuleNotFoundError):
                pytest.skip("hub.apps.apps (paid layer not installed in core-only mode)")

            # Default weak=True — the semantic handlers take no args;
            # weak=False passes (sender, **kwargs) → TypeError that aborts
            # post_save dispatch for every receiver after them.
            post_save.connect(contract_saved, sender=Contract)
            post_save.connect(asset_saved, sender=Asset)
        except (ImportError, AttributeError):
            pass
