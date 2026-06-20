"""
Phase 260.5.H — Multipart upload completion race tests (closes pass-3 B3-2).

The race this closes:

1. Client uploads N chunks via presigned PUT URLs.
2. One chunk gets a 200 OK on the wire (visible to the client) but
   the bytes never reach S3 — transient transport failure visible
   only to the proxy / NLB.
3. Client thinks all chunks succeeded; submits the full ``parts``
   list to ``POST /files/{id}/complete/``.
4. Without the server-side parts validation introduced in 260.5.H,
   ``complete_multipart_upload`` would either silently produce a
   corrupt object or fail with a generic ``InvalidPart`` 5xx the
   client cannot actionably retry.

The fix lists the parts S3 actually has, computes what the client
expected to upload, and surfaces a typed 409
``MULTIPART_INCOMPLETE`` with ``details.missing_parts`` so the
client can re-upload exactly what's missing rather than the whole
file.

Tests use REAL MinIO multipart APIs (boto3's ``upload_part`` via
the storage client's ``.client`` attribute) — no mocks of the
parts-validation logic. Skip when MinIO is unavailable.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.response_helpers import response_body
from hub.apps.users.models import UserStatus

User = get_user_model()


# Minimum part size MinIO accepts in tests; 5 MiB is the AWS S3
# minimum for non-last parts but MinIO is lenient about this for
# the LIST_PARTS path (which is what we exercise pre-compose).
# We keep parts small (a few bytes) because the gate fires BEFORE
# complete_multipart_upload — the compose step never runs in the
# 409 paths we test.
_PART_BODY = b"a" * 16


def _extract_error_code(body):
    """Phase 260.5.C.R1 GAP-D — defensive extraction across the
    flat (api_error_response) and nested (custom_exception_handler)
    error envelopes the codebase uses."""
    if not isinstance(body, dict):
        return None
    nested = body.get("error")
    if isinstance(nested, dict) and nested.get("code"):
        return nested.get("code")
    return body.get("code")


def _extract_details(body):
    """Same defensive extraction for ``details`` — the api_error_response
    shape stores it at top level, the custom_exception_handler shape
    nests it under ``error.details``."""
    if not isinstance(body, dict):
        return {}
    nested = body.get("error")
    if isinstance(nested, dict):
        details = nested.get("details") or {}
        if isinstance(details, dict):
            return details
    flat = body.get("details") or {}
    return flat if isinstance(flat, dict) else {}


class _MultipartCompleteRaceTestMixin:
    """Shared MinIO + tenant + user + multipart-helper setUp.

    ``TransactionTestCase`` because S3/MinIO writes happen
    out-of-band of Django's transaction — using a regular TestCase
    would leave parts dangling between tests.
    """

    def setUp(self):
        super().setUp()
        from hub.apps.files.storage import S3StorageClient

        self.storage_available = False
        try:
            self.storage_client = S3StorageClient()
            self.storage_client._ensure_bucket_exists()
            self.storage_available = True
        except (ConnectionError, TimeoutError, OSError):  # pragma: no cover — S3 probe
            self.storage_available = False

        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"MPRace {uid}",
            slug=f"mprace-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        # File-multipart endpoints require an active tenant subscription
        # (otherwise Phase 250.x ``subscription_inactive`` short-circuits
        # at 403) AND a DATA_PROVIDER role on the user.
        from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"mprace-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        from hub.apps.testing.role_support import ensure_user_has_data_provider_role

        ensure_user_has_data_provider_role(self.user)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _seed_pending_multipart_file(self, *, chunk_count: int) -> tuple:
        """Init a multipart upload on MinIO + create a matching
        PENDING File row with ``multipart_upload_id`` and
        ``chunk_count`` populated. Returns ``(file_obj, upload_id)``.

        Mirrors the shape ``init_upload`` produces when
        ``requires_multipart=True``.
        """
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")
        file_id = uuid.uuid4()
        storage_path = f"{self.tenant.id}/{file_id}/data.bin"
        upload_id = self.storage_client.initiate_multipart_upload(
            key=storage_path,
            content_type="application/octet-stream",
        )
        f = File.objects.create(
            id=file_id,
            tenant=self.tenant,
            name="data.bin",
            content_type="application/octet-stream",
            size=len(_PART_BODY) * chunk_count,
            status=FileStatus.UPLOADING,
            scan_status=FileScanStatus.PENDING_SCAN,
            storage_path=storage_path,
            created_by=self.user,
            metadata_json={
                "upload_method": "browser",
                "multipart_upload_id": upload_id,
                "chunk_count": chunk_count,
                "chunk_size": len(_PART_BODY),
            },
        )
        return f, upload_id

    def _upload_part(self, *, file_obj, upload_id: str, part_number: int) -> str:
        """Upload a real part to MinIO via boto3. Returns the ETag
        the client would normally include in the ``parts`` payload."""
        response = self.storage_client.client.upload_part(
            Bucket=self.storage_client.bucket_name,
            Key=file_obj.storage_path,
            UploadId=upload_id,
            PartNumber=part_number,
            Body=_PART_BODY,
        )
        return response["ETag"]


# ---------------------------------------------------------------------------
# 260.5.H.1 — Server-side parts validation
# ---------------------------------------------------------------------------


@pytest.mark.xdist_group("minio_multipart")
class MultipartIncompleteRaceTest(_MultipartCompleteRaceTestMixin, TransactionTestCase):
    """Phase 260.5.H.1 — when the client claims to have uploaded
    N parts but S3 is missing some, the server returns 409
    ``MULTIPART_INCOMPLETE`` with the missing-parts list.
    """

    @pytest.mark.integration
    def test_complete_with_no_parts_in_s3_returns_409_with_full_missing_list(self):
        # All 3 parts the client claims to have uploaded are
        # actually missing from S3 — the load-bearing race
        # scenario (every chunk's PUT returned 200 OK on the wire
        # but the bytes never reached S3).
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")
        f, upload_id = self._seed_pending_multipart_file(chunk_count=3)

        client_claimed_parts = [
            {"ETag": "fake-etag-1", "PartNumber": 1},
            {"ETag": "fake-etag-2", "PartNumber": 2},
            {"ETag": "fake-etag-3", "PartNumber": 3},
        ]

        response = self.client.post(
            f"/api/v1/files/{f.id}/complete/",
            data={
                "content_sha256": "0" * 64,
                "parts": client_claimed_parts,
            },
            format="json",
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT,
            f"Expected 409; got body={response_body(response)!r}",
        )
        code = _extract_error_code(response_body(response))
        self.assertEqual(
            code,
            "MULTIPART_INCOMPLETE",
            f"Expected MULTIPART_INCOMPLETE; got body={response_body(response)!r}",
        )
        details = _extract_details(response_body(response))
        self.assertEqual(
            sorted(details.get("missing_parts") or []),
            [1, 2, 3],
            f"Expected all 3 parts missing; got details={details!r}",
        )
        self.assertEqual(details.get("expected_count"), 3)
        self.assertEqual(details.get("uploaded_count"), 0)
        self.assertEqual(details.get("upload_id"), upload_id)
        self.assertEqual(details.get("file_id"), str(f.id))

        # The file row was NOT marked complete — the gate fires
        # before the status flip.
        f.refresh_from_db()
        self.assertEqual(f.status, FileStatus.UPLOADING)

    @pytest.mark.integration
    def test_complete_with_partial_parts_lists_only_missing_part_numbers(self):
        # Realistic transient-failure shape: parts 1 and 3 made it,
        # part 2 didn't. The 409 must name SPECIFICALLY part 2 so
        # the client re-uploads only that one chunk.
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")
        f, upload_id = self._seed_pending_multipart_file(chunk_count=3)
        # Upload parts 1 and 3 only — part 2 is the "lost in
        # transport" case.
        etag1 = self._upload_part(file_obj=f, upload_id=upload_id, part_number=1)
        etag3 = self._upload_part(file_obj=f, upload_id=upload_id, part_number=3)

        client_claimed_parts = [
            {"ETag": etag1, "PartNumber": 1},
            {"ETag": "fake-etag-2", "PartNumber": 2},  # client thinks this uploaded
            {"ETag": etag3, "PartNumber": 3},
        ]

        response = self.client.post(
            f"/api/v1/files/{f.id}/complete/",
            data={
                "content_sha256": "0" * 64,
                "parts": client_claimed_parts,
            },
            format="json",
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT,
            f"Expected 409; got body={response_body(response)!r}",
        )
        details = _extract_details(response_body(response))
        # ONLY part 2 is missing — the client can re-upload just
        # this one chunk and retry, no need to redo parts 1 / 3.
        self.assertEqual(
            details.get("missing_parts"),
            [2],
            f"Expected ONLY part 2 missing; got details={details!r}",
        )
        self.assertEqual(details.get("expected_count"), 3)
        self.assertEqual(details.get("uploaded_count"), 2)

    @pytest.mark.integration
    def test_complete_after_uploading_missing_part_succeeds(self):
        # The full retry workflow: complete returns 409 with
        # missing_parts=[2]; client uploads part 2; retry complete
        # → no longer rejected by the parts gate. This pins the
        # 260.5.H.2 client-retry contract end-to-end.
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")
        f, upload_id = self._seed_pending_multipart_file(chunk_count=3)
        etag1 = self._upload_part(file_obj=f, upload_id=upload_id, part_number=1)
        etag3 = self._upload_part(file_obj=f, upload_id=upload_id, part_number=3)

        # First complete — 409 missing part 2.
        response = self.client.post(
            f"/api/v1/files/{f.id}/complete/",
            data={
                "content_sha256": "0" * 64,
                "parts": [
                    {"ETag": etag1, "PartNumber": 1},
                    {"ETag": "fake", "PartNumber": 2},
                    {"ETag": etag3, "PartNumber": 3},
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(_extract_error_code(response_body(response)), "MULTIPART_INCOMPLETE")

        # Client retries the missing part.
        etag2 = self._upload_part(file_obj=f, upload_id=upload_id, part_number=2)

        # Second complete — gate now passes (all 3 parts present).
        # The compose step might fail on small-part size in some
        # backends but our gate's job is done; we assert the gate
        # is no longer the rejection cause.
        response = self.client.post(
            f"/api/v1/files/{f.id}/complete/",
            data={
                "content_sha256": "0" * 64,
                "parts": [
                    {"ETag": etag1, "PartNumber": 1},
                    {"ETag": etag2, "PartNumber": 2},
                    {"ETag": etag3, "PartNumber": 3},
                ],
            },
            format="json",
        )
        # Either 200 (compose succeeded — MinIO accepted small
        # parts) or 500 from compose (S3 production minimum-part-
        # size policy). NEITHER is the 409 MULTIPART_INCOMPLETE
        # we just fixed — that's the assertion.
        self.assertNotEqual(
            response.status_code,
            status.HTTP_409_CONFLICT,
            f"Gate must NOT re-fire after missing part is uploaded; "
            f"got body={response_body(response)!r}",
        )
        if _extract_error_code(response_body(response)) is not None:
            self.assertNotEqual(
                _extract_error_code(response_body(response)),
                "MULTIPART_INCOMPLETE",
                "MULTIPART_INCOMPLETE must not fire when all parts present",
            )


# ---------------------------------------------------------------------------
# 260.5.H — Aborted upload distinction
# ---------------------------------------------------------------------------


@pytest.mark.xdist_group("minio_multipart")
class MultipartUploadNoLongerExistsTest(_MultipartCompleteRaceTestMixin, TransactionTestCase):
    """Phase 260.5.H — when the upload was aborted / expired, the
    server returns 409 ``MULTIPART_UPLOAD_NO_LONGER_EXISTS``
    distinct from MULTIPART_INCOMPLETE.

    The two 409 codes drive different client recovery paths:
    * MULTIPART_INCOMPLETE → re-upload missing parts AND retry.
    * MULTIPART_UPLOAD_NO_LONGER_EXISTS → re-init the upload from
      scratch (POST /files/init/), no parts to recover.
    """

    @pytest.mark.integration
    def test_complete_after_abort_returns_no_longer_exists(self):
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")
        f, upload_id = self._seed_pending_multipart_file(chunk_count=2)
        # Abort the upload mid-flight (S3 lifecycle / manual abort
        # / expired session — same observable shape on the server
        # side: list_parts raises NoSuchUpload).
        self.storage_client.abort_multipart_upload(
            key=f.storage_path,
            upload_id=upload_id,
        )

        response = self.client.post(
            f"/api/v1/files/{f.id}/complete/",
            data={
                "content_sha256": "0" * 64,
                "parts": [{"ETag": "fake", "PartNumber": 1}],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        code = _extract_error_code(response_body(response))
        self.assertEqual(
            code,
            "MULTIPART_UPLOAD_NO_LONGER_EXISTS",
            f"Aborted upload must surface NO_LONGER_EXISTS not "
            f"INCOMPLETE; got body={response_body(response)!r}",
        )


# ---------------------------------------------------------------------------
# 260.5.H — chunk_count fallback (legacy uploads without metadata)
# ---------------------------------------------------------------------------


@pytest.mark.xdist_group("minio_multipart")
class MultipartIncompleteFallbackTest(_MultipartCompleteRaceTestMixin, TransactionTestCase):
    """When ``metadata_json.chunk_count`` is missing (legacy
    uploads pre-260.5.H), the server falls back to the client-
    submitted ``parts`` list to determine what should be present.
    Defence in depth — the union of "platform expects" and "client
    claims" must all be in S3.
    """

    @pytest.mark.integration
    def test_missing_chunk_count_uses_client_parts_as_expected_set(self):
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")
        f, _upload_id = self._seed_pending_multipart_file(chunk_count=2)
        # Strip chunk_count from metadata to simulate a legacy
        # upload — we still expect the gate to fire on missing
        # parts, just using the client's submission as the
        # "expected" set.
        f.metadata_json.pop("chunk_count", None)
        f.save()

        # Client claims it uploaded part 1 + part 2 but neither
        # actually made it to S3.
        response = self.client.post(
            f"/api/v1/files/{f.id}/complete/",
            data={
                "content_sha256": "0" * 64,
                "parts": [
                    {"ETag": "fake-1", "PartNumber": 1},
                    {"ETag": "fake-2", "PartNumber": 2},
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(
            _extract_error_code(response_body(response)),
            "MULTIPART_INCOMPLETE",
        )
        details = _extract_details(response_body(response))
        # Both parts the client claimed — the fallback used the
        # client's list as the expected set.
        self.assertEqual(
            sorted(details.get("missing_parts") or []),
            [1, 2],
        )


# ---------------------------------------------------------------------------
# 260.5.H.R1 GAP-B — concurrent-complete race already-completed handling
# ---------------------------------------------------------------------------


class CompleteUploadAlreadyCompletedTest(_MultipartCompleteRaceTestMixin, TransactionTestCase):
    """Phase 260.5.H.R1 GAP-B — when two concurrent ``complete_upload``
    requests race, the second loser MUST get a typed
    ``UPLOAD_ALREADY_COMPLETED`` 409, not a generic flat-string
    error. Distinguishes "concurrent race, already done"
    (idempotent success — treat as if THIS call succeeded) from
    "MULTIPART_INCOMPLETE / NO_LONGER_EXISTS" (recoverable but
    different actions) and from "BUSINESS_RULES_VALIDATION"
    (input rejection).
    """

    def _seed_active_file(self) -> File:
        # Single-PUT upload that already landed (status=ACTIVE).
        # Concurrent-complete race outcome the second loser sees.
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")
        file_id = uuid.uuid4()
        return File.objects.create(
            id=file_id,
            tenant=self.tenant,
            name="done.bin",
            content_type="application/octet-stream",
            size=1024,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.PENDING_SCAN,
            storage_path=f"{self.tenant.id}/{file_id}/done.bin",
            created_by=self.user,
            metadata_json={"upload_method": "browser"},
        )

    @pytest.mark.integration
    def test_complete_on_already_active_file_returns_typed_code(self):
        f = self._seed_active_file()
        response = self.client.post(
            f"/api/v1/files/{f.id}/complete/",
            data={"content_sha256": "0" * 64},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        # Typed code lets the SDK distinguish "race lost" from
        # other 409s.
        self.assertEqual(
            _extract_error_code(response_body(response)),
            "UPLOAD_ALREADY_COMPLETED",
            f"Expected UPLOAD_ALREADY_COMPLETED; got body={response_body(response)!r}",
        )
        details = _extract_details(response_body(response))
        self.assertEqual(details.get("file_id"), str(f.id))
        self.assertIn(details.get("current_status"), ("ACTIVE", "COMPLETED"))


# ---------------------------------------------------------------------------
# 260.5.H.R1 GAP-C — MULTIPART_LIST_FAILED 502 path coverage
# ---------------------------------------------------------------------------


class MultipartListFailedTest(_MultipartCompleteRaceTestMixin, TransactionTestCase):
    """Phase 260.5.H.R1 GAP-C — when ``list_multipart_parts``
    fails with a non-LookupError, non-ClientError exception
    (transient transport error, S3 5xx that bubbled past the
    storage layer's wrapping), the gate returns 502
    ``MULTIPART_LIST_FAILED`` so the client retries the SAME
    complete call rather than re-uploading or re-initialising.

    Fault injection uses a tightly-scoped subclass of
    ``S3StorageClient`` that overrides ``list_multipart_parts`` to
    raise — NOT a mock of the gate logic itself. The view's
    ``S3StorageClient()`` constructor would normally bind to the
    real client, but Django's tests don't have a clean injection
    point, so we use ``unittest.mock.patch`` AT THE BOUNDARY
    (the constructor) to swap in our subclass for this test only.
    The subclass is real Python code that exercises the real
    gate — only the storage layer is replaced.
    """

    @pytest.mark.integration
    def test_transient_list_parts_failure_surfaces_502_with_typed_code(self):
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")
        f, upload_id = self._seed_pending_multipart_file(chunk_count=1)

        # Subclass that raises on list_multipart_parts ONLY —
        # passes initiate / upload_part / complete through to the
        # real backend so any other call works normally. The view
        # creates a fresh S3StorageClient() inside the request
        # handler; we patch the class so the request gets our
        # subclass.
        from hub.apps.files.storage import S3StorageClient

        class TransientListFailureClient(S3StorageClient):
            def list_multipart_parts(self, key, upload_id):
                raise RuntimeError("simulated transient S3 error (proxy 503)")

        from unittest.mock import patch

        with patch(
            "hub.apps.files.views.S3StorageClient",
            TransientListFailureClient,
        ):
            response = self.client.post(
                f"/api/v1/files/{f.id}/complete/",
                data={
                    "content_sha256": "0" * 64,
                    "parts": [{"ETag": "fake", "PartNumber": 1}],
                },
                format="json",
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_502_BAD_GATEWAY,
            f"Expected 502 for transient list_parts failure; got body={response_body(response)!r}",
        )
        self.assertEqual(
            _extract_error_code(response_body(response)),
            "MULTIPART_LIST_FAILED",
        )
        details = _extract_details(response_body(response))
        # Triage payload — operator can correlate by file_id +
        # upload_id without parsing the message.
        self.assertEqual(details.get("file_id"), str(f.id))
        self.assertEqual(details.get("upload_id"), upload_id)
        # File row is still UPLOADING — gate did not commit.
        f.refresh_from_db()
        self.assertEqual(f.status, FileStatus.UPLOADING)
