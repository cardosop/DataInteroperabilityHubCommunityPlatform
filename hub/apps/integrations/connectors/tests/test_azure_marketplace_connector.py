"""
Tests for Azure Marketplace connector.

Uses a real HTTP test server (no mocks in connector logic) that serves
Azure Catalog API-shaped JSON. The connector performs real HTTP requests
to the test server.
"""
import json
import socket
import threading
import pytest
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any

from hub.apps.integrations.base import (
    MarketplaceType,
    SyncDirection,
    SyncStatus,
)
from hub.apps.integrations.connectors.azure_marketplace_connector import (
    AzureMarketplaceConnector,
)
from hub.apps.core.services.base import NotFoundError


# Azure-shaped product payload (real config shape per Microsoft docs)
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


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        port: int = s.getsockname()[1]
        return port


class AzureShapeHandler(BaseHTTPRequestHandler):
    """Serves Azure Catalog API-shaped responses for real HTTP tests."""

    def _send_json(self, status: int, body: Dict[str, Any]) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode("utf-8"))

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/products" or path == "/products/":
            self._send_json(200, SAMPLE_PRODUCTS_RESPONSE)
            return
        if path.startswith("/products/"):
            product_id = path.replace("/products/", "").strip("/")
            if product_id == SAMPLE_PRODUCT["uniqueProductId"]:
                self._send_json(200, SAMPLE_PRODUCT)
                return
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        pass


@pytest.fixture(scope="module")
def azure_test_server():
    """Start a real HTTP server serving Azure-shaped JSON (no mocks)."""
    port = _find_free_port()
    server = HTTPServer(("127.0.0.1", port), AzureShapeHandler)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()


@pytest.fixture
def azure_connector(azure_test_server, request):
    """Azure connector pointing at the test server (real HTTP)."""
    connector = AzureMarketplaceConnector(
        base_url=azure_test_server,
        api_key="test-api-key",
        api_version="2025-05-01",
    )

    def _close():
        if hasattr(connector, "close"):
            connector.close()

    request.addfinalizer(_close)
    return connector


@pytest.mark.django_db(transaction=True)
class TestAzureMarketplaceConnector:
    """Unit/integration tests for Azure Marketplace connector (real HTTP)."""

    def test_marketplace_type(self, azure_connector):
        expected = MarketplaceType.AZURE_MARKETPLACE
        assert azure_connector.marketplace_type == expected

    def test_supported_sync_directions(self, azure_connector):
        assert (
            azure_connector.supported_sync_directions == [SyncDirection.PULL]
        )

    def test_test_connection(self, azure_connector):
        assert azure_connector.test_connection() is True

    def test_list_listings(self, azure_connector):
        listings = azure_connector.list_listings(limit=10)
        assert len(listings) >= 1
        listing = listings[0]
        assert listing.marketplace_type == MarketplaceType.AZURE_MARKETPLACE
        assert listing.marketplace_id == SAMPLE_PRODUCT["uniqueProductId"]
        assert listing.title == SAMPLE_PRODUCT["displayName"]
        assert listing.description is not None
        assert "connector tests" in (listing.description or "")

    def test_get_listing(self, azure_connector):
        pid = SAMPLE_PRODUCT["uniqueProductId"]
        listing = azure_connector.get_listing(pid)
        assert listing.marketplace_id == pid
        assert listing.title == SAMPLE_PRODUCT["displayName"]
        assert len(listing.resources) >= 1
        assert listing.resources[0].resource_type == "PLAN"

    def test_get_listing_not_found(self, azure_connector):
        with pytest.raises(NotFoundError, match="not found"):
            azure_connector.get_listing("nonexistent-product-id")

    def test_list_resources(self, azure_connector):
        pid = SAMPLE_PRODUCT["uniqueProductId"]
        resources = azure_connector.list_resources(pid)
        assert len(resources) >= 1
        assert resources[0].name == "Standard"

    def test_map_to_hub_asset(self, azure_connector):
        pid = SAMPLE_PRODUCT["uniqueProductId"]
        listing = azure_connector.get_listing(pid)
        mapping = azure_connector.map_to_hub_asset(listing, sync_job_id="job-1")
        assert mapping.source_type.value == "FEDERATED"
        assert (
            mapping.source_metadata["marketplace_type"]
            == "AZURE_MARKETPLACE"
        )
        assert mapping.source_metadata["listing_id"] == pid
        assert mapping.source_metadata.get("sync_job_id") == "job-1"
        assert mapping.asset_data["name"] == SAMPLE_PRODUCT["displayName"]
        assert len(mapping.resources) >= 1

    def test_sync_pull_by_listing_ids(self, azure_connector):
        result = azure_connector.sync_pull(
            listing_ids=[SAMPLE_PRODUCT["uniqueProductId"]],
            options={"sync_job_id": "job-2"},
        )
        assert result.status == SyncStatus.COMPLETED
        assert result.successful_items >= 1
        assert "mappings" in result.metadata
        assert len(result.metadata["mappings"]) >= 1

    def test_sync_pull_with_filters(self, azure_connector):
        result = azure_connector.sync_pull(
            listing_ids=None,
            filters={},
            options={"limit": 5},
        )
        assert result.status in (SyncStatus.COMPLETED, SyncStatus.PARTIAL)
        assert result.total_items >= 0
        assert "mappings" in result.metadata

    def test_authenticate(self, azure_connector):
        assert azure_connector.authenticate({"api_key": "new-key"}) is True

    def test_create_listing_not_supported(self, azure_connector):
        from hub.apps.integrations.base import MarketplaceListing

        listing = MarketplaceListing(
            marketplace_id="",
            marketplace_type=MarketplaceType.AZURE_MARKETPLACE,
            title="Test",
        )
        with pytest.raises(NotImplementedError, match="create_listing"):
            azure_connector.create_listing(listing)  # push not supported

    def test_sync_push_not_supported(self, azure_connector):
        with pytest.raises(NotImplementedError, match="sync_push"):
            azure_connector.sync_push(["asset-1"])  # push not supported

    def test_download_resource_not_supported(self, azure_connector):
        with pytest.raises(NotImplementedError, match="download_resource"):
            azure_connector.download_resource("res-1", "/tmp/out")

    def test_init_from_config(self):
        connector = AzureMarketplaceConnector(
            config={
                "base_url": "https://catalogapi.azure.com",
                "api_key": "key",
                "api_version": "2025-05-01",
            }
        )
        assert connector._base_url == "https://catalogapi.azure.com"
        assert connector._api_key == "key"
        assert connector._api_version == "2025-05-01"
