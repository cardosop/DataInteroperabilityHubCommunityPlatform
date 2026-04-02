"""
Unit tests for DatasetService.

Tests cover all service methods with 100% coverage target.

All tests use real implementations (no mocks of hub services).
S3 operations use real boto3 client with graceful handling when S3 unavailable.
"""
import uuid

import pytest
from hub.apps.assets.models import Asset
from hub.apps.core.services.base import NotFoundError, ValidationError
from hub.apps.datasets.models import Dataset
from hub.apps.datasets.tests.test_base import DatasetsTestBase
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)


class DatasetServiceTest(DatasetsTestBase):
    """Test DatasetService operations"""

    def setUp(self):
        """Set up test data"""
        super().setUp()

    def test_create_dataset_success_creates_dataset(self):
        """Test successful dataset creation creates a persisted dataset."""
        dataset = self.service.create_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            file_id=str(self.file.id),
        )

        self.assertIsNotNone(dataset)
        self.assertIsNotNone(dataset.id)
        # Verify persisted to DB
        self.assertTrue(
            Dataset.objects.filter(id=dataset.id).exists()
        )

    def test_create_dataset_success_sets_file_id(self):
        """Test successful dataset creation sets file_id correctly."""
        dataset = self.service.create_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            file_id=str(self.file.id),
        )

        self.assertEqual(dataset.file_id, self.file.id)

    def test_create_dataset_file_not_found(self):
        """Test dataset creation with non-existent file"""
        with self.assertRaises(NotFoundError):
            self.service.create_dataset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                file_id="00000000-0000-0000-0000-000000000000",
            )

    def test_create_dataset_file_not_active(self):
        """Test dataset creation with inactive file"""
        self.file.status = FileStatus.FAILED
        self.file.save()

        with self.assertRaises(ValidationError) as cm:
            self.service.create_dataset(
                tenant_id=str(self.tenant.id), user_id=str(self.user.id), file_id=str(self.file.id)
            )

        self.assertEqual(cm.exception.code, "VALIDATION_ERROR")

    def test_get_dataset_success(self):
        """Test successful dataset retrieval"""
        dataset = Dataset.objects.create(
            tenant=self.tenant, file=self.file, format="CSV", schema_json={"fields": []}
        )

        retrieved = self.service.get_dataset(
            dataset_id=str(dataset.id), tenant_id=str(self.tenant.id)
        )

        self.assertEqual(retrieved.id, dataset.id)

    # ========== FAILURE SCENARIOS ==========

    def test_get_dataset_not_found(self):
        """Test retrieving non-existent dataset (failure scenario)"""
        import uuid

        fake_id = str(uuid.uuid4())

        with self.assertRaises(NotFoundError) as cm:
            self.service.get_dataset(dataset_id=fake_id, tenant_id=str(self.tenant.id))

        self.assertEqual(cm.exception.code, "NOT_FOUND")

    def test_get_dataset_wrong_tenant(self):
        """Test retrieving dataset from wrong tenant (failure scenario)"""
        # Create another tenant and dataset
        _sfx = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(name=f"Other Tenant {_sfx}", slug=f"other-tenant-{_sfx}")
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
            self.service.get_dataset(
                dataset_id=str(other_dataset.id), tenant_id=str(self.tenant.id)
            )

        self.assertEqual(cm.exception.code, "NOT_FOUND")

    def test_update_dataset_not_found(self):
        """Test updating non-existent dataset (failure scenario)"""
        import uuid

        fake_id = str(uuid.uuid4())

        with self.assertRaises(NotFoundError) as cm:
            self.service.update_dataset(
                dataset_id=fake_id,
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                format="JSON",
            )

        self.assertEqual(cm.exception.code, "NOT_FOUND")

    def test_delete_dataset_not_found(self):
        """Test deleting non-existent dataset (failure scenario)"""
        import uuid

        fake_id = str(uuid.uuid4())

        with self.assertRaises(NotFoundError) as cm:
            self.service.destroy_dataset(
                dataset_id=fake_id, tenant_id=str(self.tenant.id), user_id=str(self.user.id)
            )

        self.assertEqual(cm.exception.code, "NOT_FOUND")

    # ========== EDGE CASES ==========

    def test_create_dataset_empty_schema_creates_dataset(self):
        """Test creating dataset with empty schema creates dataset (edge case)"""
        # Create dataset directly (bypassing S3 schema inference)
        dataset = Dataset.objects.create(
            tenant=self.tenant, file=self.file, format="CSV", schema_json={}, created_by=self.user
        )

        self.assertIsNotNone(dataset)

    def test_create_dataset_empty_schema_sets_empty_schema_json(self):
        """Test creating dataset with empty schema sets schema_json to empty dict (edge case)"""
        # Create dataset directly (bypassing S3 schema inference)
        dataset = Dataset.objects.create(
            tenant=self.tenant, file=self.file, format="CSV", schema_json={}, created_by=self.user
        )

        self.assertEqual(dataset.schema_json, {})

    def test_create_dataset_with_asset(self):
        """Test creating dataset with asset_id (edge case)"""
        asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", created_by=self.user
        )

        # Create dataset directly (bypassing S3 for this test)
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            file=self.file,
            asset=asset,
            format="CSV",
            schema_json={"fields": []},
            created_by=self.user,
        )

        self.assertEqual(dataset.asset, asset)

    def test_get_dataset_with_invalid_uuid(self):
        """Test retrieving dataset with invalid UUID format (edge case)"""
        # execute_with_metrics wraps Django's UUIDField ValidationError as
        # hub.apps.core.services.base.ValidationError
        with self.assertRaises(ValidationError) as cm:
            self.service.get_dataset(dataset_id="invalid-uuid", tenant_id=str(self.tenant.id))

        self.assertIn("not a valid UUID", str(cm.exception))

    def test_create_dataset_version_starts_at_one(self):
        """Test that dataset version starts at 1 (edge case)"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            file=self.file,
            format="CSV",
            schema_json={"fields": []},
            created_by=self.user,
        )

        # Version should start at 1
        self.assertEqual(dataset.version, 1)
