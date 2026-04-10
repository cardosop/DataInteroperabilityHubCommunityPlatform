import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.6.7 -- MarketplaceListingsAPI journey.

Validates the marketplace listings surface: listing all marketplace items,
creating a new listing, retrieving by id, and searching the marketplace.
"""

from tests._persona_provisioning import provision_persona
from tests.fixtures.test_data import fresh_id
from tests.use_cases._api_helpers import api_get, api_post


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _owner_creds():
    return provision_persona("data_product_owner")


def _skip_if_not_found(resp, label="Marketplace"):
    if resp.status_code == 404:
        pytest.skip(f"{label} endpoint not available (404)")


def _extract_results(body):
    if isinstance(body, list):
        return body
    return body.get("results") or body.get("items") or body.get("data") or []


def _create_listing(creds, *, name=None):
    """Create a marketplace listing and return (response, listing_id)."""
    payload = {
        "name": name or fresh_id("listing"),
        "description": "Automated journey test listing",
        "category": "dataset",
    }
    resp = api_post("/marketplace/listings/", creds, json=payload)
    listing_id = None
    if resp.status_code in (200, 201):
        body = resp.json()
        listing_id = body.get("id") or body.get("listing_id")
    return resp, listing_id


# ===========================================================================
# Tests
# ===========================================================================


def test_list_marketplace_listings():
    """GET /marketplace/listings/ returns available listings."""
    creds = _owner_creds()
    resp = api_get("/marketplace/listings/", creds)
    _skip_if_not_found(resp, "List marketplace listings")

    assert resp.status_code == 200, (
        f"GET /marketplace/listings/ returned {resp.status_code}: {resp.text[:500]}"
    )
    body = resp.json()
    if isinstance(body, dict):
        assert "results" in body or "items" in body or "data" in body, (
            f"Paginated response missing results/items/data: {list(body.keys())}"
        )
    else:
        assert isinstance(body, list)


def test_create_listing():
    """POST /marketplace/listings/ creates a new listing."""
    creds = _owner_creds()
    resp, listing_id = _create_listing(creds)
    _skip_if_not_found(resp, "Create marketplace listing")

    assert resp.status_code in (200, 201), (
        f"POST /marketplace/listings/ returned {resp.status_code}: {resp.text[:500]}"
    )
    assert listing_id is not None, "Response missing id/listing_id"


def test_get_listing_by_id():
    """GET /marketplace/listings/<id>/ returns the listing we created."""
    creds = _owner_creds()
    create_resp, listing_id = _create_listing(creds)
    _skip_if_not_found(create_resp, "Create marketplace listing")
    if listing_id is None:
        pytest.skip("Could not create listing to retrieve")

    get_resp = api_get(f"/marketplace/listings/{listing_id}/", creds)
    assert get_resp.status_code == 200, (
        f"GET /marketplace/listings/{listing_id}/ returned "
        f"{get_resp.status_code}: {get_resp.text[:500]}"
    )
    body = get_resp.json()
    returned_id = body.get("id") or body.get("listing_id")
    assert str(returned_id) == str(listing_id)


def test_search_marketplace():
    """GET /marketplace/listings/?search=<term> returns matching results."""
    creds = _owner_creds()
    unique = fresh_id("mkt-search")
    create_resp, _ = _create_listing(creds, name=unique)
    _skip_if_not_found(create_resp, "Create listing for search")

    search_resp = api_get(
        "/marketplace/listings/",
        creds,
        params={"search": unique},
    )
    assert search_resp.status_code == 200, (
        f"Search returned {search_resp.status_code}: {search_resp.text[:500]}"
    )
    results = _extract_results(search_resp.json())
    names = [r.get("name", "") for r in results]
    assert any(unique in n for n in names), (
        f"Search for '{unique}' did not return the created listing. "
        f"Got names: {names}"
    )
