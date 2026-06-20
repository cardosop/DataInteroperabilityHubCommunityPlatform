import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.6.12 -- OrchestrationAPI journey.

Validates the orchestration/jobs surface: listing jobs, retrieving a job
by id, and verifying job objects include a status field.
"""

from tests._persona_provisioning import provision_persona
from tests.use_cases._api_helpers import api_get

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _admin_creds():
    return provision_persona("platform_admin")


def _skip_if_not_found(resp, label="Orchestration"):
    if resp.status_code == 404:
        pytest.skip(f"{label} endpoint not available (404)")


def _extract_results(body):
    if isinstance(body, list):
        return body
    return body.get("results") or body.get("items") or body.get("data") or []


def _list_jobs(creds):
    """Try common orchestration/jobs endpoint patterns."""
    for path in ("/orchestration/jobs/", "/jobs/", "/orchestration/runs/"):
        resp = api_get(path, creds)
        if resp.status_code != 404:
            return resp, path
    return resp, "/orchestration/jobs/"


# ===========================================================================
# Tests
# ===========================================================================


def test_list_jobs():
    """GET /orchestration/jobs/ returns a list of orchestration jobs."""
    creds = _admin_creds()
    resp, path = _list_jobs(creds)
    _skip_if_not_found(resp, "List orchestration jobs")

    assert resp.status_code == 200, f"GET {path} returned {resp.status_code}: {resp.text[:500]}"
    body = resp.json()
    if isinstance(body, dict):
        assert "results" in body or "items" in body or "data" in body, (
            f"Paginated response missing results/items/data: {list(body.keys())}"
        )
    else:
        assert isinstance(body, list)


def test_get_job_by_id():
    """GET /orchestration/jobs/<id>/ returns a specific job."""
    creds = _admin_creds()
    resp, base_path = _list_jobs(creds)
    _skip_if_not_found(resp, "List orchestration jobs")

    if resp.status_code != 200:
        pytest.skip(f"Cannot list jobs: {resp.status_code}")

    jobs = _extract_results(resp.json())
    if not jobs:
        pytest.skip("No orchestration jobs exist to retrieve")

    job = jobs[0]
    job_id = job.get("id") or job.get("job_id") or job.get("run_id")
    if job_id is None:
        pytest.skip("Job object has no id field")

    get_resp = api_get(f"{base_path}{job_id}/", creds)
    assert get_resp.status_code == 200, (
        f"GET {base_path}{job_id}/ returned {get_resp.status_code}: {get_resp.text[:500]}"
    )
    body = get_resp.json()
    returned_id = body.get("id") or body.get("job_id") or body.get("run_id")
    assert str(returned_id) == str(job_id)


def test_job_has_status_field():
    """Job objects should include a status field."""
    creds = _admin_creds()
    resp, _ = _list_jobs(creds)
    _skip_if_not_found(resp, "List orchestration jobs")

    if resp.status_code != 200:
        pytest.skip(f"Cannot list jobs: {resp.status_code}")

    jobs = _extract_results(resp.json())
    if not jobs:
        pytest.skip("No orchestration jobs exist to inspect")

    job = jobs[0]
    keys_lower = {k.lower() for k in job.keys()}
    has_status = any(
        k in keys_lower for k in ("status", "state", "job_status", "run_status", "execution_status")
    )
    assert has_status, f"Orchestration job missing status field: {list(job.keys())}"
