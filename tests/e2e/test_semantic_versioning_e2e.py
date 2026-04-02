"""
E2E tests for Enhanced Semantic Versioning, Tagging, and Diff Visualization

End-to-end tests for complete workflows including semantic versioning,
version tagging, and version diff visualization.
"""
import pytest

pytestmark = pytest.mark.slow
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.datasets.models import Dataset
from hub.apps.datasets.versioning import VersionHistoryManager
from hub.apps.datasets.version_comparison import VersionComparisonService
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.files.models import File, FileStatus

from .conftest import E2ETestBase


pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


class SemanticVersioningE2ETest(E2ETestBase):
    """E2E tests for semantic versioning workflows"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        # Create asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
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
            created_by=self.user
        )
    
    def test_complete_semantic_versioning_workflow(self):
        """
        Test complete semantic versioning workflow:
        1. Create initial version (1.0.0)
        2. Add new field (1.1.0 - minor increment)
        3. Remove field (2.0.0 - major increment)
        4. Metadata-only change (2.0.1 - patch increment)
        """
        # Step 1: Create initial version
        v1 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={
                "fields": [
                    {"name": "col1", "data_type": "string", "nullable": True}
                ]
            },
            format="CSV",
            version=1,
            created_by=self.user
        )
        VersionHistoryManager.create_version(v1, is_current=True)
        
        v1.refresh_from_db()
        self.assertEqual(v1.semantic_version, "1.0.0")
        
        # Step 2: Add new field (minor increment)
        file2 = File.objects.create(
            tenant=self.tenant,
            name="test2.csv",
            content_type="text/csv",
            size=2000,
            status=FileStatus.ACTIVE,
            storage_path="test/test2.csv",
            content_sha256="def456",
            created_by=self.user
        )
        
        v2 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=file2,
            schema_json={
                "fields": [
                    {"name": "col1", "data_type": "string", "nullable": True},
                    {"name": "col2", "data_type": "integer", "nullable": True}
                ]
            },
            format="CSV",
            version=2,
            created_by=self.user
        )
        VersionHistoryManager.create_version(v2, parent_version=v1, is_current=True)
        
        v2.refresh_from_db()
        self.assertEqual(v2.semantic_version, "1.1.0")  # Minor increment
        
        # Step 3: Remove field (major increment)
        file3 = File.objects.create(
            tenant=self.tenant,
            name="test3.csv",
            content_type="text/csv",
            size=3000,
            status=FileStatus.ACTIVE,
            storage_path="test/test3.csv",
            content_sha256="ghi789",
            created_by=self.user
        )
        
        v3 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=file3,
            schema_json={
                "fields": [
                    {"name": "col1", "data_type": "string", "nullable": True}
                ]
            },
            format="CSV",
            version=3,
            created_by=self.user
        )
        VersionHistoryManager.create_version(v3, parent_version=v2, is_current=True)
        
        v3.refresh_from_db()
        self.assertEqual(v3.semantic_version, "2.0.0")  # Major increment
        
        # Step 4: Metadata-only change (patch increment)
        v4 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=file3,  # Same file
            schema_json={
                "fields": [
                    {"name": "col1", "data_type": "string", "nullable": True}
                ]
            },
            row_count=100,  # Same schema
            format="CSV",
            version=4,
            created_by=self.user
        )
        VersionHistoryManager.create_version(v4, parent_version=v3, is_current=True)
        
        v4.refresh_from_db()
        self.assertEqual(v4.semantic_version, "2.0.1")  # Patch increment


class VersionTaggingE2ETest(E2ETestBase):
    """E2E tests for version tagging workflows"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        # Create asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
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
            created_by=self.user
        )
    
    def test_complete_tagging_workflow(self):
        """
        Test complete version tagging workflow:
        1. Create versions with tags
        2. Add/remove tags dynamically
        3. Query by tags (any/all)
        4. Use tags for version selection
        """
        # Step 1: Create versions with initial tags
        v1 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user
        )
        VersionHistoryManager.create_version(
            v1,
            version_tags=["production", "stable"],
            is_current=False
        )
        
        file2 = File.objects.create(
            tenant=self.tenant,
            name="test2.csv",
            content_type="text/csv",
            size=2000,
            status=FileStatus.ACTIVE,
            storage_path="test/test2.csv",
            content_sha256="def456",
            created_by=self.user
        )
        
        v2 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=file2,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=2,
            created_by=self.user
        )
        VersionHistoryManager.create_version(
            v2,
            parent_version=v1,
            version_tags=["staging"],
            is_current=True
        )
        
        # Step 2: Add tags dynamically
        VersionHistoryManager.add_version_tag(v2, "testing")
        v2.refresh_from_db()
        self.assertIn("testing", v2.version_tags)
        
        # Step 3: Query by tags (any match)
        production_versions = VersionHistoryManager.get_versions_by_tags(
            self.asset.id,
            self.tenant.id,
            ["production"],
            match_all=False
        )
        self.assertEqual(len(production_versions), 1)
        self.assertEqual(production_versions[0].id, v1.id)
        
        # Step 4: Query by tags (all match)
        production_stable_versions = VersionHistoryManager.get_versions_by_tags(
            self.asset.id,
            self.tenant.id,
            ["production", "stable"],
            match_all=True
        )
        self.assertEqual(len(production_stable_versions), 1)
        self.assertEqual(production_stable_versions[0].id, v1.id)
        
        # Step 5: Remove tag
        VersionHistoryManager.remove_version_tag(v2, "testing")
        v2.refresh_from_db()
        self.assertNotIn("testing", v2.version_tags)
        
        # Step 6: Set tags (replace)
        VersionHistoryManager.set_version_tags(v2, ["production", "stable"])
        v2.refresh_from_db()
        self.assertEqual(set(v2.version_tags), {"production", "stable"})


class VersionDiffVisualizationE2ETest(E2ETestBase):
    """E2E tests for version diff visualization workflows"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        # Create asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
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
            created_by=self.user
        )
    
    def test_complete_diff_visualization_workflow(self):
        """
        Test complete version diff visualization workflow:
        1. Create versions with schema and data changes
        2. Compare versions
        3. Visualize schema diff in multiple formats
        4. Visualize data diff in multiple formats
        5. Generate complete version diff visualization
        """
        # Step 1: Create old version
        v1 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={
                "fields": [
                    {"name": "col1", "data_type": "string", "nullable": True}
                ]
            },
            sample_data_json=[{"col1": "a"}, {"col1": "b"}],
            row_count=100,
            format="CSV",
            version=1,
            created_by=self.user
        )
        VersionHistoryManager.create_version(v1, semantic_version="1.0.0", is_current=False)
        
        # Step 2: Create new version with changes
        file2 = File.objects.create(
            tenant=self.tenant,
            name="test2.csv",
            content_type="text/csv",
            size=2000,
            status=FileStatus.ACTIVE,
            storage_path="test/test2.csv",
            content_sha256="def456",
            created_by=self.user
        )
        
        v2 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=file2,
            schema_json={
                "fields": [
                    {"name": "col1", "data_type": "string", "nullable": True},
                    {"name": "col2", "data_type": "integer", "nullable": True}
                ]
            },
            sample_data_json=[{"col1": "x", "col2": 1}, {"col1": "y", "col2": 2}],
            row_count=200,
            format="CSV",
            version=2,
            created_by=self.user
        )
        VersionHistoryManager.create_version(v2, parent_version=v1, semantic_version="1.1.0", is_current=True)
        
        # Step 3: Compare versions
        comparison = VersionComparisonService.compare_versions(v1, v2, include_data_diff=True)
        
        # Verify comparison structure
        self.assertEqual(comparison.old_version.id, v1.id)
        self.assertEqual(comparison.new_version.id, v2.id)
        self.assertIsNotNone(comparison.schema_diff)
        self.assertIsNotNone(comparison.data_diff)
        self.assertIn('fields', comparison.side_by_side)
        
        # Step 4: Visualize schema diff in multiple formats
        schema_diff_json = VersionComparisonService.visualize_schema_diff(
            comparison.schema_diff,
            format="json"
        )
        self.assertIn('compatibility_level', schema_diff_json)
        self.assertIn('changes', schema_diff_json)
        
        schema_diff_markdown = VersionComparisonService.visualize_schema_diff(
            comparison.schema_diff,
            format="markdown"
        )
        self.assertIsInstance(schema_diff_markdown, str)
        self.assertIn('Schema Diff', schema_diff_markdown)
        
        schema_diff_html = VersionComparisonService.visualize_schema_diff(
            comparison.schema_diff,
            format="html"
        )
        self.assertIsInstance(schema_diff_html, str)
        self.assertIn('schema-diff', schema_diff_html)
        
        # Step 5: Visualize data diff in multiple formats
        data_diff_json = VersionComparisonService.visualize_data_diff(
            comparison.data_diff,
            format="json"
        )
        self.assertIn('row_count_diff', data_diff_json)
        self.assertIn('field_statistics', data_diff_json)
        
        data_diff_markdown = VersionComparisonService.visualize_data_diff(
            comparison.data_diff,
            format="markdown"
        )
        self.assertIsInstance(data_diff_markdown, str)
        self.assertIn('Data Diff', data_diff_markdown)
        
        data_diff_html = VersionComparisonService.visualize_data_diff(
            comparison.data_diff,
            format="html"
        )
        self.assertIsInstance(data_diff_html, str)
        self.assertIn('data-diff', data_diff_html)
        
        # Step 6: Generate complete version diff visualization
        version_diff_json = VersionComparisonService.visualize_version_diff(
            comparison,
            format="json"
        )
        self.assertIn('metadata', version_diff_json)
        self.assertIn('schema_diff', version_diff_json)
        self.assertIn('data_diff', version_diff_json)
        self.assertIn('side_by_side_fields', version_diff_json)
        
        version_diff_markdown = VersionComparisonService.visualize_version_diff(
            comparison,
            format="markdown"
        )
        self.assertIsInstance(version_diff_markdown, str)
        self.assertIn('Version Comparison', version_diff_markdown)
        self.assertIn('Schema Diff', version_diff_markdown)
        self.assertIn('Data Diff', version_diff_markdown)
        
        version_diff_html = VersionComparisonService.visualize_version_diff(
            comparison,
            format="html"
        )
        self.assertIsInstance(version_diff_html, str)
        self.assertIn('version-diff', version_diff_html)

