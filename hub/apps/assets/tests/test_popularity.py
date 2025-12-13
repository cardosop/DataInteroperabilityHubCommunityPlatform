"""
Unit tests for Asset Popularity Metrics

Tests for view/download tracking and popularity score calculation.
"""
import pytest
from django.test import TestCase
from django.db.models import F
from django.utils import timezone
from datetime import timedelta

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
            status=AssetStatus.ACTIVE,
            view_count=0,
            download_count=0,
            created_by=self.user
        )
    
    def test_track_view(self):
        """Test view tracking"""
        initial_count = self.asset.view_count
        
        AssetPopularityService.track_view(str(self.asset.id), str(self.tenant.id))
        
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.view_count, initial_count + 1)
        self.assertIsNotNone(self.asset.popularity_score)
    
    def test_track_download(self):
        """Test download tracking"""
        initial_count = self.asset.download_count
        
        AssetPopularityService.track_download(str(self.asset.id), str(self.tenant.id))
        
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.download_count, initial_count + 1)
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
            str(self.asset.id),
            str(self.tenant.id),
            user_id=str(self.user.id)
        )
        
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.view_count, initial_view_count + 1)
    
    def test_calculate_popularity_score(self):
        """Test popularity score calculation"""
        # Set view and download counts
        self.asset.view_count = 100
        self.asset.download_count = 50
        self.asset.status = AssetStatus.PUBLIC
        self.asset.save()
        
        score = AssetPopularityService.calculate_popularity_score(self.asset)
        
        self.assertIsNotNone(score)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)
        
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
            clicked_at=timezone.now() - timedelta(days=1)
        )
        
        self.asset.view_count = 50
        self.asset.download_count = 25
        self.asset.save()
        
        score = AssetPopularityService.calculate_popularity_score(self.asset)
        
        # Should have recency bonus
        self.assertGreater(score, 0.0)
    
    def test_recalculate_all_popularity_scores(self):
        """Test recalculating all popularity scores"""
        # Create multiple assets
        for i in range(5):
            Asset.objects.create(
                tenant=self.tenant,
                key=f"asset-{i}",
                name=f"Asset {i}",
                status=AssetStatus.ACTIVE,
                view_count=i * 10,
                download_count=i * 5,
                created_by=self.user
            )
        
        count = AssetPopularityService.recalculate_all_popularity_scores(str(self.tenant.id))
        
        self.assertEqual(count, 6)  # 5 new + 1 existing
        
        # Verify scores were calculated
        assets = Asset.objects.filter(tenant=self.tenant)
        for asset in assets:
            self.assertIsNotNone(asset.popularity_score)

