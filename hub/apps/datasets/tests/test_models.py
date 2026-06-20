"""
Unit tests for Dataset model.
"""

import uuid

import pytest
from django.db import IntegrityError

from hub.apps.assets.models import Asset
from hub.apps.datasets.models import Dataset
from hub.apps.datasets.tests.test_base import DatasetsTestBase

pytestmark = pytest.mark.django_db(transaction=True)


class DatasetModelTest(DatasetsTestBase):
    """Test Dataset model"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
        )

    def test_create_dataset_sets_tenant_asset_file(self):
        """Test dataset creation sets tenant, asset, and file correctly"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=1,
            format="CSV",
            row_count=100,
        )

        self.assertEqual(dataset.tenant, self.tenant)
        self.assertEqual(dataset.asset, self.asset)
        self.assertEqual(dataset.file, self.file)

    def test_create_dataset_sets_version_format_row_count(self):
        """Test dataset creation sets version, format, and row_count correctly"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=1,
            format="CSV",
            row_count=100,
        )

        self.assertEqual(dataset.version, 1)
        self.assertEqual(dataset.format, "CSV")
        self.assertEqual(dataset.row_count, 100)

    # ========== SUCCESS SCENARIOS ==========

    def test_create_dataset_with_all_fields_creates_dataset(self):
        """Test dataset creation with all fields creates dataset (success scenario)"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=1,
            format="CSV",
            row_count=1000,
            schema_json={"fields": [{"name": "id", "type": "string"}]},
            sample_data_json=[{"id": "1"}, {"id": "2"}],
            semantic_version="1.0.0",
            version_tags=["production"],
            is_current=True,
            created_by=self.user,
        )

        self.assertEqual(dataset.tenant, self.tenant)
        self.assertEqual(dataset.asset, self.asset)
        self.assertEqual(dataset.file, self.file)
        self.assertEqual(dataset.version, 1)
        self.assertEqual(dataset.format, "CSV")
        self.assertEqual(dataset.row_count, 1000)
        self.assertEqual(dataset.semantic_version, "1.0.0")

    def test_create_dataset_with_all_fields_sets_semantic_version(self):
        """Test dataset creation with all fields sets semantic_version correctly (success scenario)"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=1,
            format="CSV",
            row_count=1000,
            schema_json={"fields": [{"name": "id", "type": "string"}]},
            sample_data_json=[{"id": "1"}, {"id": "2"}],
            semantic_version="1.0.0",
            version_tags=["production"],
            is_current=True,
            created_by=self.user,
        )

        self.assertEqual(dataset.semantic_version, "1.0.0")

    def test_create_dataset_with_all_fields_sets_version_tags_and_is_current(self):
        """Test dataset creation with all fields sets version_tags and is_current correctly (success scenario)"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=1,
            format="CSV",
            row_count=1000,
            schema_json={"fields": [{"name": "id", "type": "string"}]},
            sample_data_json=[{"id": "1"}, {"id": "2"}],
            semantic_version="1.0.0",
            version_tags=["production"],
            is_current=True,
            created_by=self.user,
        )

        self.assertEqual(dataset.version_tags, ["production"])
        self.assertTrue(dataset.is_current)

    def test_create_dataset_without_asset_sets_asset_to_none(self):
        """Test dataset creation without asset sets asset to None (success scenario)"""
        dataset = Dataset.objects.create(
            tenant=self.tenant, file=self.file, version=1, format="CSV", created_by=self.user
        )

        self.assertIsNone(dataset.asset)

    def test_create_dataset_without_asset_sets_file_correctly(self):
        """Test dataset creation without asset sets file correctly (success scenario)"""
        dataset = Dataset.objects.create(
            tenant=self.tenant, file=self.file, version=1, format="CSV", created_by=self.user
        )

        self.assertEqual(dataset.file, self.file)

    # ========== FAILURE SCENARIOS ==========

    def test_create_dataset_missing_required_fields(self):
        """Test dataset creation with missing required fields (failure scenario)"""
        # Missing tenant — the NOT NULL FK constraint raises IntegrityError.
        with self.assertRaises(IntegrityError):
            Dataset.objects.create(file=self.file, version=1, format="CSV")

    def test_create_dataset_invalid_file(self):
        """Test dataset creation with invalid file reference raises IntegrityError"""
        fake_file_id = uuid.uuid4()

        # Django defers FK checks until transaction commit
        # Force immediate FK validation using PostgreSQL constraint check
        from django.db import connection

        with self.assertRaises(IntegrityError):
            Dataset.objects.create(
                tenant=self.tenant, file_id=fake_file_id, version=1, format="CSV"
            )
            # Force FK constraint check immediately (PostgreSQL specific)
            # This will trigger the FK validation that Django normally defers until commit
            with connection.cursor() as cursor:
                cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")

    # ========== EDGE CASES ==========

    def test_create_dataset_zero_row_count(self):
        """Test dataset creation with zero row_count (edge case)"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=1,
            format="CSV",
            row_count=0,
            created_by=self.user,
        )

        self.assertEqual(dataset.row_count, 0)

    def test_create_dataset_very_large_row_count(self):
        """Test dataset creation with very large row_count (edge case)"""
        large_count = 999999999
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=1,
            format="CSV",
            row_count=large_count,
            created_by=self.user,
        )

        self.assertEqual(dataset.row_count, large_count)

    def test_create_dataset_empty_schema_json(self):
        """Test dataset creation with empty schema_json (edge case)"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=1,
            format="CSV",
            schema_json={},
            created_by=self.user,
        )

        self.assertEqual(dataset.schema_json, {})

    def test_create_dataset_complex_schema_json(self):
        """Test dataset creation with complex schema_json (edge case)"""
        complex_schema = {
            "fields": [
                {"name": "id", "type": "string", "format": "uuid"},
                {"name": "name", "type": "string", "maxLength": 255},
                {
                    "name": "metadata",
                    "type": "object",
                    "properties": {
                        "created_at": {"type": "datetime"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                    },
                },
            ]
        }

        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=1,
            format="JSON",
            schema_json=complex_schema,
            created_by=self.user,
        )

        self.assertEqual(dataset.schema_json, complex_schema)

    def test_create_dataset_version_starts_at_one(self):
        """Test that dataset version starts at 1 (edge case)"""
        dataset = Dataset.objects.create(
            tenant=self.tenant, asset=self.asset, file=self.file, format="CSV", created_by=self.user
        )

        # Version should default to 1
        self.assertEqual(dataset.version, 1)

    def test_create_dataset_multiple_versions(self):
        """Test creating multiple dataset versions (edge case)"""
        dataset_v1 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=1,
            format="CSV",
            is_current=True,
            created_by=self.user,
        )

        dataset_v2 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=2,
            format="CSV",
            parent_version=dataset_v1,
            is_current=True,
            created_by=self.user,
        )

        # Mark v1 as not current
        dataset_v1.is_current = False
        dataset_v1.save()

        self.assertEqual(dataset_v1.version, 1)
        self.assertEqual(dataset_v2.version, 2)
        self.assertEqual(dataset_v2.parent_version, dataset_v1)
        self.assertFalse(dataset_v1.is_current)
        self.assertTrue(dataset_v2.is_current)

    # ========== ERROR HANDLING ==========

    def test_create_dataset_with_valid_fields(self):
        """Minimal required fields produce a valid Dataset with correct defaults."""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=1,
            format="CSV",
            created_by=self.user,
        )
        self.assertEqual(dataset.tenant, self.tenant)
        self.assertEqual(dataset.version, 1)
        self.assertEqual(dataset.format, "CSV")
        self.assertEqual(dataset.status, "ACTIVE")  # default
        self.assertTrue(dataset.is_current)  # default

    def test_dataset_clean_validation(self):
        """dataset.clean() must succeed for a dataset with all required fields."""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=1,
            format="CSV",
            created_by=self.user,
        )

        # Dataset with all required fields must validate without raising.
        dataset.clean()
        # Verify model state is intact after validation.
        self.assertEqual(dataset.version, 1)
        self.assertEqual(dataset.format, "CSV")
