"""
Phase 260.2.D — EICAR upload → malware scan → download blocked → dataset blocked.

Self-probing: ``setUp`` checks ClamAV connectivity and EICAR detection at
runtime. If ClamAV or S3/MinIO is unavailable the test is skipped with a
clear message (no env-var gate needed). This mirrors the ``redis_or_skip()``
pattern — probe, don't pre-gate.

RQ runs synchronously under pytest (``RQ_QUEUES[*][ASYNC]=False``); the scan job
executes on transaction commit from ``complete_upload``.
"""

from __future__ import annotations

import hashlib
import time
import uuid

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TransactionTestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.files.scanner import EICAR_STANDARD_TEST_BYTES, ClamAVScanner
from hub.apps.files.storage import S3StorageClient
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

User = get_user_model()


def _clamav_detects_eicar() -> bool:
    scanner = ClamAVScanner(
        host=getattr(settings, "CLAMAV_HOST", "127.0.0.1"),
        port=int(getattr(settings, "CLAMAV_PORT", 3310)),
        timeout=min(float(getattr(settings, "CLAMAV_TIMEOUT_SECONDS", 120.0)), 90.0),
    )
    outcome, _name = scanner.classify_bytes_with_detail(EICAR_STANDARD_TEST_BYTES)
    return outcome == FileScanStatus.INFECTED


def _s3_storage_available() -> bool:
    try:
        storage = S3StorageClient()
        storage._ensure_bucket_exists()
        return True
    except Exception:
        return False


def _clamav_and_storage_skip_reason() -> str | None:
    """Return a skip message if ClamAV or S3 is unavailable, else None."""
    if not getattr(settings, "CLAMAV_ENABLED", True):
        return "CLAMAV_ENABLED is False — cannot run virus scan E2E"
    if not _clamav_detects_eicar():
        return (
            "ClamAV did not classify EICAR as INFECTED — ensure the clamav-test "
            "profile is started and CLAMAV_HOST/CLAMAV_PORT are reachable"
        )
    if not _s3_storage_available():
        return "S3/MinIO storage not available"
    return None


@pytest.mark.requires_clamav
@pytest.mark.django_db(transaction=True)
@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,
    RATE_LIMIT_ENABLED=False,
    MAGIC_BYTE_VALIDATION_ENABLED=False,
    CLAMAV_ENABLED=True,
)
class FileVirusScanE2ETest(TransactionTestCase):
    """Uses TransactionTestCase so upload commits enqueue + synchronous RQ scan.

    Self-probes ClamAV + S3 availability at ``setUp`` time — skips with
    a clear message when infrastructure is absent rather than requiring
    a pre-set env var.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        reason = _clamav_and_storage_skip_reason()
        if reason is not None:
            raise pytest.skip(reason)

    def setUp(self):
        super().setUp()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Virus E2E Tenant {uid}",
            slug=f"virus-e2e-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"virus-e2e-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @pytest.mark.integration
    def test_eicar_complete_upload_scan_download_and_dataset_rejected(self):
        body = EICAR_STANDARD_TEST_BYTES
        fid = uuid.uuid4()
        pending = File.objects.create(
            id=fid,
            tenant=self.tenant,
            name="eicar.csv",
            content_type="text/csv",
            size=len(body),
            status=FileStatus.PENDING,
            storage_path=f"{self.tenant.id}/{fid}/eicar.csv",
            created_by=self.user,
            scan_status=FileScanStatus.PENDING_SCAN,
        )

        storage = S3StorageClient()
        storage.save_file(
            tenant_id=str(self.tenant.id),
            file_id=str(pending.id),
            file_content=ContentFile(body),
            file_name=pending.name,
        )
        sha = hashlib.sha256(body).hexdigest()

        complete = self.client.post(
            f"/api/v1/files/{fid}/complete/",
            {"content_sha256": sha},
            format="json",
        )
        self.assertEqual(
            complete.status_code,
            status.HTTP_200_OK,
            msg=getattr(complete, "data", complete.content),
        )

        deadline = time.monotonic() + 180.0
        pending.refresh_from_db()
        while pending.scan_status == FileScanStatus.PENDING_SCAN and time.monotonic() < deadline:
            time.sleep(0.35)
            pending.refresh_from_db()

        self.assertEqual(
            pending.scan_status,
            FileScanStatus.INFECTED,
            msg=(
                f"Expected INFECTED after scan; got {pending.scan_status!r}. "
                "Check CLAMAV_ENABLED, worker/RQ sync mode, and daemon health."
            ),
        )

        from hub.apps.audit.models import AuditEvent

        audit = AuditEvent.objects.filter(
            action="FILE_MALWARE_DETECTED",
            resource_id=str(fid),
        ).first()
        self.assertIsNotNone(
            audit,
            "Malware scan should emit FILE_MALWARE_DETECTED audit event",
        )
        self.assertEqual(audit.result, "FAILURE")
        self.assertEqual(audit.resource_type, "FILE")
        self.assertEqual(audit.tenant_id, self.tenant.id)
        details = audit.details_json or {}
        self.assertEqual(details.get("scan_status"), FileScanStatus.INFECTED)
        self.assertIsNotNone(details.get("threat_signature"))
        self.assertIn("Eicar", details.get("threat_signature", ""))

        dl = self.client.get(f"/api/v1/files/{fid}/download/")
        self.assertEqual(dl.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(dl.data.get("code"), "FILE_INFECTED")

        ds = self.client.post("/api/v1/datasets/", {"file_id": str(fid)}, format="json")
        self.assertEqual(ds.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(ds.data.get("code"), "FILE_INFECTED")
