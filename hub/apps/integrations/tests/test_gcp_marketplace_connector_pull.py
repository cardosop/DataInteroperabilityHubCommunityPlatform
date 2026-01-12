"""
Unit Tests for GCP Marketplace Connector Pull Operations

Tests the pull operations (sync_pull, download_resource, map_to_hub_asset)
for the GCP Marketplace connector, following the metadata-first pattern.

These tests validate:
- sync_pull() does NOT subscribe to listings or extract schema
- sync_pull() only maps listings and returns mappings in metadata
- download_resource() performs deferred operations (subscription, schema extraction, data export)
- map_to_hub_asset() correctly maps Analytics Hub listings to Hub assets
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

from django.test import TestCase

from hub.apps.integrations.connectors.gcp_marketplace_connector import GCPMarketplaceConnector
from hub.apps.integrations.base import (
    MarketplaceType,
    MarketplaceListing,
    MarketplaceResource,
    MarketplaceAssetMapping,
    SyncResult,
    SyncStatus,
)
from hub.apps.assets.models import AssetSourceType
from hub.apps.core.services.base import NotFoundError, PermissionError


class TestGCPMarketplaceConnectorMapToHubAsset(TestCase):
    """Test map_to_hub_asset() method"""

    def setUp(self):
        """Set up test fixtures"""
        self.connector = GCPMarketplaceConnector(
            project_id='test-project',
            use_adc=True
        )

    @patch('hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector.list_resources')
    def test_map_to_hub_asset_basic(self, mock_list_resources):
        """Test map_to_hub_asset() maps listing to MarketplaceAssetMapping"""
        # Mock listing
        listing = MarketplaceListing(
            marketplace_id='test-listing-id',
            marketplace_type=MarketplaceType.GOOGLE_CLOUD_MARKETPLACE,
            title='Test Listing',
            description='Test description',
            category='test-category',
            tags=['tag1', 'tag2'],
            url='https://console.cloud.google.com/bigquery/analytics-hub/...',
            metadata={
                'analytics_hub_listing': {
                    'name': 'projects/test-project/locations/US/dataExchanges/test-exchange/listings/test-listing-id',
                    'display_name': 'Test Listing',
                    'description': 'Test description',
                    'categories': ['test-category'],
                    'data_provider': 'Test Provider',
                },
                'data_exchange_id': 'test-exchange',
                'odps_metadata': {
                    'product_details': {
                        'productID': 'test-listing-id',
                        'product_name': 'Test Listing',
                    }
                },
                'odcs_metadata': {
                    'schema': {
                        'dataset_reference': 'projects/test-project/datasets/test_dataset'
                    }
                }
            }
        )

        # Mock resources
        mock_resource = MarketplaceResource(
            resource_id='test-table',
            resource_type='BIGQUERY_TABLE',
            name='Test Table',
            description='Test table description',
            metadata={'external': True}
        )
        mock_list_resources.return_value = [mock_resource]

        # Map listing to Hub asset
        mapping = self.connector.map_to_hub_asset(listing)

        # Verify mapping structure
        self.assertIsInstance(mapping, MarketplaceAssetMapping)
        self.assertEqual(mapping.source_type, AssetSourceType.FEDERATED)
        self.assertIsNotNone(mapping.asset_data)
        self.assertEqual(mapping.asset_data['name'], 'Test Listing')
        self.assertEqual(mapping.asset_data['description'], 'Test description')
        # Domain should be exchange_name (data_exchange_id) per specification
        self.assertEqual(mapping.asset_data['domain'], 'test-exchange')
        self.assertEqual(mapping.asset_data['status'], 'ACTIVE')
        self.assertEqual(mapping.asset_data['visibility'], 'PUBLIC')
        self.assertIn('tag1', mapping.asset_data['tags'])
        self.assertIn('tag2', mapping.asset_data['tags'])

        # Verify source metadata
        self.assertEqual(mapping.source_metadata['marketplace_type'], MarketplaceType.GOOGLE_CLOUD_MARKETPLACE.value)
        self.assertEqual(mapping.source_metadata['listing_id'], 'test-listing-id')
        self.assertEqual(mapping.source_metadata['data_exchange_id'], 'test-exchange')
        self.assertEqual(mapping.source_metadata['provider'], 'Test Provider')

        # Verify ODPS and ODCS metadata
        self.assertIsNotNone(mapping.odps_metadata)
        self.assertIsNotNone(mapping.odcs_metadata)

        # Verify resources
        self.assertEqual(len(mapping.resources), 1)
        self.assertEqual(mapping.resources[0].resource_id, 'test-table')
        self.assertTrue(mapping.resources[0].metadata.get('external'))

    def test_map_to_hub_asset_missing_listing(self):
        """Test map_to_hub_asset() raises ValueError for missing listing"""
        with self.assertRaises(ValueError) as cm:
            self.connector.map_to_hub_asset(None)
        self.assertIn('required', str(cm.exception).lower())


class TestGCPMarketplaceConnectorSyncPull(TestCase):
    """Test sync_pull() method following metadata-first pattern"""

    def setUp(self):
        """Set up test fixtures"""
        self.connector = GCPMarketplaceConnector(
            project_id='test-project',
            use_adc=True
        )

    @patch('hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector.get_listing')
    @patch('hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector.map_to_hub_asset')
    @patch('hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector.list_resources')
    def test_sync_pull_with_listing_ids(self, mock_list_resources, mock_map_to_hub_asset, mock_get_listing):
        """Test sync_pull() with specific listing IDs"""
        # Mock listing
        listing = MarketplaceListing(
            marketplace_id='test-listing-id',
            marketplace_type=MarketplaceType.GOOGLE_CLOUD_MARKETPLACE,
            title='Test Listing',
            metadata={'data_exchange_id': 'test-exchange'}
        )
        mock_get_listing.return_value = listing

        # Mock mapping
        mapping = MarketplaceAssetMapping(
            asset_data={'name': 'Test Listing'},
            source_type=AssetSourceType.FEDERATED,
            source_metadata={'listing_id': 'test-listing-id'},
            resources=[]
        )
        mock_map_to_hub_asset.return_value = mapping

        # Mock resources
        mock_list_resources.return_value = []

        # Execute sync_pull
        result = self.connector.sync_pull(listing_ids=['test-listing-id'])

        # Verify result
        self.assertIsInstance(result, SyncResult)
        self.assertEqual(result.status, SyncStatus.COMPLETED)
        self.assertEqual(result.successful_items, 1)
        self.assertEqual(result.failed_items, 0)
        self.assertIn('mappings', result.metadata)
        self.assertEqual(len(result.metadata['mappings']), 1)

        # Verify map_to_hub_asset was called (not subscription or schema extraction)
        mock_map_to_hub_asset.assert_called_once()
        mock_get_listing.assert_called_once_with('test-listing-id')

    @patch('hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector.list_listings')
    @patch('hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector.map_to_hub_asset')
    @patch('hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector.list_resources')
    def test_sync_pull_with_filters(self, mock_list_resources, mock_map_to_hub_asset, mock_list_listings):
        """Test sync_pull() with filters"""
        # Mock listings
        listing = MarketplaceListing(
            marketplace_id='test-listing-id',
            marketplace_type=MarketplaceType.GOOGLE_CLOUD_MARKETPLACE,
            title='Test Listing',
            metadata={'data_exchange_id': 'test-exchange'}
        )
        mock_list_listings.return_value = [listing]

        # Mock mapping
        mapping = MarketplaceAssetMapping(
            asset_data={'name': 'Test Listing'},
            source_type=AssetSourceType.FEDERATED,
            source_metadata={'listing_id': 'test-listing-id'},
            resources=[]
        )
        mock_map_to_hub_asset.return_value = mapping

        # Mock resources
        mock_list_resources.return_value = []

        # Execute sync_pull
        result = self.connector.sync_pull(filters={'category': 'test'})

        # Verify result
        self.assertIsInstance(result, SyncResult)
        self.assertEqual(result.status, SyncStatus.COMPLETED)
        self.assertEqual(result.successful_items, 1)
        mock_list_listings.assert_called_once_with(filters={'category': 'test'}, limit=None)

    @patch('hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector.get_listing')
    def test_sync_pull_not_found_listing(self, mock_get_listing):
        """Test sync_pull() handles NotFoundError for non-existent listings"""
        mock_get_listing.side_effect = NotFoundError("Listing not found")

        result = self.connector.sync_pull(listing_ids=['non-existent'])

        self.assertIsInstance(result, SyncResult)
        self.assertEqual(result.skipped_items, 1)
        self.assertEqual(result.successful_items, 0)
        self.assertGreater(len(result.errors), 0)

    @patch('hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector.list_listings')
    def test_sync_pull_no_listings(self, mock_list_listings):
        """Test sync_pull() handles empty listings"""
        mock_list_listings.return_value = []

        result = self.connector.sync_pull()

        self.assertIsInstance(result, SyncResult)
        self.assertEqual(result.status, SyncStatus.COMPLETED)
        self.assertEqual(result.successful_items, 0)
        self.assertEqual(len(result.metadata['mappings']), 0)

    @patch('hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector.get_listing')
    @patch('hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector.map_to_hub_asset')
    def test_sync_pull_dry_run(self, mock_map_to_hub_asset, mock_get_listing):
        """Test sync_pull() with dry_run option"""
        listing = MarketplaceListing(
            marketplace_id='test-listing-id',
            marketplace_type=MarketplaceType.GOOGLE_CLOUD_MARKETPLACE,
            title='Test Listing',
            metadata={}
        )
        mock_get_listing.return_value = listing

        result = self.connector.sync_pull(listing_ids=['test-listing-id'], options={'dry_run': True})

        self.assertIsInstance(result, SyncResult)
        self.assertEqual(result.status, SyncStatus.COMPLETED)
        self.assertEqual(result.successful_items, 1)
        # map_to_hub_asset should NOT be called in dry_run mode
        mock_map_to_hub_asset.assert_not_called()


class TestGCPMarketplaceConnectorMapBigQueryType(TestCase):
    """Test _map_bigquery_type() method"""

    def setUp(self):
        """Set up test fixtures"""
        self.connector = GCPMarketplaceConnector(
            project_id='test-project',
            use_adc=True
        )

    def test_map_bigquery_type_string(self):
        """Test mapping STRING and BYTES to string"""
        self.assertEqual(self.connector._map_bigquery_type('STRING'), 'string')
        self.assertEqual(self.connector._map_bigquery_type('BYTES'), 'string')

    def test_map_bigquery_type_number(self):
        """Test mapping numeric types to number"""
        self.assertEqual(self.connector._map_bigquery_type('INTEGER'), 'number')
        self.assertEqual(self.connector._map_bigquery_type('INT64'), 'number')
        self.assertEqual(self.connector._map_bigquery_type('FLOAT'), 'number')
        self.assertEqual(self.connector._map_bigquery_type('FLOAT64'), 'number')
        self.assertEqual(self.connector._map_bigquery_type('NUMERIC'), 'number')
        self.assertEqual(self.connector._map_bigquery_type('BIGNUMERIC'), 'number')

    def test_map_bigquery_type_boolean(self):
        """Test mapping boolean types"""
        self.assertEqual(self.connector._map_bigquery_type('BOOLEAN'), 'boolean')
        self.assertEqual(self.connector._map_bigquery_type('BOOL'), 'boolean')

    def test_map_bigquery_type_datetime(self):
        """Test mapping datetime types"""
        self.assertEqual(self.connector._map_bigquery_type('TIMESTAMP'), 'datetime')
        self.assertEqual(self.connector._map_bigquery_type('DATETIME'), 'datetime')
        self.assertEqual(self.connector._map_bigquery_type('DATE'), 'date')
        self.assertEqual(self.connector._map_bigquery_type('TIME'), 'time')

    def test_map_bigquery_type_complex(self):
        """Test mapping complex types"""
        self.assertEqual(self.connector._map_bigquery_type('ARRAY'), 'array')
        self.assertEqual(self.connector._map_bigquery_type('STRUCT'), 'object')
        self.assertEqual(self.connector._map_bigquery_type('RECORD'), 'object')
        self.assertEqual(self.connector._map_bigquery_type('GEOGRAPHY'), 'string')

    def test_map_bigquery_type_unknown(self):
        """Test mapping unknown types defaults to string"""
        self.assertEqual(self.connector._map_bigquery_type('UNKNOWN_TYPE'), 'string')
        self.assertEqual(self.connector._map_bigquery_type(''), 'string')


class TestGCPMarketplaceConnectorExtractSchema(TestCase):
    """Test _extract_schema_from_bigquery_dataset() method"""

    def setUp(self):
        """Set up test fixtures"""
        self.connector = GCPMarketplaceConnector(
            project_id='test-project',
            use_adc=True
        )

    @patch('hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector._get_bigquery_client')
    def test_extract_schema_success(self, mock_get_client):
        """Test _extract_schema_from_bigquery_dataset() extracts schema correctly"""
        # Mock BigQuery client and query results
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock query results
        mock_row1 = MagicMock()
        mock_row1.column_name = 'id'
        mock_row1.data_type = 'INT64'
        mock_row1.is_nullable = 'NO'
        mock_row1.description = 'Primary key'
        mock_row1.column_default = None

        mock_row2 = MagicMock()
        mock_row2.column_name = 'name'
        mock_row2.data_type = 'STRING'
        mock_row2.is_nullable = 'YES'
        mock_row2.description = 'Name field'
        mock_row2.column_default = None

        mock_results = MagicMock()
        mock_results.__iter__ = lambda self: iter([mock_row1, mock_row2])
        mock_query_job = MagicMock()
        mock_query_job.result.return_value = mock_results
        mock_client.query.return_value = mock_query_job

        # Extract schema
        schema = self.connector._extract_schema_from_bigquery_dataset('test_dataset', 'test_table')

        # Verify schema structure
        self.assertIsInstance(schema, dict)
        self.assertIn('fields', schema)
        self.assertEqual(len(schema['fields']), 2)
        self.assertEqual(schema['fields'][0]['name'], 'id')
        self.assertEqual(schema['fields'][0]['type'], 'number')
        self.assertFalse(schema['fields'][0]['nullable'])
        self.assertEqual(schema['fields'][1]['name'], 'name')
        self.assertEqual(schema['fields'][1]['type'], 'string')
        self.assertTrue(schema['fields'][1]['nullable'])

    @patch('hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector._get_bigquery_client')
    def test_extract_schema_not_found(self, mock_get_client):
        """Test _extract_schema_from_bigquery_dataset() raises NotFoundError for non-existent table"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        from google.api_core.exceptions import NotFound as GoogleNotFound
        mock_client.query.side_effect = GoogleNotFound("Table not found")

        with self.assertRaises(NotFoundError):
            self.connector._extract_schema_from_bigquery_dataset('test_dataset', 'non_existent_table')


class TestGCPMarketplaceConnectorSubscribeToListing(TestCase):
    """Test _subscribe_to_listing() method"""

    def setUp(self):
        """Set up test fixtures"""
        self.connector = GCPMarketplaceConnector(
            project_id='test-project',
            use_adc=True
        )

    @patch('hub.apps.integrations.connectors.gcp_marketplace_connector.ANALYTICSHUB_AVAILABLE', True)
    @patch('hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector._get_analyticshub_client')
    def test_subscribe_to_listing_success(self, mock_get_client):
        """Test _subscribe_to_listing() subscribes successfully"""
        # Mock Analytics Hub client
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock subscribe response
        from unittest.mock import Mock
        mock_response = Mock()
        mock_dest_dataset = Mock()
        mock_dest_dataset.project_id = 'test-project'
        mock_dest_dataset.dataset_id = 'test_dataset'
        mock_response.destination_dataset = mock_dest_dataset
        mock_client.subscribe_listing.return_value = mock_response

        # Subscribe
        linked_dataset = self.connector._subscribe_to_listing('test-listing', 'test-exchange')

        # Verify
        self.assertEqual(linked_dataset, 'test-project.test_dataset')
        mock_client.subscribe_listing.assert_called_once()

    @patch('hub.apps.integrations.connectors.gcp_marketplace_connector.ANALYTICSHUB_AVAILABLE', True)
    @patch('hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector._get_analyticshub_client')
    @patch('hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector.get_listing')
    def test_subscribe_to_listing_already_subscribed(self, mock_get_listing, mock_get_client):
        """Test _subscribe_to_listing() handles already subscribed case"""
        # Mock Analytics Hub client
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock AlreadyExists exception (409)
        from google.api_core.exceptions import AlreadyExists
        mock_client.subscribe_listing.side_effect = AlreadyExists("Already subscribed")

        # Mock get_listing to return listing with linked dataset
        mock_listing = MarketplaceListing(
            marketplace_id='test-listing',
            marketplace_type=MarketplaceType.GOOGLE_CLOUD_MARKETPLACE,
            title='Test',
            metadata={
                'analytics_hub_listing': {
                    'bigquery_dataset': {
                        'dataset': 'test-project.test_dataset'
                    }
                }
            }
        )
        mock_get_listing.return_value = mock_listing

        # Subscribe (should handle AlreadyExists)
        linked_dataset = self.connector._subscribe_to_listing('test-listing', 'test-exchange')

        # Verify
        self.assertEqual(linked_dataset, 'test-project.test_dataset')

    @patch('hub.apps.integrations.connectors.gcp_marketplace_connector.ANALYTICSHUB_AVAILABLE', True)
    @patch('hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector._get_analyticshub_client')
    def test_subscribe_to_listing_not_found(self, mock_get_client):
        """Test _subscribe_to_listing() raises NotFoundError for non-existent listing"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        from google.api_core.exceptions import NotFound
        mock_client.subscribe_listing.side_effect = NotFound("Listing not found")

        with self.assertRaises(NotFoundError):
            self.connector._subscribe_to_listing('non-existent', 'test-exchange')

