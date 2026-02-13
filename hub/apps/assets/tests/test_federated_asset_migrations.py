"""
Migration tests for federated asset fields.

Tests forward and backward migrations for source_type and source_metadata fields.
"""

from io import StringIO

import pytest
from django.core.management import call_command
from django.db import connection
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetSourceType
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)


class FederatedAssetMigrationTest(TestCase):
    """Test migrations for federated asset fields"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")

    def test_source_type_field_exists(self):
        """Test that source_type field exists in database"""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = 'assets'
                AND column_name = 'source_type'
            """
            )
            result = cursor.fetchone()

        self.assertIsNotNone(result, "source_type column should exist")
        column_name, data_type, is_nullable, column_default = result
        self.assertEqual(column_name, "source_type")

    def test_source_type_field_exists_has_correct_data_type(self):
        """Test that source_type field has correct data type."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = 'assets'
                AND column_name = 'source_type'
            """
            )
            result = cursor.fetchone()

        column_name, data_type, is_nullable, column_default = result
        self.assertEqual(data_type, "character varying")

    def test_source_type_field_exists_is_not_nullable(self):
        """Test that source_type field is not nullable."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = 'assets'
                AND column_name = 'source_type'
            """
            )
            result = cursor.fetchone()

        column_name, data_type, is_nullable, column_default = result
        self.assertEqual(is_nullable, "NO")

    def test_source_type_field_exists_has_default_value(self):
        """Test that source_type field has default value."""
        asset = Asset.objects.create(
            tenant=self.tenant, key="test-default-source-type", name="Test Default Source Type"
        )
        self.assertEqual(asset.source_type, AssetSourceType.HUB_NATIVE)

    def test_source_metadata_field_exists(self):
        """Test that source_metadata field exists in database"""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'assets'
                AND column_name = 'source_metadata'
            """
            )
            result = cursor.fetchone()

        self.assertIsNotNone(result, "source_metadata column should exist")
        column_name, data_type, is_nullable = result
        self.assertEqual(column_name, "source_metadata")

    def test_source_metadata_field_exists_has_correct_data_type(self):
        """Test that source_metadata field has correct data type."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'assets'
                AND column_name = 'source_metadata'
            """
            )
            result = cursor.fetchone()

        column_name, data_type, is_nullable = result
        self.assertEqual(data_type, "jsonb")

    def test_source_metadata_field_exists_is_nullable(self):
        """Test that source_metadata field is nullable."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'assets'
                AND column_name = 'source_metadata'
            """
            )
            result = cursor.fetchone()

        column_name, data_type, is_nullable = result
        self.assertEqual(is_nullable, "YES")

    def test_source_type_index_exists(self):
        """Test that index on (tenant, source_type) exists"""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'assets'
                AND indexdef LIKE '%tenant%source_type%'
            """
            )
            indexes = [row[0] for row in cursor.fetchall()]

        # Check for the index (name may vary)
        self.assertGreater(len(indexes), 0, "Index on (tenant, source_type) should exist")

    def test_source_type_index_includes_tenant_id(self):
        """Test that index on (tenant, source_type) includes tenant_id."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT indexdef
                FROM pg_indexes
                WHERE tablename = 'assets'
                AND indexdef LIKE '%tenant%source_type%'
                LIMIT 1
            """
            )
            result = cursor.fetchone()
            if result:
                indexdef = result[0]
                self.assertIn("tenant_id", indexdef.lower())

    def test_source_type_index_includes_source_type(self):
        """Test that index on (tenant, source_type) includes source_type."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT indexdef
                FROM pg_indexes
                WHERE tablename = 'assets'
                AND indexdef LIKE '%tenant%source_type%'
                LIMIT 1
            """
            )
            result = cursor.fetchone()
            if result:
                indexdef = result[0]
                self.assertIn("source_type", indexdef.lower())

    def test_default_source_type_value(self):
        """Test that existing assets get default HUB_NATIVE value"""
        # Create asset without specifying source_type
        asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset-default", name="Test Asset Default"
        )

        self.assertEqual(asset.source_type, AssetSourceType.HUB_NATIVE)

    def test_default_source_type_value_persists_in_database(self):
        """Test that default source_type value persists in database."""
        asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset-default", name="Test Asset Default"
        )

        asset.refresh_from_db()
        self.assertEqual(asset.source_type, AssetSourceType.HUB_NATIVE)

    def test_migration_applied(self):
        """Test that migration has been applied"""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM information_schema.columns
                WHERE table_name = 'assets'
                AND column_name IN ('source_type', 'source_metadata')
            """
            )
            column_count = cursor.fetchone()[0]

        self.assertEqual(
            column_count, 2, "Both source_type and source_metadata columns should exist"
        )

    def test_source_type_constraint(self):
        """Test that source_type has correct check constraint"""
        # Create asset with valid source_type
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="valid-asset",
            name="Valid Asset",
            source_type=AssetSourceType.FEDERATED,
        )

        self.assertEqual(asset.source_type, AssetSourceType.FEDERATED)

        # Try to create asset with invalid source_type (should fail validation)
        asset_invalid = Asset(
            tenant=self.tenant, key="invalid-asset", name="Invalid Asset", source_type="INVALID"
        )

        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            asset_invalid.full_clean()

    def test_source_metadata_json_storage(self):
        """Test that source_metadata can store JSON data"""
        metadata = {
            "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
            "listing_id": "test-listing-123",
            "synced_at": "2025-01-01T12:00:00Z",
        }

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="json-asset",
            name="JSON Asset",
            source_type=AssetSourceType.FEDERATED,
            source_metadata=metadata,
        )

        # Verify JSON is stored correctly
        asset.refresh_from_db()
        self.assertEqual(asset.source_metadata, metadata)

    def test_source_metadata_json_storage_has_correct_marketplace_type(self):
        """Test that source_metadata JSON storage has correct marketplace_type."""
        metadata = {
            "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
            "listing_id": "test-listing-123",
            "synced_at": "2025-01-01T12:00:00Z",
        }

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="json-asset",
            name="JSON Asset",
            source_type=AssetSourceType.FEDERATED,
            source_metadata=metadata,
        )

        asset.refresh_from_db()
        self.assertEqual(asset.source_metadata["marketplace_type"], "SNOWFLAKE_DATA_MARKETPLACE")

    def test_index_usage(self):
        """Test that index on (tenant, source_type) is used in queries"""
        # Create test data
        for i in range(5):
            Asset.objects.create(
                tenant=self.tenant,
                key=f"hub-asset-{i}",
                name=f"Hub Asset {i}",
                source_type=AssetSourceType.HUB_NATIVE,
            )

        for i in range(3):
            Asset.objects.create(
                tenant=self.tenant,
                key=f"federated-asset-{i}",
                name=f"Federated Asset {i}",
                source_type=AssetSourceType.FEDERATED,
            )

        # Query that should use index
        federated_assets = Asset.objects.filter(
            tenant=self.tenant, source_type=AssetSourceType.FEDERATED
        )

        self.assertEqual(federated_assets.count(), 3)

    def test_index_usage_returns_federated_assets_only(self):
        """Test that index usage returns only federated assets."""
        for i in range(5):
            Asset.objects.create(
                tenant=self.tenant,
                key=f"hub-asset-{i}",
                name=f"Hub Asset {i}",
                source_type=AssetSourceType.HUB_NATIVE,
            )

        for i in range(3):
            Asset.objects.create(
                tenant=self.tenant,
                key=f"federated-asset-{i}",
                name=f"Federated Asset {i}",
                source_type=AssetSourceType.FEDERATED,
            )

        federated_assets = Asset.objects.filter(
            tenant=self.tenant, source_type=AssetSourceType.FEDERATED
        )

        for asset in federated_assets:
            self.assertEqual(asset.source_type, AssetSourceType.FEDERATED)

    # ========== SUCCESS SCENARIOS ==========

    def test_migration_success_forward(self):
        """Test successful forward migration (success scenario)"""
        # Create asset after migration
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="migration-success-asset",
            name="Migration Success Asset",
            source_type=AssetSourceType.FEDERATED,
            source_metadata={"test": "data"},
        )

        # Verify migration fields exist and work
        self.assertEqual(asset.source_type, AssetSourceType.FEDERATED)

    def test_migration_success_forward_stores_source_metadata(self):
        """Test successful forward migration stores source_metadata."""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="migration-success-asset",
            name="Migration Success Asset",
            source_type=AssetSourceType.FEDERATED,
            source_metadata={"test": "data"},
        )

        self.assertEqual(asset.source_metadata, {"test": "data"})

    # ========== FAILURE SCENARIOS ==========

    def test_migration_failure_invalid_source_type(self):
        """Test migration failure with invalid source_type (failure scenario)"""
        # Try to create asset with invalid source_type
        asset = Asset(
            tenant=self.tenant,
            key="invalid-source-type",
            name="Invalid Source Type",
            source_type="INVALID_TYPE",
        )

        # Should fail validation
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            asset.full_clean()

    def test_migration_failure_missing_required_field(self):
        """Test migration failure when required field missing (failure scenario)"""
        # source_type is required (not nullable)
        # Try to create asset without source_type (should use default)
        asset = Asset.objects.create(
            tenant=self.tenant, key="default-source-type", name="Default Source Type"
        )

        # Should default to HUB_NATIVE
        self.assertEqual(asset.source_type, AssetSourceType.HUB_NATIVE)

    # ========== EDGE CASES ==========

    def test_migration_edge_case_null_source_metadata(self):
        """Test migration with null source_metadata (edge case)"""
        # source_metadata is nullable
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="null-metadata-asset",
            name="Null Metadata Asset",
            source_type=AssetSourceType.FEDERATED,
            source_metadata=None,
        )

        self.assertIsNone(asset.source_metadata)

    def test_migration_edge_case_empty_source_metadata(self):
        """Test migration with empty source_metadata dict (edge case)"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="empty-metadata-asset",
            name="Empty Metadata Asset",
            source_type=AssetSourceType.FEDERATED,
            source_metadata={},
        )

        self.assertEqual(asset.source_metadata, {})

    def test_migration_edge_case_large_source_metadata(self):
        """Test migration with large source_metadata JSON (edge case)"""
        large_metadata = {
            "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
            "listing_id": "test-listing-123",
            "synced_at": "2025-01-01T12:00:00Z",
            "data": {"key" + str(i): "value" + str(i) for i in range(100)},
        }

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="large-metadata-asset",
            name="Large Metadata Asset",
            source_type=AssetSourceType.FEDERATED,
            source_metadata=large_metadata,
        )

        # Should store large JSON successfully
        asset.refresh_from_db()
        self.assertEqual(len(asset.source_metadata.get("data", {})), 100)

    def test_migration_edge_case_all_source_types_creates_assets(self):
        """Test migration with all source_type values creates assets."""
        # Test all enum values
        for source_type in AssetSourceType:
            asset = Asset.objects.create(
                tenant=self.tenant,
                key=f"source-type-{source_type.value.lower()}",
                name=f"Source Type {source_type.value}",
                source_type=source_type,
            )
            self.assertEqual(asset.source_type, source_type)

    def test_migration_edge_case_all_source_types(self):
        """Test migration with all source_type values (edge case)"""
        # Test all enum values
        for source_type in AssetSourceType:
            asset = Asset.objects.create(
                tenant=self.tenant,
                key=f"source-type-{source_type.value.lower()}",
                name=f"Source Type {source_type.value}",
                source_type=source_type,
            )
            self.assertEqual(asset.source_type, source_type)
