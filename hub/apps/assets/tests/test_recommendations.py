"""
Unit tests for Asset Recommendations

Tests for recommendation algorithms based on usage patterns, lineage, and user behavior.
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


class AssetRecommendationServiceTest(TestCase):
    """Test AssetRecommendationService"""
    
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
        
        # Create assets
        self.asset1 = Asset.objects.create(
            tenant=self.tenant,
            key="asset-1",
            name="Asset 1",
            status=AssetStatus.ACTIVE,
            popularity_score=90.0,
            view_count=100,
            download_count=50,
            created_by=self.user
        )
        
        self.asset2 = Asset.objects.create(
            tenant=self.tenant,
            key="asset-2",
            name="Asset 2",
            status=AssetStatus.PUBLIC,
            popularity_score=80.0,
            view_count=80,
            download_count=40,
            domain="finance",
            created_by=self.user
        )
        
        self.asset3 = Asset.objects.create(
            tenant=self.tenant,
            key="asset-3",
            name="Asset 3",
            status=AssetStatus.ACTIVE,
            popularity_score=70.0,
            view_count=60,
            download_count=30,
            domain="marketing",
            created_by=self.user
        )
    
    def test_get_recommendations_usage_patterns(self):
        """Test usage pattern-based recommendations"""
        recommendations = AssetRecommendationService.get_recommendations(
            tenant_id=str(self.tenant.id),
            limit=10,
            include_usage_patterns=True,
            include_lineage=False,
            include_user_behavior=False
        )
        
        self.assertGreater(len(recommendations), 0)
        
        # Should be sorted by score descending
        if len(recommendations) > 1:
            self.assertGreaterEqual(
                recommendations[0]["score"],
                recommendations[1]["score"]
            )
        
        # Check recommendation structure
        for rec in recommendations:
            self.assertIn("asset_id", rec)
            self.assertIn("asset_name", rec)
            self.assertIn("score", rec)
            self.assertIn("reasons", rec)
    
    def test_get_recommendations_lineage(self):
        """Test lineage-based recommendations"""
        # Create contract with lineage
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset1,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.YAML,
            original_raw='{"apiVersion": "v3", "kind": "DataContract", "id": "source-contract"}',
            hub_contract_json={
                "id": "source-contract",
                "lineage": {
                    "contracts": [
                        {
                            "namespace": "ns1",
                            "name": "target-contract"
                        }
                    ]
                }
            },
            status=ContractStatus.ACTIVE,
            created_by=self.user
        )
        
        # Create target asset with contract
        target_asset = Asset.objects.create(
            tenant=self.tenant,
            key="target-asset",
            name="Target Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )
        
        target_contract = Contract.objects.create(
            tenant=self.tenant,
            asset=target_asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.YAML,
            original_raw='{"apiVersion": "v3", "kind": "DataContract", "id": "target-contract"}',
            hub_contract_json={
                "id": "target-contract"
            },
            status=ContractStatus.ACTIVE,
            created_by=self.user
        )
        
        recommendations = AssetRecommendationService.get_recommendations(
            tenant_id=str(self.tenant.id),
            asset_id=str(self.asset1.id),
            limit=10,
            include_usage_patterns=False,
            include_lineage=True,
            include_user_behavior=False
        )
        
        # Should find target asset via lineage
        self.assertGreater(len(recommendations), 0)
    
    def test_get_recommendations_user_behavior(self):
        """Test user behavior-based recommendations"""
        # Create search analytics with clicks
        SearchAnalytics.objects.create(
            tenant=self.tenant,
            user=self.user,
            query="test query",
            clicked_result_id=self.asset2.id,
            clicked_result_type="ASSET",
            clicked_at=timezone.now()
        )
        
        recommendations = AssetRecommendationService.get_recommendations(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            limit=10,
            include_usage_patterns=False,
            include_lineage=False,
            include_user_behavior=True
        )
        
        # Should find recommendations based on user behavior
        self.assertGreater(len(recommendations), 0)
    
    def test_get_recommendations_combined(self):
        """Test combined recommendations from all sources"""
        recommendations = AssetRecommendationService.get_recommendations(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            limit=10,
            include_usage_patterns=True,
            include_lineage=True,
            include_user_behavior=True
        )
        
        self.assertGreater(len(recommendations), 0)
        
        # Check that recommendations are aggregated
        asset_ids = [r["asset_id"] for r in recommendations]
        self.assertEqual(len(asset_ids), len(set(asset_ids)))  # No duplicates
    
    def test_recommendations_limit(self):
        """Test recommendation limit"""
        recommendations = AssetRecommendationService.get_recommendations(
            tenant_id=str(self.tenant.id),
            limit=2
        )
        
        self.assertLessEqual(len(recommendations), 2)

