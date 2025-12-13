"""
Unit tests for Impact Analysis

Tests for reverse lineage traversal, impact scoring, and impact calculation.
"""
import pytest
from django.test import TestCase

from hub.apps.contracts.models import Contract
from hub.apps.contracts.impact_analysis import ImpactAnalyzer, ImpactScorer, ImpactNode
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.assets.models import Asset, AssetStatus


pytestmark = pytest.mark.django_db(transaction=True)


class ImpactAnalyzerTest(TestCase):
    """Test ImpactAnalyzer"""
    
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
        
        # Create source contract
        self.source_contract = Contract.objects.create(
            tenant=self.tenant,
            name="Source Contract",
            original_spec_type="ODCS",
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw='{"apiVersion": "v1", "kind": "DataContract", "info": {"name": "Source Contract"}}',
            hub_contract_json={
                "info": {
                    "name": "Source Contract",
                    "title": "Source Contract"
                },
                "models": [
                    {
                        "name": "UserModel",
                        "fields": [
                            {"name": "email", "type": "string"}
                        ]
                    }
                ]
            },
            created_by=self.user
        )
        
        # Create dependent contract
        self.dependent_contract = Contract.objects.create(
            tenant=self.tenant,
            name="Dependent Contract",
            original_spec_type="ODCS",
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw='{"apiVersion": "v1", "kind": "DataContract", "info": {"name": "Dependent Contract"}}',
            hub_contract_json={
                "info": {
                    "name": "Dependent Contract",
                    "title": "Dependent Contract"
                },
                "lineage": {
                    "contracts": [
                        {
                            "namespace": None,
                            "name": "Source Contract"
                        }
                    ]
                }
            },
            created_by=self.user
        )
    
    def test_analyze_impact_contract_level(self):
        """Test contract-level impact analysis"""
        analyzer = ImpactAnalyzer(max_contract_depth=5)
        result = analyzer.analyze_impact(
            contract_id=str(self.source_contract.id),
            tenant_id=str(self.tenant.id)
        )
        
        self.assertNotIn("error", result)
        self.assertIn("source", result)
        self.assertIn("impact_graph", result)
        self.assertIn("summary", result)
        self.assertEqual(result["source"]["contract_id"], str(self.source_contract.id))
    
    def test_analyze_impact_with_depth_limit(self):
        """Test impact analysis with depth limit"""
        analyzer = ImpactAnalyzer(max_contract_depth=1)
        result = analyzer.analyze_impact(
            contract_id=str(self.source_contract.id),
            tenant_id=str(self.tenant.id)
        )
        
        self.assertNotIn("error", result)
        self.assertLessEqual(result.get("max_depth", 0), 1)
    
    def test_analyze_impact_cycle_detection(self):
        """Test cycle detection in impact analysis"""
        # Create circular reference
        self.source_contract.hub_contract_json["lineage"] = {
            "contracts": [
                {"name": "Dependent Contract"}
            ]
        }
        self.source_contract.save()
        
        analyzer = ImpactAnalyzer(max_contract_depth=10)
        result = analyzer.analyze_impact(
            contract_id=str(self.source_contract.id),
            tenant_id=str(self.tenant.id)
        )
        
        # Should detect cycles
        self.assertIn("cycles_detected", result)
    
    def test_impact_scoring(self):
        """Test impact scoring calculation"""
        analyzer = ImpactAnalyzer()
        result = analyzer.analyze_impact(
            contract_id=str(self.source_contract.id),
            tenant_id=str(self.tenant.id)
        )
        
        # Check that impact scores are calculated
        impact_graph = result.get("impact_graph", {})
        self.assertIn("impact_score", impact_graph)
        self.assertIn("severity", impact_graph)
    
    def test_impact_scorer_severity(self):
        """Test ImpactScorer severity calculation"""
        self.assertEqual(ImpactScorer.calculate_severity(90.0), "CRITICAL")
        self.assertEqual(ImpactScorer.calculate_severity(60.0), "HIGH")
        self.assertEqual(ImpactScorer.calculate_severity(30.0), "MEDIUM")
        self.assertEqual(ImpactScorer.calculate_severity(10.0), "LOW")
    
    def test_impact_scorer_asset_criticality(self):
        """Test asset criticality retrieval"""
        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )
        
        # Link contract to asset
        self.source_contract.asset = asset
        self.source_contract.save()
        
        criticality = ImpactScorer.get_asset_criticality(
            contract_id=str(self.source_contract.id),
            tenant_id=str(self.tenant.id)
        )
        
        self.assertIn(criticality, ["LOW", "MEDIUM", "HIGH"])

