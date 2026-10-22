"""
Unit tests for Databricks connector pull operations.

Tests sync_pull and map_to_hub_asset methods following metadata-first pattern.
"""

from unittest.mock import patch

from django.test import TestCase

from hub.apps.assets.models import AssetSourceType
from hub.apps.core.services.base import NotFoundError
from hub.apps.integrations.base import (
    MarketplaceListing,
    MarketplaceResource,
    MarketplaceType,
    SyncStatus,
)
from hub.apps.integrations.connectors.databricks_connector import DatabricksConnector



# P3-2b: the DATABRICKS_MARKETPLACE connector TYPE registration lives in
# the databricks_admin estate (its apps.py ready()) — absent from the
# core-only public tree, the factory lookup returns None. Excluded from
# the core CI's test set; the private full suite runs them.
pytestmark = [pytest.mark.requires_estate]

class TestDatabricksConnectorSyncPull(TestCase):
    """Test sync_pull method."""

    def setUp(self):
        """Set up test fixtures."""
        from hub.apps.core.resilience.circuit_breaker import reset_circuit_breaker_by_name

        reset_circuit_breaker_by_name("databricks-connector")
        self.connector = DatabricksConnector(
            host="https://test-workspace.cloud.databricks.com", token="test-token"
        )

    @patch.object(DatabricksConnector, "_request_with_retry")
    @patch.object(DatabricksConnector, "get_listing")
    @patch.object(DatabricksConnector, "list_resources")
    @patch.object(DatabricksConnector, "map_to_hub_asset")
    def test_sync_pull_with_listing_ids(
        self, mock_map, mock_list_resources, mock_get_listing, mock_request
    ):
        """Test sync_pull with specific listing IDs."""
        # Mock listing
        listing = MarketplaceListing(
            marketplace_id="test_share",
            marketplace_type=MarketplaceType.DATABRICKS_MARKETPLACE,
            title="Test Share",
            description="Test description",
        )
        mock_get_listing.return_value = listing

        # Mock resources
        resources = [
            MarketplaceResource(
                resource_id="table1",
                resource_type="TABLE",
                name="Table 1",
                format="DATABRICKS_TABLE",
            )
        ]
        mock_list_resources.return_value = resources

        # Mock mapping
        from hub.apps.integrations.base import MarketplaceAssetMapping

        mapping = MarketplaceAssetMapping(
            asset_data={"name": "Test Share"},
            source_type=AssetSourceType.FEDERATED,
            source_metadata={"marketplace_type": "DATABRICKS_MARKETPLACE"},
            resources=resources,
        )
        mock_map.return_value = mapping

        # Execute sync_pull
        result = self.connector.sync_pull(listing_ids=["test_share"])

        # Assertions
        assert result.status == SyncStatus.COMPLETED
        assert result.total_items == 1
        assert result.successful_items == 1
        assert result.failed_items == 0
        assert "mappings" in result.metadata
        assert len(result.metadata["mappings"]) == 1
        mock_get_listing.assert_called_once_with("test_share")
        mock_list_resources.assert_called_once_with("test_share")
        mock_map.assert_called_once()

    @patch.object(DatabricksConnector, "_request_with_retry")
    @patch.object(DatabricksConnector, "list_listings")
    @patch.object(DatabricksConnector, "list_resources")
    @patch.object(DatabricksConnector, "map_to_hub_asset")
    def test_sync_pull_with_filters(
        self, mock_map, mock_list_resources, mock_list_listings, mock_request
    ):
        """Test sync_pull with filters."""
        # Mock listings
        listings = [
            MarketplaceListing(
                marketplace_id="share1",
                marketplace_type=MarketplaceType.DATABRICKS_MARKETPLACE,
                title="Share 1",
            ),
            MarketplaceListing(
                marketplace_id="share2",
                marketplace_type=MarketplaceType.DATABRICKS_MARKETPLACE,
                title="Share 2",
            ),
        ]
        mock_list_listings.return_value = listings

        # Mock resources
        mock_list_resources.return_value = []

        # Mock mapping
        from hub.apps.integrations.base import MarketplaceAssetMapping

        mapping = MarketplaceAssetMapping(
            asset_data={"name": "Share"},
            source_type=AssetSourceType.FEDERATED,
            source_metadata={"marketplace_type": "DATABRICKS_MARKETPLACE"},
            resources=[],
        )
        mock_map.return_value = mapping

        # Execute sync_pull
        result = self.connector.sync_pull(filters={}, options={"limit": 10})

        # Assertions
        assert result.status == SyncStatus.COMPLETED
        assert result.total_items == 2
        assert result.successful_items == 2
        assert result.failed_items == 0
        # list_listings is called without offset when not provided
        mock_list_listings.assert_called_once_with(filters={}, limit=10)

    @patch.object(DatabricksConnector, "_request_with_retry")
    @patch.object(DatabricksConnector, "get_listing")
    def test_sync_pull_listing_not_found(self, mock_get_listing, mock_request):
        """Test sync_pull when listing is not found."""
        mock_get_listing.side_effect = NotFoundError("Share not found")

        # Execute sync_pull
        result = self.connector.sync_pull(listing_ids=["nonexistent"])

        # Assertions
        # When listing is not found, it's skipped, not failed - status should be COMPLETED
        assert result.status == SyncStatus.COMPLETED
        assert result.total_items == 0
        assert result.successful_items == 0
        assert result.skipped_items == 1
        assert len(result.errors) == 1

    @patch.object(DatabricksConnector, "_request_with_retry")
    @patch.object(DatabricksConnector, "get_listing")
    @patch.object(DatabricksConnector, "map_to_hub_asset")
    def test_sync_pull_mapping_failure(self, mock_map, mock_get_listing, mock_request):
        """Test sync_pull when mapping fails."""
        listing = MarketplaceListing(
            marketplace_id="test_share",
            marketplace_type=MarketplaceType.DATABRICKS_MARKETPLACE,
            title="Test Share",
        )
        mock_get_listing.return_value = listing
        mock_map.side_effect = ValueError("Mapping failed")

        # Execute sync_pull
        result = self.connector.sync_pull(listing_ids=["test_share"])

        # Assertions
        # When all items fail (0 successful, 1 failed), status should be FAILED
        assert result.status == SyncStatus.FAILED
        assert result.total_items == 1
        assert result.successful_items == 0
        assert result.failed_items == 1
        assert len(result.errors) == 1

    @patch.object(DatabricksConnector, "_request_with_retry")
    @patch.object(DatabricksConnector, "list_listings")
    def test_sync_pull_no_listings(self, mock_list_listings, mock_request):
        """Test sync_pull when no listings are found."""
        mock_list_listings.return_value = []

        # Execute sync_pull
        result = self.connector.sync_pull()

        # Assertions
        assert result.status == SyncStatus.COMPLETED
        assert result.total_items == 0
        assert result.successful_items == 0
        assert result.failed_items == 0

    @patch.object(DatabricksConnector, "_request_with_retry")
    @patch.object(DatabricksConnector, "list_listings")
    @patch.object(DatabricksConnector, "list_resources")
    @patch.object(DatabricksConnector, "map_to_hub_asset")
    def test_sync_pull_without_resources(
        self, mock_map, mock_list_resources, mock_list_listings, mock_request
    ):
        """Test sync_pull with include_resources=False."""
        listing = MarketplaceListing(
            marketplace_id="share1",
            marketplace_type=MarketplaceType.DATABRICKS_MARKETPLACE,
            title="Share 1",
        )
        mock_list_listings.return_value = [listing]

        from hub.apps.integrations.base import MarketplaceAssetMapping

        mapping = MarketplaceAssetMapping(
            asset_data={"name": "Share 1"},
            source_type=AssetSourceType.FEDERATED,
            source_metadata={"marketplace_type": "DATABRICKS_MARKETPLACE"},
            resources=[],
        )
        mock_map.return_value = mapping

        # Execute sync_pull
        result = self.connector.sync_pull(options={"include_resources": False})

        # Assertions
        assert result.status == SyncStatus.COMPLETED
        mock_list_resources.assert_not_called()


class TestDatabricksConnectorMapToHubAsset(TestCase):
    """Test map_to_hub_asset method."""

    def setUp(self):
        """Set up test fixtures."""
        from hub.apps.core.resilience.circuit_breaker import reset_circuit_breaker_by_name

        reset_circuit_breaker_by_name("databricks-connector")
        self.connector = DatabricksConnector(
            host="https://test-workspace.cloud.databricks.com", token="test-token"
        )

    def test_map_to_hub_asset_basic(self):
        """Test basic mapping of listing to Hub asset."""
        listing = MarketplaceListing(
            marketplace_id="test_share",
            marketplace_type=MarketplaceType.DATABRICKS_MARKETPLACE,
            title="Test Share",
            description="Test description",
            category="test_category",
            tags=["tag1", "tag2"],
            metadata={
                "databricks_share": {
                    "name": "test_share",
                    "comment": "Test comment",
                    "owner": "test_owner",
                },
                "odps_metadata": {"product": {"name": "Test Product"}},
                "odcs_metadata": {"schema": {"fields": []}},
            },
            url="https://test-workspace.cloud.databricks.com/#share/test_share",
        )

        # Execute map_to_hub_asset
        mapping = self.connector.map_to_hub_asset(listing)

        # Assertions
        assert mapping.source_type == AssetSourceType.FEDERATED
        assert mapping.asset_data["name"] == "Test Share"
        assert mapping.asset_data["description"] == "Test description"
        assert mapping.asset_data["domain"] == "test_category"
        assert mapping.asset_data["tags"] == ["tag1", "tag2"]
        assert mapping.source_metadata["marketplace_type"] == "DATABRICKS_MARKETPLACE"
        assert mapping.source_metadata["listing_id"] == "test_share"
        assert mapping.odps_metadata is not None
        assert mapping.odcs_metadata is not None

    def test_map_to_hub_asset_with_resources(self):
        """Test mapping with resources."""
        resources = [
            MarketplaceResource(
                resource_id="table1",
                resource_type="TABLE",
                name="Table 1",
                description="Test table",
                format="DATABRICKS_TABLE",
            )
        ]

        listing = MarketplaceListing(
            marketplace_id="test_share",
            marketplace_type=MarketplaceType.DATABRICKS_MARKETPLACE,
            title="Test Share",
            resources=resources,
            metadata={"databricks_share": {"name": "test_share"}},
        )

        # Execute map_to_hub_asset
        mapping = self.connector.map_to_hub_asset(listing)

        # Assertions
        assert len(mapping.resources) == 1
        resource = mapping.resources[0]
        assert resource.resource_id == "table1"
        assert resource.metadata.get("external")
        assert resource.metadata.get("share_name") == "test_share"
        assert resource.metadata.get("table_name") == "table1"

    def test_map_to_hub_asset_with_sync_job_id(self):
        """Test mapping with sync_job_id."""
        listing = MarketplaceListing(
            marketplace_id="test_share",
            marketplace_type=MarketplaceType.DATABRICKS_MARKETPLACE,
            title="Test Share",
            metadata={"databricks_share": {"name": "test_share"}},
        )

        # Execute map_to_hub_asset
        mapping = self.connector.map_to_hub_asset(listing, sync_job_id="job-123")

        # Assertions
        assert mapping.source_metadata["sync_job_id"] == "job-123"

    def test_map_to_hub_asset_no_listing(self):
        """Test mapping with None listing raises ValueError."""
        with self.assertRaises(ValueError):
            self.connector.map_to_hub_asset(None)

    def test_map_to_hub_asset_minimal_metadata(self):
        """Test mapping with minimal metadata."""
        listing = MarketplaceListing(
            marketplace_id="test_share",
            marketplace_type=MarketplaceType.DATABRICKS_MARKETPLACE,
            title="Test Share",
            metadata={},
        )

        # Execute map_to_hub_asset
        mapping = self.connector.map_to_hub_asset(listing)

        # Assertions
        assert mapping.asset_data["name"] == "Test Share"
        assert mapping.odps_metadata is None
        assert mapping.odcs_metadata is None
