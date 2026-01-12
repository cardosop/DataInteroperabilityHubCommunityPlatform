"""
Integration tests for TenantConfig with File Upload.

GAP-1.2.3: Tests for file upload integration with tenant configuration.
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock

from hub.apps.tenants.models import Tenant, TenantConfig
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.services import get_tenant_file_size_limit
from hub.apps.tenants.validators import get_platform_defaults


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class TenantConfigFileUploadIntegrationTest(TestCase):
    """Test File Upload integration with tenant configuration"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        
        self.platform_defaults = get_platform_defaults()
    
    def test_file_upload_within_tenant_limit(self):
        """Test file upload succeeds when file size is within tenant limit"""
        # Create tenant config with custom file size limit (5 GB)
        TenantConfig.objects.create(
            tenant=self.tenant,
            max_file_size_bytes=5 * 1024 * 1024 * 1024  # 5 GB
        )
        
        self.client.force_authenticate(user=self.user)
        
        # Mock storage client
        with patch('hub.apps.files.views.S3StorageClient') as mock_storage_class:
            mock_storage = MagicMock()
            mock_storage_class.return_value = mock_storage
            # For large files (>100MB), multipart upload is used
            mock_storage.initiate_multipart_upload.return_value = "multipart-upload-id-123"
            mock_storage.generate_presigned_part_url.return_value = "https://s3.example.com/upload/part1"
            mock_storage.generate_presigned_upload_url.return_value = {
                'upload_url': 'https://s3.example.com/upload',
                'fields': {}
            }
            
            # Try to upload file within tenant limit (4 GB)
            file_size = 4 * 1024 * 1024 * 1024
            # URL pattern: /api/v1/files/ includes router that registers "files", so full path is /api/v1/files/init/
            response = self.client.post("/api/v1/files/init/", {
                "name": "test.csv",
                "content_type": "text/csv",
                "size": file_size,
                "upload_method": "sdk"
            }, format="json")
            
            # Should succeed (201 for file creation)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_file_upload_exceeding_tenant_limit(self):
        """Test file upload fails when file size exceeds tenant limit"""
        # Create tenant config with custom file size limit (5 GB)
        TenantConfig.objects.create(
            tenant=self.tenant,
            max_file_size_bytes=5 * 1024 * 1024 * 1024  # 5 GB
        )
        
        self.client.force_authenticate(user=self.user)
        
        # Try to upload file exceeding tenant limit (6 GB)
        file_size = 6 * 1024 * 1024 * 1024
        response = self.client.post("/api/v1/files/init/", {
            "name": "test.csv",
            "content_type": "text/csv",
            "size": file_size,
            "upload_method": "sdk"
        }, format="json")
        
        # Should return validation error
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("exceeds", str(response.data["error"]).lower())
    
    def test_file_upload_with_platform_default(self):
        """Test file upload uses platform default when tenant config not set"""
        # No tenant config exists
        
        self.client.force_authenticate(user=self.user)
        
        # Mock storage client
        with patch('hub.apps.files.views.S3StorageClient') as mock_storage_class:
            mock_storage = MagicMock()
            mock_storage_class.return_value = mock_storage
            mock_storage.generate_presigned_upload_url.return_value = {
                'upload_url': 'https://s3.example.com/upload',
                'fields': {}
            }
            
            # Try to upload file within platform default limit (10 GB)
            # Use a file size that's within browser method limit (100MB) but still tests platform default
            # Browser method has a 100MB limit, so use 50MB to test platform default logic
            file_size = 50 * 1024 * 1024  # 50MB - within browser limit, tests platform default
            response = self.client.post("/api/v1/files/init/", {
                "name": "test.csv",
                "content_type": "text/csv",
                "size": file_size,
                "upload_method": "browser"
            }, format="json")
            
            # Should succeed (uses platform default, within browser method limit)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_chunked_upload_validates_total_file_size(self):
        """Test chunked upload validates total file size across chunks"""
        # Create tenant config with custom file size limit (5 GB)
        TenantConfig.objects.create(
            tenant=self.tenant,
            max_file_size_bytes=5 * 1024 * 1024 * 1024  # 5 GB
        )
        
        self.client.force_authenticate(user=self.user)
        
        # Create file record with size exceeding tenant limit
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="large_file.csv",
            content_type="text/csv",
            size=6 * 1024 * 1024 * 1024,  # 6 GB (exceeds tenant limit)
            storage_path=f"{self.tenant.id}/file_id/large_file.csv",
            status=FileStatus.UPLOADING,
            created_by=self.user,
            metadata_json={
                'multipart_upload_id': 'upload-123',
                'chunk_size': 100 * 1024 * 1024,  # 100 MB chunks
                'chunk_count': 60
            }
        )
        
        # Mock storage client
        with patch('hub.apps.files.views.S3StorageClient') as mock_storage_class:
            mock_storage = MagicMock()
            mock_storage_class.return_value = mock_storage
            mock_storage.get_file_size.return_value = 6 * 1024 * 1024 * 1024
            mock_storage.file_exists.return_value = True
            
            # Try to complete upload
            response = self.client.post(f"/api/v1/files/{file_obj.id}/complete/", {
                "content_sha256": "abc123",
                "parts": [{"ETag": "etag1", "PartNumber": 1}]
            }, format="json")
            
            # Should return validation error (file size exceeds tenant limit)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("error", response.data)
            self.assertIn("exceeds tenant limit", str(response.data["error"]))
    
    def test_get_tenant_file_size_limit_utility_function(self):
        """Test get_tenant_file_size_limit utility function"""
        # Test with tenant config
        TenantConfig.objects.create(
            tenant=self.tenant,
            max_file_size_bytes=5 * 1024 * 1024 * 1024  # 5 GB
        )
        
        limit = get_tenant_file_size_limit(str(self.tenant.id))
        self.assertEqual(limit, 5 * 1024 * 1024 * 1024)
        
        # Test without tenant config (platform default)
        tenant2 = Tenant.objects.create(name="Test Tenant 2", slug="test-tenant-2")
        limit = get_tenant_file_size_limit(str(tenant2.id))
        self.assertEqual(limit, self.platform_defaults["max_file_size_bytes"])

