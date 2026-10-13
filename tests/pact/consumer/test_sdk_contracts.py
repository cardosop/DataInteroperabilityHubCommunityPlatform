"""
Pact consumer test: Python SDK → /api/v1/contracts/ (280.B.5.1).

Defines the contract expectations the Python SDK has for the Contracts API.
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
def sdk_pact():
    """Per-test Pact for the Python SDK consumer.

    The FFI pact handle is finalized by the first ``serve()`` session, so
    each test gets a fresh Pact. ``write_file(overwrite=False)`` MERGES
    the test's interactions into the committed pact file on teardown.
    """
    pact = Pact(consumer="PythonSDK", provider="MeshantAPI")
    yield pact
    pact.write_file(PACT_DIR, overwrite=False)


class TestSDKContractsContract:
    """Python SDK consumer expectations for the Contracts API."""

    def test_list_contracts(self, sdk_pact):
        """GET /api/v1/contracts/ — paginated list."""
        pact = sdk_pact
        expected = match.like(
            {
                "count": 1,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "id": match.regex("contract-uuid", regex=r"^[0-9a-f-]+$"),
                        "status": match.like("DRAFT"),
                        "asset_id": match.regex("asset-uuid", regex=r"^[0-9a-f-]+$"),
                        "original_spec_type": match.like("ODCS"),
                        "original_format": match.like("YAML"),
                        "normalization_status": match.like("NORMALIZED_OK"),
                        "version": match.like(1),
                        "created_at": match.regex(
                            "2025-01-01T00:00:00Z",
                            regex=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
                        ),
                    }
                ],
            }
        )

        (
            pact.upon_receiving("list contracts")
            .given("contracts exist")
            .with_request("GET", "/api/v1/contracts/")
            .with_query_parameter("limit", "50")
            .with_query_parameter("offset", "0")
            .will_respond_with(200)
            .with_body(expected, part="Response")
        )

        import requests

        with pact.serve(addr="localhost", port=0, raises=False) as srv:
            result = requests.get(
                f"{srv.url}/api/v1/contracts/",
                params={"limit": 50, "offset": 0},
            )
            assert result.status_code == 200
            assert len(result.json()["results"]) == 1

    def test_validate_contract(self, sdk_pact):
        """POST /api/v1/contracts/{id}/validate/ — validation endpoint."""
        pact = sdk_pact
        contract_id = "123e4567-e89b-12d3-a456-426614174000"
        expected = match.like(
            {
                "valid": True,
                "errors": [],
                "warnings": match.like([]),
                "contract_id": contract_id,
            }
        )

        (
            pact.upon_receiving("validate contract")
            .given("a contract exists")
            .with_request("POST", f"/api/v1/contracts/{contract_id}/validate/")
            .will_respond_with(200)
            .with_body(expected, part="Response")
        )

        import requests

        with pact.serve(addr="localhost", port=0, raises=False) as srv:
            result = requests.post(f"{srv.url}/api/v1/contracts/{contract_id}/validate/")
            assert result.status_code == 200
            assert result.json()["valid"] is True

    def test_export_contract(self, sdk_pact):
        """GET /api/v1/contracts/{id}/export/ — export in ODCS format."""
        pact = sdk_pact
        contract_id = "123e4567-e89b-12d3-a456-426614174000"
        expected = match.like(
            {
                "format": "ODCS",
                "content": match.like("..."),
                "filename": match.like("contract.odcs.yaml"),
            }
        )

        (
            pact.upon_receiving("export contract as ODCS")
            .given("a contract exists")
            .with_request("GET", f"/api/v1/contracts/{contract_id}/export/")
            .with_query_parameter("format", "odcs")
            .will_respond_with(200)
            .with_body(expected, part="Response")
        )

        import requests

        with pact.serve(addr="localhost", port=0, raises=False) as srv:
            result = requests.get(
                f"{srv.url}/api/v1/contracts/{contract_id}/export/",
                params={"format": "odcs"},
            )
            assert result.status_code == 200
