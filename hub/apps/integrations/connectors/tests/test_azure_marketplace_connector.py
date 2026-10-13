"""
Tests for the Azure Marketplace (Commercial Marketplace) connector.

All mocked tests patch ``httpx.Client`` (unittest.mock) — no network I/O and
no live credentials. Error-mapping tests use real ``httpx.Response`` objects
so ``raise_for_status()`` raises genuine ``httpx.HTTPStatusError`` instances,
exercising the connector's real error branches.

The live smoke test (``TestAzureMarketplaceConnectorLive``) is gated on
``AZURE_MARKETPLACE_API_KEY`` (or ``AZURE_CATALOG_API_KEY``) through the W16
environment policy: a missing key skips locally and fails the CI run loudly.

The connector is harvest-only: the Catalog API surface is
``list_listings()`` / ``get_listing()`` (List Products / Get Product).
``create_listing`` / ``update_listing`` / ``publish_resource`` / ``sync_push``
raise ``NotImplementedError``.
"""

import os
from unittest import TestCase
from unittest.mock import Mock, patch

import httpx
import pytest

from envpolicy import skip_or_fail
from hub.apps.assets.models import AssetSourceType
from hub.apps.core.services.base import ConnectionError, NotFoundError
from hub.apps.integrations.base import (
    MarketplaceListing,
    MarketplaceResource,
    MarketplaceType,
    SyncDirection,
    SyncStatus,
)
from hub.apps.integrations.connectors.azure_marketplace_connector import (
    DEFAULT_API_VERSION,
    DEFAULT_BASE_URL,
    AzureMarketplaceConnector,
)

# Azure Catalog API-shaped product payload (fields the connector actually parses).
SAMPLE_PRODUCT = {
    "displayName": "Test Data Product",
    "uniqueProductId": "test-publisher.test-data-product",
    "productId": "test-data-product-001",
    "description": "A test data product for connector tests.",
    "summary": "Test data product summary",
    "longSummary": "Long summary for test.",
    "publisherId": "test-publisher",
    "publisherDisplayName": "Test Publisher",
    "productType": "Data",
    "productFamily": "Data",
    "serviceFamily": "Analytics",
    "categoryIds": ["analytics", "data"],
    "industryIds": ["retail"],
    "pricingTypes": ["Free", "Payg"],
    "startingPrice": {
        "market": "US",
        "currency": "USD",
        "minTermPrice": 0,
        "minMeterPrice": 0.01,
    },
    "lastModifiedDateTime": "2025-01-15T12:00:00Z",
    "plans": [
        {
            "planId": "standard",
            "uniquePlanId": "test-data-product-standard",
            "displayName": "Standard",
            "description": "Standard plan",
            "summary": "Standard plan summary",
        }
    ],
}

SAMPLE_PRODUCTS_RESPONSE = {"value": [SAMPLE_PRODUCT]}
SAMPLE_PRODUCT_ID = SAMPLE_PRODUCT["uniqueProductId"]


def _response(status_code, json_body=None, *, url=DEFAULT_BASE_URL + "/products"):
    """Build a real httpx.Response so raise_for_status() raises real HTTPStatusError."""
    request = httpx.Request("GET", url)
    return httpx.Response(status_code, json=json_body, request=request)


@pytest.fixture
def mocked_http():
    """Patch httpx.Client so no connector test performs real network I/O."""
    with patch("httpx.Client") as mock_client_class:
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        yield mock_client_class, mock_client


# Snapshot the credential at IMPORT time: a mid-session os.environ mutation
# from another test file must not flip this guard into running a real HTTP
# call (test-order determinism — see the test_ckan_env_config.py leak fix).
_AZURE_LIVE_KEY_AT_IMPORT = os.getenv("AZURE_MARKETPLACE_API_KEY") or os.getenv(
    "AZURE_CATALOG_API_KEY"
)


def _azure_live_config():
    """Resolve live-API config; missing key follows the W16 environment policy."""
    api_key = _AZURE_LIVE_KEY_AT_IMPORT
    if not api_key:
        skip_or_fail(
            "AZURE_MARKETPLACE_API_KEY (or AZURE_CATALOG_API_KEY) environment variable is required"
        )
    base_url = os.getenv("AZURE_CATALOG_BASE_URL", DEFAULT_BASE_URL)
    return base_url, api_key


class TestAzureMarketplaceConnectorInit:
    """Constructor defaults and config precedence."""

    def test_defaults_when_no_arguments(self):
        connector = AzureMarketplaceConnector()
        assert connector._base_url == DEFAULT_BASE_URL
        assert connector._api_version == DEFAULT_API_VERSION
        assert connector._api_key == ""

    def test_kwargs_override_config_values(self):
        connector = AzureMarketplaceConnector(
            base_url="https://catalog.example.com",
            api_key="kw-key",
            api_version="2024-01-01",
            config={
                "base_url": "https://config.example.com",
                "api_key": "config-key",
                "api_version": "2023-01-01",
            },
        )
        assert connector._base_url == "https://catalog.example.com"
        assert connector._api_key == "kw-key"
        assert connector._api_version == "2024-01-01"

    def test_config_provides_values_when_kwargs_absent(self):
        connector = AzureMarketplaceConnector(
            config={
                "base_url": "https://catalogapi.azure.com",
                "api_key": "config-key",
                "api_version": "2025-05-01",
            }
        )
        assert connector._base_url == "https://catalogapi.azure.com"
        assert connector._api_key == "config-key"
        assert connector._api_version == "2025-05-01"

    def test_empty_config_falls_back_to_defaults(self):
        connector = AzureMarketplaceConnector(config={})
        assert connector._base_url == DEFAULT_BASE_URL
        assert connector._api_key == ""
        assert connector._api_version == DEFAULT_API_VERSION

    def test_trailing_slash_stripped_from_base_url(self):
        connector = AzureMarketplaceConnector(base_url="https://catalogapi.azure.com/")
        assert connector._base_url == "https://catalogapi.azure.com"

    def test_marketplace_type(self):
        assert AzureMarketplaceConnector().marketplace_type == MarketplaceType.AZURE_MARKETPLACE

    def test_supported_sync_directions_pull_only(self):
        directions = AzureMarketplaceConnector().supported_sync_directions
        assert directions == [SyncDirection.PULL]

    def test_http_client_created_once_and_cached(self, mocked_http):
        mock_client_class, mock_client = mocked_http
        connector = AzureMarketplaceConnector(base_url="https://catalogapi.azure.com")

        first = connector._get_client()
        second = connector._get_client()

        assert first is mock_client
        assert first is second
        assert mock_client_class.call_count == 1
        client_kwargs = mock_client_class.call_args.kwargs
        assert client_kwargs["base_url"] == "https://catalogapi.azure.com"
        assert client_kwargs["timeout"] == 30


class TestAzureMarketplaceConnectorHeaders:
    """X-API-Key header behavior."""

    def test_no_api_key_header_without_key(self, mocked_http):
        mock_client_class, _ = mocked_http
        connector = AzureMarketplaceConnector(base_url="https://catalogapi.azure.com")

        connector._get_client()

        headers = mock_client_class.call_args.kwargs["headers"]
        assert headers == {"Accept": "application/json"}
        assert "X-API-Key" not in headers

    def test_x_api_key_header_sent_when_key_set(self, mocked_http):
        mock_client_class, _ = mocked_http
        connector = AzureMarketplaceConnector(
            base_url="https://catalogapi.azure.com", api_key="secret-key"
        )

        connector._get_client()

        headers = mock_client_class.call_args.kwargs["headers"]
        assert headers["X-API-Key"] == "secret-key"
        assert headers["Accept"] == "application/json"
        # Azure Catalog API authenticates via X-API-Key, never Authorization.
        assert "Authorization" not in headers


class TestAzureMarketplaceConnectorAuthenticate:
    """authenticate() credential validation and client reset."""

    def test_empty_credentials_raises_value_error(self, mocked_http):
        connector = AzureMarketplaceConnector()
        with pytest.raises(ValueError, match="Credentials dictionary is required"):
            connector.authenticate({})

    def test_missing_api_key_raises_value_error(self, mocked_http):
        connector = AzureMarketplaceConnector()
        with pytest.raises(ValueError, match="api_key or X-API-Key is required"):
            connector.authenticate({"other": "value"})

    def test_accepts_x_api_key_header_name(self, mocked_http):
        _, mock_client = mocked_http
        mock_client.get.return_value = _response(200, SAMPLE_PRODUCTS_RESPONSE)
        connector = AzureMarketplaceConnector()

        result = connector.authenticate({"X-API-Key": "header-key"})

        assert result is True
        assert connector._api_key == "header-key"

    def test_success_sets_key_and_returns_true(self, mocked_http):
        _, mock_client = mocked_http
        mock_client.get.return_value = _response(200, SAMPLE_PRODUCTS_RESPONSE)
        connector = AzureMarketplaceConnector()

        result = connector.authenticate({"api_key": "new-key"})

        assert result is True
        assert connector._api_key == "new-key"
        # authenticate() runs test_connection(): GET /products with $top=1.
        call = mock_client.get.call_args
        assert call is not None
        assert call.args[0] == "/products"
        assert call.kwargs["params"] == {"api-version": DEFAULT_API_VERSION, "$top": 1}

    def test_authenticate_resets_existing_client(self, mocked_http):
        mock_client_class, mock_client = mocked_http
        mock_client.get.return_value = _response(200, SAMPLE_PRODUCTS_RESPONSE)
        connector = AzureMarketplaceConnector(api_key="old-key")
        connector._get_client()

        connector.authenticate({"api_key": "new-key"})

        # Old client closed, new client created with the new key.
        mock_client.close.assert_called_once()
        assert mock_client_class.call_count == 2
        headers = mock_client_class.call_args.kwargs["headers"]
        assert headers["X-API-Key"] == "new-key"


class TestAzureMarketplaceConnectorDiscovery:
    """Request shape and JSON passthrough for list_listings() / get_listing()."""

    def test_list_listings_request_shape_and_mapping(self, mocked_http):
        _, mock_client = mocked_http
        mock_client.get.return_value = _response(200, SAMPLE_PRODUCTS_RESPONSE)
        connector = AzureMarketplaceConnector(api_key="key")

        listings = connector.list_listings(
            filters={"productType": "Data", "search": "covid", "$expand": "plans"},
            limit=25,
            offset=10,
        )

        call = mock_client.get.call_args
        assert call is not None
        assert call.args[0] == "/products"
        assert call.kwargs["params"] == {
            "api-version": DEFAULT_API_VERSION,
            "$top": 25,
            "$skip": 10,
            "$filter": "productType eq 'Data'",
            "$search": "covid",
            "$expand": "plans",
        }

        assert len(listings) == 1
        listing = listings[0]
        assert listing.marketplace_type == MarketplaceType.AZURE_MARKETPLACE
        assert listing.marketplace_id == SAMPLE_PRODUCT_ID
        assert listing.title == "Test Data Product"
        assert listing.description == "A test data product for connector tests."
        assert listing.metadata["publisherId"] == "test-publisher"
        assert len(listing.resources) == 1
        assert listing.resources[0].resource_type == "PLAN"
        assert listing.resources[0].name == "Standard"

    def test_list_listings_default_params(self, mocked_http):
        _, mock_client = mocked_http
        mock_client.get.return_value = _response(200, SAMPLE_PRODUCTS_RESPONSE)
        connector = AzureMarketplaceConnector()

        listings = connector.list_listings()

        call = mock_client.get.call_args
        assert call is not None
        assert call.kwargs["params"] == {"api-version": DEFAULT_API_VERSION}
        assert len(listings) == 1

    def test_list_listings_limit_capped_at_100(self, mocked_http):
        _, mock_client = mocked_http
        mock_client.get.return_value = _response(200, SAMPLE_PRODUCTS_RESPONSE)
        connector = AzureMarketplaceConnector()

        connector.list_listings(limit=500)

        assert mock_client.get.call_args.kwargs["params"]["$top"] == 100

    def test_list_listings_skips_malformed_products(self, mocked_http):
        _, mock_client = mocked_http
        mock_client.get.return_value = _response(
            200, {"value": [{"noProductId": 1}, SAMPLE_PRODUCT]}
        )
        connector = AzureMarketplaceConnector()

        listings = connector.list_listings()

        assert len(listings) == 1
        assert listings[0].marketplace_id == SAMPLE_PRODUCT_ID

    def test_get_listing_request_shape(self, mocked_http):
        _, mock_client = mocked_http
        mock_client.get.return_value = _response(200, SAMPLE_PRODUCT)
        connector = AzureMarketplaceConnector()

        listing = connector.get_listing(SAMPLE_PRODUCT_ID)

        call = mock_client.get.call_args
        assert call is not None
        assert call.args[0] == f"/products/{SAMPLE_PRODUCT_ID}"
        assert call.kwargs["params"] == {"api-version": DEFAULT_API_VERSION}
        assert listing.marketplace_id == SAMPLE_PRODUCT_ID
        assert listing.title == "Test Data Product"

    def test_get_listing_invalid_id_raises_value_error(self, mocked_http):
        connector = AzureMarketplaceConnector()
        with pytest.raises(ValueError, match="listing_id must be a non-empty string"):
            connector.get_listing("")
        with pytest.raises(ValueError, match="listing_id must be a non-empty string"):
            connector.get_listing(None)

    def test_list_resources_from_listing(self, mocked_http):
        _, mock_client = mocked_http
        mock_client.get.return_value = _response(200, SAMPLE_PRODUCT)
        connector = AzureMarketplaceConnector()

        resources = connector.list_resources(SAMPLE_PRODUCT_ID)

        assert len(resources) == 1
        assert resources[0].resource_id == f"{SAMPLE_PRODUCT_ID}/standard"
        assert resources[0].resource_type == "PLAN"
        assert resources[0].name == "Standard"


class TestAzureMarketplaceConnectorErrorMapping:
    """HTTP status / transport errors map to the connector's error types."""

    def test_list_listings_404_returns_empty_list(self, mocked_http):
        _, mock_client = mocked_http
        mock_client.get.return_value = _response(404)
        connector = AzureMarketplaceConnector()
        assert connector.list_listings() == []

    def test_list_listings_401_raises_connection_error(self, mocked_http):
        _, mock_client = mocked_http
        mock_client.get.return_value = _response(401, {"error": "Unauthorized"})
        connector = AzureMarketplaceConnector()
        with pytest.raises(ConnectionError, match="list products failed"):
            connector.list_listings()

    def test_list_listings_429_raises_connection_error(self, mocked_http):
        _, mock_client = mocked_http
        mock_client.get.return_value = _response(429, {"error": "Rate limited"})
        connector = AzureMarketplaceConnector()
        with pytest.raises(ConnectionError, match="list products failed"):
            connector.list_listings()

    def test_list_listings_5xx_raises_connection_error(self, mocked_http):
        _, mock_client = mocked_http
        mock_client.get.return_value = _response(503, {"error": "Service unavailable"})
        connector = AzureMarketplaceConnector()
        with pytest.raises(ConnectionError, match="list products failed"):
            connector.list_listings()

    def test_list_listings_request_error_raises_connection_error(self, mocked_http):
        _, mock_client = mocked_http
        mock_client.get.side_effect = httpx.RequestError("Network down")
        connector = AzureMarketplaceConnector()
        with pytest.raises(ConnectionError, match="list products failed"):
            connector.list_listings()

    def test_get_listing_404_raises_not_found_error(self, mocked_http):
        _, mock_client = mocked_http
        mock_client.get.return_value = _response(404)
        connector = AzureMarketplaceConnector()
        with pytest.raises(NotFoundError, match="Product not found"):
            connector.get_listing(SAMPLE_PRODUCT_ID)

    def test_get_listing_401_raises_connection_error(self, mocked_http):
        _, mock_client = mocked_http
        mock_client.get.return_value = _response(401, {"error": "Unauthorized"})
        connector = AzureMarketplaceConnector()
        with pytest.raises(ConnectionError, match="get product failed"):
            connector.get_listing(SAMPLE_PRODUCT_ID)

    def test_get_listing_request_error_raises_connection_error(self, mocked_http):
        _, mock_client = mocked_http
        mock_client.get.side_effect = httpx.RequestError("Network down")
        connector = AzureMarketplaceConnector()
        with pytest.raises(ConnectionError, match="get product failed"):
            connector.get_listing(SAMPLE_PRODUCT_ID)

    def test_test_connection_success(self, mocked_http):
        _, mock_client = mocked_http
        mock_client.get.return_value = _response(200, SAMPLE_PRODUCTS_RESPONSE)
        connector = AzureMarketplaceConnector()
        assert connector.test_connection() is True

    def test_test_connection_401_invalid_key(self, mocked_http):
        _, mock_client = mocked_http
        mock_client.get.return_value = _response(401, {"error": "Unauthorized"})
        connector = AzureMarketplaceConnector()
        with pytest.raises(ConnectionError, match="invalid or missing"):
            connector.test_connection()

    def test_test_connection_5xx_raises_connection_error(self, mocked_http):
        _, mock_client = mocked_http
        mock_client.get.return_value = _response(500, {"error": "Internal error"})
        connector = AzureMarketplaceConnector()
        with pytest.raises(ConnectionError, match="connection failed"):
            connector.test_connection()

    def test_test_connection_request_error_raises_connection_error(self, mocked_http):
        _, mock_client = mocked_http
        mock_client.get.side_effect = httpx.RequestError("Network down")
        connector = AzureMarketplaceConnector()
        with pytest.raises(ConnectionError, match="connection failed"):
            connector.test_connection()


class TestAzureMarketplaceConnectorClose:
    """close() idempotency and error tolerance."""

    def test_close_idempotent(self, mocked_http):
        _, mock_client = mocked_http
        connector = AzureMarketplaceConnector()
        connector._get_client()

        connector.close()
        connector.close()

        mock_client.close.assert_called_once()
        assert connector._client is None

    def test_close_without_client_is_noop(self):
        connector = AzureMarketplaceConnector()
        connector.close()
        assert connector._client is None

    def test_close_swallows_client_close_error(self, mocked_http):
        _, mock_client = mocked_http
        mock_client.close.side_effect = RuntimeError("Simulated close failure")
        connector = AzureMarketplaceConnector()
        connector._get_client()

        # Must not raise; client reference cleared even on close failure.
        connector.close()

        assert connector._client is None


class TestAzureMarketplaceConnectorPushNotSupported(TestCase):
    """Harvest-only: every push-side operation raises NotImplementedError.

    Subclasses ``unittest.TestCase`` so ``setUp`` runs before each test —
    plain pytest classes never call ``setUp``.
    """

    def setUp(self):
        self.connector = AzureMarketplaceConnector()
        self.listing = MarketplaceListing(
            marketplace_id=SAMPLE_PRODUCT_ID,
            marketplace_type=MarketplaceType.AZURE_MARKETPLACE,
            title="Test",
        )
        self.resource = MarketplaceResource(
            resource_id="res-1", resource_type="PLAN", name="Standard"
        )

    def test_create_listing_not_supported(self):
        with pytest.raises(NotImplementedError, match="create_listing"):
            self.connector.create_listing(self.listing)

    def test_update_listing_not_supported(self):
        with pytest.raises(NotImplementedError, match="update_listing"):
            self.connector.update_listing(SAMPLE_PRODUCT_ID, self.listing)

    def test_publish_resource_not_supported(self):
        with pytest.raises(NotImplementedError, match="publish_resource"):
            self.connector.publish_resource(SAMPLE_PRODUCT_ID, self.resource)

    def test_download_resource_not_supported(self):
        with pytest.raises(NotImplementedError, match="download_resource"):
            self.connector.download_resource("res-1", "/tmp/out")

    def test_sync_push_not_supported(self):
        with pytest.raises(NotImplementedError, match="sync_push"):
            self.connector.sync_push(["asset-1"])

    def test_map_from_hub_asset_not_supported(self):
        with pytest.raises(NotImplementedError, match="map_from_hub_asset"):
            self.connector.map_from_hub_asset({"name": "Test"})


class TestAzureMarketplaceConnectorPullOperations:
    """map_to_hub_asset() and sync_pull() against mocked HTTP responses."""

    def test_map_to_hub_asset(self, mocked_http):
        _, mock_client = mocked_http
        mock_client.get.return_value = _response(200, SAMPLE_PRODUCT)
        connector = AzureMarketplaceConnector()

        listing = connector.get_listing(SAMPLE_PRODUCT_ID)
        mapping = connector.map_to_hub_asset(listing, sync_job_id="job-1")

        assert mapping.source_type == AssetSourceType.FEDERATED
        assert mapping.source_metadata["marketplace_type"] == "AZURE_MARKETPLACE"
        assert mapping.source_metadata["listing_id"] == SAMPLE_PRODUCT_ID
        assert mapping.source_metadata["sync_job_id"] == "job-1"
        assert mapping.asset_data["name"] == "Test Data Product"
        assert mapping.odps_metadata is not None
        assert mapping.odps_metadata["pricing_plans"][0]["currency"] == "USD"
        assert len(mapping.resources) == 1
        assert mapping.resources[0].metadata["external"] is True

    def test_sync_pull_by_listing_ids(self, mocked_http):
        _, mock_client = mocked_http
        mock_client.get.return_value = _response(200, SAMPLE_PRODUCT)
        connector = AzureMarketplaceConnector()

        result = connector.sync_pull(
            listing_ids=[SAMPLE_PRODUCT_ID], options={"sync_job_id": "job-2"}
        )

        assert result.status == SyncStatus.COMPLETED
        assert result.successful_items == 1
        assert result.failed_items == 0
        assert len(result.metadata["mappings"]) == 1
        assert result.metadata["mappings"][0]["asset_data"]["name"] == "Test Data Product"

    def test_sync_pull_with_filters(self, mocked_http):
        _, mock_client = mocked_http
        mock_client.get.return_value = _response(200, SAMPLE_PRODUCTS_RESPONSE)
        connector = AzureMarketplaceConnector()

        result = connector.sync_pull(filters={"search": "covid"}, options={"limit": 5})

        assert result.status == SyncStatus.COMPLETED
        assert result.successful_items == 1
        assert len(result.metadata["mappings"]) == 1

    def test_sync_pull_handles_not_found(self, mocked_http):
        _, mock_client = mocked_http
        mock_client.get.return_value = _response(404)
        connector = AzureMarketplaceConnector()

        result = connector.sync_pull(listing_ids=["missing-product"])

        assert result.status == SyncStatus.FAILED
        assert result.failed_items == 1
        assert result.successful_items == 0
        assert len(result.errors) == 1


@pytest.mark.integration
class TestAzureMarketplaceConnectorLive:
    """Live smoke tests against the real Azure Catalog API.

    Gated on AZURE_MARKETPLACE_API_KEY (or AZURE_CATALOG_API_KEY) via the W16
    environment policy: a missing key skips locally and fails CI loudly.
    """

    def test_list_listings_live(self):
        base_url, api_key = _azure_live_config()
        connector = AzureMarketplaceConnector(base_url=base_url, api_key=api_key)
        connector._timeout = 10  # keep the live smoke call short
        try:
            listings = connector.list_listings(limit=10)
            assert isinstance(listings, list)
        finally:
            connector.close()
