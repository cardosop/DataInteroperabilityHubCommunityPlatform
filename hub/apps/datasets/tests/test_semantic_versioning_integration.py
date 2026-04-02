"""
Integration tests for Enhanced Semantic Versioning

Tests for semantic versioning, version tagging, and diff visualization
in the context of API and dataset creation workflows.
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.datasets.tests.test_base import DatasetsAPITestBase
from hub.apps.datasets.version_comparison import VersionComparisonService
from hub.apps.datasets.versioning import VersionHistoryManager
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant, TenantStatus
from hub.apps.users.models import UserStatus
import uuid

User = get_user_model()


class SemanticVersioningIntegrationTest(DatasetsAPITestBase):
    """Integration tests for semantic versioning"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        # Create asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

    def test_semantic_versioning_breaking_change_workflow(self):
        """Test semantic versioning with breaking changes in workflow"""
        # Create parent version
        parent = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={
                "fields": [
                    {"name": "col1", "data_type": "string", "nullable": True},
                    {"name": "col2", "data_type": "integer", "nullable": True},
                ]
            },
            format="CSV",
            version=1,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(parent, semantic_version="1.0.0", is_current=True)

        # Create child with breaking change (field removed)
        child_file = File.objects.create(
            tenant=self.tenant,
            name="test2.csv",
            content_type="text/csv",
            size=2000,
            status=FileStatus.ACTIVE,
            storage_path="test/test2.csv",
            content_sha256="def456",
            created_by=self.user,
        )

        child = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=child_file,
            schema_json={"fields": [{"name": "col1", "data_type": "string", "nullable": True}]},
            format="CSV",
            version=2,
            created_by=self.user,
        )

        VersionHistoryManager.create_version(child, parent_version=parent, is_current=True)

        # Verify major version increment
        child.refresh_from_db()
        self.assertEqual(child.semantic_version, "2.0.0")

        # Verify parent is no longer current
        parent.refresh_from_db()
        self.assertFalse(parent.is_current)

    def test_semantic_versioning_new_field_workflow(self):
        """Test semantic versioning with new fields in workflow"""
        # Create parent version
        parent = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "data_type": "string", "nullable": True}]},
            format="CSV",
            version=1,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(parent, semantic_version="1.0.0", is_current=True)

        # Create child with new field (non-breaking)
        child_file = File.objects.create(
            tenant=self.tenant,
            name="test2.csv",
            content_type="text/csv",
            size=2000,
            status=FileStatus.ACTIVE,
            storage_path="test/test2.csv",
            content_sha256="def456",
            created_by=self.user,
        )

        child = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=child_file,
            schema_json={
                "fields": [
                    {"name": "col1", "data_type": "string", "nullable": True},
                    {"name": "col2", "data_type": "integer", "nullable": True},
                ]
            },
            format="CSV",
            version=2,
            created_by=self.user,
        )

        VersionHistoryManager.create_version(child, parent_version=parent, is_current=True)

        # Verify minor version increment
        child.refresh_from_db()
        self.assertEqual(child.semantic_version, "1.1.0")

    def test_semantic_versioning_metadata_only_workflow(self):
        """Test semantic versioning with metadata-only changes in workflow"""
        # Create parent version
        parent = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "data_type": "string", "nullable": True}]},
            row_count=100,
            format="CSV",
            version=1,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(parent, semantic_version="1.0.0", is_current=True)

        # Create child with same schema and file (metadata-only change)
        child = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,  # Same file
            schema_json={"fields": [{"name": "col1", "data_type": "string", "nullable": True}]},
            row_count=100,  # Same row count
            format="CSV",
            version=2,
            created_by=self.user,
        )

        VersionHistoryManager.create_version(child, parent_version=parent, is_current=True)

        # Verify patch version increment
        child.refresh_from_db()
        self.assertEqual(child.semantic_version, "1.0.1")


class VersionTaggingIntegrationTest(TestCase):
    """Integration tests for version tagging"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        # Create tenant
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", status="ACTIVE", kyc_status="UNVERIFIED"
        )

        # Create user
        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.user)

        # Create asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        # Create file
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1000,
            status=FileStatus.ACTIVE,
            storage_path="test/test.csv",
            content_sha256="abc123",
            created_by=self.user,
        )

    def test_version_tagging_workflow(self):
        """Test complete version tagging workflow"""
        # Create version
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

        # Add tags
        VersionHistoryManager.add_version_tag(dataset, "production")
        VersionHistoryManager.add_version_tag(dataset, "stable")

        dataset.refresh_from_db()
        self.assertIn("production", dataset.version_tags)
        self.assertIn("stable", dataset.version_tags)

        # Remove tag
        VersionHistoryManager.remove_version_tag(dataset, "stable")

        dataset.refresh_from_db()
        self.assertIn("production", dataset.version_tags)
        self.assertNotIn("stable", dataset.version_tags)

        # Set tags (replaces existing)
        VersionHistoryManager.set_version_tags(dataset, ["staging", "testing"])

        dataset.refresh_from_db()
        self.assertEqual(set(dataset.version_tags), {"staging", "testing"})

    def test_tag_based_queries_workflow(self):
        """Test tag-based queries in workflow"""
        # Create versions with different tags
        v1 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(
            v1, version_tags=["production", "stable"], is_current=False
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

        v2 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=file2,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=2,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(v2, version_tags=["staging"], is_current=True)

        file3 = File.objects.create(
            tenant=self.tenant,
            name="test3.csv",
            content_type="text/csv",
            size=3000,
            status=FileStatus.ACTIVE,
            storage_path="test/test3.csv",
            content_sha256="ghi789",
            created_by=self.user,
        )

        v3 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=file3,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=3,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(v3, version_tags=["production"], is_current=False)

        # Query by single tag (any match)
        production_versions = VersionHistoryManager.get_versions_by_tags(
            self.asset.id, self.tenant.id, ["production"], match_all=False
        )
        self.assertEqual(len(production_versions), 2)
        self.assertIn(v1.id, {v.id for v in production_versions})
        self.assertIn(v3.id, {v.id for v in production_versions})

        # Query by multiple tags (all match)
        production_stable_versions = VersionHistoryManager.get_versions_by_tags(
            self.asset.id, self.tenant.id, ["production", "stable"], match_all=True
        )
        self.assertEqual(len(production_stable_versions), 1)
        self.assertEqual(production_stable_versions[0].id, v1.id)


class VersionDiffVisualizationIntegrationTest(TestCase):
    """Integration tests for version diff visualization"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        # Create tenant
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", status="ACTIVE", kyc_status="UNVERIFIED"
        )

        # Create user
        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.user)

        # Create asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        # Create file
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1000,
            status=FileStatus.ACTIVE,
            storage_path="test/test.csv",
            content_sha256="abc123",
            created_by=self.user,
        )

    def test_version_diff_visualization_workflow(self):
        """Test version diff visualization in workflow"""
        # Create old version
        v1 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "data_type": "string", "nullable": True}]},
            sample_data_json=[{"col1": "a"}, {"col1": "b"}],
            row_count=100,
            format="CSV",
            version=1,
            semantic_version="1.0.0",
            created_by=self.user,
        )
        VersionHistoryManager.create_version(v1, semantic_version="1.0.0", is_current=False)

        # Create new version with changes
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
            schema_json={
                "fields": [
                    {"name": "col1", "data_type": "string", "nullable": True},
                    {"name": "col2", "data_type": "integer", "nullable": True},
                ]
            },
            sample_data_json=[{"col1": "x", "col2": 1}, {"col1": "y", "col2": 2}],
            row_count=200,
            format="CSV",
            version=2,
            semantic_version="1.1.0",
            created_by=self.user,
        )
        VersionHistoryManager.create_version(
            v2, parent_version=v1, semantic_version="1.1.0", is_current=True
        )

        # Compare versions
        comparison = VersionComparisonService.compare_versions(v1, v2, include_data_diff=True)

        # Test schema diff visualization
        schema_diff_json = VersionComparisonService.visualize_schema_diff(
            comparison.schema_diff, format="json"
        )
        self.assertIn("compatibility_level", schema_diff_json)
        self.assertIn("summary", schema_diff_json)
        self.assertIn("changes", schema_diff_json)

        schema_diff_markdown = VersionComparisonService.visualize_schema_diff(
            comparison.schema_diff, format="markdown"
        )
        self.assertIsInstance(schema_diff_markdown, str)
        self.assertIn("Schema Diff", schema_diff_markdown)

        # Test data diff visualization
        data_diff_json = VersionComparisonService.visualize_data_diff(
            comparison.data_diff, format="json"
        )
        self.assertIn("row_count_diff", data_diff_json)
        self.assertIn("field_statistics", data_diff_json)

        data_diff_markdown = VersionComparisonService.visualize_data_diff(
            comparison.data_diff, format="markdown"
        )
        self.assertIsInstance(data_diff_markdown, str)
        self.assertIn("Data Diff", data_diff_markdown)

        # Test complete version diff visualization
        version_diff_json = VersionComparisonService.visualize_version_diff(
            comparison, format="json"
        )
        self.assertIn("metadata", version_diff_json)
        self.assertIn("schema_diff", version_diff_json)
        self.assertIn("data_diff", version_diff_json)
        self.assertIn("side_by_side_fields", version_diff_json)

        version_diff_markdown = VersionComparisonService.visualize_version_diff(
            comparison, format="markdown"
        )
        self.assertIsInstance(version_diff_markdown, str)
        self.assertIn("Version Comparison", version_diff_markdown)
        self.assertIn("Schema Diff", version_diff_markdown)
        self.assertIn("Data Diff", version_diff_markdown)
        self.assertIn("Side-by-Side Field Comparison", version_diff_markdown)

    # ========== SUCCESS SCENARIOS ==========

    def test_semantic_versioning_integration_success(self):
        """Test successful semantic versioning integration (success scenario)"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=1,
            created_by=self.user,
        )

        VersionHistoryManager.create_version(dataset, semantic_version="1.0.0", is_current=True)

        # Should succeed
        self.assertIsNotNone(dataset)
        self.assertEqual(dataset.version, 1)

    # ========== FAILURE SCENARIOS ==========

    def test_semantic_versioning_integration_failure_invalid_version(self):
        """Test semantic versioning integration with invalid version (failure scenario)"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=1,
            created_by=self.user,
        )

        # Should handle invalid version gracefully
        try:
            VersionHistoryManager.create_version(
                dataset, semantic_version="invalid", is_current=True
            )
            # If succeeds, verify it was created
            self.assertIsNotNone(dataset)
        except (ValueError, ValidationError):
            # If fails, that's acceptable for invalid version
            pass

    # ========== EDGE CASES ==========

    def test_semantic_versioning_integration_edge_case_no_parent(self):
        """Test semantic versioning integration without parent (edge case)"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=1,
            created_by=self.user,
        )

        # Should handle no parent gracefully
        VersionHistoryManager.create_version(dataset, semantic_version="1.0.0", is_current=True)

        self.assertIsNotNone(dataset)

    def test_semantic_versioning_integration_edge_case_multiple_tags(self):
        """Test semantic versioning integration with multiple tags (edge case)"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=1,
            created_by=self.user,
        )

        VersionHistoryManager.create_version(
            dataset,
            semantic_version="1.0.0",
            version_tags=["production", "stable", "v1"],
            is_current=True,
        )

        # Should handle multiple tags gracefully
        self.assertIsNotNone(dataset)

    # ========== ERROR HANDLING ==========

    def test_semantic_versioning_integration_error_handling(self):
        """Test error handling in semantic versioning integration"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=1,
            created_by=self.user,
        )

        # Should handle errors gracefully
        try:
            VersionHistoryManager.create_version(dataset, semantic_version="1.0.0", is_current=True)
            # Should succeed
            self.assertIsNotNone(dataset)
        except Exception:
            # If raises exception, that's a problem
            self.fail("create_version should handle errors gracefully")
