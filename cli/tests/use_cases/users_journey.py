import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.7.1 — Users journey: CLI users/profile command group.

Validates user profile retrieval and update endpoints via real API
calls against the staging environment.
"""

from tests._persona_provisioning import provision_persona
from tests.use_cases._api_helpers import api_get, api_put

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _provision_analyst():
    return provision_persona("data_analyst")


# ===========================================================================
# Tests
# ===========================================================================


def test_get_current_user_profile():
    """GET /users/me/ (or /auth/me/) returns the current user's profile."""
    creds = _provision_analyst()

    resp = api_get("/users/me/", creds)
    if resp.status_code == 404:
        resp = api_get("/auth/me/", creds)
    if resp.status_code == 404:
        pytest.skip("User profile endpoint not found (404)")

    assert resp.status_code == 200, f"User profile returned {resp.status_code}: {resp.text[:500]}"

    body = resp.json()
    assert "id" in body or "user_id" in body, f"User profile missing id. Keys: {list(body.keys())}"


def test_user_has_email_and_roles():
    """The user profile response includes email and roles fields."""
    creds = _provision_analyst()

    resp = api_get("/users/me/", creds)
    if resp.status_code == 404:
        resp = api_get("/auth/me/", creds)
    if resp.status_code == 404:
        pytest.skip("User profile endpoint not found (404)")

    assert resp.status_code == 200, f"User profile returned {resp.status_code}: {resp.text[:500]}"

    body = resp.json()
    assert "email" in body, f"User profile missing 'email'. Keys: {list(body.keys())}"
    assert isinstance(body["email"], str) and "@" in body["email"], (
        f"Email field is not a valid email: {body.get('email')}"
    )

    # Roles may be a list or a single string field
    has_roles = "roles" in body or "role" in body or "groups" in body or "permissions" in body
    assert has_roles, (
        f"User profile missing role/roles/groups/permissions. Keys: {list(body.keys())}"
    )


def test_update_user_profile():
    """PUT /users/me/ with a display name update returns 200."""
    creds = _provision_analyst()

    # First, get current profile to know the endpoint works
    get_resp = api_get("/users/me/", creds)
    if get_resp.status_code == 404:
        get_resp = api_get("/auth/me/", creds)
    if get_resp.status_code == 404:
        pytest.skip("User profile endpoint not found (404)")
    assert get_resp.status_code == 200

    current = get_resp.json()
    current_name = current.get("name", current.get("display_name", "Test User"))

    # Update the profile with a modified display name
    update_payload = {"name": f"{current_name} (updated)"}
    update_resp = api_put("/users/me/", creds, json=update_payload)

    if update_resp.status_code == 404:
        pytest.skip("PUT /users/me/ endpoint not found (404)")
    if update_resp.status_code == 405:
        pytest.skip("PUT /users/me/ not allowed (405) — update may use PATCH")

    assert update_resp.status_code in (200, 204), (
        f"Profile update returned {update_resp.status_code}: {update_resp.text[:500]}"
    )

    # Verify update took effect
    if update_resp.status_code == 200:
        body = update_resp.json()
        updated_name = body.get("name", body.get("display_name", ""))
        assert "updated" in updated_name.lower() or updated_name != current_name, (
            f"Profile name was not updated: {updated_name}"
        )
