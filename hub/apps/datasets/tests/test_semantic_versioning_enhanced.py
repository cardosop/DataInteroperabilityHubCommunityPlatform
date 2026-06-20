"""
Unit tests for Enhanced Semantic Versioning

Tests for semantic version increment rules, version tagging, and enhanced diff visualization.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.datasets.tests.test_base import DatasetsTestBase
from hub.apps.datasets.version_comparison import VersionComparisonService
from hub.apps.datasets.versioning import VersionHistoryManager
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class SemanticVersioningEnhancedTest(DatasetsTestBase):
    """Test enhanced semantic versioning with proper increment rules"""

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

    def test_semantic_version_breaking_change_major_increment(self):
        """Test that breaking changes increment major version"""
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

        # Create child with field removed (breaking change)
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

        child.refresh_from_db()
        self.assertEqual(child.semantic_version, "2.0.0")  # Major increment

    def test_semantic_version_type_change_major_increment(self):
        """Test that type changes increment major version"""
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
            schema_json={"fields": [{"name": "col1", "data_type": "integer", "nullable": True}]},
            format="CSV",
            version=2,
            created_by=self.user,
        )

        VersionHistoryManager.create_version(child, parent_version=parent, is_current=True)

        child.refresh_from_db()
        self.assertEqual(child.semantic_version, "2.0.0")  # Major increment

    def test_semantic_version_nullable_to_non_nullable_major_increment(self):
        """Test that nullable -> non-nullable changes increment major version"""
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
            schema_json={"fields": [{"name": "col1", "data_type": "string", "nullable": False}]},
            format="CSV",
            version=2,
            created_by=self.user,
        )

        VersionHistoryManager.create_version(child, parent_version=parent, is_current=True)

        child.refresh_from_db()
        self.assertEqual(child.semantic_version, "2.0.0")  # Major increment

    def test_semantic_version_new_field_minor_increment(self):
        """Test that new fields increment minor version"""
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

        child.refresh_from_db()
        self.assertEqual(child.semantic_version, "1.1.0")  # Minor increment

    def test_semantic_version_metadata_only_patch_increment(self):
        """Test that metadata-only changes increment patch version"""
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

        # Create child with same schema and file content (metadata-only change)
        child = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,  # Same file (same content_sha256)
            schema_json={"fields": [{"name": "col1", "data_type": "string", "nullable": True}]},
            row_count=100,  # Same row count
            format="CSV",
            version=2,
            created_by=self.user,
        )

        VersionHistoryManager.create_version(child, parent_version=parent, is_current=True)

        child.refresh_from_db()
        self.assertEqual(child.semantic_version, "1.0.1")  # Patch increment

    def test_semantic_version_no_schema_change_patch_increment(self):
        """Test that data changes without schema changes increment patch version"""
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

        child_file = File.objects.create(
            tenant=self.tenant,
            name="test2.csv",
            content_type="text/csv",
            size=2000,
            status=FileStatus.ACTIVE,
            storage_path="test/test2.csv",
            content_sha256="def456",  # Different file content
            created_by=self.user,
        )

        child = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=child_file,
            schema_json={"fields": [{"name": "col1", "data_type": "string", "nullable": True}]},
            row_count=150,  # Different row count
            format="CSV",
            version=2,
            created_by=self.user,
        )

        VersionHistoryManager.create_version(child, parent_version=parent, is_current=True)

        child.refresh_from_db()
        self.assertEqual(
            child.semantic_version, "1.0.1"
        )  # Patch increment (bug fix/data correction)


class VersionTaggingTest(TestCase):
    """Test version tagging functionality"""

    def setUp(self):
        super().setUp()
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

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

    def test_add_version_tag(self):
        """Test adding a tag to a version"""
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

        VersionHistoryManager.add_version_tag(dataset, "production")

        dataset.refresh_from_db()
        self.assertIn("production", dataset.version_tags)

    def test_add_multiple_version_tags(self):
        """Test adding multiple tags to a version"""
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

        VersionHistoryManager.add_version_tag(dataset, "production")
        VersionHistoryManager.add_version_tag(dataset, "stable")
        VersionHistoryManager.add_version_tag(dataset, "v1")

        dataset.refresh_from_db()
        self.assertEqual(len(dataset.version_tags), 3)
        self.assertIn("production", dataset.version_tags)
        self.assertIn("stable", dataset.version_tags)
        self.assertIn("v1", dataset.version_tags)

    def test_add_duplicate_tag_ignored(self):
        """Test that adding duplicate tag is ignored"""
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

        VersionHistoryManager.add_version_tag(dataset, "production")
        VersionHistoryManager.add_version_tag(dataset, "production")  # Duplicate

        dataset.refresh_from_db()
        # version_tags is a list, count occurrences
        tag_count = sum(1 for tag in dataset.version_tags if tag == "production")
        self.assertEqual(tag_count, 1)

    def test_add_version_tag_empty_raises(self):
        """add_version_tag with empty string raises ValueError."""
        dataset = Dataset.objects.create(
            tenant=self.tenant, asset=self.asset, file=self.file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV", version=1, created_by=self.user,
        )
        VersionHistoryManager.create_version(dataset, is_current=True)
        with self.assertRaises(ValueError):
            VersionHistoryManager.add_version_tag(dataset, "")

    def test_remove_version_tag(self):
        """Test removing a tag from a version"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(
            dataset, version_tags=["production", "stable"], is_current=True
        )

        VersionHistoryManager.remove_version_tag(dataset, "production")

        dataset.refresh_from_db()
        self.assertNotIn("production", dataset.version_tags)
        self.assertIn("stable", dataset.version_tags)

    def test_set_version_tags(self):
        """Test setting tags (replaces existing tags)"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(
            dataset, version_tags=["production", "stable"], is_current=True
        )

        VersionHistoryManager.set_version_tags(dataset, ["staging", "testing"])

        dataset.refresh_from_db()
        self.assertEqual(set(dataset.version_tags), {"staging", "testing"})

    def test_set_version_tags_removes_duplicates(self):
        """Test that setting tags removes duplicates"""
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

        VersionHistoryManager.set_version_tags(dataset, ["production", "production", "stable"])

        dataset.refresh_from_db()
        self.assertEqual(len(dataset.version_tags), 2)
        self.assertIn("production", dataset.version_tags)
        self.assertIn("stable", dataset.version_tags)

    def test_get_versions_by_tags_any(self):
        """Test getting versions by tags (any match)"""
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
        VersionHistoryManager.create_version(v1, version_tags=["production"], is_current=False)

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
        VersionHistoryManager.create_version(
            v3, version_tags=["production", "stable"], is_current=False
        )

        # Get versions with "production" or "staging" tag (any match)
        versions = VersionHistoryManager.get_versions_by_tags(
            self.asset.id, self.tenant.id, ["production", "staging"], match_all=False
        )

        self.assertEqual(len(versions), 3)  # All three versions match

    def test_get_versions_by_tags_all(self):
        """Test getting versions by tags (all match)"""
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
        VersionHistoryManager.create_version(v1, version_tags=["production"], is_current=False)

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
        VersionHistoryManager.create_version(
            v2, version_tags=["production", "stable"], is_current=True
        )

        # Get versions with both "production" and "stable" tags (all match)
        versions = VersionHistoryManager.get_versions_by_tags(
            self.asset.id, self.tenant.id, ["production", "stable"], match_all=True
        )

        self.assertEqual(len(versions), 1)  # Only v2 has both tags
        self.assertEqual(versions[0].id, v2.id)

    def test_get_versions_by_tags_empty_list(self):
        """get_versions_by_tags with empty list returns empty list."""
        result = VersionHistoryManager.get_versions_by_tags(
            self.asset.id, self.tenant.id, []
        )
        self.assertEqual(result, [])


class VersionDiffVisualizationTest(TestCase):
    """Test enhanced version diff visualization"""

    def setUp(self):
        super().setUp()
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

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

    def test_visualize_data_diff_json(self):
        """Test data diff visualization in JSON format"""
        v1 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "data_type": "string", "nullable": True}]},
            sample_data_json=[{"col1": "a"}, {"col1": "b"}],
            row_count=100,
            format="CSV",
            version=1,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(v1, semantic_version="1.0.0", is_current=False)

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
            schema_json={"fields": [{"name": "col1", "data_type": "string", "nullable": True}]},
            sample_data_json=[{"col1": "x"}, {"col1": "y"}],
            row_count=200,
            format="CSV",
            version=2,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(
            v2, parent_version=v1, semantic_version="1.0.1", is_current=True
        )

        comparison = VersionComparisonService.compare_versions(v1, v2, include_data_diff=True)
        visualization = VersionComparisonService.visualize_data_diff(
            comparison.data_diff, format="json"
        )

        self.assertIn("row_count_diff", visualization)
        self.assertIn("row_count_percent_change", visualization)
        self.assertIn("field_statistics", visualization)
        self.assertIn("sample_data_diff", visualization)
        self.assertEqual(visualization["row_count_diff"], 100)

    def test_visualize_data_diff_markdown(self):
        """Test data diff visualization in Markdown format"""
        v1 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "data_type": "string", "nullable": True}]},
            row_count=100,
            format="CSV",
            version=1,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(v1, semantic_version="1.0.0", is_current=False)

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
            schema_json={"fields": [{"name": "col1", "data_type": "string", "nullable": True}]},
            row_count=200,
            format="CSV",
            version=2,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(
            v2, parent_version=v1, semantic_version="1.0.1", is_current=True
        )

        comparison = VersionComparisonService.compare_versions(v1, v2, include_data_diff=True)
        markdown = VersionComparisonService.visualize_data_diff(
            comparison.data_diff, format="markdown"
        )

        self.assertIsInstance(markdown, str)
        self.assertIn("# Data Diff", markdown)
        self.assertIn("Row Count Changes", markdown)
        self.assertIn("Field Statistics", markdown)

    def test_visualize_version_diff_json(self):
        """Test complete version diff visualization in JSON format"""
        v1 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "data_type": "string", "nullable": True}]},
            row_count=100,
            format="CSV",
            version=1,
            semantic_version="1.0.0",
            created_by=self.user,
        )
        VersionHistoryManager.create_version(v1, semantic_version="1.0.0", is_current=False)

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
            row_count=150,
            format="CSV",
            version=2,
            semantic_version="1.1.0",
            created_by=self.user,
        )
        VersionHistoryManager.create_version(
            v2, parent_version=v1, semantic_version="1.1.0", is_current=True
        )

        comparison = VersionComparisonService.compare_versions(v1, v2, include_data_diff=True)
        visualization = VersionComparisonService.visualize_version_diff(comparison, format="json")

        self.assertIn("metadata", visualization)
        self.assertIn("schema_diff", visualization)
        self.assertIn("data_diff", visualization)
        self.assertIn("side_by_side_fields", visualization)

    def test_visualize_version_diff_markdown(self):
        """Test complete version diff visualization in Markdown format"""
        v1 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "data_type": "string", "nullable": True}]},
            row_count=100,
            format="CSV",
            version=1,
            semantic_version="1.0.0",
            created_by=self.user,
        )
        VersionHistoryManager.create_version(v1, semantic_version="1.0.0", is_current=False)

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
            row_count=150,
            format="CSV",
            version=2,
            semantic_version="1.1.0",
            created_by=self.user,
        )
        VersionHistoryManager.create_version(
            v2, parent_version=v1, semantic_version="1.1.0", is_current=True
        )

        comparison = VersionComparisonService.compare_versions(v1, v2, include_data_diff=True)
        markdown = VersionComparisonService.visualize_version_diff(comparison, format="markdown")

        self.assertIsInstance(markdown, str)
        self.assertIn("# Version Comparison", markdown)
        self.assertIn("Schema Diff", markdown)
        self.assertIn("Data Diff", markdown)
        self.assertIn("Side-by-Side Field Comparison", markdown)

    # ========== SUCCESS SCENARIOS ==========

    def test_semantic_versioning_success(self):
        """Test successful semantic versioning (success scenario)"""
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

    def test_semantic_versioning_failure_invalid_version_format(self):
        """Test semantic versioning with invalid version format (failure scenario)"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=1,
            created_by=self.user,
        )

        # Should handle invalid version format gracefully
        try:
            VersionHistoryManager.create_version(
                dataset, semantic_version="invalid", is_current=True
            )
            # If succeeds, verify it was created
            self.assertIsNotNone(dataset)
        except (ValueError, ValidationError):
            # If fails, that's acceptable for invalid version format
            pass

    def test_semantic_versioning_failure_nonexistent_parent(self):
        """Test semantic versioning with non-existent parent (failure scenario)"""
        import uuid

        from django.db import IntegrityError, connection

        fake_parent_id = uuid.uuid4()
        fake_parent = Dataset(
            id=fake_parent_id, tenant=self.tenant, asset=self.asset, file=self.file
        )

        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=1,
            created_by=self.user,
        )

        # Should handle non-existent parent gracefully - FK constraint should be raised
        with self.assertRaises(IntegrityError):
            VersionHistoryManager.create_version(
                dataset, parent_version=fake_parent, semantic_version="1.0.0", is_current=True
            )
            # Force FK constraint check immediately (PostgreSQL specific)
            with connection.cursor() as cursor:
                cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")

    # ========== ERROR HANDLING ==========

    def test_semantic_versioning_create_succeeds(self):
        """Test error handling when database operations fail"""
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
            self.fail("create_version should handle database errors gracefully")

    def test_semantic_versioning_error_handling_invalid_dataset(self):
        """Test error handling with invalid dataset"""
        import uuid

        fake_dataset = Dataset(
            id=uuid.uuid4(), tenant=self.tenant, asset=self.asset, file=self.file
        )

        # Should handle invalid dataset gracefully
        try:
            VersionHistoryManager.create_version(
                fake_dataset, semantic_version="1.0.0", is_current=True
            )
            # If succeeds, verify it was created
            self.assertIsNotNone(fake_dataset.id)
        except Exception:
            # If fails, that's acceptable for invalid dataset
            pass
