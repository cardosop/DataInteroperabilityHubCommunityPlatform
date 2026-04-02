"""
Tests for Tasks 14.6 (magic-byte MIME validation) and
14.7 (path traversal prevention).
"""
import sys
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from django.core.exceptions import ValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_magic(detected_mime: str) -> MagicMock:
    """Return a mock python-magic module that reports *detected_mime*."""
    m = MagicMock()
    m.from_buffer.return_value = detected_mime
    return m


# ---------------------------------------------------------------------------
# 14.6  Magic-byte MIME validation
# ---------------------------------------------------------------------------

class TestMagicByteMimeValidation:
    """Test that files with mismatched magic bytes are rejected."""

    def test_pdf_magic_in_txt_rejected(self):
        """A .txt file with PDF magic bytes must raise ValidationError.

        Uses a mock for python-magic so the test runs even when libmagic
        is not installed in the test environment.
        """
        from hub.apps.files.validators import validate_file_magic

        file_obj = BytesIO(b'%PDF-1.4 fake content')
        with patch.dict(sys.modules, {'magic': _mock_magic('application/pdf')}):
            with pytest.raises(ValidationError, match="content type mismatch"):
                validate_file_magic(file_obj, 'text/plain', 'test.txt')

    def test_valid_text_file_accepted(self):
        """A genuine text/plain file must not raise."""
        from hub.apps.files.validators import validate_file_magic

        file_obj = BytesIO(b'Hello, world! This is plain text.')
        with patch.dict(sys.modules, {'magic': _mock_magic('text/plain')}):
            validate_file_magic(file_obj, 'text/plain', 'test.txt')

    def test_seek_reset_after_read(self):
        """validate_file_magic must reset the file position to 0."""
        from hub.apps.files.validators import validate_file_magic

        file_obj = BytesIO(b'Hello, world! This is plain text.')
        with patch.dict(sys.modules, {'magic': _mock_magic('text/plain')}):
            validate_file_magic(file_obj, 'text/plain', 'test.txt')

        assert file_obj.tell() == 0

    def test_csv_detected_as_text_plain_is_allowed(self):
        """text/csv declared, text/plain detected: allow-listed mismatch."""
        from hub.apps.files.validators import validate_file_magic

        file_obj = BytesIO(b'id,name,value\n1,foo,100\n')
        with patch.dict(sys.modules, {'magic': _mock_magic('text/plain')}):
            validate_file_magic(file_obj, 'text/csv', 'data.csv')

    def test_exact_mime_match_accepted(self):
        """Declared MIME type matches detected MIME exactly: no error."""
        from hub.apps.files.validators import validate_file_magic

        file_obj = BytesIO(b'plain text here')
        with patch.dict(sys.modules, {'magic': _mock_magic('text/plain')}):
            validate_file_magic(file_obj, 'text/plain', 'notes.txt')

    def test_graceful_fallback_when_magic_unavailable(self):
        """When python-magic cannot be imported, validation is skipped silently.

        Setting sys.modules['magic'] = None makes Python raise ImportError
        on ``import magic``, triggering the graceful-degradation path.
        """
        from hub.apps.files.validators import validate_file_magic

        file_obj = BytesIO(b'%PDF-1.4 fake content')
        with patch.dict(sys.modules, {'magic': None}):
            # Must NOT raise — graceful degradation when libmagic is absent
            validate_file_magic(file_obj, 'text/plain', 'test.txt')


# ---------------------------------------------------------------------------
# 14.7  Path traversal filename rejection
# ---------------------------------------------------------------------------

class TestPathTraversalFilenameRejection:
    """Test that path traversal filenames are rejected."""

    def test_path_traversal_rejected(self):
        from hub.apps.files.validators import validate_filename

        with pytest.raises(ValidationError):
            validate_filename('../../etc/passwd')

    def test_windows_path_traversal_rejected(self):
        from hub.apps.files.validators import validate_filename

        with pytest.raises(ValidationError):
            validate_filename('..\\..\\windows\\system32\\config\\sam')

    def test_normal_filename_accepted(self):
        from hub.apps.files.validators import validate_filename

        result = validate_filename('my-data-file.csv')
        assert result == 'my-data-file.csv'

    def test_hidden_file_rejected(self):
        from hub.apps.files.validators import validate_filename

        with pytest.raises(ValidationError):
            validate_filename('.env')

    def test_filename_truncated_to_255_bytes(self):
        from hub.apps.files.validators import validate_filename

        long_name = 'a' * 300 + '.csv'
        result = validate_filename(long_name)
        assert len(result.encode('utf-8')) <= 255

    def test_null_byte_in_filename_rejected(self):
        """Null byte in filename is a common injection vector."""
        from hub.apps.files.validators import validate_filename

        with pytest.raises(ValidationError):
            validate_filename('safe\x00.csv')

    def test_control_chars_rejected(self):
        """Control characters (ASCII < 0x20) must be rejected."""
        from hub.apps.files.validators import validate_filename

        with pytest.raises(ValidationError):
            validate_filename('file\x01name.csv')

    def test_directory_stripped_from_posix_path(self):
        """A leading directory component is stripped, leaving the basename."""
        from hub.apps.files.validators import validate_filename

        result = validate_filename('/home/user/secret.csv')
        assert result == 'secret.csv'

    def test_dot_dot_in_middle_rejected(self):
        """A '..' component anywhere in the path must be rejected."""
        from hub.apps.files.validators import validate_filename

        with pytest.raises(ValidationError):
            validate_filename('foo/../secret.txt')

    def test_trailing_dot_rejected(self):
        """Filenames ending with '.' are invalid on Windows."""
        from hub.apps.files.validators import validate_filename

        with pytest.raises(ValidationError):
            validate_filename('dangerous.')

    def test_reserved_chars_rejected(self):
        """Characters like '<', '>', '|' must be rejected."""
        from hub.apps.files.validators import validate_filename

        for char in '<>:|':
            with pytest.raises(ValidationError, match="Invalid filename"):
                validate_filename(f'file{char}name.csv')
