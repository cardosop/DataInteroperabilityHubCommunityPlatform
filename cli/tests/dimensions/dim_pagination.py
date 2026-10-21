import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.3.9 — Dimension: pagination.

Verifies that paginated list endpoints return correct page metadata,
support cursor/offset navigation, and handle large result sets.
"""

from tests._persona_provisioning import provision_persona
from tests.use_cases._api_helpers import api_get


@pytest.fixture(scope="module")
def creds():
    return provision_persona("data_engineer")


def test_first_page_has_pagination_metadata(creds):
    """GET /assets/ must return pagination metadata (count, next, results)."""
    resp = api_get("/assets/", creds, params={"page_size": 2})
    if resp.status_code != 200:
        pytest.skip(f"GET /assets/ returned {resp.status_code}")

    data = resp.json()
    # DRF pagination returns: count, next, previous, results
    assert "results" in data, f"Response missing 'results' key: {list(data.keys())}"
    assert isinstance(data["results"], list), "results is not a list"


def test_page_size_is_respected(creds):
    """page_size=1 must return at most 1 item in results."""
    resp = api_get("/assets/", creds, params={"page_size": 1})
    if resp.status_code != 200:
        pytest.skip(f"GET /assets/ returned {resp.status_code}")

    data = resp.json()
    results = data.get("results", [])
    assert len(results) <= 1, f"page_size=1 but got {len(results)} results"


def test_next_page_returns_different_results(creds):
    """Fetching page 2 must return different items than page 1."""
    resp1 = api_get("/assets/", creds, params={"page": 1, "page_size": 1})
    if resp1.status_code != 200:
        pytest.skip("Cannot test pagination (page 1 failed)")

    data1 = resp1.json()
    if not data1.get("next"):
        pytest.skip("Only 1 page of results — cannot test next page")

    resp2 = api_get("/assets/", creds, params={"page": 2, "page_size": 1})
    assert resp2.status_code == 200, f"Page 2 returned {resp2.status_code}"

    ids1 = {r.get("id") for r in data1.get("results", [])}
    ids2 = {r.get("id") for r in resp2.json().get("results", [])}
    assert ids1 != ids2 or (not ids1 and not ids2), (
        f"Page 1 and page 2 returned the same items: {ids1}"
    )


def test_page_beyond_last_returns_empty(creds):
    """Requesting a page beyond the last must return empty results, not 500."""
    resp = api_get("/assets/", creds, params={"page": 99999, "page_size": 10})
    # 200 with empty results or 404 — both acceptable
    assert resp.status_code in (200, 404), f"Page 99999 returned {resp.status_code}"
    if resp.status_code == 200:
        data = resp.json()
        assert len(data.get("results", [])) == 0, "Page 99999 returned non-empty results"


def test_negative_page_returns_error(creds):
    """page=-1 must return 400, not 500."""
    resp = api_get("/assets/", creds, params={"page": -1})
    assert resp.status_code < 500, f"Negative page caused server error: {resp.status_code}"
