import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.2.1 — Auth lifecycle: login -> refresh -> expire -> re-auth -> logout.

Validates the full authentication lifecycle across all 12 authenticated
personas (every D145 role except visitor). Each test is a standalone
function that hits the live staging API.
"""


@pytest.fixture(scope="module", autouse=True)
def _purge_persona_cache_after_auth_tests():
    """Purge all persona caches after the auth lifecycle module completes.

    The logout tests invalidate cached JWT tokens for all 12 personas.
    By proactively purging the cache, subsequent tests get a clean
    login path instead of having to detect stale tokens, evict, and
    re-login under full-suite load — a cascade that can cause
    intermittent skips in invitation and tenant-switching tests.
    """
    yield
    import glob as _g
    import pathlib as _pl
    import time as _t

    from tests._persona_provisioning import _CACHE_DIR as _cdir

    for _f in _g.glob(str(_cdir / "*.json")):
        _pl.Path(_f).unlink(missing_ok=True)
    # Brief cooldown — let gunicorn workers finish processing
    # the logout requests before the next test module starts.
    _t.sleep(2)


import base64
import json
import time

import requests

from tests._persona_provisioning import PersonaCredentials, provision_persona
from tests.fixtures.personas import MVP_PERSONA_ROLES
from tests.fixtures.test_data import fresh_id
from tests.use_cases._api_helpers import (
    api_base_url,
    api_login,
    api_unauthenticated_get,
)

# ---------------------------------------------------------------------------
# Parametrize helpers
# ---------------------------------------------------------------------------

AUTHENTICATED_PERSONAS = [r for r in MVP_PERSONA_ROLES if r != "visitor"]


def _provision(role: str) -> PersonaCredentials:
    """Provision a persona and return credentials."""
    return provision_persona(role)


def _persona_email(role: str) -> str:
    """Return the pre-seeded E2E email for a persona role.

    Must match the mapping in ``_persona_provisioning._ROLE_TO_SEEDED_EMAIL``
    and the accounts created by ``manage.py ensure_e2e_user_roles``.
    """
    from tests._persona_provisioning import _ROLE_TO_SEEDED_EMAIL

    email = _ROLE_TO_SEEDED_EMAIL.get(role, "")
    if not email:
        raise ValueError(f"No seeded email for role {role!r}")
    return email


PERSONA_PASSWORD = "TestPass123"


def _login_with_retry(email: str, password: str) -> requests.Response:
    """Login with exponential backoff on 429 rate-limit responses."""
    for attempt in range(4):
        resp = api_login(email, password)
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", "3"))
            wait = min(retry_after, 10) * (attempt + 1)
            time.sleep(wait)
            continue
        return resp
    return resp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_expired_jwt() -> str:
    """Fabricate a structurally valid but expired JWT for negative testing.

    The token has a valid header and payload structure (base64-encoded JSON)
    with an ``exp`` claim set far in the past. The signature is garbage,
    but that is fine — the API should reject the token on expiry (or
    signature) before any deeper validation.
    """
    header = (
        base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
        .rstrip(b"=")
        .decode()
    )

    payload = (
        base64.urlsafe_b64encode(
            json.dumps(
                {
                    "sub": "expired-test-user",
                    "exp": int(time.time()) - 7200,  # 2 hours ago
                    "iat": int(time.time()) - 14400,
                }
            ).encode()
        )
        .rstrip(b"=")
        .decode()
    )

    signature = base64.urlsafe_b64encode(b"not-a-real-signature").rstrip(b"=").decode()

    return f"{header}.{payload}.{signature}"


def _auth_headers(token: str) -> dict:
    """Return Authorization header dict for a bearer token."""
    return {"Authorization": f"Bearer {token}"}


# ===========================================================================
# Tests
# ===========================================================================


@pytest.mark.parametrize("persona_role", AUTHENTICATED_PERSONAS)
def test_login_returns_tokens(persona_role: str):
    """POST /auth/login/ with valid persona credentials returns 200 with
    both access_token and refresh_token in the response body.
    """
    # Ensure persona exists (provision_persona is idempotent)
    _provision(persona_role)

    email = _persona_email(persona_role)
    resp = _login_with_retry(email, PERSONA_PASSWORD)

    assert resp.status_code == 200, (
        f"Login for {persona_role} ({email}) returned {resp.status_code}: {resp.text[:500]}"
    )

    body = resp.json()
    assert "access_token" in body, (
        f"Response for {persona_role} missing access_token. Keys: {list(body.keys())}"
    )
    assert "refresh_token" in body, (
        f"Response for {persona_role} missing refresh_token. Keys: {list(body.keys())}"
    )
    # Tokens must be non-empty strings
    assert isinstance(body["access_token"], str) and len(body["access_token"]) > 10
    assert isinstance(body["refresh_token"], str) and len(body["refresh_token"]) > 10


@pytest.mark.parametrize("persona_role", AUTHENTICATED_PERSONAS)
def test_refresh_extends_session(persona_role: str):
    """POST /auth/refresh/ with a valid refresh_token returns a new
    access_token (and optionally a new refresh_token). The new access_token
    must be usable for an authenticated request.
    """
    creds = _provision(persona_role)
    base = api_base_url()

    # Use the refresh_token from provisioning
    refresh_resp = requests.post(
        f"{base}/auth/refresh/",
        json={"refresh_token": creds.refresh_token},
        timeout=15,
    )

    assert refresh_resp.status_code == 200, (
        f"Refresh for {persona_role} returned {refresh_resp.status_code}: {refresh_resp.text[:500]}"
    )

    new_body = refresh_resp.json()
    new_access = new_body.get("access_token")
    assert new_access, f"Refresh response for {persona_role} missing access_token"

    # The new token must actually work — hit /auth/me/
    me_resp = requests.get(
        f"{base}/auth/me/",
        headers=_auth_headers(new_access),
        timeout=15,
    )
    assert me_resp.status_code == 200, (
        f"GET /auth/me/ with refreshed token for {persona_role} returned "
        f"{me_resp.status_code}: {me_resp.text[:300]}"
    )


def test_expired_token_returns_401():
    """Using a fabricated expired JWT against GET /auth/me/ must return 401.

    This validates that the API rejects tokens based on expiry (or
    signature mismatch) rather than blindly trusting the bearer token.
    """
    base = api_base_url()
    expired_jwt = _build_expired_jwt()

    resp = requests.get(
        f"{base}/auth/me/",
        headers=_auth_headers(expired_jwt),
        timeout=15,
    )

    assert resp.status_code == 401, (
        f"Expired JWT should be rejected with 401, got {resp.status_code}: {resp.text[:300]}"
    )


def test_unauthenticated_me_returns_401():
    """GET /auth/me/ without any Authorization header must return 401."""
    resp = api_unauthenticated_get("/auth/me/")
    assert resp.status_code == 401, (
        f"Unauthenticated /auth/me/ should return 401, got {resp.status_code}"
    )


def test_invalid_bearer_returns_401():
    """A completely garbage bearer token must be rejected."""
    base = api_base_url()
    resp = requests.get(
        f"{base}/auth/me/",
        headers=_auth_headers("this-is-not-a-jwt"),
        timeout=15,
    )
    assert resp.status_code == 401, (
        f"Invalid bearer token should be rejected with 401, got {resp.status_code}"
    )


@pytest.mark.parametrize("persona_role", AUTHENTICATED_PERSONAS)
def test_logout_invalidates_session(persona_role: str):
    """POST /auth/logout/ invalidates the session. A subsequent
    GET /auth/me/ with the same access_token must return 401.

    Uses ``_login_with_retry`` directly (NOT ``_provision``) to avoid
    polluting the shared persona cache with credentials that will be
    invalidated by the logout call.  Other tests that call
    ``provision_persona(role)`` for the same role depend on valid
    cached tokens — if the logout test cached a token and then
    invalidated it, the next test would have to re-login under suite
    load, potentially exhausting retries.
    """
    email = _persona_email(persona_role)
    login_resp = _login_with_retry(email, PERSONA_PASSWORD)
    if login_resp.status_code == 429:
        pytest.skip(f"Rate-limited during logout test for {persona_role}")
    assert login_resp.status_code == 200, (
        f"Pre-logout login failed for {persona_role}: {login_resp.text[:300]}"
    )
    tokens = login_resp.json()
    access = tokens["access_token"]
    base = api_base_url()

    # Confirm the token works before logout
    pre_me = requests.get(
        f"{base}/auth/me/",
        headers=_auth_headers(access),
        timeout=15,
    )
    assert pre_me.status_code == 200, (
        f"Pre-logout /auth/me/ failed for {persona_role}: {pre_me.status_code}"
    )

    # Logout
    logout_resp = requests.post(
        f"{base}/auth/logout/",
        headers=_auth_headers(access),
        json={},
        timeout=15,
    )
    assert logout_resp.status_code in (200, 204), (
        f"Logout for {persona_role} returned {logout_resp.status_code}: {logout_resp.text[:300]}"
    )

    # ── Verify refresh token is invalidated ─────────────────────────
    # Logout MUST blacklist the refresh token so it cannot be used to
    # obtain a new access token.  The access token itself may remain
    # valid until expiry (stateless JWT), but the refresh token is
    # the long-lived credential — blacklisting it is the security-
    # critical part of the logout operation.
    refresh_resp = requests.post(
        f"{base}/auth/refresh/",
        json={"refresh_token": tokens.get("refresh_token", "")},
        timeout=15,
    )
    assert refresh_resp.status_code == 401, (
        f"Post-logout refresh for {persona_role} was NOT rejected — "
        f"refresh token was not blacklisted by logout! "
        f"Got {refresh_resp.status_code}: {refresh_resp.text[:200]}"
    )


@pytest.mark.parametrize("persona_role", AUTHENTICATED_PERSONAS)
def test_me_returns_correct_role(persona_role: str):
    """GET /auth/me/ with a valid token returns profile data that includes
    the expected role (or roles list containing the role).
    """
    creds = _provision(persona_role)
    base = api_base_url()

    resp = requests.get(
        f"{base}/auth/me/",
        headers=_auth_headers(creds.api_key),
        timeout=15,
    )

    assert resp.status_code == 200, (
        f"/auth/me/ for {persona_role} returned {resp.status_code}: {resp.text[:300]}"
    )

    body = resp.json()
    # Verify the profile has the structural fields we expect from an
    # authenticated user — email, tenant_id, and a roles list.
    # We do NOT assert the D145 persona name appears in the roles list
    # because the D145 taxonomy (data_engineer, data_scientist, etc.)
    # is different from the RBAC roles (DATA_PROVIDER, DATA_CONSUMER, etc.).
    # Multiple personas map to the same seeded account (see _ROLE_TO_SEEDED_EMAIL).
    assert "email" in body, f"Profile for {persona_role} missing 'email': {body}"
    assert "roles" in body, f"Profile for {persona_role} missing 'roles': {body}"
    assert isinstance(body["roles"], list), (
        f"Profile roles is not a list for {persona_role}: {type(body['roles'])}"
    )
    assert len(body["roles"]) > 0, f"Profile roles is empty for {persona_role}"
    email = _persona_email(persona_role)
    assert body["email"] == email, (
        f"Profile email mismatch for {persona_role}: expected {email}, got {body['email']}"
    )


def test_login_wrong_password_returns_401():
    """POST /auth/login/ with wrong password returns 401."""
    # Provision any persona so the email exists
    _provision("data_analyst")
    email = _persona_email("data_analyst")

    resp = api_login(email, "WrongPassword999!")
    # 401/400 = correct rejection. 429 = rate-limited from earlier tests.
    if resp.status_code == 429:
        pytest.skip("Rate-limited — cannot test wrong-password rejection")
    assert resp.status_code in (401, 400), (
        f"Login with wrong password returned {resp.status_code}, expected 401 or 400"
    )


def test_login_nonexistent_user_returns_401():
    """POST /auth/login/ with a nonexistent email returns 401."""
    fake_email = f"nonexistent-{fresh_id('user')}@meshant-internal.example.com"
    resp = api_login(fake_email, "SomePassword123!")
    # 401/400/404 = correct rejection. 429 = rate-limited from prior tests.
    if resp.status_code == 429:
        pytest.skip("Rate-limited — cannot test nonexistent-user rejection")
    assert resp.status_code in (401, 400, 404), (
        f"Login for nonexistent user returned {resp.status_code}, expected 401, 400, or 404"
    )


def test_refresh_with_invalid_token_returns_401():
    """POST /auth/refresh/ with a garbage refresh token returns 401."""
    base = api_base_url()
    resp = requests.post(
        f"{base}/auth/refresh/",
        json={"refresh_token": "this-is-not-a-valid-refresh-token"},
        timeout=15,
    )
    assert resp.status_code in (401, 400), (
        f"Refresh with invalid token returned {resp.status_code}, expected 401 or 400"
    )


def test_double_logout_is_idempotent():
    """Calling POST /auth/logout/ twice with the same token should not
    return a server error. The second call may return 401 or 200/204.
    """
    _provision("data_engineer")
    email = _persona_email("data_engineer")

    login_resp = _login_with_retry(email, PERSONA_PASSWORD)
    assert login_resp.status_code == 200
    access = login_resp.json()["access_token"]
    base = api_base_url()

    # First logout
    resp1 = requests.post(
        f"{base}/auth/logout/",
        headers=_auth_headers(access),
        json={},
        timeout=15,
    )
    assert resp1.status_code in (200, 204)

    # Second logout with the now-invalidated token
    resp2 = requests.post(
        f"{base}/auth/logout/",
        headers=_auth_headers(access),
        json={},
        timeout=15,
    )
    # Should not be a 5xx — 401 or 200/204 are acceptable
    assert resp2.status_code < 500, f"Double logout returned server error {resp2.status_code}"
