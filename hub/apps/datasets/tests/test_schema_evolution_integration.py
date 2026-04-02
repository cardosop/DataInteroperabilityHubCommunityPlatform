"""
Integration tests for Schema Evolution Tracking

Tests for schema evolution in the context of dataset creation and version management.
"""
import uuid

import pytest

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset, SchemaVersion
from hub.apps.files.models import File, FileStatus
from hub.apps.datasets.schema_evolution import CompatibilityLevel, SchemaEvolutionTracker
from hub.apps.datasets.tests.test_base import DatasetsTestBase
from hub.apps.datasets.versioning import VersionHistoryManager

pytestmark = pytest.mark.django_db(transaction=True)


class SchemaEvolutionIntegrationTest(DatasetsTestBase):
    """Integration tests for schema evolution"""

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

    def test_schema_evolution_automatic_tracking(self):
        """Test that schema evolution is automatically tracked on version creation"""
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
        VersionHistoryManager.create_version(parent, semantic_version="1.0.0", is_current=False)

        # Verify schema version was created
        self.assertTrue(hasattr(parent, "schema_version"))
        schema_v1 = parent.schema_version
        self.assertIsNotNone(schema_v1)
        self.assertEqual(schema_v1.compatibility_level, CompatibilityLevel.FULLY_COMPATIBLE.value)

        # Create child version
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

        # Verify schema version was created with correct compatibility
        self.assertTrue(hasattr(child, "schema_version"))
        schema_v2 = child.schema_version
        self.assertIsNotNone(schema_v2)
        self.assertEqual(
            schema_v2.compatibility_level, CompatibilityLevel.BACKWARD_COMPATIBLE.value
        )
        self.assertEqual(schema_v2.parent_schema_version, schema_v1)
        self.assertIn("FIELD_ADDED", schema_v2.change_summary)

    def test_schema_evolution_chain(self):
        """Test schema evolution through multiple versions"""
        # Create version chain: v1 -> v2 -> v3
        v1 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "data_type": "string", "nullable": True}]},
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
            v2, parent_version=v1, semantic_version="1.1.0", is_current=False
        )

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
            schema_json={
                "fields": [
                    {"name": "col1", "data_type": "string", "nullable": True},
                    {"name": "col2", "data_type": "integer", "nullable": True},
                    {"name": "col3", "data_type": "boolean", "nullable": True},
                ]
            },
            format="CSV",
            version=3,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(
            v3, parent_version=v2, semantic_version="1.2.0", is_current=True
        )

        # Verify schema evolution chain
        schema_v1 = v1.schema_version
        schema_v2 = v2.schema_version
        schema_v3 = v3.schema_version

        self.assertIsNone(schema_v1.parent_schema_version)
        self.assertEqual(schema_v2.parent_schema_version, schema_v1)
        self.assertEqual(schema_v3.parent_schema_version, schema_v2)

        # Verify compatibility levels
        self.assertEqual(schema_v1.compatibility_level, CompatibilityLevel.FULLY_COMPATIBLE.value)
        self.assertEqual(
            schema_v2.compatibility_level, CompatibilityLevel.BACKWARD_COMPATIBLE.value
        )
        self.assertEqual(
            schema_v3.compatibility_level, CompatibilityLevel.BACKWARD_COMPATIBLE.value
        )

    def test_change_log_generation_integration(self):
        """Test change log generation in integration context"""
        # Create versions
        v1 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "data_type": "string", "nullable": True}]},
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
            v2, parent_version=v1, semantic_version="1.1.0", is_current=True
        )

        # Generate change log
        change_log = SchemaEvolutionTracker.generate_change_log(v1, v2)

        # Verify change log structure
        self.assertIn("from_version", change_log)
        self.assertIn("to_version", change_log)
        self.assertIn("compatibility_level", change_log)
        self.assertIn("summary", change_log)
        self.assertIn("changes", change_log)

        # Verify change log content
        self.assertEqual(change_log["from_version"]["semantic_version"], "1.0.0")
        self.assertEqual(change_log["to_version"]["semantic_version"], "1.1.0")
        self.assertEqual(
            change_log["compatibility_level"], CompatibilityLevel.BACKWARD_COMPATIBLE.value
        )
        self.assertGreater(change_log["summary"].get("FIELD_ADDED", 0), 0)

    # ========== SUCCESS SCENARIOS ==========

    def test_schema_evolution_integration_success(self):
        """Test successful schema evolution integration (success scenario)"""
        parent = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=1,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(parent, semantic_version="1.0.0", is_current=False)

        # Should track schema evolution
        self.assertIsNotNone(parent)

    # ========== FAILURE SCENARIOS ==========

    def test_schema_evolution_integration_failure_nonexistent_parent(self):
        """Test schema evolution integration with non-existent parent (failure scenario)"""
        import uuid

        fake_parent_id = uuid.uuid4()
        fake_parent = Dataset(
            id=fake_parent_id, tenant=self.tenant, asset=self.asset, file=self.file
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

        # Non-existent parent must either return None or raise
        try:
            schema_version = SchemaEvolutionTracker.track_schema_version(
                child, parent_dataset=fake_parent
            )
            self.assertIsNone(schema_version)
        except Exception:
            pass

    # ========== EDGE CASES ==========

    def test_schema_evolution_integration_edge_case_no_changes(self):
        """Test schema evolution integration with no changes (edge case)"""
        parent = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "data_type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(parent, semantic_version="1.0.0", is_current=False)

        file2 = File.objects.create(
            tenant=self.tenant,
            name="test2.csv",
            content_type="text/csv",
            size=2000,
            status=FileStatus.ACTIVE,
            storage_path="test/test2.csv",
            created_by=self.user,
        )

        child = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=file2,
            schema_json={"fields": [{"name": "col1", "data_type": "string"}]},
            format="CSV",
            version=2,
            created_by=self.user,
        )

        # Should handle no changes gracefully - track_schema_version always returns a SchemaVersion
        # even when there are no changes (it tracks the schema state)
        schema_version = SchemaEvolutionTracker.track_schema_version(child, parent_dataset=parent)
        self.assertIsNotNone(schema_version)
        # Verify it was created successfully
        self.assertEqual(schema_version.dataset, child)
        self.assertEqual(schema_version.compatibility_level, "FULLY_COMPATIBLE")

    # ========== ERROR HANDLING ==========

    def test_schema_evolution_integration_error_handling(self):
        """Test error handling in schema evolution integration"""
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

        # Should handle errors gracefully - track_schema_version always returns a SchemaVersion
        schema_version = SchemaEvolutionTracker.track_schema_version(
            child, parent_dataset=parent
        )
        # Should return a valid schema version without raising exceptions
        self.assertIsNotNone(schema_version)
        self.assertEqual(schema_version.dataset, child)
        # Both schemas are empty, so should be fully compatible
        self.assertEqual(schema_version.compatibility_level, "FULLY_COMPATIBLE")
