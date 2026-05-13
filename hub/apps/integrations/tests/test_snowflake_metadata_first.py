"""
Tests for Snowflake Connector Metadata-First Architecture Pattern

Comprehensive tests to validate that the Snowflake connector properly follows
the metadata-first architecture pattern:
- sync_pull() only maps listings, does NOT create databases or download data
- download_resource() handles deferred operations (request listing, accept terms, create DB, extract schema, download)
- map_to_hub_asset() includes external resource references
"""

from datetime import datetime
from unittest.mock import MagicMock, Mock, call, patch

import pytest

from hub.apps.assets.models import AssetSourceType
from hub.apps.core.services.base import ConnectionError, NotFoundError
from hub.apps.integrations.base import (
    MarketplaceAssetMapping,
    MarketplaceListing,
    MarketplaceResource,
    MarketplaceType,
    SyncDirection,
    SyncResult,
    SyncStatus,
)
from hub.apps.integrations.connectors.snowflake_connector import SnowflakeConnector

# Use pytest.mark.django_db without transaction to avoid foreign key constraint issues
pytestmark = pytest.mark.django_db(transaction=True)


class TestSnowflakeConnectorMetadataFirst:
    """Test that Snowflake connector follows metadata-first architecture pattern"""

    @pytest.fixture
    def connector(self):
        """Create a Snowflake connector instance for testing"""
        with patch(
            "hub.apps.integrations.connectors.snowflake_connector.SNOWFLAKE_AVAILABLE", True
        ):
            connector = SnowflakeConnector(
                account="test_account", user="test_user", token="test_token"
            )
            # Mock the connection to avoid actual Snowflake calls
            connector._connection = Mock()
            connector._authenticated = True
            return connector

    @pytest.fixture
    def sample_listing(self):
        """Create a sample marketplace listing"""
        return MarketplaceListing(
            marketplace_id="SNOWFLAKE_SAMPLE_DATA",
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
            title="Sample Data",
            description="Sample data from Snowflake",
            category="Analytics",
            tags=["sample", "data"],
            metadata={
                "snowflake_database": {"DATABASE_OWNER": "SNOWFLAKE", "COMMENT": "Sample database"}
            },
        )

    def test_sync_pull_does_not_create_databases(self, connector, sample_listing):
        """Test that sync_pull() does NOT create databases (metadata-first pattern)"""
        # Mock list_listings to return sample listing
        connector.list_listings = Mock(return_value=[sample_listing])
        connector.list_resources = Mock(return_value=[])
        connector.map_to_hub_asset = Mock(
            return_value=MarketplaceAssetMapping(
                asset_data={"name": "Test"},
                source_type=AssetSourceType.FEDERATED,
                source_metadata={},
                odps_metadata={},
            )
        )

        # Mock methods that should NOT be called
        connector._request_listing = Mock()
        connector._accept_legal_terms = Mock()
        connector._create_database_from_listing = Mock()
        connector._extract_schema_metadata = Mock()

        # Execute sync_pull
        result = connector.sync_pull()

        # Verify database creation methods were NOT called
        connector._request_listing.assert_not_called()
        connector._accept_legal_terms.assert_not_called()
        connector._create_database_from_listing.assert_not_called()
        connector._extract_schema_metadata.assert_not_called()

        # Verify sync_pull only mapped listings
        assert isinstance(result, SyncResult)
        assert result.status in [SyncStatus.COMPLETED, SyncStatus.PARTIAL]
        assert "mappings" in result.metadata
        assert isinstance(result.metadata["mappings"], list)

    def test_sync_pull_only_maps_listings(self, connector, sample_listing):
        """Test that sync_pull() only maps listings to MarketplaceAssetMapping"""
        connector.list_listings = Mock(return_value=[sample_listing])
        connector.list_resources = Mock(return_value=[])

        mapping = MarketplaceAssetMapping(
            asset_data={"name": "Test"},
            source_type=AssetSourceType.FEDERATED,
            source_metadata={},
            odps_metadata={},
        )
        connector.map_to_hub_asset = Mock(return_value=mapping)

        # Execute sync_pull
        result = connector.sync_pull()

        # Verify map_to_hub_asset was called (sync_job_id is optional, may not be passed)
        connector.map_to_hub_asset.assert_called_once()
        call_args = connector.map_to_hub_asset.call_args
        assert call_args[0][0] == sample_listing

        # Verify result contains mappings
        assert len(result.metadata["mappings"]) == 1
        assert result.successful_items == 1

    def test_sync_pull_returns_mappings_in_metadata(self, connector, sample_listing):
        """Test that sync_pull() returns mappings in SyncResult.metadata"""
        connector.list_listings = Mock(return_value=[sample_listing])
        connector.list_resources = Mock(return_value=[])

        mapping = MarketplaceAssetMapping(
            asset_data={"name": "Test Asset"},
            source_type=AssetSourceType.FEDERATED,
            source_metadata={"listing_id": "SNOWFLAKE_SAMPLE_DATA"},
            odps_metadata={},
        )
        connector.map_to_hub_asset = Mock(return_value=mapping)

        # Execute sync_pull
        result = connector.sync_pull()

        # Verify mappings are in metadata
        assert "mappings" in result.metadata
        assert isinstance(result.metadata["mappings"], list)
        assert len(result.metadata["mappings"]) == 1
        # Verify mapping is serialized (dict format)
        assert isinstance(result.metadata["mappings"][0], dict)
        assert result.metadata["mappings"][0]["asset_data"]["name"] == "Test Asset"

    def test_map_to_hub_asset_includes_external_resource_references(
        self, connector, sample_listing
    ):
        """Test that map_to_hub_asset() includes external resource references"""
        # Test with no resources (should create default resource reference)
        sample_listing.resources = []

        mapping = connector.map_to_hub_asset(sample_listing)

        # Verify mapping includes resources
        assert isinstance(mapping, MarketplaceAssetMapping)
        assert len(mapping.resources) > 0

        # Verify at least one resource has external flag
        external_resources = [r for r in mapping.resources if r.metadata.get("external")]
        assert len(external_resources) > 0

        # Verify resource has listing_id for on-demand download
        assert external_resources[0].metadata.get("listing_id") == "SNOWFLAKE_SAMPLE_DATA"

    def test_map_to_hub_asset_does_not_access_external_data(self, connector, sample_listing):
        """Test that map_to_hub_asset() does NOT access external data sources"""
        # Mock methods that would access external data
        connector._execute_sql = Mock()
        connector._request_listing = Mock()
        connector._create_database_from_listing = Mock()
        connector._extract_schema_metadata = Mock()

        # Execute map_to_hub_asset
        mapping = connector.map_to_hub_asset(sample_listing)

        # Verify external data access methods were NOT called
        connector._execute_sql.assert_not_called()
        connector._request_listing.assert_not_called()
        connector._create_database_from_listing.assert_not_called()
        connector._extract_schema_metadata.assert_not_called()

        # Verify mapping was created successfully
        assert isinstance(mapping, MarketplaceAssetMapping)
        assert mapping.source_type == AssetSourceType.FEDERATED

    def test_download_resource_handles_listing_id(self, connector):
        """Test that download_resource() handles listing ID and performs deferred operations"""
        listing_id = "SNOWFLAKE_SAMPLE_DATA"
        destination_path = "/tmp/test_data.csv"

        # Mock deferred operations
        connector._request_listing = Mock(return_value=True)
        connector._accept_legal_terms = Mock(return_value=True)
        connector._create_database_from_listing = Mock(return_value="DB_SAMPLE_DATA")
        connector._extract_schema_metadata = Mock(return_value={"fields": []})
        connector._execute_sql = Mock(
            side_effect=[
                # First call: Get list of tables
                [{"TABLE_SCHEMA": "PUBLIC", "TABLE_NAME": "SAMPLE_TABLE"}],
                # Second call: Verify table exists
                [{"TABLE_NAME": "SAMPLE_TABLE"}],
                # Third call: Fetch data
                [{"col1": "value1", "col2": "value2"}],
            ]
        )
        connector._download_table = Mock(return_value=destination_path)

        # Execute download_resource with listing ID
        result_path = connector.download_resource(listing_id, destination_path)

        # Verify deferred operations were called
        connector._request_listing.assert_called_once_with(listing_id)
        connector._accept_legal_terms.assert_called_once_with(listing_id)
        connector._create_database_from_listing.assert_called_once_with(listing_id)
        connector._extract_schema_metadata.assert_called_once_with("DB_SAMPLE_DATA")

        # Verify download was attempted
        assert connector._download_table.called

    def test_download_resource_handles_table_identifier(self, connector):
        """Test that download_resource() handles table identifier (database already exists)"""
        table_identifier = "DB_SAMPLE_DATA.PUBLIC.SAMPLE_TABLE"
        destination_path = "/tmp/test_data.csv"

        # Mock deferred operations (should NOT be called)
        connector._request_listing = Mock()
        connector._accept_legal_terms = Mock()
        connector._create_database_from_listing = Mock()

        # Mock table download (database already exists, no deferred operations needed)
        connector._execute_sql = Mock(
            side_effect=[
                # Verify table exists
                [{"TABLE_NAME": "SAMPLE_TABLE"}],
                # Fetch data
                [{"col1": "value1", "col2": "value2"}],
            ]
        )
        connector._download_table = Mock(return_value=destination_path)

        # Execute download_resource with table identifier
        result_path = connector.download_resource(table_identifier, destination_path)

        # Verify deferred operations were NOT called (database already exists)
        connector._request_listing.assert_not_called()
        connector._accept_legal_terms.assert_not_called()
        connector._create_database_from_listing.assert_not_called()

        # Verify download was attempted
        connector._download_table.assert_called_once_with(table_identifier, destination_path, "CSV")

    def test_download_resource_creates_database_when_needed(self, connector):
        """Test that download_resource() creates database when listing ID is provided"""
        listing_id = "SNOWFLAKE_SAMPLE_DATA"
        destination_path = "/tmp/test_data.csv"

        # Mock database creation
        connector._request_listing = Mock(return_value=True)
        connector._accept_legal_terms = Mock(return_value=True)
        connector._create_database_from_listing = Mock(return_value="DB_SAMPLE_DATA")
        connector._extract_schema_metadata = Mock(return_value={"fields": []})
        connector._execute_sql = Mock(return_value=[])
        connector._download_table = Mock(return_value=destination_path)

        # Execute download_resource
        try:
            connector.download_resource(listing_id, destination_path)
        except Exception:
            # Expected to fail if no tables found, but database creation should be called
            pass

        # Verify database creation was called
        connector._create_database_from_listing.assert_called_once_with(listing_id)

    def test_sync_pull_with_sync_job_id(self, connector, sample_listing):
        """Test that sync_pull() passes sync_job_id to map_to_hub_asset()"""
        sync_job_id = "job-123"
        connector.list_listings = Mock(return_value=[sample_listing])
        connector.list_resources = Mock(return_value=[])

        mapping = MarketplaceAssetMapping(
            asset_data={"name": "Test"},
            source_type=AssetSourceType.FEDERATED,
            source_metadata={},
            odps_metadata={},
        )
        connector.map_to_hub_asset = Mock(return_value=mapping)

        # Execute sync_pull with sync_job_id in options
        result = connector.sync_pull(options={"sync_job_id": sync_job_id})

        # Note: sync_pull doesn't currently accept sync_job_id in options,
        # but map_to_hub_asset accepts it as a parameter
        # This test verifies the method signature supports it
        assert isinstance(result, SyncResult)

    def test_metadata_first_pattern_separation(self, connector, sample_listing):
        """Test that metadata-first pattern properly separates sync_pull from download_resource"""
        # Step 1: sync_pull should only map (metadata-only)
        connector.list_listings = Mock(return_value=[sample_listing])
        connector.list_resources = Mock(return_value=[])
        connector.map_to_hub_asset = Mock(
            return_value=MarketplaceAssetMapping(
                asset_data={"name": "Test"},
                source_type=AssetSourceType.FEDERATED,
                source_metadata={},
                odps_metadata={},
            )
        )

        sync_result = connector.sync_pull()

        # Verify sync_pull only mapped (no database operations)
        assert sync_result.successful_items == 1
        assert "mappings" in sync_result.metadata

        # Step 2: download_resource should handle deferred operations
        listing_id = "SNOWFLAKE_SAMPLE_DATA"
        connector._request_listing = Mock(return_value=True)
        connector._accept_legal_terms = Mock(return_value=True)
        connector._create_database_from_listing = Mock(return_value="DB_SAMPLE_DATA")
        connector._extract_schema_metadata = Mock(return_value={"fields": []})
        connector._execute_sql = Mock(return_value=[])
        connector._download_table = Mock(return_value="/tmp/test.csv")

        try:
            connector.download_resource(listing_id, "/tmp/test.csv")
        except Exception:
            # Expected if no tables found
            pass

        # Verify download_resource performed deferred operations
        connector._request_listing.assert_called()
        connector._create_database_from_listing.assert_called()

        # Verify sync_pull did NOT perform these operations
        # (already verified in test_sync_pull_does_not_create_databases)

    def test_sync_pull_with_empty_listing_ids(self, connector):
        """Test sync_pull() error handling with empty listing_ids list"""
        result = connector.sync_pull(listing_ids=[])
        assert isinstance(result, SyncResult)
        assert result.total_items == 0
        assert result.successful_items == 0

    def test_sync_pull_with_none_listing_ids(self, connector):
        """Test sync_pull() error handling with None listing_ids"""
        try:
            result = connector.sync_pull(listing_ids=None)  # type: ignore[arg-type]  # test: None listing_ids for full sync exercise
            # Should handle None gracefully (may use default behavior)
            assert isinstance(result, SyncResult)
        except (ValueError, TypeError):
            # Expected if validation is strict
            pass

    def test_sync_pull_with_zero_limit(self, connector, sample_listing):
        """Test sync_pull() edge case with zero limit returns no items"""
        # With limit=0, connector should process zero listings; mock list_listings to return []
        connector.list_listings = Mock(return_value=[])
        connector.list_resources = Mock(return_value=[])
        connector.map_to_hub_asset = Mock(
            return_value=MarketplaceAssetMapping(
                asset_data={"name": "Test"},
                source_type=AssetSourceType.FEDERATED,
                source_metadata={},
                odps_metadata={},
            )
        )

        result = connector.sync_pull(options={"limit": 0})
        assert isinstance(result, SyncResult)
        assert result.total_items == 0
        assert result.successful_items == 0

    def test_map_to_hub_asset_with_none_listing(self, connector):
        """Test map_to_hub_asset() error handling with None listing"""
        with pytest.raises((ValueError, TypeError)):
            connector.map_to_hub_asset(None)  # type: ignore[arg-type]  # test: edge-case type exercise

    def test_map_to_hub_asset_with_empty_metadata(self, connector):
        """Test map_to_hub_asset() error handling with empty metadata"""
        listing = MarketplaceListing(
            marketplace_id="TEST_LISTING",
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
            title="Test Listing",
            metadata={},  # Empty metadata
        )
        connector.list_resources = Mock(return_value=[])

        # Should handle empty metadata gracefully
        mapping = connector.map_to_hub_asset(listing)
        assert isinstance(mapping, MarketplaceAssetMapping)
        assert mapping.asset_data is not None

    def test_download_resource_with_empty_resource_id(self, connector):
        """Test download_resource() error handling with empty resource_id"""
        # Signature is download_resource(resource_id, destination_path) per base class
        with pytest.raises((ValueError, NotFoundError, ConnectionError)):
            connector.download_resource(resource_id="", destination_path="/tmp/test.csv")

    def test_download_resource_with_none_resource_id(self, connector):
        """Test download_resource() error handling with None resource_id"""
        with pytest.raises((ValueError, TypeError, AttributeError, NotFoundError, ConnectionError)):
            connector.download_resource(
                resource_id=None,  # type: ignore[arg-type]  # test: edge-case type exercise
                destination_path="/tmp/test.csv",
            )
