"""
W1.12 (R2-S5) — presigned-upload replay pins.

The pre-fix TOCTOU: ``init_upload`` presigned a PUT for the FINAL
storage key (1-hour expiry). ``complete_upload`` verified the content,
flipped the row ACTIVE and the scan marked it CLEAN — but the presigned
URL stayed valid, so the client (or anyone holding the URL) could
RE-PUT different content over the same key AFTER completion: the
scanned, CLEAN object was silently replaced by attacker content.

Fix (server-side final-key copy): the presigned URL covers a STAGING
key only. ``complete_upload`` verifies the staging object, then the
SERVER copies staging → final key and deletes the staging object —
the client's write capability dies with the staging object and the
final key is only ever written by the server. A re-PUT after
completion recreates a harmless orphan staging object; it can never
touch the final key.

Pins (real MinIO, real presigned URLs, real HTTP — no mocks):

* re-PUT after completion cannot serve as CLEAN: the final key still
  holds the verified content and the download serves it;
* a multipart part URL cannot be replayed after the compose either;
* the completion no-storage fallback is test/dev-only — production
  fails closed on a missing staging object.

Storage availability follows the files-suite convention (graceful skip
when MinIO is down; the W16 policy governs CI).
"""

import hashlib
import uuid

import httpx
import pytest
from django.test import override_settings
from rest_framework import status

from hub.apps.files.models import File, FileStatus
from hub.apps.files.storage import S3StorageClient
from hub.apps.files.tests.test_base import FilesAPITestBase

pytestmark = pytest.mark.django_db(transaction=True)


class PresignedReplayPinTest(FilesAPITestBase):
    """The replay matrix against the real complete flow."""

    def setUp(self):
        super().setUp()
        self.storage_available = False
        try:
            self.storage_client = S3StorageClient()
            self.storage_client._ensure_bucket_exists()
            self.storage_available = True
        except (ConnectionError, TimeoutError, OSError):
            self.storage_available = False

    def _init(self, size, upload_method="browser", name=None):
        response = self.client.post(
            "/api/v1/files/init/",
            {
                "name": name or f"replay-{uuid.uuid4().hex[:8]}.txt",
                "content_type": "text/plain",
                "size": size,
                "upload_method": upload_method,
            },
            format="json",
        )
        return response

    def _put(self, upload_url, content, content_type="text/plain"):
        return httpx.put(upload_url, content=content, headers={"Content-Type": content_type})

    def _sha(self, content):
        return hashlib.sha256(content).hexdigest()

    def test_replay_put_after_completion_cannot_serve_as_clean(self):
        """The core pin: re-PUT over the presigned URL after completion
        leaves the FINAL key (the served object) untouched."""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        content_a = b"verified content A"
        content_b = b"MALICIOUS content B"

        init = self._init(size=len(content_a))
        self.assertEqual(init.status_code, status.HTTP_201_CREATED, init.data)
        file_id = init.data["file_id"]
        upload_url = init.data["upload_url"]
        self.assertFalse(init.data["requires_multipart"])

        put_a = self._put(upload_url, content_a)
        self.assertEqual(put_a.status_code, 200)

        complete = self.client.post(
            f"/api/v1/files/{file_id}/complete/",
            {"content_sha256": self._sha(content_a)},
            format="json",
        )
        self.assertEqual(complete.status_code, status.HTTP_200_OK, complete.data)
        file_obj = File.objects.get(id=file_id)
        self.assertEqual(file_obj.status, FileStatus.ACTIVE)

        # The presigned URL is still valid — the attacker re-PUTs.
        put_b = self._put(upload_url, content_b)
        self.assertEqual(put_b.status_code, 200)

        # The final key still serves the VERIFIED content — the replay
        # cannot serve as CLEAN.
        served = self.storage_client.get_file_content(file_obj.storage_path)
        self.assertEqual(served, content_a)
        file_obj.refresh_from_db()
        self.assertEqual(file_obj.content_sha256, self._sha(content_a))

        # The download surface presigns the final key — the replayed
        # bytes never reach a client. (ClamAV is disabled in this
        # environment, so the scan pipeline never flips CLEAN — mark it
        # as the completed scan would before exercising the download.)
        from hub.apps.files.models import FileScanStatus

        File.objects.filter(id=file_id).update(
            scan_status=FileScanStatus.CLEAN
        )
        download = self.client.get(f"/api/v1/files/{file_id}/download/")
        self.assertEqual(download.status_code, status.HTTP_200_OK, download.data)
        self.assertEqual(download.data["content_sha256"], self._sha(content_a))

    @override_settings(MULTIPART_UPLOAD_THRESHOLD=1)
    def test_multipart_part_url_replay_cannot_touch_final_key(self):
        """The multipart leg: after the compose, part URLs are dead
        (S3 rejects upload_part on a completed upload) and the final
        key stays the verified content."""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        part_data = b"x" * (5 * 1024 * 1024)  # S3 minimum part size

        init = self._init(
            size=len(part_data),
            upload_method="sdk",
            name=f"replay-mp-{uuid.uuid4().hex[:8]}.txt",
        )
        self.assertEqual(init.status_code, status.HTTP_201_CREATED, init.data)
        self.assertTrue(init.data["requires_multipart"])
        file_id = init.data["file_id"]
        upload_id = init.data["upload_id"]

        # The bundled first-chunk URL is the browser-rewritten one; the
        # SDK path uses the internal URL. Re-sign part 1 for the staging
        # key resolved from the file row.
        file_obj = File.objects.get(id=file_id)
        staging_key = (
            file_obj.metadata_json.get("upload_staging_key")
            or file_obj.storage_path
        )
        internal_part_url = self.storage_client.generate_presigned_part_url(
            key=staging_key, upload_id=upload_id, part_number=1, expires_in=3600
        )
        put_part = self._put(internal_part_url, part_data)
        self.assertEqual(put_part.status_code, 200)

        listed = self.storage_client.list_multipart_parts(
            key=staging_key, upload_id=upload_id
        )
        etag = [p["etag"] for p in listed if p["part_number"] == 1][0]

        complete = self.client.post(
            f"/api/v1/files/{file_id}/complete/",
            {
                "content_sha256": self._sha(part_data),
                "parts": [{"ETag": etag, "PartNumber": 1}],
            },
            format="json",
        )
        self.assertEqual(complete.status_code, status.HTTP_200_OK, complete.data)

        # Replay: the part URL must be dead after the compose.
        replay = self._put(internal_part_url, b"y" * 1024)
        self.assertNotEqual(replay.status_code, 200)

        # The final key serves the verified part content.
        served = self.storage_client.get_file_content(file_obj.storage_path)
        self.assertEqual(served, part_data)

    @override_settings(ENVIRONMENT="production")
    def test_completion_without_staging_object_fails_closed_in_production(self):
        """The no-storage fallback is test/dev-only: in production, a
        completion with no staged object is rejected."""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        file_id = uuid.uuid4()
        File.objects.create(
            id=file_id,
            tenant=self.tenant,
            name=f"phantom-{uuid.uuid4().hex[:8]}.txt",
            content_type="text/plain",
            size=10,
            storage_path=f"{self.tenant.id}/{file_id}/phantom.txt",
            status=FileStatus.PENDING,
            created_by=self.user,
        )

        response = self.client.post(
            f"/api/v1/files/{file_id}/complete/",
            {"content_sha256": "a" * 64},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["code"], "FILE_OBJECT_MISSING")
