"""
Unit tests for file serializers.

Tests validate serializer behavior without mocks/stubs.
"""

import uuid

import pytest
from django.test import TestCase

from hub.apps.files.models import FileStatus
from hub.apps.files.serializers import (
    ChecksumMismatchSerializer,
    ChunkUploadInitSerializer,
    ChunkUploadResponseSerializer,
    FileCompleteSerializer,
    FileDownloadResponseSerializer,
    FileInitResponseSerializer,
    FileInitSerializer,
    FileRenameSerializer,
    FileSerializer,
)
from hub.apps.files.tests.test_base import FilesTestBase

pytestmark = pytest.mark.django_db(transaction=True)


class FileInitSerializerTest(FilesTestBase):
    """Test FileInitSerializer."""

    def test_serializer_valid_data(self):
        """Test serializer with valid data."""
        data = {
            "name": "test.csv",
            "content_type": "text/csv",
            "size": 1024,
            "upload_method": "browser",
        }

        serializer = FileInitSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["name"], "test.csv")
        self.assertEqual(serializer.validated_data["content_type"], "text/csv")
        self.assertEqual(serializer.validated_data["size"], 1024)
        self.assertEqual(serializer.validated_data["upload_method"], "browser")

    def test_serializer_default_upload_method(self):
        """Test serializer uses default upload_method."""
        data = {
            "name": "test.csv",
            "content_type": "text/csv",
            "size": 1024,
        }

        serializer = FileInitSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["upload_method"], "browser")

    def test_serializer_invalid_upload_method(self):
        """Test serializer rejects invalid upload_method."""
        data = {
            "name": "test.csv",
            "content_type": "text/csv",
            "size": 1024,
            "upload_method": "invalid",
        }

        serializer = FileInitSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("upload_method", serializer.errors)

    def test_serializer_missing_required_fields(self):
        """Test serializer requires all fields."""
        data = {"name": "test.csv"}

        serializer = FileInitSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("content_type", serializer.errors)
        self.assertIn("size", serializer.errors)

    def test_serializer_negative_size(self):
        """Test serializer rejects negative size."""
        data = {
            "name": "test.csv",
            "content_type": "text/csv",
            "size": -1,
        }

        serializer = FileInitSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("size", serializer.errors)

    def test_serializer_zero_size(self):
        """Test serializer accepts zero size (empty files)."""
        data = {
            "name": "empty.csv",
            "content_type": "text/csv",
            "size": 0,
        }

        serializer = FileInitSerializer(data=data)
        self.assertTrue(serializer.is_valid())


class FileInitResponseSerializerTest(FilesTestBase):
    """Test FileInitResponseSerializer."""

    def test_serializer_valid_data_simple_upload(self):
        """Test serializer with valid data for simple upload."""

        data = {
            "file_id": uuid.uuid4(),
            "upload_url": "https://s3.example.com/upload",
            "fields": {"key": "value"},
            "requires_multipart": False,
        }

        serializer = FileInitResponseSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_serializer_valid_data_multipart_upload(self):
        """Test serializer with valid data for multipart upload."""

        data = {
            "file_id": uuid.uuid4(),
            "upload_url": "https://s3.example.com/upload",
            "fields": {},
            "chunk_size": 5242880,
            "chunk_count": 10,
            "requires_multipart": True,
            "upload_id": "upload-id-123",
        }

        serializer = FileInitResponseSerializer(data=data)
        self.assertTrue(serializer.is_valid())


class FileCompleteSerializerTest(FilesTestBase):
    """Test FileCompleteSerializer."""

    def test_serializer_valid_data(self):
        """Test serializer with valid data."""
        import hashlib

        content_sha256 = hashlib.sha256(b"test content").hexdigest()
        data = {"content_sha256": content_sha256}

        serializer = FileCompleteSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["content_sha256"], content_sha256)

    def test_serializer_with_parts(self):
        """Test serializer with parts for multipart upload."""
        import hashlib

        content_sha256 = hashlib.sha256(b"test content").hexdigest()
        data = {
            "content_sha256": content_sha256,
            "parts": [
                {"ETag": "etag1", "PartNumber": 1},
                {"ETag": "etag2", "PartNumber": 2},
            ],
        }

        serializer = FileCompleteSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(len(serializer.validated_data["parts"]), 2)

    def test_serializer_missing_content_sha256(self):
        """Test serializer requires content_sha256."""
        data = {}

        serializer = FileCompleteSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("content_sha256", serializer.errors)

    def test_serializer_accepts_any_sha256_string(self):
        """SHA-256 format validation is delegated to the view layer.

        The serializer is intentionally permissive — it accepts any string
        so the view can produce a typed 400 error with the correct error code
        rather than a generic DRF validation error.
        """
        data = {"content_sha256": "invalid_hash"}

        serializer = FileCompleteSerializer(data=data)
        self.assertTrue(serializer.is_valid())


class FileSerializerTest(FilesTestBase):
    """Test FileSerializer."""

    def test_serializer_serialize_file(self):
        """Test serializing file instance."""
        serializer = FileSerializer(self.file)
        data = serializer.data

        self.assertEqual(data["id"], str(self.file.id))
        self.assertEqual(data["name"], self.file.name)
        self.assertEqual(data["content_type"], self.file.content_type)
        self.assertEqual(data["size"], self.file.size)
        self.assertEqual(data["status"], self.file.status)
        self.assertEqual(data["scan_status"], self.file.scan_status)
        self.assertEqual(data["scanned_at"], self.file.scanned_at)

    def test_serializer_read_only_fields(self):
        """Test serializer read-only fields cannot be updated."""
        data = {
            "id": "new-id",
            "name": "updated.csv",
            "status": FileStatus.DELETED.value,
        }

        serializer = FileSerializer(self.file, data=data, partial=True)
        # Read-only fields should be ignored
        self.assertTrue(serializer.is_valid())
        # ID and status should remain unchanged
        self.assertEqual(serializer.instance.id, self.file.id)

    def test_serializer_update_name(self):
        """Test updating file name."""
        data = {"name": "updated_name.csv"}

        serializer = FileSerializer(self.file, data=data, partial=True)
        self.assertTrue(serializer.is_valid())
        serializer.save()
        self.file.refresh_from_db()
        self.assertEqual(self.file.name, "updated_name.csv")


class FileDownloadResponseSerializerTest(FilesTestBase):
    """Test FileDownloadResponseSerializer."""

    def test_serializer_valid_data(self):
        """Test serializer with valid data."""
        data = {
            "download_url": "https://s3.example.com/download",
            "expires_in": 3600,
            "filename": "test.csv",
        }

        serializer = FileDownloadResponseSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["download_url"], data["download_url"])
        self.assertEqual(serializer.validated_data["expires_in"], 3600)
        self.assertEqual(serializer.validated_data["filename"], "test.csv")


class ChunkUploadInitSerializerTest(FilesTestBase):
    """Test ChunkUploadInitSerializer."""

    def test_serializer_valid_data(self):
        """Test serializer with valid data."""
        data = {"chunk_number": 1, "chunk_size": 5242880}

        serializer = ChunkUploadInitSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["chunk_number"], 1)
        self.assertEqual(serializer.validated_data["chunk_size"], 5242880)

    def test_serializer_invalid_chunk_number(self):
        """Test serializer rejects invalid chunk_number."""
        data = {"chunk_number": 0, "chunk_size": 5242880}

        serializer = ChunkUploadInitSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("chunk_number", serializer.errors)

    def test_serializer_invalid_chunk_size(self):
        """Test serializer rejects invalid chunk_size."""
        data = {"chunk_number": 1, "chunk_size": 0}

        serializer = ChunkUploadInitSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("chunk_size", serializer.errors)


class ChunkUploadResponseSerializerTest(FilesTestBase):
    """Test ChunkUploadResponseSerializer."""

    def test_serializer_valid_data(self):
        """Test serializer with valid data."""
        data = {
            "upload_url": "https://s3.example.com/upload/part/1",
            "expires_in": 3600,
        }

        serializer = ChunkUploadResponseSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["upload_url"], data["upload_url"])
        self.assertEqual(serializer.validated_data["expires_in"], 3600)


# ── Previously untested serializers ───────────────────────────────


class ChecksumMismatchSerializerTest(TestCase):
    """Unit tests for ChecksumMismatchSerializer."""

    def test_valid_sha256_passes(self):
        serializer = ChecksumMismatchSerializer(data={
            "actual_sha256": "a" * 64,
        })
        self.assertTrue(serializer.is_valid(), f"Errors: {serializer.errors}")

    def test_missing_actual_sha256_is_invalid(self):
        serializer = ChecksumMismatchSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn("actual_sha256", serializer.errors)

    def test_sha256_too_short_is_invalid(self):
        serializer = ChecksumMismatchSerializer(data={
            "actual_sha256": "a" * 32,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn("actual_sha256", serializer.errors)

    def test_sha256_too_long_is_invalid(self):
        serializer = ChecksumMismatchSerializer(data={
            "actual_sha256": "a" * 65,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn("actual_sha256", serializer.errors)


class FileRenameSerializerTest(TestCase):
    """Unit tests for FileRenameSerializer."""

    def test_valid_name_passes(self):
        serializer = FileRenameSerializer(data={"name": "new-report.csv"})
        self.assertTrue(serializer.is_valid(), f"Errors: {serializer.errors}")

    def test_missing_name_is_invalid(self):
        serializer = FileRenameSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)

    def test_empty_name_is_invalid(self):
        serializer = FileRenameSerializer(data={"name": ""})
        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)
