"""
Integration tests for Asset Recommendations

Tests for recommendations in the context of asset workflows.
"""

import uuid
from datetime import timedelta

import pytest
from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.assets.recommendations import AssetRecommendationService
from hub.apps.search.models import SearchAnalytics
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class AssetRecommendationsIntegrationTest(TestCase):
    """Integration tests for asset recommendations"""

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

        # Create assets with different popularity
        self.popular_asset = Asset.objects.create(
            tenant=self.tenant,
            key="popular-asset",
            name="Popular Asset",
            status=AssetStatus.PUBLIC,
            popularity_score=95.0,
            view_count=500,
            download_count=200,
            created_by=self.user,
        )

        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            popularity_score=70.0,
            view_count=100,
            download_count=50,
            created_by=self.user,
        )

    def test_recommendations_workflow_returns_recommendations(self):
        """Test complete recommendations workflow returns recommendations
        that include the popular asset and respect the limit."""
        SearchAnalytics.objects.create(
            tenant=self.tenant,
            user=self.user,
            query="test query",
            clicked_result_id=self.asset.id,
            clicked_result_type="ASSET",
            clicked_at=timezone.now(),
        )

        recommendations = AssetRecommendationService.get_recommendations(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id), limit=10
        )

        self.assertGreater(len(recommendations), 0)
        self.assertLessEqual(len(recommendations), 10)

        # Popular asset should be among the recommendations
        asset_ids = [r["asset_id"] for r in recommendations]
        self.assertIn(str(self.popular_asset.id), asset_ids)

        # Each recommendation must have the required schema
        for rec in recommendations:
            self.assertIn("asset_id", rec)
            self.assertIn("asset_name", rec)
            self.assertIn("score", rec)
            self.assertIn("reasons", rec)

    # ========== FAILURE SCENARIOS ==========

    def test_recommendations_integration_no_search_history(self):
        """Test that recommendations still work without search history.

        When user-behavior source is enabled but the user has no search
        history, the service should fall back to other sources (usage
        patterns, popularity) and still return results.
        """
        recommendations = AssetRecommendationService.get_recommendations(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            limit=10,
            include_user_behavior=True,
        )

        self.assertIsInstance(recommendations, list)
        # Fallback to usage-pattern recommendations means the popular
        # asset should still appear
        asset_ids = [r["asset_id"] for r in recommendations]
        self.assertIn(str(self.popular_asset.id), asset_ids)

    def test_recommendations_integration_nonexistent_user(self):
        """Test recommendations with non-existent user falls back gracefully.

        A fake user ID should not cause an error — the service should
        fall back to tenant-wide recommendations.
        """
        fake_user_id = str(uuid.uuid4())

        recommendations = AssetRecommendationService.get_recommendations(
            tenant_id=str(self.tenant.id), user_id=fake_user_id, limit=10
        )
        self.assertIsInstance(recommendations, list)
        self.assertGreater(len(recommendations), 0)

    # ========== EDGE CASES ==========

    def test_recommendations_integration_old_search_history(self):
        """Test that very old search history does not crash recommendations.

        A search click from 365 days ago should be handled gracefully —
        the result must be a valid list. The recommendation engine may
        deprioritize or ignore stale history but must not error.
        """
        SearchAnalytics.objects.create(
            tenant=self.tenant,
            user=self.user,
            query="old query",
            clicked_result_id=self.asset.id,
            clicked_result_type="ASSET",
            clicked_at=timezone.now() - timedelta(days=365),  # Very old
        )

        recommendations = AssetRecommendationService.get_recommendations(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id), limit=10
        )

        self.assertIsInstance(recommendations, list)
        # Should still return something (the popular asset via usage-patterns)
        self.assertGreater(len(recommendations), 0)

    def test_recommendations_integration_multiple_search_clicks(self):
        """Test recommendations with multiple search clicks returns results.

        Ten clicks over a 10-hour window should produce recommendations
        without error. The clicked asset should appear prominently.
        """
        for i in range(10):
            SearchAnalytics.objects.create(
                tenant=self.tenant,
                user=self.user,
                query=f"query {i}",
                clicked_result_id=self.asset.id,
                clicked_result_type="ASSET",
                clicked_at=timezone.now() - timedelta(hours=i),
            )

        recommendations = AssetRecommendationService.get_recommendations(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id), limit=10
        )

        self.assertIsInstance(recommendations, list)
        self.assertGreater(len(recommendations), 0)
        # The repeatedly-clicked asset should be recommended
        asset_ids = [r["asset_id"] for r in recommendations]
        self.assertIn(str(self.asset.id), asset_ids)
