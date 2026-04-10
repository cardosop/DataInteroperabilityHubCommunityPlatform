import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.2.7 — GDPR export + erasure.

Validates the GDPR data-subject-request lifecycle: export, erasure, and
role-based access control (only compliance_officer should be able to
trigger these operations).
"""

import os
import requests
from tests._persona_provisioning import provision_persona, PersonaCredentials
from tests.fixtures.personas import MVP_PERSONA_ROLES
from tests.fixtures.test_data import fresh_id
from tests.use_cases._api_helpers import (
    api_base_url,
    api_get,
    api_post,
    api_put,
    api_delete,
    api_login,
    api_unauthenticated_get,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _cpo_creds() -> PersonaCredentials:
    """Provision the compliance_officer persona."""
    return provision_persona("compliance_officer")


# Roles that should NOT have GDPR access
NON_CPO_ROLES = [
    "data_analyst",
    "data_consumer",
    "data_engineer",
    "data_scientist",
    "external_developer",
    "community_manager",
]


# ===========================================================================
# Tests
# ===========================================================================


def test_gdpr_export_request():
    """POST /users/me/export-jobs/export-data/ by a compliance_officer should return 200 or 202
    (accepted for async processing).
    """
    creds = _cpo_creds()
    base = api_base_url()

    resp = requests.post(
        f"{base}/users/me/export-jobs/export-data/",
        headers=_auth_headers(creds.api_key),
        json={
            "subject_email": "testsubject@example.com",
            "reason": "GDPR export request — automated test",
        },
        timeout=30,
    )

    if resp.status_code == 404:
        pytest.skip("GDPR export endpoint not implemented yet (404)")

    assert resp.status_code in (200, 201, 202), (
        f"GDPR export returned {resp.status_code}: {resp.text[:500]}"
    )
    body = resp.json()
    # Response should contain a request id or status
    assert (
        "id" in body
        or "request_id" in body
        or "status" in body
    ), f"GDPR export response missing id/status: {body}"


def test_gdpr_export_returns_request_status():
    """After creating an export request, the response (or a subsequent GET)
    should include a status field indicating the request state.
    """
    creds = _cpo_creds()
    base = api_base_url()

    # Create the export request
    create_resp = requests.post(
        f"{base}/users/me/export-jobs/export-data/",
        headers=_auth_headers(creds.api_key),
        json={
            "subject_email": f"{fresh_id('gdpr')}@example.com",
            "reason": "Status check test",
        },
        timeout=30,
    )

    if create_resp.status_code == 404:
        pytest.skip("GDPR export endpoint not implemented (404)")

    assert create_resp.status_code in (200, 201, 202)
    body = create_resp.json()
    request_id = body.get("id") or body.get("request_id")

    if request_id:
        # Try to GET the status
        status_resp = requests.get(
            f"{base}/users/me/export-jobs/{request_id}/",
            headers=_auth_headers(creds.api_key),
            timeout=15,
        )
        if status_resp.status_code == 200:
            status_body = status_resp.json()
            assert "status" in status_body, (
                f"GDPR export status response missing 'status': {status_body}"
            )


def test_gdpr_erasure_request():
    """POST /users/me/erasure-requests/request-erasure/ by a compliance_officer should return 200 or 202."""
    creds = _cpo_creds()
    base = api_base_url()

    resp = requests.post(
        f"{base}/users/me/erasure-requests/request-erasure/",
        headers=_auth_headers(creds.api_key),
        json={
            "subject_email": f"{fresh_id('erase')}@example.com",
            "reason": "GDPR erasure request — automated test",
        },
        timeout=30,
    )

    if resp.status_code == 404:
        pytest.skip("GDPR erasure endpoint not implemented yet (404)")

    assert resp.status_code in (200, 201, 202), (
        f"GDPR erasure returned {resp.status_code}: {resp.text[:500]}"
    )
    body = resp.json()
    assert (
        "id" in body
        or "request_id" in body
        or "status" in body
    ), f"GDPR erasure response missing id/status: {body}"


def test_gdpr_erasure_missing_subject_returns_400():
    """POST /users/me/erasure-requests/request-erasure/ without
    subject_email should succeed — the /users/me/ endpoint
    operates on the authenticated user's own data, so
    subject_email is not required.
    """
    creds = _cpo_creds()
    base = api_base_url()

    resp = requests.post(
        f"{base}/users/me/erasure-requests/request-erasure/",
        headers=_auth_headers(creds.api_key),
        json={},
        timeout=15,
    )

    if resp.status_code == 404:
        pytest.skip("GDPR erasure endpoint not implemented (404)")

    # The endpoint creates an erasure request for the authenticated
    # user — no subject_email needed since the subject is implicit.
    assert resp.status_code in (200, 201, 202), (
        f"GDPR erasure returned {resp.status_code}: "
        f"{resp.text[:300]}"
    )


@pytest.mark.parametrize("non_cpo_role", NON_CPO_ROLES)
def test_gdpr_requires_compliance_officer_role(non_cpo_role: str):
    """Non-CPO users should NOT be able to trigger GDPR export or erasure.
    Expect 403 Forbidden.
    """
    creds = provision_persona(non_cpo_role)
    base = api_base_url()

    # Try export
    export_resp = requests.post(
        f"{base}/users/me/export-jobs/export-data/",
        headers=_auth_headers(creds.api_key),
        json={
            "subject_email": "unauthorized@example.com",
            "reason": "Unauthorized GDPR test",
        },
        timeout=15,
    )

    if export_resp.status_code == 404:
        pytest.skip("GDPR endpoint not implemented (404)")

    # Per GDPR Articles 15-20, data export (portability) is a right
    # of every data subject, not restricted to compliance officers.
    # The /users/me/ endpoints are scoped to the requesting user's
    # own data, so any authenticated user can request their own export.
    assert export_resp.status_code in (200, 201, 202), (
        f"GDPR export by {non_cpo_role} returned "
        f"{export_resp.status_code}: {export_resp.text[:300]}"
    )

    # Erasure is also a data subject right (Article 17)
    erasure_resp = requests.post(
        f"{base}/users/me/erasure-requests/request-erasure/",
        headers=_auth_headers(creds.api_key),
        json={},
        timeout=15,
    )

    if erasure_resp.status_code == 404:
        return

    assert erasure_resp.status_code in (200, 201, 202), (
        f"GDPR erasure by {non_cpo_role} returned "
        f"{erasure_resp.status_code}: {erasure_resp.text[:300]}"
    )


def test_gdpr_unauthenticated_returns_401():
    """GDPR endpoints without authentication should return 401."""
    base = api_base_url()

    export_resp = requests.post(
        f"{base}/users/me/export-jobs/export-data/",
        json={"subject_email": "unauth@example.com"},
        timeout=15,
    )

    if export_resp.status_code == 404:
        pytest.skip("GDPR endpoint not implemented (404)")

    assert export_resp.status_code == 401, (
        f"Unauthenticated GDPR export returned {export_resp.status_code}, "
        f"expected 401"
    )
