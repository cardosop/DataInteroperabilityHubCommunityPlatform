"""
Unit tests for VersioningService.

Tests cover all service methods with 100% coverage target.

All tests use real implementations (no mocks of hub services).
"""

import uuid

import pytest

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.core.services.base import NotFoundError
from hub.apps.datasets.models import Dataset
from hub.apps.datasets.tests.test_base import DatasetsTestBase
from hub.apps.datasets.versioning_service import VersioningService

pytestmark = pytest.mark.django_db(transaction=True)


class VersioningServiceTest(DatasetsTestBase):
    """Test VersioningService operations"""

    def setUp(self):
        """Set up test data"""
        super().setUp()
        self.service = VersioningService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create asset
        self.asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", status=AssetStatus.ACTIVE
        )

        # Create dataset
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            format="CSV",
            schema_json={"fields": []},
            version=1,
        )

    def test_create_version_success(self):
        """Test successful version creation"""
        new_version = self.service.create_version(
            dataset_id=str(self.dataset.id),
            tenant_id=str(self.tenant.id),
            semantic_version="1.1.0",
            is_current=True,
        )

        new_version.refresh_from_db()
        self.assertEqual(new_version.semantic_version, "1.1.0")
        self.assertTrue(new_version.is_current)

    def test_compare_versions_success(self):
        """Test successful version comparison"""
        # Create second dataset version
        dataset2 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            format="CSV",
            schema_json={"fields": [{"name": "new_field"}]},
            version=2,
        )

        # Use real VersionComparator implementation
        result = self.service.compare_versions(
            dataset_id_1=str(self.dataset.id),
            dataset_id_2=str(dataset2.id),
            tenant_id=str(self.tenant.id),
        )

        # Should return structured comparison results
        self.assertIsInstance(result, dict)
        self.assertIn("metadata", result)
        self.assertIn("schema_diff", result)
        self.assertIn("side_by_side_fields", result)

    def test_get_version_history_success(self):
        """Test successful version history retrieval"""
        history = self.service.get_version_history(
            dataset_id=str(self.dataset.id), tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(history, list)
        self.assertGreaterEqual(len(history), 1,
                                "Version history must contain at least the dataset itself")
        # Each entry must be a Dataset with version metadata.
        for entry in history:
            self.assertTrue(hasattr(entry, "version"),
                            f"History entry {entry} missing 'version' attribute")
            self.assertTrue(hasattr(entry, "semantic_version"),
                            f"History entry {entry} missing 'semantic_version' attribute")

    # ========== FAILURE SCENARIOS ==========

    def test_create_version_not_found(self):
        """Test creating version with non-existent dataset (failure scenario)"""

        fake_id = str(uuid.uuid4())

        with self.assertRaises(NotFoundError) as cm:
            self.service.create_version(
                dataset_id=fake_id, tenant_id=str(self.tenant.id), semantic_version="1.1.0"
            )

        self.assertEqual(cm.exception.code, "NOT_FOUND")

    def test_compare_versions_not_found(self):
        """Test comparing versions with non-existent dataset (failure scenario)"""

        fake_id = str(uuid.uuid4())

        with self.assertRaises(NotFoundError) as cm:
            self.service.compare_versions(
                dataset_id_1=str(self.dataset.id),
                dataset_id_2=fake_id,
                tenant_id=str(self.tenant.id),
            )

        self.assertEqual(cm.exception.code, "NOT_FOUND")

    def test_get_version_history_not_found(self):
        """Test getting version history for non-existent dataset (failure scenario)"""

        fake_id = str(uuid.uuid4())

        with self.assertRaises(NotFoundError) as cm:
            self.service.get_version_history(dataset_id=fake_id, tenant_id=str(self.tenant.id))

        self.assertEqual(cm.exception.code, "NOT_FOUND")

    # ========== EDGE CASES ==========

    def test_create_version_without_semantic_version(self):
        """Test creating version without semantic version (edge case)"""
        new_version = self.service.create_version(
            dataset_id=str(self.dataset.id),
            tenant_id=str(self.tenant.id),
            semantic_version=None,
            is_current=True,
        )

        new_version.refresh_from_db()
        # Should auto-generate semantic version or be None
        self.assertIsNotNone(new_version)

    def test_create_version_with_empty_tags(self):
        """Test creating version with empty tags (edge case)"""
        new_version = self.service.create_version(
            dataset_id=str(self.dataset.id),
            tenant_id=str(self.tenant.id),
            semantic_version="1.1.0",
            version_tags=[],
            is_current=True,
        )

        new_version.refresh_from_db()
        self.assertEqual(new_version.version_tags, [])

    def test_compare_versions_same_dataset(self):
        """Test comparing a dataset version with itself returns no changes."""
        result = self.service.compare_versions(
            dataset_id_1=str(self.dataset.id),
            dataset_id_2=str(self.dataset.id),
            tenant_id=str(self.tenant.id),
        )

        self.assertIsInstance(result, dict)
        self.assertIn("schema_diff", result)
        self.assertEqual(len(result["schema_diff"].get("changes", [])), 0)

    def test_get_version_history_single_version(self):
        """Test getting version history for dataset with single version."""
        history = self.service.get_version_history(
            dataset_id=str(self.dataset.id), tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(history, list)
        self.assertGreaterEqual(len(history), 1)
        # The history must include the dataset itself.
        self.assertEqual(history[0].id, self.dataset.id)
        self.assertEqual(history[0].version, 1)

    # ========== ERROR HANDLING ==========

    def test_create_version_invalid_tenant(self):
        """Test creating version with invalid tenant_id raises NotFoundError."""

        fake_tenant_id = str(uuid.uuid4())

        with self.assertRaises(NotFoundError) as cm:
            self.service.create_version(
                dataset_id=str(self.dataset.id), tenant_id=fake_tenant_id, semantic_version="1.1.0"
            )

        self.assertEqual(getattr(cm.exception, "code", None), "NOT_FOUND")

    def test_compare_versions_nonexistent_dataset(self):
        """compare_versions with non-existent dataset raises NotFoundError."""

        fake_id = str(uuid.uuid4())
        with self.assertRaises(NotFoundError) as cm:
            self.service.compare_versions(
                dataset_id_1=fake_id,
                dataset_id_2=str(self.dataset.id),
                tenant_id=str(self.tenant.id),
            )

        self.assertEqual(getattr(cm.exception, "code", None), "NOT_FOUND")

    def test_get_version_history_with_persisted_dataset(self):
        """get_version_history returns history entries with expected attributes."""
        history = self.service.get_version_history(
            dataset_id=str(self.dataset.id), tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(history, list)
        self.assertGreaterEqual(len(history), 1)
        self.assertIn(self.dataset.id, {v.id for v in history})
