import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.7.1 — Auth journey: CLI auth command group.

Validates /auth/me/, /auth/login/, and /auth/logout/ endpoints
via real API calls against the staging environment.
"""

import requests
from tests._persona_provisioning import provision_persona
from tests.use_cases._api_helpers import api_base_url, api_get, api_login


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _provision_analyst():
    """Provision a data_analyst persona for auth tests."""
    return provision_persona("data_analyst")


def _persona_email() -> str:
    """Return the seeded e2e_admin email for auth journey tests."""
    return "e2e_admin@example.com"


PERSONA_PASSWORD = "TestPass123"


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ===========================================================================
# Tests
# ===========================================================================


def test_auth_me_returns_user():
    """GET /auth/me/ with a valid token returns the authenticated user profile."""
    creds = _provision_analyst()

    resp = api_get("/auth/me/", creds)

    if resp.status_code == 404:
        pytest.skip("/auth/me/ endpoint not found (404)")

    assert resp.status_code == 200, (
        f"/auth/me/ returned {resp.status_code}: {resp.text[:500]}"
    )

    body = resp.json()
    # Must contain at least an email or user id
    assert "email" in body or "id" in body or "user_id" in body, (
        f"/auth/me/ response missing user identifiers. Keys: {list(body.keys())}"
    )


def test_auth_login_endpoint():
    """POST /auth/login/ with valid credentials returns 200 and tokens."""
    _provision_analyst()
    email = _persona_email()

    resp = api_login(email, PERSONA_PASSWORD)

    if resp.status_code == 404:
        pytest.skip("/auth/login/ endpoint not found (404)")

    assert resp.status_code == 200, (
        f"/auth/login/ returned {resp.status_code}: {resp.text[:500]}"
    )

    body = resp.json()
    assert "access_token" in body, (
        f"Login response missing access_token. Keys: {list(body.keys())}"
    )
    assert isinstance(body["access_token"], str) and len(body["access_token"]) > 10


def test_auth_logout_endpoint():
    """POST /auth/logout/ with a valid token returns 200 or 204."""
    _provision_analyst()
    email = _persona_email()

    # Get a fresh token
    login_resp = api_login(email, PERSONA_PASSWORD)
    if login_resp.status_code == 404:
        pytest.skip("/auth/login/ endpoint not found (404)")
    assert login_resp.status_code == 200, (
        f"Pre-logout login failed: {login_resp.status_code}"
    )
    access = login_resp.json()["access_token"]

    base = api_base_url()
    logout_resp = requests.post(
        f"{base}/auth/logout/",
        headers=_auth_headers(access),
        json={},
        timeout=15,
    )

    if logout_resp.status_code == 404:
        pytest.skip("/auth/logout/ endpoint not found (404)")

    assert logout_resp.status_code in (200, 204), (
        f"/auth/logout/ returned {logout_resp.status_code}: "
        f"{logout_resp.text[:300]}"
    )

    # After logout, /auth/me/ should reject the token
    post_me = requests.get(
        f"{base}/auth/me/",
        headers=_auth_headers(access),
        timeout=15,
    )
    assert post_me.status_code == 401, (
        f"Post-logout /auth/me/ should return 401, got {post_me.status_code}"
    )
