"""
Phase 203 — ClamAV scanner, RQ scan job, and download gates.

Uses real TCP/S3 where possible. Live daemon tests self-probe ClamAV at
``setUp`` time via Django settings (``CLAMAV_HOST`` / ``CLAMAV_PORT``) and
skip cleanly when the daemon is unreachable — no env-var gate required.
"""

from __future__ import annotations

import unittest
import uuid

import pytest
from django.conf import settings
from django.test import TestCase, override_settings
from rest_framework import status

from hub.apps.audit.models import AuditEvent
from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.files.scanner import EICAR_STANDARD_TEST_BYTES, ClamAVScanner
from hub.apps.files.storage import S3StorageClient
from hub.apps.files.tasks import scan_file_malware
from hub.apps.files.tests.test_base import FilesAPITestBase, FilesTestBase

pytestmark = pytest.mark.django_db(transaction=True)


class ClamAVScannerUnitTest(TestCase):
    """Scanner behavior against unreachable clamd (real connection refusal, no mocks)."""

    def test_classify_bytes_unreachable_returns_scan_unavailable(self):
        scanner = ClamAVScanner(host="127.0.0.1", port=65441, timeout=1.0)
        self.assertEqual(scanner.classify_bytes(b"hello"), FileScanStatus.SCAN_UNAVAILABLE)


def _clamav_probe_scanner() -> ClamAVScanner | None:
    """Return a working ClamAVScanner or None if the daemon is unreachable."""
    host = getattr(settings, "CLAMAV_HOST", "127.0.0.1")
    port = int(getattr(settings, "CLAMAV_PORT", 3310))
    timeout = min(float(getattr(settings, "CLAMAV_TIMEOUT_SECONDS", 120.0)), 30.0)
    scanner = ClamAVScanner(host=host, port=port, timeout=timeout)
    try:
        # Quick smoke test — classify clean bytes.  If this raises,
        # clamd is unreachable and we skip.
        outcome, _ = scanner.classify_bytes_with_detail(b"no malware here\n")
        # Any outcome means connectivity works (even SCAN_UNAVAILABLE means
        # the daemon answered, just didn't scan properly).
        return scanner
    except Exception:
        return None


@pytest.mark.requires_clamav
class ClamAVScannerLiveTest(TestCase):
    """Requires a running ClamAV daemon (e.g. ``docker compose up clamav``).

    Self-probes connectivity at ``setUp`` time via Django settings
    (``CLAMAV_HOST`` / ``CLAMAV_PORT``). Skips cleanly when clamd is
    unreachable — no env-var gate needed.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if _clamav_probe_scanner() is None:
            host = getattr(settings, "CLAMAV_HOST", "127.0.0.1")
            port = int(getattr(settings, "CLAMAV_PORT", 3310))
            raise pytest.skip(
                f"ClamAV daemon unreachable at {host}:{port} — "
                "start the clamav-test profile or publish port 3310"
            )

    def test_clean_and_eicar(self):
        host = getattr(settings, "CLAMAV_HOST", "127.0.0.1")
        port = int(getattr(settings, "CLAMAV_PORT", 3310))
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
        except (ConnectionError, TimeoutError, OSError):  # pragma: no cover — S3 probe
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
        audit = AuditEvent.objects.filter(
            action="FILE_MALWARE_SCAN_UNAVAILABLE",
            resource_id=file_obj.id,
        ).first()
        self.assertIsNotNone(audit, "FILE_MALWARE_SCAN_UNAVAILABLE audit event must be emitted")
        self.assertEqual(audit.result, "WARNING")
        self.assertEqual(
            audit.details_json.get("reason"),
            "clamav_unreachable_or_client_error",
        )
        self.assertEqual(audit.details_json.get("clamav_host"), "127.0.0.1")
        self.assertEqual(audit.details_json.get("clamav_port"), 65442)
        self.assertEqual(audit.tenant, self.tenant)

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
        audit = AuditEvent.objects.filter(
            action="FILE_MALWARE_SCAN_STORAGE_ERROR",
            resource_id=file_obj.id,
        ).first()
        self.assertIsNotNone(audit, "FILE_MALWARE_SCAN_STORAGE_ERROR audit event must be emitted")
        self.assertEqual(audit.result, "WARNING")
        self.assertEqual(
            audit.details_json.get("error_type"),
            "StorageObjectNotFoundError",
        )
        self.assertEqual(audit.tenant, self.tenant)


class FileDownloadMalwareGateAPITest(FilesAPITestBase):
    """403 FILE_SCAN_PENDING / FILE_INFECTED on download endpoint."""

    def setUp(self):
        super().setUp()
        self.storage_available = False
        try:
            S3StorageClient()._ensure_bucket_exists()
            self.storage_available = True
        except (ConnectionError, TimeoutError, OSError):  # pragma: no cover — S3 probe
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


class ScanFileMalwareIdempotencyTest(FilesTestBase):
    """Idempotency and guard-clause tests for the scan_file_malware RQ task."""

    def setUp(self):
        super().setUp()
        self._storage_ok = False
        try:
            S3StorageClient()._ensure_bucket_exists()
            self._storage_ok = True
        except (ConnectionError, TimeoutError, OSError):  # pragma: no cover — S3 probe
            self._storage_ok = False

    @override_settings(CLAMAV_HOST="127.0.0.1", CLAMAV_PORT=65443, CLAMAV_ENABLED=True)
    def test_scan_file_malware_idempotent_second_call_is_noop(self):
        """Second scan call is a no-op — scanned_at must not change."""
        if not self._storage_ok:
            self.skipTest("S3/MinIO not available")

        import uuid

        body = b"idempotency-test-body"
        storage_path = f"{self.tenant.id}/{uuid.uuid4()}/idem.txt"
        storage = S3StorageClient()
        storage.upload_file(storage_path, body, "text/plain")

        file_obj = File.objects.create(
            tenant=self.tenant,
            name="idem.txt",
            content_type="text/plain",
            size=len(body),
            storage_path=storage_path,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.PENDING_SCAN,
            created_by=self.user,
        )

        # First call — sets SCAN_UNAVAILABLE (bad port)
        scan_file_malware(str(file_obj.id))
        file_obj.refresh_from_db()
        self.assertEqual(file_obj.scan_status, FileScanStatus.SCAN_UNAVAILABLE)
        first_scanned_at = file_obj.scanned_at
        self.assertIsNotNone(first_scanned_at)

        # Second call — idempotency guard at tasks.py:48-49 skips processing
        scan_file_malware(str(file_obj.id))
        file_obj.refresh_from_db()
        self.assertEqual(file_obj.scan_status, FileScanStatus.SCAN_UNAVAILABLE)
        self.assertEqual(
            file_obj.scanned_at,
            first_scanned_at,
            "Second scan call must not update scanned_at timestamp",
        )

    def test_scan_file_malware_gracefully_returns_when_file_deleted(self):
        """scan_file_malware(non_existent_uuid) must not raise or create audit events."""
        import uuid

        non_existent_id = uuid.uuid4()
        before = AuditEvent.objects.count()

        # Must not raise — the File.DoesNotExist guard at tasks.py:44-46 catches this
        scan_file_malware(str(non_existent_id))

        after = AuditEvent.objects.count()
        self.assertEqual(after, before, "No audit events must be created for a non-existent file")
