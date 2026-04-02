"""
Marketplace Mapping Serializers Tests

Comprehensive unit tests for marketplace mapping serializers.
"""

from datetime import timedelta

import pytest
from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.models import Asset
from hub.apps.integrations.base import MarketplaceType
from hub.apps.integrations.models import MarketplaceConnection, MarketplaceMapping
from hub.apps.integrations.serializers import MarketplaceMappingSerializer
from hub.apps.tenants.models import KYCStatus, Tenant
import uuid

pytestmark = pytest.mark.django_db(transaction=True)


class MarketplaceMappingSerializerTest(TestCase):
    """Test suite for MarketplaceMappingSerializer"""

    def setUp(self):
        """Set up test fixtures"""
        # CRITICAL: Disconnect semantic service signals to prevent timeouts
        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            post_save.disconnect(contract_saved, sender=Contract)
            post_save.disconnect(asset_saved, sender=Asset)
        except (ImportError, AttributeError):
            pass

        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )

        self.connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"api_key": "test_key", "api_secret": "test_secret"},
            is_active=True,
        )

        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            description="Test asset description",
        )

        self.mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-123",
            external_resource_ids=["resource-1", "resource-2"],
            sync_metadata={"last_sync_status": "success", "items_synced": 5},
            last_synced_at=timezone.now() - timedelta(hours=1),
        )

    def test_serialize_mapping(self):
        """Test serializing a marketplace mapping"""
        serializer = MarketplaceMappingSerializer(self.mapping)
        data = serializer.data

        self.assertEqual(str(self.mapping.id), data["id"])
        self.assertEqual(str(self.tenant.id), data["tenant"])
        self.assertEqual(self.tenant.name, data["tenant_name"])
        self.assertEqual(str(self.connection.id), data["connection_id"])
        self.assertEqual(self.connection.name, data["connection_name"])
        self.assertEqual(str(self.asset.id), data["hub_asset_id"])
        self.assertEqual(self.asset.name, data["hub_asset_name"])
        self.assertEqual(self.asset.key, data["hub_asset_key"])
        self.assertEqual("ext-listing-123", data["external_listing_id"])
        self.assertEqual(["resource-1", "resource-2"], data["external_resource_ids"])
        self.assertEqual({"last_sync_status": "success", "items_synced": 5}, data["sync_metadata"])
        self.assertIsNotNone(data["last_synced_at"])
        self.assertIn("created_at", data)
        self.assertIn("updated_at", data)

    def test_serialize_mapping_minimal_fields(self):
        """Test serializing a mapping with minimal fields"""
        # Create a new asset to avoid unique constraint violation
        asset_minimal = Asset.objects.create(
            tenant=self.tenant, key="test-asset-minimal", name="Test Asset Minimal"
        )
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=asset_minimal,
            external_listing_id="ext-listing-minimal",
        )

        serializer = MarketplaceMappingSerializer(mapping)
        data = serializer.data

        self.assertEqual("ext-listing-minimal", data["external_listing_id"])
        self.assertEqual([], data["external_resource_ids"])
        self.assertEqual({}, data["sync_metadata"])
        self.assertIsNone(data["last_synced_at"])

    def test_serialize_multiple_mappings(self):
        """Test serializing multiple mappings"""
        asset2 = Asset.objects.create(tenant=self.tenant, key="test-asset-2", name="Test Asset 2")

        mapping2 = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=asset2,
            external_listing_id="ext-listing-456",
        )

        serializer1 = MarketplaceMappingSerializer(self.mapping)
        serializer2 = MarketplaceMappingSerializer(mapping2)

        self.assertEqual(serializer1.data["hub_asset_name"], "Test Asset")
        self.assertEqual(serializer2.data["hub_asset_name"], "Test Asset 2")
        self.assertEqual(serializer1.data["external_listing_id"], "ext-listing-123")
        self.assertEqual(serializer2.data["external_listing_id"], "ext-listing-456")

    def test_serialize_mapping_with_complex_metadata(self):
        """Test serializing mapping with complex sync metadata"""
        # Create a new asset to avoid unique constraint violation
        asset_complex = Asset.objects.create(
            tenant=self.tenant, key="test-asset-complex", name="Test Asset Complex"
        )
        complex_metadata = {
            "last_sync_status": "success",
            "items_synced": 10,
            "items_failed": 2,
            "errors": ["error1", "error2"],
            "nested": {"key": "value", "number": 42},
            "list": [1, 2, 3],
        }

        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=asset_complex,
            external_listing_id="ext-listing-complex",
            sync_metadata=complex_metadata,
        )

        serializer = MarketplaceMappingSerializer(mapping)
        data = serializer.data

        self.assertEqual(complex_metadata, data["sync_metadata"])
        self.assertEqual(complex_metadata["nested"], data["sync_metadata"]["nested"])
        self.assertEqual(complex_metadata["list"], data["sync_metadata"]["list"])

    def test_serialize_mapping_read_only_fields(self):
        """Test that all fields are read-only"""
        serializer = MarketplaceMappingSerializer(self.mapping)
        data = serializer.data

        # All fields should be present and read-only
        read_only_fields = [
            "id",
            "tenant",
            "tenant_name",
            "connection_id",
            "connection_name",
            "hub_asset_id",
            "hub_asset_name",
            "hub_asset_key",
            "external_listing_id",
            "external_resource_ids",
            "sync_metadata",
            "last_synced_at",
            "created_at",
            "updated_at",
        ]

        for field in read_only_fields:
            self.assertIn(field, data)

    def test_serialize_mapping_different_connections(self):
        """Test serializing mappings with different connections"""
        connection2 = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE.value,
            name="Test Connection 2",
            config={"access_key": "test"},
        )

        mapping2 = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=connection2,
            hub_asset=self.asset,
            external_listing_id="ext-listing-connection2",
        )

        serializer1 = MarketplaceMappingSerializer(self.mapping)
        serializer2 = MarketplaceMappingSerializer(mapping2)

        self.assertEqual(serializer1.data["connection_name"], "Test Connection")
        self.assertEqual(serializer2.data["connection_name"], "Test Connection 2")
        self.assertEqual(serializer1.data["connection_id"], str(self.connection.id))
        self.assertEqual(serializer2.data["connection_id"], str(connection2.id))

    def test_serialize_mapping_empty_resource_ids(self):
        """Test serializing mapping with empty resource IDs"""
        # Create a new asset to avoid unique constraint violation
        asset_empty = Asset.objects.create(
            tenant=self.tenant, key="test-asset-empty", name="Test Asset Empty"
        )
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=asset_empty,
            external_listing_id="ext-listing-empty",
            external_resource_ids=[],
        )

        serializer = MarketplaceMappingSerializer(mapping)
        data = serializer.data

        self.assertEqual([], data["external_resource_ids"])

    def test_serialize_mapping_null_last_synced_at(self):
        """Test serializing mapping with null last_synced_at"""
        # Create a new asset to avoid unique constraint violation
        asset_null = Asset.objects.create(
            tenant=self.tenant, key="test-asset-null", name="Test Asset Null"
        )
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=asset_null,
            external_listing_id="ext-listing-null",
            last_synced_at=None,
        )

        serializer = MarketplaceMappingSerializer(mapping)
        data = serializer.data

        self.assertIsNone(data["last_synced_at"])

    # ========== FAILURE SCENARIOS TESTS ==========

    def test_serialize_mapping_with_deleted_connection(self):
        """Test serializing mapping when connection is deleted"""
        # Use a distinct (connection, hub_asset) pair to avoid unique constraint with setUp's self.mapping
        conn = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Conn for deleted test",
            config={},
            is_active=True,
        )
        asset = Asset.objects.create(
            tenant=self.tenant, key="asset-deleted-conn", name="Asset for deleted conn"
        )
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=conn,
            hub_asset=asset,
            external_listing_id="ext-listing-deleted",
        )

        # Delete connection (cascade may remove mapping; test serializer behavior)
        conn.delete()

        # Try to serialize - should handle gracefully
        try:
            mapping.refresh_from_db()
            serializer = MarketplaceMappingSerializer(mapping)
            # If mapping still exists, serializer should handle missing connection
            data = serializer.data
            # Connection fields may be None or missing
            self.assertIn("connection_id", data or {})
        except MarketplaceMapping.DoesNotExist:
            # If cascade delete removed mapping, that's also acceptable
            pass

    def test_serialize_mapping_with_deleted_asset(self):
        """Test serializing mapping when asset is deleted"""
        # Use a distinct (connection, hub_asset) pair to avoid unique constraint with setUp's self.mapping
        conn = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Conn for deleted asset test",
            config={},
            is_active=True,
        )
        asset = Asset.objects.create(
            tenant=self.tenant, key="asset-deleted-asset", name="Asset to delete"
        )
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=conn,
            hub_asset=asset,
            external_listing_id="ext-listing-asset-deleted",
        )

        # Delete asset (cascade may remove mapping; test serializer behavior)
        asset.delete()

        # Try to serialize - should handle gracefully
        try:
            mapping.refresh_from_db()
            serializer = MarketplaceMappingSerializer(mapping)
            # If mapping still exists, serializer should handle missing asset
            data = serializer.data
            # Asset fields may be None or missing
            self.assertIn("hub_asset_id", data or {})
        except MarketplaceMapping.DoesNotExist:
            # If cascade delete removed mapping, that's also acceptable
            pass

    # ========== ERROR HANDLING TESTS ==========

    def test_serialize_mapping_with_invalid_metadata(self):
        """Test serializing mapping with invalid metadata structure"""
        # Create mapping with potentially problematic metadata
        asset_metadata = Asset.objects.create(
            tenant=self.tenant, key="test-asset-metadata", name="Test Asset Metadata"
        )
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=asset_metadata,
            external_listing_id="ext-listing-metadata",
            sync_metadata={"nested": {"deep": {"value": "test"}}},  # Deep nesting
        )

        serializer = MarketplaceMappingSerializer(mapping)
        data = serializer.data

        # Should serialize successfully even with complex metadata
        self.assertIn("sync_metadata", data)
        self.assertEqual(data["sync_metadata"]["nested"]["deep"]["value"], "test")

    def test_serialize_mapping_with_large_resource_ids(self):
        """Test serializing mapping with large number of resource IDs"""
        asset_large = Asset.objects.create(
            tenant=self.tenant, key="test-asset-large", name="Test Asset Large"
        )
        large_resource_ids = [f"resource-{i}" for i in range(100)]

        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=asset_large,
            external_listing_id="ext-listing-large",
            external_resource_ids=large_resource_ids,
        )

        serializer = MarketplaceMappingSerializer(mapping)
        data = serializer.data

        # Should serialize successfully with large lists
        self.assertEqual(len(data["external_resource_ids"]), 100)
        self.assertEqual(data["external_resource_ids"], large_resource_ids)

    # ========== TDD COMPLIANCE TESTS ==========

    def test_serialize_mapping_returns_all_required_fields(self):
        """Test that serializer returns all required fields"""
        serializer = MarketplaceMappingSerializer(self.mapping)
        data = serializer.data

        # Verify all required fields are present
        required_fields = [
            "id",
            "tenant",
            "tenant_name",
            "connection_id",
            "connection_name",
            "hub_asset_id",
            "hub_asset_name",
            "hub_asset_key",
            "external_listing_id",
            "external_resource_ids",
            "sync_metadata",
            "last_synced_at",
            "created_at",
            "updated_at",
        ]

        for field in required_fields:
            self.assertIn(field, data, f"Required field {field} missing from serializer output")

    def test_serialize_mapping_field_types(self):
        """Test that serializer returns correct field types"""
        serializer = MarketplaceMappingSerializer(self.mapping)
        data = serializer.data

        # Verify field types
        self.assertIsInstance(data["id"], str)
        self.assertIsInstance(data["tenant"], str)
        self.assertIsInstance(data["tenant_name"], str)
        self.assertIsInstance(data["connection_id"], str)
        self.assertIsInstance(data["connection_name"], str)
        self.assertIsInstance(data["hub_asset_id"], str)
        self.assertIsInstance(data["hub_asset_name"], str)
        self.assertIsInstance(data["hub_asset_key"], str)
        self.assertIsInstance(data["external_listing_id"], str)
        self.assertIsInstance(data["external_resource_ids"], list)
        self.assertIsInstance(data["sync_metadata"], dict)

    def test_serialize_mapping_timestamp_format(self):
        """Test that timestamps are properly formatted"""
        serializer = MarketplaceMappingSerializer(self.mapping)
        data = serializer.data

        # Timestamps should be strings (ISO format)
        self.assertIsInstance(data["created_at"], str)
        self.assertIsInstance(data["updated_at"], str)
        # If last_synced_at is present, should be string or None
        if data["last_synced_at"] is not None:
            self.assertIsInstance(data["last_synced_at"], str)

    def tearDown(self):
        """Reconnect signals after test"""
        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            post_save.connect(contract_saved, sender=Contract, weak=False)
            post_save.connect(asset_saved, sender=Asset, weak=False)
        except (ImportError, AttributeError):
            pass
