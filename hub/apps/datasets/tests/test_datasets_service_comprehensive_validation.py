"""
Comprehensive Validation Tests for Datasets Service

This test suite provides engineering-grade validation for:
- 10.1.29.1: Dataset CRUD Operations Testing
- 10.1.29.2: Dataset Versioning Testing
- 10.1.29.3: Schema Evolution Testing
- 10.1.29.4: Time Travel Query Testing
- 10.1.29.5: Dataset Rollback Testing
- 10.1.29.6: Datasets Service Integration with ODPS

All tests use real services (no mocks/stubs) and follow TDD principles.
"""

import json
import uuid

import pytest

pytestmark = pytest.mark.slow
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract, ContractStatus, OriginalFormat, OriginalSpecType
from hub.apps.core.services.base import NotFoundError
from hub.apps.datasets.models import Dataset
from hub.apps.datasets.rollback import RollbackConfig, VersionRollbackManager
from hub.apps.datasets.schema_evolution import CompatibilityLevel, SchemaEvolutionTracker
from hub.apps.datasets.services import DatasetService
from hub.apps.datasets.time_travel import TimeTravelQuery
from hub.apps.datasets.versioning_service import VersioningService
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import KYCStatus, TenantStatus
from hub.apps.users.models import UserStatus

# Lazy imports — the test runner may discover this module before the
# ``tests.fixtures`` package is fully importable in some discovery
# orders (e.g. when run with other test suites that load factory
# modules first).  Deferring to first call avoids a _FailedTest.
_TenantFactory = None
_UserFactory = None
_wait_for_event_persistence = None


def _get_TenantFactory():
    global _TenantFactory
    if _TenantFactory is None:
        from tests.fixtures.test_data_factories import TenantFactory as TF

        _TenantFactory = TF
    return _TenantFactory


def _get_UserFactory():
    global _UserFactory
    if _UserFactory is None:
        from tests.fixtures.test_data_factories import UserFactory as UF

        _UserFactory = UF
    return _UserFactory


def _get_wait_for_event_persistence():
    global _wait_for_event_persistence
    if _wait_for_event_persistence is None:
        from tests.utils.wait_helpers import wait_for_event_persistence as w

        _wait_for_event_persistence = w
    return _wait_for_event_persistence


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def setUpModule():
    """Reset stale connections before any test in this module runs.

    This module's tests are connection-heavy — each setUp/tearDown
    cycle opens and closes connections aggressively.  When run in a
    shared ``--keepdb`` pool alongside other test suites, the pool
    can be exhausted before the first test starts.
    connections before the first class loads.
    """
    from django.db import connections

    connections["default"]
    connections["default"].close()


def tearDownModule():
    """Close connections after all tests in this module have run."""
    from django.db import connections

    connections.close_all()


class TestDatasetCRUDOperations(TestCase):
    """
    10.1.29.1: Dataset CRUD Operations Testing

    Tests dataset creation, update, delete, retrieval, listing with filters,
    pagination, and sorting.
    """

    # Disable automatic database flush to avoid foreign key constraint issues
    reset_sequences = False
    serialized_rollback = False

    def setUp(self):
        """Set up test fixtures"""
        cache.clear()
        unique_id = uuid.uuid4().hex[:8]
        self.tenant = _get_TenantFactory().create_tenant(
            name=f"Test Tenant {unique_id}",
            slug=f"test-tenant-{unique_id}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = _get_UserFactory().create_user(
            email=f"test-{unique_id}@example.com", tenant=self.tenant, status=UserStatus.ACTIVE
        )
        self.service = DatasetService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create test files with unique names to avoid
        # unique_active_filename_per_tenant collisions.
        self.file1 = File.objects.create(
            tenant=self.tenant,
            name=f"ds1-{uuid.uuid4().hex[:8]}.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            storage_path=f"{self.tenant.id}/{uuid.uuid4()}/dataset1.csv",
        )
        self.file2 = File.objects.create(
            tenant=self.tenant,
            name=f"ds2-{uuid.uuid4().hex[:8]}.json",
            content_type="application/json",
            size=2048,
            status=FileStatus.ACTIVE,
            storage_path=f"{self.tenant.id}/{uuid.uuid4()}/dataset2.json",
        )

        # Create test asset with unique key
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-{uuid.uuid4().hex[:8]}",
            name="Test Asset",
            description="Test asset for datasets",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

    def test_dataset_creation(self):
        """Test dataset creation"""
        dataset = self.service.create_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            file_id=str(self.file1.id),
            asset_id=str(self.asset.id),
        )

        self.assertIsNotNone(dataset)
        self.assertEqual(str(dataset.tenant_id), str(self.tenant.id))
        self.assertEqual(str(dataset.file_id), str(self.file1.id))
        self.assertEqual(str(dataset.asset_id), str(self.asset.id))
        self.assertEqual(dataset.version, 1)
        self.assertIsNotNone(dataset.schema_json)
        self.assertIsNotNone(dataset.format)

    def test_dataset_creation_without_asset(self):
        """Test dataset creation without asset"""
        dataset = self.service.create_dataset(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id), file_id=str(self.file1.id)
        )

        self.assertIsNotNone(dataset)
        self.assertEqual(str(dataset.tenant_id), str(self.tenant.id))
        self.assertIsNone(dataset.asset)
        self.assertEqual(dataset.version, 1)

    def test_dataset_creation_invalid_file(self):
        """Test dataset creation with invalid file ID"""
        with self.assertRaises(NotFoundError):
            self.service.create_dataset(
                tenant_id=str(self.tenant.id), user_id=str(self.user.id), file_id=str(uuid.uuid4())
            )

    def test_dataset_retrieval(self):
        """Test dataset retrieval"""
        # Create dataset
        created_dataset = self.service.create_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            file_id=str(self.file1.id),
            asset_id=str(self.asset.id),
        )

        # Retrieve dataset
        retrieved_dataset = self.service.get_dataset(
            dataset_id=str(created_dataset.id), tenant_id=str(self.tenant.id)
        )

        self.assertIsNotNone(retrieved_dataset)
        self.assertEqual(str(retrieved_dataset.id), str(created_dataset.id))
        self.assertEqual(str(retrieved_dataset.tenant_id), str(self.tenant.id))

    def test_dataset_retrieval_not_found(self):
        """Test dataset retrieval with invalid ID"""
        with self.assertRaises(NotFoundError):
            self.service.get_dataset(dataset_id=str(uuid.uuid4()), tenant_id=str(self.tenant.id))

    def test_dataset_listing_with_filters(self):
        """Test dataset listing with filters"""
        # Create multiple datasets
        self.service.create_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            file_id=str(self.file1.id),
            asset_id=str(self.asset.id),
        )

        self.service.create_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            file_id=str(self.file2.id),
            asset_id=str(self.asset.id),
        )

        # Filter by asset
        datasets = Dataset.objects.filter(tenant=self.tenant, asset=self.asset)
        self.assertEqual(datasets.count(), 2)

        # Filter by format
        csv_datasets = Dataset.objects.filter(tenant=self.tenant, format="CSV")
        self.assertGreaterEqual(csv_datasets.count(), 1)

    def test_dataset_pagination(self):
        """Test dataset pagination"""
        # Create multiple datasets with unique names to avoid
        # unique_active_filename_per_tenant collisions with setUp.
        for i in range(15):
            file = File.objects.create(
                tenant=self.tenant,
                name=f"paginate-{uuid.uuid4().hex[:8]}.csv",
                content_type="text/csv",
                size=1024,
                status=FileStatus.ACTIVE,
                storage_path=f"{self.tenant.id}/{uuid.uuid4()}/paginate.csv",
            )
            self.service.create_dataset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                file_id=str(file.id),
                asset_id=str(self.asset.id),
            )

        # Test pagination
        page1 = Dataset.objects.filter(tenant=self.tenant)[:10]
        page2 = Dataset.objects.filter(tenant=self.tenant)[10:20]

        self.assertEqual(len(page1), 10)
        self.assertGreaterEqual(len(page2), 5)

    def test_dataset_sorting(self):
        """Test dataset sorting"""
        # Create datasets with different timestamps
        dataset1 = self.service.create_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            file_id=str(self.file1.id),
            asset_id=str(self.asset.id),
        )

        # Wait a bit to ensure different timestamps
        _get_wait_for_event_persistence()()

        dataset2 = self.service.create_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            file_id=str(self.file2.id),
            asset_id=str(self.asset.id),
        )

        # Test sorting by created_at descending
        datasets_desc = Dataset.objects.filter(tenant=self.tenant).order_by("-created_at")
        self.assertEqual(str(datasets_desc.first().id), str(dataset2.id))

        # Test sorting by created_at ascending
        datasets_asc = Dataset.objects.filter(tenant=self.tenant).order_by("created_at")
        self.assertEqual(str(datasets_asc.first().id), str(dataset1.id))

    def test_dataset_update(self):
        """Test dataset update"""
        dataset = self.service.create_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            file_id=str(self.file1.id),
            asset_id=str(self.asset.id),
        )

        # Update dataset metadata
        dataset.snapshot_metadata = {"updated": True}
        dataset.save()

        dataset.refresh_from_db()
        self.assertEqual(dataset.snapshot_metadata.get("updated"), True)

    def test_dataset_delete(self):
        """Test dataset deletion"""
        dataset = self.service.create_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            file_id=str(self.file1.id),
            asset_id=str(self.asset.id),
        )

        dataset_id = dataset.id

        # Delete dataset
        dataset.delete()

        # Verify deletion
        with self.assertRaises(Dataset.DoesNotExist):
            Dataset.objects.get(id=dataset_id)


class TestDatasetVersioning(TestCase):
    """
    10.1.29.2: Dataset Versioning Testing

    Tests dataset version creation, comparison, rollback, history, and queries.
    """

    # Disable automatic database flush to avoid foreign key constraint issues
    reset_sequences = False
    serialized_rollback = False

    def setUp(self):
        """Set up test fixtures"""
        cache.clear()
        unique_id = uuid.uuid4().hex[:8]
        self.tenant = _get_TenantFactory().create_tenant(
            name=f"Test Tenant {unique_id}",
            slug=f"test-tenant-{unique_id}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = _get_UserFactory().create_user(
            email=f"test-{unique_id}@example.com", tenant=self.tenant, status=UserStatus.ACTIVE
        )
        self.versioning_service = VersioningService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        # Create test file and asset
        self.file = File.objects.create(
            tenant=self.tenant,
            name=f"dataset-{uuid.uuid4().hex[:8]}.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            storage_path=f"{self.tenant.id}/{uuid.uuid4()}/dataset.csv",
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-{uuid.uuid4().hex[:8]}",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        # Create initial dataset
        dataset_service = DatasetService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))
        self.dataset_v1 = dataset_service.create_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            file_id=str(self.file.id),
            asset_id=str(self.asset.id),
        )

    def test_dataset_version_creation(self):
        """Test dataset version creation"""
        # Create version 2
        new_dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json=self.dataset_v1.schema_json,
            sample_data_json=self.dataset_v1.sample_data_json,
            row_count=self.dataset_v1.row_count,
            format=self.dataset_v1.format,
            version=2,
            parent_version=self.dataset_v1,
            created_by=self.user,
        )

        # Initialize version using service
        updated_dataset = self.versioning_service.create_version(
            dataset_id=str(new_dataset.id),
            tenant_id=str(self.tenant.id),
            parent_version_id=str(self.dataset_v1.id),
            semantic_version="2.0.0",
            is_current=True,
        )

        self.assertIsNotNone(updated_dataset)
        self.assertEqual(updated_dataset.version, 2)
        self.assertEqual(updated_dataset.semantic_version, "2.0.0")
        self.assertEqual(updated_dataset.parent_version_id, self.dataset_v1.id)
        self.assertTrue(updated_dataset.is_current)

    def test_version_comparison(self):
        """Test version comparison"""
        # Create version 2 with different schema
        schema_v2 = self.dataset_v1.schema_json.copy() if self.dataset_v1.schema_json else {}
        if "fields" in schema_v2:
            schema_v2["fields"].append(
                {"name": "new_field", "data_type": "string", "nullable": True}
            )

        dataset_v2 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json=schema_v2,
            sample_data_json=self.dataset_v1.sample_data_json,
            row_count=self.dataset_v1.row_count,
            format=self.dataset_v1.format,
            version=2,
            parent_version=self.dataset_v1,
            created_by=self.user,
        )

        # Compare versions
        comparison = self.versioning_service.compare_versions(
            dataset_id_1=str(self.dataset_v1.id),
            dataset_id_2=str(dataset_v2.id),
            tenant_id=str(self.tenant.id),
        )

        self.assertIsNotNone(comparison)
        self.assertIsInstance(comparison, dict)
        # Check that comparison contains expected keys
        self.assertIn("schema_diff", comparison)

    def test_version_rollback(self):
        """Test version rollback"""
        # Create version 2
        Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json=self.dataset_v1.schema_json,
            sample_data_json=self.dataset_v1.sample_data_json,
            row_count=self.dataset_v1.row_count,
            format=self.dataset_v1.format,
            version=2,
            parent_version=self.dataset_v1,
            is_current=True,
            created_by=self.user,
        )

        # Mark v1 as not current
        self.dataset_v1.is_current = False
        self.dataset_v1.save()

        # Rollback to v1
        from hub.apps.datasets.versioning import VersionHistoryManager

        restored = VersionHistoryManager.restore_version(self.dataset_v1)

        self.assertIsNotNone(restored)
        self.assertTrue(restored.is_current)

    def test_version_history(self):
        """Test version history"""
        # Create multiple versions
        dataset_v2 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json=self.dataset_v1.schema_json,
            sample_data_json=self.dataset_v1.sample_data_json,
            row_count=self.dataset_v1.row_count,
            format=self.dataset_v1.format,
            version=2,
            parent_version=self.dataset_v1,
            created_by=self.user,
        )

        # Get version history
        history = self.versioning_service.get_version_history(
            dataset_id=str(dataset_v2.id), tenant_id=str(self.tenant.id), include_snapshots=False
        )

        self.assertIsNotNone(history)
        self.assertIsInstance(history, list)
        self.assertGreaterEqual(len(history), 1)

    def test_version_queries(self):
        """Test version queries"""
        # Create version 2
        dataset_v2 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json=self.dataset_v1.schema_json,
            sample_data_json=self.dataset_v1.sample_data_json,
            row_count=self.dataset_v1.row_count,
            format=self.dataset_v1.format,
            version=2,
            parent_version=self.dataset_v1,
            created_by=self.user,
        )

        # Query by version number
        version_1 = Dataset.objects.filter(tenant=self.tenant, asset=self.asset, version=1).first()
        self.assertIsNotNone(version_1)
        self.assertEqual(str(version_1.id), str(self.dataset_v1.id))

        # Query by semantic version
        if dataset_v2.semantic_version:
            semantic_version = Dataset.objects.filter(
                tenant=self.tenant, asset=self.asset, semantic_version=dataset_v2.semantic_version
            ).first()
            self.assertIsNotNone(semantic_version)


class TestSchemaEvolution(TestCase):
    """
    10.1.29.3: Schema Evolution Testing

    Tests schema changes, backward compatibility, migration, validation, and tracking.
    """

    # Disable automatic database flush to avoid foreign key constraint issues
    reset_sequences = False
    serialized_rollback = False

    def setUp(self):
        """Set up test fixtures"""
        cache.clear()
        unique_id = uuid.uuid4().hex[:8]
        self.tenant = _get_TenantFactory().create_tenant(
            name=f"Test Tenant {unique_id}",
            slug=f"test-tenant-{unique_id}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = _get_UserFactory().create_user(
            email=f"test-{unique_id}@example.com", tenant=self.tenant, status=UserStatus.ACTIVE
        )

        # Create test file and asset
        self.file = File.objects.create(
            tenant=self.tenant,
            name=f"dataset-{uuid.uuid4().hex[:8]}.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            storage_path=f"{self.tenant.id}/{uuid.uuid4()}/dataset.csv",
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-{uuid.uuid4().hex[:8]}",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        # Create initial dataset with schema
        dataset_service = DatasetService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))
        self.dataset_v1 = dataset_service.create_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            file_id=str(self.file.id),
            asset_id=str(self.asset.id),
        )

    def test_schema_changes(self):
        """Test schema changes detection"""
        # Create schema v1
        schema_v1 = {
            "fields": [
                {"name": "id", "data_type": "integer", "nullable": False},
                {"name": "name", "data_type": "string", "nullable": True},
            ]
        }

        # Create schema v2 with added field
        schema_v2 = {
            "fields": [
                {"name": "id", "data_type": "integer", "nullable": False},
                {"name": "name", "data_type": "string", "nullable": True},
                {"name": "email", "data_type": "string", "nullable": True},
            ]
        }

        # Calculate diff
        schema_diff = SchemaEvolutionTracker.calculate_schema_diff(schema_v1, schema_v2)

        self.assertIsNotNone(schema_diff)
        self.assertEqual(len(schema_diff.changes), 1)
        self.assertEqual(schema_diff.changes[0].change_type.value, "FIELD_ADDED")
        self.assertEqual(schema_diff.compatibility_level, CompatibilityLevel.BACKWARD_COMPATIBLE)

    def test_backward_compatibility(self):
        """Test backward compatibility detection"""
        schema_v1 = {
            "fields": [
                {"name": "id", "data_type": "integer", "nullable": False},
                {"name": "name", "data_type": "string", "nullable": True},
            ]
        }

        # Add field (backward compatible)
        schema_v2 = {
            "fields": [
                {"name": "id", "data_type": "integer", "nullable": False},
                {"name": "name", "data_type": "string", "nullable": True},
                {"name": "email", "data_type": "string", "nullable": True},
            ]
        }

        schema_diff = SchemaEvolutionTracker.calculate_schema_diff(schema_v1, schema_v2)
        self.assertEqual(schema_diff.compatibility_level, CompatibilityLevel.BACKWARD_COMPATIBLE)

    def test_schema_migration(self):
        """Test schema migration tracking"""
        # Create dataset v2 with different schema
        schema_v2 = self.dataset_v1.schema_json.copy() if self.dataset_v1.schema_json else {}
        if "fields" in schema_v2:
            schema_v2["fields"].append(
                {"name": "new_field", "data_type": "string", "nullable": True}
            )

        dataset_v2 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json=schema_v2,
            sample_data_json=self.dataset_v1.sample_data_json,
            row_count=self.dataset_v1.row_count,
            format=self.dataset_v1.format,
            version=2,
            parent_version=self.dataset_v1,
            created_by=self.user,
        )

        # Track schema version
        schema_version = SchemaEvolutionTracker.track_schema_version(
            dataset=dataset_v2, parent_dataset=self.dataset_v1
        )

        self.assertIsNotNone(schema_version)
        self.assertEqual(schema_version.dataset_id, dataset_v2.id)
        self.assertIsNotNone(schema_version.compatibility_level)

    def test_schema_validation(self):
        """Test schema validation"""
        # Valid schema
        valid_schema = {
            "fields": [
                {"name": "id", "data_type": "integer", "nullable": False},
                {"name": "name", "data_type": "string", "nullable": True},
            ]
        }

        schema_diff = SchemaEvolutionTracker.calculate_schema_diff({}, valid_schema)
        self.assertIsNotNone(schema_diff)

    def test_schema_evolution_tracking(self):
        """Test schema evolution tracking"""
        # Create dataset v2
        schema_v2 = self.dataset_v1.schema_json.copy() if self.dataset_v1.schema_json else {}
        if "fields" in schema_v2:
            schema_v2["fields"].append(
                {"name": "new_field", "data_type": "string", "nullable": True}
            )

        dataset_v2 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json=schema_v2,
            sample_data_json=self.dataset_v1.sample_data_json,
            row_count=self.dataset_v1.row_count,
            format=self.dataset_v1.format,
            version=2,
            parent_version=self.dataset_v1,
            created_by=self.user,
        )

        # Track evolution
        schema_version = SchemaEvolutionTracker.track_schema_version(
            dataset=dataset_v2, parent_dataset=self.dataset_v1
        )

        # Verify tracking
        self.assertIsNotNone(schema_version)
        self.assertIsNotNone(schema_version.change_summary)
        self.assertIsNotNone(schema_version.change_log)


class TestTimeTravelQueries(TestCase):
    """
    10.1.29.4: Time Travel Query Testing

    Tests time travel queries, historical data access, point-in-time queries,
    performance, and validation.
    """

    # Disable automatic database flush to avoid foreign key constraint issues
    reset_sequences = False
    serialized_rollback = False

    def setUp(self):
        """Set up test fixtures"""
        cache.clear()
        unique_id = uuid.uuid4().hex[:8]
        self.tenant = _get_TenantFactory().create_tenant(
            name=f"Test Tenant {unique_id}",
            slug=f"test-tenant-{unique_id}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = _get_UserFactory().create_user(
            email=f"test-{unique_id}@example.com", tenant=self.tenant, status=UserStatus.ACTIVE
        )

        # Create test file and asset
        self.file = File.objects.create(
            tenant=self.tenant,
            name=f"dataset-{uuid.uuid4().hex[:8]}.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            storage_path=f"{self.tenant.id}/{uuid.uuid4()}/dataset.csv",
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-{uuid.uuid4().hex[:8]}",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        # Create initial dataset
        dataset_service = DatasetService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))
        self.dataset_v1 = dataset_service.create_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            file_id=str(self.file.id),
            asset_id=str(self.asset.id),
        )

        # Wait to ensure different timestamps
        _get_wait_for_event_persistence()()

    def test_time_travel_queries(self):
        """Test time travel queries"""
        # Create version 2
        timestamp_before_v2 = timezone.now()
        _get_wait_for_event_persistence()()

        Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json=self.dataset_v1.schema_json,
            sample_data_json=self.dataset_v1.sample_data_json,
            row_count=self.dataset_v1.row_count,
            format=self.dataset_v1.format,
            version=2,
            parent_version=self.dataset_v1,
            created_by=self.user,
        )

        # Get version at timestamp
        version_at_timestamp = TimeTravelQuery.get_version_at_timestamp(
            asset_id=self.asset.id, tenant_id=self.tenant.id, timestamp=timestamp_before_v2
        )

        self.assertIsNotNone(version_at_timestamp)
        self.assertEqual(str(version_at_timestamp.id), str(self.dataset_v1.id))

    def test_historical_data_access(self):
        """Test historical data access"""
        # Create multiple versions
        Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json=self.dataset_v1.schema_json,
            sample_data_json=self.dataset_v1.sample_data_json,
            row_count=self.dataset_v1.row_count,
            format=self.dataset_v1.format,
            version=2,
            parent_version=self.dataset_v1,
            created_by=self.user,
        )

        # Access historical version
        historical = TimeTravelQuery.get_version_by_number(
            asset_id=self.asset.id, tenant_id=self.tenant.id, version_number=1
        )

        self.assertIsNotNone(historical)
        self.assertEqual(str(historical.id), str(self.dataset_v1.id))
        self.assertEqual(historical.version, 1)

    def test_point_in_time_queries(self):
        """Test point-in-time queries"""
        # Create version 2 with delay
        timestamp_v1 = self.dataset_v1.created_at
        _get_wait_for_event_persistence()()

        dataset_v2 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json=self.dataset_v1.schema_json,
            sample_data_json=self.dataset_v1.sample_data_json,
            row_count=self.dataset_v1.row_count,
            format=self.dataset_v1.format,
            version=2,
            parent_version=self.dataset_v1,
            created_by=self.user,
        )

        timestamp_v2 = dataset_v2.created_at

        # Query at point between v1 and v2
        midpoint = timestamp_v1 + (timestamp_v2 - timestamp_v1) / 2
        version_at_midpoint = TimeTravelQuery.get_version_at_timestamp(
            asset_id=self.asset.id, tenant_id=self.tenant.id, timestamp=midpoint
        )

        self.assertIsNotNone(version_at_midpoint)

    def test_time_travel_performance(self):
        """Test time travel performance"""
        # Create multiple versions
        datasets = [self.dataset_v1]
        for i in range(2, 6):
            _get_wait_for_event_persistence()()
            dataset = Dataset.objects.create(
                tenant=self.tenant,
                asset=self.asset,
                file=self.file,
                schema_json=self.dataset_v1.schema_json,
                sample_data_json=self.dataset_v1.sample_data_json,
                row_count=self.dataset_v1.row_count,
                format=self.dataset_v1.format,
                version=i,
                parent_version=datasets[-1],
                created_by=self.user,
            )
            datasets.append(dataset)

        # Measure query performance
        import time

        start = time.time()
        version = TimeTravelQuery.get_version_by_number(
            asset_id=self.asset.id, tenant_id=self.tenant.id, version_number=1
        )
        elapsed = time.time() - start

        self.assertIsNotNone(version)
        self.assertLess(elapsed, 1.0)  # Should be fast

    def test_time_travel_query_validation(self):
        """Test time travel query validation"""
        # Valid query
        version = TimeTravelQuery.get_version_by_number(
            asset_id=self.asset.id, tenant_id=self.tenant.id, version_number=1
        )
        self.assertIsNotNone(version)

        # Invalid version number
        invalid_version = TimeTravelQuery.get_version_by_number(
            asset_id=self.asset.id, tenant_id=self.tenant.id, version_number=999
        )
        self.assertIsNone(invalid_version)


class TestDatasetRollback(TestCase):
    """
    10.1.29.5: Dataset Rollback Testing

    Tests dataset rollback to previous version, data integrity, event publishing,
    compensation logic, and validation.
    """

    # Disable automatic database flush to avoid foreign key constraint issues
    reset_sequences = False
    serialized_rollback = False

    def setUp(self):
        """Set up test fixtures"""
        cache.clear()
        unique_id = uuid.uuid4().hex[:8]
        self.tenant = _get_TenantFactory().create_tenant(
            name=f"Test Tenant {unique_id}",
            slug=f"test-tenant-{unique_id}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = _get_UserFactory().create_user(
            email=f"test-{unique_id}@example.com", tenant=self.tenant, status=UserStatus.ACTIVE
        )

        # Create test file and asset
        self.file = File.objects.create(
            tenant=self.tenant,
            name=f"dataset-{uuid.uuid4().hex[:8]}.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            storage_path=f"{self.tenant.id}/{uuid.uuid4()}/dataset.csv",
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-{uuid.uuid4().hex[:8]}",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        # Create initial dataset
        dataset_service = DatasetService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))
        self.dataset_v1 = dataset_service.create_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            file_id=str(self.file.id),
            asset_id=str(self.asset.id),
        )

        # Create version 2
        self.dataset_v2 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json=self.dataset_v1.schema_json,
            sample_data_json=self.dataset_v1.sample_data_json,
            row_count=self.dataset_v1.row_count,
            format=self.dataset_v1.format,
            version=2,
            parent_version=self.dataset_v1,
            is_current=True,
            created_by=self.user,
        )

        # Mark v1 as not current
        self.dataset_v1.is_current = False
        self.dataset_v1.save()

    def test_dataset_rollback_to_previous_version(self):
        """Test dataset rollback to previous version"""
        # Execute rollback
        result = VersionRollbackManager.execute_rollback(
            dataset=self.dataset_v2,
            approved_by=self.user,
            reason="Test rollback",
            config=RollbackConfig(require_approval=False),
        )

        self.assertTrue(result.get("success", False))
        self.assertIn("rolled_back_to", result)

        # Verify v1 is now current
        self.dataset_v1.refresh_from_db()
        self.assertTrue(self.dataset_v1.is_current)

    def test_rollback_data_integrity(self):
        """Test rollback data integrity"""
        # Store original v1 data
        original_schema = self.dataset_v1.schema_json
        original_version = self.dataset_v1.version

        # Execute rollback
        result = VersionRollbackManager.execute_rollback(
            dataset=self.dataset_v2,
            approved_by=self.user,
            reason="Test rollback",
            config=RollbackConfig(require_approval=False),
        )

        self.assertTrue(result.get("success", False))

        # Verify data integrity
        self.dataset_v1.refresh_from_db()
        self.assertEqual(self.dataset_v1.schema_json, original_schema)
        self.assertEqual(self.dataset_v1.version, original_version)

    def test_rollback_compensation_logic(self):
        """Test rollback compensation logic"""
        # Execute rollback
        result = VersionRollbackManager.execute_rollback(
            dataset=self.dataset_v2,
            approved_by=self.user,
            reason="Test rollback",
            config=RollbackConfig(require_approval=False),
        )

        self.assertTrue(result.get("success", False))

        # Verify compensation: v2 should no longer be current
        self.dataset_v2.refresh_from_db()
        self.assertFalse(self.dataset_v2.is_current)

    def test_rollback_validation(self):
        """Test rollback validation"""
        # Rollback without parent version should fail
        dataset_no_parent = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json=self.dataset_v1.schema_json,
            sample_data_json=self.dataset_v1.sample_data_json,
            row_count=self.dataset_v1.row_count,
            format=self.dataset_v1.format,
            version=3,
            parent_version=None,
            is_current=False,
            created_by=self.user,
        )

        result = VersionRollbackManager.execute_rollback(
            dataset=dataset_no_parent,
            approved_by=self.user,
            reason="Test rollback",
            config=RollbackConfig(require_approval=False),
        )

        self.assertFalse(result.get("success", False))
        self.assertIn("error", result)


class TestDatasetsODPSIntegration(TestCase):
    """
    10.1.29.6: Datasets Service Integration with ODPS

    Tests datasets linked to ODPS contracts, ODPS product data in datasets,
    dataset versioning with ODPS, ODPS schema evolution, and ODPS time travel queries.
    """

    # Disable automatic database flush to avoid foreign key constraint issues
    reset_sequences = False
    serialized_rollback = False

    def setUp(self):
        """Set up test fixtures"""
        cache.clear()
        unique_id = uuid.uuid4().hex[:8]
        self.tenant = _get_TenantFactory().create_tenant(
            name=f"Test Tenant {unique_id}",
            slug=f"test-tenant-{unique_id}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = _get_UserFactory().create_user(
            email=f"test-{unique_id}@example.com", tenant=self.tenant, status=UserStatus.ACTIVE
        )

        # Create test file and asset
        self.file = File.objects.create(
            tenant=self.tenant,
            name=f"dataset-{uuid.uuid4().hex[:8]}.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            storage_path=f"{self.tenant.id}/{uuid.uuid4()}/dataset.csv",
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-{uuid.uuid4().hex[:8]}",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        # Create ODPS contract
        odps_contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product",
                        "description": "Test product description",
                    }
                },
                "contract": {
                    "spec": {
                        "apiVersion": "odcs/v3",
                        "kind": "DataContract",
                        "id": "test-contract",
                        "schema": {
                            "fields": [
                                {"name": "id", "type": "string"},
                                {"name": "name", "type": "string"},
                            ]
                        },
                    }
                },
            },
        }

        self.odps_contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            version=1,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(odps_contract_data),
            hub_contract_version="1.0.0",
            hub_contract_json=odps_contract_data,
            created_by=self.user,
        )

        # Create initial dataset
        dataset_service = DatasetService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))
        self.dataset_v1 = dataset_service.create_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            file_id=str(self.file.id),
            asset_id=str(self.asset.id),
        )

    def test_datasets_linked_to_odps_contracts(self):
        """Test datasets linked to ODPS contracts"""
        # Verify asset has ODPS contract
        contracts = Contract.objects.filter(
            tenant=self.tenant, asset=self.asset, original_spec_type=OriginalSpecType.ODPS
        )

        self.assertEqual(contracts.count(), 1)
        self.assertEqual(str(contracts.first().id), str(self.odps_contract.id))

        # Verify dataset is linked to asset with ODPS contract
        self.assertEqual(self.dataset_v1.asset_id, self.asset.id)
        self.assertEqual(
            self.asset.contracts.filter(original_spec_type=OriginalSpecType.ODPS).count(), 1
        )

    def test_odps_product_data_in_datasets(self):
        """Test ODPS product data in datasets"""
        # Verify ODPS contract data
        self.assertIsNotNone(self.odps_contract.hub_contract_json)
        product_data = self.odps_contract.hub_contract_json.get("product", {})
        self.assertIsNotNone(product_data)

        # Verify dataset can access ODPS data through asset
        asset_contracts = self.asset.contracts.filter(original_spec_type=OriginalSpecType.ODPS)
        self.assertEqual(asset_contracts.count(), 1)

    def test_dataset_versioning_with_odps(self):
        """Test dataset versioning with ODPS"""
        # Create version 2
        dataset_v2 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json=self.dataset_v1.schema_json,
            sample_data_json=self.dataset_v1.sample_data_json,
            row_count=self.dataset_v1.row_count,
            format=self.dataset_v1.format,
            version=2,
            parent_version=self.dataset_v1,
            created_by=self.user,
        )

        # Verify versioning works with ODPS contract
        self.assertEqual(dataset_v2.asset_id, self.asset.id)
        self.assertEqual(
            self.asset.contracts.filter(original_spec_type=OriginalSpecType.ODPS).count(), 1
        )

        # Version history should work
        versioning_service = VersioningService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        history = versioning_service.get_version_history(
            dataset_id=str(dataset_v2.id), tenant_id=str(self.tenant.id)
        )
        self.assertIsNotNone(history)

    def test_odps_schema_evolution(self):
        """Test ODPS schema evolution"""
        # Create version 2 with schema changes
        schema_v2 = self.dataset_v1.schema_json.copy() if self.dataset_v1.schema_json else {}
        if "fields" in schema_v2:
            schema_v2["fields"].append(
                {"name": "new_field", "data_type": "string", "nullable": True}
            )

        dataset_v2 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json=schema_v2,
            sample_data_json=self.dataset_v1.sample_data_json,
            row_count=self.dataset_v1.row_count,
            format=self.dataset_v1.format,
            version=2,
            parent_version=self.dataset_v1,
            created_by=self.user,
        )

        # Track schema evolution
        schema_version = SchemaEvolutionTracker.track_schema_version(
            dataset=dataset_v2, parent_dataset=self.dataset_v1
        )

        # Verify evolution tracking works with ODPS
        self.assertIsNotNone(schema_version)
        self.assertEqual(schema_version.dataset_id, dataset_v2.id)

    def test_odps_time_travel_queries(self):
        """Test ODPS time travel queries"""
        # Create version 2
        _get_wait_for_event_persistence()()

        Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json=self.dataset_v1.schema_json,
            sample_data_json=self.dataset_v1.sample_data_json,
            row_count=self.dataset_v1.row_count,
            format=self.dataset_v1.format,
            version=2,
            parent_version=self.dataset_v1,
            created_by=self.user,
        )

        # Time travel queries should work with ODPS-linked datasets
        version_at_timestamp = TimeTravelQuery.get_version_at_timestamp(
            asset_id=self.asset.id, tenant_id=self.tenant.id, timestamp=self.dataset_v1.created_at
        )

        self.assertIsNotNone(version_at_timestamp)
        self.assertEqual(str(version_at_timestamp.id), str(self.dataset_v1.id))

        # Verify ODPS contract is still linked
        self.assertEqual(
            self.asset.contracts.filter(original_spec_type=OriginalSpecType.ODPS).count(), 1
        )

    # ========== EDGE CASES ==========

    def test_comprehensive_validation_edge_case_empty_dataset(self):
        """Test comprehensive validation with empty dataset (edge case)"""
        # Use a distinct asset with unique key so (tenant, asset, version=1) is unique and we avoid
        # unique_dataset_version_per_asset / unique_asset_key_per_tenant collisions (e.g. with --reuse-db).
        unique_key = f"edge-empty-{uuid.uuid4().hex}"
        edge_asset = Asset.objects.create(
            tenant=self.tenant,
            key=unique_key,
            name="Edge Empty Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )
        empty_dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=edge_asset,
            file=self.file,
            schema_json={},
            format="CSV",
            version=1,
            created_by=self.user,
        )

        # Should handle empty dataset gracefully
        self.assertIsNotNone(empty_dataset)
        self.assertEqual(empty_dataset.schema_json, {})

    def test_comprehensive_validation_edge_case_large_dataset(self):
        """Test comprehensive validation with large dataset (edge case)"""
        # Use a distinct asset with unique key so (tenant, asset, version=1) is unique and we avoid
        # unique_dataset_version_per_asset / unique_asset_key_per_tenant collisions (e.g. with --reuse-db).
        unique_key = f"edge-large-{uuid.uuid4().hex}"
        edge_asset = Asset.objects.create(
            tenant=self.tenant,
            key=unique_key,
            name="Edge Large Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )
        large_schema = {"fields": [{"name": f"col{i}", "data_type": "string"} for i in range(1000)]}

        large_dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=edge_asset,
            file=self.file,
            schema_json=large_schema,
            format="CSV",
            version=1,
            created_by=self.user,
        )

        # Should handle large dataset gracefully
        self.assertIsNotNone(large_dataset)
        self.assertEqual(len(large_dataset.schema_json.get("fields", [])), 1000)

    def test_comprehensive_validation_edge_case_multiple_versions(self):
        """Test comprehensive validation with multiple versions (edge case)"""
        # setUp already created version 1 (self.dataset_v1). Create versions 2–5 with parent chain.
        # Use a dedicated asset so (tenant, asset, version) is unique and we avoid collisions with
        # any existing datasets for self.asset from other tests or --reuse-db state.
        multi_asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"edge-multi-version-{uuid.uuid4().hex}",
            name="Edge Multi Version Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )
        dataset_service = DatasetService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))
        parent = dataset_service.create_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            file_id=str(self.file.id),
            asset_id=str(multi_asset.id),
        )
        for version_number in (2, 3, 4, 5):
            parent = Dataset.objects.create(
                tenant=self.tenant,
                asset=multi_asset,
                file=self.file,
                schema_json={"fields": []},
                format="CSV",
                version=version_number,
                parent_version=parent,
                created_by=self.user,
            )

        # Should handle multiple versions gracefully
        versions = Dataset.objects.filter(tenant=self.tenant, asset=multi_asset)
        self.assertEqual(versions.count(), 5)
