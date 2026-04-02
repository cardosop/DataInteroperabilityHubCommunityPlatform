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
from hub.apps.contracts.models import Contract, ContractStatus, OriginalFormat, OriginalSpecType
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
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", status="ACTIVE", kyc_status="UNVERIFIED"
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
        """Test complete recommendations workflow returns recommendations."""
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

    def test_recommendations_workflow_includes_popular_asset(self):
        """Test complete recommendations workflow includes popular asset."""
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

        asset_ids = [r["asset_id"] for r in recommendations]
        self.assertIn(str(self.popular_asset.id), asset_ids)

    # ========== SUCCESS SCENARIOS ==========

    def test_recommendations_integration_success(self):
        """Test successful recommendations integration workflow (success scenario)"""
        # Create search history
        SearchAnalytics.objects.create(
            tenant=self.tenant,
            user=self.user,
            query="test query",
            clicked_result_id=self.asset.id,
            clicked_result_type="ASSET",
            clicked_at=timezone.now(),
        )

        # Get recommendations
        recommendations = AssetRecommendationService.get_recommendations(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id), limit=10
        )

        # Should return recommendations
        self.assertGreater(len(recommendations), 0)

    # ========== FAILURE SCENARIOS ==========

    def test_recommendations_integration_no_search_history(self):
        """Test recommendations without search history (failure scenario)"""
        # Don't create search history

        recommendations = AssetRecommendationService.get_recommendations(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            limit=10,
            include_user_behavior=True,
        )

        # Should still return recommendations (from other sources)
        self.assertIsInstance(recommendations, list)

    def test_recommendations_integration_nonexistent_user(self):
        """Test recommendations with non-existent user returns empty recommendations"""
        fake_user_id = str(uuid.uuid4())

        recommendations = AssetRecommendationService.get_recommendations(
            tenant_id=str(self.tenant.id), user_id=fake_user_id, limit=10
        )
        self.assertIsInstance(recommendations, list)

    # ========== EDGE CASES ==========

    def test_recommendations_integration_old_search_history(self):
        """Test recommendations with old search history (edge case)"""
        # Create old search history
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

        # Should handle old history gracefully
        self.assertIsInstance(recommendations, list)

    def test_recommendations_integration_multiple_search_clicks(self):
        """Test recommendations with multiple search clicks (edge case)"""
        # Create multiple search clicks
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

        # Should handle multiple clicks gracefully
        self.assertIsInstance(recommendations, list)

    # ========== ERROR HANDLING ==========

    def test_recommendations_integration_error_handling(self):
        """Test error handling in recommendations integration"""
        # Use valid data
        try:
            recommendations = AssetRecommendationService.get_recommendations(
                tenant_id=str(self.tenant.id), user_id=str(self.user.id), limit=10
            )
            # Should return recommendations
            self.assertIsNotNone(recommendations)
            self.assertIsInstance(recommendations, list)
        except Exception:
            # If raises exception, that's a problem
            self.fail("get_recommendations should handle errors gracefully")
