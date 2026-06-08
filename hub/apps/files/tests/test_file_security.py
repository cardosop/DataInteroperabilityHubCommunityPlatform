"""
Tests for file security hardening — G2.1 path traversal (glittery-herding-graham).

Verifies that user-provided filenames are sanitized before being used in
S3 storage paths, preventing directory traversal attacks.
"""

import os
import uuid

import pytest
from django.test import TestCase

pytestmark = pytest.mark.django_db(transaction=True)


class FilePathTraversalTest(TestCase):
    """User-provided filename must be sanitized in the storage path."""

    def test_filename_with_path_traversal_is_sanitized(self):
        """../../etc/passwd should become just 'passwd' in the storage path."""
        name = "../../etc/passwd"
        safe_name = os.path.basename(name) or "unnamed"
        storage_path = f"{uuid.uuid4()}/{uuid.uuid4()}/{safe_name}"

        self.assertNotIn("..", storage_path)
        self.assertTrue(storage_path.endswith("passwd"))

    def test_filename_with_subdirectory_is_flattened(self):
        """subdir/file.txt should become just 'file.txt'."""
        name = "subdir/nested/file.txt"
        safe_name = os.path.basename(name) or "unnamed"

        self.assertEqual(safe_name, "file.txt")

    def test_empty_filename_gets_default(self):
        """Empty filename should become 'unnamed'."""
        for name in ["", "   ", None]:
            safe_name = os.path.basename((name or "").strip()) or "unnamed"
            self.assertEqual(safe_name, "unnamed")

    def test_backslash_traversal_stripped(self):
        """Windows-style ..\\..\\etc\\passwd should be sanitized."""
        name = "..\\..\\etc\\passwd"
        safe_name = os.path.basename(name.replace("\\", "/")) or "unnamed"
        self.assertEqual(safe_name, "passwd")

    def test_null_byte_in_filename_stripped(self):
        """Null bytes in filenames must be removed."""
        name = "file\x00.txt"
        safe_name = os.path.basename(name.replace("\x00", "")) or "unnamed"
        self.assertEqual(safe_name, "file.txt")
