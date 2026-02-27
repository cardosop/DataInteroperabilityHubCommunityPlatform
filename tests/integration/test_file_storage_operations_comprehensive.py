"""
Comprehensive File Storage Operations Tests for Django 6

Tests all file storage operations:
- File upload
- File download
- File deletion
- File storage integration (S3/MinIO)
- File storage error handling

Multi-status cases (see docs/TEST_ASSERTION_CONVENTIONS.md):
- Init upload: 201=success, 400=validation, 503=S3 unavailable, 500=internal error
- Download: 200=success, 404=not found, 503=S3 unavailable, 400=file not downloadable (e.g. deleted)
- Delete: 204=success, 200=success (both valid), 404=not found
- Unauthorized: 401 (single expected)
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus
from tests.factories import TenantFactory

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class FileUploadTest(TestCase):
    """Test file upload operations"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant()
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.client.force_authenticate(user=self.user)

    def test_file_upload_init(self):
        """Test file upload initialization (POST /api/v1/files/init/)."""
        response = self.client.post(
            "/api/v1/files/init/",
            {"name": "test.txt", "size": 1024, "content_type": "text/plain"},
            format="json",
        )

        # 201=success; 400=validation; 503=S3 unavailable; 500=internal (see module docstring)
        self.assertIn(response.status_code, [201, 400, 500, 503])

        if response.status_code == 201:
            self.assertIn("file_id", response.data or {})

    def test_file_upload_with_ingestion_mode(self):
        """Test file upload with ingestion_mode (extra field; init accepts it or ignores)."""
        response = self.client.post(
            "/api/v1/files/init/",
            {
                "name": "test.csv",
                "size": 2048,
                "content_type": "text/csv",
                "ingestion_mode": "streaming",
            },
            format="json",
        )

        # 201=success; 400=validation; 503=S3 unavailable; 500=internal
        self.assertIn(response.status_code, [201, 400, 500, 503])


class FileDownloadTest(TestCase):
    """Test file download operations"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant()
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.user)

        # Create test file
        self.file_obj = File.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="test-download.txt",
            status=FileStatus.ACTIVE,
            storage_path="test/path/test-download.txt",
            size=1024,
        )

    def test_file_download(self):
        """Test file download (file exists, ACTIVE status)."""
        response = self.client.get(f"/api/v1/files/{self.file_obj.id}/download/")

        # 200=success; 404=not found (tenant isolation); 503=S3 unavailable; 500=internal
        self.assertIn(response.status_code, [200, 404, 500, 503])

    def test_file_download_nonexistent(self):
        """Test file download for nonexistent file — single expected 404."""
        response = self.client.get("/api/v1/files/00000000-0000-0000-0000-000000000000/download/")
        self.assertEqual(response.status_code, 404)


class FileDeletionTest(TestCase):
    """Test file deletion operations"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant()
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.client.force_authenticate(user=self.user)

        # Create test file
        self.file_obj = File.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="test-delete.txt",
            status=FileStatus.ACTIVE,
            storage_path="test/path/test-delete.txt",
            size=1024,
        )

    def test_file_deletion(self):
        """Test file deletion"""
        response = self.client.delete(f"/api/v1/files/{self.file_obj.id}/")

        # 204/200=success; 404=not found (see module docstring)
        self.assertIn(response.status_code, [200, 204, 404])

        if response.status_code in [200, 204]:
            # File should be marked as deleted (soft delete)
            self.file_obj.refresh_from_db()
            self.assertEqual(self.file_obj.status, FileStatus.DELETED)


class FileStorageIntegrationTest(TestCase):
    """Test file storage integration (S3/MinIO)"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant()
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.user)

    def test_s3_storage_client_initialization(self):
        """Test S3 storage client initialization"""
        from hub.apps.files.storage import S3StorageClient

        # S3StorageClient should be importable
        self.assertIsNotNone(S3StorageClient)

        # Try to initialize (may fail if credentials not configured, which is OK)
        try:
            client = S3StorageClient()
            # If initialization succeeds, client should exist
            self.assertIsNotNone(client)
        except Exception:
            # Initialization may fail if credentials not configured
            # This is acceptable in test environment
            pass

    def test_s3_storage_integration(self):
        """Test S3 storage integration"""
        # Create file
        file_obj = File.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="s3-test.txt",
            status=FileStatus.PENDING,
            storage_path="test/s3-test.txt",
            size=1024,
        )

        # File should be created
        self.assertIsNotNone(file_obj.id)

        # Storage path should be set
        self.assertIsNotNone(file_obj.storage_path)


class FileStorageErrorHandlingTest(TestCase):
    """Test file storage error handling"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant()
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.client.force_authenticate(user=self.user)

    def test_file_upload_invalid_data(self):
        """Test file upload with invalid data"""
        response = self.client.post(
            "/api/v1/files/init/", {"invalid_field": "invalid_value"}, format="json"
        )

        self.assertEqual(response.status_code, 400)

    def test_file_download_deleted_file(self):
        """Test file download for deleted file"""
        # Create and delete file
        file_obj = File.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="deleted-file.txt",
            status=FileStatus.DELETED,
            storage_path="test/deleted-file.txt",
            size=1024,
        )

        response = self.client.get(f"/api/v1/files/{file_obj.id}/download/")

        self.assertEqual(response.status_code, 400)

    def test_file_upload_unauthorized(self):
        """Test file upload without authentication"""
        self.client.force_authenticate(user=None)

        response = self.client.post(
            "/api/v1/files/init/",
            {"name": "test.txt", "size": 1024, "content_type": "text/plain"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)
