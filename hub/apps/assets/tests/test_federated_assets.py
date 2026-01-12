"""
Unit tests for federated asset functionality.

Tests Asset model with source_type and source_metadata fields for federated assets.
"""
import pytest
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta

from hub.apps.tenants.models import Tenant
from hub.apps.assets.models import Asset, AssetSourceType


pytestmark = pytest.mark.django_db(transaction=True)


class FederatedAssetModelTest(TestCase):
    """Test Asset model with federated asset fields"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )

    def test_create_hub_native_asset(self):
        """Test creating a Hub-native asset (default)"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset"
        )

        self.assertEqual(asset.source_type, AssetSourceType.HUB_NATIVE)
        self.assertIsNone(asset.source_metadata)
        self.assertEqual(asset.get_source_type_display(), "Hub Native")

    def test_create_federated_asset(self):
        """Test creating a federated asset"""
        source_metadata = {
            "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
            "marketplace_id": "marketplace-123",
            "listing_id": "listing-456",
            "listing_url": "https://marketplace.example.com/listings/456",
            "synced_at": timezone.now().isoformat(),
            "sync_job_id": "sync-job-789"
        }

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="federated-asset",
            name="Federated Asset",
            source_type=AssetSourceType.FEDERATED,
            source_metadata=source_metadata
        )

        self.assertEqual(asset.source_type, AssetSourceType.FEDERATED)
        self.assertEqual(asset.source_metadata, source_metadata)
        self.assertEqual(asset.get_source_type_display(), "Federated")
        self.assertEqual(asset.source_metadata["marketplace_type"], "SNOWFLAKE_DATA_MARKETPLACE")
        self.assertEqual(asset.source_metadata["listing_id"], "listing-456")

    def test_source_type_choices(self):
        """Test that all source type choices are available"""
        choices = AssetSourceType.choices
        choice_values = [choice[0] for choice in choices]

        self.assertIn(AssetSourceType.HUB_NATIVE, choice_values)
        self.assertIn(AssetSourceType.FEDERATED, choice_values)
        self.assertEqual(len(choice_values), 2)

    def test_source_metadata_optional(self):
        """Test that source_metadata is optional"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="asset-no-metadata",
            name="Asset Without Metadata",
            source_type=AssetSourceType.FEDERATED,
            source_metadata=None
        )

        self.assertIsNone(asset.source_metadata)

    def test_source_metadata_empty_dict(self):
        """Test that source_metadata can be an empty dict"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="asset-empty-metadata",
            name="Asset With Empty Metadata",
            source_type=AssetSourceType.FEDERATED,
            source_metadata={}
        )

        self.assertEqual(asset.source_metadata, {})

    def test_source_metadata_structure(self):
        """Test source_metadata with all expected fields"""
        source_metadata = {
            "marketplace_type": "AWS_DATA_EXCHANGE",
            "marketplace_id": "aws-marketplace-123",
            "listing_id": "aws-listing-456",
            "listing_url": "https://aws.amazon.com/marketplace/listing/456",
            "synced_at": "2025-01-01T12:00:00Z",
            "sync_job_id": "sync-job-abc123"
        }

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="federated-asset-full",
            name="Federated Asset Full Metadata",
            source_type=AssetSourceType.FEDERATED,
            source_metadata=source_metadata
        )

        asset.refresh_from_db()
        self.assertEqual(asset.source_metadata["marketplace_type"], "AWS_DATA_EXCHANGE")
        self.assertEqual(asset.source_metadata["marketplace_id"], "aws-marketplace-123")
        self.assertEqual(asset.source_metadata["listing_id"], "aws-listing-456")
        self.assertEqual(asset.source_metadata["listing_url"], "https://aws.amazon.com/marketplace/listing/456")
        self.assertEqual(asset.source_metadata["synced_at"], "2025-01-01T12:00:00Z")
        self.assertEqual(asset.source_metadata["sync_job_id"], "sync-job-abc123")

    def test_filter_by_source_type(self):
        """Test filtering assets by source_type"""
        # Create Hub-native assets
        Asset.objects.create(
            tenant=self.tenant,
            key="hub-asset-1",
            name="Hub Asset 1",
            source_type=AssetSourceType.HUB_NATIVE
        )
        Asset.objects.create(
            tenant=self.tenant,
            key="hub-asset-2",
            name="Hub Asset 2",
            source_type=AssetSourceType.HUB_NATIVE
        )

        # Create federated assets
        Asset.objects.create(
            tenant=self.tenant,
            key="federated-asset-1",
            name="Federated Asset 1",
            source_type=AssetSourceType.FEDERATED,
            source_metadata={"marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE"}
        )
        Asset.objects.create(
            tenant=self.tenant,
            key="federated-asset-2",
            name="Federated Asset 2",
            source_type=AssetSourceType.FEDERATED,
            source_metadata={"marketplace_type": "AWS_DATA_EXCHANGE"}
        )

        # Filter Hub-native assets
        hub_native_assets = Asset.objects.filter(source_type=AssetSourceType.HUB_NATIVE)
        self.assertEqual(hub_native_assets.count(), 2)

        # Filter federated assets
        federated_assets = Asset.objects.filter(source_type=AssetSourceType.FEDERATED)
        self.assertEqual(federated_assets.count(), 2)

        # Filter by tenant and source_type (using index)
        tenant_federated = Asset.objects.filter(
            tenant=self.tenant,
            source_type=AssetSourceType.FEDERATED
        )
        self.assertEqual(tenant_federated.count(), 2)

    def test_update_source_metadata(self):
        """Test updating source_metadata"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="federated-asset",
            name="Federated Asset",
            source_type=AssetSourceType.FEDERATED,
            source_metadata={"marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE"}
        )

        # Update metadata
        asset.source_metadata = {
            "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
            "listing_id": "updated-listing-123",
            "synced_at": timezone.now().isoformat()
        }
        asset.save()

        asset.refresh_from_db()
        self.assertEqual(asset.source_metadata["listing_id"], "updated-listing-123")

    def test_default_source_type(self):
        """Test that default source_type is HUB_NATIVE"""
        asset = Asset(
            tenant=self.tenant,
            key="default-asset",
            name="Default Asset"
        )

        self.assertEqual(asset.source_type, AssetSourceType.HUB_NATIVE)

    def test_source_type_display(self):
        """Test source_type display values"""
        asset_hub = Asset.objects.create(
            tenant=self.tenant,
            key="hub-asset",
            name="Hub Asset",
            source_type=AssetSourceType.HUB_NATIVE
        )

        asset_federated = Asset.objects.create(
            tenant=self.tenant,
            key="federated-asset",
            name="Federated Asset",
            source_type=AssetSourceType.FEDERATED
        )

        self.assertEqual(asset_hub.get_source_type_display(), "Hub Native")
        self.assertEqual(asset_federated.get_source_type_display(), "Federated")

    def test_invalid_source_type(self):
        """Test that invalid source_type raises validation error"""
        asset = Asset(
            tenant=self.tenant,
            key="invalid-asset",
            name="Invalid Asset",
            source_type="INVALID_TYPE"
        )

        with self.assertRaises(ValidationError):
            asset.full_clean()

    def test_source_metadata_json_structure(self):
        """Test that source_metadata can store complex JSON structures"""
        complex_metadata = {
            "marketplace_type": "DATABRICKS_MARKETPLACE",
            "marketplace_id": "databricks-123",
            "listing_id": "db-listing-456",
            "listing_url": "https://databricks.com/marketplace/456",
            "synced_at": timezone.now().isoformat(),
            "sync_job_id": "sync-job-xyz",
            "additional_info": {
                "provider": "Data Provider Inc",
                "category": "Financial Data",
                "tags": ["finance", "market-data"]
            },
            "sync_history": [
                {"date": "2025-01-01", "status": "success"},
                {"date": "2025-01-02", "status": "success"}
            ]
        }

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="complex-federated-asset",
            name="Complex Federated Asset",
            source_type=AssetSourceType.FEDERATED,
            source_metadata=complex_metadata
        )

        asset.refresh_from_db()
        self.assertEqual(asset.source_metadata["additional_info"]["provider"], "Data Provider Inc")
        self.assertEqual(len(asset.source_metadata["sync_history"]), 2)
        self.assertEqual(asset.source_metadata["sync_history"][0]["status"], "success")


class FederatedAssetIntegrationTest(TestCase):
    """Integration tests for federated asset creation and management"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )

    def test_create_federated_asset_with_marketplace_info(self):
        """Test creating a federated asset with complete marketplace information"""
        from hub.apps.integrations.models import MarketplaceConnection, MarketplaceMapping
        from hub.apps.integrations.base import MarketplaceType

        # Create marketplace connection
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Snowflake Connection",
            config={"api_key": "test-key"}
        )

        # Create federated asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="snowflake-asset",
            name="Snowflake Federated Asset",
            source_type=AssetSourceType.FEDERATED,
            source_metadata={
                "marketplace_type": MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
                "marketplace_id": str(connection.id),
                "listing_id": "snowflake-listing-123",
                "listing_url": "https://app.snowflake.com/marketplace/listing/123",
                "synced_at": timezone.now().isoformat()
            }
        )

        # Create mapping
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=connection,
            hub_asset=asset,
            external_listing_id="snowflake-listing-123"
        )

        # Verify relationships
        self.assertEqual(asset.source_type, AssetSourceType.FEDERATED)
        self.assertEqual(mapping.hub_asset, asset)
        self.assertEqual(mapping.connection, connection)
        self.assertEqual(asset.source_metadata["marketplace_type"], MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value)

    def test_federated_asset_query_performance(self):
        """Test that queries using source_type index are efficient"""
        # Create multiple assets
        for i in range(10):
            Asset.objects.create(
                tenant=self.tenant,
                key=f"hub-asset-{i}",
                name=f"Hub Asset {i}",
                source_type=AssetSourceType.HUB_NATIVE
            )

        for i in range(5):
            Asset.objects.create(
                tenant=self.tenant,
                key=f"federated-asset-{i}",
                name=f"Federated Asset {i}",
                source_type=AssetSourceType.FEDERATED,
                source_metadata={"marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE"}
            )

        # Query using index (tenant, source_type)
        federated_assets = Asset.objects.filter(
            tenant=self.tenant,
            source_type=AssetSourceType.FEDERATED
        )

        self.assertEqual(federated_assets.count(), 5)

        # Verify all returned assets are federated
        for asset in federated_assets:
            self.assertEqual(asset.source_type, AssetSourceType.FEDERATED)

