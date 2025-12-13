"""
Integration tests for Asset Popularity Metrics

Tests for popularity tracking in the context of asset workflows.
"""
import pytest
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

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
    
    def test_popularity_tracking_workflow(self):
        """Test complete popularity tracking workflow"""
        # Track views
        for _ in range(5):
            AssetPopularityService.track_view(str(self.asset.id), str(self.tenant.id))
        
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.view_count, 5)
        self.assertIsNotNone(self.asset.popularity_score)
        
        # Track downloads
        for _ in range(3):
            AssetPopularityService.track_download(str(self.asset.id), str(self.tenant.id))
        
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.download_count, 3)
        
        # Popularity score should be recalculated
        final_score = AssetPopularityService.calculate_popularity_score(self.asset)
        self.assertGreater(final_score, 0.0)

