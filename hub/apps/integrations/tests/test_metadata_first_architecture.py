"""
Tests for Metadata-First Architecture Pattern Documentation and Validation

Comprehensive tests to validate that the base connector class properly documents
and enforces the metadata-first architecture pattern for marketplace connectors.

These tests ensure:
1. All abstract methods have comprehensive docstrings
2. Documentation clearly explains metadata-first behavior
3. Connectors follow the correct pattern (discovery → mapping → workflow → download)
4. Documentation includes examples and workflow integration details
"""

import inspect

from hub.apps.assets.models import AssetSourceType
from hub.apps.integrations.base import (
    DataMarketplaceConnector,
    MarketplaceAssetMapping,
    MarketplaceListing,
    MarketplaceType,
    SyncDirection,
    SyncResult,
    SyncStatus,
)


class TestMetadataFirstArchitectureDocumentation:
    """Test that metadata-first architecture is properly documented"""

    def test_class_docstring_exists(self):
        """Test that DataMarketplaceConnector class has comprehensive docstring"""
        docstring = inspect.getdoc(DataMarketplaceConnector)
        assert docstring is not None, "DataMarketplaceConnector class must have a docstring"
        assert len(docstring) > 500, "Docstring should be comprehensive (at least 500 characters)"

    def test_class_docstring_mentions_metadata_first(self):
        """Test that class docstring mentions metadata-first architecture"""
        docstring = inspect.getdoc(DataMarketplaceConnector)
        assert "metadata-first" in docstring.lower(), (
            "Class docstring must mention metadata-first architecture"
        )

    def test_class_docstring_explains_connector_responsibilities(self):
        """Test that class docstring explains connector responsibilities"""
        docstring = inspect.getdoc(DataMarketplaceConnector)
        assert "discovery" in docstring.lower() or "discover" in docstring.lower(), (
            "Docstring should explain discovery responsibility"
        )
        assert "mapping" in docstring.lower() or "map" in docstring.lower(), (
            "Docstring should explain mapping responsibility"
        )
        assert "harvest" in docstring.lower() or "sync_pull" in docstring.lower(), (
            "Docstring should explain harvest/sync_pull responsibility"
        )
        assert "download" in docstring.lower(), "Docstring should explain download responsibility"

    def test_class_docstring_explains_what_connectors_must_not_do(self):
        """Test that class docstring explains what connectors MUST NOT do"""
        docstring = inspect.getdoc(DataMarketplaceConnector)
        assert "must not" in docstring.lower() or "does not" in docstring.lower(), (
            "Docstring should explain what connectors must NOT do"
        )
        assert "create assets" in docstring.lower(), (
            "Docstring should state that connectors must NOT create assets"
        )
        assert (
            "download data" in docstring.lower() or "download in sync_pull" in docstring.lower()
        ), "Docstring should state that connectors must NOT download data in sync_pull"

    def test_class_docstring_explains_workflow_integration(self):
        """Test that class docstring explains workflow integration"""
        docstring = inspect.getdoc(DataMarketplaceConnector)
        assert "workflow" in docstring.lower(), "Docstring should explain workflow integration"

    def test_class_docstring_explains_metadata_first_benefits(self):
        """Test that class docstring explains metadata-first benefits"""
        docstring = inspect.getdoc(DataMarketplaceConnector)
        assert (
            "benefit" in docstring.lower()
            or "fast" in docstring.lower()
            or "scalability" in docstring.lower()
        ), "Docstring should explain metadata-first benefits"

    def test_class_docstring_mentions_reference_implementations(self):
        """Test that class docstring mentions reference implementations"""
        docstring = inspect.getdoc(DataMarketplaceConnector)
        assert "ckan" in docstring.lower() or "reference" in docstring.lower(), (
            "Docstring should mention reference implementations"
        )


class TestSyncPullDocumentation:
    """Test that sync_pull() method has comprehensive metadata-first documentation"""

    def test_sync_pull_docstring_exists(self):
        """Test that sync_pull() method has docstring"""
        docstring = inspect.getdoc(DataMarketplaceConnector.sync_pull)
        assert docstring is not None, "sync_pull() method must have a docstring"
        assert len(docstring) > 300, (
            "sync_pull() docstring should be comprehensive (at least 300 characters)"
        )

    def test_sync_pull_docstring_mentions_metadata_first(self):
        """Test that sync_pull() docstring mentions metadata-first pattern"""
        docstring = inspect.getdoc(DataMarketplaceConnector.sync_pull)
        assert "metadata-first" in docstring.lower(), (
            "sync_pull() docstring must mention metadata-first pattern"
        )

    def test_sync_pull_docstring_explains_what_it_does(self):
        """Test that sync_pull() docstring explains what it does"""
        docstring = inspect.getdoc(DataMarketplaceConnector.sync_pull)
        assert "discovers" in docstring.lower() or "discovers listings" in docstring.lower(), (
            "sync_pull() docstring should explain that it discovers listings"
        )
        assert "maps" in docstring.lower() or "mappings" in docstring.lower(), (
            "sync_pull() docstring should explain that it maps listings"
        )

    def test_sync_pull_docstring_explains_what_it_does_not_do(self):
        """Test that sync_pull() docstring explains what it does NOT do"""
        docstring = inspect.getdoc(DataMarketplaceConnector.sync_pull)
        assert "does not" in docstring.lower() or "doesn't" in docstring.lower(), (
            "sync_pull() docstring should explain what it does NOT do"
        )
        assert "create assets" in docstring.lower(), (
            "sync_pull() docstring should state it does NOT create assets"
        )
        assert "download data" in docstring.lower() or "download" in docstring.lower(), (
            "sync_pull() docstring should state it does NOT download data"
        )

    def test_sync_pull_docstring_explains_return_format(self):
        """Test that sync_pull() docstring explains return format"""
        docstring = inspect.getdoc(DataMarketplaceConnector.sync_pull)
        assert "syncresult" in docstring.lower(), (
            "sync_pull() docstring should mention SyncResult return type"
        )
        assert "mappings" in docstring.lower() or "metadata" in docstring.lower(), (
            "sync_pull() docstring should explain that mappings are in metadata"
        )

    def test_sync_pull_docstring_explains_workflow_integration(self):
        """Test that sync_pull() docstring explains workflow integration"""
        docstring = inspect.getdoc(DataMarketplaceConnector.sync_pull)
        assert "workflow" in docstring.lower(), (
            "sync_pull() docstring should explain workflow integration"
        )

    def test_sync_pull_docstring_includes_examples(self):
        """Test that sync_pull() docstring includes examples"""
        docstring = inspect.getdoc(DataMarketplaceConnector.sync_pull)
        assert "example" in docstring.lower() or "```" in docstring, (
            "sync_pull() docstring should include examples"
        )


class TestMapToHubAssetDocumentation:
    """Test that map_to_hub_asset() method has comprehensive metadata-first documentation"""

    def test_map_to_hub_asset_docstring_exists(self):
        """Test that map_to_hub_asset() method has docstring"""
        docstring = inspect.getdoc(DataMarketplaceConnector.map_to_hub_asset)
        assert docstring is not None, "map_to_hub_asset() method must have a docstring"
        assert len(docstring) > 400, (
            "map_to_hub_asset() docstring should be comprehensive (at least 400 characters)"
        )

    def test_map_to_hub_asset_docstring_mentions_metadata_first(self):
        """Test that map_to_hub_asset() docstring mentions metadata-first pattern"""
        docstring = inspect.getdoc(DataMarketplaceConnector.map_to_hub_asset)
        assert "metadata-first" in docstring.lower(), (
            "map_to_hub_asset() docstring must mention metadata-first pattern"
        )

    def test_map_to_hub_asset_docstring_explains_what_it_does(self):
        """Test that map_to_hub_asset() docstring explains what it does"""
        docstring = inspect.getdoc(DataMarketplaceConnector.map_to_hub_asset)
        assert "extracts" in docstring.lower() or "extract" in docstring.lower(), (
            "map_to_hub_asset() docstring should explain that it extracts metadata"
        )
        assert "marketplaceassetmapping" in docstring.lower() or "mapping" in docstring.lower(), (
            "map_to_hub_asset() docstring should mention MarketplaceAssetMapping"
        )

    def test_map_to_hub_asset_docstring_explains_what_it_does_not_do(self):
        """Test that map_to_hub_asset() docstring explains what it does NOT do"""
        docstring = inspect.getdoc(DataMarketplaceConnector.map_to_hub_asset)
        assert "does not" in docstring.lower() or "doesn't" in docstring.lower(), (
            "map_to_hub_asset() docstring should explain what it does NOT do"
        )
        assert "access external" in docstring.lower() or "external data" in docstring.lower(), (
            "map_to_hub_asset() docstring should state it does NOT access external data sources"
        )
        assert "download" in docstring.lower(), (
            "map_to_hub_asset() docstring should state it does NOT download data"
        )

    def test_map_to_hub_asset_docstring_explains_external_references(self):
        """Test that map_to_hub_asset() docstring explains external resource references"""
        docstring = inspect.getdoc(DataMarketplaceConnector.map_to_hub_asset)
        assert "external" in docstring.lower() or "reference" in docstring.lower(), (
            "map_to_hub_asset() docstring should explain external resource references"
        )

    def test_map_to_hub_asset_docstring_explains_return_format(self):
        """Test that map_to_hub_asset() docstring explains return format"""
        docstring = inspect.getdoc(DataMarketplaceConnector.map_to_hub_asset)
        assert "marketplaceassetmapping" in docstring.lower(), (
            "map_to_hub_asset() docstring should explain MarketplaceAssetMapping return type"
        )
        assert "asset_data" in docstring.lower(), (
            "map_to_hub_asset() docstring should explain asset_data field"
        )
        assert "source_metadata" in docstring.lower(), (
            "map_to_hub_asset() docstring should explain source_metadata field"
        )
        assert "resources" in docstring.lower(), (
            "map_to_hub_asset() docstring should explain resources field"
        )

    def test_map_to_hub_asset_docstring_includes_examples(self):
        """Test that map_to_hub_asset() docstring includes examples"""
        docstring = inspect.getdoc(DataMarketplaceConnector.map_to_hub_asset)
        assert "example" in docstring.lower() or "```" in docstring, (
            "map_to_hub_asset() docstring should include examples"
        )

    def test_map_to_hub_asset_signature_includes_sync_job_id(self):
        """Test that map_to_hub_asset() signature includes optional sync_job_id parameter"""
        sig = inspect.signature(DataMarketplaceConnector.map_to_hub_asset)
        assert "sync_job_id" in sig.parameters, (
            "map_to_hub_asset() should have sync_job_id parameter"
        )
        param = sig.parameters["sync_job_id"]
        # Check that parameter has a default value (even if None) - indicates it's optional
        assert param.default != inspect.Parameter.empty, (
            "sync_job_id parameter should have a default value (optional)"
        )
        # Verify the default is None (making it optional)
        assert param.default is None, "sync_job_id parameter default should be None (optional)"


class TestDownloadResourceDocumentation:
    """Test that download_resource() method has comprehensive on-demand download documentation"""

    def test_download_resource_docstring_exists(self):
        """Test that download_resource() method has docstring"""
        docstring = inspect.getdoc(DataMarketplaceConnector.download_resource)
        assert docstring is not None, "download_resource() method must have a docstring"
        assert len(docstring) > 400, (
            "download_resource() docstring should be comprehensive (at least 400 characters)"
        )

    def test_download_resource_docstring_mentions_on_demand(self):
        """Test that download_resource() docstring mentions on-demand behavior"""
        docstring = inspect.getdoc(DataMarketplaceConnector.download_resource)
        assert "on-demand" in docstring.lower() or "on demand" in docstring.lower(), (
            "download_resource() docstring must mention on-demand behavior"
        )

    def test_download_resource_docstring_explains_marketplace_operations(self):
        """Test that download_resource() docstring explains marketplace-specific operations"""
        docstring = inspect.getdoc(DataMarketplaceConnector.download_resource)
        assert "marketplace" in docstring.lower() or "specific" in docstring.lower(), (
            "download_resource() docstring should explain marketplace-specific operations"
        )
        assert (
            "database" in docstring.lower()
            or "subscribe" in docstring.lower()
            or "snowflake" in docstring.lower()
        ), (
            "download_resource() docstring should mention marketplace-specific operations (e.g., database creation, subscriptions)"
        )

    def test_download_resource_docstring_explains_when_called(self):
        """Test that download_resource() docstring explains when it is called"""
        docstring = inspect.getdoc(DataMarketplaceConnector.download_resource)
        assert "data_strategy" in docstring.lower() or "when" in docstring.lower(), (
            "download_resource() docstring should explain when it is called"
        )
        assert "metadata_only" in docstring.lower() or "metadata-only" in docstring.lower(), (
            "download_resource() docstring should mention METADATA_ONLY data strategy"
        )

    def test_download_resource_docstring_explains_workflow_integration(self):
        """Test that download_resource() docstring explains workflow integration"""
        docstring = inspect.getdoc(DataMarketplaceConnector.download_resource)
        assert "workflow" in docstring.lower(), (
            "download_resource() docstring should explain workflow integration"
        )

    def test_download_resource_docstring_includes_examples(self):
        """Test that download_resource() docstring includes examples"""
        docstring = inspect.getdoc(DataMarketplaceConnector.download_resource)
        assert "example" in docstring.lower() or "```" in docstring, (
            "download_resource() docstring should include examples"
        )
        assert "snowflake" in docstring.lower() or "aws" in docstring.lower(), (
            "download_resource() docstring should include marketplace-specific examples"
        )


class TestMetadataFirstPatternValidation:
    """Test that concrete implementations follow metadata-first pattern"""

    def test_complete_connector_implements_all_methods(self):
        """Test that a complete connector implementation has all required methods"""

        class CompleteConnector(DataMarketplaceConnector):
            @property
            def marketplace_type(self):
                return MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE

            @property
            def supported_sync_directions(self):
                return [SyncDirection.PULL]

            def authenticate(self, credentials):
                return True

            def test_connection(self):
                return True

            def list_listings(self, filters=None, limit=None, offset=None):
                return []

            def get_listing(self, listing_id):
                return MarketplaceListing(
                    marketplace_id=listing_id,
                    marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
                    title="Test",
                )

            def list_resources(self, listing_id):
                return []

            def create_listing(self, listing):
                return listing

            def update_listing(self, listing_id, listing):
                return listing

            def publish_resource(self, listing_id, resource):
                return resource

            def download_resource(self, resource_id, destination_path):
                return destination_path

            def map_to_hub_asset(self, listing, sync_job_id=None):
                return MarketplaceAssetMapping(
                    asset_data={"name": "Test"},
                    source_type=AssetSourceType.FEDERATED,
                    source_metadata={},
                    odps_metadata={},
                )

            def map_from_hub_asset(self, asset_data, odps_metadata=None, odcs_metadata=None):
                return MarketplaceListing(
                    marketplace_id="test",
                    marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
                    title="Test",
                )

            def sync_push(self, asset_ids, options=None):
                return SyncResult(status=SyncStatus.COMPLETED)

            def sync_pull(self, listing_ids=None, filters=None, options=None):
                # Metadata-first: Only map listings, don't create assets or download data
                listings = []
                if listing_ids:
                    listings = [self.get_listing(id) for id in listing_ids]
                else:
                    listings = self.list_listings(filters=filters)

                mappings = []
                for listing in listings:
                    mapping = self.map_to_hub_asset(listing)
                    mappings.append(mapping)

                return SyncResult(
                    status=SyncStatus.COMPLETED,
                    successful_items=len(mappings),
                    metadata={"mappings": [mapping.__dict__ for mapping in mappings]},
                )

        # Should be instantiable
        connector = CompleteConnector()

        # Test sync_pull returns mappings (metadata-first)
        result = connector.sync_pull()
        assert isinstance(result, SyncResult)
        assert "mappings" in result.metadata
        assert isinstance(result.metadata["mappings"], list)

        # Test map_to_hub_asset accepts optional sync_job_id
        listing = MarketplaceListing(
            marketplace_id="test-123",
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
            title="Test Listing",
        )
        mapping = connector.map_to_hub_asset(listing)
        assert isinstance(mapping, MarketplaceAssetMapping)

        mapping_with_job_id = connector.map_to_hub_asset(listing, sync_job_id="job-123")
        assert isinstance(mapping_with_job_id, MarketplaceAssetMapping)
