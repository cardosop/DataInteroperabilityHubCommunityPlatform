"""
Unit tests for file size limits and validation.
"""

import pytest
from django.conf import settings
from django.core.exceptions import ValidationError
from rest_framework import status

from hub.apps.files.tests.test_base import FilesAPITestBase
from hub.apps.files.validators import validate_file_size, validate_file_type

pytestmark = pytest.mark.django_db(transaction=True)


class FileSizeLimitsTest(FilesAPITestBase):
    """Test file size limits and validation"""

    def test_validate_file_size_browser_within_limit(self):
        """Test file size validation for browser upload within limit"""
        size = settings.MAX_BROWSER_UPLOAD_SIZE - 1

        # Should not raise exception
        try:
            validate_file_size(size, "browser")
        except ValidationError:
            self.fail("validate_file_size raised ValidationError for valid size")

    def test_validate_file_size_browser_exceeds_limit(self):
        """Test file size validation for browser upload exceeding limit"""
        size = settings.MAX_BROWSER_UPLOAD_SIZE + 1

        with self.assertRaises(ValidationError) as cm:
            validate_file_size(size, "browser")

        self.assertIn("browser upload limit", str(cm.exception))

    def test_validate_file_size_sdk_within_limit(self):
        """Test file size validation for SDK upload within limit"""
        size = settings.MAX_SDK_UPLOAD_SIZE - 1

        # Should not raise exception
        try:
            validate_file_size(size, "sdk")
        except ValidationError:
            self.fail("validate_file_size raised ValidationError for valid size")

    def test_validate_file_size_sdk_exceeds_limit(self):
        """Test file size validation for SDK upload exceeding limit"""
        size = settings.MAX_SDK_UPLOAD_SIZE + 1

        with self.assertRaises(ValidationError) as cm:
            validate_file_size(size, "sdk")

        self.assertIn("SDK upload limit", str(cm.exception))

    def test_validate_file_size_exceeds_global_max(self):
        """Test file size validation exceeding global maximum"""
        size = settings.MAX_FILE_SIZE + 1

        with self.assertRaises(ValidationError) as cm:
            validate_file_size(size, "browser")

        # Check for either "global maximum" or "platform default limit" in error message
        error_msg = str(cm.exception).lower()
        self.assertTrue(
            "global maximum" in error_msg
            or "platform default limit" in error_msg
            or "exceeds" in error_msg,
            f"Expected 'global maximum' or 'platform default limit' in error message, got: {cm.exception}",
        )

    def test_validate_file_type_allowed(self):
        """Test file type validation for allowed types"""
        # Should not raise exception for allowed types
        allowed_types = settings.ALLOWED_FILE_TYPES

        for ext in allowed_types:
            try:
                validate_file_type(f"test.{ext}")
            except ValidationError:
                self.fail(f"validate_file_type raised ValidationError for allowed type: {ext}")

    def test_validate_file_type_not_allowed(self):
        """Test file type validation for disallowed types"""
        with self.assertRaises(ValidationError) as cm:
            validate_file_type("test.exe")

        self.assertIn("not allowed", str(cm.exception))

    def test_validate_file_type_no_extension(self):
        """Test file type validation for file without extension"""
        with self.assertRaises(ValidationError) as cm:
            validate_file_type("testfile")

        self.assertIn("extension", str(cm.exception))

    def test_init_upload_browser_size_limit(self):
        """Test upload initialization enforces browser size limit"""

        data = {
            "name": "large.csv",
            "content_type": "text/csv",
            "size": settings.MAX_BROWSER_UPLOAD_SIZE + 1,
            "upload_method": "browser",
        }

        response = self.client.post("/api/v1/files/init/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Check that error details contain size validation information
        self.assertIn("detail", response.data)
        self.assertIn("size", response.data["detail"].lower())

    def test_init_upload_sdk_size_limit(self):
        """Test upload initialization enforces SDK size limit"""

        data = {
            "name": "huge.csv",
            "content_type": "text/csv",
            "size": settings.MAX_SDK_UPLOAD_SIZE + 1,
            "upload_method": "sdk",
        }

        response = self.client.post("/api/v1/files/init/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Check that error details contain size validation information
        self.assertIn("detail", response.data)
        self.assertIn("size", response.data["detail"].lower())

    def test_init_upload_global_size_limit(self):
        """Test upload initialization enforces global size limit"""

        data = {
            "name": "massive.csv",
            "content_type": "text/csv",
            "size": settings.MAX_FILE_SIZE + 1,
            "upload_method": "sdk",
        }

        response = self.client.post("/api/v1/files/init/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Check that error details contain size validation information
        self.assertIn("detail", response.data)
        self.assertIn("size", response.data["detail"].lower())

    def test_no_conflicting_upload_size_settings(self):
        """Regression: ensure orphaned _BYTES upload-limit settings do not exist.

        Previously settings.py defined both MAX_BROWSER_UPLOAD_SIZE (100 MB,
        used) and MAX_BROWSER_UPLOAD_SIZE_BYTES (1 GB, unused), which caused
        confusion.  Only the non-_BYTES variants should be present.
        """
        self.assertFalse(
            hasattr(settings, "MAX_BROWSER_UPLOAD_SIZE_BYTES"),
            "MAX_BROWSER_UPLOAD_SIZE_BYTES should not exist — use MAX_BROWSER_UPLOAD_SIZE",
        )
        self.assertFalse(
            hasattr(settings, "MAX_SDK_UPLOAD_SIZE_BYTES"),
            "MAX_SDK_UPLOAD_SIZE_BYTES should not exist — use MAX_SDK_UPLOAD_SIZE",
        )

    def test_upload_limits_are_sensible(self):
        """Verify upload limit settings have sane values."""
        self.assertGreater(settings.MAX_BROWSER_UPLOAD_SIZE, 0)
        self.assertGreater(settings.MAX_SDK_UPLOAD_SIZE, 0)
        self.assertGreaterEqual(
            settings.MAX_SDK_UPLOAD_SIZE,
            settings.MAX_BROWSER_UPLOAD_SIZE,
            "SDK upload limit should be >= browser upload limit",
        )
        self.assertGreaterEqual(
            settings.MAX_FILE_SIZE,
            settings.MAX_SDK_UPLOAD_SIZE,
            "Global MAX_FILE_SIZE should be >= SDK upload limit",
        )

    def test_init_upload_file_type_validation(self):
        """Test upload initialization validates file type"""

        data = {
            "name": "test.exe",
            "content_type": "application/x-msdownload",
            "size": 1024,
            "upload_method": "browser",
        }

        response = self.client.post("/api/v1/files/init/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("type", str(response.data).lower())
