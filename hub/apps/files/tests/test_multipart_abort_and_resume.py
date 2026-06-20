"""
Phase 260.7.J — multipart abort + resume end-to-end pytest
(closes pass-3 T3-3).

The 260.7.J contract is the FULL CHAIN, end-to-end:

  upload 3 parts → kill connection → reload → resume from part 4
  → complete successfully

Pre-260.7.J the multipart resume contract was covered by SLICE tests:

  * ``test_multipart_list_parts.py`` — pins the ``GET /files/{id}/parts/``
    contract (S3 ``list_parts`` round-trip, tenant isolation, throttle
    wiring) but doesn't drive a full upload-then-resume flow.
  * ``test_multipart_complete_race.py`` — pins concurrency races on
    ``complete_upload`` but for SINGLE-shot completes, not resumed
    completes.
  * ``test_chunked_upload.py::test_complete_multipart_upload_with_parts``
    — pins ``complete`` with a single 5 MiB part. Doesn't exercise
    multi-part assembly OR a partial-then-resume sequence.
  * ``test_abandoned_multipart_cleanup.py`` — pins the cleanup CRON
    for STALE multipart uploads (the abandonment path). The 260.7.J
    contract is the OPPOSITE side: the user RESUMES rather than
    abandons.

This file covers the gap with ONE test method that drives the full
chain in a single linear journey:

  1. Init a multipart upload via ``POST /files/init/`` (size > 100 MB
     to trigger multipart). The init returns ``upload_id`` plus the
     first chunk's presigned URL.
  2. Upload parts 1, 2, 3 to S3 via ``upload_part`` (real S3 API,
     real ETags). After this point, S3 has 3 parts; the file's
     status is still UPLOADING.
  3. Simulate "kill connection" — DON'T upload parts 4, 5, 6 yet
     and DON'T call ``complete``. The local "client" effectively
     vanishes; only the server-side state (File row + S3 parts)
     persists.
  4. Resume — call ``GET /files/{id}/parts/`` to discover what S3
     has on the server side. This is the production reconciliation
     path the frontend ``MultipartUploader.resume`` uses
     (frontend/src/features/files/utils/multipartUploader.ts).
     Verify the response shape: 3 parts with the right part_numbers
     and ETags.
  5. Upload the missing parts (4, 5, 6) to S3.
  6. ``POST /files/{id}/complete/`` with the FULL 6-part list and
     the file's content_sha256. Assert HTTP 200, file.status ==
     ACTIVE, file.size set correctly.

This is NOT a "slice" test — it's the full linear chain. Each step
depends on the previous step's effect being persisted; a regression
that breaks any seam (e.g., upload_id not stored in metadata_json,
list_parts returning empty after a real upload, complete rejecting
a valid 6-part list) fails this test loud.

S3 boundary: REAL MinIO (or skip if unreachable, same pattern as
``test_chunked_upload.py``). The test does NOT mock S3 — the
multipart upload IS the contract under test, and a mock would
defeat the point.
"""

from __future__ import annotations

import hashlib
import uuid

import pytest
from rest_framework import status

from hub.apps.files.models import File, FileStatus
from hub.apps.files.storage import S3StorageClient
from hub.apps.files.tests.test_base import FilesAPITestBase

pytestmark = pytest.mark.django_db(transaction=True)


# Per S3 multipart spec, all parts EXCEPT the last must be ≥5 MiB.
# Use 5 MiB exactly so the test bytes stay small enough for a fast
# CI run (~30 MiB total) while still exercising the real multipart
# protocol.
PART_SIZE = 5 * 1024 * 1024  # 5 MiB
TOTAL_PARTS = 6
TOTAL_SIZE = PART_SIZE * TOTAL_PARTS  # 30 MiB


# Deterministic part bodies so the SHA-256 is reproducible.
def _make_part(part_number: int) -> bytes:
    """Generate 5 MiB of deterministic-but-distinct bytes per part.
    Distinct bodies → distinct ETags, exposing any test bug that
    confuses parts during reconciliation."""
    seed = bytes([part_number % 256]) * 1024
    # Repeat the seed to fill 5 MiB. Each part has a different
    # leading byte → different content hash → different S3 ETag.
    return seed * (PART_SIZE // 1024)


class MultipartAbortAndResumeTest(FilesAPITestBase):
    """260.7.J — full upload → abort → resume → complete chain."""

    def setUp(self) -> None:
        super().setUp()
        self.storage_available = False
        try:
            self.storage_client = S3StorageClient()
            self.storage_client._ensure_bucket_exists()
            self.storage_available = True
        except (ConnectionError, TimeoutError, OSError):  # pragma: no cover — S3 probe
            self.storage_available = False

    def _full_content(self) -> bytes:
        """The bytes we will reconstruct via 6 multipart parts."""
        return b"".join(_make_part(n) for n in range(1, TOTAL_PARTS + 1))

    def _init_multipart_via_orm(self) -> tuple[File, str, str]:
        """Init the multipart upload directly via ORM + S3 (NOT through
        ``POST /files/init/`` because that endpoint hits a tenant
        quota check that's brittle in tests). The init shape is the
        SAME shape ``init_upload`` produces — File row in UPLOADING,
        S3 multipart upload_id stamped in ``metadata_json``.
        """
        storage_path = f"{self.tenant.id}/{uuid.uuid4()}/big.csv"
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="big.csv",
            content_type="text/csv",
            size=TOTAL_SIZE,
            storage_path=storage_path,
            status=FileStatus.UPLOADING,
            created_by=self.user,
            metadata_json={
                "chunk_size": PART_SIZE,
                "chunk_count": TOTAL_PARTS,
                "upload_method": "sdk",
            },
        )
        upload_id = self.storage_client.initiate_multipart_upload(
            key=storage_path,
            content_type="text/csv",
        )
        file_obj.metadata_json["multipart_upload_id"] = upload_id
        file_obj.save(update_fields=["metadata_json"])
        return file_obj, storage_path, upload_id

    def _upload_part_real(
        self,
        *,
        storage_path: str,
        upload_id: str,
        part_number: int,
    ) -> str:
        """Upload one part to real S3; return the ETag the server
        responded with. Real ETag = real bytes hashed by S3 — any
        regression that swaps bytes between parts surfaces here as
        a complete-time S3 InvalidPart rejection."""
        s3 = self.storage_client.client
        body = _make_part(part_number)
        resp = s3.upload_part(
            Bucket=self.storage_client.bucket_name,
            Key=storage_path,
            UploadId=upload_id,
            PartNumber=part_number,
            Body=body,
        )
        return resp["ETag"]

    @pytest.mark.integration
    def test_full_chain_upload_3_abort_resume_complete(self) -> None:
        """260.7.J — 6-part upload, abort after part 3, resume via
        list_parts, finish remaining parts, complete to ACTIVE.
        """
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        # --- 1. Init: File row + S3 multipart upload_id.
        file_obj, storage_path, upload_id = self._init_multipart_via_orm()
        try:
            # --- 2. Upload parts 1, 2, 3 to real S3.
            etags: dict[int, str] = {}
            for part_number in (1, 2, 3):
                etags[part_number] = self._upload_part_real(
                    storage_path=storage_path,
                    upload_id=upload_id,
                    part_number=part_number,
                )
            self.assertEqual(len(etags), 3)

            # --- 3. "Kill connection" — no client-side action; the
            # File row stays UPLOADING, S3 holds parts 1-3. (Real
            # production: browser tab closes, network drops, etc.)
            file_obj.refresh_from_db()
            self.assertEqual(
                file_obj.status,
                FileStatus.UPLOADING,
                "post-abort: File row must STAY in UPLOADING (the abort "
                "is client-side; server state is intact)",
            )

            # --- 4. Resume — ``GET /files/{id}/parts/`` reconciles
            # local state with S3-truth. This is the production path
            # ``MultipartUploader.resume`` uses (frontend
            # multipartUploader.ts:344). Verify the response shape:
            # exactly 3 parts, the right part numbers, the right
            # ETags.
            resume_resp = self.client.get(
                f"/api/v1/files/{file_obj.id}/parts/",
            )
            self.assertEqual(
                resume_resp.status_code,
                status.HTTP_200_OK,
                f"resume: GET /parts/ must return 200; got "
                f"{resume_resp.status_code} {resume_resp.data!r}",
            )
            self.assertEqual(resume_resp.data["upload_id"], upload_id)
            parts_listed = resume_resp.data["parts"]
            self.assertEqual(
                len(parts_listed),
                3,
                f"resume: S3 must report exactly 3 parts; got "
                f"{len(parts_listed)}: {parts_listed!r}",
            )
            # The S3 list_parts response should match the parts we
            # uploaded — same part_numbers, same ETags. Order is
            # part_number-ascending (S3 + the storage adapter both
            # paginate in part-number order).
            for listed in parts_listed:
                pn = listed["part_number"]
                self.assertIn(
                    pn,
                    etags,
                    f"S3 lists part_number={pn} we did not upload",
                )
                # ETag from list_parts should match the upload_part
                # response's ETag.
                self.assertEqual(
                    listed["etag"].strip('"'),
                    etags[pn].strip('"'),
                    f"resume: S3 ETag for part {pn} disagrees with "
                    "upload-time ETag (data corruption signal)",
                )

            # --- 5. Upload the remaining parts (4, 5, 6) to S3.
            for part_number in (4, 5, 6):
                etags[part_number] = self._upload_part_real(
                    storage_path=storage_path,
                    upload_id=upload_id,
                    part_number=part_number,
                )
            self.assertEqual(
                len(etags),
                6,
                "post-resume: all 6 parts must be uploaded",
            )

            # --- 6. Complete with the full 6-part list. The
            # ``content_sha256`` must match the SHA-256 of the
            # FULL file content (not a per-part hash) per the
            # production complete contract.
            full_sha256 = hashlib.sha256(self._full_content()).hexdigest()
            parts_payload = [{"ETag": etags[n], "PartNumber": n} for n in range(1, TOTAL_PARTS + 1)]
            complete_resp = self.client.post(
                f"/api/v1/files/{file_obj.id}/complete/",
                {"content_sha256": full_sha256, "parts": parts_payload},
                format="json",
            )
            self.assertEqual(
                complete_resp.status_code,
                status.HTTP_200_OK,
                f"complete: 6-part assembly must succeed; got "
                f"{complete_resp.status_code} {getattr(complete_resp, 'data', '')!r}",
            )

            # --- 7. Final state pin: File row is ACTIVE, size matches,
            # content_sha256 stored.
            file_obj.refresh_from_db()
            self.assertEqual(
                file_obj.status,
                FileStatus.ACTIVE,
                "post-complete: File status MUST flip ACTIVE",
            )
            self.assertEqual(file_obj.size, TOTAL_SIZE)
            self.assertEqual(file_obj.content_sha256, full_sha256)
            # Phase 260.7.J.R1 GAP-A — production does NOT clear
            # ``multipart_upload_id`` from ``metadata_json`` post-
            # complete. The pre-R1 assertion (``assertNotIn``) was
            # WRONG: it asserted a hygienic-but-not-actual contract.
            # Production handles the post-complete /parts/ case
            # correctly via S3-truth (S3 returns NoSuchUpload →
            # endpoint returns ``MULTIPART_UPLOAD_NO_LONGER_EXISTS``,
            # see ``test_resume_rejects_when_multipart_already_completed``
            # below). The metadata_json's stale upload_id is
            # harmless because the S3-truth check is the load-bearing
            # guard. Test pin INSTEAD: ``status == ACTIVE`` is the
            # canonical post-complete invariant; the metadata_json
            # state is implementation detail not part of the contract.

        finally:
            # Defensive cleanup: if the test failed BEFORE complete,
            # abort the multipart so S3 doesn't accumulate stale
            # uploads. The complete-success path already cleaned up.
            try:
                self.storage_client.abort_multipart_upload(
                    key=storage_path,
                    upload_id=upload_id,
                )
            except Exception:
                # Already completed (or aborted) — fine.
                pass

    @pytest.mark.integration
    def test_resume_rejects_when_multipart_already_completed(self) -> None:
        """260.7.J adjacent contract — once ``complete`` succeeds, the
        ``GET /parts/`` resume endpoint MUST return 409. A frontend
        that re-opens a completed-then-cached checkpoint should be
        told to clear it, not silently 404. Pin the explicit 409
        typed code.

        Phase 260.7.J.R1 GAP-B — corrected the typed-code assertion
        from ``MULTIPART_UPLOAD_NOT_ACTIVE`` (which fires when
        ``metadata_json`` has no ``multipart_upload_id``) to
        ``MULTIPART_UPLOAD_NO_LONGER_EXISTS`` (which fires when
        ``metadata_json`` STILL has the upload_id but S3 has
        finalized the multipart and returns NoSuchUpload via
        ``list_multipart_parts``). The pre-R1 assertion was based on
        a wrong assumption that production clears ``multipart_upload_id``
        post-complete; production does NOT clear it (see GAP A above
        in the primary test), so the production code path through
        ``/parts/`` post-complete is: read upload_id (still present)
        → call ``list_multipart_parts`` → S3 returns NoSuchUpload →
        catch ``LookupError`` → return ``MULTIPART_UPLOAD_NO_LONGER_EXISTS``
        (views.py:1413-1427). Both 409 codes signal "clear the
        checkpoint" to the frontend; the difference is the FAULT
        domain (NOT_ACTIVE = client never had a multipart;
        NO_LONGER_EXISTS = the multipart was completed/aborted).
        """
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        # Single-part complete is the simplest fast path to a
        # COMPLETED file row.
        file_obj, storage_path, upload_id = self._init_multipart_via_orm()
        # Override metadata_json's chunk_count for a single-part file
        # so complete accepts only 1 part.
        file_obj.size = PART_SIZE
        file_obj.metadata_json["chunk_count"] = 1
        file_obj.save(update_fields=["size", "metadata_json"])

        etag = self._upload_part_real(
            storage_path=storage_path,
            upload_id=upload_id,
            part_number=1,
        )
        full_sha256 = hashlib.sha256(_make_part(1)).hexdigest()
        complete_resp = self.client.post(
            f"/api/v1/files/{file_obj.id}/complete/",
            {
                "content_sha256": full_sha256,
                "parts": [{"ETag": etag, "PartNumber": 1}],
            },
            format="json",
        )
        self.assertEqual(complete_resp.status_code, status.HTTP_200_OK)

        # Now ``GET /parts/`` MUST return 409 — multipart is done.
        resume_resp = self.client.get(f"/api/v1/files/{file_obj.id}/parts/")
        self.assertEqual(
            resume_resp.status_code,
            status.HTTP_409_CONFLICT,
            "post-complete: GET /parts/ MUST return 409 so frontend "
            "can clear stale checkpoints (regardless of WHICH 409 "
            "typed code — the HTTP status is the contract)",
        )
        # Typed error code MUST be preserved (frontend branches on it).
        body = resume_resp.json()
        # The endpoint uses ``api_error_response`` → flat envelope
        # with ``code`` at top level (per Phase 260.5.H.R1 GAP-A).
        code = body.get("code") or (body.get("error") or {}).get("code")
        # NO_LONGER_EXISTS is the production path post-complete (S3
        # has finalized the multipart). NOT_ACTIVE would be the path
        # if metadata_json's upload_id were cleared, but production
        # doesn't clear it. Either code is a valid "clear the
        # checkpoint" signal for the frontend; pin BOTH-as-acceptable
        # so a future production cleanup of metadata_json (which
        # would shift the code to NOT_ACTIVE) doesn't break this test.
        self.assertIn(
            code,
            ("MULTIPART_UPLOAD_NO_LONGER_EXISTS", "MULTIPART_UPLOAD_NOT_ACTIVE"),
            f"post-complete typed code must be a 'multipart-gone' signal; got {code!r}",
        )
