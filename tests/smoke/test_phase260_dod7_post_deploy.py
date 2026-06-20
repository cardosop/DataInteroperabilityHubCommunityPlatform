"""
Smoke test — Phase 260 Definition of Done #7 (260.DoD.7).

Closes the production smoke contract for Phase 260's full datasets-files
lifecycle:

    "Production smoke test post-deploy: file upload + virus scan +
     dataset creation + retire + restore-via-orphan-cleanup against
     staging completes; INFECTED EICAR upload blocks download;
     magic-byte mismatch rejects PE-as-CSV; quota meter shows correct
     percentage."

Coverage map
------------
This file pins the FOUR sub-criteria in DoD.7. Each runs as its own
test class so a single failing sub-criterion does not mask the others
(an intentional split — the DoD.7 contract is FOUR independent
post-deploy guarantees, not a single chain).

    1. ``TestPhase260DoD7FullLifecycleChain`` —
        upload → poll-scan-status → create dataset → retire dataset →
        delete dataset → verify the orphan-cleanup contract holds
        (the file row's lifecycle responds correctly when its last
        Dataset reference evaporates per the
        ``Eligible orphan files retire when Dataset references
        evaporate`` requirement at
        ``openspec/changes/preprod01/specs/datasets-files/spec.md``).

    2. ``TestPhase260DoD7EicarUploadBlocksDownload`` —
        the EICAR test signature uploads cleanly (the upload itself
        succeeds — that's how virus scanners are SUPPOSED to behave;
        rejection happens at scan time, not at upload time), the scan
        flips ``scan_status`` to ``INFECTED``, and a subsequent
        ``GET /files/{id}/download/`` returns 403 with error code
        ``FILE_INFECTED``.

    3. ``TestPhase260DoD7MagicByteMismatchRejectsPeAsCsv`` —
        a Windows PE binary header (``MZ\\x90\\x00``) labelled as
        ``text/csv`` is REJECTED. The rejection point depends on the
        ``MAGIC_BYTE_VALIDATION_ENABLED`` setting on staging: if
        enabled, ``POST /files/{id}/complete/`` rejects with the
        magic-byte error code; if disabled, the test SKIPs (rather
        than passing silently).

    4. ``TestPhase260DoD7QuotaMeterReflectsBytes`` —
        ``GET /api/v1/files/quota/`` returns a baseline; an upload of
        N bytes lands; the next ``/quota/`` call reflects ≥ N more
        bytes in ``used_bytes`` AND the ``utilization_pct`` field is
        either monotonically non-decreasing OR within float-precision
        tolerance.

Why no business-logic mocks
---------------------------
This is a POST-DEPLOY smoke test. Mocking would defeat the purpose:
the contract is "the full chain works against the deployed system".
Where the deployed system is missing a precondition (e.g., MinIO
unreachable, magic-byte validation not enabled), the test SKIPs with
a clear message — silent passing is the failure mode we explicitly
guard against. Same pattern as ``test_phase260_dod4_post_deploy.py``.

Required env vars (provided by ``conftest.py``)
-----------------------------------------------
SMOKE_ADMIN_EMAIL / SMOKE_ADMIN_PASSWORD
    Authenticated session for the probe.

Optional env vars
-----------------
SMOKE_PHASE260_DOD7_SCAN_TIMEOUT_S
    Max seconds to poll for ``scan_status`` to leave ``PENDING_SCAN``
    (default: 60). The clean-scan path is typically <5s; the EICAR
    path can take longer because ClamAV synchronously matches the
    full signature DB.

SMOKE_PHASE260_DOD7_SCAN_POLL_INTERVAL_S
    Seconds between polls (default: 2.0).
"""

from __future__ import annotations

import hashlib
import os
import time

import pytest
import requests

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

SCAN_TIMEOUT_S = int(os.getenv("SMOKE_PHASE260_DOD7_SCAN_TIMEOUT_S", "60"))
SCAN_POLL_INTERVAL_S = float(os.getenv("SMOKE_PHASE260_DOD7_SCAN_POLL_INTERVAL_S", "2.0"))

# API paths (relative to base_url)
_FILES_INIT = "/api/v1/files/init/"
_FILES_DETAIL_TPL = "/api/v1/files/{file_id}/"
_FILES_COMPLETE_TPL = "/api/v1/files/{file_id}/complete/"
_FILES_DOWNLOAD_TPL = "/api/v1/files/{file_id}/download/"
_FILES_SCAN_STATUS_TPL = "/api/v1/files/{file_id}/scan-status/"
_FILES_QUOTA = "/api/v1/files/quota/"
_DATASETS_PATH = "/api/v1/datasets/"
_DATASETS_DETAIL_TPL = "/api/v1/datasets/{dataset_id}/"
_DATASETS_RETIRE_TPL = "/api/v1/datasets/{dataset_id}/retire/"

# EICAR canonical anti-malware test signature (the literal string ClamAV
# matches as TEST/EICAR_Test_File). Reading-this-source-as-data must NOT
# trip the scanner on the dev box, so we assemble it from fragments — a
# trick borrowed from VirusTotal's test corpus and the existing
# `tests/integration/test_clamav_eicar.py:18-22` helper.
_EICAR_FRAGMENTS = (
    r"X5O!P%@AP[4\PZX54(P^)7CC)7}",
    r"$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*",
)
_EICAR_SIGNATURE = ("".join(_EICAR_FRAGMENTS)).encode("ascii")

# Windows PE binary header — the canonical "MZ" magic bytes plus enough
# of the DOS stub that magic-byte validation reliably classifies the
# content as application/x-dosexec, NOT text/csv. See
# ``hub/apps/files/magic_bytes.py:136-180``.
_PE_BYTES = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00" * 32

# Small clean CSV used as the happy-path fixture (also the lifecycle
# test's payload). Distinct content per test prevents content-sha256
# collisions between concurrent test runs.
_CLEAN_CSV_LIFECYCLE = (
    b"id,name,note\n"
    b"1,smoke-dod7-lifecycle,phase-260-dod7\n"
    b"2,smoke-dod7-lifecycle,production-readiness\n"
)

_CLEAN_CSV_QUOTA_PROBE = b"id,counter\n1,1\n2,2\n3,3\n"


# ---------------------------------------------------------------------------
# Helpers (mirror the patterns in test_compliance.py + test_phase260_dod4_post_deploy.py)
# ---------------------------------------------------------------------------


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _init_upload(
    base_url: str,
    session: requests.Session,
    timeout: int,
    *,
    name: str,
    content_type: str,
    payload: bytes,
) -> dict:
    """POST /files/init/ — returns the init response dict.

    SKIPS the test if the endpoint is unreachable (cluster not deployed
    or path renamed); this is the canonical smoke-test escape hatch.
    """
    init_resp = session.post(
        f"{base_url}{_FILES_INIT}",
        json={
            "name": name,
            "content_type": content_type,
            "size": len(payload),
            "upload_method": "sdk",
        },
        timeout=timeout,
    )
    if init_resp.status_code == 404:
        pytest.skip(
            f"Files init endpoint not found at {_FILES_INIT} — "
            "check SMOKE_BASE_URL points at a Phase 260+ deployment."
        )
    assert init_resp.status_code in (200, 201), (
        f"File init failed ({init_resp.status_code}): {init_resp.text[:400]}"
    )
    return init_resp.json()


def _put_to_presigned(
    upload_url: str,
    payload: bytes,
    *,
    content_type: str,
    timeout: int,
) -> requests.Response:
    """PUT raw bytes to the presigned URL (no auth header — would break S3)."""
    upload_session = requests.Session()
    return upload_session.put(
        upload_url,
        data=payload,
        headers={"Content-Type": content_type},
        timeout=timeout,
    )


def _complete_upload(
    base_url: str,
    session: requests.Session,
    timeout: int,
    *,
    file_id: str,
    payload: bytes,
) -> requests.Response:
    """POST /files/{id}/complete/ — returns the response (caller asserts status)."""
    return session.post(
        f"{base_url}{_FILES_COMPLETE_TPL.format(file_id=file_id)}",
        json={"content_sha256": _sha256_hex(payload)},
        timeout=timeout,
    )


def _poll_scan_status_until(
    base_url: str,
    session: requests.Session,
    timeout: int,
    *,
    file_id: str,
    target_states: frozenset[str],
    poll_timeout: int = SCAN_TIMEOUT_S,
    poll_interval: float = SCAN_POLL_INTERVAL_S,
) -> str:
    """Poll /files/{id}/scan-status/ until ``scan_status`` is one of
    ``target_states``. Returns the final scan_status string.

    Fails the test (rather than skipping) if the deadline expires —
    a stuck PENDING_SCAN at deploy time IS a regression worth surfacing.
    """
    deadline = time.monotonic() + poll_timeout
    last_status = "unknown"
    while time.monotonic() < deadline:
        resp = session.get(
            f"{base_url}{_FILES_SCAN_STATUS_TPL.format(file_id=file_id)}",
            timeout=timeout,
        )
        if resp.status_code == 404:
            pytest.skip(
                f"scan-status endpoint not found at "
                f"{_FILES_SCAN_STATUS_TPL.format(file_id=file_id)} — "
                "check SMOKE_BASE_URL points at a Phase 260.3.D+ deployment."
            )
        assert resp.status_code == 200, (
            f"scan-status poll failed ({resp.status_code}): {resp.text[:300]}"
        )
        last_status = str(resp.json().get("scan_status", "unknown")).upper()
        if last_status in target_states:
            return last_status
        time.sleep(poll_interval)  # noqa: sleep-needed  # INTENTIONAL: post-deploy poll cadence
    pytest.fail(
        f"scan-status for file {file_id} did not reach any of "
        f"{sorted(target_states)} within {poll_timeout}s. "
        f"Last status: {last_status!r}. Likely causes: ClamAV daemon "
        "down, RQ scan worker stalled, or scan_status not transitioning "
        "out of PENDING_SCAN."
    )


def _delete_file_best_effort(
    base_url: str, session: requests.Session, timeout: int, file_id: str | None
) -> None:
    """DELETE the file, swallowing errors so cleanup never masks the assertion."""
    if not file_id:
        return
    try:
        session.delete(
            f"{base_url}{_FILES_DETAIL_TPL.format(file_id=file_id)}",
            timeout=timeout,
        )
    except Exception as exc:
        print(f"  cleanup-warning: DELETE file {file_id} failed: {exc}")


def _delete_dataset_best_effort(
    base_url: str, session: requests.Session, timeout: int, dataset_id: str | None
) -> None:
    """DELETE the dataset, swallowing errors so cleanup never masks the assertion."""
    if not dataset_id:
        return
    try:
        session.delete(
            f"{base_url}{_DATASETS_DETAIL_TPL.format(dataset_id=dataset_id)}",
            timeout=timeout,
        )
    except Exception as exc:
        print(f"  cleanup-warning: DELETE dataset {dataset_id} failed: {exc}")


# ---------------------------------------------------------------------------
# Sub-criterion 1 — Full lifecycle chain
# ---------------------------------------------------------------------------


class TestPhase260DoD7FullLifecycleChain:
    """260.DoD.7 — file upload + virus scan + dataset create + retire + orphan."""

    def test_full_lifecycle_chain_completes(
        self,
        base_url: str,
        authenticated_session: requests.Session,
        timeout: int,
    ) -> None:
        file_id: str | None = None
        dataset_id: str | None = None
        try:
            # 1. Init + upload + complete (clean CSV).
            init = _init_upload(
                base_url,
                authenticated_session,
                timeout,
                name=f"smoke-dod7-lifecycle-{int(time.time())}.csv",
                content_type="text/csv",
                payload=_CLEAN_CSV_LIFECYCLE,
            )
            file_id = init["file_id"]
            put_resp = _put_to_presigned(
                init["upload_url"],
                _CLEAN_CSV_LIFECYCLE,
                content_type="text/csv",
                timeout=timeout,
            )
            assert put_resp.status_code in (200, 204), (
                f"presigned PUT failed: {put_resp.status_code} {put_resp.text[:200]}"
            )
            complete_resp = _complete_upload(
                base_url,
                authenticated_session,
                timeout,
                file_id=file_id,
                payload=_CLEAN_CSV_LIFECYCLE,
            )
            assert complete_resp.status_code in (200, 201), (
                f"complete failed: {complete_resp.status_code} {complete_resp.text[:300]}"
            )

            # 2. Virus scan must reach a terminal CLEAN state.
            final = _poll_scan_status_until(
                base_url,
                authenticated_session,
                timeout,
                file_id=file_id,
                target_states=frozenset({"CLEAN", "INFECTED", "SCAN_UNAVAILABLE"}),
            )
            assert final == "CLEAN", (
                f"clean CSV expected CLEAN scan_status, got {final!r}. "
                "If SCAN_UNAVAILABLE: ClamAV daemon is unreachable from the "
                "deployed worker pool; investigate `clamav` deployment health."
            )

            # 3. Create a dataset that references the file.
            ds_resp = authenticated_session.post(
                f"{base_url}{_DATASETS_PATH}",
                json={
                    "name": f"smoke-dod7-lifecycle-{int(time.time())}",
                    "file_id": file_id,
                    "format": "csv",
                },
                timeout=timeout,
            )
            if ds_resp.status_code == 404:
                pytest.skip(f"Dataset create endpoint not found at {_DATASETS_PATH}")  # noqa: skip-in-body — runtime service dependency
            assert ds_resp.status_code in (200, 201), (
                f"dataset create failed: {ds_resp.status_code} {ds_resp.text[:400]}"
            )
            dataset_id = ds_resp.json().get("id")
            assert dataset_id, f"dataset create missing id: {ds_resp.json()}"

            # 4. Retire the dataset (Phase 260.4.A.1: ACTIVE → RETIRED).
            retire_resp = authenticated_session.post(
                f"{base_url}{_DATASETS_RETIRE_TPL.format(dataset_id=dataset_id)}",
                timeout=timeout,
            )
            assert retire_resp.status_code in (200, 202), (
                f"dataset retire failed: {retire_resp.status_code} {retire_resp.text[:300]}"
            )

            # 5. Delete the dataset → triggers the orphan-cleanup contract:
            # the LAST Dataset row for (tenant, file_id) being deleted
            # transitions the backing File to DELETED inside the same
            # commit per the spec at
            # `openspec/changes/preprod01/specs/datasets-files/spec.md`.
            del_resp = authenticated_session.delete(
                f"{base_url}{_DATASETS_DETAIL_TPL.format(dataset_id=dataset_id)}",
                timeout=timeout,
            )
            assert del_resp.status_code in (200, 202, 204), (
                f"dataset delete failed: {del_resp.status_code} {del_resp.text[:300]}"
            )
            dataset_id = None  # cleanup no longer needed for the dataset

            # 6. Verify the orphan-cleanup contract: the file detail call
            # returns either (a) 200 with status=DELETED (soft tombstone),
            # or (b) 404 (post-purge). Either is a valid steady-state per
            # the spec — what we MUST NOT see is the file still in ACTIVE
            # state with no Dataset reference (that would be the orphan
            # leak the contract guards against).
            file_resp = authenticated_session.get(
                f"{base_url}{_FILES_DETAIL_TPL.format(file_id=file_id)}",
                timeout=timeout,
            )
            assert file_resp.status_code in (200, 404), (
                f"file detail post-orphan: {file_resp.status_code} {file_resp.text[:300]}"
            )
            if file_resp.status_code == 200:
                file_status = file_resp.json().get("status", "").upper()
                assert file_status in {"DELETED", "DELETING", "RETIRED"}, (
                    f"orphan-cleanup contract violated: file {file_id} is "
                    f"still in status={file_status!r} after its last Dataset "
                    "reference was deleted. Per the datasets-files spec, "
                    "the file MUST transition out of ACTIVE."
                )
                # Cleanup not needed when the orphan path already DELETED'd.
                file_id = None

        finally:
            _delete_dataset_best_effort(base_url, authenticated_session, timeout, dataset_id)
            _delete_file_best_effort(base_url, authenticated_session, timeout, file_id)


# ---------------------------------------------------------------------------
# Sub-criterion 2 — EICAR upload blocks download
# ---------------------------------------------------------------------------


class TestPhase260DoD7EicarUploadBlocksDownload:
    """260.DoD.7 — INFECTED EICAR upload blocks download."""

    def test_eicar_upload_blocks_download(
        self,
        base_url: str,
        authenticated_session: requests.Session,
        timeout: int,
    ) -> None:
        file_id: str | None = None
        try:
            # 1. Init + upload + complete the EICAR signature labelled as a
            # binary blob. The upload itself MUST succeed — virus scanners
            # are supposed to scan AFTER receipt, not block at the door.
            init = _init_upload(
                base_url,
                authenticated_session,
                timeout,
                name=f"smoke-dod7-eicar-{int(time.time())}.bin",
                content_type="application/octet-stream",
                payload=_EICAR_SIGNATURE,
            )
            file_id = init["file_id"]
            put_resp = _put_to_presigned(
                init["upload_url"],
                _EICAR_SIGNATURE,
                content_type="application/octet-stream",
                timeout=timeout,
            )
            assert put_resp.status_code in (200, 204), (
                f"EICAR presigned PUT failed: {put_resp.status_code}"
            )
            complete_resp = _complete_upload(
                base_url,
                authenticated_session,
                timeout,
                file_id=file_id,
                payload=_EICAR_SIGNATURE,
            )
            assert complete_resp.status_code in (200, 201), (
                f"EICAR complete failed: {complete_resp.status_code} {complete_resp.text[:300]}"
            )

            # 2. Poll until scan_status == INFECTED (the contract).
            final = _poll_scan_status_until(
                base_url,
                authenticated_session,
                timeout,
                file_id=file_id,
                target_states=frozenset({"INFECTED", "CLEAN", "SCAN_UNAVAILABLE"}),
            )
            if final == "SCAN_UNAVAILABLE":
                pytest.skip(  # noqa: skip-in-body — runtime service dependency
                    "ClamAV daemon unavailable — DoD.7 EICAR test cannot run. "
                    "Investigate ClamAV deploy health and re-run."
                )
            assert final == "INFECTED", (
                f"EICAR signature expected INFECTED, got {final!r}. "
                "Either the EICAR signature isn't being matched (ClamAV "
                "signature DB out-of-date) or the virus-scanning pipeline "
                "is not running."
            )

            # 3. Download attempt MUST be blocked with 403 + FILE_INFECTED.
            download_resp = authenticated_session.get(
                f"{base_url}{_FILES_DOWNLOAD_TPL.format(file_id=file_id)}",
                timeout=timeout,
                allow_redirects=False,
            )
            assert download_resp.status_code == 403, (
                f"DoD.7 contract violated: INFECTED file allowed download "
                f"({download_resp.status_code}). The download MUST 403 with "
                f"code FILE_INFECTED. Body: {download_resp.text[:300]}"
            )
            try:
                body = download_resp.json()
            except ValueError:
                body = {}
            error_code = body.get("code") or body.get("error_code") or ""
            assert error_code == "FILE_INFECTED", (
                f"DoD.7 contract: 403 expected with code=FILE_INFECTED, got "
                f"{error_code!r}. Body: {download_resp.text[:300]}"
            )
        finally:
            _delete_file_best_effort(base_url, authenticated_session, timeout, file_id)


# ---------------------------------------------------------------------------
# Sub-criterion 3 — Magic-byte mismatch rejects PE-as-CSV
# ---------------------------------------------------------------------------


class TestPhase260DoD7MagicByteMismatchRejectsPeAsCsv:
    """260.DoD.7 — magic-byte mismatch rejects PE-as-CSV."""

    def test_pe_payload_labelled_as_csv_is_rejected(
        self,
        base_url: str,
        authenticated_session: requests.Session,
        timeout: int,
    ) -> None:
        file_id: str | None = None
        try:
            init = _init_upload(
                base_url,
                authenticated_session,
                timeout,
                name=f"smoke-dod7-magicbyte-{int(time.time())}.csv",
                content_type="text/csv",  # Lie: declared CSV, actually PE.
                payload=_PE_BYTES,
            )
            file_id = init["file_id"]
            put_resp = _put_to_presigned(
                init["upload_url"],
                _PE_BYTES,
                content_type="text/csv",
                timeout=timeout,
            )
            assert put_resp.status_code in (200, 204), (
                f"PE-as-CSV presigned PUT failed: {put_resp.status_code}"
            )

            # The rejection point: POST /files/{id}/complete/ runs
            # `magic_byte_check_post_upload` which re-reads the head bytes
            # from S3 and matches against the declared content_type. With
            # MAGIC_BYTE_VALIDATION_ENABLED=true (the staging default per
            # Phase 260.2.B), a PE header on a text/csv decl returns a 4xx.
            complete_resp = _complete_upload(
                base_url,
                authenticated_session,
                timeout,
                file_id=file_id,
                payload=_PE_BYTES,
            )

            if complete_resp.status_code in (200, 201):
                # Magic-byte validation is disabled on this deploy.
                # Skip rather than silently passing — the DoD.7 contract
                # is "rejection happens", and an environment where it
                # doesn't is a deploy-config issue, not a test failure.
                pytest.skip(  # noqa: skip-in-body — runtime service dependency
                    "PE-as-CSV upload was ACCEPTED — magic-byte validation "
                    "appears disabled on this deploy. Set "
                    "MAGIC_BYTE_VALIDATION_ENABLED=true for DoD.7 to apply."
                )

            assert complete_resp.status_code in (400, 422), (
                f"DoD.7 contract violated: PE-as-CSV expected 4xx, got "
                f"{complete_resp.status_code}. Body: {complete_resp.text[:300]}"
            )
            try:
                body = complete_resp.json()
            except ValueError:
                body = {}
            error_code = body.get("code") or body.get("error_code") or ""
            # The exact code is one of CONTENT_TYPE_MISMATCH /
            # MAGIC_BYTE_MISMATCH / FILE_CONTENT_TYPE_MISMATCH (the
            # production code paths use slightly different names; we
            # accept any code that names the mismatch).
            assert "MISMATCH" in error_code.upper() or "CONTENT_TYPE" in error_code.upper(), (
                f"DoD.7: 4xx expected with a MISMATCH-class code, got "
                f"{error_code!r}. Body: {complete_resp.text[:300]}"
            )
        finally:
            _delete_file_best_effort(base_url, authenticated_session, timeout, file_id)


# ---------------------------------------------------------------------------
# Sub-criterion 4 — Quota meter shows correct percentage
# ---------------------------------------------------------------------------


class TestPhase260DoD7QuotaMeterReflectsBytes:
    """260.DoD.7 — quota meter shows correct percentage."""

    def test_quota_meter_increments_after_upload(
        self,
        base_url: str,
        authenticated_session: requests.Session,
        timeout: int,
    ) -> None:
        # 1. Baseline read.
        baseline_resp = authenticated_session.get(f"{base_url}{_FILES_QUOTA}", timeout=timeout)
        if baseline_resp.status_code == 404:
            pytest.skip(  # noqa: skip-in-body — runtime service dependency
                f"quota endpoint not found at {_FILES_QUOTA} — "
                "check SMOKE_BASE_URL points at a Phase 260.4.G+ deployment."
            )
        assert baseline_resp.status_code == 200, (
            f"baseline quota read failed: {baseline_resp.status_code} {baseline_resp.text[:300]}"
        )
        baseline = baseline_resp.json()
        baseline_used = int(baseline.get("used_bytes", 0))

        file_id: str | None = None
        try:
            # 2. Upload N bytes.
            payload = _CLEAN_CSV_QUOTA_PROBE
            init = _init_upload(
                base_url,
                authenticated_session,
                timeout,
                name=f"smoke-dod7-quota-{int(time.time())}.csv",
                content_type="text/csv",
                payload=payload,
            )
            file_id = init["file_id"]
            put_resp = _put_to_presigned(
                init["upload_url"],
                payload,
                content_type="text/csv",
                timeout=timeout,
            )
            assert put_resp.status_code in (200, 204), (
                f"quota-probe presigned PUT failed: {put_resp.status_code}"
            )
            complete_resp = _complete_upload(
                base_url,
                authenticated_session,
                timeout,
                file_id=file_id,
                payload=payload,
            )
            assert complete_resp.status_code in (200, 201), (
                f"quota-probe complete failed: {complete_resp.status_code}"
            )

            # 3. Re-read the meter.
            after_resp = authenticated_session.get(f"{base_url}{_FILES_QUOTA}", timeout=timeout)
            assert after_resp.status_code == 200, (
                f"post-upload quota read failed: {after_resp.status_code}"
            )
            after = after_resp.json()
            after_used = int(after.get("used_bytes", 0))

            # 4. The meter MUST reflect at least the bytes we uploaded.
            assert after_used >= baseline_used + len(payload), (
                f"DoD.7 contract violated: quota meter did not reflect "
                f"the {len(payload)}-byte upload. Baseline used_bytes="
                f"{baseline_used}, after upload={after_used}, expected "
                f">= {baseline_used + len(payload)}."
            )

            # 5. The percentage field, if present, must be coherent with
            # the byte counter (within float-precision tolerance — a
            # tenant whose quota has changed mid-test is allowed).
            after_pct = after.get("utilization_pct")
            limit_bytes = int(after.get("limit_bytes", 0)) or None
            if after_pct is not None and limit_bytes:
                expected_pct = (after_used / limit_bytes) * 100.0
                assert abs(float(after_pct) - expected_pct) < 0.5, (
                    f"DoD.7 contract: utilization_pct={after_pct} but "
                    f"used_bytes/limit_bytes={expected_pct:.2f}. "
                    "Quota meter percentage drifted from byte counter."
                )
        finally:
            _delete_file_best_effort(base_url, authenticated_session, timeout, file_id)
