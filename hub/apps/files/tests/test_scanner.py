"""
Phase 203 — ClamAV scanner, RQ scan job, and download gates.

Uses real TCP/S3 where possible. Live daemon tests run only when
``RUN_CLAMAV_LIVE_TESTS=1`` and ``CLAMAV_LIVE_TEST_HOST`` point at a reachable clamd.
"""

from __future__ import annotations

import os
import unittest
import uuid

import pytest
from django.test import TestCase, override_settings
from rest_framework import status

from hub.apps.audit.models import AuditEvent
from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.files.scanner import ClamAVScanner, EICAR_STANDARD_TEST_BYTES
from hub.apps.files.storage import S3StorageClient
from hub.apps.files.tasks import scan_file_malware
from hub.apps.files.tests.test_base import FilesAPITestBase, FilesTestBase

pytestmark = pytest.mark.django_db(transaction=True)


class ClamAVScannerUnitTest(TestCase):
    """Scanner behavior against unreachable clamd (real connection refusal, no mocks)."""

    def test_classify_bytes_unreachable_returns_scan_unavailable(self):
        scanner = ClamAVScanner(host="127.0.0.1", port=65441, timeout=1.0)
        self.assertEqual(scanner.classify_bytes(b"hello"), FileScanStatus.SCAN_UNAVAILABLE)


@unittest.skipUnless(
    os.environ.get("RUN_CLAMAV_LIVE_TESTS") == "1"
    and bool(os.environ.get("CLAMAV_LIVE_TEST_HOST", "").strip()),
    "Set RUN_CLAMAV_LIVE_TESTS=1 and CLAMAV_LIVE_TEST_HOST (e.g. 127.0.0.1 when port 3310 is published)",
)
class ClamAVScannerLiveTest(TestCase):
    """Requires a running ClamAV daemon (e.g. docker compose up clamav)."""

    def test_clean_and_eicar(self):
        host = os.environ["CLAMAV_LIVE_TEST_HOST"].strip()
        port = int(os.environ.get("CLAMAV_LIVE_TEST_PORT", "3310"))
        scanner = ClamAVScanner(host=host, port=port, timeout=120.0)
        clean, cth = scanner.classify_bytes_with_detail(b"no malware here\n")
        self.assertEqual(clean, FileScanStatus.CLEAN)
        self.assertIsNone(cth)
        bad, threat = scanner.classify_bytes_with_detail(EICAR_STANDARD_TEST_BYTES)
        self.assertEqual(bad, FileScanStatus.INFECTED)
        self.assertIsNotNone(threat)
        self.assertIn("Eicar", threat, msg=threat)


class ScanFileMalwareJobTest(FilesTestBase):
    """RQ task reads from real S3 when available."""

    def setUp(self):
        super().setUp()
        self._storage_ok = False
        try:
            S3StorageClient()._ensure_bucket_exists()
            self._storage_ok = True
        except Exception:
            self._storage_ok = False

    @override_settings(CLAMAV_HOST="127.0.0.1", CLAMAV_PORT=65442, CLAMAV_ENABLED=True)
    def test_scan_marks_unavailable_and_audit_when_clam_unreachable(self):
        if not self._storage_ok:
            self.skipTest("S3/MinIO not available")

        body = b"plain text for scan job"
        storage_path = f"{self.tenant.id}/{uuid.uuid4()}/scan-job.txt"
        storage = S3StorageClient()
        storage.upload_file(storage_path, body, "text/plain")

        file_obj = File.objects.create(
            tenant=self.tenant,
            name="scan-job.txt",
            content_type="text/plain",
            size=len(body),
            storage_path=storage_path,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.PENDING_SCAN,
            created_by=self.user,
        )

        scan_file_malware(str(file_obj.id))

        file_obj.refresh_from_db()
        self.assertEqual(file_obj.scan_status, FileScanStatus.SCAN_UNAVAILABLE)
        self.assertIsNotNone(file_obj.scanned_at)
        self.assertTrue(
            AuditEvent.objects.filter(
                action="FILE_MALWARE_SCAN_UNAVAILABLE",
                resource_id=file_obj.id,
            ).exists()
        )

    @override_settings(CLAMAV_ENABLED=True, CLAMAV_HOST="127.0.0.1", CLAMAV_PORT=65442)
    def test_scan_marks_scan_error_and_audit_when_storage_missing_object(self):
        if not self._storage_ok:
            self.skipTest("S3/MinIO not available")

        file_obj = File.objects.create(
            tenant=self.tenant,
            name="ghost.txt",
            content_type="text/plain",
            size=3,
            storage_path=f"{self.tenant.id}/{uuid.uuid4()}/does-not-exist-in-bucket.txt",
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.PENDING_SCAN,
            created_by=self.user,
        )

        scan_file_malware(str(file_obj.id))

        file_obj.refresh_from_db()
        self.assertEqual(file_obj.scan_status, FileScanStatus.SCAN_ERROR)
        self.assertIsNotNone(file_obj.scanned_at)
        self.assertTrue(
            AuditEvent.objects.filter(
                action="FILE_MALWARE_SCAN_STORAGE_ERROR",
                resource_id=file_obj.id,
            ).exists()
        )


class FileDownloadMalwareGateAPITest(FilesAPITestBase):
    """403 FILE_SCAN_PENDING / FILE_INFECTED on download endpoint."""

    def setUp(self):
        super().setUp()
        self.storage_available = False
        try:
            S3StorageClient()._ensure_bucket_exists()
            self.storage_available = True
        except Exception:
            self.storage_available = False

    def test_download_blocked_when_pending_scan(self):
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        file_obj = File.objects.create(
            tenant=self.tenant,
            name="pending-scan.csv",
            content_type="text/csv",
            size=32,
            storage_path=f"{self.tenant.id}/{uuid.uuid4()}/pending-scan.csv",
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.PENDING_SCAN,
            created_by=self.user,
        )

        response = self.client.get(f"/api/v1/files/{file_obj.id}/download/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data.get("code"), "FILE_SCAN_PENDING")

    def test_download_blocked_when_infected(self):
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        file_obj = File.objects.create(
            tenant=self.tenant,
            name="bad.csv",
            content_type="text/csv",
            size=32,
            storage_path=f"{self.tenant.id}/{uuid.uuid4()}/bad.csv",
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.INFECTED,
            created_by=self.user,
        )

        response = self.client.get(f"/api/v1/files/{file_obj.id}/download/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data.get("code"), "FILE_INFECTED")

    def test_download_ok_when_clean(self):
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        response = self.client.get(f"/api/v1/files/{self.file.id}/download/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("download_url", response.data)
