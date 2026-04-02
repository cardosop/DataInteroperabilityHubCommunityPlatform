"""
Unit tests for chunked/multipart upload functionality.

Tests use real S3StorageClient with graceful handling when storage unavailable.
"""

import hashlib
import uuid

import pytest
from rest_framework import status

from hub.apps.files.models import File, FileStatus
from hub.apps.files.storage import S3StorageClient
from hub.apps.files.tests.test_base import FilesAPITestBase
from hub.apps.files.validators import calculate_chunk_count, get_chunk_size

pytestmark = pytest.mark.django_db(transaction=True)


class ChunkedUploadTest(FilesAPITestBase):
    """Test chunked upload functionality"""

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

    def test_init_chunk_upload(self):
        """Test chunk upload initialization"""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        # Create file with multipart upload
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="large.csv",
            content_type="text/csv",
            size=150 * 1024 * 1024,
            storage_path=f"{self.tenant.id}/large.csv",
            status=FileStatus.UPLOADING,
            created_by=self.user,
            metadata_json={
                "chunk_size": 10 * 1024 * 1024,
                "chunk_count": 15,
            },
        )

        # Initiate real multipart upload
        upload_id = self.storage_client.initiate_multipart_upload(
            key=file_obj.storage_path, content_type="text/csv"
        )
        file_obj.metadata_json["multipart_upload_id"] = upload_id
        file_obj.save(update_fields=["metadata_json"])

        data = {"chunk_number": 5, "chunk_size": 10 * 1024 * 1024}

        response = self.client.post(
            f"/api/v1/files/{file_obj.id}/chunks/init/", data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("upload_url", response.data)
        self.assertEqual(response.data["expires_in"], 3600)

        # Clean up multipart upload
        try:
            self.storage_client.abort_multipart_upload(
                key=file_obj.storage_path, upload_id=upload_id
            )
        except Exception:
            pass

    def test_init_chunk_upload_not_uploading(self):
        """Test chunk upload initialization for non-uploading file"""
        # Create file in PENDING state
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            storage_path=f"{self.tenant.id}/test.csv",
            status=FileStatus.PENDING,
            created_by=self.user,
        )

        data = {"chunk_number": 1, "chunk_size": 1024}

        response = self.client.post(
            f"/api/v1/files/{file_obj.id}/chunks/init/", data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_complete_multipart_upload_with_parts(self):
        """Test completing multipart upload with real S3 parts."""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        # Build a small file from real parts so ETags are valid
        part_data = b"x" * (5 * 1024 * 1024)  # 5 MiB minimum part size
        full_content = part_data  # single part for simplicity

        storage_key = f"{self.tenant.id}/{uuid.uuid4()}/large.csv"

        file_obj = File.objects.create(
            tenant=self.tenant,
            name="large.csv",
            content_type="text/csv",
            size=len(full_content),
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

        sha256_hash = hashlib.sha256(full_content).hexdigest()
        parts = [{"ETag": real_etag, "PartNumber": 1}]
        data = {"content_sha256": sha256_hash, "parts": parts}

        response = self.client.post(
            f"/api/v1/files/{file_obj.id}/complete/", data, format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            f"Expected 200 but got {response.status_code}: "
            f"{getattr(response, 'data', '')}",
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
