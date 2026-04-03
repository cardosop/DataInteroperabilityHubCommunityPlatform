"""
Unit tests for FileViewSet.

Comprehensive tests for FileViewSet endpoints without mocks/stubs.
Uses real S3StorageClient with graceful handling when storage unavailable.
"""
import uuid

import hashlib

import pytest
from django.test import override_settings
from rest_framework import status

from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.files.storage import S3StorageClient
from hub.apps.files.tests.test_base import FilesAPITestBase
from hub.apps.tenants.models import KYCStatus, Tenant

pytestmark = pytest.mark.django_db(transaction=True)


@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,
    RATE_LIMIT_ENABLED=False,
)
class FileViewSetTest(FilesAPITestBase):
    """Test FileViewSet with real implementations."""

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

    def test_list_files_success_returns_200(self):
        """Test listing files successfully returns 200 with results list."""
        response = self.client.get("/api/v1/files/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertIsInstance(response.data["results"], list)

    def test_list_files_tenant_isolation_excludes_other_tenant_files(self):
        """Test tenant isolation - users only see their tenant's files."""
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

        response = self.client.get("/api/v1/files/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        file_ids = [f["id"] for f in response.data["results"]]

        # Should only see files in own tenant
        self.assertIn(str(self.file.id), file_ids)
        self.assertNotIn(str(other_file.id), file_ids)

    def test_retrieve_file_success_returns_200(self):
        """Test retrieving file successfully returns 200 with correct data."""
        response = self.client.get(f"/api/v1/files/{self.file.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.file.id))
        self.assertEqual(response.data["name"], self.file.name)
        self.assertEqual(response.data["size"], self.file.size)

    def test_retrieve_file_not_found(self):
        """Test retrieving non-existent file returns 404."""
        import uuid

        non_existent_id = uuid.uuid4()
        response = self.client.get(f"/api/v1/files/{non_existent_id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_file_tenant_isolation(self):
        """Test tenant isolation - cannot retrieve other tenant's file."""
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

        response = self.client.get(f"/api/v1/files/{other_file.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_init_upload_success_simple_upload(self):
        """Test initializing simple file upload."""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        data = {
            "name": "test.csv",
            "content_type": "text/csv",
            "size": 1024,  # Small file, no multipart
            "upload_method": "browser",
        }

        response = self.client.post("/api/v1/files/init/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("file_id", response.data)
        self.assertIn("upload_url", response.data)
        self.assertEqual(response.data["requires_multipart"], False)

    def test_init_upload_success_multipart_upload(self):
        """Test initializing multipart file upload."""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        data = {
            "name": "large.csv",
            "content_type": "text/csv",
            "size": 150 * 1024 * 1024,  # Large file, requires multipart
            "upload_method": "sdk",
        }

        response = self.client.post("/api/v1/files/init/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("file_id", response.data)
        self.assertIn("upload_url", response.data)
        self.assertEqual(response.data["requires_multipart"], True)
        self.assertIn("chunk_size", response.data)
        self.assertIn("chunk_count", response.data)

    def test_init_upload_missing_required_fields(self):
        """Test initializing upload with missing fields returns 400."""
        data = {"name": "test.csv"}

        response = self.client.post("/api/v1/files/init/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Verify error references missing required fields
        self.assertIn("content_type", response.data)
        self.assertIn("size", response.data)

    def test_init_upload_invalid_upload_method(self):
        """Test initializing upload with invalid upload_method returns 400."""
        data = {
            "name": "test.csv",
            "content_type": "text/csv",
            "size": 1024,
            "upload_method": "invalid",
        }

        response = self.client.post("/api/v1/files/init/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Verify error references the invalid field
        self.assertIn("upload_method", response.data)

    def test_init_upload_unauthenticated(self):
        """Test initializing upload without authentication returns 401."""
        self.client.force_authenticate(user=None)
        data = {
            "name": "test.csv",
            "content_type": "text/csv",
            "size": 1024,
        }

        response = self.client.post("/api/v1/files/init/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_complete_upload_success(self):
        """Test completing file upload."""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        # Align storage_path with FileService / save_file(..., file_name=...)
        fid = uuid.uuid4()
        test_content = b"test,data\n1,2"
        pending_file = File.objects.create(
            id=fid,
            tenant=self.tenant,
            name="pending.csv",
            content_type="text/csv",
            size=len(test_content),
            status=FileStatus.PENDING,
            storage_path=f"{self.tenant.id}/{fid}/pending.csv",
            created_by=self.user,
        )

        # Upload test content to storage
        storage_client = S3StorageClient()
        from django.core.files.base import ContentFile

        storage_client.save_file(
            tenant_id=str(self.tenant.id),
            file_id=str(pending_file.id),
            file_content=ContentFile(test_content),
            file_name=pending_file.name,
        )

        content_sha256 = hashlib.sha256(test_content).hexdigest()
        data = {"content_sha256": content_sha256}

        response = self.client.post(
            f"/api/v1/files/{pending_file.id}/complete/", data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        pending_file.refresh_from_db()
        self.assertEqual(pending_file.status, FileStatus.ACTIVE)
        self.assertEqual(pending_file.content_sha256, content_sha256)

    def test_complete_upload_invalid_sha256_format(self):
        """Test completing upload with invalid SHA-256 format returns 400."""
        pending_file = File.objects.create(
            tenant=self.tenant,
            name="pending.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.PENDING,
            storage_path=f"{self.tenant.id}/pending.csv",
            created_by=self.user,
        )

        data = {"content_sha256": "invalid_hash"}

        response = self.client.post(
            f"/api/v1/files/{pending_file.id}/complete/", data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Verify error references the hash issue
        error_text = str(response.data).lower()
        self.assertTrue(
            "sha" in error_text or "hash" in error_text or "hex" in error_text,
            f"Expected error about invalid hash, got: {response.data}",
        )

    def test_complete_upload_file_not_found(self):
        """Test completing upload for non-existent file returns 404."""
        import uuid

        non_existent_id = uuid.uuid4()
        content_sha256 = hashlib.sha256(b"test").hexdigest()
        data = {"content_sha256": content_sha256}

        response = self.client.post(
            f"/api/v1/files/{non_existent_id}/complete/", data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_download_file_success(self):
        """Test downloading file successfully."""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        response = self.client.get(f"/api/v1/files/{self.file.id}/download/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("download_url", response.data)
        self.assertIn("expires_in", response.data)
        self.assertIn("filename", response.data)

    def test_download_file_not_active(self):
        """Test downloading non-active file returns 400."""
        pending_file = File.objects.create(
            tenant=self.tenant,
            name="pending.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.PENDING,
            storage_path=f"{self.tenant.id}/pending.csv",
            created_by=self.user,
        )

        response = self.client.get(f"/api/v1/files/{pending_file.id}/download/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_download_file_not_found(self):
        """Test downloading non-existent file returns 404."""
        import uuid

        non_existent_id = uuid.uuid4()
        response = self.client.get(f"/api/v1/files/{non_existent_id}/download/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_init_chunk_upload_success(self):
        """Test initializing chunk upload."""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        # Create file with multipart upload
        uploading_file = File.objects.create(
            tenant=self.tenant,
            name="large.csv",
            content_type="text/csv",
            size=150 * 1024 * 1024,
            status=FileStatus.UPLOADING,
            storage_path=f"{self.tenant.id}/large.csv",
            created_by=self.user,
            metadata_json={
                "multipart_upload_id": "test-upload-id",
                "chunk_size": 10 * 1024 * 1024,
                "chunk_count": 15,
            },
        )

        # Initiate multipart upload to get real upload_id
        storage_client = S3StorageClient()
        upload_id = storage_client.initiate_multipart_upload(
            key=uploading_file.storage_path,
            content_type="text/csv",
        )
        uploading_file.metadata_json["multipart_upload_id"] = upload_id
        uploading_file.save(update_fields=["metadata_json"])

        data = {"chunk_number": 1, "chunk_size": 10 * 1024 * 1024}

        response = self.client.post(
            f"/api/v1/files/{uploading_file.id}/chunks/init/", data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("upload_url", response.data)
        self.assertIn("expires_in", response.data)

        # Clean up
        try:
            storage_client.abort_multipart_upload(
                key=uploading_file.storage_path, upload_id=upload_id
            )
        except Exception:
            pass

    def test_init_chunk_upload_file_not_uploading(self):
        """Test initializing chunk upload for non-uploading file returns 400."""
        data = {"chunk_number": 1, "chunk_size": 5242880}

        response = self.client.post(
            f"/api/v1/files/{self.file.id}/chunks/init/", data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_init_chunk_upload_no_multipart_upload_id(self):
        """Test initializing chunk upload without multipart upload ID."""
        uploading_file = File.objects.create(
            tenant=self.tenant,
            name="uploading.csv",
            content_type="text/csv",
            size=150 * 1024 * 1024,
            status=FileStatus.UPLOADING,
            storage_path=f"{self.tenant.id}/uploading.csv",
            created_by=self.user,
            metadata_json={},  # No multipart_upload_id
        )

        data = {"chunk_number": 1, "chunk_size": 5242880}

        response = self.client.post(
            f"/api/v1/files/{uploading_file.id}/chunks/init/", data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_file_success(self):
        """Test deleting file successfully."""
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

        response = self.client.delete(f"/api/v1/files/{active_file.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        active_file.refresh_from_db()
        self.assertEqual(active_file.status, FileStatus.DELETED)

    def test_delete_file_not_found(self):
        """Test deleting non-existent file returns 404."""
        import uuid

        non_existent_id = uuid.uuid4()
        response = self.client.delete(f"/api/v1/files/{non_existent_id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_file_tenant_isolation(self):
        """Test tenant isolation - cannot delete other tenant's file."""
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

        response = self.client.delete(f"/api/v1/files/{other_file.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_file_success(self):
        """Test updating file."""
        data = {"name": "updated_name.csv"}

        response = self.client.patch(f"/api/v1/files/{self.file.id}/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.file.refresh_from_db()
        self.assertEqual(self.file.name, "updated_name.csv")

    def test_update_file_not_found(self):
        """Test updating non-existent file returns 404."""
        import uuid

        non_existent_id = uuid.uuid4()
        data = {"name": "updated.csv"}

        response = self.client.patch(f"/api/v1/files/{non_existent_id}/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_files_search_by_name(self):
        """Test searching files by name (29.69.2)."""
        File.objects.create(
            tenant=self.tenant,
            name="report-data.csv",
            content_type="text/csv",
            size=100,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=f"{self.tenant.id}/report-data.csv",
            created_by=self.user,
        )
        response = self.client.get("/api/v1/files/?search=report")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [f["name"] for f in response.data["results"]]
        self.assertIn("report-data.csv", names)

    def test_list_files_ordering(self):
        """Test ordering files returns results in correct order (29.69.2)."""
        # Create files with known names (self.file already exists from setUp)
        File.objects.create(
            tenant=self.tenant,
            name="alpha.csv",
            content_type="text/csv",
            size=100,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=f"{self.tenant.id}/alpha.csv",
            created_by=self.user,
        )
        File.objects.create(
            tenant=self.tenant,
            name="zulu.csv",
            content_type="text/csv",
            size=200,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=f"{self.tenant.id}/zulu.csv",
            created_by=self.user,
        )
        File.objects.create(
            tenant=self.tenant,
            name="mike.csv",
            content_type="text/csv",
            size=300,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=f"{self.tenant.id}/mike.csv",
            created_by=self.user,
        )

        # Test ascending name ordering
        response = self.client.get("/api/v1/files/?ordering=name")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [f["name"] for f in response.data["results"]]
        self.assertEqual(names, sorted(names))

        # Test descending name ordering
        response_desc = self.client.get("/api/v1/files/?ordering=-name")
        self.assertEqual(response_desc.status_code, status.HTTP_200_OK)
        names_desc = [f["name"] for f in response_desc.data["results"]]
        self.assertEqual(names_desc, sorted(names_desc, reverse=True))

    def test_list_files_filter_by_status(self):
        """Test filtering files by status."""
        # Create files with different statuses
        pending_file = File.objects.create(
            tenant=self.tenant,
            name="pending.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.PENDING,
            storage_path=f"{self.tenant.id}/pending.csv",
            created_by=self.user,
        )

        response = self.client.get("/api/v1/files/?status=ACTIVE")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        file_ids = [f["id"] for f in response.data["results"]]
        self.assertIn(str(self.file.id), file_ids)
        self.assertNotIn(str(pending_file.id), file_ids)

    def test_list_files_unauthenticated(self):
        """Test listing files without authentication returns 401."""
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/v1/files/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_retrieve_file_unauthenticated(self):
        """Test retrieving file without authentication returns 401."""
        self.client.force_authenticate(user=None)
        response = self.client.get(f"/api/v1/files/{self.file.id}/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
