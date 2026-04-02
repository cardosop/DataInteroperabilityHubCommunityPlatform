"""
Integration tests for Asset Popularity Metrics

Tests for popularity tracking in the context of asset workflows.
"""
import uuid

from datetime import timedelta

import pytest
from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.assets.popularity import AssetPopularityService
from hub.apps.search.models import SearchAnalytics
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class AssetPopularityIntegrationTest(TestCase):
    """Integration tests for asset popularity"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", status="ACTIVE", kyc_status="UNVERIFIED"
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
            status=AssetStatus.ACTIVE,
            view_count=0,
            download_count=0,
            created_by=self.user,
        )

    def test_popularity_tracking_workflow_tracks_views(self):
        """Test complete popularity tracking workflow tracks views."""
        for _ in range(5):
            AssetPopularityService.track_view(str(self.asset.id), str(self.tenant.id))

        self.asset.refresh_from_db()
        self.assertEqual(self.asset.view_count, 5)

    def test_popularity_tracking_workflow_updates_popularity_score(self):
        """Test complete popularity tracking workflow updates popularity score."""
        for _ in range(5):
            AssetPopularityService.track_view(str(self.asset.id), str(self.tenant.id))

        self.asset.refresh_from_db()
        self.assertIsNotNone(self.asset.popularity_score)

    def test_popularity_tracking_workflow_tracks_downloads(self):
        """Test complete popularity tracking workflow tracks downloads."""
        for _ in range(5):
            AssetPopularityService.track_view(str(self.asset.id), str(self.tenant.id))

        for _ in range(3):
            AssetPopularityService.track_download(str(self.asset.id), str(self.tenant.id))

        self.asset.refresh_from_db()
        self.assertEqual(self.asset.download_count, 3)

    def test_popularity_tracking_workflow_calculates_final_score(self):
        """Test complete popularity tracking workflow calculates final score."""
        for _ in range(5):
            AssetPopularityService.track_view(str(self.asset.id), str(self.tenant.id))

        for _ in range(3):
            AssetPopularityService.track_download(str(self.asset.id), str(self.tenant.id))

        final_score = AssetPopularityService.calculate_popularity_score(self.asset)
        self.assertGreater(final_score, 0.0)

    # ========== SUCCESS SCENARIOS ==========

    def test_popularity_integration_success_increments_view_count(self):
        """Test successful popularity tracking integration increments view count."""
        AssetPopularityService.track_view(str(self.asset.id), str(self.tenant.id))

        self.asset.refresh_from_db()
        self.assertEqual(self.asset.view_count, 1)

    def test_popularity_integration_success_updates_popularity_score(self):
        """Test successful popularity tracking integration updates popularity score."""
        AssetPopularityService.track_view(str(self.asset.id), str(self.tenant.id))

        self.asset.refresh_from_db()
        self.assertIsNotNone(self.asset.popularity_score)

    # ========== FAILURE SCENARIOS ==========

    def test_popularity_integration_failure_nonexistent_asset(self):
        """Test popularity tracking with non-existent asset does not raise.

        The track_view function handles DoesNotExist internally, so calling it
        with a non-existent asset ID should not propagate an exception.
        """
        fake_asset_id = str(uuid.uuid4())

        # Should not raise -- the service handles missing assets internally
        AssetPopularityService.track_view(fake_asset_id, str(self.tenant.id))

    # ========== EDGE CASES ==========

    def test_popularity_integration_edge_case_rapid_tracking_increments_count(self):
        """Test rapid popularity tracking increments view count correctly."""
        for _ in range(100):
            AssetPopularityService.track_view(str(self.asset.id), str(self.tenant.id))

        self.asset.refresh_from_db()
        self.assertEqual(self.asset.view_count, 100)

    def test_popularity_integration_edge_case_rapid_tracking_updates_score(self):
        """Test rapid popularity tracking updates popularity score."""
        for _ in range(100):
            AssetPopularityService.track_view(str(self.asset.id), str(self.tenant.id))

        self.asset.refresh_from_db()
        self.assertIsNotNone(self.asset.popularity_score)

    def test_popularity_integration_edge_case_zero_initial_counts_tracks_view(self):
        """Test popularity tracking with zero initial counts tracks view."""
        AssetPopularityService.track_view(str(self.asset.id), str(self.tenant.id))
        AssetPopularityService.track_download(str(self.asset.id), str(self.tenant.id))

        self.asset.refresh_from_db()
        self.assertEqual(self.asset.view_count, 1)

    def test_popularity_integration_edge_case_zero_initial_counts_tracks_download(self):
        """Test popularity tracking with zero initial counts tracks download."""
        AssetPopularityService.track_view(str(self.asset.id), str(self.tenant.id))
        AssetPopularityService.track_download(str(self.asset.id), str(self.tenant.id))

        self.asset.refresh_from_db()
        self.assertEqual(self.asset.download_count, 1)

    # ========== ERROR HANDLING ==========

    def test_popularity_integration_valid_tracking_succeeds(self):
        """Valid popularity tracking succeeds without error."""
        AssetPopularityService.track_view(
            str(self.asset.id), str(self.tenant.id),
        )
        self.asset.refresh_from_db()
        self.assertGreaterEqual(self.asset.view_count, 1)
