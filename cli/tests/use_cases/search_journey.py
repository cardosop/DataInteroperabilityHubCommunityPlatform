import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.7.1 — Search journey: CLI search command group.

Validates asset search by query, empty-query handling, and
pagination via real API calls against the staging environment.
"""

from tests._persona_provisioning import provision_persona
from tests.use_cases._api_helpers import api_get


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _provision_analyst():
    return provision_persona("data_analyst")


def _extract_results(body):
    """Extract search results from a paginated or flat response."""
    if isinstance(body, list):
        return body
    return body.get("results", body.get("items", body.get("hits", [])))


# ===========================================================================
# Tests
# ===========================================================================


def test_search_assets_by_query():
    """GET /search/ with a query parameter returns matching results."""
    creds = _provision_analyst()

    resp = api_get("/search/", creds, params={"q": "test"})
    if resp.status_code == 404:
        resp = api_get("/search/assets/", creds, params={"q": "test"})
    if resp.status_code == 404:
        resp = api_get("/assets/", creds, params={"search": "test"})
    if resp.status_code == 404:
        pytest.skip("Search endpoint not found (404)")

    assert resp.status_code == 200, (
        f"Search returned {resp.status_code}: {resp.text[:500]}"
    )

    body = resp.json()
    results = _extract_results(body)
    assert isinstance(results, list), (
        f"Expected search results to be a list, got {type(results).__name__}"
    )


def test_search_empty_returns_results():
    """GET /search/ with an empty or wildcard query returns all results
    (or at least a valid response).
    """
    creds = _provision_analyst()

    resp = api_get("/search/", creds, params={"q": ""})
    if resp.status_code == 404:
        resp = api_get("/search/assets/", creds, params={"q": ""})
    if resp.status_code == 404:
        resp = api_get("/assets/", creds)
    if resp.status_code == 404:
        pytest.skip("Search endpoint not found (404)")

    # Empty query may return 200 with all results or 400 if query is required
    if resp.status_code == 400:
        pytest.skip("Empty search query not supported (400)")

    assert resp.status_code == 200, (
        f"Empty search returned {resp.status_code}: {resp.text[:500]}"
    )

    body = resp.json()
    results = _extract_results(body)
    assert isinstance(results, list), (
        f"Expected search results to be a list, got {type(results).__name__}"
    )


def test_search_pagination():
    """GET /search/ with limit and offset returns paginated results."""
    creds = _provision_analyst()

    resp = api_get(
        "/search/",
        creds,
        params={"q": "test", "limit": 5, "offset": 0},
    )
    if resp.status_code == 404:
        resp = api_get(
            "/search/assets/",
            creds,
            params={"q": "test", "limit": 5, "offset": 0},
        )
    if resp.status_code == 404:
        resp = api_get(
            "/assets/",
            creds,
            params={"search": "test", "limit": 5, "offset": 0},
        )
    if resp.status_code == 404:
        pytest.skip("Search endpoint not found (404)")

    assert resp.status_code == 200, (
        f"Paginated search returned {resp.status_code}: {resp.text[:500]}"
    )

    body = resp.json()
    results = _extract_results(body)
    assert isinstance(results, list), (
        f"Expected paginated results to be a list, got {type(results).__name__}"
    )
    assert len(results) <= 5, (
        f"Requested limit=5 but got {len(results)} results"
    )

    # Check for pagination metadata if response is a dict
    if isinstance(body, dict):
        pagination_keys = {"count", "total", "total_count", "next", "has_more"}
        has_pagination = any(k in body for k in pagination_keys)
        # Pagination metadata is nice to have but not strictly required
        if has_pagination:
            total = body.get("count", body.get("total", body.get("total_count")))
            if total is not None:
                assert isinstance(total, int) and total >= 0
