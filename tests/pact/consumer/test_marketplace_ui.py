"""
Pact consumer test: Marketplace UI → /api/v1/marketplace/ (281.A.2.2).

Consumer #4 of 5 critical API consumers.
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
def mkt_pact():
    """Per-test Pact for the Marketplace UI consumer.

    The FFI pact handle is finalized by the first ``serve()`` session, so
    each test gets a fresh Pact. ``write_file(overwrite=False)`` MERGES
    the test's interactions into the committed pact file on teardown.
    """
    pact = Pact(consumer="MarketplaceUI", provider="MeshantAPI")
    yield pact
    pact.write_file(PACT_DIR, overwrite=False)


class TestMarketplaceUIContract:
    """Marketplace UI consumer expectations."""

    def test_list_listings(self, mkt_pact):
        pact = mkt_pact
        (
            pact.upon_receiving("browse marketplace listings")
            .given("listings exist")
            .with_request("GET", "/api/v1/marketplace/listings/")
            .with_query_parameter("limit", "20")
            .with_query_parameter("offset", "0")
            .will_respond_with(200)
            .with_body(
                {
                    "count": 1,
                    "results": [
                        {
                            "id": match.regex("listing-uuid", regex=r"^[0-9a-f-]+$"),
                            "title": match.like("Sales Dataset"),
                            "status": match.like("PUBLISHED"),
                            "price": match.like("$100"),
                        }
                    ],
                },
                part="Response",
            )
        )

        import requests

        with pact.serve(addr="localhost", port=0, raises=False) as srv:
            result = requests.get(
                f"{srv.url}/api/v1/marketplace/listings/", params={"limit": 20, "offset": 0}
            )
            assert result.status_code == 200

    def test_checkout(self, mkt_pact):
        pact = mkt_pact
        (
            pact.upon_receiving("create order from listing")
            .given("listing is purchasable")
            .with_request("POST", "/api/v1/marketplace/orders/")
            .with_body({"listing_id": match.like("listing-uuid")}, part="Request")
            .will_respond_with(201)
            .with_body(
                {
                    "id": match.regex("order-uuid", regex=r"^[0-9a-f-]+$"),
                    "status": "PENDING",
                    "total": match.like("$100"),
                },
                part="Response",
            )
        )

        import requests

        with pact.serve(addr="localhost", port=0, raises=False) as srv:
            result = requests.post(
                f"{srv.url}/api/v1/marketplace/orders/",
                json={
                    "listing_id": "listing-uuid",
                },
            )
            assert result.status_code == 201

    def test_entitlements(self, mkt_pact):
        pact = mkt_pact
        (
            pact.upon_receiving("list my entitlements")
            .given("user has purchased listings")
            .with_request("GET", "/api/v1/marketplace/entitlements/")
            .with_query_parameter("limit", "50")
            .with_query_parameter("offset", "0")
            .will_respond_with(200)
            .with_body(
                {
                    "results": [
                        {
                            "id": match.regex("ent-uuid", regex=r"^[0-9a-f-]+$"),
                            "asset": {"name": match.like("Sales Data")},
                            "status": match.like("ACTIVE"),
                        }
                    ],
                },
                part="Response",
            )
        )

        import requests

        with pact.serve(addr="localhost", port=0, raises=False) as srv:
            result = requests.get(
                f"{srv.url}/api/v1/marketplace/entitlements/",
                params={"limit": 50, "offset": 0},
            )
            assert result.status_code == 200
