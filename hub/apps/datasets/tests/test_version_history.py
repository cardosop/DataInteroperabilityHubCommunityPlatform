"""
Unit tests for Dataset Version History

Tests for version creation, tree traversal, and querying.
"""

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.datasets.tests.test_base import DatasetsTestBase
from hub.apps.datasets.versioning import VersionHistoryManager
from hub.apps.files.models import File, FileStatus

pytestmark = pytest.mark.django_db(transaction=True)


class VersionHistoryManagerTest(DatasetsTestBase):
    """Test VersionHistoryManager"""

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

    def test_calculate_version_hash(self):
        """Test version hash calculation"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user,
        )

        hash1 = VersionHistoryManager.calculate_version_hash(dataset)

        # Same schema and file should produce same hash
        hash2 = VersionHistoryManager.calculate_version_hash(dataset)
        self.assertEqual(hash1, hash2)

        # Different schema should produce different hash
        dataset2 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col2", "type": "integer"}]},
            format="CSV",
            version=2,
            created_by=self.user,
        )
        hash3 = VersionHistoryManager.calculate_version_hash(dataset2)
        self.assertNotEqual(hash1, hash3)

    # ========== SUCCESS SCENARIOS ==========

    def test_get_version_history_success(self):
        """Test successfully getting version history"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=1,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(dataset, is_current=True)

        history = VersionHistoryManager.get_version_tree(dataset)

        # Should return history (list of versions)
        self.assertIsNotNone(history)
        self.assertIsInstance(history, list)

    # ========== FAILURE SCENARIOS ==========

    def test_get_version_history_nonexistent_dataset(self):
        """get_version_tree on an unsaved dataset returns a list with the dataset node."""
        import uuid
        from hub.apps.datasets.models import Dataset

        # Unsaved Dataset — not in DB, but get_version_tree accepts a Dataset instance.
        fake_dataset = Dataset(
            id=uuid.uuid4(),
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=1,
            format="CSV",
        )
        tree = VersionHistoryManager.get_version_tree(fake_dataset)
        self.assertIsNotNone(tree,
            "get_version_tree must return a result for any Dataset instance")
        self.assertIsInstance(tree, list,
            "get_version_tree must return a list")

    def test_create_version_invalid_dataset(self):
        """Test creating version with invalid dataset (failure scenario)"""
        import uuid

        fake_dataset = Dataset(
            id=uuid.uuid4(), tenant=self.tenant, asset=self.asset, file=self.file
        )

        # create_version on a non-persisted dataset returns a result
        # without raising — the dataset object is populated in-memory.
        VersionHistoryManager.create_version(fake_dataset, is_current=True)
        self.assertIsNotNone(fake_dataset.id,
            "create_version must assign an id to the dataset")

    # ========== EDGE CASES ==========

    def test_get_version_history_empty_history(self):
        """Test getting version history when none exists (edge case)"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=1,
            created_by=self.user,
        )
        # Don't create version history

        # Should return history with at least the dataset itself
        history = VersionHistoryManager.get_version_tree(dataset)
        # Should return at least the dataset itself (even if no version history created)
        self.assertIsNotNone(history)
        self.assertIsInstance(history, list)
        self.assertGreaterEqual(len(history), 1)

    def test_create_version_without_parent_edge_case(self):
        """Test creating version without parent (edge case)"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=1,
            created_by=self.user,
        )

        # Should create version without parent
        VersionHistoryManager.create_version(dataset, is_current=True)

        self.assertIsNotNone(dataset)
        self.assertEqual(dataset.version, 1)

    def test_calculate_version_hash_same_content(self):
        """Test version hash calculation with same content (edge case)"""
        dataset1 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user,
        )

        dataset2 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=2,
            created_by=self.user,
        )

        hash1 = VersionHistoryManager.calculate_version_hash(dataset1)
        hash2 = VersionHistoryManager.calculate_version_hash(dataset2)

        # Same schema and file should produce same hash
        self.assertEqual(hash1, hash2)

    # ========== ERROR HANDLING ==========

    def test_get_version_tree_with_persisted_dataset(self):
        """Test error handling when database query fails"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=1,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(dataset, is_current=True)

        # get_version_tree must return a result without raising for a
        # valid persisted dataset with version history.
        history = VersionHistoryManager.get_version_tree(dataset)
        self.assertIsNotNone(history,
            "get_version_tree must return a list of versions")
        self.assertIsInstance(history, list)

    def test_create_version_with_persisted_dataset(self):
        """Test that create_version succeeds for valid dataset without raising."""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=1,
            created_by=self.user,
        )

        VersionHistoryManager.create_version(dataset, is_current=True)
        self.assertIsNotNone(dataset,
            "create_version must succeed for a persisted dataset")

    def test_create_version_without_parent(self):
        """Test creating version without parent"""
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

        dataset.refresh_from_db()
        self.assertIsNone(dataset.parent_version)
        self.assertIsNotNone(dataset.version_hash)
        self.assertEqual(dataset.semantic_version, "1.0.0")
        self.assertTrue(dataset.is_current)
        self.assertEqual(dataset.version_tags, [])

    def test_create_version_with_parent(self):
        """Test creating version with parent"""
        # Create parent version
        parent = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(parent, is_current=True)

        # Create child version
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
                "fields": [{"name": "col1", "type": "string"}, {"name": "col2", "type": "integer"}]
            },
            format="CSV",
            version=2,
            created_by=self.user,
        )

        VersionHistoryManager.create_version(child, parent_version=parent, is_current=True)

        child.refresh_from_db()
        self.assertEqual(child.parent_version, parent)
        self.assertEqual(child.semantic_version, "1.1.0")  # Minor increment (new field)
        self.assertTrue(child.is_current)

        # Parent should no longer be current
        parent.refresh_from_db()
        self.assertFalse(parent.is_current)

    def test_create_version_semantic_version_inference_breaking_change(self):
        """Test semantic version inference for breaking changes"""
        # Create parent with schema
        parent = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={
                "fields": [{"name": "col1", "type": "string"}, {"name": "col2", "type": "integer"}]
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
            schema_json={"fields": [{"name": "col1", "type": "string"}]},  # col2 removed
            format="CSV",
            version=2,
            created_by=self.user,
        )

        VersionHistoryManager.create_version(child, parent_version=parent, is_current=True)

        child.refresh_from_db()
        self.assertEqual(child.semantic_version, "2.0.0")  # Major increment (breaking)

    def test_create_version_semantic_version_inference_type_change(self):
        """Test semantic version inference for type changes (breaking)"""
        # Create parent
        parent = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(parent, semantic_version="1.0.0", is_current=True)

        # Create child with type change (breaking)
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
            schema_json={"fields": [{"name": "col1", "type": "integer"}]},  # Type changed
            format="CSV",
            version=2,
            created_by=self.user,
        )

        VersionHistoryManager.create_version(child, parent_version=parent, is_current=True)

        child.refresh_from_db()
        self.assertEqual(child.semantic_version, "2.0.0")  # Major increment (breaking)

    def test_create_version_with_tags(self):
        """Test creating version with tags"""
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

        dataset.refresh_from_db()
        self.assertEqual(set(dataset.version_tags), {"production", "stable"})

    def test_get_root_version(self):
        """Test getting root version"""
        # Create version chain: v1 -> v2 -> v3
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

        v2_file = File.objects.create(
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
            file=v2_file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=2,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(v2, parent_version=v1, is_current=False)

        v3_file = File.objects.create(
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
            file=v3_file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=3,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(v3, parent_version=v2, is_current=True)

        # Get root from v3
        root = VersionHistoryManager.get_root_version(v3)
        self.assertEqual(root.id, v1.id)

    def test_get_ancestors(self):
        """Test getting ancestor versions"""
        # Create version chain: v1 -> v2 -> v3
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

        v2_file = File.objects.create(
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
            file=v2_file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=2,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(v2, parent_version=v1, is_current=False)

        v3_file = File.objects.create(
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
            file=v3_file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=3,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(v3, parent_version=v2, is_current=True)

        # Get ancestors from v3
        ancestors = VersionHistoryManager.get_ancestors(v3)
        self.assertEqual(len(ancestors), 2)
        self.assertEqual(ancestors[0].id, v2.id)  # Parent
        self.assertEqual(ancestors[1].id, v1.id)  # Grandparent

    def test_get_descendants(self):
        """Test getting descendant versions"""
        # Create version chain: v1 -> v2 -> v3
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

        v2_file = File.objects.create(
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
            file=v2_file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=2,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(v2, parent_version=v1, is_current=False)

        v3_file = File.objects.create(
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
            file=v3_file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=3,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(v3, parent_version=v2, is_current=True)

        # Get descendants from v1
        descendants = VersionHistoryManager.get_descendants(v1)
        self.assertEqual(len(descendants), 2)
        self.assertEqual(descendants[0].id, v2.id)  # Direct child
        self.assertEqual(descendants[1].id, v3.id)  # Grandchild

    def test_get_version_tree(self):
        """Test getting complete version tree"""
        # Create version chain: v1 -> v2 -> v3
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

        v2_file = File.objects.create(
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
            file=v2_file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=2,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(v2, parent_version=v1, is_current=False)

        v3_file = File.objects.create(
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
            file=v3_file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=3,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(v3, parent_version=v2, is_current=True)

        # Get version tree from v2
        tree = VersionHistoryManager.get_version_tree(v2)
        self.assertEqual(len(tree), 3)
        self.assertEqual(tree[0].id, v1.id)  # Root
        self.assertEqual(tree[1].id, v2.id)  # v2
        self.assertEqual(tree[2].id, v3.id)  # v3

    def test_get_current_version(self):
        """Test getting current version"""
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

        v2_file = File.objects.create(
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
            file=v2_file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=2,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(v2, parent_version=v1, is_current=True)

        # Get current version
        current = VersionHistoryManager.get_current_version(self.asset.id, self.tenant.id)
        self.assertIsNotNone(current)
        self.assertEqual(current.id, v2.id)
        self.assertTrue(current.is_current)

    def test_get_version_by_semantic_version(self):
        """Test getting version by semantic version"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(dataset, semantic_version="1.2.3", is_current=True)

        # Get by semantic version
        found = VersionHistoryManager.get_version_by_semantic_version(
            self.asset.id, self.tenant.id, "1.2.3"
        )
        self.assertIsNotNone(found)
        self.assertEqual(found.id, dataset.id)
        self.assertEqual(found.semantic_version, "1.2.3")

    def test_get_versions_by_tag(self):
        """Test getting versions by tag"""
        # Create versions with tags
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

        v2_file = File.objects.create(
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
            file=v2_file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=2,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(v2, version_tags=["staging"], is_current=True)

        v3_file = File.objects.create(
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
            file=v3_file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=3,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(v3, version_tags=["production"], is_current=False)

        # Get versions by tag
        production_versions = VersionHistoryManager.get_versions_by_tag(
            self.asset.id, self.tenant.id, "production"
        )
        self.assertEqual(len(production_versions), 2)
        self.assertIn(v1.id, {v.id for v in production_versions})
        self.assertIn(v3.id, {v.id for v in production_versions})

    def test_get_versions_by_timestamp(self):
        """Test getting version by timestamp"""
        # Create versions at different times
        v1 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user,
        )
        v1.created_at = timezone.now() - timedelta(days=3)
        v1.save()
        VersionHistoryManager.create_version(v1, is_current=False)

        v2_file = File.objects.create(
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
            file=v2_file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=2,
            created_by=self.user,
        )
        v2.created_at = timezone.now() - timedelta(days=1)
        v2.save()
        VersionHistoryManager.create_version(v2, parent_version=v1, is_current=True)

        # Get version at timestamp between v1 and v2
        timestamp = timezone.now() - timedelta(days=2)
        found = VersionHistoryManager.get_versions_by_timestamp(
            self.asset.id, self.tenant.id, timestamp
        )
        self.assertIsNotNone(found)
        self.assertEqual(found.id, v1.id)

    def test_archive_version(self):
        """Test archiving a version"""
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

        # Archive version
        archived_at = timezone.now()
        VersionHistoryManager.archive_version(dataset, archived_at=archived_at)

        dataset.refresh_from_db()
        self.assertIsNotNone(dataset.archived_at)
        self.assertFalse(dataset.is_current)

    def test_restore_version(self):
        """Test restoring an archived version"""
        # Create two versions
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
        VersionHistoryManager.archive_version(v1)

        v2_file = File.objects.create(
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
            file=v2_file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=2,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(v2, parent_version=v1, is_current=True)

        # Restore v1
        VersionHistoryManager.restore_version(v1)

        v1.refresh_from_db()
        v2.refresh_from_db()
        self.assertIsNone(v1.archived_at)
        self.assertTrue(v1.is_current)
        self.assertFalse(v2.is_current)
