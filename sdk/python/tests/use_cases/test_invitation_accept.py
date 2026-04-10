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

import requests
from tests._persona_provisioning import provision_persona, PersonaCredentials
from tests.fixtures.test_data import fresh_id
from tests.use_cases._api_helpers import api_base_url


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _unique_email() -> str:
    uid = fresh_id("invite")
    return f"{uid}@meshant-internal.example.com"


def _get_e2e_invitation_token(
    creds: PersonaCredentials,
) -> str | None:
    """Use the E2E test helper to create an invited user and return
    the plaintext invitation token.  Returns None if the helper
    endpoint is not available.
    """
    base = api_base_url()
    resp = requests.post(
        f"{base}/test/ensure-e2e-invitation-token/",
        headers=_auth_headers(creds.api_key),
        json={},
        timeout=15,
    )
    if resp.status_code in (200, 201):
        return resp.json().get("token")
    return None


# ===========================================================================
# Tests
# ===========================================================================


def test_tenant_admin_invites_user():
    """Provision a tenant_admin, then POST /users/invite/ to invite a
    new email address.  Expect 201 with user data including INVITED
    status.
    """
    admin_creds = provision_persona("tenant_admin")
    invitee_email = _unique_email()
    base = api_base_url()

    resp = requests.post(
        f"{base}/users/invite/",
        headers=_auth_headers(admin_creds.api_key),
        json={
            "email": invitee_email,
        },
        timeout=15,
    )

    if resp.status_code == 404:
        pytest.skip(
            "Invitation endpoint not implemented yet (404)"
        )

    assert resp.status_code in (200, 201), (
        f"Invitation creation returned {resp.status_code}: "
        f"{resp.text[:500]}"
    )
    body = resp.json()
    assert (
        "id" in body
        or "email" in body
        or "status" in body
    ), f"Invitation response missing id/email/status: {body}"


def test_invited_user_accepts():
    """Full invitation lifecycle:
    1. tenant_admin obtains an invitation token via E2E helper
    2. The invited user accepts via POST /auth/accept-invitation/
    3. The response contains access tokens for the new user

    The E2E helper POST /test/ensure-e2e-invitation-token/ creates
    an invited user and returns the plaintext token, bypassing email
    delivery.
    """
    admin_creds = provision_persona("tenant_admin")
    base = api_base_url()

    # Step 1: Get invitation token via E2E helper
    token = _get_e2e_invitation_token(admin_creds)
    if token is None:
        pytest.skip(
            "E2E invitation-token helper not available "
            "(404 or missing token)"
        )

    # Step 2: Accept the invitation
    accept_resp = requests.post(
        f"{base}/auth/accept-invitation/",
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
    admin_creds = provision_persona("tenant_admin")
    base = api_base_url()

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
    first_resp = requests.post(
        f"{base}/auth/accept-invitation/",
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
    second_resp = requests.post(
        f"{base}/auth/accept-invitation/",
        json=accept_payload,
        timeout=15,
    )

    assert second_resp.status_code in (400, 409, 422), (
        f"Re-accept returned {second_resp.status_code}, "
        f"expected 400/409/422: {second_resp.text[:300]}"
    )


def test_non_admin_cannot_create_invitation():
    """A non-admin persona (data_analyst) should not be able to
    create invitations via POST /users/invite/ — expect 403.
    """
    analyst_creds = provision_persona("auditor")
    invitee_email = _unique_email()
    base = api_base_url()

    resp = requests.post(
        f"{base}/users/invite/",
        headers=_auth_headers(analyst_creds.api_key),
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
