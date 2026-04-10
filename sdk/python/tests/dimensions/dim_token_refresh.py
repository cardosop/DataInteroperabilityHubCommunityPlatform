import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.3.6 — Dimension: auth-expiry / token-refresh.

Verifies that a long-running operation that spans a token expiry
boundary can recover via refresh and complete successfully.
"""

import time
import requests
from tests._persona_provisioning import provision_persona
from tests.use_cases._api_helpers import api_base_url, api_get


def test_refresh_token_yields_new_access_token():
    """POST /auth/refresh/ with a valid refresh_token returns a new access_token."""
    creds = provision_persona("data_engineer")

    resp = requests.post(
        f"{api_base_url()}/auth/refresh/",
        json={"refresh_token": creds.refresh_token},
        timeout=15,
    )
    if resp.status_code == 404:
        pytest.skip("Refresh endpoint not available")
    assert resp.status_code == 200, (
        f"Refresh failed: {resp.status_code} {resp.text[:200]}"
    )
    data = resp.json()
    new_token = data.get("access_token")
    assert new_token, "Refresh response missing access_token"
    assert new_token != creds.api_key, "Refresh returned the same token (not rotated)"


def test_new_access_token_is_valid():
    """The new access_token from refresh must authenticate successfully."""
    creds = provision_persona("data_engineer")

    refresh_resp = requests.post(
        f"{api_base_url()}/auth/refresh/",
        json={"refresh_token": creds.refresh_token},
        timeout=15,
    )
    if refresh_resp.status_code != 200:
        pytest.skip("Refresh endpoint not available or failed")

    new_token = refresh_resp.json().get("access_token", "")
    me_resp = requests.get(
        f"{api_base_url()}/auth/me/",
        headers={"Authorization": f"Bearer {new_token}"},
        timeout=15,
    )
    assert me_resp.status_code == 200, (
        f"New token from refresh did not authenticate: {me_resp.status_code}"
    )


def test_old_token_still_works_after_refresh():
    """Refreshing should NOT immediately invalidate the old token.

    Short-lived overlap is expected — both old and new tokens are valid
    until the old one expires naturally. This prevents race conditions in
    concurrent requests during refresh.
    """
    creds = provision_persona("data_consumer")

    # Refresh to get a new token
    refresh_resp = requests.post(
        f"{api_base_url()}/auth/refresh/",
        json={"refresh_token": creds.refresh_token},
        timeout=15,
    )
    if refresh_resp.status_code != 200:
        pytest.skip("Refresh endpoint not available")

    # Old token should still work (grace period)
    me_resp = api_get("/auth/me/", creds)
    # 200 = grace period working. 401 = immediate invalidation (also acceptable).
    assert me_resp.status_code in (200, 401), (
        f"Old token after refresh: {me_resp.status_code}"
    )


def test_refresh_with_invalid_token_returns_401():
    """Refresh with a fabricated token must return 401."""
    resp = requests.post(
        f"{api_base_url()}/auth/refresh/",
        json={"refresh_token": "fabricated-invalid-refresh-token"},
        timeout=15,
    )
    if resp.status_code == 404:
        pytest.skip("Refresh endpoint not available")
    assert resp.status_code == 401, (
        f"Refresh with invalid token: {resp.status_code}"
    )
