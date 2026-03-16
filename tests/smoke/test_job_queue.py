"""
Smoke test — job queue end-to-end.

Enqueues a no-op job via the API and polls until it reaches a terminal state
(COMPLETED / SUCCEEDED / done) within a 30-second timeout.

This validates that:
  1. The API can accept and persist a job request
  2. The worker service is alive and consuming from the queue
  3. Redis (the RQ broker) is reachable from both API and worker
  4. The job reaches a terminal SUCCESS state (not stuck in QUEUED/RUNNING)

Required env vars:
    SMOKE_ADMIN_EMAIL / SMOKE_ADMIN_PASSWORD  (via conftest admin_credentials)

Optional env vars:
    SMOKE_JOB_API_PATH    Path to the jobs API (default: /api/v1/jobs/)
    SMOKE_JOB_TYPE        Job type identifier for no-op test (default: no_op)
    SMOKE_JOB_POLL_TIMEOUT  Max seconds to wait for completion (default: 30)
    SMOKE_JOB_POLL_INTERVAL Poll interval in seconds (default: 2)

Terminal states recognised (case-insensitive):
    completed, succeeded, done, success, finished, failed, error

A FAILED/ERROR terminal state causes the test to fail with the job's error
message, giving actionable signal even when the job infrastructure is up.
"""
import os
import time
import pytest
import requests

JOB_API_PATH = os.getenv("SMOKE_JOB_API_PATH", "/api/v1/jobs/")
JOB_TYPE = os.getenv("SMOKE_JOB_TYPE", "no_op")
POLL_TIMEOUT = int(os.getenv("SMOKE_JOB_POLL_TIMEOUT", "30"))
POLL_INTERVAL = float(os.getenv("SMOKE_JOB_POLL_INTERVAL", "2"))

# Terminal states (normalised to lowercase for comparison)
SUCCESS_STATES = frozenset({"completed", "succeeded", "done", "success", "finished"})
FAILURE_STATES = frozenset({"failed", "error", "errored", "cancelled", "canceled"})
TERMINAL_STATES = SUCCESS_STATES | FAILURE_STATES


def _get_job_status(
    session: requests.Session,
    base_url: str,
    job_id: str,
    timeout: int,
) -> dict:
    """Fetch the current status of a job by ID."""
    response = session.get(
        f"{base_url}{JOB_API_PATH}{job_id}/",
        timeout=timeout,
    )
    assert response.status_code == 200, (
        f"Job status endpoint returned {response.status_code}: {response.text[:300]}"
    )
    return response.json()


class TestJobQueue:
    """Validate the job queue pipeline is operational after deployment."""

    def test_enqueue_noop_job_and_poll_completion(
        self,
        base_url: str,
        authenticated_session: requests.Session,
        timeout: int,
    ) -> None:
        """
        Enqueue a no-op job, poll until it reaches a SUCCESS terminal state.

        Timeout: SMOKE_JOB_POLL_TIMEOUT seconds (default: 30).
        """
        # --- Step 1: Enqueue the job ----------------------------------------
        enqueue_response = authenticated_session.post(
            f"{base_url}{JOB_API_PATH}",
            json={
                "job_type": JOB_TYPE,
                "payload": {},
                "priority": "low",
            },
            timeout=timeout,
        )
        if enqueue_response.status_code == 404:
            pytest.skip(
                f"Job endpoint not found at {JOB_API_PATH} — "
                "set SMOKE_JOB_API_PATH to the correct path"
            )
        if enqueue_response.status_code == 422:
            pytest.skip(
                f"Job creation returned 422 — payload fields may differ: "
                f"{enqueue_response.text[:300]}"
            )

        assert enqueue_response.status_code in (200, 201, 202), (
            f"Job enqueue failed ({enqueue_response.status_code}): "
            f"{enqueue_response.text[:500]}"
        )

        job_data = enqueue_response.json()
        job_id = job_data.get("id") or job_data.get("job_id") or job_data.get("uuid")
        assert job_id, f"Enqueue response missing job ID: {job_data}"
        print(f"\nEnqueued job_id={job_id}, initial status={job_data.get('status')}")

        # --- Step 2: Poll until terminal state or timeout -------------------
        deadline = time.monotonic() + POLL_TIMEOUT
        last_status: str = job_data.get("status", "unknown")

        while time.monotonic() < deadline:
            current = _get_job_status(
                authenticated_session, base_url, str(job_id), timeout
            )
            last_status = str(current.get("status", "unknown")).lower()
            print(
                f"  job_id={job_id} status={last_status} "
                f"(elapsed={time.monotonic() - (deadline - POLL_TIMEOUT):.1f}s)"
            )

            if last_status in TERMINAL_STATES:
                break
            time.sleep(POLL_INTERVAL)
        else:
            pytest.fail(
                f"Job {job_id} did not reach a terminal state within {POLL_TIMEOUT}s. "
                f"Last observed status: '{last_status}'. "
                "Check that the worker service is running and consuming the queue."
            )

        # --- Step 3: Assert the terminal state is SUCCESS -------------------
        if last_status in FAILURE_STATES:
            final = _get_job_status(
                authenticated_session, base_url, str(job_id), timeout
            )
            error_detail = final.get("error") or final.get("error_message") or final
            pytest.fail(
                f"Job {job_id} reached terminal FAILURE state '{last_status}'. "
                f"Error: {error_detail}"
            )

        assert last_status in SUCCESS_STATES, (
            f"Job {job_id} ended in unexpected state '{last_status}' "
            f"(not in success states: {SUCCESS_STATES})"
        )
        print(f"  ✓ Job {job_id} completed successfully in state '{last_status}'")
