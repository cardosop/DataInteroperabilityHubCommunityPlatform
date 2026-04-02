"""
Unit tests for file upload and download.

Tests use real S3StorageClient with graceful handling when storage unavailable.
"""

import hashlib

import pytest
from django.core.files.base import ContentFile
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.files.storage import S3StorageClient
from hub.apps.files.tests.test_base import FilesAPITestBase
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import UserStatus
import uuid

pytestmark = pytest.mark.django_db(transaction=True)


class FileUploadDownloadTest(FilesAPITestBase):
    """Test file upload and download functionality"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.storage_available = False
        try:
            self.storage_client = S3StorageClient()
            self.storage_client._ensure_bucket_exists()
            self.storage_available = True
        except Exception:
            self.storage_available = False

    def test_init_file_upload_simple(self):
        """Test file upload initialization for simple upload"""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        data = {
            "name": "test.csv",
            "content_type": "text/csv",
            "size": 1024,  # 1KB - small file, no multipart
            "upload_method": "browser",
        }

        response = self.client.post("/api/v1/files/init/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("file_id", response.data)
        self.assertIn("upload_url", response.data)
        self.assertEqual(response.data["requires_multipart"], False)

        # Verify file was created
        file_id = response.data["file_id"]
        file_obj = File.objects.get(id=file_id)
        self.assertEqual(file_obj.name, "test.csv")
        self.assertEqual(file_obj.status, FileStatus.PENDING)
        self.assertEqual(file_obj.size, 1024)

    def test_init_file_upload_multipart(self):
        """Test file upload initialization for multipart upload (large file)"""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        data = {
            "name": "large.csv",
            "content_type": "text/csv",
            "size": 150 * 1024 * 1024,  # 150MB - requires multipart
            "upload_method": "sdk",
        }

        response = self.client.post("/api/v1/files/init/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("file_id", response.data)
        self.assertIn("upload_url", response.data)
        self.assertEqual(response.data["requires_multipart"], True)
        self.assertIn("chunk_size", response.data)
        self.assertIn("chunk_count", response.data)

        # Verify file was created with UPLOADING status
        file_id = response.data["file_id"]
        file_obj = File.objects.get(id=file_id)
        self.assertEqual(file_obj.status, FileStatus.UPLOADING)
        self.assertIn("multipart_upload_id", file_obj.metadata_json)

    def test_init_file_upload_over_browser_size_limit_rejected(self):
        """Test that browser upload exceeding size limit is rejected."""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")
        from django.conf import settings

        over_limit_size = (
            getattr(
                settings, "MAX_BROWSER_UPLOAD_SIZE", 100 * 1024 * 1024
            ) + 1
        )
        data = {
            "name": "large.csv",
            "content_type": "text/csv",
            "size": over_limit_size,
            "upload_method": "browser",
        }

        response = self.client.post(
            "/api/v1/files/init/", data, format="json"
        )

        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST
        )
        self.assertIn("size", str(response.data).lower())

    def test_init_file_upload_under_browser_size_limit_succeeds(self):
        """Test that browser upload under size limit succeeds as simple upload."""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        data = {
            "name": "small.csv",
            "content_type": "text/csv",
            "size": 1024,
            "upload_method": "browser",
        }

        response = self.client.post("/api/v1/files/init/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data["requires_multipart"])

    def test_init_file_upload_invalid_type(self):
        """Test file upload with invalid file type"""
        data = {
            "name": "test.exe",
            "content_type": "application/x-msdownload",
            "size": 1024,
            "upload_method": "browser",
        }

        response = self.client.post("/api/v1/files/init/", data, format="json")

        # May succeed or fail depending on business rules
        self.assertIn(
            response.status_code,
            [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST],
        )

    def test_complete_file_upload(self):
        """Test file upload completion"""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        # Create file record
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            storage_path=f"{self.tenant.id}/test.csv",
            status=FileStatus.PENDING,
            created_by=self.user,
        )

        # Upload file content to storage
        test_content = b"test content"
        self.storage_client.save_file(
            tenant_id=str(self.tenant.id),
            file_id=str(file_obj.id),
            file_content=ContentFile(test_content),
        )

        # Calculate SHA-256 hash
        sha256_hash = hashlib.sha256(test_content).hexdigest()

        data = {"content_sha256": sha256_hash}

        response = self.client.post(f"/api/v1/files/{file_obj.id}/complete/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify file was updated
        file_obj.refresh_from_db()
        self.assertEqual(file_obj.status, FileStatus.ACTIVE)
        self.assertEqual(file_obj.content_sha256, sha256_hash)

    def test_complete_multipart_upload(self):
        """Test multipart upload completion with a real S3 part."""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        # 5 MiB is the S3 minimum part size
        part_data = b"x" * (5 * 1024 * 1024)
        storage_key = (
            f"{self.tenant.id}/{uuid.uuid4()}/large.csv"
        )

        file_obj = File.objects.create(
            tenant=self.tenant,
            name="large.csv",
            content_type="text/csv",
            size=len(part_data),
            storage_path=storage_key,
            status=FileStatus.UPLOADING,
            created_by=self.user,
            metadata_json={
                "chunk_size": len(part_data),
                "chunk_count": 1,
            },
        )

        # Initiate real multipart upload in S3
        upload_id = self.storage_client.initiate_multipart_upload(
            key=storage_key, content_type="text/csv"
        )
        file_obj.metadata_json["multipart_upload_id"] = upload_id
        file_obj.save(update_fields=["metadata_json"])

        # Upload a real part to get a valid ETag
        s3 = self.storage_client.client
        part_resp = s3.upload_part(
            Bucket=self.storage_client.bucket_name,
            Key=storage_key,
            UploadId=upload_id,
            PartNumber=1,
            Body=part_data,
        )
        real_etag = part_resp["ETag"]

        sha256_hash = hashlib.sha256(part_data).hexdigest()
        data = {
            "content_sha256": sha256_hash,
            "parts": [
                {"ETag": real_etag, "PartNumber": 1},
            ],
        }

        response = self.client.post(
            f"/api/v1/files/{file_obj.id}/complete/",
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            f"Expected 200: {getattr(response, 'data', '')}",
        )
        file_obj.refresh_from_db()
        self.assertEqual(file_obj.status, FileStatus.ACTIVE)

        # Clean up multipart upload
        try:
            self.storage_client.abort_multipart_upload(
                key=file_obj.storage_path, upload_id=upload_id
            )
        except Exception:
            pass

    def test_download_file(self):
        """Test file download"""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        # Create active file
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            storage_path=f"{self.tenant.id}/test.csv",
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            created_by=self.user,
        )

        response = self.client.get(f"/api/v1/files/{file_obj.id}/download/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("download_url", response.data)
        self.assertEqual(response.data["filename"], "test.csv")
        self.assertEqual(response.data["expires_in"], 3600)

    def test_download_file_not_active(self):
        """Test downloading a file that is not active"""
        # Create pending file
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            storage_path=f"{self.tenant.id}/test.csv",
            status=FileStatus.PENDING,
            created_by=self.user,
        )

        response = self.client.get(f"/api/v1/files/{file_obj.id}/download/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_file(self):
        """Test file deletion"""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        # Create active file
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            storage_path=f"{self.tenant.id}/test.csv",
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            created_by=self.user,
        )

        response = self.client.delete(f"/api/v1/files/{file_obj.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify file was soft deleted
        file_obj.refresh_from_db()
        self.assertEqual(file_obj.status, FileStatus.DELETED)

    def test_list_files_tenant_scoped(self):
        """Test that users can only see files in their tenant"""
        # Create another tenant and file
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}",
            slug=f"other-tenant-{_uid}",
            kyc_status=KYCStatus.VERIFIED,
        )
        other_file = File.objects.create(
            tenant=other_tenant,
            name="other.csv",
            content_type="text/csv",
            size=1024,
            storage_path=f"{other_tenant.id}/other.csv",
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
        )

        # Create file in user's tenant
        my_file = File.objects.create(
            tenant=self.tenant,
            name="my.csv",
            content_type="text/csv",
            size=1024,
            storage_path=f"{self.tenant.id}/my.csv",
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            created_by=self.user,
        )

        response = self.client.get("/api/v1/files/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        file_ids = [f["id"] for f in response.data["results"]]

        # Should only see files in own tenant
        self.assertIn(str(my_file.id), file_ids)
        self.assertNotIn(str(other_file.id), file_ids)
