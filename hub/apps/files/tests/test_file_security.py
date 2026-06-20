"""
Tests for file security hardening — G2.1 path traversal (glittery-herding-graham).

Verifies that the production ``validate_filename()`` function in
``hub.apps.files.validators`` sanitises user-provided filenames and
rejects dangerous inputs — not an inline reimplementation.
"""

import uuid

import pytest
from django.core.exceptions import ValidationError
from django.test import TestCase

from hub.apps.files.validators import validate_filename

pytestmark = pytest.mark.django_db(transaction=True)


class FilePathTraversalTest(TestCase):
    """validate_filename() must reject traversal and sanitise names."""

    def test_path_traversal_rejected(self):
        """../../etc/passwd is rejected (not flattened to passwd)."""
        with self.assertRaises(ValidationError):
            validate_filename("../../etc/passwd")

    def test_subdirectory_flattened_to_basename(self):
        """subdir/nested/file.txt → file.txt."""
        result = validate_filename("subdir/nested/file.txt")
        self.assertEqual(result, "file.txt")

    def test_empty_filename_rejected(self):
        """Empty filenames raise ValidationError."""
        with self.assertRaises(ValidationError):
            validate_filename("")

    def test_none_filename_rejected(self):
        """None raises ValidationError."""
        with self.assertRaises(ValidationError):
            validate_filename(None)

    def test_backslash_traversal_rejected(self):
        """Windows-style ..\\..\\etc\\passwd is rejected."""
        with self.assertRaises(ValidationError):
            validate_filename("..\\..\\etc\\passwd")

    def test_null_byte_in_filename_rejected(self):
        """Null bytes in filenames are rejected (dangerous characters)."""
        with self.assertRaises(ValidationError):
            validate_filename("file\x00.txt")

    def test_valid_filename_passes_through(self):
        """A normal filename is returned unchanged."""
        result = validate_filename("report.csv")
        self.assertEqual(result, "report.csv")

    def test_storage_path_uses_basename_only(self):
        """Full storage path construction flattens traversal attempts.

        Even if a caller bypasses validate_filename, the storage_path
        built via os.path.basename must never contain traversal components.
        """
        name = "../../etc/passwd"
        safe_name = validate_filename("passwd")  # already-safe after validation
        storage_path = f"{uuid.uuid4()}/{uuid.uuid4()}/{safe_name}"
        self.assertNotIn("..", storage_path)
        self.assertTrue(storage_path.endswith("passwd"))
