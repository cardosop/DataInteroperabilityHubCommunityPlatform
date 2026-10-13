"""
Pact consumer test: CLI → /api/v1/assets/ (280.B.5.1).

Defines the contract expectations the CLI has for the Assets API.
Written against the pact-python 3.x FFI DSL (``match.like`` / ``match.regex``,
``pact.serve()`` context manager, ``write_file`` on module teardown).
"""

import pytest

try:
    import pact as _pact
    from pact import Pact, match
except ImportError:
    from envpolicy import environment_guard

    environment_guard("pact-python is not installed — install it to run the Pact consumer tests")
    pytest.skip("pact-python is not installed", allow_module_level=True)

PACT_DIR = "tests/pact/pacts"


@pytest.fixture
def assets_pact():
    """Per-test Pact for the CLI consumer.

    The FFI pact handle is finalized by the first ``serve()`` session, so
    each test gets a fresh Pact. ``write_file(overwrite=False)`` MERGES
    the test's interactions into the committed pact file on teardown.
    """
    pact = Pact(consumer="CLI", provider="MeshantAPI")
    yield pact
    pact.write_file(PACT_DIR, overwrite=False)


class TestCLIAssetsContract:
    """CLI consumer expectations for the Assets API."""

    def test_list_assets(self, assets_pact):
        """GET /api/v1/assets/ — paginated list with status filter."""
        pact = assets_pact
        expected = match.like(
            {
                "count": 2,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "id": match.regex("asset-uuid-001", regex=r"^[0-9a-f-]+$"),
                        "name": match.like("Test Asset"),
                        "key": match.like("test-asset"),
                        "status": match.like("ACTIVE"),
                        "domain": match.like("finance"),
                        "visibility": match.like("INTERNAL"),
                        "description": match.like("A test asset"),
                        "created_at": match.regex(
                            "2025-01-01T00:00:00Z",
                            regex=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
                        ),
                        "updated_at": match.regex(
                            "2025-01-01T00:00:00Z",
                            regex=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
                        ),
                    }
                ],
            }
        )

        (
            pact.upon_receiving("list assets with status filter")
            .given("assets exist")
            .with_request("GET", "/api/v1/assets/")
            .with_query_parameter("status", "ACTIVE")
            .with_query_parameter("limit", "50")
            .with_query_parameter("offset", "0")
            .will_respond_with(200)
            .with_body(expected, part="Response")
        )

        import requests

        with pact.serve(addr="localhost", port=0, raises=False) as srv:
            result = requests.get(
                f"{srv.url}/api/v1/assets/",
                params={"status": "ACTIVE", "limit": 50, "offset": 0},
            )
            assert result.status_code == 200
            data = result.json()
            assert isinstance(data["results"], list)
            assert len(data["results"]) > 0

    def test_get_asset(self, assets_pact):
        """GET /api/v1/assets/{id}/ — single asset retrieval."""
        pact = assets_pact
        asset_id = "123e4567-e89b-12d3-a456-426614174000"
        expected = match.like(
            {
                "id": asset_id,
                "name": match.like("Test Asset"),
                "key": match.like("test-asset"),
                "status": match.like("ACTIVE"),
                "domain": match.like("finance"),
                "visibility": match.like("INTERNAL"),
                "created_at": match.regex(
                    "2025-01-01T00:00:00Z",
                    regex=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
                ),
                "updated_at": match.regex(
                    "2025-01-01T00:00:00Z",
                    regex=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
                ),
            }
        )

        (
            pact.upon_receiving("get asset by id")
            .given("an asset exists")
            .with_request("GET", f"/api/v1/assets/{asset_id}/")
            .will_respond_with(200)
            .with_body(expected, part="Response")
        )

        import requests

        with pact.serve(addr="localhost", port=0, raises=False) as srv:
            result = requests.get(f"{srv.url}/api/v1/assets/{asset_id}/")
            assert result.status_code == 200
            assert result.json()["id"] == asset_id

    def test_asset_not_found(self, assets_pact):
        """GET /api/v1/assets/{id}/ — 404 when asset doesn't exist."""
        pact = assets_pact
        error_body = match.like(
            {
                "error": {
                    "code": "ASSET_NOT_FOUND",
                    "message": match.like("Asset not found"),
                    "http_status": 404,
                }
            }
        )

        (
            pact.upon_receiving("get non-existent asset")
            .given("asset does not exist")
            .with_request("GET", "/api/v1/assets/nonexistent/")
            .will_respond_with(404)
            .with_body(error_body, part="Response")
        )

        import requests

        with pact.serve(addr="localhost", port=0, raises=False) as srv:
            result = requests.get(f"{srv.url}/api/v1/assets/nonexistent/")
            assert result.status_code == 404

    def test_create_asset(self, assets_pact):
        """POST /api/v1/assets/ — create a new asset."""
        pact = assets_pact
        request_body = {
            "name": "New Asset",
            "key": "new-asset",
            "visibility": "INTERNAL",
            "description": "Created via CLI",
        }
        expected = match.like(
            {
                "id": match.regex("new-uuid", regex=r"^[0-9a-f-]+$"),
                "name": "New Asset",
                "key": "new-asset",
                "status": "DRAFT",
                "visibility": "INTERNAL",
                "created_at": match.regex(
                    "2025-06-01T00:00:00Z",
                    regex=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
                ),
            }
        )

        (
            pact.upon_receiving("create new asset")
            .given("tenant can create assets")
            .with_request("POST", "/api/v1/assets/")
            .with_body(request_body, part="Request")
            .will_respond_with(201)
            .with_body(expected, part="Response")
        )

        import requests

        with pact.serve(addr="localhost", port=0, raises=False) as srv:
            result = requests.post(
                f"{srv.url}/api/v1/assets/",
                json=request_body,
            )
            assert result.status_code == 201
            assert result.json()["name"] == "New Asset"
