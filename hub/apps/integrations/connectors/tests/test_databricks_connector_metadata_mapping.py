"""
Unit tests for Databricks connector metadata mapping operations.

Tests map_to_hub_asset and verifies that push methods raise NotImplementedError.
"""

from django.test import TestCase

from hub.apps.assets.models import AssetSourceType
from hub.apps.integrations.base import (
    MarketplaceAssetMapping,
    MarketplaceListing,
    MarketplaceResource,
    MarketplaceType,
)
from hub.apps.integrations.connectors.databricks_connector import DatabricksConnector


class TestDatabricksConnectorMetadataMapping(TestCase):
    """Test metadata mapping operations."""

    def setUp(self):
        """Set up test fixtures."""
        from hub.apps.core.resilience.circuit_breaker import reset_circuit_breaker_by_name

        reset_circuit_breaker_by_name("databricks-connector")
        self.connector = DatabricksConnector(
            host="https://test-workspace.cloud.databricks.com", token="test-token"
        )

    def test_map_to_hub_asset_complete_metadata(self):
        """Test map_to_hub_asset with complete metadata."""
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
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-02T00:00:00Z",
                },
                "odps_metadata": {
                    "product": {"name": "Test Product", "description": "Product description"},
                    "pricing_plans": [{"name": "Free", "price": 0}],
                    "access_methods": {"api": {"type": "REST"}},
                    "payment_gateways": {},
                },
                "odcs_metadata": {
                    "schema": {"fields": [{"name": "col1", "type": "string"}]},
                    "quality": {"completeness": 0.95},
                    "sla": {"availability": "99.9%"},
                },
            },
            url="https://test-workspace.cloud.databricks.com/#share/test_share",
        )

        # Execute map_to_hub_asset
        mapping = self.connector.map_to_hub_asset(listing)

        # Verify mapping structure
        assert isinstance(mapping, MarketplaceAssetMapping)
        assert mapping.source_type == AssetSourceType.FEDERATED

        # Verify asset_data
        assert mapping.asset_data["name"] == "Test Share"
        assert mapping.asset_data["description"] == "Test description"
        assert mapping.asset_data["domain"] == "test_category"
        assert mapping.asset_data["tags"] == ["tag1", "tag2"]
        assert mapping.asset_data["status"] == "ACTIVE"
        assert mapping.asset_data["visibility"] == "PUBLIC"

        # Verify source_metadata
        assert (
            mapping.source_metadata["marketplace_type"]
            == MarketplaceType.DATABRICKS_MARKETPLACE.value
        )
        assert mapping.source_metadata["listing_id"] == "test_share"
        assert "synced_at" in mapping.source_metadata
        assert "listing_url" in mapping.source_metadata

        # Verify ODPS metadata
        assert mapping.odps_metadata is not None
        assert "product" in mapping.odps_metadata
        assert "pricing_plans" in mapping.odps_metadata

        # Verify ODCS metadata
        assert mapping.odcs_metadata is not None
        assert "schema" in mapping.odcs_metadata
        assert "quality" in mapping.odcs_metadata
        assert "sla" in mapping.odcs_metadata

    def test_map_to_hub_asset_with_resources(self):
        """Test map_to_hub_asset with resources."""
        resources = [
            MarketplaceResource(
                resource_id="catalog.schema.table1",
                resource_type="TABLE",
                name="Table 1",
                description="Test table 1",
                format="DATABRICKS_TABLE",
            ),
            MarketplaceResource(
                resource_id="catalog.schema.table2",
                resource_type="TABLE",
                name="Table 2",
                description="Test table 2",
                format="DATABRICKS_TABLE",
            ),
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

        # Verify resources
        assert len(mapping.resources) == 2
        for i, resource in enumerate(mapping.resources):
            assert resource.resource_id == resources[i].resource_id
            assert resource.name == resources[i].name
            assert resource.metadata.get("external")
            assert resource.metadata.get("share_name") == "test_share"
            assert resource.metadata.get("table_name") == resources[i].resource_id

    def test_map_to_hub_asset_domain_from_owner(self):
        """Test map_to_hub_asset extracts domain from share owner when category not available."""
        listing = MarketplaceListing(
            marketplace_id="test_share",
            marketplace_type=MarketplaceType.DATABRICKS_MARKETPLACE,
            title="Test Share",
            metadata={"databricks_share": {"name": "test_share", "owner": "owner@example.com"}},
        )

        # Execute map_to_hub_asset
        mapping = self.connector.map_to_hub_asset(listing)

        # Verify domain is extracted from owner
        assert mapping.asset_data["domain"] == "owner@example.com"

    def test_map_to_hub_asset_with_sync_job_id(self):
        """Test map_to_hub_asset includes sync_job_id in source_metadata."""
        listing = MarketplaceListing(
            marketplace_id="test_share",
            marketplace_type=MarketplaceType.DATABRICKS_MARKETPLACE,
            title="Test Share",
            metadata={"databricks_share": {"name": "test_share"}},
        )

        sync_job_id = "job-123-456"

        # Execute map_to_hub_asset
        mapping = self.connector.map_to_hub_asset(listing, sync_job_id=sync_job_id)

        # Verify sync_job_id is included
        assert mapping.source_metadata.get("sync_job_id") == sync_job_id

    def test_map_to_hub_asset_listing_url_generation(self):
        """Test map_to_hub_asset generates listing_url when not provided."""
        listing = MarketplaceListing(
            marketplace_id="test_share",
            marketplace_type=MarketplaceType.DATABRICKS_MARKETPLACE,
            title="Test Share",
            metadata={"databricks_share": {"name": "test_share"}},
        )

        # Execute map_to_hub_asset
        mapping = self.connector.map_to_hub_asset(listing)

        # Verify listing_url is generated
        expected_url = f"{self.connector.host}/#share/test_share"
        assert mapping.source_metadata["listing_url"] == expected_url

    def test_map_to_hub_asset_minimal_listing(self):
        """Test map_to_hub_asset with minimal listing data."""
        listing = MarketplaceListing(
            marketplace_id="minimal_share",
            marketplace_type=MarketplaceType.DATABRICKS_MARKETPLACE,
            title="Minimal Share",
            metadata={},
        )

        # Execute map_to_hub_asset
        mapping = self.connector.map_to_hub_asset(listing)

        # Verify mapping is created with defaults
        assert isinstance(mapping, MarketplaceAssetMapping)
        assert mapping.asset_data["name"] == "Minimal Share"
        assert mapping.asset_data["status"] == "ACTIVE"
        assert mapping.asset_data["visibility"] == "PUBLIC"
        assert mapping.odps_metadata is None
        assert mapping.odcs_metadata is None


class TestDatabricksConnectorPushOperations(TestCase):
    """Test that push operations raise NotImplementedError."""

    def setUp(self):
        """Set up test fixtures."""
        from hub.apps.core.resilience.circuit_breaker import reset_circuit_breaker_by_name

        reset_circuit_breaker_by_name("databricks-connector")
        self.connector = DatabricksConnector(
            host="https://test-workspace.cloud.databricks.com", token="test-token"
        )

    def test_create_listing_raises_not_implemented(self):
        """Test create_listing() raises NotImplementedError."""
        listing_data = {"name": "test_share", "comment": "Test share"}

        with self.assertRaises(NotImplementedError) as cm:
            self.connector.create_listing(listing_data)

        assert "harvest-only" in str(cm.exception).lower()
        assert "PULL" in str(cm.exception)

    def test_update_listing_raises_not_implemented(self):
        """Test update_listing() raises NotImplementedError."""
        listing_data = {"comment": "Updated comment"}

        with self.assertRaises(NotImplementedError) as cm:
            self.connector.update_listing("test_share", listing_data)

        assert "harvest-only" in str(cm.exception).lower()
        assert "PULL" in str(cm.exception)

    def test_publish_resource_raises_not_implemented(self):
        """Test publish_resource() raises NotImplementedError."""
        resource_data = {"name": "test_table", "type": "TABLE"}

        with self.assertRaises(NotImplementedError) as cm:
            self.connector.publish_resource("test_share", resource_data)

        assert "harvest-only" in str(cm.exception).lower()
        assert "PULL" in str(cm.exception)

    def test_map_from_hub_asset_raises_not_implemented(self):
        """Test map_from_hub_asset() raises NotImplementedError."""
        asset_data = {"name": "Test Asset", "description": "Test description"}

        with self.assertRaises(NotImplementedError) as cm:
            self.connector.map_from_hub_asset(asset_data)

        assert "harvest-only" in str(cm.exception).lower()
        assert "PULL" in str(cm.exception)

    def test_sync_push_raises_not_implemented(self):
        """Test sync_push() raises NotImplementedError."""
        with self.assertRaises(NotImplementedError) as cm:
            self.connector.sync_push(["asset-1", "asset-2"])

        assert "harvest-only" in str(cm.exception).lower()
        assert "PULL" in str(cm.exception)

    def test_sync_push_with_options_raises_not_implemented(self):
        """Test sync_push() with options raises NotImplementedError."""
        options = {"dry_run": True, "force_update": False}

        with self.assertRaises(NotImplementedError) as cm:
            self.connector.sync_push(["asset-1"], options)

        assert "harvest-only" in str(cm.exception).lower()
        assert "PULL" in str(cm.exception)

    def test_sync_push_empty_list_raises_not_implemented(self):
        """Test sync_push() with empty list raises NotImplementedError."""
        with self.assertRaises(NotImplementedError) as cm:
            self.connector.sync_push([])

        assert "harvest-only" in str(cm.exception).lower()
        assert "PULL" in str(cm.exception)

    def test_supported_sync_directions_is_pull_only(self):
        """Test that supported_sync_directions only includes PULL."""
        from hub.apps.integrations.base import SyncDirection

        supported = self.connector.supported_sync_directions
        assert len(supported) == 1
        assert supported[0] == SyncDirection.PULL
        assert SyncDirection.PUSH not in supported
        assert SyncDirection.BIDIRECTIONAL not in supported
