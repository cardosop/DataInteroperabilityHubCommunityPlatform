"""
E2E tests for Impact Analysis

End-to-end tests for complete impact analysis workflows.
"""
import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.contracts.models import Contract
from hub.apps.contracts.impact_analysis import ImpactAnalyzer
from hub.apps.contracts.impact_visualization import ImpactVisualizer
from hub.apps.contracts.impact_notifications import ImpactNotifier
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.assets.models import Asset, AssetStatus

from .conftest import E2ETestBase, get_response_data


pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


class ImpactAnalysisE2ETest(E2ETestBase):
    """E2E tests for impact analysis"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        # Create source contract (Contract model has no 'name' field; name is in hub_contract_json.info)
        self.source_contract = Contract.objects.create(
            tenant=self.tenant,
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
        
        # Create dependent contract (Contract model has no 'name' field)
        self.dependent_contract = Contract.objects.create(
            tenant=self.tenant,
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
    
    def test_complete_impact_analysis_workflow(self):
        """Test complete impact analysis workflow: analyze -> visualize -> notify"""
        # Step 1: Perform impact analysis
        analyzer = ImpactAnalyzer(max_contract_depth=10)
        impact_result = analyzer.analyze_impact(
            contract_id=str(self.source_contract.id),
            tenant_id=str(self.tenant.id)
        )
        
        self.assertNotIn("error", impact_result)
        self.assertGreater(impact_result.get("total_affected", 0), 0)
        
        # Step 2: Generate visualization
        json_graph = ImpactVisualizer.generate_impact_json(impact_result)
        self.assertIn("nodes", json_graph)
        self.assertIn("links", json_graph)
        
        # Step 3: Generate CSV export
        csv_string = ImpactVisualizer.generate_impact_csv(impact_result)
        self.assertIn("Resource Type", csv_string)
        
        # Step 4: Generate paths
        paths = ImpactVisualizer.generate_impact_paths(impact_result)
        self.assertIsInstance(paths, list)
        
        # Step 5: Test notification (would require email configuration)
        # For now, just verify the function exists and can be called
        notification_sent = ImpactNotifier.send_impact_notification(
            impact_result=impact_result,
            recipients=["test@example.com"],
            change_description="Test change",
            change_type="UPDATE"
        )
        # May be False if severity is too low, which is expected behavior
    
    def test_impact_analysis_api_workflow(self):
        """Test impact analysis via API (use direct path to avoid NoReverseMatch in E2E urlconf)."""
        base = f"/api/v1/contracts/{self.source_contract.id}/impact-analysis/"
        response = self.client.get(base)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = get_response_data(response)
        self.assertIn("nodes", data)
        self.assertIn("summary", data)

        response = self.client.get(base, {"output": "csv"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["content-type"], "text/csv")

        response = self.client.get(base, {"output": "paths"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = get_response_data(response)
        self.assertIn("paths", data)
    
    def test_impact_analysis_with_asset_criticality(self):
        """Test impact analysis with asset criticality weighting"""
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
        
        # Perform impact analysis
        analyzer = ImpactAnalyzer()
        impact_result = analyzer.analyze_impact(
            contract_id=str(self.source_contract.id),
            tenant_id=str(self.tenant.id)
        )
        
        # Check that asset criticality is included
        impact_graph = impact_result.get("impact_graph", {})
        metadata = impact_graph.get("metadata", {})
        self.assertIn("asset_criticality", metadata)

