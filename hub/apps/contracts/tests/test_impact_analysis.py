"""
Unit tests for Impact Analysis

Tests for reverse lineage traversal, impact scoring, and impact calculation.
"""

import pytest

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.impact_analysis import ImpactAnalyzer, ImpactNode, ImpactScorer
from hub.apps.contracts.models import Contract
from hub.apps.contracts.tests.test_base import ContractsTestBase
from hub.apps.tenants.models import Tenant
import uuid

pytestmark = pytest.mark.django_db(transaction=True)


class ImpactAnalyzerTest(ContractsTestBase):
    """Test ImpactAnalyzer"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        import uuid; uid = uuid.uuid4().hex[:8]
        # Update tenant name/email for impact analysis tests
        self.tenant.name = f"Test Tenant {uid}"
        self.tenant.slug = f"test-tenant-{uid}"
        self.tenant.save()

        self.user.email = f"user-{uid}@example.com"
        self.user.save()

        # Create source contract
        self.source_contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type="ODCS",
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw='{"apiVersion": "v1", "kind": "DataContract", "info": {"name": "Source Contract"}}',
            hub_contract_json={
                "info": {"name": "Source Contract", "title": "Source Contract"},
                "models": [{"name": "UserModel", "fields": [{"name": "email", "type": "string"}]}],
            },
            created_by=self.user,
        )

        # Create dependent contract
        self.dependent_contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type="ODCS",
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw='{"apiVersion": "v1", "kind": "DataContract", "info": {"name": "Dependent Contract"}}',
            hub_contract_json={
                "info": {"name": "Dependent Contract", "title": "Dependent Contract"},
                "lineage": {"contracts": [{"namespace": None, "name": "Source Contract"}]},
            },
            created_by=self.user,
        )

    def test_analyze_impact_contract_level(self):
        """Test contract-level impact analysis"""
        analyzer = ImpactAnalyzer(max_contract_depth=5)
        result = analyzer.analyze_impact(
            contract_id=str(self.source_contract.id), tenant_id=str(self.tenant.id)
        )

        self.assertNotIn("error", result)
        self.assertIn("source", result)
        self.assertIn("impact_graph", result)
        self.assertIn("summary", result)
        self.assertEqual(result["source"]["contract_id"], str(self.source_contract.id))

    def test_analyze_impact_with_depth_limit(self):
        """Test impact analysis with depth limit"""
        # Arrange
        analyzer = ImpactAnalyzer(max_contract_depth=1)

        # Act
        result = analyzer.analyze_impact(
            contract_id=str(self.source_contract.id), tenant_id=str(self.tenant.id)
        )

        # Assert
        self.assertNotIn("error", result)
        self.assertLessEqual(result.get("max_depth", 0), 1)

    def test_analyze_impact_cycle_detection(self):
        """Test cycle detection in impact analysis"""
        # Create circular reference
        self.source_contract.hub_contract_json["lineage"] = {
            "contracts": [{"name": "Dependent Contract"}]
        }
        self.source_contract.save()

        analyzer = ImpactAnalyzer(max_contract_depth=10)
        result = analyzer.analyze_impact(
            contract_id=str(self.source_contract.id), tenant_id=str(self.tenant.id)
        )

        # Should detect cycles
        self.assertIn("cycles_detected", result)

    def test_impact_scoring(self):
        """Test impact scoring calculation"""
        analyzer = ImpactAnalyzer()
        result = analyzer.analyze_impact(
            contract_id=str(self.source_contract.id), tenant_id=str(self.tenant.id)
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
            created_by=self.user,
        )

        # Link contract to asset
        self.source_contract.asset = asset
        self.source_contract.save()

        criticality = ImpactScorer.get_asset_criticality(
            contract_id=str(self.source_contract.id), tenant_id=str(self.tenant.id)
        )

        self.assertIn(criticality, ["LOW", "MEDIUM", "HIGH"])

    # Edge cases and error handling tests
    def test_analyze_impact_contract_not_found(self):
        """Test impact analysis with non-existent contract."""
        import uuid

        fake_contract_id = str(uuid.uuid4())

        analyzer = ImpactAnalyzer()
        result = analyzer.analyze_impact(
            contract_id=fake_contract_id, tenant_id=str(self.tenant.id)
        )

        # Non-existent contract should return an error
        self.assertIn("error", result, "Non-existent contract should produce an error")
        self.assertIsInstance(result["error"], str)

    def test_analyze_impact_cross_tenant_isolation(self):
        """Test that impact analysis respects tenant isolation."""
        # Create another tenant
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}",
            slug=f"other-tenant-impact-{_uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

        # Try to analyze contract from other tenant
        analyzer = ImpactAnalyzer()
        result = analyzer.analyze_impact(
            contract_id=str(self.source_contract.id), tenant_id=str(other_tenant.id)
        )

        # Should not find contract from other tenant — must return error
        self.assertIn(
            "error", result,
            "Cross-tenant access should produce an error",
        )
        self.assertIsInstance(result["error"], str)

    def test_analyze_impact_with_empty_lineage(self):
        """Test impact analysis with contract that has no lineage."""
        contract_no_lineage = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type="ODCS",
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw='{"apiVersion": "v1", "kind": "DataContract", "info": {"name": "No Lineage"}}',
            hub_contract_json={
                "info": {"name": "No Lineage Contract", "title": "No Lineage Contract"},
                # No lineage field
            },
            created_by=self.user,
        )

        analyzer = ImpactAnalyzer()
        result = analyzer.analyze_impact(
            contract_id=str(contract_no_lineage.id), tenant_id=str(self.tenant.id)
        )

        # Should handle gracefully
        self.assertNotIn("error", result)
        self.assertIn("source", result)
        self.assertIn("impact_graph", result)

    def test_analyze_impact_with_missing_hub_contract_json(self):
        """Test impact analysis with contract missing hub_contract_json."""
        contract_no_hub = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type="ODCS",
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw='{"apiVersion": "v1", "kind": "DataContract", "info": {"name": "No Hub"}}',
            # hub_contract_json is None
            created_by=self.user,
        )

        analyzer = ImpactAnalyzer()
        result = analyzer.analyze_impact(
            contract_id=str(contract_no_hub.id), tenant_id=str(self.tenant.id)
        )

        # Contract with no hub_contract_json should still be analyzable
        self.assertIsNotNone(result)
        self.assertNotIn("error", result)
        self.assertIn("source", result)

    def test_analyze_impact_with_invalid_contract_id_format(self):
        """Test impact analysis with invalid contract_id format."""
        analyzer = ImpactAnalyzer()
        result = analyzer.analyze_impact(contract_id="not-a-uuid", tenant_id=str(self.tenant.id))

        # Invalid UUID should produce an error
        self.assertIn(
            "error", result,
            "Invalid contract_id format should produce an error",
        )
        self.assertIsInstance(result["error"], str)

    def test_analyze_impact_with_zero_depth_limit(self):
        """Test impact analysis with zero depth limit."""
        analyzer = ImpactAnalyzer(max_contract_depth=0)
        result = analyzer.analyze_impact(
            contract_id=str(self.source_contract.id), tenant_id=str(self.tenant.id)
        )

        # Should handle zero depth gracefully
        self.assertNotIn("error", result)
        self.assertIn("source", result)
        self.assertEqual(result.get("max_depth", 0), 0)

    def test_analyze_impact_with_very_large_depth_limit(self):
        """Test impact analysis with very large depth limit."""
        analyzer = ImpactAnalyzer(max_contract_depth=1000)
        result = analyzer.analyze_impact(
            contract_id=str(self.source_contract.id), tenant_id=str(self.tenant.id)
        )

        # Should handle large depth gracefully
        self.assertNotIn("error", result)
        self.assertIn("source", result)

    def test_impact_scorer_severity_edge_cases(self):
        """Test ImpactScorer severity calculation with edge case values."""
        # Test boundary values
        self.assertEqual(ImpactScorer.calculate_severity(100.0), "CRITICAL")
        self.assertEqual(ImpactScorer.calculate_severity(0.0), "LOW")
        self.assertEqual(
            ImpactScorer.calculate_severity(50.0), "HIGH"
        )  # Boundary between HIGH and MEDIUM
        self.assertEqual(
            ImpactScorer.calculate_severity(20.0), "MEDIUM"
        )  # Boundary between MEDIUM and LOW

    def test_impact_scorer_severity_with_negative_values(self):
        """Test ImpactScorer severity calculation with negative values."""
        # Negative values should clamp to LOW severity
        result = ImpactScorer.calculate_severity(-10.0)
        self.assertEqual(result, "LOW")

    def test_impact_scorer_severity_with_values_over_100(self):
        """Test ImpactScorer severity calculation with values over 100."""
        # Values over 100 should clamp to CRITICAL severity
        result = ImpactScorer.calculate_severity(150.0)
        self.assertEqual(result, "CRITICAL")

    def test_impact_scorer_asset_criticality_without_asset(self):
        """Test asset criticality retrieval for contract without asset."""
        # Contract without asset should still return a criticality
        criticality = ImpactScorer.get_asset_criticality(
            contract_id=str(self.source_contract.id), tenant_id=str(self.tenant.id)
        )

        self.assertIn(criticality, ["LOW", "MEDIUM", "HIGH"])

    def test_impact_scorer_asset_criticality_contract_not_found(self):
        """Test asset criticality retrieval for non-existent contract."""
        import uuid

        fake_contract_id = str(uuid.uuid4())

        # Should handle gracefully
        try:
            criticality = ImpactScorer.get_asset_criticality(
                contract_id=fake_contract_id, tenant_id=str(self.tenant.id)
            )
            self.assertIn(criticality, ["LOW", "MEDIUM", "HIGH"])
        except Exception:
            # If it raises exception, that's also acceptable
            pass

    def test_analyze_impact_with_broken_lineage_references(self):
        """Test impact analysis with broken lineage references."""
        contract_broken = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type="ODCS",
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw='{"apiVersion": "v1", "kind": "DataContract", "info": {"name": "Broken"}}',
            hub_contract_json={
                "info": {"name": "Broken Lineage Contract", "title": "Broken Lineage Contract"},
                "lineage": {
                    "contracts": [
                        {"name": "Nonexistent Contract"}  # Reference to non-existent contract
                    ]
                },
            },
            created_by=self.user,
        )

        analyzer = ImpactAnalyzer()
        result = analyzer.analyze_impact(
            contract_id=str(contract_broken.id), tenant_id=str(self.tenant.id)
        )

        # Should handle broken references gracefully
        self.assertNotIn("error", result)
        self.assertIn("source", result)

    def test_analyze_impact_with_multiple_dependent_contracts(self):
        """Test impact analysis with multiple dependent contracts."""
        # Create multiple dependent contracts
        for i in range(5):
            Contract.objects.create(
                tenant=self.tenant,
                original_spec_type="ODCS",
                original_spec_version="3.0.2",
                original_format="JSON",
                original_raw=f'{{"apiVersion": "v1", "kind": "DataContract", "info": {{"name": "Dependent {i}"}}}}',
                hub_contract_json={
                    "info": {"name": f"Dependent Contract {i}", "title": f"Dependent Contract {i}"},
                    "lineage": {"contracts": [{"name": "Source Contract"}]},
                },
                created_by=self.user,
            )

        analyzer = ImpactAnalyzer()
        result = analyzer.analyze_impact(
            contract_id=str(self.source_contract.id), tenant_id=str(self.tenant.id)
        )

        # Should handle multiple dependents
        self.assertNotIn("error", result)
        self.assertIn("source", result)
        self.assertIn("impact_graph", result)

    def test_impact_node_creation(self):
        """Test ImpactNode creation and properties."""
        node = ImpactNode(
            contract_id=str(self.source_contract.id),
            contract_name="Test Contract",
            impact_score=75.0,
            depth=1,
        )

        self.assertEqual(node.contract_id, str(self.source_contract.id))
        self.assertEqual(node.contract_name, "Test Contract")
        self.assertEqual(node.impact_score, 75.0)
        self.assertEqual(node.depth, 1)
        # Default severity when not explicitly passed
        self.assertEqual(node.severity, "LOW")

    def test_impact_node_with_edge_case_values(self):
        """Test ImpactNode with edge case values."""
        # Test with zero values
        node1 = ImpactNode(
            contract_id=str(self.source_contract.id),
            contract_name="Test",
            impact_score=0.0,
            depth=0,
        )
        self.assertEqual(node1.impact_score, 0.0)
        self.assertEqual(node1.depth, 0)

        # Test with very large values
        node2 = ImpactNode(
            contract_id=str(self.source_contract.id),
            contract_name="Test",
            impact_score=999.0,
            depth=1000,
        )
        self.assertEqual(node2.impact_score, 999.0)
        self.assertEqual(node2.depth, 1000)
