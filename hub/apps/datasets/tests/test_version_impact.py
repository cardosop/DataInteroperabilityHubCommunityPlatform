"""
Unit tests for Version Impact Analysis

Tests for analyzing impact of dataset version changes on assets and downstream systems.
"""
import uuid

import pytest
from django.core.exceptions import ValidationError as DjangoValidationError

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract, ContractStatus, OriginalFormat, OriginalSpecType
from hub.apps.datasets.models import Dataset
from hub.apps.datasets.tests.test_base import DatasetsTestBase
from hub.apps.datasets.version_impact import VersionImpactAnalyzer
from hub.apps.datasets.versioning import VersionHistoryManager
from hub.apps.files.models import File, FileStatus

pytestmark = pytest.mark.django_db(transaction=True)


class VersionImpactAnalyzerTest(DatasetsTestBase):
    """Test VersionImpactAnalyzer"""

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

    def test_analyze_impact_basic(self):
        """Test basic impact analysis"""
        # Create dataset
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

        self.assertIn("source", result)
        self.assertIn("impact_graph", result)
        self.assertIn("summary", result)
        self.assertEqual(result["source"]["dataset_id"], str(dataset.id))

    def test_analyze_impact_with_contract(self):
        """Test impact analysis with contract"""
        # Create contract for asset
        contract = Contract.objects.create(
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

        # Create dataset
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

        # Should find asset and contract
        self.assertGreater(result["summary"]["total_assets"], 0)
        self.assertGreater(result["summary"]["total_contracts"], 0)

    def test_analyze_impact_severity_scoring(self):
        """Test impact severity scoring"""
        # Create asset with ACTIVE status (higher criticality)
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="critical-asset",
            name="Critical Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        file2 = File.objects.create(
            tenant=self.tenant,
            name="test2.csv",
            content_type="text/csv",
            size=2000,
            status=FileStatus.ACTIVE,
            storage_path="test/test2.csv",
            content_sha256="def456",
            created_by=self.user,
        )

        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=asset,
            file=file2,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(dataset, is_current=True)

        # Analyze impact
        analyzer = VersionImpactAnalyzer()
        result = analyzer.analyze_impact(str(dataset.id))

        # Check that impact graph has severity scores
        impact_graph = result["impact_graph"]
        self.assertIn("severity", impact_graph)
        self.assertIn("impact_score", impact_graph)

    def test_analyze_impact_summary(self):
        """Test impact analysis summary"""
        # Create dataset with contract
        contract = Contract.objects.create(
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

        summary = result["summary"]
        self.assertIn("total_assets", summary)
        self.assertIn("total_contracts", summary)
        self.assertIn("high_impact_count", summary)
        self.assertIn("medium_impact_count", summary)
        self.assertIn("low_impact_count", summary)

    def test_analyze_impact_depth_limit(self):
        """Test impact analysis depth limit"""
        # Create multiple versions
        v1 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(v1, is_current=False)

        file2 = File.objects.create(
            tenant=self.tenant,
            name="test2.csv",
            content_type="text/csv",
            size=2000,
            status=FileStatus.ACTIVE,
            storage_path="test/test2.csv",
            content_sha256="def456",
            created_by=self.user,
        )

        v2 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=file2,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=2,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(v2, parent_version=v1, is_current=True)

        # Analyze with depth limit
        analyzer = VersionImpactAnalyzer(max_depth=2)
        result = analyzer.analyze_impact(str(v2.id))

        # Check that depth is limited
        self.assertLessEqual(result["max_depth"], 2)

    # ========== SUCCESS SCENARIOS ==========

    def test_version_impact_success(self):
        """Test successful version impact analysis (success scenario)"""
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

    def test_version_impact_failure_nonexistent_dataset(self):
        """Test version impact analysis with non-existent dataset (failure scenario)"""
        import uuid

        fake_dataset_id = str(uuid.uuid4())

        analyzer = VersionImpactAnalyzer()

        # Non-existent dataset — the analyzer returns a dict with an error
        # key rather than raising.
        result = analyzer.analyze_impact(fake_dataset_id)
        self.assertIsNotNone(result,
            "analyze_impact must return a result dict for non-existent dataset_id")
        self.assertIn("error", result,
            "analyze_impact must include an 'error' key for non-existent dataset")

    def test_version_impact_failure_invalid_dataset_id(self):
        """Test version impact analysis with invalid dataset_id (failure scenario)"""
        analyzer = VersionImpactAnalyzer()

        # Should handle invalid dataset_id gracefully - Django's UUIDField raises ValidationError
        with self.assertRaises(DjangoValidationError) as cm:
            analyzer.analyze_impact("invalid-id")
        
        # Django's UUIDField validation error should be raised
        self.assertIn("not a valid UUID", str(cm.exception))

    # ========== EDGE CASES ==========

    def test_version_impact_edge_case_no_downstream(self):
        """Test version impact analysis with no downstream dependencies (edge case)"""
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

    def test_version_impact_edge_case_zero_max_depth(self):
        """Test version impact analysis with zero max_depth (edge case)"""
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

    def test_analyze_impact_valid_dataset(self):
        """Test error handling in version impact analysis"""
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
        self.assertIsNotNone(result,
            "analyze_impact must return a result for a valid persisted dataset")
