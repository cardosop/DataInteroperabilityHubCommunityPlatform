import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.2.13 — Security: token replay.

Verifies that a revoked/logged-out token cannot be reused.
"""

import requests
from tests._persona_provisioning import provision_persona
from tests.use_cases._api_helpers import api_base_url, api_get, api_post


def test_logged_out_token_returns_401():
    """After logout, the old access_token must be rejected with 401."""
    creds = provision_persona("data_engineer")

    # Verify token works before logout
    resp = api_get("/auth/me/", creds)
    assert resp.status_code == 200, f"Pre-logout /auth/me/ failed: {resp.status_code}"

    # Logout
    logout_resp = api_post("/auth/logout/", creds)
    # 200 or 204 — both acceptable
    assert logout_resp.status_code in (200, 204, 205), (
        f"Logout failed: {logout_resp.status_code}"
    )

    # Replay the old token — must be rejected
    replay_resp = requests.get(
        f"{api_base_url()}/auth/me/",
        headers={"Authorization": f"Bearer {creds.api_key}"},
        timeout=15,
    )
    assert replay_resp.status_code == 401, (
        f"Replayed token after logout returned {replay_resp.status_code}, expected 401"
    )


def test_refresh_token_after_logout_returns_401():
    """After logout, the refresh_token must also be rejected."""
    creds = provision_persona("data_consumer")

    # Logout
    api_post("/auth/logout/", creds)

    # Try to refresh with the old refresh token
    refresh_resp = requests.post(
        f"{api_base_url()}/auth/refresh/",
        json={"refresh_token": creds.refresh_token},
        timeout=15,
    )
    assert refresh_resp.status_code == 401, (
        f"Refresh after logout returned {refresh_resp.status_code}, expected 401"
    )
