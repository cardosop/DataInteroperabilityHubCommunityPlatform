"""
Integration tests for Asset Popularity Metrics

Tests for popularity tracking in the context of asset workflows.
"""

import uuid

import pytest
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.assets.popularity import AssetPopularityService
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class AssetPopularityIntegrationTest(TestCase):
    """Integration tests for asset popularity"""

    def setUp(self):
        """Set up test fixtures"""
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
        """Complete popularity tracking workflow updates popularity score
        to a value in the valid [0, 100] range."""
        for _ in range(5):
            AssetPopularityService.track_view(str(self.asset.id), str(self.tenant.id))

        self.asset.refresh_from_db()
        self.assertIsNotNone(self.asset.popularity_score)
        self.assertGreaterEqual(self.asset.popularity_score, 0.0)
        self.assertLessEqual(self.asset.popularity_score, 100.0)

    def test_popularity_tracking_workflow_tracks_downloads(self):
        """Complete popularity tracking workflow tracks downloads
        independently from views."""
        for _ in range(3):
            AssetPopularityService.track_download(str(self.asset.id), str(self.tenant.id))

        self.asset.refresh_from_db()
        self.assertEqual(self.asset.download_count, 3)
        # View count must remain at initial value (0) — downloads do
        # not increment views.
        self.assertEqual(self.asset.view_count, 0)

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
        """Successful popularity tracking integration updates popularity score
        to a value in the valid [0, 100] range."""
        AssetPopularityService.track_view(str(self.asset.id), str(self.tenant.id))

        self.asset.refresh_from_db()
        self.assertIsNotNone(self.asset.popularity_score)
        self.assertGreaterEqual(self.asset.popularity_score, 0.0)
        self.assertLessEqual(self.asset.popularity_score, 100.0)

    # ========== FAILURE SCENARIOS ==========

    def test_popularity_integration_failure_nonexistent_asset(self):
        """Test popularity tracking with non-existent asset does not raise.

        The track_view function handles DoesNotExist internally, so calling it
        with a non-existent asset ID should not propagate an exception and must
        not modify any existing asset's counters.
        """
        fake_asset_id = str(uuid.uuid4())
        original_count = self.asset.view_count

        # Should not raise -- the service handles missing assets internally
        AssetPopularityService.track_view(fake_asset_id, str(self.tenant.id))

        # Existing asset must be untouched
        self.asset.refresh_from_db()
        self.assertEqual(
            self.asset.view_count,
            original_count,
            "track_view with a non-existent asset_id must not alter "
            "the view_count of an existing asset.",
        )
        # No new asset must have been created
        self.assertFalse(
            Asset.objects.filter(id=fake_asset_id).exists(),
            "track_view must not create a spurious Asset row for "
            "a non-existent asset_id.",
        )

    # ========== EDGE CASES ==========

    def test_popularity_integration_edge_case_rapid_tracking_increments_count(self):
        """Test rapid popularity tracking increments view count correctly."""
        for _ in range(100):
            AssetPopularityService.track_view(str(self.asset.id), str(self.tenant.id))

        self.asset.refresh_from_db()
        self.assertEqual(self.asset.view_count, 100)

    def test_popularity_integration_edge_case_rapid_tracking_updates_score(self):
        """Rapid popularity tracking updates popularity score to a valid
        value in the [0, 100] range."""
        for _ in range(100):
            AssetPopularityService.track_view(str(self.asset.id), str(self.tenant.id))

        self.asset.refresh_from_db()
        self.assertIsNotNone(self.asset.popularity_score)
        self.assertGreaterEqual(self.asset.popularity_score, 0.0)
        self.assertLessEqual(self.asset.popularity_score, 100.0)

    def test_popularity_integration_edge_case_zero_initial_counts(self):
        """Test popularity tracking with zero initial counts tracks both
        view and download accurately."""
        AssetPopularityService.track_view(str(self.asset.id), str(self.tenant.id))
        AssetPopularityService.track_download(str(self.asset.id), str(self.tenant.id))

        self.asset.refresh_from_db()
        self.assertEqual(self.asset.view_count, 1)
        self.assertEqual(self.asset.download_count, 1)

    # ========== ERROR HANDLING ==========

    def test_popularity_integration_valid_tracking_succeeds(self):
        """Valid popularity tracking increments view_count by exactly 1."""
        AssetPopularityService.track_view(
            str(self.asset.id),
            str(self.tenant.id),
        )
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.view_count, 1)
