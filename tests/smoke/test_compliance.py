"""
Smoke test — compliance pipeline end-to-end (Phase 19.16.2).

Validates the full async compliance flow after a deployment:
  1. Upload a small CSV file with PII data (email + Chinese national ID)
     via the three-step presigned-URL flow:
       POST /api/v1/files/init  →  PUT <presigned>  →  POST /api/v1/files/{id}/complete
  2. Create a compliance run via POST /api/v1/compliance/runs/
     with regulations GDPR + PIPL_CN and destination_jurisdiction US
     (cross-border: Chinese-citizen data stored outside China).
  3. Poll GET /api/v1/compliance/runs/{id}/ until status == SUCCEEDED
     (max 60 s, 5 s interval).
  4. Assert the v2 response fields are correctly populated:
       - regulation_summaries  — non-empty list (v2 per-regulation summaries)
       - cross_border_alert.applicable == True
         (PIPL_CN: Chinese national ID data transferred to US jurisdiction)
       - schema_version == "2.0"

The test cleans up the created File and ComplianceRun records on exit
via the API DELETE endpoints so it is idempotent and leaves the system
in its original state.

Required env / CLI options (all inherited from conftest):
    SMOKE_BASE_URL  /  --base-url     Deployed API base URL
    SMOKE_ADMIN_EMAIL                 Admin account for authentication
    SMOKE_ADMIN_PASSWORD

Optional:
    SMOKE_COMPLIANCE_POLL_TIMEOUT     Max seconds to wait (default: 60)
    SMOKE_COMPLIANCE_POLL_INTERVAL    Seconds between polls (default: 5)
"""

from __future__ import annotations

import hashlib
import io
import os
import time

import pytest
import requests

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

POLL_TIMEOUT = int(os.getenv("SMOKE_COMPLIANCE_POLL_TIMEOUT", "60"))
POLL_INTERVAL = float(os.getenv("SMOKE_COMPLIANCE_POLL_INTERVAL", "5"))

# Terminal states for the Django ComplianceRun.status field
_SUCCESS_STATES = frozenset({"succeeded", "completed"})
_FAILURE_STATES = frozenset({"failed", "error", "errored", "cancelled", "canceled"})
_TERMINAL_STATES = _SUCCESS_STATES | _FAILURE_STATES

# Compliance API paths (relative to base_url)
_FILES_INIT_PATH = "/api/v1/files/init/"
_FILES_COMPLETE_TPL = "/api/v1/files/{file_id}/complete/"
_FILES_DELETE_TPL = "/api/v1/files/{file_id}/"
_RUNS_PATH = "/api/v1/compliance/runs/"
_RUN_DETAIL_TPL = "/api/v1/compliance/runs/{run_id}/"

# CSV with email (triggers GDPR) + national_id_cn (triggers PIPL_CN)
_TEST_CSV = (
    b"email,national_id_cn,name\n"
    b"alice@example.com,110101199001011234,Alice\n"
    b"bob@example.com,310115198505152345,Bob\n"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _poll_run(
    session: requests.Session,
    base_url: str,
    run_id: str,
    timeout: int,
    poll_timeout: int,
    poll_interval: float,
) -> dict:
    """
    Poll the compliance run detail endpoint until it reaches a terminal state
    or the deadline expires.

    Returns the final response body dict.
    Raises pytest.fail() on timeout or FAILED terminal state.
    """
    deadline = time.monotonic() + poll_timeout
    last_data: dict = {}
    last_status = "unknown"

    while time.monotonic() < deadline:
        resp = session.get(
            f"{base_url}{_RUN_DETAIL_TPL.format(run_id=run_id)}",
            timeout=timeout,
        )
        assert resp.status_code == 200, (
            f"Polling compliance run {run_id} returned {resp.status_code}: {resp.text[:400]}"
        )
        last_data = resp.json()
        last_status = str(last_data.get("status", "unknown")).lower()

        elapsed = poll_timeout - (deadline - time.monotonic())
        print(f"  compliance_run_id={run_id} status={last_status} (elapsed={elapsed:.1f}s)")

        if last_status in _TERMINAL_STATES:
            break
        time.sleep(poll_interval)  # noqa: sleep-needed  # INTENTIONAL: test-specific delay
    else:
        pytest.fail(
            f"Compliance run {run_id} did not reach a terminal state within "
            f"{poll_timeout}s. Last status: '{last_status}'. "
            "Ensure the worker service is running and the compliance service "
            "is reachable."
        )

    if last_status in _FAILURE_STATES:
        error_detail = (
            last_data.get("regulation_mapping_json", {}).get("error")
            or last_data.get("error")
            or last_data
        )
        pytest.fail(
            f"Compliance run {run_id} reached terminal FAILURE state "
            f"'{last_status}'. Detail: {error_detail}"
        )

    return last_data


# ---------------------------------------------------------------------------
# Smoke test class
# ---------------------------------------------------------------------------


class TestCompliancePipelineV2:
    """
    Post-deploy smoke test for the compliance async pipeline.

    Exercises the full flow from file upload → compliance run creation
    → async processing → v2 result persistence, validating that the
    compliance service and Django backend are correctly wired.
    """

    def test_compliance_run_full_pipeline(
        self,
        base_url: str,
        authenticated_session: requests.Session,
        timeout: int,
    ) -> None:
        """
        Upload a PII-containing CSV, run compliance, poll until SUCCEEDED,
        and assert all v2 response fields are correctly populated.
        """
        file_id: str | None = None
        run_id: str | None = None

        try:
            # ----------------------------------------------------------------
            # Step 1: Initialise the file upload (get presigned PUT URL)
            # ----------------------------------------------------------------
            csv_size = len(_TEST_CSV)
            init_resp = authenticated_session.post(
                f"{base_url}{_FILES_INIT_PATH}",
                json={
                    "name": "smoke-compliance-test.csv",
                    "content_type": "text/csv",
                    "size": csv_size,
                    "upload_method": "sdk",
                },
                timeout=timeout,
            )
            if init_resp.status_code == 404:
                pytest.skip(  # noqa: skip-in-body — runtime service dependency
                    f"Files init endpoint not found at {_FILES_INIT_PATH} — "
                    "check SMOKE_BASE_URL and API routing."
                )
            assert init_resp.status_code in (200, 201), (
                f"File init failed ({init_resp.status_code}): {init_resp.text[:400]}"
            )

            init_data = init_resp.json()
            file_id = init_data.get("file_id")
            upload_url = init_data.get("upload_url")
            assert file_id, f"No file_id in init response: {init_data}"
            assert upload_url, f"No upload_url in init response: {init_data}"
            print(f"\n  file_id={file_id} upload_url_prefix={upload_url[:60]}…")

            # ----------------------------------------------------------------
            # Step 2: PUT file content directly to the presigned URL (S3/MinIO)
            # ----------------------------------------------------------------
            # Use a raw requests.Session (no auth header) for S3 presigned PUT —
            # sending the Authorization header to S3 causes a SignatureDoesNotMatch.
            upload_session = requests.Session()

            fields = init_data.get("fields") or {}
            if fields:
                # Presigned POST form (rare for sdk method, but handle it)
                put_resp = upload_session.post(
                    upload_url,
                    data=fields,
                    files={
                        "file": ("smoke-compliance-test.csv", io.BytesIO(_TEST_CSV), "text/csv")
                    },
                    timeout=timeout,
                )
            else:
                # Presigned PUT (standard for sdk/browser upload_method)
                put_resp = upload_session.put(
                    upload_url,
                    data=_TEST_CSV,
                    headers={"Content-Type": "text/csv"},
                    timeout=timeout,
                )

            assert put_resp.status_code in (200, 204), (
                f"S3 presigned upload failed ({put_resp.status_code}): {put_resp.text[:400]}"
            )
            print(f"  File uploaded to S3 ({csv_size} bytes, status={put_resp.status_code})")

            # ----------------------------------------------------------------
            # Step 3: Complete the upload (mark file ACTIVE in Django)
            # ----------------------------------------------------------------
            complete_resp = authenticated_session.post(
                f"{base_url}{_FILES_COMPLETE_TPL.format(file_id=file_id)}",
                json={"content_sha256": _sha256_hex(_TEST_CSV)},
                timeout=timeout,
            )
            assert complete_resp.status_code in (200, 201), (
                f"File complete failed ({complete_resp.status_code}): {complete_resp.text[:400]}"
            )
            print(f"  File marked ACTIVE (status={complete_resp.status_code})")

            # ----------------------------------------------------------------
            # Step 4: Create the compliance run
            # GDPR (email) + PIPL_CN (national_id_cn) + destination US
            # → cross_border_alert.applicable should be True (PIPL_CN data
            #   leaving China to the US triggers localisation/cross-border).
            # ----------------------------------------------------------------
            run_resp = authenticated_session.post(
                f"{base_url}{_RUNS_PATH}",
                json={
                    "file_id": file_id,
                    "scan_mode": "external",
                    "applicable_regulations": ["GDPR", "PIPL_CN"],
                    "legal_basis": "consent",
                    "destination_jurisdiction": "US",
                },
                timeout=timeout,
            )
            if run_resp.status_code == 404:
                pytest.skip(  # noqa: skip-in-body — runtime service dependency
                    f"Compliance runs endpoint not found at {_RUNS_PATH} — check SMOKE_BASE_URL."
                )
            assert run_resp.status_code in (200, 201, 202), (
                f"Compliance run create failed ({run_resp.status_code}): {run_resp.text[:500]}"
            )

            run_data = run_resp.json()
            run_id = run_data.get("id")
            assert run_id, f"No run id in create response: {run_data}"
            initial_status = run_data.get("status", "unknown")
            print(f"  Compliance run created: run_id={run_id} initial_status={initial_status}")

            # ----------------------------------------------------------------
            # Step 5: Poll until SUCCEEDED (or FAILED, or timeout)
            # ----------------------------------------------------------------
            final_data = _poll_run(
                session=authenticated_session,
                base_url=base_url,
                run_id=run_id,
                timeout=timeout,
                poll_timeout=POLL_TIMEOUT,
                poll_interval=POLL_INTERVAL,
            )

            # ----------------------------------------------------------------
            # Step 6: Assert v2 response fields
            # ----------------------------------------------------------------
            print(f"\n  Final compliance run data keys: {list(final_data.keys())}")

            # 6a — regulation_summaries must be a non-empty list
            regulation_summaries = final_data.get("regulation_summaries")
            assert regulation_summaries is not None, (
                "Expected 'regulation_summaries' key in compliance run response "
                f"(v2 schema). Got keys: {list(final_data.keys())}"
            )
            assert isinstance(regulation_summaries, list), (
                f"Expected regulation_summaries to be a list, "
                f"got {type(regulation_summaries).__name__}: {regulation_summaries!r}"
            )
            assert len(regulation_summaries) > 0, (
                "Expected regulation_summaries to be non-empty. "
                "GDPR and PIPL_CN should each produce a summary entry."
            )
            print(
                f"  ✓ regulation_summaries: {len(regulation_summaries)} "
                f"regulation(s) — {[r.get('regulation') for r in regulation_summaries]}"
            )

            # 6b — cross_border_alert.applicable must be True
            cross_border_alert = final_data.get("cross_border_alert")
            assert cross_border_alert is not None, (
                "Expected 'cross_border_alert' in compliance run response. "
                "PIPL_CN with destination_jurisdiction=US should produce this alert."
            )
            assert isinstance(cross_border_alert, dict), (
                f"Expected cross_border_alert to be a dict, got {type(cross_border_alert).__name__}"
            )
            assert cross_border_alert.get("applicable") is True, (
                "Expected cross_border_alert.applicable == True. "
                "Chinese national ID data (PIPL_CN) transferred to US jurisdiction "
                f"should trigger a cross-border alert. Got: {cross_border_alert!r}"
            )
            print(
                f"  ✓ cross_border_alert.applicable=True "
                f"regulations={cross_border_alert.get('regulations', [])}"
            )

            # 6c — schema_version must be "2.0"
            schema_version = final_data.get("schema_version")
            assert schema_version is not None, (
                "Expected 'schema_version' in compliance run response. "
                "The compliance service must return schema_version in its response."
            )
            assert schema_version == "2.0", (
                f"Expected schema_version == '2.0', got {schema_version!r}. "
                "Ensure the compliance service is running the v2 implementation."
            )
            print(f"  ✓ schema_version={schema_version!r}")

        finally:
            # ----------------------------------------------------------------
            # Cleanup: delete the compliance run and file so the test is
            # idempotent and does not pollute the target environment.
            # ----------------------------------------------------------------
            if run_id:
                try:
                    del_resp = authenticated_session.delete(
                        f"{base_url}{_RUN_DETAIL_TPL.format(run_id=run_id)}",
                        timeout=timeout,
                    )
                    print(f"\n  Cleanup: DELETE compliance run {run_id} → {del_resp.status_code}")
                except Exception as exc:
                    print(f"\n  Cleanup warning: could not delete run {run_id}: {exc}")

            if file_id:
                try:
                    del_resp = authenticated_session.delete(
                        f"{base_url}{_FILES_DELETE_TPL.format(file_id=file_id)}",
                        timeout=timeout,
                    )
                    print(f"  Cleanup: DELETE file {file_id} → {del_resp.status_code}")
                except Exception as exc:
                    print(f"  Cleanup warning: could not delete file {file_id}: {exc}")
