"""
Integration tests for Version Impact Analysis

Tests for impact analysis in the context of complete workflows.
"""

import uuid

import pytest

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract, ContractStatus, OriginalFormat, OriginalSpecType
from hub.apps.datasets.models import Dataset
from hub.apps.datasets.tests.test_base import DatasetsAPITestBase
from hub.apps.datasets.version_impact import VersionImpactAnalyzer
from hub.apps.datasets.versioning import VersionHistoryManager

pytestmark = pytest.mark.django_db(transaction=True)


class VersionImpactIntegrationTest(DatasetsAPITestBase):
    """Integration tests for version impact analysis"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

    def test_version_impact_analysis_workflow(self):
        """Test complete version impact analysis workflow"""
        # Create contract
        Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            version=1,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"apiVersion": "v3", "kind": "DataContract"}',
            hub_contract_version="1.0.0",
            hub_contract_json={"info": {"name": "Test Contract"}},
            created_by=self.user,
        )

        # Create dataset version
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(dataset, is_current=True)

        # Analyze impact
        analyzer = VersionImpactAnalyzer()
        result = analyzer.analyze_impact(str(dataset.id))

        # Verify impact analysis
        self.assertIn("source", result)
        self.assertIn("impact_graph", result)
        self.assertIn("summary", result)
        self.assertGreater(result["summary"]["total_assets"], 0)
        self.assertGreater(result["summary"]["total_contracts"], 0)

    # ========== SUCCESS SCENARIOS ==========

    def test_version_impact_integration_success(self):
        """Test successful version impact integration (success scenario)"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=1,
            created_by=self.user,
        )

        analyzer = VersionImpactAnalyzer()
        result = analyzer.analyze_impact(str(dataset.id))

        # Should return impact analysis
        self.assertIsNotNone(result)
        self.assertIn("source", result)

    # ========== FAILURE SCENARIOS ==========

    def test_version_impact_integration_failure_nonexistent_dataset(self):
        """Test version impact integration with non-existent dataset (failure scenario)"""

        fake_dataset_id = str(uuid.uuid4())

        analyzer = VersionImpactAnalyzer()

        # Non-existent dataset returns error in result dict
        result = analyzer.analyze_impact(fake_dataset_id)
        self.assertIn("error", result)

    # ========== EDGE CASES ==========

    def test_version_impact_integration_edge_case_no_downstream(self):
        """Test version impact integration with no downstream dependencies (edge case)"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=1,
            created_by=self.user,
        )

        analyzer = VersionImpactAnalyzer(max_depth=1)
        result = analyzer.analyze_impact(str(dataset.id))

        # Should handle no downstream gracefully
        self.assertIsNotNone(result)
        self.assertIn("impact_graph", result)

    def test_version_impact_integration_edge_case_zero_max_depth(self):
        """Test version impact integration with zero max_depth (edge case)"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=1,
            created_by=self.user,
        )

        analyzer = VersionImpactAnalyzer(max_depth=0)
        result = analyzer.analyze_impact(str(dataset.id))

        # Should handle zero depth gracefully
        self.assertIsNotNone(result)

    # ========== ERROR HANDLING ==========

    def test_version_impact_integration_create_succeeds(self):
        """Test error handling in version impact integration"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=1,
            created_by=self.user,
        )

        analyzer = VersionImpactAnalyzer()

        # Should handle errors gracefully
        try:
            result = analyzer.analyze_impact(str(dataset.id))
            # Should return result
            self.assertIsNotNone(result)
        except Exception:
            # If raises exception, that's a problem
            self.fail("analyze_impact should handle errors gracefully")
