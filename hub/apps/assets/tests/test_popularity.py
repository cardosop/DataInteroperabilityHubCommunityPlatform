"""
Unit tests for Asset Popularity Metrics

Tests for view/download tracking and popularity score calculation.
"""
import uuid

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
        self.assertGreater(self.asset.popularity_score, 0.0)

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
        self.assertGreater(self.asset.popularity_score, 0.0)

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

    # ========== FAILURE SCENARIOS ==========

    def test_track_view_nonexistent_asset(self):
        """track_view with non-existent asset does not raise (logs warning)."""
        fake_asset_id = str(uuid.uuid4())
        # Should not raise — production code catches DoesNotExist
        AssetPopularityService.track_view(fake_asset_id, str(self.tenant.id))
        # Verify no orphan records were created
        self.assertFalse(Asset.objects.filter(id=fake_asset_id).exists())

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
        """Negative counts produce a numeric score (not clamped by service)."""
        self.asset.view_count = -1
        self.asset.download_count = -1
        self.asset.save()

        score = AssetPopularityService.calculate_popularity_score(self.asset)
        self.assertIsInstance(score, float)

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

    def test_track_view_succeeds_with_valid_asset(self):
        """Test that track_view succeeds with a valid asset."""
        AssetPopularityService.track_view(str(self.asset.id), str(self.tenant.id))
        self.asset.refresh_from_db()
        self.assertGreaterEqual(self.asset.view_count, 1)

    def test_calculate_popularity_score_succeeds_with_valid_asset(self):
        """Test that calculate_popularity_score succeeds with a valid asset."""
        score = AssetPopularityService.calculate_popularity_score(self.asset)
        self.assertIsNotNone(score)
        self.assertGreaterEqual(score, 0.0)

    def test_recalculate_all_popularity_scores_succeeds_with_valid_tenant(self):
        """Test that recalculate_all_popularity_scores succeeds with a valid tenant."""
        count = AssetPopularityService.recalculate_all_popularity_scores(str(self.tenant.id))
        self.assertGreaterEqual(count, 0)
