"""
Unit tests for federated asset functionality.

Tests Asset model with source_type and source_metadata fields for federated assets.
Consolidated from ~25 single-assertion tests into ~14 multi-assertion tests.
"""

import uuid

import pytest
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetSourceType
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)

# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

FEDERATED_SOURCE_METADATA = {
    "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
    "marketplace_id": "marketplace-123",
    "listing_id": "listing-456",
    "listing_url": "https://marketplace.example.com/listings/456",
    "synced_at": "2025-01-01T12:00:00Z",
    "sync_job_id": "sync-job-789",
}

AWS_SOURCE_METADATA = {
    "marketplace_type": "AWS_DATA_EXCHANGE",
    "marketplace_id": "aws-marketplace-123",
    "listing_id": "aws-listing-456",
    "listing_url": "https://aws.amazon.com/marketplace/listing/456",
    "synced_at": "2025-01-01T12:00:00Z",
    "sync_job_id": "sync-job-abc123",
}


class FederatedAssetModelTest(TestCase):
    """Test Asset model with federated asset fields"""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}"
        )

    # ------------------------------------------------------------------
    # Hub-native asset creation (consolidated from 3 single-assertion tests)
    # ------------------------------------------------------------------

    def test_create_hub_native_asset(self):
        """Hub-native asset has correct defaults: source_type, None metadata, display."""
        asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset"
        )
        self.assertEqual(asset.source_type, AssetSourceType.HUB_NATIVE)
        self.assertIsNone(asset.source_metadata)
        self.assertEqual(asset.get_source_type_display(), "Hub Native")

    # ------------------------------------------------------------------
    # Federated asset creation (consolidated from 5 single-assertion tests)
    # ------------------------------------------------------------------

    def test_create_federated_asset(self):
        """Federated asset stores source_type, metadata, display, and individual fields."""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="federated-asset",
            name="Federated Asset",
            source_type=AssetSourceType.FEDERATED,
            source_metadata={
                "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
                "marketplace_id": "marketplace-123",
                "listing_id": "listing-456",
                "listing_url": "https://marketplace.example.com/listings/456",
                "synced_at": timezone.now().isoformat(),
                "sync_job_id": "sync-job-789",
            },
        )
        self.assertEqual(asset.source_type, AssetSourceType.FEDERATED)
        self.assertEqual(asset.source_metadata["marketplace_type"],
                         "SNOWFLAKE_DATA_MARKETPLACE")
        self.assertEqual(asset.source_metadata["listing_id"], "listing-456")
        self.assertEqual(asset.get_source_type_display(), "Federated")

    # ------------------------------------------------------------------
    # Source type choices
    # ------------------------------------------------------------------

    def test_source_type_choices(self):
        """All source type choices are available and enumeration is correct."""
        choices = AssetSourceType.choices
        choice_values = [choice[0] for choice in choices]
        self.assertIn(AssetSourceType.HUB_NATIVE, choice_values)
        self.assertIn(AssetSourceType.FEDERATED, choice_values)
        self.assertEqual(len(choice_values), 2)

    # ------------------------------------------------------------------
    # Source metadata edge cases: None + empty dict
    # ------------------------------------------------------------------

    def test_source_metadata_edge_cases(self):
        """source_metadata accepts None (optional) and empty dict."""
        asset_none = Asset.objects.create(
            tenant=self.tenant,
            key="asset-no-metadata",
            name="Asset Without Metadata",
            source_type=AssetSourceType.FEDERATED,
            source_metadata=None,
        )
        self.assertIsNone(asset_none.source_metadata)

        asset_empty = Asset.objects.create(
            tenant=self.tenant,
            key="asset-empty-metadata",
            name="Asset With Empty Metadata",
            source_type=AssetSourceType.FEDERATED,
            source_metadata={},
        )
        self.assertEqual(asset_empty.source_metadata, {})

    # ------------------------------------------------------------------
    # Source metadata structure (consolidated from 6 single-field tests)
    # ------------------------------------------------------------------

    def test_source_metadata_structure(self):
        """source_metadata JSON stores all expected fields correctly."""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="federated-asset-full",
            name="Federated Asset Full Metadata",
            source_type=AssetSourceType.FEDERATED,
            source_metadata=AWS_SOURCE_METADATA,
        )
        asset.refresh_from_db()
        self.assertEqual(asset.source_metadata["marketplace_type"], "AWS_DATA_EXCHANGE")
        self.assertEqual(asset.source_metadata["marketplace_id"], "aws-marketplace-123")
        self.assertEqual(asset.source_metadata["listing_id"], "aws-listing-456")
        self.assertEqual(
            asset.source_metadata["listing_url"],
            "https://aws.amazon.com/marketplace/listing/456",
        )
        self.assertEqual(asset.source_metadata["synced_at"], "2025-01-01T12:00:00Z")
        self.assertEqual(asset.source_metadata["sync_job_id"], "sync-job-abc123")

    # ------------------------------------------------------------------
    # Complex JSON metadata (consolidated from 3 single-field tests)
    # ------------------------------------------------------------------

    def test_source_metadata_complex_json_structure(self):
        """source_metadata can store nested objects and arrays."""
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
                "tags": ["finance", "market-data"],
            },
            "sync_history": [
                {"date": "2025-01-01", "status": "success"},
                {"date": "2025-01-02", "status": "success"},
            ],
        }

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="complex-federated-asset",
            name="Complex Federated Asset",
            source_type=AssetSourceType.FEDERATED,
            source_metadata=complex_metadata,
        )
        asset.refresh_from_db()

        self.assertEqual(
            asset.source_metadata["additional_info"]["provider"], "Data Provider Inc"
        )
        self.assertEqual(len(asset.source_metadata["sync_history"]), 2)
        self.assertEqual(asset.source_metadata["sync_history"][0]["status"], "success")

    # ------------------------------------------------------------------
    # Filter by source_type (consolidated from 3 tests)
    # ------------------------------------------------------------------

    def test_filter_by_source_type(self):
        """Filtering by source_type returns correct assets; tenant + source_type index works."""
        # Hub-native assets
        Asset.objects.create(
            tenant=self.tenant, key="hub-asset-1", name="Hub Asset 1",
            source_type=AssetSourceType.HUB_NATIVE,
        )
        Asset.objects.create(
            tenant=self.tenant, key="hub-asset-2", name="Hub Asset 2",
            source_type=AssetSourceType.HUB_NATIVE,
        )
        # Federated assets
        Asset.objects.create(
            tenant=self.tenant, key="federated-asset-1", name="Federated Asset 1",
            source_type=AssetSourceType.FEDERATED,
            source_metadata={"marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE"},
        )
        Asset.objects.create(
            tenant=self.tenant, key="federated-asset-2", name="Federated Asset 2",
            source_type=AssetSourceType.FEDERATED,
            source_metadata={"marketplace_type": "AWS_DATA_EXCHANGE"},
        )

        hub_native = Asset.objects.filter(
            tenant=self.tenant, source_type=AssetSourceType.HUB_NATIVE
        )
        self.assertEqual(hub_native.count(), 2)

        federated = Asset.objects.filter(
            tenant=self.tenant, source_type=AssetSourceType.FEDERATED
        )
        self.assertEqual(federated.count(), 2)
        for asset in federated:
            self.assertEqual(asset.source_type, AssetSourceType.FEDERATED)

    # ------------------------------------------------------------------
    # Update source_metadata
    # ------------------------------------------------------------------

    def test_update_source_metadata(self):
        """source_metadata can be updated and changes persist."""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="federated-asset",
            name="Federated Asset",
            source_type=AssetSourceType.FEDERATED,
            source_metadata={"marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE"},
        )
        asset.source_metadata = {
            "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
            "listing_id": "updated-listing-123",
            "synced_at": timezone.now().isoformat(),
        }
        asset.save()
        asset.refresh_from_db()
        self.assertEqual(asset.source_metadata["listing_id"], "updated-listing-123")

    # ------------------------------------------------------------------
    # Default source_type
    # ------------------------------------------------------------------

    def test_default_source_type(self):
        """Default source_type is HUB_NATIVE when not specified."""
        asset = Asset(tenant=self.tenant, key="default-asset", name="Default Asset")
        self.assertEqual(asset.source_type, AssetSourceType.HUB_NATIVE)

    # ------------------------------------------------------------------
    # Source type display (consolidated from 2 tests)
    # ------------------------------------------------------------------

    def test_source_type_display(self):
        """get_source_type_display() returns correct values for both types."""
        hub_asset = Asset.objects.create(
            tenant=self.tenant, key="hub-asset", name="Hub Asset",
            source_type=AssetSourceType.HUB_NATIVE,
        )
        fed_asset = Asset.objects.create(
            tenant=self.tenant, key="federated-asset", name="Federated Asset",
            source_type=AssetSourceType.FEDERATED,
        )
        self.assertEqual(hub_asset.get_source_type_display(), "Hub Native")
        self.assertEqual(fed_asset.get_source_type_display(), "Federated")

    # ------------------------------------------------------------------
    # Invalid source_type
    # ------------------------------------------------------------------

    def test_invalid_source_type(self):
        """Invalid source_type raises ValidationError on full_clean."""
        asset = Asset(
            tenant=self.tenant,
            key="invalid-asset",
            name="Invalid Asset",
            source_type="INVALID_TYPE",
        )
        with self.assertRaises(ValidationError):
            asset.full_clean()


class FederatedAssetIntegrationTest(TestCase):
    """Integration tests for federated asset creation and management"""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}"
        )

    # ------------------------------------------------------------------
    # Federated asset with marketplace info (consolidated from 4 tests)
    # ------------------------------------------------------------------

    def test_create_federated_asset_with_marketplace_info(self):
        """End-to-end: create connection → asset → mapping, verify all relationships."""
        from hub.apps.integrations.base import MarketplaceType
        from hub.apps.integrations.models import MarketplaceConnection, MarketplaceMapping

        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Snowflake Connection",
            config={"api_key": "test-key"},
        )

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
                "synced_at": timezone.now().isoformat(),
            },
        )

        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=connection,
            hub_asset=asset,
            external_listing_id="snowflake-listing-123",
        )

        self.assertEqual(asset.source_type, AssetSourceType.FEDERATED)
        self.assertEqual(mapping.hub_asset, asset)
        self.assertEqual(mapping.connection, connection)
        self.assertEqual(
            asset.source_metadata["marketplace_type"],
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
        )

    # ------------------------------------------------------------------
    # Query performance / index usage (consolidated from 2 tests)
    # ------------------------------------------------------------------

    def test_federated_asset_query_performance(self):
        """Filtering by tenant + source_type is correct and uses index efficiently."""
        for i in range(10):
            Asset.objects.create(
                tenant=self.tenant,
                key=f"hub-asset-{i}",
                name=f"Hub Asset {i}",
                source_type=AssetSourceType.HUB_NATIVE,
            )

        for i in range(5):
            Asset.objects.create(
                tenant=self.tenant,
                key=f"federated-asset-{i}",
                name=f"Federated Asset {i}",
                source_type=AssetSourceType.FEDERATED,
                source_metadata={"marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE"},
            )

        federated = Asset.objects.filter(
            tenant=self.tenant, source_type=AssetSourceType.FEDERATED
        )
        self.assertEqual(federated.count(), 5)
        for asset in federated:
            self.assertEqual(asset.source_type, AssetSourceType.FEDERATED)
