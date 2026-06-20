"""
Unit tests for DadosGovBrConnector.

Tests Swagger-based connector for dados.gov.br implementing DataMarketplaceConnector interface.
Follows TDD approach - tests written before implementation.
"""

from unittest.mock import patch

import pytest

from hub.apps.core.services.base import ConnectionError, NotFoundError
from hub.apps.integrations.base import (
    MarketplaceListing,
    MarketplaceResource,
    MarketplaceType,
    SyncDirection,
)
from hub.apps.integrations.connectors.dados_gov_br_connector import DadosGovBrConnector


class TestDadosGovBrConnector:
    """Test suite for DadosGovBrConnector."""

    def test_init_with_base_url_and_token(self):
        """Test connector initialization."""
        connector = DadosGovBrConnector(base_url="https://dados.gov.br", jwt_token="test-token-123")
        assert connector.base_url == "https://dados.gov.br"
        assert connector.client is not None

    def test_marketplace_type_is_ckan_instance(self):
        """Test that marketplace type is CKAN_INSTANCE for compatibility."""
        connector = DadosGovBrConnector(base_url="https://dados.gov.br", jwt_token="test-token")
        assert connector.marketplace_type == MarketplaceType.CKAN_INSTANCE

    def test_supported_sync_directions_is_pull_only(self):
        """Test that connector supports only PULL (harvest-only)."""
        connector = DadosGovBrConnector(base_url="https://dados.gov.br", jwt_token="test-token")
        assert connector.supported_sync_directions == [SyncDirection.PULL]

    def test_list_listings_with_filters(self):
        """Test listing datasets with filters."""
        connector = DadosGovBrConnector(base_url="https://dados.gov.br", jwt_token="test-token")

        mock_datasets = [
            {"id": "dataset-1", "name": "Dataset 1", "title": "Test Dataset 1"},
            {"id": "dataset-2", "name": "Dataset 2", "title": "Test Dataset 2"},
        ]

        # API returns direct array according to Swagger spec
        mock_client_response = mock_datasets

        with patch.object(connector.client, "search_datasets") as mock_search:
            mock_search.return_value = mock_client_response

            listings = connector.list_listings(filters={"q": "test"}, limit=10, offset=0)

            assert len(listings) == 2
            assert all(isinstance(l, MarketplaceListing) for l in listings)
            assert listings[0].marketplace_id == "dataset-1"
            assert listings[0].title == "Test Dataset 1"

    def test_get_listing_by_id(self):
        """Test getting a specific listing by ID."""
        connector = DadosGovBrConnector(base_url="https://dados.gov.br", jwt_token="test-token")

        mock_dataset = {
            "id": "test-dataset",
            "name": "test-dataset",
            "title": "Test Dataset",
            "notes": "Test description",
        }

        mock_client_response = {"success": True, "result": mock_dataset}

        with patch.object(connector.client, "get_dataset") as mock_get:
            mock_get.return_value = mock_client_response

            listing = connector.get_listing("test-dataset")

            assert isinstance(listing, MarketplaceListing)
            assert listing.marketplace_id == "test-dataset"
            assert listing.title == "Test Dataset"

    def test_get_listing_raises_not_found_error(self):
        """Test that get_listing raises NotFoundError for non-existent dataset."""
        connector = DadosGovBrConnector(base_url="https://dados.gov.br", jwt_token="test-token")

        mock_client_response = {"success": False, "error": {"message": "Not found"}}

        with patch.object(connector.client, "get_dataset") as mock_get:
            mock_get.return_value = mock_client_response

            with pytest.raises(NotFoundError):
                connector.get_listing("non-existent")

    def test_list_resources_for_dataset(self):
        """Test listing resources for a dataset."""
        connector = DadosGovBrConnector(base_url="https://dados.gov.br", jwt_token="test-token")

        mock_dataset = {
            "id": "test-dataset",
            "resources": [
                {"id": "resource-1", "name": "Resource 1", "url": "https://example.com/r1.csv"},
                {"id": "resource-2", "name": "Resource 2", "url": "https://example.com/r2.json"},
            ],
        }

        mock_client_response = {"success": True, "result": mock_dataset}

        with patch.object(connector.client, "get_dataset") as mock_get:
            mock_get.return_value = mock_client_response

            resources = connector.list_resources("test-dataset")

            assert len(resources) == 2
            assert all(isinstance(r, MarketplaceResource) for r in resources)
            assert resources[0].resource_id == "resource-1"

    def test_test_connection_success(self):
        """Test connection test with successful response."""
        connector = DadosGovBrConnector(base_url="https://dados.gov.br", jwt_token="test-token")

        # API returns direct array according to Swagger spec (empty array for test)
        mock_client_response = []

        with patch.object(connector.client, "search_datasets") as mock_search:
            mock_search.return_value = mock_client_response

            result = connector.test_connection()

            assert result is True

    def test_test_connection_failure(self):
        """Test connection test with failure."""
        connector = DadosGovBrConnector(base_url="https://dados.gov.br", jwt_token="test-token")

        with patch.object(connector.client, "search_datasets") as mock_search:
            mock_search.side_effect = ConnectionError("Connection failed")

            with pytest.raises(ConnectionError):
                connector.test_connection()

    def test_swagger_dataset_to_listing_mapping(self):
        """Test mapping Swagger dataset response to MarketplaceListing."""
        connector = DadosGovBrConnector(base_url="https://dados.gov.br", jwt_token="test-token")

        swagger_dataset = {
            "id": "test-dataset",
            "name": "test-dataset",
            "title": "Test Dataset",
            "notes": "Test description",
            "tags": [{"name": "tag1"}, {"name": "tag2"}],
            "organization": {"name": "test-org"},
            "metadata_created": "2024-01-01T00:00:00",
            "metadata_modified": "2024-01-02T00:00:00",
        }

        listing = connector._swagger_dataset_to_listing(swagger_dataset)

        assert isinstance(listing, MarketplaceListing)
        assert listing.marketplace_id == "test-dataset"
        assert listing.title == "Test Dataset"
        assert listing.description == "Test description"
        assert listing.category == "test-org"
        assert len(listing.tags) == 2
        assert "tag1" in listing.tags

    def test_swagger_resource_to_marketplace_resource_mapping(self):
        """Test mapping Swagger resource response to MarketplaceResource."""
        connector = DadosGovBrConnector(base_url="https://dados.gov.br", jwt_token="test-token")

        swagger_resource = {
            "id": "test-resource",
            "name": "Test Resource",
            "description": "Resource description",
            "url": "https://example.com/resource.csv",
            "format": "CSV",
            "size": 1024,
        }

        resource = connector._swagger_resource_to_marketplace_resource(swagger_resource)

        assert isinstance(resource, MarketplaceResource)
        assert resource.resource_id == "test-resource"
        assert resource.name == "Test Resource"
        assert resource.url == "https://example.com/resource.csv"
        assert resource.format == "CSV"
