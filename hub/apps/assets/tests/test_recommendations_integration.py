"""
Integration tests for Asset Recommendations

Tests for recommendations in the context of asset workflows.
"""
import pytest
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.assets.recommendations import AssetRecommendationService
from hub.apps.contracts.models import Contract, ContractStatus, OriginalSpecType, OriginalFormat
from hub.apps.search.models import SearchAnalytics
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus


pytestmark = pytest.mark.django_db(transaction=True)


class AssetRecommendationsIntegrationTest(TestCase):
    """Integration tests for asset recommendations"""
    
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
        
        # Create assets with different popularity
        self.popular_asset = Asset.objects.create(
            tenant=self.tenant,
            key="popular-asset",
            name="Popular Asset",
            status=AssetStatus.PUBLIC,
            popularity_score=95.0,
            view_count=500,
            download_count=200,
            created_by=self.user
        )
        
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            popularity_score=70.0,
            view_count=100,
            download_count=50,
            created_by=self.user
        )
    
    def test_recommendations_workflow(self):
        """Test complete recommendations workflow"""
        # Create user search history
        SearchAnalytics.objects.create(
            tenant=self.tenant,
            user=self.user,
            query="test query",
            clicked_result_id=self.asset.id,
            clicked_result_type="ASSET",
            clicked_at=timezone.now()
        )
        
        # Get recommendations
        recommendations = AssetRecommendationService.get_recommendations(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            limit=10
        )
        
        # Verify recommendations
        self.assertGreater(len(recommendations), 0)
        
        # Popular asset should be recommended
        asset_ids = [r["asset_id"] for r in recommendations]
        self.assertIn(str(self.popular_asset.id), asset_ids)

