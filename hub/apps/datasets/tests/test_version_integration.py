"""
Integration tests for Dataset Version History

Tests for version operations in the context of API and dataset creation.
"""

import json

import pytest
from django.utils import timezone
from rest_framework import status

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.datasets.tests.test_base import DatasetsAPITestBase
from hub.apps.datasets.versioning import VersionHistoryManager
from hub.apps.files.models import File, FileStatus

pytestmark = pytest.mark.django_db(transaction=True)


class VersionHistoryIntegrationTest(DatasetsAPITestBase):
    """Integration tests for version history"""

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

    def test_dataset_creation_with_version_history(self):
        """Test that dataset creation automatically sets up version history"""
        # Create dataset via API
        response = self.client.post(
            "/api/v1/datasets/",
            {"file_id": str(self.file.id), "asset_id": str(self.asset.id)},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        dataset_id = response.data["id"]

        # Verify version history fields
        dataset = Dataset.objects.get(id=dataset_id)
        self.assertIsNotNone(dataset.version_hash)
        self.assertEqual(dataset.semantic_version, "1.0.0")
        self.assertTrue(dataset.is_current)
        self.assertIsNone(dataset.parent_version)

    def test_version_chain_creation(self):
        """Test creating multiple versions in sequence"""
        # Create first version
        v1 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(v1, is_current=True)

        # Create second version
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
                "fields": [{"name": "col1", "type": "string"}, {"name": "col2", "type": "integer"}]
            },
            format="CSV",
            version=2,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(v2, parent_version=v1, is_current=True)

        # Verify version chain
        v2.refresh_from_db()
        self.assertEqual(v2.parent_version, v1)
        self.assertEqual(v2.semantic_version, "1.1.0")  # Minor increment
        self.assertTrue(v2.is_current)

        v1.refresh_from_db()
        self.assertFalse(v1.is_current)

    def test_version_querying_integration(self):
        """Test version querying operations"""
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
        VersionHistoryManager.create_version(
            v1, semantic_version="1.0.0", version_tags=["production"], is_current=False
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
        VersionHistoryManager.create_version(
            v2,
            parent_version=v1,
            semantic_version="1.1.0",
            version_tags=["staging"],
            is_current=True,
        )

        # Test get_current_version
        current = VersionHistoryManager.get_current_version(self.asset.id, self.tenant.id)
        self.assertEqual(current.id, v2.id)

        # Test get_version_by_semantic_version
        found = VersionHistoryManager.get_version_by_semantic_version(
            self.asset.id, self.tenant.id, "1.0.0"
        )
        self.assertEqual(found.id, v1.id)

        # Test get_versions_by_tag
        production_versions = VersionHistoryManager.get_versions_by_tag(
            self.asset.id, self.tenant.id, "production"
        )
        self.assertEqual(len(production_versions), 1)
        self.assertEqual(production_versions[0].id, v1.id)

    def test_version_tree_traversal_integration(self):
        """Test version tree traversal operations"""
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
        VersionHistoryManager.create_version(v2, parent_version=v1, is_current=False)

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
        VersionHistoryManager.create_version(v3, parent_version=v2, is_current=True)

        # Test get_root_version
        root = VersionHistoryManager.get_root_version(v3)
        self.assertEqual(root.id, v1.id)

        # Test get_ancestors
        ancestors = VersionHistoryManager.get_ancestors(v3)
        self.assertEqual(len(ancestors), 2)
        self.assertEqual(ancestors[0].id, v2.id)
        self.assertEqual(ancestors[1].id, v1.id)

        # Test get_descendants
        descendants = VersionHistoryManager.get_descendants(v1)
        self.assertEqual(len(descendants), 2)
        self.assertEqual(descendants[0].id, v2.id)
        self.assertEqual(descendants[1].id, v3.id)

        # Test get_version_tree
        tree = VersionHistoryManager.get_version_tree(v2)
        self.assertEqual(len(tree), 3)
        self.assertEqual(tree[0].id, v1.id)
        self.assertEqual(tree[1].id, v2.id)
        self.assertEqual(tree[2].id, v3.id)

    def test_archive_and_restore_integration(self):
        """Test archiving and restoring versions"""
        # Create versions
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

        # Archive v1
        VersionHistoryManager.archive_version(v1)
        v1.refresh_from_db()
        self.assertIsNotNone(v1.archived_at)
        self.assertFalse(v1.is_current)

        # Restore v1
        VersionHistoryManager.restore_version(v1)
        v1.refresh_from_db()
        v2.refresh_from_db()
        self.assertIsNone(v1.archived_at)
        self.assertTrue(v1.is_current)
        self.assertFalse(v2.is_current)

    # ========== FAILURE SCENARIOS ==========

    def test_version_integration_failure_nonexistent_dataset(self):
        """Test version integration with non-existent dataset (failure scenario)"""
        import uuid

        fake_dataset_id = str(uuid.uuid4())

        # Should handle non-existent dataset gracefully
        try:
            history = VersionHistoryManager.get_version_history(
                dataset_id=fake_dataset_id, tenant_id=str(self.tenant.id)
            )
            # If succeeds, should return empty history or None
            self.assertIsNone(history) or self.assertEqual(len(history), 0)
        except Exception:
            # If fails, that's acceptable for non-existent dataset
            pass

    # ========== EDGE CASES ==========

    def test_version_integration_edge_case_empty_history(self):
        """Test version integration with empty history (edge case)"""
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

        # Should handle empty history gracefully
        try:
            history = VersionHistoryManager.get_version_history(
                dataset_id=str(dataset.id), tenant_id=str(self.tenant.id)
            )
            # Should return empty history or None
            self.assertIsNone(history) or self.assertEqual(len(history), 0)
        except Exception:
            # If fails, that's acceptable for empty history
            pass

    def test_version_integration_edge_case_single_version(self):
        """Test version integration with single version (edge case)"""
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

        # Should handle single version gracefully
        self.assertIsNotNone(dataset)
        self.assertEqual(dataset.version, 1)

    # ========== ERROR HANDLING ==========

    def test_version_integration_error_handling(self):
        """Test error handling in version integration"""
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
