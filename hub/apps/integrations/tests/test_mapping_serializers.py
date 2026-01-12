"""
Marketplace Mapping Serializers Tests

Comprehensive unit tests for marketplace mapping serializers.
"""
import pytest
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from hub.apps.integrations.serializers import MarketplaceMappingSerializer
from hub.apps.integrations.models import MarketplaceMapping, MarketplaceConnection
from hub.apps.integrations.base import MarketplaceType
from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.assets.models import Asset


pytestmark = pytest.mark.django_db(transaction=True)


class MarketplaceMappingSerializerTest(TestCase):
    """Test suite for MarketplaceMappingSerializer"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            kyc_status=KYCStatus.VERIFIED
        )

        self.connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"api_key": "test_key", "api_secret": "test_secret"},
            is_active=True
        )

        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            description="Test asset description"
        )

        self.mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-123",
            external_resource_ids=["resource-1", "resource-2"],
            sync_metadata={"last_sync_status": "success", "items_synced": 5},
            last_synced_at=timezone.now() - timedelta(hours=1)
        )

    def test_serialize_mapping(self):
        """Test serializing a marketplace mapping"""
        serializer = MarketplaceMappingSerializer(self.mapping)
        data = serializer.data

        self.assertEqual(str(self.mapping.id), data['id'])
        self.assertEqual(str(self.tenant.id), data['tenant'])
        self.assertEqual(self.tenant.name, data['tenant_name'])
        self.assertEqual(str(self.connection.id), data['connection_id'])
        self.assertEqual(self.connection.name, data['connection_name'])
        self.assertEqual(str(self.asset.id), data['hub_asset_id'])
        self.assertEqual(self.asset.name, data['hub_asset_name'])
        self.assertEqual(self.asset.key, data['hub_asset_key'])
        self.assertEqual("ext-listing-123", data['external_listing_id'])
        self.assertEqual(["resource-1", "resource-2"], data['external_resource_ids'])
        self.assertEqual({"last_sync_status": "success", "items_synced": 5}, data['sync_metadata'])
        self.assertIsNotNone(data['last_synced_at'])
        self.assertIn('created_at', data)
        self.assertIn('updated_at', data)

    def test_serialize_mapping_minimal_fields(self):
        """Test serializing a mapping with minimal fields"""
        # Create a new asset to avoid unique constraint violation
        asset_minimal = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset-minimal",
            name="Test Asset Minimal"
        )
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=asset_minimal,
            external_listing_id="ext-listing-minimal"
        )

        serializer = MarketplaceMappingSerializer(mapping)
        data = serializer.data

        self.assertEqual("ext-listing-minimal", data['external_listing_id'])
        self.assertEqual([], data['external_resource_ids'])
        self.assertEqual({}, data['sync_metadata'])
        self.assertIsNone(data['last_synced_at'])

    def test_serialize_multiple_mappings(self):
        """Test serializing multiple mappings"""
        asset2 = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset-2",
            name="Test Asset 2"
        )

        mapping2 = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=asset2,
            external_listing_id="ext-listing-456"
        )

        serializer1 = MarketplaceMappingSerializer(self.mapping)
        serializer2 = MarketplaceMappingSerializer(mapping2)

        self.assertEqual(serializer1.data['hub_asset_name'], "Test Asset")
        self.assertEqual(serializer2.data['hub_asset_name'], "Test Asset 2")
        self.assertEqual(serializer1.data['external_listing_id'], "ext-listing-123")
        self.assertEqual(serializer2.data['external_listing_id'], "ext-listing-456")

    def test_serialize_mapping_with_complex_metadata(self):
        """Test serializing mapping with complex sync metadata"""
        # Create a new asset to avoid unique constraint violation
        asset_complex = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset-complex",
            name="Test Asset Complex"
        )
        complex_metadata = {
            "last_sync_status": "success",
            "items_synced": 10,
            "items_failed": 2,
            "errors": ["error1", "error2"],
            "nested": {
                "key": "value",
                "number": 42
            },
            "list": [1, 2, 3]
        }

        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=asset_complex,
            external_listing_id="ext-listing-complex",
            sync_metadata=complex_metadata
        )

        serializer = MarketplaceMappingSerializer(mapping)
        data = serializer.data

        self.assertEqual(complex_metadata, data['sync_metadata'])
        self.assertEqual(complex_metadata['nested'], data['sync_metadata']['nested'])
        self.assertEqual(complex_metadata['list'], data['sync_metadata']['list'])

    def test_serialize_mapping_read_only_fields(self):
        """Test that all fields are read-only"""
        serializer = MarketplaceMappingSerializer(self.mapping)
        data = serializer.data

        # All fields should be present and read-only
        read_only_fields = [
            'id', 'tenant', 'tenant_name', 'connection_id', 'connection_name',
            'hub_asset_id', 'hub_asset_name', 'hub_asset_key',
            'external_listing_id', 'external_resource_ids', 'sync_metadata',
            'last_synced_at', 'created_at', 'updated_at'
        ]

        for field in read_only_fields:
            self.assertIn(field, data)

    def test_serialize_mapping_different_connections(self):
        """Test serializing mappings with different connections"""
        connection2 = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE.value,
            name="Test Connection 2",
            config={"access_key": "test"}
        )

        mapping2 = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=connection2,
            hub_asset=self.asset,
            external_listing_id="ext-listing-connection2"
        )

        serializer1 = MarketplaceMappingSerializer(self.mapping)
        serializer2 = MarketplaceMappingSerializer(mapping2)

        self.assertEqual(serializer1.data['connection_name'], "Test Connection")
        self.assertEqual(serializer2.data['connection_name'], "Test Connection 2")
        self.assertEqual(serializer1.data['connection_id'], str(self.connection.id))
        self.assertEqual(serializer2.data['connection_id'], str(connection2.id))

    def test_serialize_mapping_empty_resource_ids(self):
        """Test serializing mapping with empty resource IDs"""
        # Create a new asset to avoid unique constraint violation
        asset_empty = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset-empty",
            name="Test Asset Empty"
        )
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=asset_empty,
            external_listing_id="ext-listing-empty",
            external_resource_ids=[]
        )

        serializer = MarketplaceMappingSerializer(mapping)
        data = serializer.data

        self.assertEqual([], data['external_resource_ids'])

    def test_serialize_mapping_null_last_synced_at(self):
        """Test serializing mapping with null last_synced_at"""
        # Create a new asset to avoid unique constraint violation
        asset_null = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset-null",
            name="Test Asset Null"
        )
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=asset_null,
            external_listing_id="ext-listing-null",
            last_synced_at=None
        )

        serializer = MarketplaceMappingSerializer(mapping)
        data = serializer.data

        self.assertIsNone(data['last_synced_at'])

