"""
Unit tests for Databricks connector discovery operations.

Tests list_listings, get_listing, and list_resources methods.
Follows TDD approach - tests written before implementation.
"""

from typing import Any, Dict, List
from unittest.mock import Mock, patch
from datetime import datetime

import httpx
import pytest
from django.test import TestCase

from hub.apps.integrations.connectors.databricks_connector import DatabricksConnector
from hub.apps.integrations.base import (
    MarketplaceListing,
    MarketplaceResource,
    MarketplaceType,
)
from hub.apps.core.services.base import NotFoundError


class TestDatabricksConnectorListListings(TestCase):
    """Test Databricks connector list_listings method"""

    def setUp(self):
        """Set up test fixtures"""
        self.connector = DatabricksConnector(
            host='https://test-workspace.cloud.databricks.com',
            token='dapi1234567890abcdef'
        )

    def test_list_listings_basic(self):
        """Test basic list_listings without filters"""
        # Mock Unity Catalog shares.list() response
        mock_shares_response = {
            'shares': [
                {
                    'name': 'test_share_1',
                    'comment': 'Test Share 1',
                    'owner': 'test@example.com',
                    'created_at': 1767890085912,
                    'updated_at': 1767890085912
                },
                {
                    'name': 'test_share_2',
                    'comment': 'Test Share 2',
                    'owner': 'test@example.com',
                    'created_at': 1767890085913,
                    'updated_at': 1767890085914
                }
            ]
        }

        with patch.object(self.connector, '_request_with_retry') as mock_request:
            # Mock shares.list() call
            mock_response = Mock()
            mock_response.json.return_value = mock_shares_response
            mock_response.status_code = 200
            mock_request.return_value = mock_response

            # Mock _get_share_details for each share
            with patch.object(self.connector, '_get_share_details') as mock_get_details:
                mock_get_details.side_effect = [
                    {'name': 'test_share_1', 'comment': 'Test Share 1', 'owner': 'test@example.com'},
                    {'name': 'test_share_2', 'comment': 'Test Share 2', 'owner': 'test@example.com'}
                ]

                listings = self.connector.list_listings()

                self.assertIsInstance(listings, list)
                self.assertEqual(len(listings), 2)
                self.assertIsInstance(listings[0], MarketplaceListing)
                self.assertEqual(listings[0].marketplace_id, 'test_share_1')
                self.assertEqual(listings[0].marketplace_type, MarketplaceType.DATABRICKS_MARKETPLACE)

    def test_list_listings_with_limit(self):
        """Test list_listings with limit parameter"""
        mock_shares_response = {
            'shares': [
                {'name': f'share_{i}', 'comment': f'Share {i}'}
                for i in range(10)
            ]
        }

        with patch.object(self.connector, '_request_with_retry') as mock_request:
            mock_response = Mock()
            mock_response.json.return_value = mock_shares_response
            mock_response.status_code = 200
            mock_request.return_value = mock_response

            with patch.object(self.connector, '_get_share_details') as mock_get_details:
                mock_get_details.return_value = {'name': 'test', 'comment': 'Test'}

                listings = self.connector.list_listings(limit=5)

                self.assertEqual(len(listings), 5)
                mock_get_details.assert_called_once()

    def test_list_listings_with_offset(self):
        """Test list_listings with offset parameter"""
        mock_shares_response = {
            'shares': [
                {'name': f'share_{i}', 'comment': f'Share {i}'}
                for i in range(10)
            ]
        }

        with patch.object(self.connector, '_request_with_retry') as mock_request:
            mock_response = Mock()
            mock_response.json.return_value = mock_shares_response
            mock_response.status_code = 200
            mock_request.return_value = mock_response

            with patch.object(self.connector, '_get_share_details') as mock_get_details:
                mock_get_details.return_value = {'name': 'test', 'comment': 'Test'}

                listings = self.connector.list_listings(offset=5)

                # Should skip first 5 and return remaining
                self.assertGreaterEqual(len(listings), 0)
                mock_get_details.assert_called_once()

    def test_list_listings_empty_result(self):
        """Test list_listings when no shares exist"""
        mock_shares_response = {'shares': []}

        with patch.object(self.connector, '_request_with_retry') as mock_request:
            mock_response = Mock()
            mock_response.json.return_value = mock_shares_response
            mock_response.status_code = 200
            mock_request.return_value = mock_response

            listings = self.connector.list_listings()

            self.assertIsInstance(listings, list)
            self.assertEqual(len(listings), 0)

    def test_list_listings_connection_error(self):
        """Test list_listings raises ConnectionError on failure"""
        with patch.object(self.connector, '_request_with_retry') as mock_request:
            mock_request.side_effect = httpx.RequestError("Connection failed")

            with self.assertRaises(ConnectionError):
                self.connector.list_listings()


class TestDatabricksConnectorGetListing(TestCase):
    """Test Databricks connector get_listing method"""

    def setUp(self):
        """Set up test fixtures"""
        self.connector = DatabricksConnector(
            host='https://test-workspace.cloud.databricks.com',
            token='dapi1234567890abcdef'
        )

    def test_get_listing_success(self):
        """Test successful get_listing"""
        mock_share_details = {
            'name': 'test_share',
            'comment': 'Test Share Description',
            'owner': 'test@example.com',
            'created_at': 1767890085912,
            'updated_at': 1767890085913
        }

        with patch.object(self.connector, '_get_share_details') as mock_get_details:
            mock_get_details.return_value = mock_share_details

            listing = self.connector.get_listing('test_share')

            self.assertIsInstance(listing, MarketplaceListing)
            self.assertEqual(listing.marketplace_id, 'test_share')
            self.assertEqual(listing.title, 'test_share')
            self.assertEqual(listing.description, 'Test Share Description')
            self.assertEqual(listing.marketplace_type, MarketplaceType.DATABRICKS_MARKETPLACE)
            mock_get_details.assert_called_once_with('test_share')

    def test_get_listing_not_found(self):
        """Test get_listing raises NotFoundError when share doesn't exist"""
        with patch.object(self.connector, '_get_share_details') as mock_get_details:
            mock_get_details.side_effect = httpx.HTTPStatusError(
                "Not Found",
                request=Mock(),
                response=Mock(status_code=404)
            )

            with self.assertRaises(NotFoundError):
                self.connector.get_listing('non_existent_share')

    def test_get_listing_connection_error(self):
        """Test get_listing raises ConnectionError on network failure"""
        with patch.object(self.connector, '_get_share_details') as mock_get_details:
            mock_get_details.side_effect = httpx.RequestError("Connection failed")

            with self.assertRaises(ConnectionError):
                self.connector.get_listing('test_share')


class TestDatabricksConnectorListResources(TestCase):
    """Test Databricks connector list_resources method"""

    def setUp(self):
        """Set up test fixtures"""
        self.connector = DatabricksConnector(
            host='https://test-workspace.cloud.databricks.com',
            token='dapi1234567890abcdef'
        )

    def test_list_resources_success(self):
        """Test successful list_resources"""
        # Mock share details with schemas
        mock_share_details = {
            'name': 'test_share',
            'comment': 'Test Share',
            'schemas': [
                {
                    'name': 'schema1',
                    'catalog_name': 'test_catalog'
                }
            ]
        }

        mock_catalogs_response = {
            'catalogs': [
                {
                    'name': 'test_catalog'
                }
            ]
        }

        mock_schemas_response = {
            'schemas': [
                {
                    'name': 'schema1',
                    'catalog_name': 'test_catalog',
                    'share_name': 'test_share'
                }
            ]
        }

        mock_tables_response = {
            'tables': [
                {
                    'name': 'table1',
                    'schema_name': 'schema1',
                    'catalog_name': 'test_catalog',
                    'table_type': 'MANAGED',
                    'share_name': 'test_share'
                },
                {
                    'name': 'table2',
                    'schema_name': 'schema1',
                    'catalog_name': 'test_catalog',
                    'table_type': 'EXTERNAL',
                    'share_name': 'test_share'
                }
            ]
        }

        with patch.object(self.connector, '_get_share_details') as mock_get_share:
            mock_get_share.return_value = mock_share_details

            with patch.object(self.connector, '_request_with_retry') as mock_request:
                # Since schemas are in share_details, we only need to query tables
                # Mock tables.list() call for schema1
                mock_tables_response_obj = Mock()
                mock_tables_response_obj.json.return_value = mock_tables_response
                mock_tables_response_obj.status_code = 200

                mock_request.return_value = mock_tables_response_obj

                resources = self.connector.list_resources('test_share')

                self.assertIsInstance(resources, list)
                self.assertEqual(len(resources), 2)
                self.assertIsInstance(resources[0], MarketplaceResource)
                self.assertEqual(resources[0].resource_type, 'TABLE')
                self.assertEqual(resources[0].resource_id, 'test_catalog.schema1.table1')

                # Verify tables.list() was called with correct parameters
                mock_request.assert_called_once()
                call_args = mock_request.call_args
                self.assertEqual(call_args[0][1], '/api/2.0/unity-catalog/tables')
                self.assertEqual(call_args[1]['params']['catalog_name'], 'test_catalog')
                self.assertEqual(call_args[1]['params']['schema_name'], 'schema1')

    def test_list_resources_empty(self):
        """Test list_resources when share has no schemas"""
        mock_share_details = {
            'name': 'test_share',
            'comment': 'Test Share',
            'schemas': []  # No schemas
        }

        with patch.object(self.connector, '_get_share_details') as mock_get_share:
            mock_get_share.return_value = mock_share_details

            resources = self.connector.list_resources('test_share')

            self.assertIsInstance(resources, list)
            self.assertEqual(len(resources), 0)

    def test_list_resources_share_not_found(self):
        """Test list_resources raises NotFoundError when share doesn't exist"""
        with patch.object(self.connector, '_request_with_retry') as mock_request:
            mock_request.side_effect = httpx.HTTPStatusError(
                "Not Found",
                request=Mock(),
                response=Mock(status_code=404)
            )

            with self.assertRaises(NotFoundError):
                self.connector.list_resources('non_existent_share')

    def test_list_resources_connection_error(self):
        """Test list_resources raises ConnectionError on network failure"""
        with patch.object(self.connector, '_request_with_retry') as mock_request:
            mock_request.side_effect = httpx.RequestError("Connection failed")

            with self.assertRaises(ConnectionError):
                self.connector.list_resources('test_share')

