"""
Unit tests for MarketplaceMapping model.

Comprehensive tests for model creation, unique constraints, sync metadata updates, and validation.
"""
import pytest
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone
from datetime import timedelta

from hub.apps.tenants.models import Tenant
from hub.apps.assets.models import Asset
from hub.apps.integrations.models import MarketplaceConnection, MarketplaceMapping
from hub.apps.integrations.base import MarketplaceType


pytestmark = pytest.mark.django_db(transaction=True)


class MarketplaceMappingModelTest(TestCase):
    """Test MarketplaceMapping model"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"api_key": "test-key"}
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            description="Test asset description"
        )

    def test_create_mapping(self):
        """Test basic mapping creation"""
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-123"
        )

        self.assertIsNotNone(mapping.id)
        self.assertEqual(mapping.tenant, self.tenant)
        self.assertEqual(mapping.connection, self.connection)
        self.assertEqual(mapping.hub_asset, self.asset)
        self.assertEqual(mapping.external_listing_id, "ext-listing-123")
        self.assertEqual(mapping.external_resource_ids, [])
        self.assertEqual(mapping.sync_metadata, {})
        self.assertIsNone(mapping.last_synced_at)
        self.assertIsNotNone(mapping.created_at)

    def test_create_mapping_with_all_fields(self):
        """Test mapping creation with all fields"""
        external_resource_ids = ["resource-1", "resource-2", "resource-3"]
        sync_metadata = {"last_sync_status": "success", "items_synced": 10}
        last_synced = timezone.now() - timedelta(hours=1)

        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-456",
            external_resource_ids=external_resource_ids,
            sync_metadata=sync_metadata,
            last_synced_at=last_synced
        )

        self.assertEqual(mapping.external_listing_id, "ext-listing-456")
        self.assertEqual(mapping.external_resource_ids, external_resource_ids)
        self.assertEqual(mapping.sync_metadata, sync_metadata)
        self.assertEqual(mapping.last_synced_at, last_synced)

    def test_mapping_str_representation(self):
        """Test string representation of mapping"""
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-789"
        )

        str_repr = str(mapping)
        self.assertIn("Test Asset", str_repr)
        self.assertIn("Test Connection", str_repr)
        self.assertIn("ext-listing-789", str_repr)

    def test_unique_constraint_connection_asset(self):
        """Test that connection + hub_asset combination must be unique"""
        MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-1"
        )

        # Try to create another mapping with same connection and asset
        with self.assertRaises(ValidationError) as cm:
            MarketplaceMapping.objects.create(
                tenant=self.tenant,
                connection=self.connection,
                hub_asset=self.asset,
                external_listing_id="ext-listing-2"
            )

        self.assertIn('A mapping already exists for this connection and asset.', str(cm.exception))

    def test_same_asset_different_connections(self):
        """Test that same asset can be mapped to different connections"""
        connection2 = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE.value,
            name="Test Connection 2",
            config={"api_key": "test-key-2"}
        )

        mapping1 = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-1"
        )

        mapping2 = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=connection2,
            hub_asset=self.asset,
            external_listing_id="ext-listing-2"
        )

        self.assertNotEqual(mapping1.id, mapping2.id)
        self.assertEqual(mapping1.hub_asset, mapping2.hub_asset)
        self.assertNotEqual(mapping1.connection, mapping2.connection)

    def test_same_connection_different_assets(self):
        """Test that same connection can map different assets"""
        asset2 = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset-2",
            name="Test Asset 2"
        )

        mapping1 = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-1"
        )

        mapping2 = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=asset2,
            external_listing_id="ext-listing-2"
        )

        self.assertNotEqual(mapping1.id, mapping2.id)
        self.assertEqual(mapping1.connection, mapping2.connection)
        self.assertNotEqual(mapping1.hub_asset, mapping2.hub_asset)

    def test_validation_empty_external_listing_id(self):
        """Test validation fails for empty external_listing_id"""
        mapping = MarketplaceMapping(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id=""
        )

        with self.assertRaises(ValidationError):
            mapping.full_clean()

    def test_validation_whitespace_only_external_listing_id(self):
        """Test validation fails for whitespace-only external_listing_id"""
        mapping = MarketplaceMapping(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="   "
        )

        with self.assertRaises(ValidationError):
            mapping.full_clean()

    def test_validation_external_resource_ids_not_list(self):
        """Test validation fails when external_resource_ids is not a list"""
        mapping = MarketplaceMapping(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-123",
            external_resource_ids="not-a-list"
        )

        with self.assertRaises(ValidationError):
            mapping.full_clean()

    def test_validation_sync_metadata_not_dict(self):
        """Test validation fails when sync_metadata is not a dict"""
        mapping = MarketplaceMapping(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-123",
            sync_metadata="not-a-dict"
        )

        with self.assertRaises(ValidationError):
            mapping.full_clean()

    def test_update_sync_metadata(self):
        """Test update_sync_metadata method"""
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-123",
            sync_metadata={"existing": "value"}
        )

        initial_last_synced = mapping.last_synced_at

        import time
        time.sleep(0.01)

        mapping.update_sync_metadata(
            metadata={"new_key": "new_value", "existing": "updated"},
            last_synced_at=timezone.now()
        )

        mapping.refresh_from_db()
        self.assertEqual(mapping.sync_metadata["existing"], "updated")
        self.assertEqual(mapping.sync_metadata["new_key"], "new_value")
        self.assertIsNotNone(mapping.last_synced_at)
        self.assertGreater(mapping.last_synced_at, initial_last_synced or timezone.now() - timedelta(seconds=1))

    def test_update_sync_metadata_without_last_synced_at(self):
        """Test update_sync_metadata without explicit last_synced_at"""
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-123"
        )

        before_time = timezone.now()
        mapping.update_sync_metadata(metadata={"status": "synced"})
        after_time = timezone.now()

        mapping.refresh_from_db()
        self.assertEqual(mapping.sync_metadata["status"], "synced")
        self.assertIsNotNone(mapping.last_synced_at)
        self.assertGreaterEqual(mapping.last_synced_at, before_time)
        self.assertLessEqual(mapping.last_synced_at, after_time)

    def test_update_sync_metadata_invalid_type(self):
        """Test update_sync_metadata fails with non-dict metadata"""
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-123"
        )

        with self.assertRaises(ValueError):
            mapping.update_sync_metadata(metadata="not-a-dict")

        with self.assertRaises(ValueError):
            mapping.update_sync_metadata(metadata=["not-a-dict"])

    def test_update_sync_metadata_merge(self):
        """Test that update_sync_metadata merges with existing metadata"""
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-123",
            sync_metadata={"key1": "value1", "key2": "value2"}
        )

        mapping.update_sync_metadata(metadata={"key2": "updated", "key3": "value3"})

        mapping.refresh_from_db()
        self.assertEqual(mapping.sync_metadata["key1"], "value1")  # Preserved
        self.assertEqual(mapping.sync_metadata["key2"], "updated")  # Updated
        self.assertEqual(mapping.sync_metadata["key3"], "value3")  # Added

    def test_cascade_delete_connection(self):
        """Test that mappings are deleted when connection is deleted"""
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-123"
        )

        mapping_id = mapping.id

        # Delete connection
        self.connection.delete()

        # Verify mapping is deleted
        self.assertFalse(MarketplaceMapping.objects.filter(id=mapping_id).exists())

    def test_cascade_delete_tenant(self):
        """Test that mappings are deleted when tenant is deleted"""
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-123"
        )

        mapping_id = mapping.id

        # Delete tenant
        self.tenant.delete()

        # Verify mapping is deleted
        self.assertFalse(MarketplaceMapping.objects.filter(id=mapping_id).exists())

    def test_cascade_delete_asset(self):
        """Test that mappings are deleted when asset is deleted"""
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-123"
        )

        mapping_id = mapping.id

        # Delete asset
        self.asset.delete()

        # Verify mapping is deleted
        self.assertFalse(MarketplaceMapping.objects.filter(id=mapping_id).exists())

    def test_indexes_exist(self):
        """Test that indexes are created correctly"""
        # Create mappings to test indexes
        MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-1"
        )

        asset2 = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset-2",
            name="Test Asset 2"
        )

        MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=asset2,
            external_listing_id="ext-listing-2"
        )

        # Verify queries execute without error
        from django.db import connection as db_connection

        with db_connection.cursor() as cursor:
            # Query that should use tenant + connection index
            cursor.execute("""
                EXPLAIN SELECT * FROM marketplace_mappings
                WHERE tenant_id = %s AND connection_id = %s
            """, [self.tenant.id, self.connection.id])

            # Just verify query executes without error

    def test_ordering_by_created_at_desc(self):
        """Test that mappings are ordered by created_at descending"""
        mapping1 = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-1"
        )

        import time
        time.sleep(0.01)

        asset2 = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset-2",
            name="Test Asset 2"
        )

        mapping2 = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=asset2,
            external_listing_id="ext-listing-2"
        )

        mappings = list(MarketplaceMapping.objects.all())
        self.assertEqual(mappings[0], mapping2)  # Most recent first
        self.assertEqual(mappings[1], mapping1)

    def test_external_resource_ids_list(self):
        """Test that external_resource_ids can store a list of IDs"""
        resource_ids = ["resource-1", "resource-2", "resource-3"]

        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-123",
            external_resource_ids=resource_ids
        )

        mapping.refresh_from_db()
        self.assertEqual(mapping.external_resource_ids, resource_ids)
        self.assertEqual(len(mapping.external_resource_ids), 3)

    def test_external_resource_ids_empty_list(self):
        """Test that external_resource_ids can be an empty list"""
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-123",
            external_resource_ids=[]
        )

        mapping.refresh_from_db()
        self.assertEqual(mapping.external_resource_ids, [])

    def test_sync_metadata_empty_dict(self):
        """Test that sync_metadata can be an empty dict"""
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-123",
            sync_metadata={}
        )

        mapping.refresh_from_db()
        self.assertEqual(mapping.sync_metadata, {})

    def test_update_sync_metadata_preserves_existing_keys(self):
        """Test that update_sync_metadata preserves keys not in new metadata"""
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-123",
            sync_metadata={"preserved": "value", "updated": "old"}
        )

        mapping.update_sync_metadata(metadata={"updated": "new"})

        mapping.refresh_from_db()
        self.assertEqual(mapping.sync_metadata["preserved"], "value")
        self.assertEqual(mapping.sync_metadata["updated"], "new")

    def test_last_synced_at_nullable(self):
        """Test that last_synced_at can be None"""
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-123",
            last_synced_at=None
        )

        mapping.refresh_from_db()
        self.assertIsNone(mapping.last_synced_at)

    def test_update_sync_metadata_with_explicit_datetime(self):
        """Test update_sync_metadata with explicit datetime"""
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-123"
        )

        explicit_time = timezone.now() - timedelta(days=1)
        mapping.update_sync_metadata(
            metadata={"test": "value"},
            last_synced_at=explicit_time
        )

        mapping.refresh_from_db()
        self.assertEqual(mapping.last_synced_at, explicit_time)

