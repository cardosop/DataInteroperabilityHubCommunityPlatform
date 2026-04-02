"""
Unit tests for FileService.

Tests use real FileService implementation without mocks/stubs.
"""
import uuid

import hashlib

import pytest
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings

from hub.apps.audit.models import AuditEvent
from hub.apps.core.services.base import NotFoundError, ValidationError
from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.files.services import FileService
from hub.apps.files.storage import S3StorageClient
from hub.apps.files.tests.test_base import FilesTestBase

pytestmark = pytest.mark.django_db(transaction=True)


class FileServiceTest(FilesTestBase):
    """Test FileService with real implementation."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.storage_available = False
        try:
            storage_client = S3StorageClient()
            storage_client._ensure_bucket_exists()
            self.storage_available = True
        except Exception:
            self.storage_available = False

    def test_get_file_success(self):
        """Test getting file by ID."""
        file_obj = self.service.get_file(file_id=str(self.file.id), tenant_id=str(self.tenant.id))

        self.assertIsNotNone(file_obj)
        self.assertEqual(file_obj.id, self.file.id)
        self.assertEqual(file_obj.tenant, self.tenant)

    def test_get_file_not_found(self):
        """Test getting non-existent file raises NotFoundError."""
        import uuid

        non_existent_id = str(uuid.uuid4())

        with self.assertRaises(NotFoundError):
            self.service.get_file(file_id=non_existent_id, tenant_id=str(self.tenant.id))

    def test_get_file_tenant_mismatch(self):
        """Test getting file from different tenant raises NotFoundError."""
        from hub.apps.tenants.models import KYCStatus, Tenant

        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}",
            slug=f"other-tenant-{_uid}",
            kyc_status=KYCStatus.VERIFIED,
        )

        with self.assertRaises(NotFoundError):
            self.service.get_file(file_id=str(self.file.id), tenant_id=str(other_tenant.id))

    def test_validate_file_active_success(self):
        """Test validating active file."""
        file_obj = self.service.validate_file_active(
            file_id=str(self.file.id), tenant_id=str(self.tenant.id)
        )

        self.assertIsNotNone(file_obj)
        self.assertEqual(file_obj.status, FileStatus.ACTIVE)

    def test_validate_file_active_not_active(self):
        """Test validating non-active file raises ValidationError."""
        inactive_file = File.objects.create(
            tenant=self.tenant,
            name="inactive.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.DELETED,
            storage_path=f"{self.tenant.id}/inactive.csv",
            created_by=self.user,
        )

        with self.assertRaises(ValidationError):
            self.service.validate_file_active(
                file_id=str(inactive_file.id), tenant_id=str(self.tenant.id)
            )

    def test_create_file_success(self):
        """Test creating file."""
        file_obj = self.service.create_file(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="new_file.csv",
            content_type="text/csv",
            size=2048,
            upload_method="browser",
            created_by_id=str(self.user.id),
        )

        self.assertIsNotNone(file_obj)
        self.assertEqual(file_obj.name, "new_file.csv")
        self.assertEqual(file_obj.size, 2048)
        self.assertEqual(file_obj.status, FileStatus.PENDING)
        self.assertEqual(file_obj.tenant, self.tenant)

    def test_create_file_invalid_size(self):
        """Test creating file with invalid size raises ValidationError."""
        # Assuming business rules reject files that are too large
        # This depends on tenant limits - test with extremely large size
        with self.assertRaises(ValidationError):
            self.service.create_file(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="huge_file.csv",
                content_type="text/csv",
                size=10**15,  # Extremely large
                upload_method="browser",
                created_by_id=str(self.user.id),
            )

    def test_update_file_success(self):
        """Test updating file."""
        pending_file = File.objects.create(
            tenant=self.tenant,
            name="pending.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.PENDING,
            storage_path=f"{self.tenant.id}/pending.csv",
            created_by=self.user,
        )

        content_sha256 = hashlib.sha256(b"test content").hexdigest()

        updated_file = self.service.update_file(
            file_id=str(pending_file.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            content_sha256=content_sha256,
            new_status=FileStatus.ACTIVE.value,
        )

        self.assertEqual(updated_file.content_sha256, content_sha256)
        self.assertEqual(updated_file.status, FileStatus.ACTIVE)

    def test_update_file_invalid_status_transition(self):
        """Test updating file with invalid status transition."""
        deleted_file = File.objects.create(
            tenant=self.tenant,
            name="deleted.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.DELETED,
            storage_path=f"{self.tenant.id}/deleted.csv",
            created_by=self.user,
        )

        # Try to reactivate deleted file (should fail business rules)
        with self.assertRaises(ValidationError):
            self.service.update_file(
                file_id=str(deleted_file.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                new_status=FileStatus.ACTIVE.value,
            )

    def test_delete_file_success(self):
        """Test deleting file."""
        active_file = File.objects.create(
            tenant=self.tenant,
            name="to_delete.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=f"{self.tenant.id}/to_delete.csv",
            created_by=self.user,
        )

        self.service.delete_file(
            file_id=str(active_file.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Refresh from DB
        active_file.refresh_from_db()
        self.assertEqual(active_file.status, FileStatus.DELETED)

    def test_delete_file_not_found(self):
        """Test deleting non-existent file raises NotFoundError."""
        import uuid

        non_existent_id = str(uuid.uuid4())

        with self.assertRaises(NotFoundError):
            self.service.delete_file(
                file_id=non_existent_id,
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
            )

    def test_create_file_without_user(self):
        """Test creating file without user."""
        file_obj = self.service.create_file(
            tenant_id=str(self.tenant.id),
            user_id=None,
            name="no_user.csv",
            content_type="text/csv",
            size=1024,
            upload_method="browser",
            created_by_id=None,
        )

        self.assertIsNotNone(file_obj)
        self.assertIsNone(file_obj.created_by)

    def test_get_file_without_tenant_id(self):
        """Test getting file uses service tenant_id when not provided."""
        # Service already has tenant_id from setUp
        file_obj = self.service.get_file(file_id=str(self.file.id))

        self.assertIsNotNone(file_obj)
        self.assertEqual(file_obj.id, self.file.id)

    def test_validate_file_active_without_tenant_id(self):
        """Test validating file uses service tenant_id when not provided."""
        file_obj = self.service.validate_file_active(file_id=str(self.file.id))

        self.assertIsNotNone(file_obj)
        self.assertEqual(file_obj.status, FileStatus.ACTIVE)

    @override_settings(
        CLAMAV_ENABLED=True,
        CLAMAV_HOST="127.0.0.1",
        CLAMAV_PORT=65444,
    )
    def test_update_file_completed_with_hash_triggers_scan_job(self):
        """COMPLETED + content_sha256 enqueues scan (same as ACTIVE); RQ runs inline in tests."""
        pending_file = File.objects.create(
            tenant=self.tenant,
            name="done.csv",
            content_type="text/csv",
            size=512,
            status=FileStatus.PENDING,
            storage_path=f"{self.tenant.id}/done.csv",
            created_by=self.user,
        )
        content_sha256 = hashlib.sha256(b"completed-path").hexdigest()
        with self.captureOnCommitCallbacks(execute=True):
            self.service.update_file(
                file_id=str(pending_file.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                content_sha256=content_sha256,
                new_status=FileStatus.COMPLETED.value,
            )
        pending_file.refresh_from_db()
        self.assertEqual(pending_file.status, FileStatus.COMPLETED)
        self.assertEqual(pending_file.scan_status, FileScanStatus.SCAN_UNAVAILABLE)

    @override_settings(CLAMAV_ENABLED=False)
    def test_update_file_active_when_clamav_disabled_sets_scan_unavailable(self):
        """CLAMAV_ENABLED=False skips queue and sets SCAN_UNAVAILABLE with audit."""
        pending_file = File.objects.create(
            tenant=self.tenant,
            name="clam-off.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.PENDING,
            storage_path=f"{self.tenant.id}/clam-off.csv",
            created_by=self.user,
        )
        content_sha256 = hashlib.sha256(b"payload").hexdigest()
        with self.captureOnCommitCallbacks(execute=True):
            updated = self.service.update_file(
                file_id=str(pending_file.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                content_sha256=content_sha256,
                new_status=FileStatus.ACTIVE.value,
            )
        updated.refresh_from_db()
        self.assertEqual(updated.scan_status, FileScanStatus.SCAN_UNAVAILABLE)
        self.assertIsNotNone(updated.scanned_at)
        self.assertTrue(
            AuditEvent.objects.filter(
                action="FILE_MALWARE_SCAN_SKIPPED",
                resource_id=updated.id,
            ).exists()
        )
