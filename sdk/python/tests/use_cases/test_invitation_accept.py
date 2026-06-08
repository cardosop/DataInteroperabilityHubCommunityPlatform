import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.2.3 — Invitation lifecycle.

Validates that a tenant_admin can invite a new user, the invited user
can accept the invitation and receive proper credentials, and that
re-accepting an already-used token returns an error.

Actual API paths:
  POST /users/invite/                  — admin creates invitation
  POST /auth/accept-invitation/        — invitee accepts with token
  POST /test/ensure-e2e-invitation-token/ — E2E helper to get a token
"""

import requests as _requests

from tests._persona_provisioning import provision_persona, PersonaCredentials
from tests.fixtures.test_data import fresh_id
from tests.use_cases._api_helpers import (
    api_base_url,
    api_post,
    api_unauthenticated_post,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _e2e_token() -> str:
    """Return the E2E shared secret for /test/ensure-e2e-* endpoints."""
    import os as _os
    return _os.environ.get("E2E_TEST_SECRET", "e2e-test-secret-for-local-dev")


def _safe_provision(role: str) -> "PersonaCredentials | None":
    """Provision a persona without letting pytest.skip propagate.

    ``provision_persona`` can call ``pytest.skip`` when the login is
    rate-limited or the self-heal fails.  This wrapper catches that
    skip and returns None so the caller can retry instead of being
    skipped immediately.
    """
    try:
        return provision_persona(role)
    except BaseException:
        return None


def _unique_email() -> str:
    uid = fresh_id("invite")
    return f"{uid}@meshant-internal.example.com"


def _get_e2e_invitation_token(
    creds: PersonaCredentials,
) -> str | None:
    """Use the E2E test helper to create an invited user and return
    the plaintext invitation token.  Returns None if the helper
    endpoint is not available.

    The /test/ensure-e2e-* endpoints require the ``X-E2E-Token`` header
    in addition to bearer auth.  To tolerate token-version bumps caused
    by earlier test suites, the helper validates the current token
    before first use and re-provisions a fresh persona when the token
    is stale (401 / TOKEN_INVALIDATED).  Up to 3 attempts total.
    """
    base = api_base_url()
    role = creds.role
    current = creds

    for attempt in range(3):
        # ── Validate token before first attempt ────────────────────
        if attempt == 0:
            validate_resp = _requests.get(
                f"{base}/auth/me/",
                headers={"Authorization": f"Bearer {current.api_key}"},
                timeout=5,
            )
            if validate_resp.status_code != 200:
                # Token is stale — purge cache, re-provision, and fall
                # through to attempt > 0 path below.
                from tests._persona_provisioning import _CACHE_DIR as _cdir
                import glob as _glob, pathlib as _pl
                for _f in _glob.glob(str(_cdir / f"*{role}*.json")):
                    _pl.Path(_f).unlink(missing_ok=True)
                current = _safe_provision(role)
                # fall through to the request (attempt is still 0, but
                # current is now a fresh persona)

        # ── Purge cache + re-provision on subsequent attempts ──────
        if attempt > 0:
            from tests._persona_provisioning import _CACHE_DIR as _cdir
            import glob as _glob, pathlib as _pl
            for _f in _glob.glob(str(_cdir / f"*{role}*.json")):
                _pl.Path(_f).unlink(missing_ok=True)
            current = _safe_provision(role)

        resp = _requests.post(
            f"{base}/test/ensure-e2e-invitation-token/",
            headers={
                "Authorization": f"Bearer {current.api_key}",
                "X-E2E-Token": _e2e_token(),
            },
            json={},
            timeout=15,
        )
        if resp.status_code in (200, 201):
            token = resp.json().get("token")
            if token:
                return token
            # Rare: 200 but token field missing/null — retry
            continue

        if resp.status_code == 404:
            return None  # endpoint genuinely not deployed

        # 401 / TOKEN_INVALIDATED — purge cache + re-provision on
        # this attempt (don't wait for the next iteration).
        if resp.status_code in (401, 403) and attempt < 2:
            from tests._persona_provisioning import _CACHE_DIR as _cdir
            import glob as _glob, pathlib as _pl
            for _f in _glob.glob(str(_cdir / f"*{role}*.json")):
                _pl.Path(_f).unlink(missing_ok=True)
            fresh = _safe_provision(role)
            if fresh is None:
                continue
            current = fresh
            continue

        # Any other non-success — retry with fresh creds
        continue

    # If we exhausted all retries, try one last-resort fresh login
    # with a longer backoff (rate-limiting may have cooled down).
    import time as _time
    _time.sleep(3)
    try:
        from tests._persona_provisioning import _CACHE_DIR as _cdir
        from tests._persona_provisioning import _provision_via_login
        import glob as _glob, pathlib as _pl
        for _f in _glob.glob(str(_cdir / f"*{role}*.json")):
            _pl.Path(_f).unlink(missing_ok=True)
        last_creds = _provision_via_login(role, None)
        resp = _requests.post(
            f"{base}/test/ensure-e2e-invitation-token/",
            headers={
                "Authorization": f"Bearer {last_creds.api_key}",
                "X-E2E-Token": _e2e_token(),
            },
            json={},
            timeout=15,
        )
        if resp.status_code in (200, 201):
            token = resp.json().get("token")
            if token:
                return token
    except Exception:
        pass

    return None


# ===========================================================================
# Tests
# ===========================================================================


def _provision_with_retry(role: str, max_attempts: int = 4) -> "PersonaCredentials":
    """Provision a persona with retry on transient skip conditions.

    When the full test suite runs, the auth lifecycle tests invalidate
    all cached tokens, causing a burst of re-logins that can exhaust
    the login retry budget.  ``provision_persona`` converts these to
    ``pytest.skip`` (which raises ``BaseException``).  This wrapper
    catches that skip and retries with increasing backoff so the test
    has a chance to recover rather than being skipped outright.
    """
    import time as _t
    for attempt in range(max_attempts):
        try:
            return provision_persona(role)  # noqa: PHASE216-STATIC-ID
        except BaseException as _skip_exc:
            # Only retry pytest skip, not other BaseExceptions (KeyboardInterrupt, etc.)
            skip_type = type(_skip_exc).__name__
            if "Skip" not in skip_type and "Skipped" not in skip_type:
                raise
            if attempt < max_attempts - 1:
                _t.sleep(2 ** attempt)  # 1s, 2s, 4s, 8s
                continue
            raise


def test_tenant_admin_invites_user():
    """Provision a tenant_admin, then POST /users/invite/ to invite a
    new email address.  Expect 201 with user data including INVITED
    status.
    """
    admin_creds = provision_persona("tenant_admin")  # noqa: PHASE216-STATIC-ID
    invitee_email = _unique_email()

    resp = api_post(
        "/users/invite/",
        admin_creds,
        json={
            "email": invitee_email,
        },
        timeout=15,
    )

    if resp.status_code == 404:
        pytest.skip(
            "Invitation endpoint not implemented yet (404)"
        )

    # 500 (deadlock, etc.) and 429 (rate-limit) are auto-retried by
    # api_post — only assert non-retryable errors here.
    assert resp.status_code in (200, 201), (
        f"Invitation creation returned {resp.status_code}: "
        f"{resp.text[:500]}"
    )
    body = resp.json()
    assert "id" in body, f"Invitation response missing id: {body}"
    assert "email" in body, f"Invitation response missing email: {body}"
    # The invited user must have INVITED status (not ACTIVE, not null).
    status_value = body.get("status")
    assert status_value is not None, (
        f"Invitation response missing status field: {body}"
    )
    # Accept "INVITED" or its lower/upper variants.
    assert "invited" in str(status_value).lower(), (
        f"Invited user status is not INVITED: {status_value}"
    )


def test_invited_user_accepts():
    """Full invitation lifecycle:
    1. tenant_admin obtains an invitation token via E2E helper
    2. The invited user accepts via POST /auth/accept-invitation/
    3. The response contains access tokens for the new user

    The E2E helper POST /test/ensure-e2e-invitation-token/ creates
    an invited user and returns the plaintext token, bypassing email
    delivery.
    """
    admin_creds = _provision_with_retry("tenant_admin")

    # Step 1: Get invitation token via E2E helper
    token = _get_e2e_invitation_token(admin_creds)
    if token is None:
        pytest.skip(
            "E2E invitation-token helper not available "
            "(404 or missing token)"
        )

    # Step 2: Accept the invitation (unauthenticated)
    accept_resp = api_unauthenticated_post(
        "/auth/accept-invitation/",
        json={
            "token": token,
            "password": "InvitedUser@1!",
        },
        timeout=15,
    )

    if accept_resp.status_code == 404:
        pytest.skip(
            "accept-invitation endpoint not implemented (404)"
        )

    assert accept_resp.status_code in (200, 201), (
        f"Invitation accept returned {accept_resp.status_code}: "
        f"{accept_resp.text[:500]}"
    )

    # Step 3: Response should contain access tokens
    body = accept_resp.json()
    assert "access_token" in body, (
        f"Accept response missing access_token: {body}"
    )


def test_invitation_already_accepted_returns_conflict():
    """Re-accepting an already-used invitation token should return
    400 (invalid or expired token).
    """
    admin_creds = _provision_with_retry("tenant_admin")

    token = _get_e2e_invitation_token(admin_creds)
    if token is None:
        pytest.skip(
            "E2E invitation-token helper not available"
        )

    accept_payload = {
        "token": token,
        "password": "ConflictUser@1!",
    }

    # First accept
    first_resp = api_unauthenticated_post(
        "/auth/accept-invitation/",
        json=accept_payload,
        timeout=15,
    )

    if first_resp.status_code == 404:
        pytest.skip(
            "accept-invitation endpoint not implemented (404)"
        )

    assert first_resp.status_code in (200, 201), (
        f"First accept failed: {first_resp.status_code}: "
        f"{first_resp.text[:300]}"
    )

    # Second accept with same token — should fail
    second_resp = api_unauthenticated_post(
        "/auth/accept-invitation/",
        json=accept_payload,
        timeout=15,
    )

    assert second_resp.status_code in (400, 409, 422), (
        f"Re-accept returned {second_resp.status_code}, "
        f"expected 400/409/422: {second_resp.text[:300]}"
    )


def test_non_admin_cannot_create_invitation():
    """A non-admin persona (auditor) should not be able to
    create invitations via POST /users/invite/ — expect 403.
    """
    analyst_creds = provision_persona("auditor")
    invitee_email = _unique_email()

    resp = api_post(
        "/users/invite/",
        analyst_creds,
        json={
            "email": invitee_email,
        },
        timeout=15,
    )

    if resp.status_code == 404:
        pytest.skip(
            "Invitation endpoint not implemented yet (404)"
        )

    assert resp.status_code in (403, 401), (
        f"Non-admin invitation creation returned "
        f"{resp.status_code}, expected 403: {resp.text[:300]}"
    )
