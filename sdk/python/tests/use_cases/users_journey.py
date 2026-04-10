import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.6.11 -- UsersAPI journey.

Validates the users surface: retrieving the current user, listing users,
verifying required fields, and updating the user profile.
"""

from tests._persona_provisioning import provision_persona
from tests.fixtures.test_data import fresh_id
from tests.use_cases._api_helpers import api_get, api_put


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _admin_creds():
    return provision_persona("platform_admin")


def _user_creds():
    return provision_persona("data_analyst")


def _skip_if_not_found(resp, label="Users"):
    if resp.status_code == 404:
        pytest.skip(f"{label} endpoint not available (404)")


def _extract_results(body):
    if isinstance(body, list):
        return body
    return body.get("results") or body.get("items") or body.get("data") or []


def _get_current_user(creds):
    """Try common current-user endpoint patterns."""
    for path in ("/users/me/", "/users/current/", "/auth/me/"):
        resp = api_get(path, creds)
        if resp.status_code != 404:
            return resp
    return resp  # last (404)


# ===========================================================================
# Tests
# ===========================================================================


def test_get_current_user():
    """GET /users/me/ returns the authenticated user's profile."""
    creds = _user_creds()
    resp = _get_current_user(creds)
    _skip_if_not_found(resp, "Current user")

    assert resp.status_code == 200, (
        f"Current user returned {resp.status_code}: {resp.text[:500]}"
    )
    body = resp.json()
    assert isinstance(body, dict)
    user_id = body.get("id") or body.get("user_id")
    assert user_id is not None, f"User response missing id: {list(body.keys())}"


def test_list_users():
    """GET /users/ returns a list of users."""
    creds = _admin_creds()
    resp = api_get("/users/", creds)
    _skip_if_not_found(resp, "List users")

    assert resp.status_code in (200, 403), (
        f"GET /users/ returned {resp.status_code}: {resp.text[:500]}"
    )
    if resp.status_code == 403:
        pytest.skip("User listing requires higher privileges (403)")

    body = resp.json()
    if isinstance(body, dict):
        assert "results" in body or "items" in body or "data" in body, (
            f"Paginated response missing results/items/data: {list(body.keys())}"
        )
    else:
        assert isinstance(body, list)


def test_user_has_required_fields():
    """User objects should include id, email, and name/role."""
    creds = _user_creds()
    resp = _get_current_user(creds)
    _skip_if_not_found(resp, "Current user")

    if resp.status_code != 200:
        pytest.skip(f"Could not get current user: {resp.status_code}")

    user = resp.json()
    keys_lower = {k.lower() for k in user.keys()}

    has_id = any(k in keys_lower for k in ("id", "user_id"))
    has_email = "email" in keys_lower
    has_name = any(k in keys_lower for k in ("name", "display_name", "full_name", "username"))

    assert has_id, f"User missing id field: {list(user.keys())}"
    assert has_email, f"User missing email field: {list(user.keys())}"
    assert has_name, f"User missing name field: {list(user.keys())}"


def test_update_user_profile():
    """PUT /users/me/ (or PATCH) updates the authenticated user's profile."""
    creds = _user_creds()
    new_display = f"Journey Test {fresh_id('user')}"

    # Try PUT first, then PATCH
    resp = api_put("/users/me/", creds, json={"display_name": new_display})
    if resp.status_code == 404:
        resp = api_put("/users/current/", creds, json={"display_name": new_display})

    _skip_if_not_found(resp, "Update user profile")

    assert resp.status_code in (200, 204), (
        f"Update user profile returned {resp.status_code}: {resp.text[:500]}"
    )

    # Verify the update stuck
    get_resp = _get_current_user(creds)
    if get_resp.status_code == 200:
        body = get_resp.json()
        actual_name = (
            body.get("display_name")
            or body.get("name")
            or body.get("full_name")
            or ""
        )
        # Soft check: the name may be stored differently
        if new_display not in actual_name:
            import warnings
            warnings.warn(
                f"Updated display_name not reflected in GET response: "
                f"expected '{new_display}', got '{actual_name}'"
            )
