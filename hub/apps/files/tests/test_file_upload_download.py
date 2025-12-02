"""
Unit tests for file upload and download.
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import Mock, patch, MagicMock
import hashlib
import io

from hub.apps.files.models import File, FileStatus
from hub.apps.users.models import UserStatus
from hub.apps.tenants.models import Tenant


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class FileUploadDownloadTest(TestCase):
    """Test file upload and download functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        
        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        
        # Create user
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
    
    @patch('hub.apps.files.views.S3StorageClient')
    def test_init_file_upload_simple(self, mock_storage_client_class):
        """Test file upload initialization for simple upload"""
        self.client.force_authenticate(user=self.user)
        
        # Mock storage client
        mock_storage_client = MagicMock()
        mock_storage_client_class.return_value = mock_storage_client
        mock_storage_client.generate_presigned_upload_url.return_value = {
            'upload_url': 'https://s3.example.com/upload',
            'fields': {'key': 'value'},
            'key': 'test/path/file.csv'
        }
        
        data = {
            "name": "test.csv",
            "content_type": "text/csv",
            "size": 1024,  # 1KB - small file, no multipart
            "upload_method": "browser"
        }
        
        response = self.client.post("/api/v1/files/files/init/", data, format="json")
        
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
    
    @patch('hub.apps.files.views.S3StorageClient')
    def test_init_file_upload_multipart(self, mock_storage_client_class):
        """Test file upload initialization for multipart upload (large file)"""
        self.client.force_authenticate(user=self.user)
        
        # Mock storage client
        mock_storage_client = MagicMock()
        mock_storage_client_class.return_value = mock_storage_client
        mock_storage_client.initiate_multipart_upload.return_value = "upload-id-123"
        mock_storage_client.generate_presigned_part_url.return_value = "https://s3.example.com/upload/part/1"
        
        data = {
            "name": "large.csv",
            "content_type": "text/csv",
            "size": 150 * 1024 * 1024,  # 150MB - requires multipart
            "upload_method": "sdk"
        }
        
        response = self.client.post("/api/v1/files/files/init/", data, format="json")
        
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
    
    def test_init_file_upload_size_limit_browser(self):
        """Test file upload size limit for browser uploads"""
        self.client.force_authenticate(user=self.user)
        
        from django.conf import settings
        
        # Try to upload file exceeding browser limit
        data = {
            "name": "large.csv",
            "content_type": "text/csv",
            "size": settings.MAX_BROWSER_UPLOAD_SIZE + 1,  # Exceeds limit
            "upload_method": "browser"
        }
        
        response = self.client.post("/api/v1/files/files/init/", data, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("size", response.data)
    
    def test_init_file_upload_invalid_type(self):
        """Test file upload with invalid file type"""
        self.client.force_authenticate(user=self.user)
        
        data = {
            "name": "test.exe",
            "content_type": "application/x-msdownload",
            "size": 1024,
            "upload_method": "browser"
        }
        
        response = self.client.post("/api/v1/files/files/init/", data, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("type", str(response.data).lower())
    
    @patch('hub.apps.files.views.S3StorageClient')
    def test_complete_file_upload(self, mock_storage_client_class):
        """Test file upload completion"""
        self.client.force_authenticate(user=self.user)
        
        # Create file record
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            storage_path="test/path/file.csv",
            status=FileStatus.PENDING,
            created_by=self.user
        )
        
        # Mock storage client
        mock_storage_client = MagicMock()
        mock_storage_client_class.return_value = mock_storage_client
        mock_storage_client.file_exists.return_value = True
        mock_storage_client.get_file_size.return_value = 1024
        
        # Calculate SHA-256 hash
        test_content = b"test content"
        sha256_hash = hashlib.sha256(test_content).hexdigest()
        
        data = {
            "content_sha256": sha256_hash
        }
        
        response = self.client.post(f"/api/v1/files/files/{file_obj.id}/complete/", data, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify file was updated
        file_obj.refresh_from_db()
        self.assertEqual(file_obj.status, FileStatus.ACTIVE)
        self.assertEqual(file_obj.content_sha256, sha256_hash)
    
    @patch('hub.apps.files.views.S3StorageClient')
    def test_complete_multipart_upload(self, mock_storage_client_class):
        """Test multipart upload completion"""
        self.client.force_authenticate(user=self.user)
        
        # Create file record with multipart upload
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="large.csv",
            content_type="text/csv",
            size=150 * 1024 * 1024,
            storage_path="test/path/large.csv",
            status=FileStatus.UPLOADING,
            created_by=self.user,
            metadata_json={
                'multipart_upload_id': 'upload-id-123',
                'chunk_size': 5 * 1024 * 1024,
                'chunk_count': 30
            }
        )
        
        # Mock storage client
        mock_storage_client = MagicMock()
        mock_storage_client_class.return_value = mock_storage_client
        mock_storage_client.file_exists.return_value = True
        mock_storage_client.get_file_size.return_value = 150 * 1024 * 1024
        mock_storage_client.complete_multipart_upload.return_value = {'ETag': 'final-etag'}
        
        sha256_hash = hashlib.sha256(b"test").hexdigest()
        parts = [
            {"ETag": "etag1", "PartNumber": 1},
            {"ETag": "etag2", "PartNumber": 2}
        ]
        
        data = {
            "content_sha256": sha256_hash,
            "parts": parts
        }
        
        response = self.client.post(f"/api/v1/files/files/{file_obj.id}/complete/", data, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify multipart upload was completed
        mock_storage_client.complete_multipart_upload.assert_called_once()
        
        # Verify file was updated
        file_obj.refresh_from_db()
        self.assertEqual(file_obj.status, FileStatus.ACTIVE)
    
    @patch('hub.apps.files.views.S3StorageClient')
    def test_download_file(self, mock_storage_client_class):
        """Test file download"""
        self.client.force_authenticate(user=self.user)
        
        # Create active file
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            storage_path="test/path/file.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user
        )
        
        # Mock storage client
        mock_storage_client = MagicMock()
        mock_storage_client_class.return_value = mock_storage_client
        mock_storage_client.generate_presigned_download_url.return_value = "https://s3.example.com/download"
        
        response = self.client.get(f"/api/v1/files/files/{file_obj.id}/download/")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("download_url", response.data)
        self.assertEqual(response.data["filename"], "test.csv")
        self.assertEqual(response.data["expires_in"], 3600)
    
    def test_download_file_not_active(self):
        """Test downloading a file that is not active"""
        self.client.force_authenticate(user=self.user)
        
        # Create pending file
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            storage_path="test/path/file.csv",
            status=FileStatus.PENDING,
            created_by=self.user
        )
        
        response = self.client.get(f"/api/v1/files/files/{file_obj.id}/download/")
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    @patch('hub.apps.files.views.S3StorageClient')
    def test_delete_file(self, mock_storage_client_class):
        """Test file deletion"""
        self.client.force_authenticate(user=self.user)
        
        # Create active file
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            storage_path="test/path/file.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user
        )
        
        # Mock storage client
        mock_storage_client = MagicMock()
        mock_storage_client_class.return_value = mock_storage_client
        
        response = self.client.delete(f"/api/v1/files/files/{file_obj.id}/")
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify file was soft deleted
        file_obj.refresh_from_db()
        self.assertEqual(file_obj.status, FileStatus.DELETED)
        
        # Verify delete was called on storage
        mock_storage_client.delete_file.assert_called_once_with(file_obj.storage_path)
    
    def test_list_files_tenant_scoped(self):
        """Test that users can only see files in their tenant"""
        self.client.force_authenticate(user=self.user)
        
        # Create another tenant and file
        other_tenant = Tenant.objects.create(
            name="Other Tenant",
            slug="other-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        other_file = File.objects.create(
            tenant=other_tenant,
            name="other.csv",
            content_type="text/csv",
            size=1024,
            storage_path="other/path/file.csv",
            status=FileStatus.ACTIVE
        )
        
        # Create file in user's tenant
        my_file = File.objects.create(
            tenant=self.tenant,
            name="my.csv",
            content_type="text/csv",
            size=1024,
            storage_path="my/path/file.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user
        )
        
        response = self.client.get("/api/v1/files/files/")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        file_ids = [f["id"] for f in response.data["results"]]
        
        # Should only see files in own tenant
        self.assertIn(str(my_file.id), file_ids)
        self.assertNotIn(str(other_file.id), file_ids)

