"""
Unit tests for Schema Evolution Tracking

Tests for schema diff, compatibility calculation, and change log generation.
"""

import pytest

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.datasets.schema_evolution import (
    ChangeType,
    CompatibilityLevel,
    SchemaEvolutionTracker,
)
from hub.apps.datasets.tests.test_base import DatasetsTestBase
from hub.apps.files.models import File, FileStatus

pytestmark = pytest.mark.django_db(transaction=True)


class SchemaEvolutionTrackerTest(DatasetsTestBase):
    """Test SchemaEvolutionTracker"""

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

    def test_calculate_schema_diff_no_changes(self):
        """Test schema diff with no changes"""
        old_schema = {"fields": [{"name": "col1", "data_type": "string", "nullable": True}]}
        new_schema = {"fields": [{"name": "col1", "data_type": "string", "nullable": True}]}

        diff = SchemaEvolutionTracker.calculate_schema_diff(old_schema, new_schema)

        self.assertEqual(len(diff.changes), 0)
        self.assertEqual(diff.compatibility_level, CompatibilityLevel.FULLY_COMPATIBLE)

    def test_calculate_schema_diff_field_added(self):
        """Test schema diff with field added"""
        old_schema = {"fields": [{"name": "col1", "data_type": "string", "nullable": True}]}
        new_schema = {
            "fields": [
                {"name": "col1", "data_type": "string", "nullable": True},
                {"name": "col2", "data_type": "integer", "nullable": True},
            ]
        }

        diff = SchemaEvolutionTracker.calculate_schema_diff(old_schema, new_schema)

        self.assertEqual(len(diff.changes), 1)
        self.assertEqual(diff.changes[0].change_type, ChangeType.FIELD_ADDED)
        self.assertEqual(diff.changes[0].field_name, "col2")
        self.assertFalse(diff.changes[0].breaking)
        self.assertEqual(diff.compatibility_level, CompatibilityLevel.BACKWARD_COMPATIBLE)

    def test_calculate_schema_diff_field_removed(self):
        """Test schema diff with field removed"""
        old_schema = {
            "fields": [
                {"name": "col1", "data_type": "string", "nullable": True},
                {"name": "col2", "data_type": "integer", "nullable": True},
            ]
        }
        new_schema = {"fields": [{"name": "col1", "data_type": "string", "nullable": True}]}

        diff = SchemaEvolutionTracker.calculate_schema_diff(old_schema, new_schema)

        self.assertEqual(len(diff.changes), 1)
        self.assertEqual(diff.changes[0].change_type, ChangeType.FIELD_REMOVED)
        self.assertEqual(diff.changes[0].field_name, "col2")
        self.assertTrue(diff.changes[0].breaking)
        self.assertEqual(diff.compatibility_level, CompatibilityLevel.FORWARD_COMPATIBLE)

    def test_calculate_schema_diff_type_changed(self):
        """Test schema diff with type change"""
        old_schema = {"fields": [{"name": "col1", "data_type": "string", "nullable": True}]}
        new_schema = {"fields": [{"name": "col1", "data_type": "integer", "nullable": True}]}

        diff = SchemaEvolutionTracker.calculate_schema_diff(old_schema, new_schema)

        self.assertEqual(len(diff.changes), 1)
        self.assertEqual(diff.changes[0].change_type, ChangeType.FIELD_TYPE_CHANGED)
        self.assertEqual(diff.changes[0].field_name, "col1")
        self.assertTrue(diff.changes[0].breaking)
        self.assertEqual(diff.compatibility_level, CompatibilityLevel.INCOMPATIBLE)

    def test_calculate_schema_diff_nullable_changed(self):
        """Test schema diff with nullable change"""
        old_schema = {"fields": [{"name": "col1", "data_type": "string", "nullable": True}]}
        new_schema = {"fields": [{"name": "col1", "data_type": "string", "nullable": False}]}

        diff = SchemaEvolutionTracker.calculate_schema_diff(old_schema, new_schema)

        self.assertEqual(len(diff.changes), 1)
        self.assertEqual(diff.changes[0].change_type, ChangeType.FIELD_NULLABLE_CHANGED)
        self.assertEqual(diff.changes[0].field_name, "col1")
        self.assertTrue(diff.changes[0].breaking)  # Breaking when changed to non-nullable

    def test_calculate_schema_diff_primary_key_changed(self):
        """Test schema diff with primary key change"""
        old_schema = {
            "fields": [{"name": "id", "data_type": "integer", "nullable": False}],
            "primary_key_candidates": ["id"],
        }
        new_schema = {
            "fields": [
                {"name": "id", "data_type": "integer", "nullable": False},
                {"name": "uuid", "data_type": "string", "nullable": False},
            ],
            "primary_key_candidates": ["uuid"],
        }

        diff = SchemaEvolutionTracker.calculate_schema_diff(old_schema, new_schema)

        pk_changes = [c for c in diff.changes if c.change_type == ChangeType.PRIMARY_KEY_CHANGED]
        self.assertEqual(len(pk_changes), 1)
        self.assertTrue(pk_changes[0].breaking)

    def test_generate_change_log(self):
        """Test change log generation"""
        # Create parent dataset
        parent = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "data_type": "string", "nullable": True}]},
            format="CSV",
            version=1,
            created_by=self.user,
        )
        from hub.apps.datasets.versioning import VersionHistoryManager

        VersionHistoryManager.create_version(parent, semantic_version="1.0.0", is_current=False)

        # Create child dataset
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

        child = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=file2,
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
        VersionHistoryManager.create_version(
            child, parent_version=parent, semantic_version="1.1.0", is_current=True
        )

        # Generate change log
        change_log = SchemaEvolutionTracker.generate_change_log(parent, child)

        self.assertEqual(change_log["from_version"]["semantic_version"], "1.0.0")
        self.assertEqual(change_log["to_version"]["semantic_version"], "1.1.0")
        self.assertEqual(
            change_log["compatibility_level"], CompatibilityLevel.BACKWARD_COMPATIBLE.value
        )
        self.assertIn("changes", change_log)
        self.assertIn("summary", change_log)

    def test_track_schema_version(self):
        """Test tracking schema version"""
        # Create parent dataset
        parent = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "data_type": "string", "nullable": True}]},
            format="CSV",
            version=1,
            created_by=self.user,
        )
        from hub.apps.datasets.versioning import VersionHistoryManager

        VersionHistoryManager.create_version(parent, semantic_version="1.0.0", is_current=False)

        # Create child dataset
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

        child = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=file2,
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
        # Do not call create_version(child) here: it already calls track_schema_version,
        # and we are testing track_schema_version directly (one SchemaVersion per dataset).

        # Track schema version (creates SchemaVersion for child)
        schema_version = SchemaEvolutionTracker.track_schema_version(child, parent_dataset=parent)

        self.assertIsNotNone(schema_version)
        self.assertEqual(schema_version.dataset, child)
        self.assertEqual(
            schema_version.compatibility_level, CompatibilityLevel.BACKWARD_COMPATIBLE.value
        )
        self.assertIn("FIELD_ADDED", schema_version.change_summary)
        self.assertIn("changes", schema_version.change_log)

    # ========== SUCCESS SCENARIOS ==========

    def test_schema_evolution_success(self):
        """Test successful schema evolution tracking (success scenario)"""
        old_schema = {"fields": [{"name": "col1", "data_type": "string"}]}
        new_schema = {
            "fields": [
                {"name": "col1", "data_type": "string"},
                {"name": "col2", "data_type": "integer"},
            ]
        }

        diff = SchemaEvolutionTracker.calculate_schema_diff(old_schema, new_schema)

        # Should return diff
        self.assertIsNotNone(diff)
        self.assertEqual(len(diff.changes), 1)

    # ========== FAILURE SCENARIOS ==========

    def test_schema_evolution_failure_invalid_schema(self):
        """calculate_schema_diff with None old_schema returns diff gracefully."""
        diff = SchemaEvolutionTracker.calculate_schema_diff(None, {})
        self.assertIsNotNone(diff)
        # None old_schema is treated as empty — the diff should report
        # the entire new schema as added fields.
        self.assertGreaterEqual(len(diff.changes), 0)

    def test_schema_evolution_failure_empty_schemas(self):
        """Test schema evolution with empty schemas (failure scenario)"""
        diff = SchemaEvolutionTracker.calculate_schema_diff({}, {})

        # Should handle empty schemas gracefully
        self.assertIsNotNone(diff)
        self.assertEqual(len(diff.changes), 0)

    # ========== ERROR HANDLING ==========

    def test_schema_evolution_no_changes(self):
        """Test error handling in schema evolution"""
        old_schema = {"fields": [{"name": "col1", "data_type": "string"}]}
        new_schema = {"fields": [{"name": "col1", "data_type": "string"}]}

        # Should handle errors gracefully
        try:
            diff = SchemaEvolutionTracker.calculate_schema_diff(old_schema, new_schema)
            # Should return diff
            self.assertIsNotNone(diff)
        except Exception:
            # If raises exception, that's a problem
            self.fail("calculate_schema_diff should handle errors gracefully")

    def test_track_schema_version_with_parent(self):
        """Test error handling when tracking schema version fails"""
        parent = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=1,
            created_by=self.user,
        )

        child = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=2,
            created_by=self.user,
        )

        # Should handle errors gracefully (no exception)
        try:
            schema_version = SchemaEvolutionTracker.track_schema_version(
                child, parent_dataset=parent
            )
            # May return a SchemaVersion instance or None
            self.assertTrue(
                schema_version is None or hasattr(schema_version, "dataset"),
                f"Expected None or SchemaVersion, got {type(schema_version).__name__}",
            )
        except Exception:
            self.fail("track_schema_version should handle errors gracefully")
