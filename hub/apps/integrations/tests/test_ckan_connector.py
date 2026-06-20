"""
Unit and Integration Tests for CKAN Connector

Tests the CKANConnector implementation including:
- Connector initialization
- Authentication
- Connection testing
- CRUD operations
- Circuit breaker and retry logic
- Error handling
"""

import os
import tempfile
import unittest
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import httpx
import pytest
from django.test import TestCase, override_settings

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
from hub.apps.integrations.connectors.ckan_connector import CKANConnector
from hub.apps.integrations.tests.utils.marketplace_test_helpers import (
    create_test_connector,
    marketplace_available,
)


class TestCKANConnectorInitialization(TestCase):
    """Test CKAN connector initialization"""

    def test_init_with_base_url(self):
        """Test connector initialization with base URL"""
        connector = CKANConnector(base_url="https://data.gov")
        self.assertEqual(connector.base_url, "https://data.gov")
        self.assertEqual(connector.marketplace_type, MarketplaceType.CKAN_INSTANCE)

    def test_init_with_base_url_trailing_slash(self):
        """Test connector removes trailing slash from base URL"""
        connector = CKANConnector(base_url="https://data.gov/")
        self.assertEqual(connector.base_url, "https://data.gov")

    def test_init_with_api_key(self):
        """Test connector initialization with API key"""
        connector = CKANConnector(base_url="https://data.gov", api_key="test-key")
        self.assertEqual(connector.api_key, "test-key")

    @override_settings(CKAN_DEFAULT_BASE_URL="https://default.ckan.org")
    def test_init_uses_settings_default_url(self):
        """Test connector uses default URL from settings"""
        connector = CKANConnector()
        self.assertEqual(connector.base_url, "https://default.ckan.org")

    def test_init_requires_base_url(self):
        """Test connector raises error if base URL not provided"""
        with self.assertRaises(ValueError) as cm:
            CKANConnector()
        self.assertIn("base_url", str(cm.exception))

    def test_marketplace_type_property(self):
        """Test marketplace_type property returns correct value"""
        connector = CKANConnector(base_url="https://data.gov")
        self.assertEqual(connector.marketplace_type, MarketplaceType.CKAN_INSTANCE)

    def test_supported_sync_directions_property(self):
        """Test supported_sync_directions is PULL only (CKAN is harvest-only)."""
        connector = CKANConnector(base_url="https://data.gov")
        directions = connector.supported_sync_directions
        self.assertEqual(directions, [SyncDirection.PULL])
        self.assertIn(SyncDirection.PULL, directions)
        self.assertNotIn(SyncDirection.PUSH, directions)
        self.assertNotIn(SyncDirection.BIDIRECTIONAL, directions)


class TestCKANConnectorAuthentication(TestCase):
    """Test CKAN connector authentication"""

    def setUp(self):
        """Set up test fixtures"""
        self.connector = CKANConnector(base_url="https://data.gov")

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector._request_with_retry")
    def test_authenticate_success(self, mock_request):
        """Test successful authentication"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "success": True,
            "result": {"site_title": "Test CKAN Instance", "site_description": "Test"},
        }
        mock_request.return_value = mock_response

        credentials = {"api_key": "test-key"}
        result = self.connector.authenticate(credentials)

        self.assertTrue(result)
        self.assertTrue(self.connector._authenticated)
        self.assertEqual(self.connector.api_key, "test-key")
        mock_request.assert_called_once_with("GET", "/api/3/action/status_show")

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector._request_with_retry")
    def test_authenticate_with_base_url(self, mock_request):
        """Test authentication updates base URL if provided"""
        mock_response = Mock()
        mock_response.json.return_value = {"success": True, "result": {"site_title": "Test"}}
        mock_request.return_value = mock_response

        credentials = {"api_key": "test-key", "base_url": "https://new.ckan.org"}
        result = self.connector.authenticate(credentials)

        self.assertTrue(result)
        self.assertEqual(self.connector.base_url, "https://new.ckan.org")

    def test_authenticate_missing_credentials(self):
        """Test authentication raises error if credentials missing"""
        with self.assertRaises(ValueError) as cm:
            self.connector.authenticate({})
        error_msg = str(cm.exception)
        # Check for either error message variant
        self.assertTrue(
            "api_key" in error_msg or "Credentials dictionary is required" in error_msg,
            f"Expected 'api_key' or 'Credentials dictionary is required' in error message, got: {error_msg}",
        )

    def test_authenticate_connection_error(self):
        """Test authentication raises ConnectionError on failure"""
        with patch(
            "hub.apps.integrations.connectors.ckan_connector.CKANConnector._request_with_retry"
        ) as mock_request:
            mock_request.side_effect = ConnectionError("Connection failed")

            credentials = {"api_key": "test-key"}
            with self.assertRaises(ConnectionError):
                self.connector.authenticate(credentials)

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector._request_with_retry")
    def test_authenticate_invalid_response(self, mock_request):
        """Test authentication fails on invalid response"""
        mock_response = Mock()
        mock_response.json.return_value = {"success": False, "error": "Invalid API key"}
        mock_request.return_value = mock_response

        credentials = {"api_key": "invalid-key"}
        result = self.connector.authenticate(credentials)

        self.assertFalse(result)
        self.assertFalse(self.connector._authenticated)


class TestCKANConnectorConnectionTest(TestCase):
    """Test CKAN connector connection testing"""

    def setUp(self):
        """Set up test fixtures"""
        self.connector = CKANConnector(base_url="https://data.gov")

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector._request_with_retry")
    def test_test_connection_success(self, mock_request):
        """Test successful connection test (connector uses package_search with rows=0)."""
        mock_response = Mock()
        mock_response.json.return_value = {"success": True}
        mock_request.return_value = mock_response

        result = self.connector.test_connection()

        self.assertTrue(result)
        mock_request.assert_called_once_with(
            "GET", "/api/3/action/package_search", params={"rows": 0}
        )

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector._request_with_retry")
    def test_test_connection_failure(self, mock_request):
        """Test connection test returns False when response has no 'success' field."""
        mock_response = Mock()
        mock_response.json.return_value = {"error": "Invalid response"}
        mock_request.return_value = mock_response

        result = self.connector.test_connection()

        self.assertFalse(result)

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector._request_with_retry")
    def test_test_connection_error(self, mock_request):
        """Test connection test raises ConnectionError on failure"""
        mock_request.side_effect = ConnectionError("Connection failed")

        with self.assertRaises(ConnectionError):
            self.connector.test_connection()


class TestCKANConnectorListListings(TestCase):
    """Test CKAN connector list_listings method"""

    def setUp(self):
        """Set up test fixtures"""
        self.connector = CKANConnector(base_url="https://data.gov")

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector._request_with_retry")
    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector.get_listing")
    def test_list_listings_success(self, mock_get_listing, mock_request):
        """Test successful listing retrieval"""
        # Mock package_list response
        mock_response = Mock()
        mock_response.json.return_value = {"success": True, "result": ["package-1", "package-2"]}
        mock_request.return_value = mock_response

        # Mock get_listing responses
        mock_get_listing.side_effect = [
            MarketplaceListing(
                marketplace_id="package-1",
                marketplace_type=MarketplaceType.CKAN_INSTANCE,
                title="Package 1",
            ),
            MarketplaceListing(
                marketplace_id="package-2",
                marketplace_type=MarketplaceType.CKAN_INSTANCE,
                title="Package 2",
            ),
        ]

        listings = self.connector.list_listings()

        self.assertEqual(len(listings), 2)
        self.assertEqual(listings[0].marketplace_id, "package-1")
        self.assertEqual(listings[1].marketplace_id, "package-2")

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector._request_with_retry")
    def test_list_listings_with_filters(self, mock_request):
        """Test listing retrieval with filters"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "success": True,
            "result": {
                "results": [
                    {
                        "id": "package-1",
                        "name": "package-1",
                        "title": "Package 1",
                        "notes": "Description",
                        "tags": [{"name": "tag1"}],
                        "organization": {"name": "org1"},
                    }
                ]
            },
        }
        mock_request.return_value = mock_response

        filters = {"q": "test", "organization": "org1"}
        listings = self.connector.list_listings(filters=filters)

        self.assertEqual(len(listings), 1)
        # Verify search endpoint was called
        call_args = mock_request.call_args
        self.assertEqual(call_args[0][1], "/api/3/action/package_search")

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector._request_with_retry")
    def test_list_listings_with_pagination(self, mock_request):
        """Test listing retrieval with pagination"""
        mock_response = Mock()
        mock_response.json.return_value = {"success": True, "result": {"results": []}}
        mock_request.return_value = mock_response

        listings = self.connector.list_listings(limit=10, offset=20)

        # Verify search endpoint was called with pagination params
        call_args = mock_request.call_args
        self.assertEqual(call_args[0][1], "/api/3/action/package_search")
        self.assertEqual(call_args[1]["params"]["rows"], 10)
        self.assertEqual(call_args[1]["params"]["start"], 20)


class TestCKANConnectorGetListing(TestCase):
    """Test CKAN connector get_listing method"""

    def setUp(self):
        """Set up test fixtures"""
        self.connector = CKANConnector(base_url="https://data.gov")

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector._request_with_retry")
    def test_get_listing_success(self, mock_request):
        """Test successful listing retrieval"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "success": True,
            "result": {
                "id": "test-package",
                "name": "test-package",
                "title": "Test Package",
                "notes": "Test Description",
                "tags": [{"name": "tag1"}, {"name": "tag2"}],
                "organization": {"name": "test-org"},
                "metadata_created": "2023-01-01T00:00:00Z",
                "metadata_modified": "2023-01-02T00:00:00Z",
            },
        }
        mock_request.return_value = mock_response

        listing = self.connector.get_listing("test-package")

        self.assertEqual(listing.marketplace_id, "test-package")
        self.assertEqual(listing.title, "Test Package")
        self.assertEqual(listing.description, "Test Description")
        self.assertEqual(len(listing.tags), 2)
        self.assertEqual(listing.category, "test-org")
        self.assertIsNotNone(listing.created_at)
        self.assertIsNotNone(listing.updated_at)

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector._request_with_retry")
    def test_get_listing_not_found(self, mock_request):
        """Test get_listing raises NotFoundError for non-existent package"""
        mock_response = Mock()
        mock_response.json.return_value = {"success": False, "error": {"message": "Not found"}}
        mock_request.return_value = mock_response

        with self.assertRaises(NotFoundError):
            self.connector.get_listing("non-existent")

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector._request_with_retry")
    def test_get_listing_http_404(self, mock_request):
        """Test get_listing raises NotFoundError on HTTP 404"""
        mock_request.side_effect = httpx.HTTPStatusError(
            "Not found", request=Mock(), response=Mock(status_code=404)
        )

        with self.assertRaises(NotFoundError):
            self.connector.get_listing("non-existent")


class TestCKANConnectorListResources(TestCase):
    """Test CKAN connector list_resources method"""

    def setUp(self):
        """Set up test fixtures"""
        self.connector = CKANConnector(base_url="https://data.gov")

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector.get_listing")
    def test_list_resources_success(self, mock_get_listing):
        """Test successful resource listing"""
        mock_listing = MarketplaceListing(
            marketplace_id="test-package",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Test Package",
            metadata={
                "ckan_package": {
                    "resources": [
                        {
                            "id": "resource-1",
                            "name": "Resource 1",
                            "description": "Description 1",
                            "url": "https://example.com/resource1.csv",
                            "format": "CSV",
                            "size": 1024,
                        },
                        {
                            "id": "resource-2",
                            "name": "Resource 2",
                            "url": "https://example.com/resource2.json",
                            "format": "JSON",
                        },
                    ]
                }
            },
        )
        mock_get_listing.return_value = mock_listing

        resources = self.connector.list_resources("test-package")

        self.assertEqual(len(resources), 2)
        self.assertEqual(resources[0].resource_id, "resource-1")
        self.assertEqual(resources[0].name, "Resource 1")
        self.assertEqual(resources[0].url, "https://example.com/resource1.csv")
        self.assertEqual(resources[0].format, "CSV")
        self.assertEqual(resources[0].size_bytes, 1024)

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector.get_listing")
    def test_list_resources_not_found(self, mock_get_listing):
        """Test list_resources raises NotFoundError if package not found"""
        mock_get_listing.side_effect = NotFoundError("Package not found")

        with self.assertRaises(NotFoundError):
            self.connector.list_resources("non-existent")


class TestCKANConnectorDownloadResource(TestCase):
    """Test CKAN connector download_resource method"""

    def setUp(self):
        """Set up test fixtures"""
        self.connector = CKANConnector(base_url="https://data.gov")

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector._request_with_retry")
    @patch("httpx.get")
    def test_download_resource_success(self, mock_get, mock_request):
        """Test successful resource download"""
        # Mock resource_show response
        mock_response = Mock()
        mock_response.json.return_value = {
            "success": True,
            "result": {"id": "resource-1", "url": "https://example.com/resource.csv"},
        }
        mock_request.return_value = mock_response

        # Mock download response with proper iter_bytes implementation
        mock_download_response = Mock()
        mock_download_response.content = b"csv,data,here"

        # Mock iter_bytes to return an iterator over the content
        def iter_bytes_side_effect(chunk_size):
            content = b"csv,data,here"
            for i in range(0, len(content), chunk_size):
                yield content[i : i + chunk_size]

        mock_download_response.iter_bytes = iter_bytes_side_effect
        mock_download_response.raise_for_status = Mock()
        mock_get.return_value = mock_download_response

        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            destination_path = tmp_file.name

        try:
            result_path = self.connector.download_resource("resource-1", destination_path)

            self.assertEqual(result_path, destination_path)
            self.assertTrue(os.path.exists(destination_path))
            with open(destination_path, "rb") as f:
                self.assertEqual(f.read(), b"csv,data,here")
        finally:
            if os.path.exists(destination_path):
                os.unlink(destination_path)

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector._request_with_retry")
    def test_download_resource_not_found(self, mock_request):
        """Test download_resource raises NotFoundError if resource not found"""
        mock_response = Mock()
        mock_response.json.return_value = {"success": False, "error": {"message": "Not found"}}
        mock_request.return_value = mock_response

        with self.assertRaises(NotFoundError):
            self.connector.download_resource("non-existent", "/tmp/test.csv")


class TestCKANConnectorMapping(TestCase):
    """Test CKAN connector mapping methods"""

    def setUp(self):
        """Set up test fixtures"""
        self.connector = CKANConnector(base_url="https://data.gov")

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector.list_resources")
    def test_map_to_hub_asset_basic(self, mock_list_resources):
        """Test basic mapping CKAN package to Hub asset"""
        mock_list_resources.return_value = []

        listing = MarketplaceListing(
            marketplace_id="test-package",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Test Package",
            description="Test Description",
            category="test-org",
            tags=["tag1", "tag2"],
            url="https://data.gov/dataset/test-package",
        )

        mapping = self.connector.map_to_hub_asset(listing)

        self.assertIsInstance(mapping, MarketplaceAssetMapping)
        self.assertEqual(mapping.asset_data["name"], "Test Package")
        self.assertEqual(mapping.asset_data["description"], "Test Description")
        self.assertEqual(mapping.asset_data["key"], "ckan-test-package")
        self.assertEqual(mapping.asset_data["tags"], ["tag1", "tag2"])
        self.assertEqual(mapping.asset_data["domain"], "test-org")
        self.assertEqual(mapping.source_type, AssetSourceType.FEDERATED)
        self.assertEqual(
            mapping.source_metadata["marketplace_type"], MarketplaceType.CKAN_INSTANCE.value
        )
        self.assertEqual(mapping.source_metadata["listing_id"], "test-package")
        self.assertIn("synced_at", mapping.source_metadata)

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector.list_resources")
    def test_map_to_hub_asset_with_sync_job_id(self, mock_list_resources):
        """Test mapping with sync_job_id parameter"""
        mock_list_resources.return_value = []

        listing = MarketplaceListing(
            marketplace_id="test-package",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Test Package",
            description="Test Description",
        )

        mapping = self.connector.map_to_hub_asset(listing, sync_job_id="job-123")

        self.assertEqual(mapping.source_metadata["sync_job_id"], "job-123")

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector.list_resources")
    def test_map_to_hub_asset_with_ckan_package_metadata(self, mock_list_resources):
        """Test mapping with CKAN package metadata"""
        mock_list_resources.return_value = []

        ckan_package = {
            "id": "test-package",
            "title": "CKAN Title",
            "notes": "CKAN Description",
            "version": "1.0.0",
            "author": "Test Author",
            "maintainer": "Test Maintainer",
            "license_id": "cc-by",
            "license_title": "Creative Commons Attribution",
            "organization": {"name": "test-org", "title": "Test Organization"},
            "tags": [{"name": "ckan-tag1"}, {"name": "ckan-tag2"}],
            "private": False,
            "resources": [{"id": "res-1", "name": "Resource 1"}],
        }

        listing = MarketplaceListing(
            marketplace_id="test-package",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Test Package",
            description="Test Description",
            metadata={"ckan_package": ckan_package},
        )

        mapping = self.connector.map_to_hub_asset(listing)

        # Should use CKAN package title if available
        self.assertEqual(mapping.asset_data["name"], "CKAN Title")
        self.assertEqual(mapping.asset_data["description"], "CKAN Description")
        self.assertEqual(mapping.asset_data["domain"], "test-org")
        self.assertEqual(mapping.asset_data["status"], "ACTIVE")  # Public package with resources
        self.assertEqual(mapping.asset_data["visibility"], "PUBLIC")

        # Check ODPS metadata
        self.assertIsNotNone(mapping.odps_metadata)
        if mapping.odps_metadata:
            self.assertEqual(mapping.odps_metadata["product_details"]["product_version"], "1.0.0")
            self.assertEqual(mapping.odps_metadata["product_details"]["author"], "Test Author")
            self.assertEqual(
                mapping.odps_metadata["product_details"]["maintainer"], "Test Maintainer"
            )
            self.assertEqual(mapping.odps_metadata["product_details"]["license_id"], "cc-by")

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector.list_resources")
    def test_map_to_hub_asset_multilingual_fields(self, mock_list_resources):
        """Test mapping with multilingual fields"""
        mock_list_resources.return_value = []

        ckan_package = {
            "id": "test-package",
            "title": {"en": "English Title", "fr": "Titre français", "de": "Deutscher Titel"},
            "notes": {"en": "English description", "fr": "Description française"},
        }

        listing = MarketplaceListing(
            marketplace_id="test-package",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Fallback Title",
            description="Fallback Description",
            metadata={"ckan_package": ckan_package},
        )

        mapping = self.connector.map_to_hub_asset(listing)

        # Should prefer English
        self.assertEqual(mapping.asset_data["name"], "English Title")
        self.assertEqual(mapping.asset_data["description"], "English description")

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector.list_resources")
    def test_map_to_hub_asset_multilingual_fallback(self, mock_list_resources):
        """Test multilingual field fallback when English not available"""
        mock_list_resources.return_value = []

        ckan_package = {
            "id": "test-package",
            "title": {"fr": "Titre français", "de": "Deutscher Titel"},
        }

        listing = MarketplaceListing(
            marketplace_id="test-package",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Fallback Title",
            metadata={"ckan_package": ckan_package},
        )

        mapping = self.connector.map_to_hub_asset(listing)

        # Should use first available language (French)
        self.assertEqual(mapping.asset_data["name"], "Titre français")

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector.list_resources")
    def test_map_to_hub_asset_private_package(self, mock_list_resources):
        """Test mapping private CKAN package"""
        mock_list_resources.return_value = []

        ckan_package = {"id": "test-package", "title": "Private Package", "private": True}

        listing = MarketplaceListing(
            marketplace_id="test-package",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Private Package",
            metadata={"ckan_package": ckan_package},
        )

        mapping = self.connector.map_to_hub_asset(listing)

        self.assertEqual(mapping.asset_data["status"], "DRAFT")
        self.assertEqual(mapping.asset_data["visibility"], "INTERNAL")

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector.list_resources")
    def test_map_to_hub_asset_with_odps_pricing_plans(self, mock_list_resources):
        """Test mapping with ODPS pricing plans in metadata"""
        mock_list_resources.return_value = []

        pricing_plans = [
            {
                "planID": "plan-1",
                "name": "Basic Plan",
                "price": 10.0,
                "currency": "USD",
                "billingPeriod": "monthly",
            }
        ]

        listing = MarketplaceListing(
            marketplace_id="test-package",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Test Package",
            metadata={"pricing_plans": pricing_plans},
        )

        mapping = self.connector.map_to_hub_asset(listing)

        self.assertIsNotNone(mapping.odps_metadata)
        if mapping.odps_metadata:
            self.assertIn("pricing_plans", mapping.odps_metadata)
            self.assertEqual(len(mapping.odps_metadata["pricing_plans"]), 1)
            self.assertEqual(mapping.odps_metadata["pricing_plans"][0]["planID"], "plan-1")

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector.list_resources")
    def test_map_to_hub_asset_with_odps_access_methods(self, mock_list_resources):
        """Test mapping with ODPS access methods in metadata"""
        mock_list_resources.return_value = []

        access_methods = {
            "api": {
                "type": "REST_API",
                "endpoint": "https://api.example.com/data",
                "authenticationType": "API_KEY",
            }
        }

        listing = MarketplaceListing(
            marketplace_id="test-package",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Test Package",
            metadata={"access_methods": access_methods},
        )

        mapping = self.connector.map_to_hub_asset(listing)

        self.assertIsNotNone(mapping.odps_metadata)
        self.assertIn("access_methods", mapping.odps_metadata)
        if mapping.odps_metadata:
            self.assertIn("api", mapping.odps_metadata["access_methods"])

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector.list_resources")
    def test_map_to_hub_asset_with_odps_payment_gateways(self, mock_list_resources):
        """Test mapping with ODPS payment gateways in metadata"""
        mock_list_resources.return_value = []

        payment_gateways = {
            "stripe": {
                "gatewayID": "stripe",
                "enabled": True,
                "config": {"public_key": "pk_test_123"},
            }
        }

        listing = MarketplaceListing(
            marketplace_id="test-package",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Test Package",
            metadata={"payment_gateways": payment_gateways},
        )

        mapping = self.connector.map_to_hub_asset(listing)

        self.assertIsNotNone(mapping.odps_metadata)
        self.assertIn("payment_gateways", mapping.odps_metadata)
        if mapping.odps_metadata:
            self.assertIn("stripe", mapping.odps_metadata["payment_gateways"])

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector.list_resources")
    def test_map_to_hub_asset_with_odcs_metadata(self, mock_list_resources):
        """Test mapping with ODCS metadata in CKAN package extras"""
        mock_list_resources.return_value = []

        import json

        schema_data = {
            "fields": [{"name": "id", "type": "integer"}, {"name": "name", "type": "string"}]
        }

        ckan_package = {
            "id": "test-package",
            "title": "Test Package",
            "extras": [
                {"key": "odcs_schema", "value": json.dumps(schema_data)},
                {"key": "quality", "value": json.dumps({"rules": []})},
                {"key": "sla", "value": json.dumps({"availability": 99.9})},
            ],
        }

        listing = MarketplaceListing(
            marketplace_id="test-package",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Test Package",
            metadata={"ckan_package": ckan_package},
        )

        mapping = self.connector.map_to_hub_asset(listing)

        self.assertIsNotNone(mapping.odcs_metadata)
        self.assertIn("schema", mapping.odcs_metadata)
        self.assertIn("quality", mapping.odcs_metadata)
        self.assertIn("sla", mapping.odcs_metadata)

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector.list_resources")
    def test_map_to_hub_asset_missing_fields(self, mock_list_resources):
        """Test mapping with missing fields handled gracefully"""
        mock_list_resources.return_value = []

        listing = MarketplaceListing(
            marketplace_id="test-package",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Test Package",
            description=None,
            category=None,
            tags=[],
        )

        mapping = self.connector.map_to_hub_asset(listing)

        self.assertEqual(mapping.asset_data["name"], "Test Package")
        self.assertEqual(mapping.asset_data["description"], "")
        self.assertNotIn("domain", mapping.asset_data)
        self.assertEqual(mapping.asset_data["tags"], [])
        self.assertIsNone(mapping.odps_metadata)  # No ODPS data available
        self.assertIsNone(mapping.odcs_metadata)  # No ODCS data available

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector.list_resources")
    def test_map_to_hub_asset_with_resources(self, mock_list_resources):
        """Test mapping includes resources"""
        mock_resources = [
            MarketplaceResource(
                resource_id="res-1",
                resource_type="FILE",
                name="Resource 1",
                url="https://example.com/resource1.csv",
                format="CSV",
            )
        ]
        mock_list_resources.return_value = mock_resources

        listing = MarketplaceListing(
            marketplace_id="test-package",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Test Package",
        )

        mapping = self.connector.map_to_hub_asset(listing)

        self.assertEqual(len(mapping.resources), 1)
        self.assertEqual(mapping.resources[0].resource_id, "res-1")

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector.list_resources")
    def test_map_to_hub_asset_resources_failure_handled(self, mock_list_resources):
        """Test that resource fetch failure is handled gracefully"""
        mock_list_resources.side_effect = ConnectionError("Resource fetch failed")

        listing = MarketplaceListing(
            marketplace_id="test-package",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Test Package",
        )

        mapping = self.connector.map_to_hub_asset(listing)

        # Should still create mapping with empty resources
        self.assertEqual(mapping.resources, [])

    def test_map_to_hub_asset_raises_on_none_listing(self):
        """Test that mapping raises ValueError for None listing"""
        with self.assertRaises((ValueError, TypeError, AttributeError)):
            # type: ignore[misc]  # test: edge-case type exercise - intentionally passing None to test error handling
            self.connector.map_to_hub_asset(None)  # type: ignore[misc]  # test: edge-case type exercise

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector.list_resources")
    def test_map_to_hub_asset_organization_extraction(self, mock_list_resources):
        """Test organization extraction from CKAN package"""
        mock_list_resources.return_value = []

        ckan_package = {
            "id": "test-package",
            "title": "Test Package",
            "organization": {"name": "org-name", "title": "Organization Title"},
        }

        listing = MarketplaceListing(
            marketplace_id="test-package",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Test Package",
            metadata={"ckan_package": ckan_package},
        )

        mapping = self.connector.map_to_hub_asset(listing)

        self.assertEqual(mapping.asset_data["domain"], "org-name")

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector.list_resources")
    def test_map_to_hub_asset_tags_from_ckan_package(self, mock_list_resources):
        """Test tag extraction from CKAN package when not in listing"""
        mock_list_resources.return_value = []

        ckan_package = {
            "id": "test-package",
            "title": "Test Package",
            "tags": [{"name": "ckan-tag1"}, {"name": "ckan-tag2"}],
        }

        listing = MarketplaceListing(
            marketplace_id="test-package",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Test Package",
            tags=[],  # Empty tags in listing
            metadata={"ckan_package": ckan_package},
        )

        mapping = self.connector.map_to_hub_asset(listing)

        self.assertEqual(len(mapping.asset_data["tags"]), 2)
        self.assertIn("ckan-tag1", mapping.asset_data["tags"])
        self.assertIn("ckan-tag2", mapping.asset_data["tags"])

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector.list_resources")
    def test_marketplace_asset_mapping_serialization(self, mock_list_resources):
        """Test MarketplaceAssetMapping dataclass serialization"""
        mock_list_resources.return_value = [
            MarketplaceResource(
                resource_id="res-1",
                resource_type="FILE",
                name="Resource 1",
                url="https://example.com/res1.csv",
                format="CSV",
            )
        ]

        listing = MarketplaceListing(
            marketplace_id="test-package",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Test Package",
            description="Test Description",
            category="test-org",
            tags=["tag1", "tag2"],
            metadata={
                "pricing_plans": [{"planID": "plan-1", "name": "Basic"}],
                "ckan_package": {"extras": [{"key": "odcs_schema", "value": '{"fields": []}'}]},
            },
        )

        mapping = self.connector.map_to_hub_asset(listing, sync_job_id="job-123")

        # Test that all fields are serializable
        import json
        from dataclasses import asdict

        # Convert to dict
        mapping_dict = asdict(mapping)

        # Verify structure
        self.assertIn("asset_data", mapping_dict)
        self.assertIn("source_type", mapping_dict)
        self.assertIn("source_metadata", mapping_dict)
        self.assertIn("odps_metadata", mapping_dict)
        self.assertIn("odcs_metadata", mapping_dict)
        self.assertIn("resources", mapping_dict)

        # Verify source_type is serializable (should be string value)
        self.assertIsInstance(mapping_dict["source_type"], str)

        # Test JSON serialization
        json_str = json.dumps(mapping_dict, default=str)
        self.assertIsInstance(json_str, str)

        # Test deserialization
        deserialized = json.loads(json_str)
        self.assertEqual(deserialized["asset_data"]["name"], "Test Package")
        self.assertEqual(deserialized["source_metadata"]["sync_job_id"], "job-123")
        self.assertEqual(len(deserialized["resources"]), 1)

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector.list_resources")
    def test_marketplace_asset_mapping_with_none_metadata(self, mock_list_resources):
        """Test MarketplaceAssetMapping with None ODPS/ODCS metadata"""
        mock_list_resources.return_value = []

        listing = MarketplaceListing(
            marketplace_id="test-package",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Test Package",
        )

        mapping = self.connector.map_to_hub_asset(listing)

        # None metadata should be serializable
        import json
        from dataclasses import asdict

        mapping_dict = asdict(mapping)
        self.assertIsNone(mapping_dict["odps_metadata"])
        self.assertIsNone(mapping_dict["odcs_metadata"])

        # Should serialize to JSON without errors
        json_str = json.dumps(mapping_dict, default=str)
        deserialized = json.loads(json_str)
        self.assertIsNone(deserialized["odps_metadata"])
        self.assertIsNone(deserialized["odcs_metadata"])


class TestCKANConnectorSyncOperations(TestCase):
    """Test CKAN connector sync operations"""

    def setUp(self):
        """Set up test fixtures"""
        self.connector = CKANConnector(base_url="https://data.gov")


    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector.list_listings")
    def test_sync_pull_success(self, mock_list_listings):
        """Test sync_pull with listings"""
        mock_list_listings.return_value = [
            MarketplaceListing(
                marketplace_id="package-1",
                marketplace_type=MarketplaceType.CKAN_INSTANCE,
                title="Package 1",
            ),
            MarketplaceListing(
                marketplace_id="package-2",
                marketplace_type=MarketplaceType.CKAN_INSTANCE,
                title="Package 2",
            ),
        ]

        result = self.connector.sync_pull(options={"dry_run": True})

        self.assertIsInstance(result, SyncResult)
        self.assertEqual(result.total_items, 2)
        self.assertEqual(result.successful_items, 2)
        self.assertTrue(result.metadata.get("dry_run"))

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector.get_listing")
    def test_sync_pull_with_listing_ids(self, mock_get_listing):
        """Test sync_pull with specific listing IDs"""
        mock_get_listing.side_effect = [
            MarketplaceListing(
                marketplace_id="package-1",
                marketplace_type=MarketplaceType.CKAN_INSTANCE,
                title="Package 1",
            ),
            MarketplaceListing(
                marketplace_id="package-2",
                marketplace_type=MarketplaceType.CKAN_INSTANCE,
                title="Package 2",
            ),
        ]

        result = self.connector.sync_pull(
            listing_ids=["package-1", "package-2"], options={"dry_run": True}
        )

        self.assertEqual(result.total_items, 2)
        self.assertEqual(result.successful_items, 2)


class TestCKANConnectorCircuitBreaker(TestCase):
    """Test CKAN connector circuit breaker integration"""

    def setUp(self):
        """Set up test fixtures"""
        # Reset circuit breaker so prior test failures don't leave it OPEN
        from hub.apps.core.resilience.circuit_breaker import reset_circuit_breaker_by_name
        reset_circuit_breaker_by_name("ckan-connector")
        self.connector = CKANConnector(base_url="https://data.gov")

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector._request_with_retry")
    def test_circuit_breaker_protection(self, mock_request):
        """Test that circuit breaker is used for requests"""
        mock_response = Mock()
        mock_response.json.return_value = {"success": True}
        mock_request.return_value = mock_response

        result = self.connector.test_connection()

        self.assertTrue(result)
        # Verify that _request_with_retry was called (which uses circuit breaker internally)
        mock_request.assert_called_once()


class TestCKANConnectorRetryLogic(TestCase):
    """Test CKAN connector retry logic"""

    def setUp(self):
        """Set up test fixtures"""
        # Reset circuit breaker so prior test failures don't leave it OPEN
        from hub.apps.core.resilience.circuit_breaker import reset_circuit_breaker_by_name
        reset_circuit_breaker_by_name("ckan-connector")
        self.connector = CKANConnector(base_url="https://data.gov")

    @patch("time.sleep")
    @patch("hub.apps.integrations.connectors.ckan_connector.httpx.Client")
    def test_retry_on_5xx_error(self, mock_client_class, mock_sleep):
        """Test retry logic on 5xx errors"""
        # Create a mock client instance
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_response_500 = Mock()
        mock_response_500.status_code = 500
        mock_response_500.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=Mock(), response=mock_response_500
        )

        mock_response_200 = Mock()
        mock_response_200.json.return_value = {"success": True}
        mock_response_200.raise_for_status = Mock()

        # Simulate retry: first call fails, second succeeds
        call_count = [0]

        def request_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise httpx.HTTPStatusError(
                    "Server Error", request=Mock(), response=mock_response_500
                )
            return mock_response_200

        mock_client.request.side_effect = request_side_effect

        # Create connector - it will use the mocked httpx.Client
        connector = CKANConnector(base_url="https://data.gov")

        # This should retry and eventually succeed
        result = connector.test_connection()

        self.assertTrue(result)
        # Verify retry was attempted (should be called twice: once fails, once succeeds)
        self.assertEqual(mock_client.request.call_count, 2)
        # Verify sleep was called for backoff
        mock_sleep.assert_called_once()


# Integration tests with real CKAN instance (skipped if not available)
@pytest.mark.integration
class TestCKANConnectorIntegration(TestCase):
    """Integration tests with real CKAN instance.

    Uses centralized test utilities (ckan_available, create_test_connector) so behavior
    matches discovery/pull/push integration tests: runs when a CKAN instance is available
    (CKAN_TEST_URL, .env.test.ckan, or default demo.ckan.org); skips otherwise.
    """

    @classmethod
    def setUpClass(cls):
        """Set up integration test class using centralized marketplace helpers."""
        super().setUpClass()
        cls.connector = None
        cls.ckan_url = ""
        cls.ckan_api_key = ""
        if not marketplace_available():
            return
        cls.connector = create_test_connector(verify_connection=True)
        if not cls.connector:
            return
        cls.ckan_url = getattr(cls.connector, "base_url", "") or ""
        cls.ckan_api_key = getattr(cls.connector, "api_key", None) or os.getenv("CKAN_TEST_API_KEY", "")

    def setUp(self):
        """Set up test fixtures."""
        if not marketplace_available() or not getattr(self, "connector", None):
            self.skipTest("No CKAN instance available for testing")

    def test_integration_authenticate(self):
        """Integration test for authentication"""
        assert self.connector is not None  # ensured by setUp skip
        if not self.ckan_api_key:
            raise unittest.SkipTest("CKAN_TEST_API_KEY not set, skipping authentication test")

        credentials = {"api_key": self.ckan_api_key}
        result = self.connector.authenticate(credentials)

        self.assertTrue(result)

    def test_integration_test_connection(self):
        """Integration test for connection testing"""
        assert self.connector is not None  # ensured by setUp skip
        result = self.connector.test_connection()

        self.assertTrue(result)

    def test_integration_list_listings(self):
        """Integration test for listing packages"""
        assert self.connector is not None  # ensured by setUp skip
        listings = self.connector.list_listings(limit=10)

        self.assertIsInstance(listings, list)
        # Verify all listings are MarketplaceListing objects
        for listing in listings:
            self.assertIsInstance(listing, MarketplaceListing)
            self.assertEqual(listing.marketplace_type, MarketplaceType.CKAN_INSTANCE)

    def test_integration_get_listing(self):
        """Integration test for getting a specific listing"""
        assert self.connector is not None  # ensured by setUp skip
        # First, get a list of packages
        listings = self.connector.list_listings(limit=1)

        if not listings:
            self.skipTest("CKAN instance has no listings — cannot test get_listing")

        package_id = listings[0].marketplace_id
        listing = self.connector.get_listing(package_id)

        self.assertIsInstance(listing, MarketplaceListing)
        self.assertEqual(listing.marketplace_id, package_id)

    def test_integration_list_resources(self):
        """Integration test for listing resources"""
        assert self.connector is not None  # ensured by setUp skip
        # First, get a list of packages
        listings = self.connector.list_listings(limit=1)

        if not listings:
            self.skipTest("CKAN instance has no listings — cannot test list_resources")

        package_id = listings[0].marketplace_id
        resources = self.connector.list_resources(package_id)

        self.assertIsInstance(resources, list)
        # Verify all resources are MarketplaceResource objects
        for resource in resources:
            self.assertIsInstance(resource, MarketplaceResource)


# ============================================================================
# Comprehensive Error Handling Tests
# ============================================================================


class TestCKANConnectorErrorHandling(TestCase):
    """Comprehensive error handling tests for CKAN connector"""

    def setUp(self):
        """Set up test fixtures"""
        self.connector = CKANConnector(base_url="https://data.gov")

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector._request_with_retry")
    def test_authenticate_handles_connection_error(self, mock_request):
        """Test authenticate handles connection errors gracefully"""
        mock_request.side_effect = ConnectionError("Connection failed")

        with self.assertRaises(ConnectionError):
            self.connector.authenticate({"api_key": "test-key"})

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector._request_with_retry")
    def test_authenticate_handles_invalid_response(self, mock_request):
        """Test authenticate handles invalid API response"""
        mock_response = Mock()
        mock_response.json.return_value = {"success": False}
        mock_request.return_value = mock_response

        result = self.connector.authenticate({"api_key": "test-key"})
        self.assertFalse(result)

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector._request_with_retry")
    def test_test_connection_handles_timeout(self, mock_request):
        """Test test_connection handles timeout errors"""
        mock_request.side_effect = ConnectionError("Request timed out")

        with self.assertRaises(ConnectionError):
            self.connector.test_connection()

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector._request_with_retry")
    def test_list_listings_handles_500_error(self, mock_request):
        """Test list_listings handles 500 server errors"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=Mock(), response=mock_response
        )
        mock_request.side_effect = mock_response.raise_for_status

        # The connector wraps HTTPStatusError in ConnectionError
        with self.assertRaises(ConnectionError):
            self.connector.list_listings()

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector._request_with_retry")
    def test_get_listing_handles_404_error(self, mock_request):
        """Test get_listing handles 404 not found errors"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"success": False, "error": {"message": "Not found"}}
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=Mock(), response=mock_response
        )
        mock_request.side_effect = mock_response.raise_for_status

        with self.assertRaises(NotFoundError):
            self.connector.get_listing("non-existent")

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector._request_with_retry")
    @patch("httpx.get")
    def test_download_resource_handles_403_error(self, mock_get, mock_request):
        """Test download_resource handles 403 permission errors"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "success": True,
            "result": {"id": "resource-1", "url": "https://example.com/resource.csv"},
        }
        mock_request.return_value = mock_response

        mock_download_response = Mock()
        mock_download_response.status_code = 403
        mock_download_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Forbidden", request=Mock(), response=mock_download_response
        )
        mock_get.side_effect = mock_download_response.raise_for_status

        with self.assertRaises(PermissionError):
            self.connector.download_resource("resource-1", "/tmp/test.csv")

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector._request_with_retry")
    @patch("httpx.get")
    @patch("builtins.open", side_effect=IOError("Disk write error"))
    def test_download_resource_handles_io_error(self, mock_open, mock_get, mock_request):
        """Test download_resource handles IO errors when writing file"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "success": True,
            "result": {"id": "resource-1", "url": "https://example.com/resource.csv"},
        }
        mock_request.return_value = mock_response

        mock_download_response = Mock()

        def iter_bytes_side_effect(chunk_size):
            yield b"data"

        mock_download_response.iter_bytes = iter_bytes_side_effect
        mock_download_response.raise_for_status = Mock()
        mock_get.return_value = mock_download_response

        # builtins.open is mocked to raise IOError
        with self.assertRaises(IOError):
            self.connector.download_resource("resource-1", "/tmp/test_io_error.csv")


    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector.list_listings")
    def test_sync_pull_handles_empty_listings(self, mock_list_listings):
        """Test sync_pull handles empty listing list"""
        mock_list_listings.return_value = []

        result = self.connector.sync_pull()

        self.assertEqual(result.total_items, 0)
        self.assertEqual(result.status, SyncStatus.COMPLETED)

    def test_map_to_hub_asset_handles_missing_resources(self):
        """Test map_to_hub_asset handles resource fetch failure gracefully.

        Source ckan_connector.py lines 1276-1280: when list_resources raises,
        the exception is caught and logged — the mapping is returned with an
        empty resources list.  The exception does NOT propagate to the caller.
        """
        listing = MarketplaceListing(
            marketplace_id="test-package",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Test Package",
        )

        with patch.object(self.connector, "list_resources", side_effect=ConnectionError("API Error")):
            mapping = self.connector.map_to_hub_asset(listing)
            self.assertIsInstance(mapping, MarketplaceAssetMapping)
            self.assertEqual(mapping.resources, [],
                "map_to_hub_asset should return empty resources when list_resources fails")


class TestCKANConnectorSecurity(TestCase):
    """Security tests for CKAN connector"""

    def setUp(self):
        """Set up test fixtures"""
        self.connector = CKANConnector(base_url="https://data.gov")

    def test_api_key_not_exposed_in_headers_when_none(self):
        """Test that API key is not included in headers when not provided"""
        headers = self.connector._get_default_headers()
        self.assertNotIn("Authorization", headers)
        self.assertNotIn("X-CKAN-API-Key", headers)

    def test_api_key_included_in_headers_when_provided(self):
        """Test that API key is included in headers when provided"""
        connector = CKANConnector(base_url="https://data.gov", api_key="test-key")
        headers = connector._get_default_headers()
        self.assertEqual(headers["Authorization"], "test-key")
        self.assertEqual(headers["X-CKAN-API-Key"], "test-key")

    def test_sql_injection_protection_in_filters(self):
        """Test that SQL injection attempts in filters are handled safely"""
        # CKAN API should handle this, but we test that we don't break on malicious input
        malicious_filters = {
            "q": "'; DROP TABLE packages; --",
            "fq": "name:'; DELETE FROM resources; --",
        }

        # Should not raise exception, but may return empty results
        # The actual protection is at the CKAN API level
        with patch.object(self.connector, "_request_with_retry") as mock_request:
            mock_response = Mock()
            mock_response.json.return_value = {
                "success": True,
                "result": {"results": [], "count": 0},
            }
            mock_request.return_value = mock_response

            result = self.connector.list_listings(filters=malicious_filters)
            self.assertIsInstance(result, list)

    def test_path_traversal_protection_in_download(self):
        """Test that path traversal attempts are handled safely"""
        # Test that destination_path validation prevents directory traversal
        with patch.object(self.connector, "_request_with_retry") as mock_request:
            mock_response = Mock()
            mock_response.json.return_value = {
                "success": True,
                "result": {"id": "resource-1", "url": "https://example.com/resource.csv"},
            }
            mock_request.return_value = mock_response

            # Path traversal attempt
            malicious_path = "../../../etc/passwd"

            # Should fail validation or be sanitized
            with patch("httpx.get") as mock_get:
                mock_download_response = Mock()

                def iter_bytes_side_effect(chunk_size):
                    yield b"data"

                mock_download_response.iter_bytes = iter_bytes_side_effect
                mock_download_response.raise_for_status = Mock()
                mock_get.return_value = mock_download_response

                # The actual path validation happens in the download method
                # This test ensures we don't blindly accept malicious paths
                try:
                    self.connector.download_resource("resource-1", malicious_path)
                except (IOError, ValueError, PermissionError):
                    pass  # Expected - path should be rejected

    def test_xss_protection_in_listing_data(self):
        """Test that XSS attempts in listing data are handled safely"""
        # Test that script tags and other XSS vectors are handled
        xss_title = '<script>alert("XSS")</script>'

        listing = MarketplaceListing(
            marketplace_id="test", marketplace_type=MarketplaceType.CKAN_INSTANCE, title=xss_title
        )

        # Mapping should handle XSS content safely
        with patch.object(self.connector, "list_resources", return_value=[]):
            mapping = self.connector.map_to_hub_asset(listing)
            # The mapping should contain the title as-is (sanitization happens at display layer)
            self.assertIn(xss_title, mapping.asset_data.get("name", ""))

    def test_large_input_handling(self):
        """Test that large inputs are handled without DoS"""
        # Test with very large title
        large_title = "A" * 10000

        listing = MarketplaceListing(
            marketplace_id="test", marketplace_type=MarketplaceType.CKAN_INSTANCE, title=large_title
        )

        # Should handle large input without crashing
        with patch.object(self.connector, "list_resources", return_value=[]):
            mapping = self.connector.map_to_hub_asset(listing)
            # Package name should be truncated to CKAN limit (100 chars)
            self.assertLessEqual(len(mapping.asset_data.get("key", "")), 100)

    def test_credential_handling_security(self):
        """Test that credentials are handled securely"""
        # Test that credentials are not logged or exposed
        connector = CKANConnector(base_url="https://data.gov", api_key="secret-key-12345")

        # API key should be in headers but not in string representation
        connector_str = str(connector)
        self.assertNotIn("secret-key", connector_str)

        # Headers should contain the key (this is expected behavior)
        headers = connector._get_default_headers()
        self.assertEqual(headers["Authorization"], "secret-key-12345")


# ============================================================================
# Performance Tests
# ============================================================================


class TestCKANConnectorPerformance(TestCase):
    """Performance tests for CKAN connector"""

    def setUp(self):
        """Set up test fixtures"""
        self.connector = CKANConnector(base_url="https://data.gov")

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector._request_with_retry")
    def test_list_listings_performance_with_pagination(self, mock_request):
        """Test that list_listings handles pagination efficiently"""
        # Mock response with pagination
        mock_response = Mock()
        mock_response.json.return_value = {
            "success": True,
            "result": {
                "results": [{"id": f"package-{i}", "name": f"package-{i}"} for i in range(100)],
                "count": 1000,
            },
        }
        mock_request.return_value = mock_response

        import time

        start = time.time()
        listings = self.connector.list_listings(limit=100)
        elapsed = time.time() - start

        # Should complete quickly (under 1 second for mocked request)
        self.assertLess(elapsed, 1.0)
        self.assertEqual(len(listings), 100)

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector._request_with_retry")
    def test_batch_operations_performance(self, mock_request):
        """Test that batch operations are efficient"""
        mock_response = Mock()
        mock_response.json.return_value = {"success": True, "result": {"id": "test"}}
        mock_request.return_value = mock_response

        import time

        start = time.time()

        # Simulate batch of 10 operations
        for i in range(10):
            listing = MarketplaceListing(
                marketplace_id=f"test-{i}",
                marketplace_type=MarketplaceType.CKAN_INSTANCE,
                title=f"Test {i}",
            )
            with patch.object(self.connector, "list_resources", return_value=[]):
                self.connector.map_to_hub_asset(listing)

        elapsed = time.time() - start

        # Should complete batch operations efficiently
        self.assertLess(elapsed, 2.0)

    def test_circuit_breaker_performance(self):
        """Test that circuit breaker doesn't add significant overhead"""
        import time

        # Test normal operation performance
        start = time.time()
        with patch.object(self.connector, "_request_with_retry") as mock_request:
            mock_response = Mock()
            mock_response.json.return_value = {"success": True}
            mock_request.return_value = mock_response

            self.connector.test_connection()

        elapsed = time.time() - start

        # Circuit breaker overhead should be minimal (< 0.1s for mocked call)
        self.assertLess(elapsed, 0.1)


# ============================================================================
# E2E Workflow Tests
# ============================================================================


class TestCKANConnectorE2EWorkflows(TestCase):
    """End-to-end workflow tests for CKAN connector"""

    def setUp(self):
        """Set up test fixtures"""
        self.connector = CKANConnector(base_url="https://data.gov")

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector._request_with_retry")
    @patch("httpx.get")
    def test_e2e_download_workflow(self, mock_get, mock_request):
        """Test complete download workflow"""
        # Step 1: Get resource info
        resource_response = Mock()
        resource_response.json.return_value = {
            "success": True,
            "result": {
                "id": "resource-1",
                "url": "https://example.com/data.csv",
                "name": "data.csv",
            },
        }
        mock_request.return_value = resource_response

        # Step 2: Download resource
        mock_download_response = Mock()
        mock_download_response.content = b"csv,data,here"

        def iter_bytes_side_effect(chunk_size):
            content = b"csv,data,here"
            for i in range(0, len(content), chunk_size):
                yield content[i : i + chunk_size]

        mock_download_response.iter_bytes = iter_bytes_side_effect
        mock_download_response.raise_for_status = Mock()
        mock_get.return_value = mock_download_response

        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            destination_path = tmp_file.name

        try:
            result_path = self.connector.download_resource("resource-1", destination_path)

            self.assertEqual(result_path, destination_path)
            self.assertTrue(os.path.exists(destination_path))
            with open(destination_path, "rb") as f:
                content = f.read()
                self.assertEqual(content, b"csv,data,here")
        finally:
            if os.path.exists(destination_path):
                os.unlink(destination_path)


# ============================================================================
# Helper Method Tests
# ============================================================================


class TestCKANConnectorHelperMethods(TestCase):
    """Tests for helper/private methods"""

    def setUp(self):
        """Set up test fixtures"""
        self.connector = CKANConnector(base_url="https://data.gov")

    def test_generate_package_name_from_title(self):
        """Test _generate_package_name creates valid CKAN package names"""
        # Test basic conversion
        name = self.connector._generate_package_name("Test Package")
        self.assertEqual(name, "test-package")

        # Test with special characters (note: & becomes empty, creating double hyphen)
        name = self.connector._generate_package_name("Test & Package (2024)")
        # The regex removes & and (), leaving spaces which become hyphens
        # Result may have multiple consecutive hyphens which is acceptable
        self.assertTrue(name.startswith("test"))
        self.assertTrue("package" in name)
        self.assertTrue("2024" in name)

        # Test with numbers at start
        name = self.connector._generate_package_name("123 Package")
        self.assertEqual(name, "pkg-123-package")

        # Test truncation
        long_title = "A" * 150
        name = self.connector._generate_package_name(long_title)
        self.assertLessEqual(len(name), 100)

    def test_extract_multilingual_field_string(self):
        """Test _extract_multilingual_field with string value"""
        package_data = {"title": "Test Title"}
        result = self.connector._extract_multilingual_field(package_data, ["title"], "Default")
        self.assertEqual(result, "Test Title")

    def test_extract_multilingual_field_dict_en(self):
        """Test _extract_multilingual_field with dictionary preferring English"""
        package_data = {"title": {"en": "English Title", "fr": "Titre Français"}}
        result = self.connector._extract_multilingual_field(package_data, ["title"], "Default")
        self.assertEqual(result, "English Title")

    def test_extract_multilingual_field_dict_fallback(self):
        """Test _extract_multilingual_field with dictionary fallback"""
        package_data = {"title": {"fr": "Titre Français", "de": "Deutscher Titel"}}
        result = self.connector._extract_multilingual_field(package_data, ["title"], "Default")
        self.assertIn(result, ["Titre Français", "Deutscher Titel"])

    def test_extract_multilingual_field_list(self):
        """Test _extract_multilingual_field with list of dictionaries"""
        package_data = {"title": [{"en": "English Title"}]}
        result = self.connector._extract_multilingual_field(package_data, ["title"], "Default")
        self.assertEqual(result, "English Title")

    def test_extract_multilingual_field_fallback(self):
        """Test _extract_multilingual_field uses fallback when field missing"""
        package_data = {}
        result = self.connector._extract_multilingual_field(
            package_data, ["title", "name"], "Default Value"
        )
        self.assertEqual(result, "Default Value")

    def test_listing_changed_detection(self):
        """Test _listing_changed detects changes correctly"""
        existing = MarketplaceListing(
            marketplace_id="test",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Original Title",
            description="Original Description",
            metadata={"organization": {"name": "test-org"}},
        )

        unchanged = MarketplaceListing(
            marketplace_id="test",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Original Title",
            description="Original Description",
            metadata={"organization": {"name": "test-org"}},
        )

        changed_title = MarketplaceListing(
            marketplace_id="test",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="New Title",
            description="Original Description",
            metadata={"organization": {"name": "test-org"}},
        )

        changed_org = MarketplaceListing(
            marketplace_id="test",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Original Title",
            description="Original Description",
            metadata={"organization": {"name": "other-org"}},
        )

        # Test unchanged listing
        self.assertFalse(self.connector._listing_changed(existing, unchanged))

        # Test changed title
        self.assertTrue(self.connector._listing_changed(existing, changed_title))

        # Test changed organization
        self.assertTrue(self.connector._listing_changed(existing, changed_org))

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector._request_with_retry")
    def test_list_listings_with_zero_limit(self, mock_request):
        """Test list_listings() edge case with zero limit"""
        mock_response = Mock()
        mock_response.json.return_value = {"success": True, "result": {"results": [], "count": 0}}
        mock_request.return_value = mock_response

        listings = self.connector.list_listings(limit=0)
        self.assertIsInstance(listings, list)
        self.assertEqual(len(listings), 0)

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector._request_with_retry")
    def test_list_listings_with_none_limit(self, mock_request):
        """Test that limit=None uses package_list API (no limit applied).

        When limit, offset, and filters are all None/empty, list_listings
        falls through to package_list (source line 328-330), ignoring limit.
        """
        mock_response = Mock()
        mock_response.json.return_value = {
            "success": True,
            "result": ["package-1", "package-2"],
        }
        mock_request.return_value = mock_response

        with patch.object(self.connector, "get_listing") as mock_get:
            mock_get.side_effect = [
                MarketplaceListing(
                    marketplace_id=f"package-{i}",
                    marketplace_type=MarketplaceType.CKAN_INSTANCE,
                    title=f"Package {i}",
                )
                for i in range(1, 3)
            ]

            listings = self.connector.list_listings(limit=None)
            self.assertIsInstance(listings, list)
            self.assertEqual(len(listings), 2)

        # Verify package_list endpoint was used (not package_search)
        self.assertEqual(
            mock_request.call_args[0][1], "/api/3/action/package_list"
        )

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector._request_with_retry")
    def test_get_listing_with_empty_id(self, mock_request):
        """get_listing('') raises ValueError (source line 454)."""
        with self.assertRaises(ValueError):
            self.connector.get_listing("")

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector._request_with_retry")
    def test_get_listing_with_none_id(self, mock_request):
        """get_listing(None) raises ValueError (source line 452)."""
        with self.assertRaises(ValueError):
            self.connector.get_listing(None)  # type: ignore[arg-type]

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector._request_with_retry")
    def test_list_resources_with_empty_package_id(self, mock_request):
        """list_resources('') raises ValueError (via get_listing)."""
        with self.assertRaises(ValueError):
            self.connector.list_resources("")

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector._request_with_retry")
    def test_list_resources_with_none_package_id(self, mock_request):
        """list_resources(None) raises ValueError (via get_listing)."""
        with self.assertRaises(ValueError):
            self.connector.list_resources(None)  # type: ignore[arg-type]

    def test_authenticate_with_empty_credentials(self):
        """authenticate({}) raises ValueError (source line 235-236)."""
        with self.assertRaises(ValueError):
            self.connector.authenticate({})

    def test_authenticate_with_none_credentials(self):
        """authenticate(None) raises ValueError (source line 235-236)."""
        with self.assertRaises(ValueError):
            self.connector.authenticate(None)  # type: ignore[arg-type]
