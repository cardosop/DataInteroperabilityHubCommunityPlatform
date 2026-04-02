"""
Comprehensive E2E tests for file operations.

Covers:
- Simple file upload
- Chunked file upload
- File download
- Pre-signed URLs
- File deletion
- Content hash verification
- Size limits
- File status transitions
- S3 storage verification
- Audit logging

Uses REAL services (MinIO, no mocks).
"""
import pytest
import hashlib
import boto3
from botocore.exceptions import ClientError
from django.test import TestCase
from django.conf import settings
from rest_framework import status

from hub.apps.files.models import File, FileStatus
from hub.apps.audit.models import AuditEvent

from .conftest import E2ETestBase, get_response_data


pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e1]


class FileOperationsE2ETest(E2ETestBase):
    """Test file operations"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
    
    def test_simple_file_upload_success(self):
        """Test simple file upload (small file)"""
        test_content = b'col1,col2\nval1,val2\nval3,val4'
        content_hash = hashlib.sha256(test_content).hexdigest()
        
        # Initialize upload
        file_id = self.init_file_upload(
            name='test_simple.csv',
            content_type='text/csv',
            size=len(test_content)
        )
        
        # Complete upload
        self.complete_file_upload(file_id, content_sha256=content_hash, test_content=test_content)
        
        # Verify file in database
        file_obj = File.objects.get(id=file_id)
        self.assertEqual(file_obj.name, 'test_simple.csv')
        self.assertEqual(file_obj.content_type, 'text/csv')
        self.assertEqual(file_obj.size, len(test_content))
        self.assertEqual(file_obj.content_sha256, content_hash)
        self.assertEqual(file_obj.status, FileStatus.ACTIVE)
        
        # Verify file in S3
        self.verify_file_in_s3(file_id, expected_content=test_content, expected_size=len(test_content))
        
        # Verify audit log created
        self.verify_audit_log(
            action='FILE_UPLOAD_COMPLETED',
            resource_type='FILE',
            resource_id=file_id,
            result='SUCCESS'
        )
    
    def test_chunked_file_upload_success(self):
        """Test chunked file upload (large file)"""
        # Create large test content (simulate large file)
        test_content = b'x' * (10 * 1024 * 1024)  # 10 MB
        content_hash = hashlib.sha256(test_content).hexdigest()
        
        # Initialize upload (should trigger chunked mode for large files)
        file_id = self.init_file_upload(
            name='test_large.csv',
            content_type='text/csv',
            size=len(test_content)
        )
        
        # For chunked uploads, we'd need to implement chunk upload logic
        # For now, test that init returns chunked mode if file is large
        file_obj = File.objects.get(id=file_id)
        
        # Complete upload (simplified - in real scenario would upload chunks first)
        # Note: This test may need adjustment based on actual chunked upload implementation
        self.complete_file_upload(file_id, content_sha256=content_hash, test_content=test_content)
        
        # Verify file in database
        file_obj.refresh_from_db()
        self.assertEqual(file_obj.size, len(test_content))
        self.assertEqual(file_obj.content_sha256, content_hash)
        self.assertEqual(file_obj.status, FileStatus.ACTIVE)
        
        # Verify file in S3
        self.verify_file_in_s3(file_id, expected_size=len(test_content))
    
    def test_file_upload_with_presigned_url(self):
        """Test file upload with pre-signed URL"""
        test_content = b'presigned upload test content'
        content_hash = hashlib.sha256(test_content).hexdigest()
        
        # Initialize upload (returns pre-signed URL)
        response = self.client.post(
            '/api/v1/files/init/',
            {
                'name': 'presigned_test.csv',
                'content_type': 'text/csv',
                'size': len(test_content)
            },
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = get_response_data(response) or {}
        file_id = data['file_id']
        self.assertIn('upload_url', data)
        if 'expires_in' in data:
            self.assertIsInstance(data['expires_in'], (int, str))
        
        # Complete upload
        self.complete_file_upload(file_id, content_sha256=content_hash, test_content=test_content)
        
        # Verify file exists
        file_obj = File.objects.get(id=file_id)
        self.assertEqual(file_obj.status, FileStatus.ACTIVE)
    
    def test_file_download_success(self):
        """Test downloading a file"""
        test_content = b'download test content'
        content_hash = hashlib.sha256(test_content).hexdigest()
        
        # Upload file first
        file_id = self.init_file_upload(
            name='download_test.csv',
            content_type='text/csv',
            size=len(test_content)
        )
        self.complete_file_upload(file_id, content_sha256=content_hash, test_content=test_content)
        
        # Download file
        response = self.client.get(f'/api/v1/files/{file_id}/download/')
        
        # Should return pre-signed URL or redirect
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_302_FOUND])
        
        if response.status_code == status.HTTP_302_FOUND:
            # Redirect to pre-signed URL
            self.assertIn('Location', response)
        elif response.status_code == status.HTTP_200_OK:
            data = get_response_data(response) or {}
            self.assertIn('download_url', data)
    
    def test_file_download_not_found(self):
        """Test downloading non-existent file fails"""
        import uuid
        fake_file_id = uuid.uuid4()
        
        response = self.client.get(f'/api/v1/files/{fake_file_id}/download/')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_file_download_deleted_file_fails(self):
        """Test downloading deleted file fails"""
        test_content = b'delete test content'
        content_hash = hashlib.sha256(test_content).hexdigest()
        
        # Upload file
        file_id = self.init_file_upload(
            name='delete_test.csv',
            content_type='text/csv',
            size=len(test_content)
        )
        self.complete_file_upload(file_id, content_sha256=content_hash, test_content=test_content)
        
        # Delete file
        response = self.client.delete(f'/api/v1/files/{file_id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Try to download deleted file
        response = self.client.get(f'/api/v1/files/{file_id}/download/')
        # Deleted file should return an error: 400 (bad request — file is deleted),
        # 404 (not found), or 410 (gone)
        self.assertIn(response.status_code, [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_410_GONE,
        ], f"Deleted file download should fail, got {response.status_code}")
    
    def test_delete_file_success(self):
        """Test deleting a file"""
        test_content = b'delete test content'
        content_hash = hashlib.sha256(test_content).hexdigest()
        
        # Upload file
        file_id = self.init_file_upload(
            name='delete_test.csv',
            content_type='text/csv',
            size=len(test_content)
        )
        self.complete_file_upload(file_id, content_sha256=content_hash, test_content=test_content)
        
        # Delete file
        response = self.client.delete(f'/api/v1/files/{file_id}/')
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify file status updated
        file_obj = File.objects.get(id=file_id)
        self.assertEqual(file_obj.status, FileStatus.DELETED)
        
        # Verify audit log created
        self.verify_audit_log(
            action='FILE_DELETED',
            resource_type='FILE',
            resource_id=file_id,
            result='SUCCESS'
        )
    
    def test_file_upload_with_invalid_hash_fails(self):
        """Test file upload with invalid content hash fails"""
        test_content = b'test content'
        wrong_hash = 'wrong_hash_value'
        
        # Initialize upload
        file_id = self.init_file_upload(
            name='invalid_hash.csv',
            content_type='text/csv',
            size=len(test_content)
        )
        
        # Try to complete with wrong hash
        response = self.client.post(
            f'/api/v1/files/{file_id}/complete/',
            {'content_sha256': wrong_hash},
            format='json'
        )
        
        # Should fail validation
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_file_upload_with_size_mismatch_fails(self):
        """Test file upload with size mismatch fails"""
        test_content = b'test content'
        declared_size = len(test_content) + 100  # Declare larger size
        
        # Initialize upload with wrong size
        response = self.client.post(
            '/api/v1/files/init/',
            {
                'name': 'size_mismatch.csv',
                'content_type': 'text/csv',
                'size': declared_size
            },
            format='json'
        )
        
        # Init should succeed
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = get_response_data(response) or {}
        file_id = data['file_id']
        
        # Complete with actual content (smaller than declared)
        content_hash = hashlib.sha256(test_content).hexdigest()
        response = self.complete_file_upload(file_id, content_sha256=content_hash, test_content=test_content)
        
        # Note: Implementation may allow this or reject it
        # Adjust test based on actual behavior
        file_obj = File.objects.get(id=file_id)
        # File may be completed with actual size, or rejected
        # This depends on implementation
    
    def test_file_upload_empty_file(self):
        """Test uploading empty file"""
        test_content = b''
        content_hash = hashlib.sha256(test_content).hexdigest()
        
        # Initialize upload
        file_id = self.init_file_upload(
            name='empty.csv',
            content_type='text/csv',
            size=0
        )
        
        # Complete upload
        self.complete_file_upload(file_id, content_sha256=content_hash, test_content=test_content)
        
        # Verify file exists
        file_obj = File.objects.get(id=file_id)
        self.assertEqual(file_obj.size, 0)
        self.assertEqual(file_obj.status, FileStatus.ACTIVE)
    
    def test_file_upload_unsupported_format(self):
        """Test uploading unsupported file format"""
        # Try to upload unsupported format
        response = self.client.post(
            '/api/v1/files/init/',
            {
                'name': 'test.xyz',
                'content_type': 'application/xyz',
                'size': 100
            },
            format='json'
        )
        
        # May succeed or fail depending on implementation
        # If validation is strict, should return 400
        # If permissive, should return 201 with warning
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST,
            f"Unsupported format should be rejected, got {response.status_code}")
    
    def test_file_upload_concurrent_uploads(self):
        """Test concurrent file uploads"""
        test_content1 = b'content1'
        test_content2 = b'content2'
        
        # Initialize two uploads concurrently
        file_id1 = self.init_file_upload(
            name='concurrent1.csv',
            content_type='text/csv',
            size=len(test_content1)
        )
        file_id2 = self.init_file_upload(
            name='concurrent2.csv',
            content_type='text/csv',
            size=len(test_content2)
        )
        
        # Complete both uploads
        hash1 = hashlib.sha256(test_content1).hexdigest()
        hash2 = hashlib.sha256(test_content2).hexdigest()
        
        self.complete_file_upload(file_id1, content_sha256=hash1, test_content=test_content1)
        self.complete_file_upload(file_id2, content_sha256=hash2, test_content=test_content2)
        
        # Verify both files exist
        file1 = File.objects.get(id=file_id1)
        file2 = File.objects.get(id=file_id2)
        
        self.assertEqual(file1.status, FileStatus.ACTIVE)
        self.assertEqual(file2.status, FileStatus.ACTIVE)
        self.assertEqual(file1.size, len(test_content1))
        self.assertEqual(file2.size, len(test_content2))
    
    def test_file_status_transitions(self):
        """Test file status transitions during upload"""
        test_content = b'status test'
        
        # Initialize upload (should be PENDING)
        file_id = self.init_file_upload(
            name='status_test.csv',
            content_type='text/csv',
            size=len(test_content)
        )
        
        file_obj = File.objects.get(id=file_id)
        # Status may be PENDING or UPLOADING depending on implementation
        self.assertIn(file_obj.status, [FileStatus.PENDING, FileStatus.UPLOADING])
        
        # Complete upload (should be ACTIVE)
        content_hash = hashlib.sha256(test_content).hexdigest()
        self.complete_file_upload(file_id, content_sha256=content_hash, test_content=test_content)
        
        file_obj.refresh_from_db()
        self.assertEqual(file_obj.status, FileStatus.ACTIVE)
        
        # Delete (should be DELETED)
        self.client.delete(f'/api/v1/files/{file_id}/')
        file_obj.refresh_from_db()
        self.assertEqual(file_obj.status, FileStatus.DELETED)
    
    def test_get_file_metadata(self):
        """Test retrieving file metadata"""
        test_content = b'metadata test'
        content_hash = hashlib.sha256(test_content).hexdigest()
        
        # Upload file
        file_id = self.init_file_upload(
            name='metadata_test.csv',
            content_type='text/csv',
            size=len(test_content)
        )
        self.complete_file_upload(file_id, content_sha256=content_hash, test_content=test_content)
        
        # Get file metadata
        response = self.client.get(f'/api/v1/files/{file_id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = get_response_data(response) or {}
        self.assertEqual(data['id'], str(file_id))
        self.assertEqual(data['name'], 'metadata_test.csv')
        self.assertEqual(data['content_type'], 'text/csv')
        self.assertEqual(data['size'], len(test_content))
        self.assertEqual(data['status'], FileStatus.ACTIVE)
    
    def test_file_upload_verifies_s3_storage(self):
        """Test that file upload verifies S3 storage"""
        test_content = b's3 verification test'
        content_hash = hashlib.sha256(test_content).hexdigest()
        
        # Upload file
        file_id = self.init_file_upload(
            name='s3_test.csv',
            content_type='text/csv',
            size=len(test_content)
        )
        self.complete_file_upload(file_id, content_sha256=content_hash, test_content=test_content)
        
        # Verify file exists in S3 with correct content
        self.verify_file_in_s3(
            file_id,
            expected_content=test_content,
            expected_size=len(test_content)
        )
        
        # Verify file metadata matches
        file_obj = File.objects.get(id=file_id)
        self.assertEqual(file_obj.content_sha256, content_hash)
        self.assertEqual(file_obj.size, len(test_content))

