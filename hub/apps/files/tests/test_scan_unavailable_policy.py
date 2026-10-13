"""W1.18 (oss-release-remediation) — SCAN_UNAVAILABLE_POLICY pins.

The ClamAV outage policy decision: when a file's scan status is
``SCAN_UNAVAILABLE`` (ClamAV disabled OR unreachable at scan time), the
upload/download/dataset gates historically FAILED OPEN — the file was
served and usable as a dataset source.

``SCAN_UNAVAILABLE_POLICY`` (default ``allow`` — availability, SRE
alerting via ``FILE_MALWARE_SCAN_UNAVAILABLE`` audits; the documented
decision + runbook live in docs/runbooks/file-virus-scan-incident.md)
flips the gates:

  * ``allow`` — SCAN_UNAVAILABLE proceeds (the pre-W1.18 behaviour).
  * ``block`` — SCAN_UNAVAILABLE is treated like PENDING_SCAN at the
    dataset-source gate AND the download gate: 503
    ``FILE_SCAN_UNAVAILABLE`` + a ``FILE_SCAN_UNAVAILABLE_BLOCKED``
    audit row.

These pins exercise the real gate functions and the real download view.
"""

import uuid
from pathlib import Path

import pytest
from django.test import override_settings
from rest_framework import status

from hub.apps.core.services.base import ValidationError
from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.files.tests.test_base import FilesAPITestBase

pytestmark = pytest.mark.django_db(transaction=True)


class _ScanUnavailablePolicyMixin(FilesAPITestBase):
    """Common fixture: an ACTIVE file whose scan never produced a verdict."""

    def setUp(self):
        super().setUp()
        self.unscanned_file = File.objects.create(
            tenant=self.tenant,
            name=f"unscanned-{uuid.uuid4().hex[:8]}.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.SCAN_UNAVAILABLE,
            storage_path=f"{self.tenant.id}/unscanned.csv",
            created_by=self.user,
        )

    def _audit_blocked_exists(self) -> bool:
        from hub.apps.audit.models import AuditEvent

        return AuditEvent.objects.filter(
            action="FILE_SCAN_UNAVAILABLE_BLOCKED",
            resource_id=str(self.unscanned_file.id),
        ).exists()


@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,
    RATE_LIMIT_ENABLED=False,
    SCAN_UNAVAILABLE_POLICY="block",
)
class TestScanUnavailablePolicyBlock(_ScanUnavailablePolicyMixin):
    """Policy=block: SCAN_UNAVAILABLE cannot back a dataset nor be
    downloaded — 503 with the typed code + audit."""

    def test_dataset_source_gate_blocks(self):
        from hub.apps.datasets.file_dataset_source_gate import (
            validate_file_allows_dataset_creation,
        )

        with pytest.raises(ValidationError) as ei:
            validate_file_allows_dataset_creation(self.unscanned_file)
        assert ei.value.code == "FILE_SCAN_UNAVAILABLE"
        assert ei.value.http_status == 503

    def test_dataset_source_gate_block_emits_audit(self):
        from hub.apps.datasets.file_dataset_source_gate import (
            validate_file_allows_dataset_creation,
        )

        with pytest.raises(ValidationError):
            validate_file_allows_dataset_creation(self.unscanned_file)
        assert (
            self._audit_blocked_exists()
        ), "The block must emit FILE_SCAN_UNAVAILABLE_BLOCKED for the file"

    def test_download_blocked(self):
        response = self.client.get(f"/api/v1/files/{self.unscanned_file.id}/download/")
        assert (
            response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        ), f"Expected 503, got {response.status_code}: {response.data}"
        assert response.data.get("code") == "FILE_SCAN_UNAVAILABLE"
        assert self._audit_blocked_exists()

    def test_clean_file_unaffected(self):
        from hub.apps.datasets.file_dataset_source_gate import (
            validate_file_allows_dataset_creation,
        )

        clean_file = File.objects.create(
            tenant=self.tenant,
            name="clean.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=f"{self.tenant.id}/clean.csv",
            created_by=self.user,
        )
        validate_file_allows_dataset_creation(clean_file)  # no raise

    def test_pending_file_still_blocked_with_original_code(self):
        from hub.apps.datasets.file_dataset_source_gate import (
            validate_file_allows_dataset_creation,
        )

        pending_file = File.objects.create(
            tenant=self.tenant,
            name="pending.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.PENDING_SCAN,
            storage_path=f"{self.tenant.id}/pending.csv",
            created_by=self.user,
        )
        with pytest.raises(ValidationError) as ei:
            validate_file_allows_dataset_creation(pending_file)
        assert ei.value.code == "FILE_SCAN_PENDING"  # unchanged


@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,
    RATE_LIMIT_ENABLED=False,
    SCAN_UNAVAILABLE_POLICY="allow",
)
class TestScanUnavailablePolicyAllow(_ScanUnavailablePolicyMixin):
    """Policy=allow (the default): SCAN_UNAVAILABLE proceeds."""

    def test_dataset_source_gate_allows(self):
        from hub.apps.datasets.file_dataset_source_gate import (
            validate_file_allows_dataset_creation,
        )

        validate_file_allows_dataset_creation(self.unscanned_file)  # no raise

    def test_download_allowed_when_storage_available(self):
        from hub.apps.files.storage import S3StorageClient

        storage_available = False
        try:
            S3StorageClient()._ensure_bucket_exists()
            storage_available = True
        except (ConnectionError, TimeoutError, OSError):  # pragma: no cover
            pass
        if not storage_available:
            pytest.skip("S3/MinIO storage not available")

        response = self.client.get(f"/api/v1/files/{self.unscanned_file.id}/download/")
        assert response.status_code == status.HTTP_200_OK
        assert "download_url" in response.data


class TestScanUnavailablePolicySetting:
    """The setting exists with validated values (source-level pin)."""

    def test_settings_declares_validated_policy(self):
        settings_path = Path(__file__).resolve().parents[3] / "settings.py"
        source = settings_path.read_text()
        assert (
            "SCAN_UNAVAILABLE_POLICY" in source
        ), "settings.py must declare SCAN_UNAVAILABLE_POLICY"
        block = source[source.index("SCAN_UNAVAILABLE_POLICY") - 200 :]
        assert (
            "ImproperlyConfigured" in block[: 200 + 400]
        ), "SCAN_UNAVAILABLE_POLICY must reject invalid values at boot"
        assert '"allow"' in source
        assert '"block"' in source

    def test_audit_event_constant_registered(self):
        from hub.apps.audit import event_types

        assert event_types.FILE_SCAN_UNAVAILABLE_BLOCKED == (
            "FILE_SCAN_UNAVAILABLE_BLOCKED"
        )
