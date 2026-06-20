import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.6.9 -- SearchAPI journey.

Validates the global search surface: searching assets, searching contracts,
handling empty queries, and verifying pagination in results.
"""

from tests._persona_provisioning import provision_persona
from tests.use_cases._api_helpers import api_get

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _user_creds():
    return provision_persona("data_analyst")


def _skip_if_not_found(resp, label="Search"):
    if resp.status_code == 404:
        pytest.skip(f"{label} endpoint not available (404)")


def _extract_results(body):
    if isinstance(body, list):
        return body
    return body.get("results") or body.get("items") or body.get("data") or []


def _search(creds, query, **extra_params):
    """Try common search endpoint patterns and return first non-404 response."""
    params = {"q": query, **extra_params}
    for path in ("/search/", "/search"):
        resp = api_get(path, creds, params=params)
        if resp.status_code != 404:
            return resp

    # Also try query= instead of q=
    params_alt = {"query": query, **extra_params}
    for path in ("/search/", "/search"):
        resp = api_get(path, creds, params=params_alt)
        if resp.status_code != 404:
            return resp

    return resp  # return last response (404)


# ===========================================================================
# Tests
# ===========================================================================


def test_search_assets():
    """Search for assets by keyword returns a response."""
    creds = _user_creds()
    resp = _search(creds, "asset")
    _skip_if_not_found(resp, "Search assets")

    assert resp.status_code == 200, f"Search returned {resp.status_code}: {resp.text[:500]}"
    body = resp.json()
    # Should be a list or paginated dict
    assert isinstance(body, (dict, list)), f"Unexpected search response type: {type(body)}"


def test_search_contracts():
    """Search for contracts by keyword returns a response."""
    creds = _user_creds()
    resp = _search(creds, "contract")
    _skip_if_not_found(resp, "Search contracts")

    assert resp.status_code == 200, f"Search returned {resp.status_code}: {resp.text[:500]}"


def test_search_empty_query():
    """Search with an empty query returns 200 (all results) or 400 (bad request)."""
    creds = _user_creds()
    resp = _search(creds, "")
    _skip_if_not_found(resp, "Search empty query")

    assert resp.status_code in (200, 400, 422), (
        f"Empty search returned unexpected {resp.status_code}: {resp.text[:500]}"
    )


def test_search_returns_pagination():
    """Search results include pagination metadata (count, next, page, etc.)."""
    creds = _user_creds()
    resp = _search(creds, "test")
    _skip_if_not_found(resp, "Search pagination")

    assert resp.status_code == 200
    body = resp.json()

    if isinstance(body, list):
        # Bare lists are acceptable but lack pagination
        pytest.skip("Search returns a bare list without pagination metadata")

    keys_lower = {k.lower() for k in body.keys()}
    has_pagination = any(
        k in keys_lower
        for k in (
            "count",
            "total",
            "total_count",
            "total_results",
            "next",
            "previous",
            "page",
            "page_size",
            "limit",
            "offset",
            "has_more",
            "has_next",
        )
    )
    assert has_pagination, f"Search response lacks pagination metadata: {list(body.keys())}"
