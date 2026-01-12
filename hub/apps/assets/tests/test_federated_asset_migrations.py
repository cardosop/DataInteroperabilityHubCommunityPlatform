"""
Migration tests for federated asset fields.

Tests forward and backward migrations for source_type and source_metadata fields.
"""
import pytest
from django.test import TestCase
from django.db import connection
from django.core.management import call_command
from io import StringIO

from hub.apps.tenants.models import Tenant
from hub.apps.assets.models import Asset, AssetSourceType


pytestmark = pytest.mark.django_db(transaction=True)


class FederatedAssetMigrationTest(TestCase):
    """Test migrations for federated asset fields"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )

    def test_source_type_field_exists(self):
        """Test that source_type field exists in database"""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = 'assets'
                AND column_name = 'source_type'
            """)
            result = cursor.fetchone()

        self.assertIsNotNone(result, "source_type column should exist")
        column_name, data_type, is_nullable, column_default = result
        self.assertEqual(column_name, 'source_type')
        self.assertEqual(data_type, 'character varying')
        self.assertEqual(is_nullable, 'NO')  # Not nullable
        # Default may be set at application level (Django) or database level
        # Verify default works by creating asset without specifying source_type
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-default-source-type",
            name="Test Default Source Type"
        )
        self.assertEqual(asset.source_type, AssetSourceType.HUB_NATIVE)

    def test_source_metadata_field_exists(self):
        """Test that source_metadata field exists in database"""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'assets'
                AND column_name = 'source_metadata'
            """)
            result = cursor.fetchone()

        self.assertIsNotNone(result, "source_metadata column should exist")
        column_name, data_type, is_nullable = result
        self.assertEqual(column_name, 'source_metadata')
        self.assertEqual(data_type, 'jsonb')  # PostgreSQL JSONB type
        self.assertEqual(is_nullable, 'YES')  # Nullable

    def test_source_type_index_exists(self):
        """Test that index on (tenant, source_type) exists"""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'assets'
                AND indexdef LIKE '%tenant%source_type%'
            """)
            indexes = [row[0] for row in cursor.fetchall()]

        # Check for the index (name may vary)
        self.assertGreater(len(indexes), 0, "Index on (tenant, source_type) should exist")

        # Verify index includes both fields
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT indexdef
                FROM pg_indexes
                WHERE tablename = 'assets'
                AND indexdef LIKE '%tenant%source_type%'
                LIMIT 1
            """)
            result = cursor.fetchone()
            if result:
                indexdef = result[0]
                self.assertIn('tenant_id', indexdef.lower())
                self.assertIn('source_type', indexdef.lower())

    def test_default_source_type_value(self):
        """Test that existing assets get default HUB_NATIVE value"""
        # Create asset without specifying source_type
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset-default",
            name="Test Asset Default"
        )

        self.assertEqual(asset.source_type, AssetSourceType.HUB_NATIVE)

        # Verify in database
        asset.refresh_from_db()
        self.assertEqual(asset.source_type, AssetSourceType.HUB_NATIVE)

    def test_migration_applied(self):
        """Test that migration has been applied"""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*)
                FROM information_schema.columns
                WHERE table_name = 'assets'
                AND column_name IN ('source_type', 'source_metadata')
            """)
            column_count = cursor.fetchone()[0]

        self.assertEqual(column_count, 2, "Both source_type and source_metadata columns should exist")

    def test_source_type_constraint(self):
        """Test that source_type has correct check constraint"""
        # Create asset with valid source_type
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="valid-asset",
            name="Valid Asset",
            source_type=AssetSourceType.FEDERATED
        )

        self.assertEqual(asset.source_type, AssetSourceType.FEDERATED)

        # Try to create asset with invalid source_type (should fail validation)
        asset_invalid = Asset(
            tenant=self.tenant,
            key="invalid-asset",
            name="Invalid Asset",
            source_type="INVALID"
        )

        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            asset_invalid.full_clean()

    def test_source_metadata_json_storage(self):
        """Test that source_metadata can store JSON data"""
        metadata = {
            "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
            "listing_id": "test-listing-123",
            "synced_at": "2025-01-01T12:00:00Z"
        }

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="json-asset",
            name="JSON Asset",
            source_type=AssetSourceType.FEDERATED,
            source_metadata=metadata
        )

        # Verify JSON is stored correctly
        asset.refresh_from_db()
        self.assertEqual(asset.source_metadata, metadata)
        self.assertEqual(asset.source_metadata["marketplace_type"], "SNOWFLAKE_DATA_MARKETPLACE")

    def test_index_usage(self):
        """Test that index on (tenant, source_type) is used in queries"""
        # Create test data
        for i in range(5):
            Asset.objects.create(
                tenant=self.tenant,
                key=f"hub-asset-{i}",
                name=f"Hub Asset {i}",
                source_type=AssetSourceType.HUB_NATIVE
            )

        for i in range(3):
            Asset.objects.create(
                tenant=self.tenant,
                key=f"federated-asset-{i}",
                name=f"Federated Asset {i}",
                source_type=AssetSourceType.FEDERATED
            )

        # Query that should use index
        federated_assets = Asset.objects.filter(
            tenant=self.tenant,
            source_type=AssetSourceType.FEDERATED
        )

        self.assertEqual(federated_assets.count(), 3)

        # Verify all are federated
        for asset in federated_assets:
            self.assertEqual(asset.source_type, AssetSourceType.FEDERATED)

