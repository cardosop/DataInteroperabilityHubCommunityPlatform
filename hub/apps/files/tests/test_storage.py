"""
Unit tests for S3StorageClient.

Tests use real S3StorageClient with graceful handling when S3/MinIO unavailable.
"""

import pytest
from django.core.files.base import ContentFile
from django.test import TestCase

from hub.apps.files.storage import S3StorageClient
from hub.apps.files.tests.test_base import FilesTestBase

pytestmark = pytest.mark.django_db(transaction=True)


class S3StorageClientTest(FilesTestBase):
    """Test S3StorageClient with real implementation."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.storage_available = False
        try:
            self.storage_client = S3StorageClient()
            self.storage_client._ensure_bucket_exists()
            self.storage_available = True
        except Exception:
            self.storage_available = False

    def test_storage_client_initialization(self):
        """Test S3StorageClient initializes with correct settings."""
        from django.conf import settings

        storage_client = S3StorageClient()
        self.assertIsNotNone(storage_client.client)
        self.assertEqual(storage_client.bucket_name, settings.AWS_STORAGE_BUCKET_NAME)

    def test_ensure_bucket_exists_success(self):
        """Test bucket creation when available."""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        storage_client = S3StorageClient()
        # Should not raise
        storage_client._ensure_bucket_exists()

        # Verify the bucket actually exists by calling head_bucket
        response = storage_client.client.head_bucket(Bucket=storage_client.bucket_name)
        self.assertEqual(response["ResponseMetadata"]["HTTPStatusCode"], 200)

    def test_save_file_success(self):
        """Test saving file to storage when available."""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        test_content = b"test,data\n1,2\n3,4"
        file_id = str(self.file.id)

        storage_path = self.storage_client.save_file(
            tenant_id=str(self.tenant.id),
            file_id=file_id,
            file_content=ContentFile(test_content),
        )

        self.assertIsNotNone(storage_path)
        self.assertIn(str(self.tenant.id), storage_path)
        self.assertIn(file_id, storage_path)

    def test_file_exists_success(self):
        """Test checking file existence when storage available."""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        test_content = b"test,data\n1,2"
        file_id = str(self.file.id)

        # Save file first
        storage_path = self.storage_client.save_file(
            tenant_id=str(self.tenant.id),
            file_id=file_id,
            file_content=ContentFile(test_content),
        )

        # Check existence
        exists = self.storage_client.file_exists(storage_path)
        self.assertTrue(exists)

    def test_file_exists_not_found(self):
        """Test checking file existence for non-existent file."""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        non_existent_path = f"{self.tenant.id}/nonexistent/file.csv"
        exists = self.storage_client.file_exists(non_existent_path)
        self.assertFalse(exists)

    def test_get_file_size_success(self):
        """Test getting file size when storage available."""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        test_content = b"test,data\n1,2\n3,4"
        file_id = str(self.file.id)

        storage_path = self.storage_client.save_file(
            tenant_id=str(self.tenant.id),
            file_id=file_id,
            file_content=ContentFile(test_content),
        )

        size = self.storage_client.get_file_size(storage_path)
        self.assertEqual(size, len(test_content))

    def test_get_file_content_success(self):
        """Test getting file content when storage available."""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        test_content = b"test,data\n1,2\n3,4"
        file_id = str(self.file.id)

        storage_path = self.storage_client.save_file(
            tenant_id=str(self.tenant.id),
            file_id=file_id,
            file_content=ContentFile(test_content),
        )

        content = self.storage_client.get_file_content(storage_path)
        self.assertEqual(content, test_content)

    def test_delete_file_success(self):
        """Test deleting file when storage available."""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        test_content = b"test,data\n1,2"
        file_id = str(self.file.id)

        storage_path = self.storage_client.save_file(
            tenant_id=str(self.tenant.id),
            file_id=file_id,
            file_content=ContentFile(test_content),
        )

        # Delete file
        self.storage_client.delete_file(storage_path)

        # Verify deleted
        exists = self.storage_client.file_exists(storage_path)
        self.assertFalse(exists)

    def test_generate_presigned_upload_url_success(self):
        """Test generating presigned upload URL."""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        storage_path = f"{self.tenant.id}/{self.file.id}/test.csv"

        result = self.storage_client.generate_presigned_upload_url(
            key=storage_path,
            content_type="text/csv",
            expires_in=3600,
            use_put=True,
        )

        self.assertIn("upload_url", result)
        self.assertIn("fields", result)
        self.assertIsNotNone(result["upload_url"])

    def test_generate_presigned_download_url_success(self):
        """Test generating presigned download URL."""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        test_content = b"test,data\n1,2"
        file_id = str(self.file.id)

        storage_path = self.storage_client.save_file(
            tenant_id=str(self.tenant.id),
            file_id=file_id,
            file_content=ContentFile(test_content),
        )

        download_url = self.storage_client.generate_presigned_download_url(
            key=storage_path,
            expires_in=3600,
            filename="test.csv",
        )

        self.assertIsNotNone(download_url)
        self.assertIn("http", download_url)

    def test_initiate_multipart_upload_success(self):
        """Test initiating multipart upload."""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        storage_path = f"{self.tenant.id}/{self.file.id}/large.csv"

        upload_id = self.storage_client.initiate_multipart_upload(
            key=storage_path,
            content_type="text/csv",
        )

        self.assertIsNotNone(upload_id)

        # Clean up - abort multipart upload
        try:
            self.storage_client.abort_multipart_upload(key=storage_path, upload_id=upload_id)
        except Exception:
            pass

    def test_generate_presigned_part_url_success(self):
        """Test generating presigned part URL."""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        storage_path = f"{self.tenant.id}/{self.file.id}/large.csv"

        upload_id = self.storage_client.initiate_multipart_upload(
            key=storage_path,
            content_type="text/csv",
        )

        part_url = self.storage_client.generate_presigned_part_url(
            key=storage_path,
            upload_id=upload_id,
            part_number=1,
            expires_in=3600,
        )

        self.assertIsNotNone(part_url)
        self.assertIn("http", part_url)

        # Clean up
        try:
            self.storage_client.abort_multipart_upload(key=storage_path, upload_id=upload_id)
        except Exception:
            pass

    def test_initiate_and_abort_multipart_upload(self):
        """Test that a multipart upload can be initiated and then aborted.

        A full complete-multipart test requires uploading real parts; this test
        verifies the initiate/abort lifecycle instead.
        """
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        storage_path = f"{self.tenant.id}/{self.file.id}/large.csv"

        upload_id = self.storage_client.initiate_multipart_upload(
            key=storage_path,
            content_type="text/csv",
        )
        self.assertIsNotNone(upload_id)

        # Abort the multipart upload — catch only S3-related errors
        try:
            self.storage_client.abort_multipart_upload(key=storage_path, upload_id=upload_id)
        except self.storage_client.client.exceptions.NoSuchUpload:
            pass  # Already completed or aborted

    def test_storage_unavailable_graceful_handling(self):
        """Test graceful handling when storage is unavailable.

        Creates an S3StorageClient pointed at an unreachable endpoint and
        verifies that operations raise exceptions instead of crashing
        silently or hanging.
        """
        from django.test import override_settings
        from botocore.config import Config

        # Build a client aimed at an unreachable address.
        # Use RFC 5737 TEST-NET-1 (192.0.2.0/24) — guaranteed non-routable,
        # unlike 127.0.0.1:1 which gets an instant connection-refused that
        # some botocore versions handle differently from a true timeout.
        bad_client = S3StorageClient.__new__(S3StorageClient)
        bad_client.bucket_name = "nonexistent-bucket"
        bad_client.endpoint_url = "http://192.0.2.1:9999"
        bad_client.use_ssl = False
        bad_client._bucket_checked = False
        bad_client._original_endpoint = "http://192.0.2.1:9999"
        s3_config = Config(
            signature_version="s3v4",
            retries={"max_attempts": 1, "mode": "standard"},
            connect_timeout=1,
            read_timeout=1,
        )
        import boto3 as _boto3
        bad_client.client = _boto3.client(
            "s3",
            endpoint_url="http://192.0.2.1:9999",
            aws_access_key_id="fake",
            aws_secret_access_key="fake",
            use_ssl=False,
            verify=False,
            config=s3_config,
        )

        # _ensure_bucket_exists is designed to be lenient (swallows
        # connection errors to allow fallback), so we test the actual
        # storage operations that must propagate errors.

        # file_exists should raise, not silently return False
        with self.assertRaises(Exception):
            bad_client.file_exists("any/key")

        # save_file should raise
        from django.core.files.base import ContentFile

        with self.assertRaises(Exception):
            bad_client.save_file(
                tenant_id="t",
                file_id="f",
                file_content=ContentFile(b"data"),
            )

        # get_file_content should raise
        with self.assertRaises(Exception):
            bad_client.get_file_content("any/key")
