"""
Pact consumer test: Marketplace UI → /api/v1/marketplace/ (281.A.2.2).

Consumer #4 of 5 critical API consumers.
"""

import pytest
from pact import Pact
from pact.matchers import Like, Term

PACT_DIR = "tests/pact/pacts"


@pytest.fixture(scope="module")
def mkt_pact():
    pact = Pact("MarketplaceUI", "MeshantAPI")
    pact.with_specification("V4").with_pact_dir(PACT_DIR)
    with pact.start_mocking(port=1237):
        yield pact


class TestMarketplaceUIContract:
    """Marketplace UI consumer expectations."""

    def test_list_listings(self, mkt_pact):
        mkt_pact.given("listings exist").upon_receiving("browse marketplace listings").with_request(
            "GET", "/api/v1/marketplace/listings/", query="limit=20&offset=0"
        ).will_respond_with(
            200,
            body={
                "count": 1,
                "results": [
                    {
                        "id": Term(r"^[0-9a-f-]+$", "listing-uuid"),
                        "title": Like("Sales Dataset"),
                        "status": Like("PUBLISHED"),
                        "price": Like("$100"),
                    }
                ],
            },
        )

        import requests

        result = requests.get(
            "http://localhost:1237/api/v1/marketplace/listings/", params={"limit": 20, "offset": 0}
        )
        assert result.status_code == 200

    def test_checkout(self, mkt_pact):
        mkt_pact.given("listing is purchasable").upon_receiving(
            "create order from listing"
        ).with_request(
            "POST",
            "/api/v1/marketplace/orders/",
            body={
                "listing_id": Like("listing-uuid"),
            },
        ).will_respond_with(
            201,
            body={
                "id": Term(r"^[0-9a-f-]+$", "order-uuid"),
                "status": "PENDING",
                "total": Like("$100"),
            },
        )

        import requests

        result = requests.post(
            "http://localhost:1237/api/v1/marketplace/orders/",
            json={
                "listing_id": "listing-uuid",
            },
        )
        assert result.status_code == 201

    def test_entitlements(self, mkt_pact):
        mkt_pact.given("user has purchased listings").upon_receiving(
            "list my entitlements"
        ).with_request(
            "GET", "/api/v1/marketplace/entitlements/", query="limit=50&offset=0"
        ).will_respond_with(
            200,
            body={
                "results": [
                    {
                        "id": Term(r"^[0-9a-f-]+$", "ent-uuid"),
                        "asset": {"name": Like("Sales Data")},
                        "status": Like("ACTIVE"),
                    }
                ],
            },
        )

        import requests

        result = requests.get(
            "http://localhost:1237/api/v1/marketplace/entitlements/",
            params={"limit": 50, "offset": 0},
        )
        assert result.status_code == 200
