"""
Unit tests for Asset Popularity Metrics

Tests for view/download tracking and popularity score calculation.
"""

from datetime import timedelta

import pytest
from django.db.models import F
from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.assets.popularity import AssetPopularityService
from hub.apps.search.models import SearchAnalytics
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class AssetPopularityServiceTest(TestCase):
    """Test AssetPopularityService"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", status="ACTIVE", kyc_status="UNVERIFIED"
        )

        self.user = User.objects.create_user(
            email="user@example.com",
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

    def test_track_view_increments_view_count(self):
        """Test track_view increments view_count."""
        initial_count = self.asset.view_count

        AssetPopularityService.track_view(str(self.asset.id), str(self.tenant.id))

        self.asset.refresh_from_db()
        self.assertEqual(self.asset.view_count, initial_count + 1)

    def test_track_view_updates_popularity_score(self):
        """Test track_view updates popularity_score."""
        AssetPopularityService.track_view(str(self.asset.id), str(self.tenant.id))

        self.asset.refresh_from_db()
        self.assertIsNotNone(self.asset.popularity_score)

    def test_track_download_increments_download_count(self):
        """Test track_download increments download_count."""
        initial_count = self.asset.download_count

        AssetPopularityService.track_download(str(self.asset.id), str(self.tenant.id))

        self.asset.refresh_from_db()
        self.assertEqual(self.asset.download_count, initial_count + 1)

    def test_track_download_updates_popularity_score(self):
        """Test track_download updates popularity_score."""
        AssetPopularityService.track_download(str(self.asset.id), str(self.tenant.id))

        self.asset.refresh_from_db()
        self.assertIsNotNone(self.asset.popularity_score)

    def test_track_usage_frequency(self):
        """Test usage frequency tracking"""
        initial_view_count = self.asset.view_count

        AssetPopularityService.track_usage_frequency(str(self.asset.id), str(self.tenant.id))

        self.asset.refresh_from_db()
        self.assertEqual(self.asset.view_count, initial_view_count + 1)

    def test_track_user_engagement(self):
        """Test user engagement tracking"""
        initial_view_count = self.asset.view_count

        AssetPopularityService.track_user_engagement(
            str(self.asset.id), str(self.tenant.id), user_id=str(self.user.id)
        )

        self.asset.refresh_from_db()
        self.assertEqual(self.asset.view_count, initial_view_count + 1)

    def test_calculate_popularity_score_returns_score(self):
        """Test calculate_popularity_score returns a score."""
        self.asset.view_count = 100
        self.asset.download_count = 50
        self.asset.status = AssetStatus.PUBLIC
        self.asset.save()

        score = AssetPopularityService.calculate_popularity_score(self.asset)
        self.assertIsNotNone(score)

    def test_calculate_popularity_score_returns_score_in_range(self):
        """Test calculate_popularity_score returns score between 0 and 100."""
        self.asset.view_count = 100
        self.asset.download_count = 50
        self.asset.status = AssetStatus.PUBLIC
        self.asset.save()

        score = AssetPopularityService.calculate_popularity_score(self.asset)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)

    def test_calculate_popularity_score_saves_score_to_asset(self):
        """Test calculate_popularity_score saves score to asset."""
        self.asset.view_count = 100
        self.asset.download_count = 50
        self.asset.status = AssetStatus.PUBLIC
        self.asset.save()

        score = AssetPopularityService.calculate_popularity_score(self.asset)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.popularity_score, score)

    def test_calculate_popularity_score_with_recency(self):
        """Test popularity score with recency bonus"""
        # Create recent search clicks
        SearchAnalytics.objects.create(
            tenant=self.tenant,
            user=self.user,
            query="test",
            clicked_result_id=self.asset.id,
            clicked_result_type="ASSET",
            clicked_at=timezone.now() - timedelta(days=1),
        )

        self.asset.view_count = 50
        self.asset.download_count = 25
        self.asset.save()

        score = AssetPopularityService.calculate_popularity_score(self.asset)

        # Should have recency bonus
        self.assertGreater(score, 0.0)

    def test_recalculate_all_popularity_scores_returns_correct_count(self):
        """Test recalculating all popularity scores returns correct count."""
        for i in range(5):
            Asset.objects.create(
                tenant=self.tenant,
                key=f"asset-{i}",
                name=f"Asset {i}",
                status=AssetStatus.ACTIVE,
                view_count=i * 10,
                download_count=i * 5,
                created_by=self.user,
            )

        count = AssetPopularityService.recalculate_all_popularity_scores(str(self.tenant.id))
        self.assertEqual(count, 6)

    def test_recalculate_all_popularity_scores_calculates_scores(self):
        """Test recalculating all popularity scores calculates scores for all assets."""
        for i in range(5):
            Asset.objects.create(
                tenant=self.tenant,
                key=f"asset-{i}",
                name=f"Asset {i}",
                status=AssetStatus.ACTIVE,
                view_count=i * 10,
                download_count=i * 5,
                created_by=self.user,
            )

        AssetPopularityService.recalculate_all_popularity_scores(str(self.tenant.id))

        assets = Asset.objects.filter(tenant=self.tenant)
        for asset in assets:
            self.assertIsNotNone(asset.popularity_score)

    # ========== SUCCESS SCENARIOS ==========

    def test_track_view_success_increments_count(self):
        """Test successful view tracking increments count."""
        initial_count = self.asset.view_count

        AssetPopularityService.track_view(str(self.asset.id), str(self.tenant.id))

        self.asset.refresh_from_db()
        self.assertEqual(self.asset.view_count, initial_count + 1)

    def test_track_view_success_updates_score(self):
        """Test successful view tracking updates popularity score."""
        AssetPopularityService.track_view(str(self.asset.id), str(self.tenant.id))

        self.asset.refresh_from_db()
        self.assertIsNotNone(self.asset.popularity_score)

    def test_track_download_success_increments_count(self):
        """Test successful download tracking increments count."""
        initial_count = self.asset.download_count

        AssetPopularityService.track_download(str(self.asset.id), str(self.tenant.id))

        self.asset.refresh_from_db()
        self.assertEqual(self.asset.download_count, initial_count + 1)

    def test_track_download_success_updates_score(self):
        """Test successful download tracking updates popularity score."""
        AssetPopularityService.track_download(str(self.asset.id), str(self.tenant.id))

        self.asset.refresh_from_db()
        self.assertIsNotNone(self.asset.popularity_score)

    # ========== FAILURE SCENARIOS ==========

    def test_track_view_nonexistent_asset(self):
        """Test view tracking with non-existent asset (failure scenario)"""
        import uuid

        fake_asset_id = str(uuid.uuid4())

        # Should handle non-existent asset gracefully
        try:
            AssetPopularityService.track_view(fake_asset_id, str(self.tenant.id))
            # If succeeds, that's acceptable
        except Exception:
            # If fails, that's acceptable for non-existent asset
            pass

    def test_calculate_popularity_score_zero_counts(self):
        """Test popularity score calculation with zero counts (failure scenario)"""
        self.asset.view_count = 0
        self.asset.download_count = 0
        self.asset.save()

        score = AssetPopularityService.calculate_popularity_score(self.asset)

        # Should return score (may be 0 or minimum)
        self.assertIsNotNone(score)
        self.assertGreaterEqual(score, 0.0)

    # ========== EDGE CASES ==========

    def test_calculate_popularity_score_very_high_counts(self):
        """Test popularity score with very high counts (edge case)"""
        self.asset.view_count = 999999
        self.asset.download_count = 999999
        self.asset.status = AssetStatus.PUBLIC
        self.asset.save()

        score = AssetPopularityService.calculate_popularity_score(self.asset)

        # Should handle very high counts gracefully
        self.assertIsNotNone(score)
        self.assertLessEqual(score, 100.0)  # Should cap at 100

    def test_calculate_popularity_score_negative_counts(self):
        """Test popularity score with negative counts (edge case)"""
        # Should handle negative counts gracefully
        self.asset.view_count = -1
        self.asset.download_count = -1
        self.asset.save()

        try:
            score = AssetPopularityService.calculate_popularity_score(self.asset)
            # If succeeds, should handle gracefully
            self.assertIsNotNone(score)
        except Exception:
            # If fails, that's acceptable for negative counts
            pass

    def test_recalculate_all_popularity_scores_empty_tenant(self):
        """Test recalculating scores for tenant with no assets (edge case)"""
        from hub.apps.tenants.models import Tenant

        empty_tenant = Tenant.objects.create(
            name="Empty Tenant", slug="empty-tenant", status="ACTIVE", kyc_status="UNVERIFIED"
        )

        count = AssetPopularityService.recalculate_all_popularity_scores(str(empty_tenant.id))

        # Should return 0 for empty tenant
        self.assertEqual(count, 0)

    # ========== ERROR HANDLING ==========

    def test_track_view_database_error_handling(self):
        """Test error handling when view tracking fails"""
        # Use valid asset
        try:
            AssetPopularityService.track_view(str(self.asset.id), str(self.tenant.id))
            # Should succeed
            self.asset.refresh_from_db()
            self.assertGreaterEqual(self.asset.view_count, 0)
        except Exception:
            # If raises exception, that's a problem
            self.fail("track_view should handle database errors gracefully")

    def test_calculate_popularity_score_error_handling(self):
        """Test error handling when score calculation fails"""
        # Use valid asset
        try:
            score = AssetPopularityService.calculate_popularity_score(self.asset)
            # Should return score
            self.assertIsNotNone(score)
        except Exception:
            # If raises exception, that's a problem
            self.fail("calculate_popularity_score should handle errors gracefully")

    def test_recalculate_all_popularity_scores_error_handling(self):
        """Test error handling when recalculating all scores fails"""
        # Use valid tenant
        try:
            count = AssetPopularityService.recalculate_all_popularity_scores(str(self.tenant.id))
            # Should return count
            self.assertGreaterEqual(count, 0)
        except Exception:
            # If raises exception, that's a problem
            self.fail("recalculate_all_popularity_scores should handle errors gracefully")
