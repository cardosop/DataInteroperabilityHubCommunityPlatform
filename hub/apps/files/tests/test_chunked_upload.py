"""
Unit tests for chunked/multipart upload functionality.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock

from hub.apps.files.models import File, FileStatus
from hub.apps.users.models import UserStatus
from hub.apps.tenants.models import Tenant
from hub.apps.files.validators import get_chunk_size, calculate_chunk_count

User = get_user_model()


class ChunkedUploadTest(TestCase):
    """Test chunked upload functionality"""
    
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
    
    def test_get_chunk_size_small_file(self):
        """Test chunk size calculation for small files"""
        # File < 100MB should use 5MB chunks
        chunk_size = get_chunk_size(50 * 1024 * 1024)  # 50MB
        self.assertEqual(chunk_size, 5 * 1024 * 1024)  # 5MB
    
    def test_get_chunk_size_medium_file(self):
        """Test chunk size calculation for medium files"""
        # File 100MB - 1GB should use 10MB chunks
        chunk_size = get_chunk_size(500 * 1024 * 1024)  # 500MB
        self.assertEqual(chunk_size, 10 * 1024 * 1024)  # 10MB
    
    def test_get_chunk_size_large_file(self):
        """Test chunk size calculation for large files"""
        # File 1GB - 5GB should use 50MB chunks
        chunk_size = get_chunk_size(2 * 1024 * 1024 * 1024)  # 2GB
        self.assertEqual(chunk_size, 50 * 1024 * 1024)  # 50MB
    
    def test_get_chunk_size_very_large_file(self):
        """Test chunk size calculation for very large files"""
        # File > 5GB should use 100MB chunks
        chunk_size = get_chunk_size(10 * 1024 * 1024 * 1024)  # 10GB
        self.assertEqual(chunk_size, 100 * 1024 * 1024)  # 100MB
    
    def test_calculate_chunk_count(self):
        """Test chunk count calculation"""
        file_size = 150 * 1024 * 1024  # 150MB
        chunk_size = 10 * 1024 * 1024  # 10MB
        
        chunk_count = calculate_chunk_count(file_size, chunk_size)
        
        # 150MB / 10MB = 15 chunks
        self.assertEqual(chunk_count, 15)
    
    @patch('hub.apps.files.views.S3StorageClient')
    def test_init_chunk_upload(self, mock_storage_client_class):
        """Test chunk upload initialization"""
        self.client.force_authenticate(user=self.user)
        
        # Create file with multipart upload
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
                'chunk_size': 10 * 1024 * 1024,
                'chunk_count': 15
            }
        )
        
        # Mock storage client
        mock_storage_client = MagicMock()
        mock_storage_client_class.return_value = mock_storage_client
        mock_storage_client.generate_presigned_part_url.return_value = "https://s3.example.com/upload/part/5"
        
        data = {
            "chunk_number": 5,
            "chunk_size": 10 * 1024 * 1024
        }
        
        response = self.client.post(f"/api/v1/files/files/{file_obj.id}/chunks/init/", data, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("upload_url", response.data)
        self.assertEqual(response.data["expires_in"], 3600)
        
        # Verify correct part number was used
        mock_storage_client.generate_presigned_part_url.assert_called_once_with(
            key=file_obj.storage_path,
            upload_id='upload-id-123',
            part_number=5,
            expires_in=3600
        )
    
    def test_init_chunk_upload_not_uploading(self):
        """Test chunk upload initialization for non-uploading file"""
        self.client.force_authenticate(user=self.user)
        
        # Create file in PENDING state
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            storage_path="test/path/file.csv",
            status=FileStatus.PENDING,
            created_by=self.user
        )
        
        data = {
            "chunk_number": 1,
            "chunk_size": 1024
        }
        
        response = self.client.post(f"/api/v1/files/files/{file_obj.id}/chunks/init/", data, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    @patch('hub.apps.files.views.S3StorageClient')
    def test_complete_multipart_upload_with_parts(self, mock_storage_client_class):
        """Test completing multipart upload with parts"""
        self.client.force_authenticate(user=self.user)
        
        # Create file with multipart upload
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
                'chunk_size': 10 * 1024 * 1024,
                'chunk_count': 15
            }
        )
        
        # Mock storage client
        mock_storage_client = MagicMock()
        mock_storage_client_class.return_value = mock_storage_client
        mock_storage_client.file_exists.return_value = True
        mock_storage_client.get_file_size.return_value = 150 * 1024 * 1024
        mock_storage_client.complete_multipart_upload.return_value = {'ETag': 'final-etag'}
        
        import hashlib
        sha256_hash = hashlib.sha256(b"test").hexdigest()
        
        parts = [
            {"ETag": "etag1", "PartNumber": 1},
            {"ETag": "etag2", "PartNumber": 2},
            {"ETag": "etag3", "PartNumber": 3}
        ]
        
        data = {
            "content_sha256": sha256_hash,
            "parts": parts
        }
        
        response = self.client.post(f"/api/v1/files/files/{file_obj.id}/complete/", data, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify complete_multipart_upload was called with correct parts
        mock_storage_client.complete_multipart_upload.assert_called_once_with(
            key=file_obj.storage_path,
            upload_id='upload-id-123',
            parts=parts
        )
        
        # Verify file was activated
        file_obj.refresh_from_db()
        self.assertEqual(file_obj.status, FileStatus.ACTIVE)

