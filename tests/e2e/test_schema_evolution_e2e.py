"""
E2E tests for Schema Evolution and Version Comparison

End-to-end tests for complete schema evolution and comparison workflows.
"""

import pytest

pytestmark = pytest.mark.slow

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.datasets.schema_evolution import CompatibilityLevel, SchemaEvolutionTracker
from hub.apps.datasets.time_travel import TimeTravelQuery
from hub.apps.datasets.version_comparison import VersionComparisonService
from hub.apps.datasets.versioning import VersionHistoryManager
from hub.apps.files.models import File, FileStatus

from .conftest import E2ETestBase

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


class SchemaEvolutionE2ETest(E2ETestBase):
    """E2E tests for schema evolution and comparison"""

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

    def test_complete_schema_evolution_workflow(self):
        """Test complete schema evolution workflow"""
        # Step 1: Create initial version
        v1 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={
                "fields": [
                    {"name": "id", "data_type": "integer", "nullable": False},
                    {"name": "name", "data_type": "string", "nullable": True},
                ],
                "primary_key_candidates": ["id"],
            },
            row_count=100,
            format="CSV",
            version=1,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(
            v1, semantic_version="1.0.0", version_tags=["production"], is_current=True
        )

        # Verify schema version created
        self.assertTrue(hasattr(v1, "schema_version"))
        schema_v1 = v1.schema_version
        self.assertEqual(schema_v1.compatibility_level, CompatibilityLevel.FULLY_COMPATIBLE.value)

        # Step 2: Create version with new field (backward compatible)
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
                    {"name": "id", "data_type": "integer", "nullable": False},
                    {"name": "name", "data_type": "string", "nullable": True},
                    {"name": "email", "data_type": "string", "nullable": True},  # New field
                ],
                "primary_key_candidates": ["id"],
            },
            row_count=150,
            format="CSV",
            version=2,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(
            v2,
            parent_version=v1,
            semantic_version="1.1.0",
            version_tags=["staging"],
            is_current=True,
        )

        # Verify schema evolution
        schema_v2 = v2.schema_version
        self.assertEqual(
            schema_v2.compatibility_level, CompatibilityLevel.BACKWARD_COMPATIBLE.value
        )
        self.assertEqual(schema_v2.parent_schema_version, schema_v1)
        self.assertIn("FIELD_ADDED", schema_v2.change_summary)

        # Step 3: Generate change log
        change_log = SchemaEvolutionTracker.generate_change_log(v1, v2)
        self.assertEqual(
            change_log["compatibility_level"], CompatibilityLevel.BACKWARD_COMPATIBLE.value
        )
        self.assertEqual(len(change_log["changes"]), 1)
        self.assertEqual(change_log["changes"][0]["type"], "FIELD_ADDED")

        # Step 4: Create snapshot
        snapshot = TimeTravelQuery.create_snapshot(v2, snapshot_type="FULL")
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.snapshot_type, "FULL")

        # Step 5: Compare versions
        comparison = VersionComparisonService.compare_versions(v1, v2, include_data_diff=True)
        self.assertEqual(
            comparison.schema_diff.compatibility_level, CompatibilityLevel.BACKWARD_COMPATIBLE
        )
        self.assertIsNotNone(comparison.data_diff)
        self.assertEqual(comparison.data_diff.row_count_diff, 50)

        # Step 6: Visualize schema diff
        markdown = VersionComparisonService.visualize_schema_diff(
            comparison.schema_diff, format="markdown"
        )
        self.assertIn("Schema Diff", markdown)
        self.assertIn("BACKWARD_COMPATIBLE", markdown)

        # Step 7: Restore from snapshot
        restored = TimeTravelQuery.restore_from_snapshot(snapshot)
        self.assertIsNotNone(restored)
        self.assertEqual(restored.version, 3)  # Next version
        self.assertEqual(restored.schema_json, v2.schema_json)

    def test_breaking_change_workflow(self):
        """Test workflow with breaking changes"""
        # Create initial version
        v1 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={
                "fields": [
                    {"name": "id", "data_type": "integer", "nullable": False},
                    {"name": "name", "data_type": "string", "nullable": True},
                ]
            },
            format="CSV",
            version=1,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(v1, semantic_version="1.0.0", is_current=True)

        # Create version with breaking change (field removed)
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
                    {"name": "id", "data_type": "integer", "nullable": False}
                    # name field removed
                ]
            },
            format="CSV",
            version=2,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(
            v2, parent_version=v1, semantic_version="2.0.0", is_current=True
        )

        # Verify breaking change detected
        schema_v2 = v2.schema_version
        self.assertEqual(schema_v2.compatibility_level, CompatibilityLevel.FORWARD_COMPATIBLE.value)
        self.assertIn("FIELD_REMOVED", schema_v2.change_summary)

        # Compare versions
        comparison = VersionComparisonService.compare_versions(v1, v2)
        self.assertEqual(
            comparison.schema_diff.compatibility_level, CompatibilityLevel.FORWARD_COMPATIBLE
        )

        # Check for breaking changes
        breaking_changes = [c for c in comparison.schema_diff.changes if c.breaking]
        self.assertGreater(len(breaking_changes), 0)

        # Visualize breaking changes
        markdown = VersionComparisonService.visualize_schema_diff(
            comparison.schema_diff, format="markdown"
        )
        self.assertIn("BREAKING", markdown)

    def test_time_travel_and_comparison_workflow(self):
        """Test time-travel queries with version comparison"""
        from datetime import timedelta

        from django.utils import timezone

        # Create versions at different times
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
        v1.created_at = timezone.now() - timedelta(days=5)
        v1.save()
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
            created_by=self.user,
        )
        v2.created_at = timezone.now() - timedelta(days=2)
        v2.save()
        VersionHistoryManager.create_version(
            v2, parent_version=v1, semantic_version="1.1.0", is_current=True
        )

        # Time-travel query
        timestamp = timezone.now() - timedelta(days=3)
        old_version = TimeTravelQuery.get_version_at_timestamp(
            self.asset.id, self.tenant.id, timestamp
        )
        self.assertEqual(old_version.id, v1.id)

        # Compare time-traveled version with current
        comparison = VersionComparisonService.compare_versions(old_version, v2)
        self.assertEqual(
            comparison.schema_diff.compatibility_level, CompatibilityLevel.BACKWARD_COMPATIBLE
        )

        # Create snapshot of old version
        snapshot = TimeTravelQuery.create_snapshot(old_version, snapshot_type="FULL")
        self.assertIsNotNone(snapshot)

        # Restore and compare
        restored = TimeTravelQuery.restore_from_snapshot(snapshot)
        comparison_restored = VersionComparisonService.compare_versions(old_version, restored)
        self.assertEqual(
            comparison_restored.schema_diff.compatibility_level, CompatibilityLevel.FULLY_COMPATIBLE
        )
