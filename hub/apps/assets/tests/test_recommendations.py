"""
Unit tests for Asset Recommendations

Tests for recommendation algorithms based on usage patterns, lineage, and user behavior.
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


class AssetRecommendationServiceTest(TestCase):
    """Test AssetRecommendationService"""

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

        # Create assets
        self.asset1 = Asset.objects.create(
            tenant=self.tenant,
            key="asset-1",
            name="Asset 1",
            status=AssetStatus.ACTIVE,
            popularity_score=90.0,
            view_count=100,
            download_count=50,
            created_by=self.user,
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
            created_by=self.user,
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
            created_by=self.user,
        )

        # Create another asset with finance domain for user behavior recommendations
        self.asset4 = Asset.objects.create(
            tenant=self.tenant,
            key="asset-4",
            name="Asset 4",
            status=AssetStatus.ACTIVE,
            popularity_score=75.0,
            view_count=70,
            download_count=35,
            domain="finance",
            created_by=self.user,
        )

    def test_get_recommendations_usage_patterns_returns_recommendations(self):
        """Test usage pattern-based recommendations are sorted by score descending."""
        recommendations = AssetRecommendationService.get_recommendations(
            tenant_id=str(self.tenant.id),
            limit=10,
            include_usage_patterns=True,
            include_lineage=False,
            include_user_behavior=False,
        )

        self.assertGreater(len(recommendations), 0)
        # Usage-pattern recommendations should be sorted by score descending
        scores = [r["score"] for r in recommendations]
        self.assertEqual(scores, sorted(scores, reverse=True),
                         "usage-pattern recommendations must be sorted by score descending")

    def test_get_recommendations_usage_patterns_sorted_by_score(self):
        """Test usage pattern-based recommendations are sorted by score descending."""
        recommendations = AssetRecommendationService.get_recommendations(
            tenant_id=str(self.tenant.id),
            limit=10,
            include_usage_patterns=True,
            include_lineage=False,
            include_user_behavior=False,
        )

        self.assertGreater(len(recommendations), 1, "Need >1 recommendations to verify sort")
        self.assertGreaterEqual(recommendations[0]["score"], recommendations[1]["score"])

    def test_get_recommendations_usage_patterns_has_required_fields(self):
        """Test usage pattern-based recommendations have required fields."""
        recommendations = AssetRecommendationService.get_recommendations(
            tenant_id=str(self.tenant.id),
            limit=10,
            include_usage_patterns=True,
            include_lineage=False,
            include_user_behavior=False,
        )

        for rec in recommendations:
            self.assertIn("asset_id", rec)
            self.assertIn("asset_name", rec)
            self.assertIn("score", rec)
            self.assertIn("reasons", rec)

    def test_get_recommendations_lineage(self):
        """Test lineage-based recommendations return target assets."""
        # Create contract with lineage pointing to a target contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset1,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.YAML,
            original_raw='{"apiVersion": "v3", "kind": "DataContract", "id": "source-contract"}',
            hub_contract_json={
                "id": "source-contract",
                "lineage": {"contracts": [{"namespace": "ns1", "name": "target-contract"}]},
            },
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        # Create target asset with the referenced contract
        target_asset = Asset.objects.create(
            tenant=self.tenant,
            key="target-asset",
            name="Target Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        target_contract = Contract.objects.create(
            tenant=self.tenant,
            asset=target_asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.YAML,
            original_raw='{"apiVersion": "v3", "kind": "DataContract", "id": "target-contract"}',
            hub_contract_json={"id": "target-contract"},
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        recommendations = AssetRecommendationService.get_recommendations(
            tenant_id=str(self.tenant.id),
            asset_id=str(self.asset1.id),
            limit=10,
            include_usage_patterns=False,
            include_lineage=True,
            include_user_behavior=False,
        )

        # Should find recommendations via lineage
        self.assertGreater(len(recommendations), 0)
        # The target asset should be among the recommendations
        target_ids = [r["asset_id"] for r in recommendations]
        self.assertIn(str(target_asset.id), target_ids)

    def test_get_recommendations_user_behavior(self):
        """Test user behavior-based recommendations include clicked/similar assets."""
        # Create search analytics with clicks on asset2
        SearchAnalytics.objects.create(
            tenant=self.tenant,
            user=self.user,
            query="finance data",
            clicked_result_id=self.asset2.id,
            clicked_result_type="ASSET",
            clicked_at=timezone.now(),
        )

        recommendations = AssetRecommendationService.get_recommendations(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            limit=10,
            include_usage_patterns=False,
            include_lineage=False,
            include_user_behavior=True,
        )

        # Should find recommendations based on user behavior
        self.assertGreater(len(recommendations), 0)
        # At least one recommendation should be scoped to the same tenant
        recommended_ids = [r["asset_id"] for r in recommendations]
        tenant_asset_ids = set(
            str(a.id) for a in Asset.objects.filter(tenant=self.tenant)
        )
        self.assertTrue(
            any(rid in tenant_asset_ids for rid in recommended_ids),
            "Recommendations must include assets from the user's tenant",
        )

    def test_get_recommendations_combined(self):
        """Test combined recommendations from all sources"""
        recommendations = AssetRecommendationService.get_recommendations(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            limit=10,
            include_usage_patterns=True,
            include_lineage=True,
            include_user_behavior=True,
        )

        self.assertGreater(len(recommendations), 0)

        # Check that recommendations are aggregated
        asset_ids = [r["asset_id"] for r in recommendations]
        self.assertEqual(len(asset_ids), len(set(asset_ids)))  # No duplicates

    def test_recommendations_limit(self):
        """Test recommendation limit"""
        recommendations = AssetRecommendationService.get_recommendations(
            tenant_id=str(self.tenant.id), limit=2
        )

        self.assertLessEqual(len(recommendations), 2)

    # ========== SUCCESS SCENARIOS ==========

    def test_get_recommendations_success(self):
        """Test successful recommendation retrieval (success scenario)"""
        recommendations = AssetRecommendationService.get_recommendations(
            tenant_id=str(self.tenant.id), limit=10
        )

        # Should return recommendations for assets in the tenant
        self.assertIsInstance(recommendations, list)
        self.assertGreater(len(recommendations), 0)
        # Each recommendation must have the required schema fields
        for rec in recommendations:
            self.assertIn("asset_id", rec)
            self.assertIn("asset_name", rec)
            self.assertIn("score", rec)
            self.assertIn("reasons", rec)
        # Scores should be non-negative
        for rec in recommendations:
            self.assertGreaterEqual(rec["score"], 0)

    # ========== FAILURE SCENARIOS ==========

    def test_get_recommendations_nonexistent_tenant(self):
        """Test recommendations with non-existent tenant returns empty list"""
        fake_tenant_id = str(uuid.uuid4())

        recommendations = AssetRecommendationService.get_recommendations(
            tenant_id=fake_tenant_id, limit=10
        )
        self.assertEqual(len(recommendations), 0)

    def test_get_recommendations_unknown_asset_id_falls_back_to_tenant_wide(self):
        """Test that a non-matching asset_id returns tenant-wide recommendations.

        When the given asset_id doesn't match any asset, the service falls back
        to returning all tenant assets (the fake UUID is simply excluded from
        personalized filtering, not treated as an error)."""
        fake_asset_id = str(uuid.uuid4())

        recommendations = AssetRecommendationService.get_recommendations(
            tenant_id=str(self.tenant.id), asset_id=fake_asset_id, limit=10
        )
        # Service returns tenant-wide recommendations because the given
        # asset_id matches nothing — the result is NOT empty.
        self.assertIsInstance(recommendations, list)
        self.assertGreater(len(recommendations), 0)
        # All returned assets must belong to the tenant
        tenant_asset_ids = set(
            str(a.id) for a in Asset.objects.filter(tenant=self.tenant)
        )
        for rec in recommendations:
            self.assertIn(rec["asset_id"], tenant_asset_ids)

    # ========== EDGE CASES ==========

    def test_get_recommendations_zero_limit(self):
        """Test recommendations with zero limit (edge case)"""
        recommendations = AssetRecommendationService.get_recommendations(
            tenant_id=str(self.tenant.id), limit=0
        )

        # Should return empty list or handle gracefully
        self.assertIsInstance(recommendations, list)
        self.assertEqual(len(recommendations), 0)

    def test_get_recommendations_very_large_limit(self):
        """Test recommendations with very large limit (edge case)"""
        recommendations = AssetRecommendationService.get_recommendations(
            tenant_id=str(self.tenant.id), limit=999999
        )

        # Should return available recommendations (limited by data)
        self.assertIsInstance(recommendations, list)
        self.assertLessEqual(len(recommendations), 999999)

    def test_get_recommendations_no_assets(self):
        """Test recommendations when no assets exist (edge case)"""
        # Create empty tenant
        empty_tenant = Tenant.objects.create(
            name="Empty Tenant", slug="empty-tenant", status="ACTIVE", kyc_status="UNVERIFIED"
        )

        recommendations = AssetRecommendationService.get_recommendations(
            tenant_id=str(empty_tenant.id), limit=10
        )

        # Should return empty list
        self.assertEqual(len(recommendations), 0)

    def test_get_recommendations_all_filters_disabled(self):
        """Test recommendations with all sources disabled returns empty list."""
        recommendations = AssetRecommendationService.get_recommendations(
            tenant_id=str(self.tenant.id),
            limit=10,
            include_usage_patterns=False,
            include_lineage=False,
            include_user_behavior=False,
        )

        # With all recommendation sources disabled, the result must be empty
        self.assertIsInstance(recommendations, list)
        self.assertEqual(len(recommendations), 0)

    def test_get_recommendations_invalid_parameters(self):
        """Test recommendations with invalid tenant_id returns empty list."""
        recommendations = AssetRecommendationService.get_recommendations(
            tenant_id="invalid-uuid", limit=10
        )
        self.assertIsInstance(recommendations, list)
        self.assertEqual(len(recommendations), 0)

    def test_get_recommendations_negative_limit(self):
        """Test recommendations with negative limit raises ValueError.

        Django querysets do not support negative indexing ([:limit] with
        limit < 0 raises ValueError).  The recommendation service should
        validate the limit parameter before slicing, but currently passes
        the raw value through to the queryset.
        """
        with self.assertRaises(ValueError):
            AssetRecommendationService.get_recommendations(
                tenant_id=str(self.tenant.id), limit=-1
            )
