"""
Unit tests for File model.
"""

import uuid
from io import BytesIO

import pytest

from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.files.tests.test_base import FilesTestBase

pytestmark = pytest.mark.django_db(transaction=True)


class FileModelTest(FilesTestBase):
    """Test File model"""

    def test_create_file(self):
        """Test file creation"""
        file_obj = File.objects.create(
            tenant=self.tenant,
            name=f"model-{uuid.uuid4().hex[:8]}.csv",
            size=1024,
            content_type="text/csv",
            status=FileStatus.UPLOADING,
            created_by=self.user,
        )

        self.assertEqual(file_obj.tenant, self.tenant)
        self.assertEqual(file_obj.name[:6], "model-")
        self.assertEqual(file_obj.size, 1024)
        self.assertEqual(file_obj.status, FileStatus.UPLOADING)

    def test_file_status_choices(self):
        """Test file status enum — ACTIVE is the terminal upload state."""
        file_obj = File.objects.create(
            tenant=self.tenant,
            name=f"status-{uuid.uuid4().hex[:8]}.csv",
            size=1024,
            content_type="text/csv",
            storage_path=f"tenants/{self.tenant.id}/files/{uuid.uuid4()}.csv",
        )

        file_obj.status = FileStatus.ACTIVE
        file_obj.save()
        self.assertEqual(file_obj.status, FileStatus.ACTIVE)

    # ── can_download() ──────────────────────────────────────────

    def test_can_download_active_clean(self):
        """ACTIVE + CLEAN → True."""
        f = File.objects.create(
            tenant=self.tenant, name=f"dl-{uuid.uuid4().hex[:8]}.csv",
            size=1, content_type="text/csv", status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN, created_by=self.user,
        )
        self.assertTrue(f.can_download())

    def test_can_download_active_pending_scan(self):
        """ACTIVE + PENDING_SCAN → False."""
        f = File.objects.create(
            tenant=self.tenant, name=f"dl-{uuid.uuid4().hex[:8]}.csv",
            size=1, content_type="text/csv", status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.PENDING_SCAN, created_by=self.user,
        )
        self.assertFalse(f.can_download())

    def test_can_download_active_infected(self):
        """ACTIVE + INFECTED → False."""
        f = File.objects.create(
            tenant=self.tenant, name=f"dl-{uuid.uuid4().hex[:8]}.csv",
            size=1, content_type="text/csv", status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.INFECTED, created_by=self.user,
        )
        self.assertFalse(f.can_download())

    def test_can_download_pending(self):
        """PENDING status → False regardless of scan."""
        f = File.objects.create(
            tenant=self.tenant, name=f"dl-{uuid.uuid4().hex[:8]}.csv",
            size=1, content_type="text/csv", status=FileStatus.PENDING,
            scan_status=FileScanStatus.CLEAN, created_by=self.user,
        )
        self.assertFalse(f.can_download())

    # ── is_uploading() ───────────────────────────────────────────

    def test_is_uploading_true(self):
        f = File.objects.create(
            tenant=self.tenant, name=f"up-{uuid.uuid4().hex[:8]}.csv",
            size=1, content_type="text/csv", status=FileStatus.UPLOADING,
            created_by=self.user,
        )
        self.assertTrue(f.is_uploading())

    def test_is_uploading_false(self):
        f = File.objects.create(
            tenant=self.tenant, name=f"up-{uuid.uuid4().hex[:8]}.csv",
            size=1, content_type="text/csv", status=FileStatus.ACTIVE,
            created_by=self.user,
        )
        self.assertFalse(f.is_uploading())

    # ── calculate_sha256() ───────────────────────────────────────

    def test_calculate_sha256_known_content(self):
        content = b"hello world"
        expected = (
            "b94d27b9934d3e08a52e52d7da7dabfa"
            "c484efe37a5380ee9088f7ace2efcde9"
        )
        result = File.calculate_sha256(BytesIO(content))
        self.assertEqual(result, expected)
        # Verify file pointer was reset
        self.assertEqual(BytesIO(content).read(), content)
