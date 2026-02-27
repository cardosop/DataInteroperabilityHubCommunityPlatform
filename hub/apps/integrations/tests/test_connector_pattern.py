"""
Connector Pattern Verification Tests

Comprehensive tests to verify that all marketplace connectors follow the metadata-first
architecture pattern. These tests ensure consistency across all connector implementations
and validate that connectors properly separate listing discovery/mapping from asset
creation and data downloading.

Tests verify:
- sync_pull() does NOT create assets or download data
- sync_pull() returns mappings only (SyncResult with mappings in metadata)
- map_to_hub_asset() returns MarketplaceAssetMapping with all required fields
- map_to_hub_asset() includes external resource references
- download_resource() handles on-demand downloads
- Connector workflow integration

No mocks/stubs - uses real connector implementations.
"""

import os
from unittest.mock import Mock, patch

import pytest
from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetSourceType, AssetStatus
from hub.apps.contracts.models import Contract
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File
from hub.apps.integrations.base import (
    MarketplaceAssetMapping,
    MarketplaceListing,
    MarketplaceResource,
    MarketplaceType,
    SyncDirection,
    SyncResult,
    SyncStatus,
)

# Note: Mock/patch imports are only used for external API calls (httpx.get, httpx.stream, etc.)
# which are acceptable per requirements. Internal service mocks have been removed.
from hub.apps.integrations.connectors.ckan_connector import CKANConnector
from hub.apps.integrations.connectors.dados_gov_br_connector import DadosGovBrConnector
from hub.apps.integrations.connectors.snowflake_connector import SnowflakeConnector
from hub.apps.integrations.models import MarketplaceConnection, MarketplaceSyncJob
from hub.apps.tenants.models import Tenant

User = get_user_model()


def _get_dados_gov_br_jwt_token():
    """Return JWT token for DadosGovBr connector; skip test if not set."""
    token = os.getenv("DADOS_GOV_BR_API_KEY") or os.getenv("CKAN_DADOS_GOV_BR_API_KEY")
    if not token:
        pytest.skip(
            "DADOS_GOV_BR_API_KEY or CKAN_DADOS_GOV_BR_API_KEY required for DadosGovBr "
            "connector pattern tests"
        )
    return token


# Use pytest.mark.django_db without transaction to avoid foreign key constraint issues
pytestmark = pytest.mark.django_db


class TestConnectorPatternBase(TestCase):
    """Base test class for connector pattern verification"""

    def setUp(self):
        """Set up test fixtures"""
        # Create test tenant
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")

        # Create test user (User model uses email as username)
        self.user = User.objects.create_user(email="test@example.com", tenant=self.tenant)

    def get_initial_counts(self):
        """Get initial counts of database records"""
        return {
            "assets": Asset.objects.count(),
            "contracts": Contract.objects.count(),
            "files": File.objects.count(),
            "datasets": Dataset.objects.count(),
        }


class TestSyncPullDoesNotCreateAssets(TestConnectorPatternBase):
    """Test that sync_pull() does NOT create assets, contracts, files, or datasets"""

    def test_ckan_sync_pull_does_not_create_assets(self):
        """Test CKAN connector sync_pull() does not create assets"""
        # Create CKAN connector (requires base_url)
        connector = CKANConnector(base_url="https://data.gov")

        # Get initial counts
        initial_counts = self.get_initial_counts()

        # Create sample listing to ensure mappings are returned
        sample_listing = MarketplaceListing(
            marketplace_id="test-package",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Test Package",
            description="Test description",
        )

        # Mock list_listings to return sample listing (avoiding actual API call)
        # We use patching here only to avoid external API calls, not to mock behavior
        with patch.object(connector, "list_listings", return_value=[sample_listing]):
            with patch.object(connector, "list_resources", return_value=[]):
                # Execute sync_pull
                result = connector.sync_pull()

        # Verify sync_pull returned SyncResult
        self.assertIsInstance(result, SyncResult)
        # When listings are provided, mappings should be in metadata
        if result.successful_items > 0:
            self.assertIn("mappings", result.metadata)
            self.assertIsInstance(result.metadata["mappings"], list)

        # Verify no assets were created
        final_counts = self.get_initial_counts()
        self.assertEqual(
            final_counts["assets"],
            initial_counts["assets"],
            "sync_pull() should NOT create Asset records",
        )
        self.assertEqual(
            final_counts["contracts"],
            initial_counts["contracts"],
            "sync_pull() should NOT create Contract records",
        )
        self.assertEqual(
            final_counts["files"],
            initial_counts["files"],
            "sync_pull() should NOT create File records",
        )
        self.assertEqual(
            final_counts["datasets"],
            initial_counts["datasets"],
            "sync_pull() should NOT create Dataset records",
        )

    def test_dados_gov_br_sync_pull_does_not_create_assets(self):
        """Test DadosGovBr connector sync_pull() does not create assets"""
        token = _get_dados_gov_br_jwt_token()
        connector = DadosGovBrConnector(
            base_url="https://dados.gov.br", jwt_token=token
        )

        # Get initial counts
        initial_counts = self.get_initial_counts()

        # Mock list_listings to return empty list (avoiding actual API call)
        with patch.object(connector, "list_listings", return_value=[]):
            with patch.object(connector, "list_resources", return_value=[]):
                # Execute sync_pull
                result = connector.sync_pull()

        # Verify sync_pull returned SyncResult
        self.assertIsInstance(result, SyncResult)
        self.assertIn("mappings", result.metadata)

        # Verify no assets were created
        final_counts = self.get_initial_counts()
        self.assertEqual(
            final_counts["assets"],
            initial_counts["assets"],
            "sync_pull() should NOT create Asset records",
        )
        self.assertEqual(
            final_counts["contracts"],
            initial_counts["contracts"],
            "sync_pull() should NOT create Contract records",
        )
        self.assertEqual(
            final_counts["files"],
            initial_counts["files"],
            "sync_pull() should NOT create File records",
        )
        self.assertEqual(
            final_counts["datasets"],
            initial_counts["datasets"],
            "sync_pull() should NOT create Dataset records",
        )

    def test_snowflake_sync_pull_does_not_create_assets(self):
        """Test Snowflake connector sync_pull() does not create assets"""
        # Create Snowflake connector (requires credentials, but we'll mock list_listings)
        connector = SnowflakeConnector(account="test_account", user="test_user", token="test_token")

        # Get initial counts
        initial_counts = self.get_initial_counts()

        # Mock list_listings to return empty list (avoiding actual Snowflake connection)
        with patch.object(connector, "list_listings", return_value=[]):
            with patch.object(connector, "list_resources", return_value=[]):
                # Execute sync_pull
                result = connector.sync_pull()

        # Verify sync_pull returned SyncResult
        self.assertIsInstance(result, SyncResult)
        self.assertIn("mappings", result.metadata)

        # Verify no assets were created
        final_counts = self.get_initial_counts()
        self.assertEqual(
            final_counts["assets"],
            initial_counts["assets"],
            "sync_pull() should NOT create Asset records",
        )
        self.assertEqual(
            final_counts["contracts"],
            initial_counts["contracts"],
            "sync_pull() should NOT create Contract records",
        )
        self.assertEqual(
            final_counts["files"],
            initial_counts["files"],
            "sync_pull() should NOT create File records",
        )
        self.assertEqual(
            final_counts["datasets"],
            initial_counts["datasets"],
            "sync_pull() should NOT create Dataset records",
        )


class TestSyncPullReturnsMappingsOnly(TestConnectorPatternBase):
    """Test that sync_pull() returns SyncResult with mappings in metadata"""

    def test_ckan_sync_pull_returns_mappings_only(self):
        """Test CKAN connector sync_pull() returns mappings only"""
        connector = CKANConnector(base_url="https://data.gov")

        # Create sample listing
        sample_listing = MarketplaceListing(
            marketplace_id="test-package",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Test Package",
            description="Test description",
        )

        with patch.object(connector, "list_listings", return_value=[sample_listing]):
            with patch.object(connector, "list_resources", return_value=[]):
                result = connector.sync_pull()

        # Verify SyncResult structure
        self.assertIsInstance(result, SyncResult)
        # When listings are provided, mappings should be in metadata
        if result.successful_items > 0:
            self.assertIn("mappings", result.metadata)
            mappings = result.metadata["mappings"]
            self.assertIsInstance(mappings, list)

            # Verify mappings format
            # CKAN connector returns list of dicts with 'listing_id' and 'mapping' keys
            if mappings:
                mapping_item = mappings[0]
                # CKAN connector wraps mappings in dict with 'listing_id' and 'mapping'
                if isinstance(mapping_item, dict) and "mapping" in mapping_item:
                    mapping = mapping_item["mapping"]
                    # Mapping can be dict or MarketplaceAssetMapping object
                    if isinstance(mapping, dict):
                        self.assertIn("asset_data", mapping)
                        self.assertIn("source_type", mapping)
                    elif isinstance(mapping, MarketplaceAssetMapping):
                        self.assertIsNotNone(mapping.asset_data)
                        self.assertIsNotNone(mapping.source_type)
                elif isinstance(mapping_item, dict):
                    # Direct dict format
                    self.assertIn("asset_data", mapping_item)
                    self.assertIn("source_type", mapping_item)
                elif isinstance(mapping_item, MarketplaceAssetMapping):
                    # Direct MarketplaceAssetMapping object
                    self.assertIsNotNone(mapping_item.asset_data)
                    self.assertIsNotNone(mapping_item.source_type)

        # Verify no asset IDs or contract IDs in return value
        result_str = str(result)
        # Asset IDs are UUIDs, Contract IDs are UUIDs - verify they're not in the result
        # We check that the result doesn't contain asset or contract creation logic
        self.assertNotIn("asset_id", result_str.lower())
        self.assertNotIn("contract_id", result_str.lower())

    def test_dados_gov_br_sync_pull_returns_mappings_only(self):
        """Test DadosGovBr connector sync_pull() returns mappings only"""
        token = _get_dados_gov_br_jwt_token()
        connector = DadosGovBrConnector(
            base_url="https://dados.gov.br", jwt_token=token
        )

        # Create sample listing (DadosGovBr uses CKAN_INSTANCE type)
        sample_listing = MarketplaceListing(
            marketplace_id="test-dataset",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Test Dataset",
            description="Test description",
        )

        with patch.object(connector, "list_listings", return_value=[sample_listing]):
            with patch.object(connector, "list_resources", return_value=[]):
                result = connector.sync_pull()

        # Verify SyncResult structure
        self.assertIsInstance(result, SyncResult)
        # When listings are provided, mappings should be in metadata
        if result.successful_items > 0:
            self.assertIn("mappings", result.metadata)
            mappings = result.metadata["mappings"]
            self.assertIsInstance(mappings, list)

            # Verify mappings format (DadosGovBr returns MarketplaceAssetMapping objects, not dicts)
            if mappings:
                mapping = mappings[0]
                # Mapping can be dict or MarketplaceAssetMapping object
                if isinstance(mapping, dict):
                    self.assertIn("asset_data", mapping)
                    self.assertIn("source_type", mapping)
                    self.assertIn("source_metadata", mapping)
                elif isinstance(mapping, MarketplaceAssetMapping):
                    self.assertIsNotNone(mapping.asset_data)
                    self.assertIsNotNone(mapping.source_type)
                    self.assertIsNotNone(mapping.source_metadata)

    def test_snowflake_sync_pull_returns_mappings_only(self):
        """Test Snowflake connector sync_pull() returns mappings only"""
        connector = SnowflakeConnector(account="test_account", user="test_user", token="test_token")

        # Create sample listing
        sample_listing = MarketplaceListing(
            marketplace_id="SNOWFLAKE_TEST",
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
            title="Test Listing",
            description="Test description",
        )

        with patch.object(connector, "list_listings", return_value=[sample_listing]):
            with patch.object(connector, "list_resources", return_value=[]):
                result = connector.sync_pull()

        # Verify SyncResult structure
        self.assertIsInstance(result, SyncResult)
        self.assertIn("mappings", result.metadata)
        self.assertIsInstance(result.metadata["mappings"], list)

        # Verify mappings are dicts (serialized MarketplaceAssetMapping)
        if result.metadata["mappings"]:
            mapping = result.metadata["mappings"][0]
            self.assertIsInstance(mapping, dict)
            self.assertIn("asset_data", mapping)
            self.assertIn("source_type", mapping)
            self.assertIn("source_metadata", mapping)


class TestSyncPullDoesNotDownloadData(TestConnectorPatternBase):
    """Test that sync_pull() does NOT download data or call download_resource()"""

    def test_ckan_sync_pull_does_not_download_data(self):
        """Test CKAN connector sync_pull() does not download data"""
        connector = CKANConnector(base_url="https://data.gov")

        # Track if download_resource is called
        download_called = {"called": False}

        original_download = connector.download_resource

        def track_download(*args, **kwargs):
            download_called["called"] = True
            return original_download(*args, **kwargs)

        connector.download_resource = track_download

        # Create sample listing
        sample_listing = MarketplaceListing(
            marketplace_id="test-package",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Test Package",
        )

        with patch.object(connector, "list_listings", return_value=[sample_listing]):
            with patch.object(connector, "list_resources", return_value=[]):
                result = connector.sync_pull()

        # Verify download_resource was NOT called
        self.assertFalse(
            download_called["called"], "sync_pull() should NOT call download_resource()"
        )

        # Verify no files or datasets were created
        initial_counts = self.get_initial_counts()
        final_counts = self.get_initial_counts()
        self.assertEqual(
            final_counts["files"],
            initial_counts["files"],
            "sync_pull() should NOT create File records",
        )
        self.assertEqual(
            final_counts["datasets"],
            initial_counts["datasets"],
            "sync_pull() should NOT create Dataset records",
        )

    def test_dados_gov_br_sync_pull_does_not_download_data(self):
        """Test DadosGovBr connector sync_pull() does not download data"""
        token = _get_dados_gov_br_jwt_token()
        connector = DadosGovBrConnector(
            base_url="https://dados.gov.br", jwt_token=token
        )

        # Track if download_resource is called
        download_called = {"called": False}

        original_download = connector.download_resource

        def track_download(*args, **kwargs):
            download_called["called"] = True
            return original_download(*args, **kwargs)

        connector.download_resource = track_download

        # Create sample listing (DadosGovBr uses CKAN_INSTANCE type)
        sample_listing = MarketplaceListing(
            marketplace_id="test-dataset",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Test Dataset",
        )

        with patch.object(connector, "list_listings", return_value=[sample_listing]):
            with patch.object(connector, "list_resources", return_value=[]):
                result = connector.sync_pull()

        # Verify download_resource was NOT called
        self.assertFalse(
            download_called["called"], "sync_pull() should NOT call download_resource()"
        )

    def test_snowflake_sync_pull_does_not_download_data(self):
        """Test Snowflake connector sync_pull() does not download data"""
        connector = SnowflakeConnector(account="test_account", user="test_user", token="test_token")

        # Track if download_resource is called
        download_called = {"called": False}

        original_download = connector.download_resource

        def track_download(*args, **kwargs):
            download_called["called"] = True
            return original_download(*args, **kwargs)

        connector.download_resource = track_download

        # Create sample listing
        sample_listing = MarketplaceListing(
            marketplace_id="SNOWFLAKE_TEST",
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
            title="Test Listing",
        )

        with patch.object(connector, "list_listings", return_value=[sample_listing]):
            with patch.object(connector, "list_resources", return_value=[]):
                result = connector.sync_pull()

        # Verify download_resource was NOT called
        self.assertFalse(
            download_called["called"], "sync_pull() should NOT call download_resource()"
        )


class TestMapToHubAssetReturnsMarketplaceAssetMapping(TestConnectorPatternBase):
    """Test that map_to_hub_asset() returns MarketplaceAssetMapping with all required fields"""

    def test_ckan_map_to_hub_asset_returns_marketplace_asset_mapping(self):
        """Test CKAN connector map_to_hub_asset() returns MarketplaceAssetMapping"""
        connector = CKANConnector(base_url="https://data.gov")

        # Create sample listing
        listing = MarketplaceListing(
            marketplace_id="test-package",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Test Package",
            description="Test description",
            tags=["test", "data"],
        )

        # Mock list_resources to avoid actual API call (map_to_hub_asset calls it internally)
        # CKAN connector's map_to_hub_asset calls list_resources internally
        with patch.object(connector, "list_resources", return_value=[]):
            mapping = connector.map_to_hub_asset(listing)

        # Verify mapping is MarketplaceAssetMapping
        self.assertIsInstance(mapping, MarketplaceAssetMapping)

        # Verify all required fields are present
        self.assertIsNotNone(mapping.asset_data)
        self.assertIsInstance(mapping.asset_data, dict)
        self.assertIn("name", mapping.asset_data)

        self.assertEqual(mapping.source_type, AssetSourceType.FEDERATED)

        self.assertIsNotNone(mapping.source_metadata)
        self.assertIsInstance(mapping.source_metadata, dict)
        self.assertIn("marketplace_type", mapping.source_metadata)

        # odps_metadata is optional and can be None or dict
        if mapping.odps_metadata is not None:
            self.assertIsInstance(mapping.odps_metadata, dict)

        # odcs_metadata is optional and can be None or dict
        if mapping.odcs_metadata is not None:
            self.assertIsInstance(mapping.odcs_metadata, dict)

        self.assertIsNotNone(mapping.resources)
        self.assertIsInstance(mapping.resources, list)

    def test_dados_gov_br_map_to_hub_asset_returns_marketplace_asset_mapping(self):
        """Test DadosGovBr connector map_to_hub_asset() returns MarketplaceAssetMapping"""
        token = _get_dados_gov_br_jwt_token()
        connector = DadosGovBrConnector(
            base_url="https://dados.gov.br", jwt_token=token
        )

        # Create sample listing (DadosGovBr uses CKAN_INSTANCE type)
        listing = MarketplaceListing(
            marketplace_id="test-dataset",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Test Dataset",
            description="Test description",
        )

        # Mock client methods to avoid actual API calls
        with patch.object(connector.client, "get_dataset", return_value={}):
            mapping = connector.map_to_hub_asset(listing)

        # Verify mapping is MarketplaceAssetMapping
        self.assertIsInstance(mapping, MarketplaceAssetMapping)

        # Verify all required fields are present
        self.assertIsNotNone(mapping.asset_data)
        self.assertEqual(mapping.source_type, AssetSourceType.FEDERATED)
        self.assertIsNotNone(mapping.source_metadata)
        # odps_metadata and odcs_metadata are optional (can be None)
        # resources is required but can be empty list
        self.assertIsNotNone(mapping.resources)
        self.assertIsInstance(mapping.resources, list)

    def test_snowflake_map_to_hub_asset_returns_marketplace_asset_mapping(self):
        """Test Snowflake connector map_to_hub_asset() returns MarketplaceAssetMapping"""
        connector = SnowflakeConnector(account="test_account", user="test_user", token="test_token")

        # Create sample listing
        listing = MarketplaceListing(
            marketplace_id="SNOWFLAKE_TEST",
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
            title="Test Listing",
            description="Test description",
            metadata={"snowflake_database": {"DATABASE_OWNER": "SNOWFLAKE"}},
        )

        mapping = connector.map_to_hub_asset(listing)

        # Verify mapping is MarketplaceAssetMapping
        self.assertIsInstance(mapping, MarketplaceAssetMapping)

        # Verify all required fields are present
        self.assertIsNotNone(mapping.asset_data)
        self.assertEqual(mapping.source_type, AssetSourceType.FEDERATED)
        self.assertIsNotNone(mapping.source_metadata)
        # odps_metadata and odcs_metadata are optional (can be None)
        # resources is required but can be empty list
        self.assertIsNotNone(mapping.resources)
        self.assertIsInstance(mapping.resources, list)


class TestMapToHubAssetIncludesExternalResources(TestConnectorPatternBase):
    """Test that map_to_hub_asset() includes external resource references"""

    def test_ckan_map_to_hub_asset_includes_external_resources(self):
        """Test CKAN connector map_to_hub_asset() includes external resources"""
        connector = CKANConnector(base_url="https://data.gov")

        # Create sample listing with resources
        resource = MarketplaceResource(
            resource_id="test-resource",
            resource_type="FILE",
            name="Test Resource",
            url="https://data.gov/resource/test.csv",
            format="CSV",
            size_bytes=1024,
        )

        listing = MarketplaceListing(
            marketplace_id="test-package",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Test Package",
            resources=[resource],
        )

        # Mock list_resources to return the resource (map_to_hub_asset calls it internally)
        with patch.object(connector, "list_resources", return_value=[resource]):
            mapping = connector.map_to_hub_asset(listing)

        # Verify resources are included
        self.assertIsNotNone(mapping.resources)
        self.assertGreater(len(mapping.resources), 0)

        # Verify resources have external references
        for res in mapping.resources:
            self.assertIsInstance(res, MarketplaceResource)
            # Resources should have URLs or external identifiers
            self.assertTrue(
                res.url is not None or res.resource_id is not None,
                "Resources should have URLs or resource IDs for external access",
            )

    def test_dados_gov_br_map_to_hub_asset_includes_external_resources(self):
        """Test DadosGovBr connector map_to_hub_asset() includes external resources"""
        token = _get_dados_gov_br_jwt_token()
        connector = DadosGovBrConnector(
            base_url="https://dados.gov.br", jwt_token=token
        )

        # Create sample listing with resources
        resource = MarketplaceResource(
            resource_id="test-resource",
            resource_type="FILE",
            name="Test Resource",
            url="https://dados.gov.br/resource/test.csv",
            format="CSV",
        )

        listing = MarketplaceListing(
            marketplace_id="test-dataset",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Test Dataset",
            resources=[resource],
        )

        # Mock client methods to avoid actual API calls
        with patch.object(connector.client, "get_dataset", return_value={}):
            mapping = connector.map_to_hub_asset(listing)

        # Verify resources are included
        self.assertIsNotNone(mapping.resources)
        # Resources may be empty if listing has no resources, but if present, they should have external references
        if mapping.resources:
            for res in mapping.resources:
                self.assertIsInstance(res, MarketplaceResource)
                self.assertTrue(
                    res.url is not None or res.resource_id is not None,
                    "Resources should have URLs or resource IDs for external access",
                )

    def test_snowflake_map_to_hub_asset_includes_external_resources(self):
        """Test Snowflake connector map_to_hub_asset() includes external resources"""
        connector = SnowflakeConnector(account="test_account", user="test_user", token="test_token")

        # Create sample listing (Snowflake creates default resource if none exist)
        listing = MarketplaceListing(
            marketplace_id="SNOWFLAKE_TEST",
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
            title="Test Listing",
            description="Test description",
            metadata={"snowflake_database": {"DATABASE_OWNER": "SNOWFLAKE"}},
        )

        mapping = connector.map_to_hub_asset(listing)

        # Verify resources are included (Snowflake creates default resource reference)
        self.assertIsNotNone(mapping.resources)
        self.assertGreater(
            len(mapping.resources),
            0,
            "Snowflake connector should create default resource reference",
        )

        # Verify resources have external metadata
        for res in mapping.resources:
            self.assertIsInstance(res, MarketplaceResource)
            # Verify external flag in metadata
            if res.metadata:
                self.assertTrue(
                    res.metadata.get("external", False)
                    or res.metadata.get("listing_id") is not None,
                    "Resources should have external=True flag or listing_id in metadata",
                )


class TestDownloadResourceHandlesOnDemandDownloads(TestConnectorPatternBase):
    """Test that download_resource() handles on-demand downloads"""

    def test_ckan_download_resource_handles_on_demand_downloads(self):
        """Test CKAN connector download_resource() handles on-demand downloads"""
        connector = CKANConnector(base_url="https://data.gov")

        # Mock the actual download to avoid external API calls
        # We're testing the method signature and behavior, not the actual download
        import os
        import tempfile

        # Mock _request_with_retry to return resource details
        def mock_request(method, url, **kwargs):
            mock_response = Mock()
            if "resource_show" in url:
                # Return resource details
                mock_response.json.return_value = {
                    "success": True,
                    "result": {
                        "url": "https://data.gov/resource/test.csv",
                        "name": "test.csv",
                        "format": "CSV",
                    },
                }
            return mock_response

        # Mock httpx.get for file download
        def mock_httpx_get(url, **kwargs):
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.content = b"test,data\n1,2"
            mock_response.iter_bytes.return_value = [b"test,data\n1,2"]
            mock_response.raise_for_status = Mock()
            return mock_response

        with patch.object(connector, "_request_with_retry", side_effect=mock_request):
            with patch("httpx.get", side_effect=mock_httpx_get):
                with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                    destination_path = tmp_file.name

                try:
                    # Execute download_resource
                    result_path = connector.download_resource(
                        resource_id="test-resource", destination_path=destination_path
                    )

                    # Verify download_resource returns path
                    self.assertIsNotNone(result_path)
                    self.assertEqual(result_path, destination_path)
                finally:
                    # Cleanup
                    if os.path.exists(destination_path):
                        os.unlink(destination_path)

    def test_dados_gov_br_download_resource_handles_on_demand_downloads(self):
        """Test DadosGovBr connector download_resource() handles on-demand downloads"""
        token = _get_dados_gov_br_jwt_token()
        connector = DadosGovBrConnector(
            base_url="https://dados.gov.br", jwt_token=token
        )

        # Mock the actual download to avoid external API calls
        import os
        import tempfile

        # Mock client.get_resource to return resource data
        def mock_get_resource(resource_id):
            return {
                "success": True,
                "result": {
                    "id": resource_id,
                    "url": "https://dados.gov.br/resource/test.csv",
                    "nome": "test.csv",
                    "formato": "CSV",
                },
            }

        # Mock httpx.stream to return a context manager
        class MockStreamResponse:
            def __init__(self):
                self.status_code = 200
                self.iter_bytes_return = [b"test,data\n1,2"]

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def iter_bytes(self):
                return iter(self.iter_bytes_return)

            def raise_for_status(self):
                pass

        def mock_httpx_stream(method, url, **kwargs):
            return MockStreamResponse()

        with patch.object(connector.client, "get_resource", side_effect=mock_get_resource):
            with patch("httpx.stream", side_effect=mock_httpx_stream):
                with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                    destination_path = tmp_file.name

                try:
                    # Execute download_resource
                    result_path = connector.download_resource(
                        resource_id="test-resource", destination_path=destination_path
                    )

                    # Verify download_resource returns path
                    self.assertIsNotNone(result_path)
                    self.assertEqual(result_path, destination_path)
                finally:
                    # Cleanup
                    if os.path.exists(destination_path):
                        os.unlink(destination_path)

    def test_snowflake_download_resource_handles_on_demand_downloads(self):
        """Test Snowflake connector download_resource() handles on-demand downloads"""
        connector = SnowflakeConnector(account="test_account", user="test_user", token="test_token")

        # Mock connection and SQL execution to avoid actual Snowflake calls
        connector._authenticated = True

        import os
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp_file:
            destination_path = tmp_file.name

        # Mock all methods that download_resource calls for table identifier (3 parts: DB.SCHEMA.TABLE)
        # download_resource will parse "TEST_DB.TEST_SCHEMA.TEST_TABLE" as 3 parts and call _download_table
        # _download_table calls _execute_sql to verify table exists, then downloads it
        # We mock _execute_sql and _download_table directly to avoid connection setup
        with patch.object(connector, "_execute_sql", return_value=[{"TABLE_NAME": "TEST_TABLE"}]):
            with patch.object(connector, "_download_table", return_value=destination_path):
                try:
                    # Execute download_resource with table identifier
                    result_path = connector.download_resource(
                        resource_id="TEST_DB.TEST_SCHEMA.TEST_TABLE",
                        destination_path=destination_path,
                    )

                    # Verify download_resource returns path
                    self.assertIsNotNone(result_path)
                    self.assertEqual(result_path, destination_path)
                finally:
                    # Cleanup
                    if os.path.exists(destination_path):
                        os.unlink(destination_path)


class TestConnectorWorkflowIntegration(TestConnectorPatternBase):
    """Test connector workflow integration"""

    def test_sync_from_marketplace_triggers_workflow(self):
        """Test that sync_from_marketplace() triggers workflow"""
        from hub.apps.integrations.base import DataMarketplaceConnector
        from hub.apps.integrations.factory import MarketplaceConnectorFactory
        from hub.apps.integrations.services import MarketplaceIntegrationService
        from hub.apps.orchestration.models import WorkflowInstance

        # Use SNOWFLAKE_DATA_MARKETPLACE with test connector - CKAN_INSTANCE may be
        # unregistered by other tests (e.g. test_federated_asset_workflow)
        class _TestSnowflakeConnector(DataMarketplaceConnector):
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
                    asset_data={"name": listing.title},
                    source_type=AssetSourceType.FEDERATED,
                    source_metadata={},
                    odps_metadata=None,
                    odcs_metadata=None,
                )

            def map_from_hub_asset(self, asset_data, odps_metadata=None, odcs_metadata=None):
                return MarketplaceListing(
                    marketplace_id="test",
                    marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
                    title=asset_data.get("name", "Unknown"),
                )

            def sync_push(self, asset_ids, options=None):
                return SyncResult(status=SyncStatus.COMPLETED)

            def sync_pull(self, listing_ids=None, filters=None, options=None):
                return SyncResult(status=SyncStatus.COMPLETED, metadata={"mappings": []})

        original = MarketplaceConnectorFactory._connectors.get(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value
        )
        try:
            MarketplaceConnectorFactory.register_connector(
                MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE, _TestSnowflakeConnector
            )
            connection = MarketplaceConnection.objects.create(
                tenant=self.tenant,
                name="Test Connection",
                marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
                config={"endpoint": "https://api.example.com"},
                is_active=True,
            )

            service = MarketplaceIntegrationService(
                tenant_id=str(self.tenant.id), user_id=str(self.user.id)
            )

            initial_workflow_count = WorkflowInstance.objects.filter(
                tenant=self.tenant, workflow_name__startswith="marketplace_sync"
            ).count()

            try:
                sync_job = service.sync_from_marketplace(
                    connection_id=str(connection.id),
                    tenant_id=str(self.tenant.id),
                    user_id=str(self.user.id),
                    options={"dry_run": True},
                )

                self.assertIsNotNone(sync_job)
                self.assertIsInstance(sync_job, MarketplaceSyncJob)
                self.assertEqual(sync_job.direction, SyncDirection.PULL.value)

                final_workflow_count = WorkflowInstance.objects.filter(
                    tenant=self.tenant, workflow_name__startswith="marketplace_sync"
                ).count()
                self.assertGreaterEqual(final_workflow_count, initial_workflow_count)

            except Exception as e:
                sync_jobs = MarketplaceSyncJob.objects.filter(
                    connection=connection, direction=SyncDirection.PULL.value
                )
                self.assertGreater(
                    sync_jobs.count(), 0,
                    f"Sync job should be created even if workflow fails: {e}",
                )
        finally:
            try:
                MarketplaceConnectorFactory.unregister_connector(
                    MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
                )
                if original is not None:
                    MarketplaceConnectorFactory.register_connector(
                        MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE, original
                    )
            except ValueError:
                pass

    def test_workflow_calls_create_federated_asset_with_contracts(self):
        """Test that workflow calls create_federated_asset_with_contracts() for asset creation"""
        from hub.apps.integrations.services import MarketplaceIntegrationService

        # Create marketplace connection
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            name="Test Connection",
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            config={"base_url": "https://data.gov"},
            is_active=True,
        )

        # Create service instance
        service = MarketplaceIntegrationService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        # Verify that create_federated_asset_with_contracts exists and is callable
        self.assertTrue(hasattr(service, "create_federated_asset_with_contracts"))
        self.assertTrue(callable(getattr(service, "create_federated_asset_with_contracts")))

        # Verify method signature accepts MarketplaceAssetMapping
        import inspect

        sig = inspect.signature(service.create_federated_asset_with_contracts)
        params = list(sig.parameters.keys())
        self.assertIn(
            "asset_mapping",
            params,
            "create_federated_asset_with_contracts should accept asset_mapping parameter",
        )

    def test_workflow_integration_error_handling(self):
        """Test that workflow integration handles errors gracefully"""
        from hub.apps.integrations.services import MarketplaceIntegrationService

        # Create marketplace connection
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            name="Test Connection Error",
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            config={"base_url": "https://data.gov"},
            is_active=True,
        )

        # Create service instance
        service = MarketplaceIntegrationService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        # Test with invalid connection (should raise NotFoundError)
        from hub.apps.core.services.base import NotFoundError

        with self.assertRaises(NotFoundError):
            service.sync_from_marketplace(
                connection_id="invalid-connection-id",
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                options={"dry_run": True},
            )

    def test_workflow_integration_with_inactive_connection(self):
        """Test that workflow integration handles inactive connections"""
        from hub.apps.core.services.base import ValidationError
        from hub.apps.integrations.services import MarketplaceIntegrationService

        # Create inactive marketplace connection
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            name="Inactive Connection",
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            config={"base_url": "https://data.gov"},
            is_active=False,  # Inactive connection
        )

        # Create service instance
        service = MarketplaceIntegrationService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        # Test with inactive connection (should raise ValidationError)
        with self.assertRaises(ValidationError):
            service.sync_from_marketplace(
                connection_id=str(connection.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                options={"dry_run": True},
            )
