import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.2.2 — Signup -> onboard -> first asset.

Validates that a brand-new user can register, log in, and immediately
create their first asset. Also verifies that registration automatically
provisions a default tenant for the new user.
"""

import requests

from tests.fixtures.test_data import fresh_id
from tests.use_cases._api_helpers import (
    api_base_url,
    api_login,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unique_email() -> str:
    """Generate a unique email for registration tests."""
    uid = fresh_id("signup")
    return f"{uid}@meshant-internal.example.com"


def _register_user(
    email: str,
    password: str = "NewUser@Secure1!",
    name: str = "Signup Test User",
) -> requests.Response:
    """POST /auth/register/ with the given payload."""
    base = api_base_url()
    return requests.post(
        f"{base}/auth/register/",
        json={
            "email": email,
            "name": name,
            "password": password,
        },
        timeout=15,
    )


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ===========================================================================
# Tests
# ===========================================================================


def test_register_new_user():
    """POST /auth/register/ with a fresh, unique email returns 201 (or 200).

    The response should include at minimum the user id and email.
    """
    email = _unique_email()
    resp = _register_user(email)

    assert resp.status_code in (200, 201), (
        f"Registration returned {resp.status_code}: {resp.text[:500]}"
    )

    body = resp.json()
    # The response should echo back the email or contain a user id
    body_str = str(body).lower()
    assert email.lower() in body_str or "id" in body_str, (
        f"Registration response does not contain the email or user id: {body}"
    )


def test_register_duplicate_email_returns_conflict():
    """Registering the same email twice should return 409 or 400."""
    email = _unique_email()

    resp1 = _register_user(email)
    assert resp1.status_code in (200, 201), (
        f"First registration failed: {resp1.status_code}: {resp1.text[:300]}"
    )

    resp2 = _register_user(email)
    assert resp2.status_code in (400, 409, 422), (
        f"Duplicate registration returned {resp2.status_code}, expected 400/409/422: "
        f"{resp2.text[:300]}"
    )


def test_register_weak_password_rejected():
    """Registration with a weak password should be rejected (400 or 422)."""
    email = _unique_email()
    resp = _register_user(email, password="123")

    assert resp.status_code in (400, 422), (
        f"Weak password accepted with {resp.status_code}, expected 400/422: {resp.text[:300]}"
    )


def test_register_missing_email_returns_400():
    """Registration without an email should return 400 or 422."""
    base = api_base_url()
    resp = requests.post(
        f"{base}/auth/register/",
        json={"password": "ValidPass1!", "name": "No Email"},
        timeout=15,
    )
    assert resp.status_code in (400, 422), (
        f"Missing email accepted with {resp.status_code}: {resp.text[:300]}"
    )


def test_create_first_asset_after_signup():
    """Full onboarding flow: register -> login -> create asset -> 201.

    This validates the happy path for a new user's first interaction
    with the platform.
    """
    email = _unique_email()
    password = "OnboardAsset@1!"

    # Step 1: Register
    reg_resp = _register_user(email, password=password, name="Asset Creator")
    assert reg_resp.status_code in (200, 201), (
        f"Registration failed: {reg_resp.status_code}: {reg_resp.text[:300]}"
    )

    # Step 2: Login
    login_resp = api_login(email, password)
    assert login_resp.status_code == 200, (
        f"Post-registration login failed: {login_resp.status_code}: {login_resp.text[:300]}"
    )
    tokens = login_resp.json()
    access_token = tokens["access_token"]

    # Step 3: Create asset
    asset_name = fresh_id("first-asset")
    base = api_base_url()
    create_resp = requests.post(
        f"{base}/assets/",
        headers=_auth_headers(access_token),
        json={
            "name": asset_name,
            "key": fresh_id("asset-key"),  # noqa: PHASE216-STATIC-ID
            "description": "First asset created during onboarding test",
        },
        timeout=15,
    )

    assert create_resp.status_code in (200, 201), (
        f"Asset creation after signup returned {create_resp.status_code}: {create_resp.text[:500]}"
    )
    body = create_resp.json()
    assert "id" in body or "key" in body, f"Asset creation response missing id/key: {body}"


def test_onboarding_creates_default_tenant():
    """After registration, the user should have a tenant_id assigned
    (either via the registration response or visible in /auth/me/).
    """
    email = _unique_email()
    password = "TenantCheck@1!"

    # Register
    reg_resp = _register_user(email, password=password, name="Tenant Checker")
    assert reg_resp.status_code in (200, 201), (
        f"Registration failed: {reg_resp.status_code}: {reg_resp.text[:300]}"
    )

    # Login to get a token
    login_resp = api_login(email, password)
    assert login_resp.status_code == 200, (
        f"Login failed: {login_resp.status_code}: {login_resp.text[:300]}"
    )
    tokens = login_resp.json()
    access_token = tokens["access_token"]

    # Check /auth/me/ for tenant information
    base = api_base_url()
    me_resp = requests.get(
        f"{base}/auth/me/",
        headers=_auth_headers(access_token),
        timeout=15,
    )
    assert me_resp.status_code == 200, (
        f"/auth/me/ returned {me_resp.status_code}: {me_resp.text[:300]}"
    )

    me_body = me_resp.json()
    # The user should have at least one tenant associated
    tenant_id = (
        me_body.get("tenant_id")  # noqa: PHASE216-STATIC-ID
        or (me_body.get("tenants", [{}])[0].get("id") if me_body.get("tenants") else None)
        or tokens.get("tenant_id")  # noqa: PHASE216-STATIC-ID
    )
    assert tenant_id, (
        f"New user has no tenant_id. /auth/me/ body: {me_body}, login tokens: {list(tokens.keys())}"
    )


def test_registered_user_can_login():
    """Immediately after registration, the user can log in successfully."""
    email = _unique_email()
    password = "LoginAfterReg@1!"

    reg_resp = _register_user(email, password=password)
    assert reg_resp.status_code in (200, 201)

    login_resp = api_login(email, password)
    assert login_resp.status_code == 200, (
        f"Login after registration returned {login_resp.status_code}: {login_resp.text[:300]}"
    )
    body = login_resp.json()
    assert "access_token" in body


def test_registered_user_appears_in_me():
    """After registration and login, /auth/me/ returns the correct email."""
    email = _unique_email()
    password = "MeEndpoint@1!"

    _register_user(email, password=password, name="Me Test")
    login_resp = api_login(email, password)
    assert login_resp.status_code == 200
    access = login_resp.json()["access_token"]

    base = api_base_url()
    me_resp = requests.get(
        f"{base}/auth/me/",
        headers=_auth_headers(access),
        timeout=15,
    )
    assert me_resp.status_code == 200
    me_body = me_resp.json()

    # The response should contain the registered email
    assert email.lower() in str(me_body).lower(), f"/auth/me/ does not contain {email}: {me_body}"
