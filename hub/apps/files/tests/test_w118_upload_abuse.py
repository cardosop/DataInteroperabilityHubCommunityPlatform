"""W11.8 (oss-release-remediation) — ASVS V12 file-upload abuse suite
(register rows 3/14).

One named test per abuse class, against the REAL stack (real MinIO,
real presigned URLs, real HTTP — no mocks; the storage guard follows
the files-suite convention):

* **magic-byte bypass** — a PE payload declared ``text/csv`` is
  rejected at ``complete_upload`` with ``FILE_FORMAT_MISMATCH`` (the
  view-level integration cell the unit suite did not carry);
* **content-type spoof** — a ZIP payload declared ``text/csv`` is
  rejected the same way (the PK prefix is in the disguise list);
* **zip-bomb / zip-slip** — the platform extracts NOTHING (the AST pin
  in scripts/tests proves no ``extractall``/``extract``/
  ``unpack_archive`` in the non-test tree) and zip containers are
  REJECTED at every ingestion gate (worker inference + the legacy
  workflow's strict map — the pre-fix CSV-default gap is fixed and
  pinned here);
* **oversized** — the existing size pins are cited (validator +
  init-API + worker caps);
* **unicode names** — NFC roundtrip + traversal rejection cited, plus
  the adversarial overlong/RTL cells here;
* **presigned replay** — the W1.12 staging-key design is pinned by
  ``test_presigned_replay_w112.py`` (3/3 — the fix shipped in this
  change).

The production-deploy magic-byte posture (settings default True AND
helm ``"true"``) is pinned in ``scripts/tests/test_w118_upload_abuse_veracity.py``.
"""

import hashlib
import uuid

import pytest
from django.test import TestCase
from rest_framework import status

from hub.apps.files.models import File, FileStatus
from hub.apps.files.storage import S3StorageClient
from hub.apps.files.tests.test_base import FilesAPITestBase
from hub.apps.scheduled_ingestion.catalog_records import _infer_format_from_path

pytestmark = pytest.mark.django_db(transaction=True)

_PE_HEAD = b"MZ" + b"\x00" * 64 + b"This program cannot be run in DOS mode"
_ZIP_HEAD = b"PK\x03\x04" + b"\x00" * 64


class UploadAbuseViewTest(FilesAPITestBase):
    """The view-level abuse matrix against the real complete flow."""

    def setUp(self):
        super().setUp()
        self.storage_available = False
        try:
            self.storage_client = S3StorageClient()
            self.storage_client._ensure_bucket_exists()
            self.storage_available = True
        except (ConnectionError, TimeoutError, OSError):
            self.storage_available = False

    def _upload_and_complete(self, content: bytes, content_type: str, name: str):
        init = self.client.post(
            "/api/v1/files/init/",
            {
                "name": name,
                "content_type": content_type,
                "size": len(content),
                "upload_method": "browser",
            },
            format="json",
        )
        assert init.status_code == status.HTTP_201_CREATED, init.data
        file_id = init.data["file_id"]

        import httpx

        put = httpx.put(init.data["upload_url"], content=content, headers={"Content-Type": content_type})
        assert put.status_code == 200, put.text

        complete = self.client.post(
            f"/api/v1/files/{file_id}/complete/",
            {"content_sha256": hashlib.sha256(content).hexdigest()},
            format="json",
        )
        return complete, File.objects.get(id=file_id)

    def test_magic_byte_bypass_pe_as_csv_rejected_at_complete(self):
        """The magic-byte cell, view-level: a PE payload declared
        text/csv is rejected at complete_upload — FILE_FORMAT_MISMATCH,
        row FAILED, the object deleted (no orphan)."""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        complete, file_obj = self._upload_and_complete(
            _PE_HEAD, "text/csv", f"abuse-{uuid.uuid4().hex[:8]}.csv"
        )

        self.assertEqual(complete.status_code, status.HTTP_400_BAD_REQUEST, complete.data)
        self.assertEqual(complete.json()["code"], "FILE_FORMAT_MISMATCH")
        file_obj.refresh_from_db()
        self.assertEqual(file_obj.status, FileStatus.FAILED)
        # The rejected object was deleted (R2-B4 — no orphan).
        self.assertFalse(self.storage_client.file_exists(file_obj.storage_path))

    def test_content_type_spoof_zip_as_csv_rejected(self):
        """The content-type spoof cell: a ZIP payload declared text/csv
        hits the PK prefix in the disguise list — same rejection."""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        complete, _file_obj = self._upload_and_complete(
            _ZIP_HEAD, "text/csv", f"abuse-{uuid.uuid4().hex[:8]}.csv"
        )

        self.assertEqual(complete.status_code, status.HTTP_400_BAD_REQUEST, complete.data)
        self.assertEqual(complete.json()["code"], "FILE_FORMAT_MISMATCH")

    def test_unicode_overlong_and_rtl_names_roundtrip(self):
        """The unicode-names cell: an overlong (300-char) name is
        REJECTED with 400 (never silently truncated into a different
        name — the abuse-safe contract), and an RTL/bidi name
        roundtrips through init → detail unchanged."""
        overlong = ("é" * 300) + ".txt"
        init = self.client.post(
            "/api/v1/files/init/",
            {
                "name": overlong,
                "content_type": "text/plain",
                "size": 4,
                "upload_method": "browser",
            },
            format="json",
        )
        self.assertEqual(init.status_code, status.HTTP_400_BAD_REQUEST, init.data)
        self.assertEqual(init.json()["error"]["code"], "VALIDATION_ERROR")

        rtl_name = "דוח-סופי-" + chr(0x202E) + "-report.txt"  # RTL + bidi override
        init2 = self.client.post(
            "/api/v1/files/init/",
            {
                "name": rtl_name,
                "content_type": "text/plain",
                "size": 4,
                "upload_method": "browser",
            },
            format="json",
        )
        self.assertEqual(init2.status_code, status.HTTP_201_CREATED, init2.data)
        detail = self.client.get(f"/api/v1/files/{init2.data['file_id']}/")
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data["name"], rtl_name)


class IngestionFormatGateTest(TestCase):
    """The zip/gz rejection gates on the ingestion paths (zip-bomb /
    zip-slip absence via strict inference)."""

    def test_worker_inference_rejects_archive_extensions(self):
        for name in ("payload.zip", "payload.gz", "payload.tar", "payload.exe"):
            self.assertIsNone(_infer_format_from_path(name))

    def test_worker_inference_accepts_the_allowlist(self):
        for name in ("data.csv", "data.json", "data.parquet", "data.xlsx", "data.xls"):
            self.assertIsNotNone(_infer_format_from_path(name))

    def test_legacy_workflow_has_no_csv_default(self):
        """Source pin — the pre-fix legacy workflow map defaulted
        unknown extensions to CSV (register row 14); the default is
        gone from the source."""
        from pathlib import Path

        source = (
            Path(__file__).resolve().parent.parent.parent.parent.parent
            / "hub"
            / "apps"
            / "orchestration"
            / "workflows"
            / "scheduled_ingestion.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn('format_map.get(file_ext, "CSV")', source)
        self.assertIn("_infer_format_from_path", source)

    def test_dataset_format_map_has_no_csv_default(self):
        """Source pin — the dataset-creation format map no longer
        defaults unmapped content types to CSV; the xlsx MIMEs are
        mapped and the unresolvable pair is rejected typed."""
        from pathlib import Path

        source = (
            Path(__file__).resolve().parent.parent.parent.parent.parent
            / "hub"
            / "apps"
            / "datasets"
            / "services.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn('format_map.get(file_obj.content_type, "CSV")', source)
        self.assertIn(
            '"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "XLSX"',
            source,
        )
        self.assertIn('code="UNSUPPORTED_FORMAT"', source)
