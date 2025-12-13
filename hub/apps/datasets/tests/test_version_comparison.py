"""
Unit tests for Version Comparison

Tests for schema diff visualization, data diff, and side-by-side comparison.
"""
import pytest
from django.test import TestCase

from hub.apps.datasets.models import Dataset
from hub.apps.datasets.version_comparison import (
    VersionComparisonService,
    CompatibilityLevel
)
from hub.apps.datasets.versioning import VersionHistoryManager
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.files.models import File, FileStatus


pytestmark = pytest.mark.django_db(transaction=True)


class VersionComparisonServiceTest(TestCase):
    """Test VersionComparisonService"""
    
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
        
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )
        
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
    
    def test_compare_versions_no_changes(self):
        """Test comparing versions with no changes"""
        v1 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={
                "fields": [
                    {"name": "col1", "data_type": "string", "nullable": True}
                ]
            },
            row_count=100,
            format="CSV",
            version=1,
            created_by=self.user
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
            created_by=self.user
        )
        
        v2 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=file2,
            schema_json={
                "fields": [
                    {"name": "col1", "data_type": "string", "nullable": True}
                ]
            },
            row_count=100,
            format="CSV",
            version=2,
            created_by=self.user
        )
        VersionHistoryManager.create_version(v2, parent_version=v1, semantic_version="1.0.1", is_current=True)
        
        comparison = VersionComparisonService.compare_versions(v1, v2)
        
        self.assertEqual(comparison.old_version.id, v1.id)
        self.assertEqual(comparison.new_version.id, v2.id)
        self.assertEqual(comparison.schema_diff.compatibility_level, CompatibilityLevel.FULLY_COMPATIBLE)
        self.assertIsNotNone(comparison.data_diff)
        self.assertEqual(comparison.data_diff.row_count_diff, 0)
    
    def test_compare_versions_with_schema_changes(self):
        """Test comparing versions with schema changes"""
        v1 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={
                "fields": [
                    {"name": "col1", "data_type": "string", "nullable": True}
                ]
            },
            row_count=100,
            format="CSV",
            version=1,
            created_by=self.user
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
            row_count=150,
            format="CSV",
            version=2,
            created_by=self.user
        )
        VersionHistoryManager.create_version(v2, parent_version=v1, semantic_version="1.1.0", is_current=True)
        
        comparison = VersionComparisonService.compare_versions(v1, v2)
        
        self.assertEqual(comparison.schema_diff.compatibility_level, CompatibilityLevel.BACKWARD_COMPATIBLE)
        self.assertGreater(len(comparison.schema_diff.changes), 0)
        self.assertIsNotNone(comparison.data_diff)
        self.assertEqual(comparison.data_diff.row_count_diff, 50)
        self.assertIn('col2', comparison.data_diff.field_statistics)
    
    def test_compare_versions_data_diff(self):
        """Test data diff calculation"""
        v1 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={
                "fields": [
                    {"name": "col1", "data_type": "string", "nullable": True, "sample_values": ["a", "b"]}
                ]
            },
            sample_data_json=[{"col1": "a"}, {"col1": "b"}],
            row_count=100,
            format="CSV",
            version=1,
            created_by=self.user
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
            created_by=self.user
        )
        
        v2 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=file2,
            schema_json={
                "fields": [
                    {"name": "col1", "data_type": "string", "nullable": True, "sample_values": ["x", "y"]}
                ]
            },
            sample_data_json=[{"col1": "x"}, {"col1": "y"}],
            row_count=200,
            format="CSV",
            version=2,
            created_by=self.user
        )
        VersionHistoryManager.create_version(v2, parent_version=v1, semantic_version="1.0.1", is_current=True)
        
        comparison = VersionComparisonService.compare_versions(v1, v2, include_data_diff=True)
        
        self.assertIsNotNone(comparison.data_diff)
        self.assertEqual(comparison.data_diff.row_count_diff, 100)
        self.assertEqual(comparison.data_diff.row_count_percent_change, 100.0)
        self.assertTrue(comparison.data_diff.sample_data_diff['samples_changed'])
    
    def test_side_by_side_comparison(self):
        """Test side-by-side comparison generation"""
        v1 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={
                "fields": [
                    {"name": "col1", "data_type": "string", "nullable": True}
                ]
            },
            row_count=100,
            format="CSV",
            version=1,
            semantic_version="1.0.0",
            created_by=self.user
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
            row_count=150,
            format="CSV",
            version=2,
            semantic_version="1.1.0",
            created_by=self.user
        )
        VersionHistoryManager.create_version(v2, parent_version=v1, semantic_version="1.1.0", is_current=True)
        
        comparison = VersionComparisonService.compare_versions(v1, v2)
        
        self.assertIn('metadata', comparison.side_by_side)
        self.assertIn('fields', comparison.side_by_side)
        self.assertIn('schema_changes', comparison.side_by_side)
        
        # Check metadata
        self.assertEqual(comparison.side_by_side['metadata']['old']['version'], 1)
        self.assertEqual(comparison.side_by_side['metadata']['new']['version'], 2)
        
        # Check fields comparison
        fields = comparison.side_by_side['fields']
        self.assertEqual(len(fields), 2)
        
        col1_field = next(f for f in fields if f['field_name'] == 'col1')
        self.assertEqual(col1_field['status'], 'unchanged')
        
        col2_field = next(f for f in fields if f['field_name'] == 'col2')
        self.assertEqual(col2_field['status'], 'added')
    
    def test_visualize_schema_diff_json(self):
        """Test schema diff visualization in JSON format"""
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
        VersionHistoryManager.create_version(v1, semantic_version="1.0.0", is_current=False)
        
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
        VersionHistoryManager.create_version(v2, parent_version=v1, semantic_version="1.1.0", is_current=True)
        
        comparison = VersionComparisonService.compare_versions(v1, v2)
        visualization = VersionComparisonService.visualize_schema_diff(
            comparison.schema_diff,
            format="json"
        )
        
        self.assertIn('compatibility_level', visualization)
        self.assertIn('summary', visualization)
        self.assertIn('changes', visualization)
        self.assertEqual(visualization['compatibility_level'], CompatibilityLevel.BACKWARD_COMPATIBLE.value)
    
    def test_visualize_schema_diff_markdown(self):
        """Test schema diff visualization in Markdown format"""
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
        VersionHistoryManager.create_version(v1, semantic_version="1.0.0", is_current=False)
        
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
        VersionHistoryManager.create_version(v2, parent_version=v1, semantic_version="1.1.0", is_current=True)
        
        comparison = VersionComparisonService.compare_versions(v1, v2)
        markdown = VersionComparisonService.visualize_schema_diff(
            comparison.schema_diff,
            format="markdown"
        )
        
        self.assertIsInstance(markdown, str)
        self.assertIn('# Schema Diff', markdown)
        self.assertIn('Compatibility Level', markdown)
        self.assertIn('Summary', markdown)
        self.assertIn('Changes', markdown)

