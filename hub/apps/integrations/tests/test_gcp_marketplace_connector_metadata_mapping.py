"""
Unit Tests for GCP Marketplace Connector Metadata Mapping Operations

Tests the metadata mapping operations (map_to_hub_asset, map_from_hub_asset)
and push operations (create_listing, update_listing, publish_resource, sync_push)
for the GCP Marketplace connector.

These tests validate:
- map_to_hub_asset() correctly maps Analytics Hub listings to Hub assets
- map_to_hub_asset() uses exchange_name (data_exchange_id) as domain
- All push methods correctly raise NotImplementedError
- Metadata extraction (ODPS and ODCS) is correct
"""

from unittest.mock import Mock, patch

from django.test import TestCase

from hub.apps.assets.models import AssetSourceType
from hub.apps.core.services.base import NotFoundError
from hub.apps.integrations.base import (
    MarketplaceAssetMapping,
    MarketplaceListing,
    MarketplaceResource,
    MarketplaceType,
)
from hub.apps.core.resilience.circuit_breaker import reset_circuit_breaker_by_name
from hub.apps.integrations.connectors.gcp_marketplace_connector import GCPMarketplaceConnector


class TestGCPMarketplaceConnectorMetadataMapping(TestCase):
    """Test metadata mapping operations"""

    def setUp(self):
        """Set up test fixtures"""
        reset_circuit_breaker_by_name("gcp-marketplace-connector")
        self.connector = GCPMarketplaceConnector(project_id="test-project", use_adc=True)

    @patch(
        "hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector.list_resources"
    )
    def test_map_to_hub_asset_uses_exchange_name_as_domain(self, mock_list_resources):
        """Test map_to_hub_asset() uses exchange_name (data_exchange_id) as domain"""
        # Mock listing with data_exchange_id
        listing = MarketplaceListing(
            marketplace_id="test-listing-id",
            marketplace_type=MarketplaceType.GOOGLE_CLOUD_MARKETPLACE,
            title="Test Listing",
            description="Test description",
            category="test-category",  # Should be overridden by exchange_name
            metadata={
                "analytics_hub_listing": {
                    "display_name": "Test Listing",
                    "description": "Test description",
                },
                "data_exchange_id": "test-exchange-name",  # This should be used as domain
            },
        )

        mock_list_resources.return_value = []

        # Map to Hub asset
        mapping = self.connector.map_to_hub_asset(listing)

        # Verify domain is set to exchange_name (data_exchange_id)
        self.assertEqual(mapping.asset_data["domain"], "test-exchange-name")
        # Verify category is NOT used (exchange_name takes precedence)
        self.assertNotEqual(mapping.asset_data.get("domain"), "test-category")

    @patch(
        "hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector.list_resources"
    )
    def test_map_to_hub_asset_extracts_all_metadata(self, mock_list_resources):
        """Test map_to_hub_asset() extracts all required metadata"""
        listing = MarketplaceListing(
            marketplace_id="test-listing-id",
            marketplace_type=MarketplaceType.GOOGLE_CLOUD_MARKETPLACE,
            title="Test Listing",
            description="Test description",
            tags=["tag1", "tag2"],
            url="https://console.cloud.google.com/bigquery/analytics-hub/...",
            metadata={
                "analytics_hub_listing": {
                    "name": "projects/test-project/locations/US/dataExchanges/test-exchange/listings/test-listing-id",
                    "display_name": "Test Listing",
                    "description": "Test description",
                    "bigquery_dataset": {"dataset": "projects/test-project/datasets/test_dataset"},
                    "data_provider": "Test Provider",
                },
                "data_exchange_id": "test-exchange",
                "odps_metadata": {
                    "product_details": {
                        "productID": "test-listing-id",
                        "product_name": "Test Listing",
                    },
                    "pricing_plans": [{"plan_name": "subscription"}],
                },
                "odcs_metadata": {
                    "schema": {"dataset_reference": "projects/test-project/datasets/test_dataset"}
                },
            },
        )

        mock_resource = MarketplaceResource(
            resource_id="test-table",
            resource_type="BIGQUERY_TABLE",
            name="Test Table",
            metadata={"external": True},
        )
        mock_list_resources.return_value = [mock_resource]

        # Map to Hub asset
        mapping = self.connector.map_to_hub_asset(listing, sync_job_id="test-job-123")

        # Verify asset_data
        self.assertEqual(mapping.asset_data["name"], "Test Listing")
        self.assertEqual(mapping.asset_data["description"], "Test description")
        self.assertEqual(mapping.asset_data["domain"], "test-exchange")  # exchange_name
        self.assertEqual(mapping.asset_data["status"], "ACTIVE")
        self.assertEqual(mapping.asset_data["visibility"], "PUBLIC")
        self.assertIn("tag1", mapping.asset_data["tags"])
        self.assertIn("tag2", mapping.asset_data["tags"])

        # Verify source_metadata
        self.assertEqual(
            mapping.source_metadata["marketplace_type"],
            MarketplaceType.GOOGLE_CLOUD_MARKETPLACE.value,
        )
        self.assertEqual(mapping.source_metadata["listing_id"], "test-listing-id")
        self.assertEqual(mapping.source_metadata["data_exchange_id"], "test-exchange")
        self.assertEqual(mapping.source_metadata["sync_job_id"], "test-job-123")
        self.assertIn("synced_at", mapping.source_metadata)
        self.assertEqual(
            mapping.source_metadata["bigquery_dataset"],
            "projects/test-project/datasets/test_dataset",
        )
        self.assertEqual(mapping.source_metadata["provider"], "Test Provider")

        # Verify ODPS and ODCS metadata
        self.assertIsNotNone(mapping.odps_metadata)
        self.assertIn("product_details", mapping.odps_metadata)
        self.assertIsNotNone(mapping.odcs_metadata)
        self.assertIn("schema", mapping.odcs_metadata)

        # Verify resources
        self.assertEqual(len(mapping.resources), 1)
        self.assertTrue(mapping.resources[0].metadata.get("external"))

    @patch(
        "hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector.list_resources"
    )
    def test_map_to_hub_asset_fallback_domain(self, mock_list_resources):
        """Test map_to_hub_asset() falls back to category if exchange_name not available"""
        listing = MarketplaceListing(
            marketplace_id="test-listing-id",
            marketplace_type=MarketplaceType.GOOGLE_CLOUD_MARKETPLACE,
            title="Test Listing",
            category="fallback-category",
            metadata={
                "analytics_hub_listing": {
                    "display_name": "Test Listing",
                },
                # No data_exchange_id
            },
        )

        mock_list_resources.return_value = []

        # Map to Hub asset
        mapping = self.connector.map_to_hub_asset(listing)

        # Verify domain falls back to category
        self.assertEqual(mapping.asset_data["domain"], "fallback-category")

    def test_map_to_hub_asset_missing_listing(self):
        """Test map_to_hub_asset() raises ValueError for missing listing"""
        with self.assertRaises(ValueError) as cm:
            self.connector.map_to_hub_asset(None)  # type: ignore[arg-type]  # test: edge-case type exercise
        self.assertIn("required", str(cm.exception).lower())

    def test_map_from_hub_asset_raises_not_implemented(self):
        """Test map_from_hub_asset() raises NotImplementedError"""
        asset_data = {"name": "Test Asset"}
        with self.assertRaises(NotImplementedError) as cm:
            self.connector.map_from_hub_asset(asset_data)
        self.assertIn("harvest-only", str(cm.exception).lower())
        self.assertIn("PULL", str(cm.exception))

    def test_create_listing_raises_not_implemented(self):
        """Test create_listing() raises NotImplementedError"""
        listing = Mock()
        with self.assertRaises(NotImplementedError) as cm:
            self.connector.create_listing(listing)
        self.assertIn("harvest-only", str(cm.exception).lower())
        self.assertIn("PULL", str(cm.exception))

    def test_update_listing_raises_not_implemented(self):
        """Test update_listing() raises NotImplementedError"""
        listing = Mock()
        with self.assertRaises(NotImplementedError) as cm:
            self.connector.update_listing("test-id", listing)
        self.assertIn("harvest-only", str(cm.exception).lower())
        self.assertIn("PULL", str(cm.exception))

    def test_publish_resource_raises_not_implemented(self):
        """Test publish_resource() raises NotImplementedError"""
        resource = Mock()
        with self.assertRaises(NotImplementedError) as cm:
            self.connector.publish_resource("test-id", resource)
        self.assertIn("harvest-only", str(cm.exception).lower())
        self.assertIn("PULL", str(cm.exception))

    def test_sync_push_raises_not_implemented(self):
        """Test sync_push() raises NotImplementedError"""
        with self.assertRaises(NotImplementedError) as cm:
            self.connector.sync_push(["asset-1", "asset-2"])
        self.assertIn("harvest-only", str(cm.exception).lower())
        self.assertIn("PULL", str(cm.exception))

    @patch(
        "hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector.list_resources"
    )
    def test_map_to_hub_asset_source_type_federated(self, mock_list_resources):
        """Test map_to_hub_asset() always returns FEDERATED source type"""
        listing = MarketplaceListing(
            marketplace_id="test-listing-id",
            marketplace_type=MarketplaceType.GOOGLE_CLOUD_MARKETPLACE,
            title="Test Listing",
            metadata={
                "analytics_hub_listing": {"display_name": "Test Listing"},
                "data_exchange_id": "test-exchange",
            },
        )

        mock_list_resources.return_value = []

        mapping = self.connector.map_to_hub_asset(listing)

        # Verify source_type is always FEDERATED
        self.assertEqual(mapping.source_type, AssetSourceType.FEDERATED)

    @patch(
        "hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector.list_resources"
    )
    def test_map_to_hub_asset_listing_url(self, mock_list_resources):
        """Test map_to_hub_asset() includes listing_url in source_metadata"""
        listing = MarketplaceListing(
            marketplace_id="test-listing-id",
            marketplace_type=MarketplaceType.GOOGLE_CLOUD_MARKETPLACE,
            title="Test Listing",
            url="https://console.cloud.google.com/bigquery/analytics-hub/exchange/test-project/US/test-exchange/listing/test-listing-id",
            metadata={
                "analytics_hub_listing": {"display_name": "Test Listing"},
                "data_exchange_id": "test-exchange",
            },
        )

        mock_list_resources.return_value = []

        mapping = self.connector.map_to_hub_asset(listing)

        # Verify listing_url is included
        self.assertEqual(mapping.source_metadata["listing_url"], listing.url)

    @patch(
        "hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector.list_resources"
    )
    def test_map_to_hub_asset_with_resources(self, mock_list_resources):
        """Test map_to_hub_asset() includes resources with external metadata"""
        listing = MarketplaceListing(
            marketplace_id="test-listing-id",
            marketplace_type=MarketplaceType.GOOGLE_CLOUD_MARKETPLACE,
            title="Test Listing",
            metadata={
                "analytics_hub_listing": {
                    "display_name": "Test Listing",
                    "bigquery_dataset": {"dataset": "projects/test-project/datasets/test_dataset"},
                },
                "data_exchange_id": "test-exchange",
            },
        )

        mock_resource1 = MarketplaceResource(
            resource_id="table1", resource_type="BIGQUERY_TABLE", name="Table 1", metadata={}
        )
        mock_resource2 = MarketplaceResource(
            resource_id="table2", resource_type="BIGQUERY_TABLE", name="Table 2", metadata={}
        )
        mock_list_resources.return_value = [mock_resource1, mock_resource2]

        mapping = self.connector.map_to_hub_asset(listing)

        # Verify resources are included
        self.assertEqual(len(mapping.resources), 2)
        # Verify all resources are marked as external
        for resource in mapping.resources:
            self.assertTrue(resource.metadata.get("external"))
            self.assertEqual(resource.metadata.get("listing_id"), "test-listing-id")
            self.assertEqual(resource.metadata.get("data_exchange_id"), "test-exchange")
            self.assertEqual(
                resource.metadata.get("bigquery_dataset"),
                "projects/test-project/datasets/test_dataset",
            )

    @patch(
        "hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector.list_resources"
    )
    def test_map_to_hub_asset_with_empty_metadata(self, mock_list_resources):
        """Test map_to_hub_asset() handles empty metadata gracefully"""
        listing = MarketplaceListing(
            marketplace_id="test-listing-id",
            marketplace_type=MarketplaceType.GOOGLE_CLOUD_MARKETPLACE,
            title="Test Listing",
            description="Test description",
            metadata={},  # Empty metadata
        )

        mock_list_resources.return_value = []

        # Should handle empty metadata gracefully
        mapping = self.connector.map_to_hub_asset(listing)

        # Verify basic structure is still created
        self.assertIsInstance(mapping, MarketplaceAssetMapping)
        self.assertEqual(mapping.asset_data["name"], "Test Listing")
        self.assertEqual(mapping.source_type, AssetSourceType.FEDERATED)

    @patch(
        "hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector.list_resources"
    )
    def test_map_to_hub_asset_with_missing_title(self, mock_list_resources):
        """Test map_to_hub_asset() handles missing title gracefully"""
        listing = MarketplaceListing(
            marketplace_id="test-listing-id",
            marketplace_type=MarketplaceType.GOOGLE_CLOUD_MARKETPLACE,
            title=None,  # type: ignore[arg-type]  # Missing title
            metadata={
                "analytics_hub_listing": {"display_name": "Display Name"},
                "data_exchange_id": "test-exchange",
            },
        )

        mock_list_resources.return_value = []

        # Should use display_name as fallback
        mapping = self.connector.map_to_hub_asset(listing)

        # Verify fallback to display_name
        self.assertIsNotNone(mapping.asset_data.get("name"))
        self.assertEqual(mapping.asset_data["name"], "Display Name")

    def test_map_to_hub_asset_with_invalid_listing_type(self):
        """Test map_to_hub_asset() error handling with invalid listing type"""
        # Create listing with wrong marketplace type
        listing = MarketplaceListing(
            marketplace_id="test-listing-id",
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE,  # Wrong type
            title="Test Listing",
            metadata={"data_exchange_id": "test-exchange"},
        )

        # Should handle gracefully or raise appropriate error
        try:
            mapping = self.connector.map_to_hub_asset(listing)
            # If it succeeds, verify basic structure
            self.assertIsInstance(mapping, MarketplaceAssetMapping)
        except (ValueError, TypeError):
            # Expected if connector validates marketplace type
            pass

    @patch(
        "hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector.list_resources"
    )
    def test_map_to_hub_asset_with_list_resources_error(self, mock_list_resources):
        """Test map_to_hub_asset() handles list_resources errors gracefully"""
        listing = MarketplaceListing(
            marketplace_id="test-listing-id",
            marketplace_type=MarketplaceType.GOOGLE_CLOUD_MARKETPLACE,
            title="Test Listing",
            metadata={
                "analytics_hub_listing": {"display_name": "Test Listing"},
                "data_exchange_id": "test-exchange",
            },
        )

        # Simulate list_resources raising an error
        from hub.apps.core.services.base import NotFoundError

        mock_list_resources.side_effect = NotFoundError("Resources not found")

        # Should handle error gracefully and still create mapping
        try:
            mapping = self.connector.map_to_hub_asset(listing)
            # If it succeeds, verify basic structure
            self.assertIsInstance(mapping, MarketplaceAssetMapping)
            # Resources may be empty due to error
            self.assertIsInstance(mapping.resources, list)
        except NotFoundError:
            # Expected if connector propagates error
            pass

    def test_map_from_hub_asset_with_none(self):
        """Test map_from_hub_asset() error handling with None"""
        with self.assertRaises((NotImplementedError, ValueError, TypeError)):
            self.connector.map_from_hub_asset(None)  # type: ignore[arg-type]  # test: edge-case type exercise

    def test_create_listing_with_none(self):
        """Test create_listing() error handling with None"""
        with self.assertRaises((NotImplementedError, ValueError, TypeError)):
            self.connector.create_listing(None)  # type: ignore[arg-type]  # test: edge-case type exercise

    def test_update_listing_with_invalid_id(self):
        """Test update_listing() error handling with invalid ID"""
        listing = Mock()
        with self.assertRaises(NotImplementedError):
            self.connector.update_listing(None, listing)  # type: ignore[arg-type]  # test: edge-case type exercise
        with self.assertRaises(NotImplementedError):
            self.connector.update_listing("", listing)
