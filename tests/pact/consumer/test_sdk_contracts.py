"""
Pact consumer test: Python SDK → /api/v1/contracts/ (280.B.5.1).

Defines the contract expectations the Python SDK has for the Contracts API.
"""

import atexit

from pact import Consumer, Like, Provider, Term

PACT_DIR = "tests/pact/pacts"

pact = Consumer("PythonSDK").has_pact_with(
    Provider("MeshantAPI"),
    pact_dir=PACT_DIR,
    host_name="localhost",
    port=1235,
)
pact.start_service()
atexit.register(pact.stop_service)


class TestSDKContractsContract:
    """Python SDK consumer expectations for the Contracts API."""

    def test_list_contracts(self):
        """GET /api/v1/contracts/ — paginated list."""
        expected = Like(
            {
                "count": 1,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "id": Term(r"^[0-9a-f-]+$", "contract-uuid"),
                        "status": Like("DRAFT"),
                        "asset_id": Term(r"^[0-9a-f-]+$", "asset-uuid"),
                        "original_spec_type": Like("ODCS"),
                        "original_format": Like("YAML"),
                        "normalization_status": Like("NORMALIZED_OK"),
                        "version": Like(1),
                        "created_at": Term(
                            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", "2025-01-01T00:00:00Z"
                        ),
                    }
                ],
            }
        )

        (
            pact.given("contracts exist")
            .upon_receiving("list contracts")
            .with_request("GET", "/api/v1/contracts/", query={"limit": "50", "offset": "0"})
            .will_respond_with(200, body=expected)
        )

        with pact:
            import requests

            result = requests.get(
                "http://localhost:1235/api/v1/contracts/",
                params={"limit": 50, "offset": 0},
            )
            assert result.status_code == 200
            assert len(result.json()["results"]) == 1

    def test_validate_contract(self):
        """POST /api/v1/contracts/{id}/validate/ — validation endpoint."""
        contract_id = "123e4567-e89b-12d3-a456-426614174000"
        expected = Like(
            {
                "valid": True,
                "errors": [],
                "warnings": Like([]),
                "contract_id": contract_id,
            }
        )

        (
            pact.given("a contract exists")
            .upon_receiving("validate contract")
            .with_request("POST", f"/api/v1/contracts/{contract_id}/validate/")
            .will_respond_with(200, body=expected)
        )

        with pact:
            import requests

            result = requests.post(
                f"http://localhost:1235/api/v1/contracts/{contract_id}/validate/"
            )
            assert result.status_code == 200
            assert result.json()["valid"] is True

    def test_export_contract(self):
        """GET /api/v1/contracts/{id}/export/ — export in ODCS format."""
        contract_id = "123e4567-e89b-12d3-a456-426614174000"
        expected = Like(
            {
                "format": "ODCS",
                "content": Like("..."),
                "filename": Like("contract.odcs.yaml"),
            }
        )

        (
            pact.given("a contract exists")
            .upon_receiving("export contract as ODCS")
            .with_request(
                "GET", f"/api/v1/contracts/{contract_id}/export/", query={"format": "odcs"}
            )
            .will_respond_with(200, body=expected)
        )

        with pact:
            import requests

            result = requests.get(
                f"http://localhost:1235/api/v1/contracts/{contract_id}/export/",
                params={"format": "odcs"},
            )
            assert result.status_code == 200
