"""
Comprehensive unit tests for Dataset Versioning operations.

Tests cover:
- Version creation
- Version comparison
- Version history traversal
- Semantic versioning
- Version tags
- Success scenarios
- Failure scenarios
- Edge cases
- Error handling

All tests use real implementations (no mocks of hub services).
"""

import uuid

import pytest
from rest_framework import status

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.core.services.base import NotFoundError
from hub.apps.datasets.models import Dataset
from hub.apps.datasets.tests.test_base import DatasetsAPITestBase
from hub.apps.datasets.versioning import VersionHistoryManager
from hub.apps.datasets.versioning_service import VersioningService
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)


class DatasetVersioningTest(DatasetsAPITestBase):
    """Comprehensive tests for Dataset Versioning"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        # Create asset
        self.asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", created_by=self.user
        )

        # Create base dataset
        self.base_dataset = Dataset.objects.create(
            tenant=self.tenant,
            file=self.file,
            asset=self.asset,
            format="CSV",
            schema_json={"fields": [{"name": "id", "type": "string"}]},
            version=1,
            is_current=True,
            created_by=self.user,
        )

        # Initialize versioning service
        self.versioning_service = VersioningService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    # ========== VERSION CREATION TESTS ==========

    def test_create_version_success(self):
        """Test creating a new dataset version successfully"""
        new_version = self.versioning_service.create_version(
            dataset_id=str(self.base_dataset.id),
            tenant_id=str(self.tenant.id),
            semantic_version="1.1.0",
            version_tags=["production"],
            is_current=True,
        )

        self.assertIsNotNone(new_version)
        self.assertEqual(new_version.version, 2)
        self.assertEqual(new_version.semantic_version, "1.1.0")
        self.assertEqual(new_version.version_tags, ["production"])
        self.assertTrue(new_version.is_current)

        # Verify parent version is no longer current
        self.base_dataset.refresh_from_db()
        self.assertFalse(self.base_dataset.is_current)

    def test_create_version_with_parent(self):
        """Test creating version with parent version"""
        # Create version 2
        version2 = self.versioning_service.create_version(
            dataset_id=str(self.base_dataset.id),
            tenant_id=str(self.tenant.id),
            semantic_version="1.1.0",
            is_current=True,
        )

        # Create version 3 with version 2 as parent
        version3 = self.versioning_service.create_version(
            dataset_id=str(version2.id),
            tenant_id=str(self.tenant.id),
            parent_version_id=str(version2.id),
            semantic_version="1.2.0",
            is_current=True,
        )

        self.assertEqual(version3.version, 3)
        self.assertEqual(version3.parent_version, version2)
        self.assertEqual(version3.semantic_version, "1.2.0")

    def test_create_version_not_found(self):
        """Test creating version with non-existent dataset (failure scenario)"""
        fake_id = str(uuid.uuid4())

        with self.assertRaises(NotFoundError) as cm:
            self.versioning_service.create_version(
                dataset_id=fake_id, tenant_id=str(self.tenant.id), semantic_version="1.1.0"
            )

        self.assertEqual(cm.exception.code, "NOT_FOUND")

    def test_create_version_wrong_tenant(self):
        """Test creating version with dataset from wrong tenant (failure scenario)"""
        # Create another tenant and dataset
        _sfx = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_sfx}", slug=f"other-tenant-{_sfx}", status="ACTIVE", kyc_status="UNVERIFIED"
        )

        other_file = File.objects.create(
            tenant=other_tenant,
            name="other.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            storage_path=f"{other_tenant.id}/other.csv",
        )

        other_dataset = Dataset.objects.create(
            tenant=other_tenant, file=other_file, format="CSV", schema_json={"fields": []}
        )

        with self.assertRaises(NotFoundError) as cm:
            self.versioning_service.create_version(
                dataset_id=str(other_dataset.id),
                tenant_id=str(self.tenant.id),
                semantic_version="1.1.0",
            )

        self.assertEqual(cm.exception.code, "NOT_FOUND")

    # ========== VERSION HISTORY TESTS ==========

    def test_get_version_history_success(self):
        """Test retrieving version history successfully"""
        # Create multiple versions
        version2 = self.versioning_service.create_version(
            dataset_id=str(self.base_dataset.id),
            tenant_id=str(self.tenant.id),
            semantic_version="1.1.0",
            is_current=True,
        )

        version3 = self.versioning_service.create_version(
            dataset_id=str(version2.id),
            tenant_id=str(self.tenant.id),
            parent_version_id=str(version2.id),
            semantic_version="1.2.0",
            is_current=True,
        )

        # Get version history
        history = VersionHistoryManager.get_version_tree(self.base_dataset)

        self.assertIsNotNone(history)
        # Should include all versions
        version_ids = [v.id for v in history]
        self.assertIn(self.base_dataset.id, version_ids)
        self.assertIn(version2.id, version_ids)
        self.assertIn(version3.id, version_ids)

    def test_get_version_history_empty(self):
        """Test retrieving version history for dataset with no versions (edge case)"""
        history = VersionHistoryManager.get_version_tree(self.base_dataset)

        # Should return at least the base dataset
        self.assertIsNotNone(history)
        self.assertGreaterEqual(len(history), 1)

    # ========== SEMANTIC VERSIONING TESTS ==========

    def test_semantic_versioning_major(self):
        """Test semantic versioning - major version increment"""
        new_version = self.versioning_service.create_version(
            dataset_id=str(self.base_dataset.id),
            tenant_id=str(self.tenant.id),
            semantic_version="2.0.0",
            is_current=True,
        )

        self.assertEqual(new_version.semantic_version, "2.0.0")

    def test_semantic_versioning_minor(self):
        """Test semantic versioning - minor version increment"""
        new_version = self.versioning_service.create_version(
            dataset_id=str(self.base_dataset.id),
            tenant_id=str(self.tenant.id),
            semantic_version="1.1.0",
            is_current=True,
        )

        self.assertEqual(new_version.semantic_version, "1.1.0")

    def test_semantic_versioning_patch(self):
        """Test semantic versioning - patch version increment"""
        new_version = self.versioning_service.create_version(
            dataset_id=str(self.base_dataset.id),
            tenant_id=str(self.tenant.id),
            semantic_version="1.0.1",
            is_current=True,
        )

        self.assertEqual(new_version.semantic_version, "1.0.1")

    def test_semantic_versioning_invalid_format(self):
        """Invalid semantic versions are accepted and stored as-is (no validation)."""
        new_version = self.versioning_service.create_version(
            dataset_id=str(self.base_dataset.id),
            tenant_id=str(self.tenant.id),
            semantic_version="invalid-version",
            is_current=True,
        )
        self.assertIsNotNone(new_version)
        self.assertEqual(new_version.semantic_version, "invalid-version",
            "Service must store invalid semantic versions as-is")

    # ========== VERSION TAGS TESTS ==========

    def test_version_tags_single(self):
        """Test creating version with single tag"""
        new_version = self.versioning_service.create_version(
            dataset_id=str(self.base_dataset.id),
            tenant_id=str(self.tenant.id),
            version_tags=["production"],
            is_current=True,
        )

        self.assertEqual(new_version.version_tags, ["production"])

    def test_version_tags_multiple(self):
        """Test creating version with multiple tags"""
        new_version = self.versioning_service.create_version(
            dataset_id=str(self.base_dataset.id),
            tenant_id=str(self.tenant.id),
            version_tags=["production", "staging", "test"],
            is_current=True,
        )

        self.assertEqual(len(new_version.version_tags), 3)
        self.assertIn("production", new_version.version_tags)
        self.assertIn("staging", new_version.version_tags)
        self.assertIn("test", new_version.version_tags)

    def test_version_tags_empty(self):
        """Test creating version with empty tags (edge case)"""
        new_version = self.versioning_service.create_version(
            dataset_id=str(self.base_dataset.id),
            tenant_id=str(self.tenant.id),
            version_tags=[],
            is_current=True,
        )

        self.assertEqual(new_version.version_tags, [])

    # ========== VERSION COMPARISON TESTS ==========

    def test_compare_versions_same_schema(self):
        """Test comparing versions with same schema"""
        # Create version with same schema
        version2 = Dataset.objects.create(
            tenant=self.tenant,
            file=self.file,
            asset=self.asset,
            format="CSV",
            schema_json={"fields": [{"name": "id", "type": "string"}]},
            version=2,
            parent_version=self.base_dataset,
            is_current=True,
            created_by=self.user,
        )

        # Comparison should indicate no changes
        # Note: Actual comparison logic depends on VersionComparisonService implementation
        # This test verifies the structure exists
        self.assertIsNotNone(version2.schema_json)
        self.assertEqual(version2.schema_json, self.base_dataset.schema_json)

    def test_compare_versions_different_schema(self):
        """Test comparing versions with different schema"""
        # Create version with different schema
        version2 = Dataset.objects.create(
            tenant=self.tenant,
            file=self.file,
            asset=self.asset,
            format="CSV",
            schema_json={
                "fields": [{"name": "id", "type": "string"}, {"name": "name", "type": "string"}]
            },
            version=2,
            parent_version=self.base_dataset,
            is_current=True,
            created_by=self.user,
        )

        # Comparison should indicate schema changes
        self.assertNotEqual(version2.schema_json, self.base_dataset.schema_json)
        self.assertGreater(
            len(version2.schema_json.get("fields", [])),
            len(self.base_dataset.schema_json.get("fields", [])),
        )

    # ========== EDGE CASES ==========

    def test_create_version_without_is_current(self):
        """Test creating version without setting is_current (edge case)"""
        new_version = self.versioning_service.create_version(
            dataset_id=str(self.base_dataset.id),
            tenant_id=str(self.tenant.id),
            semantic_version="1.1.0",
            is_current=False,
        )

        self.assertFalse(new_version.is_current)
        # Base dataset should still be current
        self.base_dataset.refresh_from_db()
        self.assertTrue(self.base_dataset.is_current)

    def test_create_version_with_snapshot_metadata(self):
        """Test creating version with snapshot metadata (edge case)"""
        snapshot_metadata = {
            "description": "Major schema change",
            "changes": ["Added new field", "Removed deprecated field"],
        }

        new_version = self.versioning_service.create_version(
            dataset_id=str(self.base_dataset.id),
            tenant_id=str(self.tenant.id),
            semantic_version="2.0.0",
            snapshot_metadata=snapshot_metadata,
            is_current=True,
        )

        self.assertIsNotNone(new_version.snapshot_metadata)
        self.assertEqual(new_version.snapshot_metadata.get("description"), "Major schema change")

    def test_create_version_max_version_number(self):
        """Test version number increments correctly (edge case)"""
        # Create multiple versions
        version2 = self.versioning_service.create_version(
            dataset_id=str(self.base_dataset.id),
            tenant_id=str(self.tenant.id),
            semantic_version="1.1.0",
            is_current=True,
        )

        version3 = self.versioning_service.create_version(
            dataset_id=str(version2.id),
            tenant_id=str(self.tenant.id),
            parent_version_id=str(version2.id),
            semantic_version="1.2.0",
            is_current=True,
        )

        self.assertEqual(version2.version, 2)
        self.assertEqual(version3.version, 3)

    # ========== ERROR HANDLING ==========

    def test_create_version_with_nonexistent_tenant(self):
        """Test error handling when version creation fails"""
        # Use valid dataset ID but invalid tenant ID
        fake_tenant_id = str(uuid.uuid4())

        with self.assertRaises(NotFoundError) as cm:
            self.versioning_service.create_version(
                dataset_id=str(self.base_dataset.id),
                tenant_id=fake_tenant_id,
                semantic_version="1.1.0",
            )

        self.assertEqual(cm.exception.code, "NOT_FOUND")

    def test_get_version_history_nonexistent_dataset(self):
        """Test getting version history for non-existent dataset returns result."""
        fake_dataset = Dataset(id=uuid.uuid4(), tenant=self.tenant)

        # get_version_tree must handle a non-persisted dataset gracefully —
        # returning a result (even if empty), not raising.
        history = VersionHistoryManager.get_version_tree(fake_dataset)
        self.assertIsNotNone(history,
            "get_version_tree must return a result even for non-existent dataset")
