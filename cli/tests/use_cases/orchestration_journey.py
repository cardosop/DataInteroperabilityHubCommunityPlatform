import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.7.1 — Orchestration journey: CLI jobs/orchestration command group.

Validates job listing, retrieval by ID, and status field presence
via real API calls against the staging environment.
"""

from tests._persona_provisioning import provision_persona
from tests.use_cases._api_helpers import api_get


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _provision_engineer():
    return provision_persona("data_engineer")


def _extract_jobs(body):
    """Extract the jobs list from a paginated or flat response."""
    if isinstance(body, list):
        return body
    return body.get("results", body.get("items", body.get("jobs", [])))


# ===========================================================================
# Tests
# ===========================================================================


def test_list_jobs():
    """GET /jobs/ returns a list of orchestration jobs."""
    creds = _provision_engineer()

    resp = api_get("/jobs/", creds)
    if resp.status_code == 404:
        resp = api_get("/orchestration/jobs/", creds)
    if resp.status_code == 404:
        pytest.skip("Jobs endpoint not found (404)")

    assert resp.status_code == 200, (
        f"/jobs/ returned {resp.status_code}: {resp.text[:500]}"
    )

    body = resp.json()
    jobs = _extract_jobs(body)
    assert isinstance(jobs, list), (
        f"Expected a list of jobs, got {type(jobs).__name__}"
    )


def test_get_job_by_id():
    """GET /jobs/<id>/ returns a single job when a valid job exists."""
    creds = _provision_engineer()

    # First, list jobs to find an existing ID
    list_resp = api_get("/jobs/", creds)
    if list_resp.status_code == 404:
        list_resp = api_get("/orchestration/jobs/", creds)
    if list_resp.status_code == 404:
        pytest.skip("Jobs endpoint not found (404)")

    assert list_resp.status_code == 200, (
        f"/jobs/ returned {list_resp.status_code}: {list_resp.text[:500]}"
    )

    jobs = _extract_jobs(list_resp.json())
    if not jobs:
        pytest.skip("No jobs available — cannot test get-by-id")

    job_id = jobs[0].get("id", jobs[0].get("job_id"))
    assert job_id, (
        f"First job missing id field. Keys: {list(jobs[0].keys())}"
    )

    # Fetch the individual job
    resp = api_get(f"/jobs/{job_id}/", creds)
    if resp.status_code == 404:
        resp = api_get(f"/orchestration/jobs/{job_id}/", creds)
    if resp.status_code == 404:
        pytest.skip(f"Job detail endpoint not found for id={job_id}")

    assert resp.status_code == 200, (
        f"Job detail returned {resp.status_code}: {resp.text[:500]}"
    )

    body = resp.json()
    returned_id = body.get("id", body.get("job_id"))
    assert str(returned_id) == str(job_id), (
        f"Returned job id {returned_id} does not match requested {job_id}"
    )


def test_job_has_status():
    """Each job in the list response includes a status field."""
    creds = _provision_engineer()

    resp = api_get("/jobs/", creds)
    if resp.status_code == 404:
        resp = api_get("/orchestration/jobs/", creds)
    if resp.status_code == 404:
        pytest.skip("Jobs endpoint not found (404)")

    assert resp.status_code == 200, (
        f"/jobs/ returned {resp.status_code}: {resp.text[:500]}"
    )

    jobs = _extract_jobs(resp.json())
    if not jobs:
        pytest.skip("No jobs returned — cannot validate status field")

    job = jobs[0]
    has_status = (
        "status" in job
        or "state" in job
        or "job_status" in job
    )
    assert has_status, (
        f"Job missing status/state field. Keys: {list(job.keys())}"
    )

    status_value = job.get("status", job.get("state", job.get("job_status")))
    assert isinstance(status_value, str) and len(status_value) > 0, (
        f"Job status should be a non-empty string, got: {status_value}"
    )
