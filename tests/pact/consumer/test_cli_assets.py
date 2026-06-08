"""
Pact consumer test: CLI → /api/v1/assets/ (280.B.5.1).

Defines the contract expectations the CLI has for the Assets API.
Run with a Pact mock server:
    pytest tests/pact/consumer/test_cli_assets.py -v
"""
import atexit
import json

import pytest
from pact import Consumer, Like, Provider, Term

PACT_DIR = "tests/pact/pacts"

# Define the consumer (CLI) and provider (Meshant API)
pact = Consumer("CLI").has_pact_with(
    Provider("MeshantAPI"),
    pact_dir=PACT_DIR,
    host_name="localhost",
    port=1234,
)
pact.start_service()
atexit.register(pact.stop_service)


class TestCLIAssetsContract:
    """CLI consumer expectations for the Assets API."""

    def test_list_assets(self):
        """GET /api/v1/assets/ — paginated list with status filter."""
        expected = Like({
            "count": 2,
            "next": None,
            "previous": None,
            "results": [
                {
                    "id": Term(r"^[0-9a-f-]+$", "asset-uuid-001"),
                    "name": Like("Test Asset"),
                    "key": Like("test-asset"),
                    "status": Like("ACTIVE"),
                    "domain": Like("finance"),
                    "visibility": Like("INTERNAL"),
                    "description": Like("A test asset"),
                    "created_at": Term(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", "2025-01-01T00:00:00Z"),
                    "updated_at": Term(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", "2025-01-01T00:00:00Z"),
                }
            ],
        })

        (pact
         .given("assets exist")
         .upon_receiving("list assets with status filter")
         .with_request("GET", "/api/v1/assets/", query={"status": "ACTIVE", "limit": "50", "offset": "0"})
         .will_respond_with(200, body=expected))

        with pact:
            import requests
            result = requests.get(
                "http://localhost:1234/api/v1/assets/",
                params={"status": "ACTIVE", "limit": 50, "offset": 0},
            )
            assert result.status_code == 200
            data = result.json()
            assert isinstance(data["results"], list)
            assert len(data["results"]) > 0

    def test_get_asset(self):
        """GET /api/v1/assets/{id}/ — single asset retrieval."""
        asset_id = "123e4567-e89b-12d3-a456-426614174000"
        expected = Like({
            "id": asset_id,
            "name": Like("Test Asset"),
            "key": Like("test-asset"),
            "status": Like("ACTIVE"),
            "domain": Like("finance"),
            "visibility": Like("INTERNAL"),
            "created_at": Term(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", "2025-01-01T00:00:00Z"),
            "updated_at": Term(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", "2025-01-01T00:00:00Z"),
        })

        (pact
         .given("an asset exists")
         .upon_receiving("get asset by id")
         .with_request("GET", f"/api/v1/assets/{asset_id}/")
         .will_respond_with(200, body=expected))

        with pact:
            import requests
            result = requests.get(f"http://localhost:1234/api/v1/assets/{asset_id}/")
            assert result.status_code == 200
            assert result.json()["id"] == asset_id

    def test_asset_not_found(self):
        """GET /api/v1/assets/{id}/ — 404 when asset doesn't exist."""
        error_body = Like({
            "error": {
                "code": "ASSET_NOT_FOUND",
                "message": Like("Asset not found"),
                "http_status": 404,
            }
        })

        (pact
         .given("asset does not exist")
         .upon_receiving("get non-existent asset")
         .with_request("GET", "/api/v1/assets/nonexistent/")
         .will_respond_with(404, body=error_body))

        with pact:
            import requests
            result = requests.get("http://localhost:1234/api/v1/assets/nonexistent/")
            assert result.status_code == 404

    def test_create_asset(self):
        """POST /api/v1/assets/ — create a new asset."""
        request_body = {
            "name": "New Asset",
            "key": "new-asset",
            "visibility": "INTERNAL",
            "description": "Created via CLI",
        }
        expected = Like({
            "id": Term(r"^[0-9a-f-]+$", "new-uuid"),
            "name": "New Asset",
            "key": "new-asset",
            "status": "DRAFT",
            "visibility": "INTERNAL",
            "created_at": Term(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", "2025-06-01T00:00:00Z"),
        })

        (pact
         .given("tenant can create assets")
         .upon_receiving("create new asset")
         .with_request("POST", "/api/v1/assets/", body=request_body)
         .will_respond_with(201, body=expected))

        with pact:
            import requests
            result = requests.post(
                "http://localhost:1234/api/v1/assets/",
                json=request_body,
            )
            assert result.status_code == 201
            assert result.json()["name"] == "New Asset"
