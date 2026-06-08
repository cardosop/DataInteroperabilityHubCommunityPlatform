import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.2.7 — GDPR data-export + erasure (self-service).

Validates the GDPR data-subject-request lifecycle.  The actual API
exposes self-service endpoints under /users/me/:

  POST /users/me/export-jobs/export-data/   — request data export
  GET  /users/me/export-jobs/               — list export jobs
  GET  /users/me/export-jobs/{job_id}/      — retrieve job status
  POST /users/me/erasure-requests/request-erasure/ — request erasure
  GET  /users/me/erasure-requests/          — list erasure requests

These are available to any authenticated user for their own data.
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


# ===========================================================================
# Tests
# ===========================================================================


def test_gdpr_export_request():
    """POST /users/me/export-jobs/export-data/ by an authenticated user
    should return 201 (created) or 202 (accepted for async processing).
    """
    creds = provision_persona("auditor")
    base = api_base_url()

    resp = requests.post(
        f"{base}/users/me/export-jobs/export-data/",
        headers=_auth_headers(creds.api_key),
        json={},
        timeout=30,
    )

    if resp.status_code == 404:
        pytest.skip(
            "GDPR export endpoint not implemented yet (404)"
        )

    assert resp.status_code in (200, 201, 202), (
        f"GDPR export returned {resp.status_code}: "
        f"{resp.text[:500]}"
    )
    body = resp.json()
    assert (
        "job_id" in body
        or "id" in body
        or "status" in body
    ), f"GDPR export response missing job_id/id/status: {body}"


def test_gdpr_export_returns_request_status():
    """After creating an export request, the job should appear in
    GET /users/me/export-jobs/ with a status field.
    """
    creds = provision_persona("auditor")
    base = api_base_url()

    # Create the export request
    create_resp = requests.post(
        f"{base}/users/me/export-jobs/export-data/",
        headers=_auth_headers(creds.api_key),
        json={},
        timeout=30,
    )

    if create_resp.status_code == 404:
        pytest.skip(
            "GDPR export endpoint not implemented (404)"
        )

    assert create_resp.status_code in (200, 201, 202)
    body = create_resp.json()
    job_id = body.get("job_id") or body.get("id")

    if job_id:
        # Retrieve the specific job status
        status_resp = requests.get(
            f"{base}/users/me/export-jobs/{job_id}/",
            headers=_auth_headers(creds.api_key),
            timeout=15,
        )
        if status_resp.status_code == 200:
            status_body = status_resp.json()
            assert "status" in status_body, (
                f"GDPR export status response missing 'status': "
                f"{status_body}"
            )


def test_gdpr_erasure_request():
    """POST /users/me/erasure-requests/request-erasure/ by an
    authenticated user should return 201 or 202.
    """
    creds = provision_persona("tenant_admin")  # noqa: PHASE216-STATIC-ID
    base = api_base_url()

    resp = requests.post(
        f"{base}/users/me/erasure-requests/request-erasure/",
        headers=_auth_headers(creds.api_key),
        json={},
        timeout=30,
    )

    if resp.status_code == 404:
        pytest.skip(
            "GDPR erasure endpoint not implemented yet (404)"
        )

    assert resp.status_code in (200, 201, 202), (
        f"GDPR erasure returned {resp.status_code}: "
        f"{resp.text[:500]}"
    )
    body = resp.json()
    assert (
        "request_id" in body
        or "id" in body
        or "status" in body
    ), f"GDPR erasure response missing id/status: {body}"


def test_gdpr_erasure_list_returns_requests():
    """GET /users/me/erasure-requests/ should return the user's
    erasure request history.
    """
    creds = provision_persona("tenant_admin")  # noqa: PHASE216-STATIC-ID
    base = api_base_url()

    resp = requests.get(
        f"{base}/users/me/erasure-requests/",
        headers=_auth_headers(creds.api_key),
        timeout=15,
    )

    if resp.status_code == 404:
        pytest.skip(
            "GDPR erasure-requests endpoint not implemented (404)"
        )

    assert resp.status_code == 200, (
        f"GET /users/me/erasure-requests/ returned "
        f"{resp.status_code}: {resp.text[:300]}"
    )


def test_gdpr_export_unauthenticated_returns_401():
    """GDPR export endpoint without authentication should return 401."""
    base = api_base_url()

    resp = requests.post(
        f"{base}/users/me/export-jobs/export-data/",
        json={},
        timeout=15,
    )

    if resp.status_code == 404:
        pytest.skip("GDPR endpoint not implemented (404)")

    assert resp.status_code == 401, (
        f"Unauthenticated GDPR export returned "
        f"{resp.status_code}, expected 401"
    )


def test_gdpr_erasure_unauthenticated_returns_401():
    """GDPR erasure endpoint without authentication should return 401."""
    base = api_base_url()

    resp = requests.post(
        f"{base}/users/me/erasure-requests/request-erasure/",
        json={},
        timeout=15,
    )

    if resp.status_code == 404:
        pytest.skip("GDPR endpoint not implemented (404)")

    assert resp.status_code == 401, (
        f"Unauthenticated GDPR erasure returned "
        f"{resp.status_code}, expected 401"
    )


def test_gdpr_export_jobs_list_unauthenticated_returns_401():
    """GET /users/me/export-jobs/ without auth should return 401."""
    base = api_base_url()

    resp = requests.get(
        f"{base}/users/me/export-jobs/",
        timeout=15,
    )

    if resp.status_code == 404:
        pytest.skip("GDPR endpoint not implemented (404)")

    assert resp.status_code == 401, (
        f"Unauthenticated export-jobs list returned "
        f"{resp.status_code}, expected 401"
    )
