import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.2.10 — Security: authn required.

Verifies that unauthenticated requests to protected endpoints return
401 (not 500, not crash, not 200).
"""

import requests
from tests.use_cases._api_helpers import api_base_url, api_unauthenticated_get

# Representative protected endpoints that every MVP deployment must have.
PROTECTED_ENDPOINTS = [
    "/assets/",
    "/contracts/",
    "/auth/me/",
    "/files/upload/",
    "/compliance/runs/",
    "/tenants/",
]


@pytest.mark.parametrize("endpoint", PROTECTED_ENDPOINTS)
def test_unauthenticated_request_returns_401(endpoint):
    """GET {endpoint} without any auth header must return 401, not 500."""
    resp = api_unauthenticated_get(endpoint)
    assert resp.status_code == 401, (
        f"GET {endpoint} without auth returned {resp.status_code}, expected 401. "
        f"Body: {resp.text[:300]}"
    )


def test_unauthenticated_post_returns_401():
    """POST /assets/ without auth must return 401."""
    resp = requests.post(
        f"{api_base_url()}/assets/",
        json={"name": "should-fail"},
        timeout=15,
    )
    assert resp.status_code == 401


def test_empty_bearer_returns_401():
    """Authorization: Bearer <empty> must return 401."""
    resp = requests.get(
        f"{api_base_url()}/auth/me/",
        headers={"Authorization": "Bearer "},
        timeout=15,
    )
    assert resp.status_code == 401


def test_malformed_auth_header_returns_401():
    """Authorization: NotBearer xyz must return 401."""
    resp = requests.get(
        f"{api_base_url()}/auth/me/",
        headers={"Authorization": "NotBearer xyz123"},
        timeout=15,
    )
    assert resp.status_code == 401
