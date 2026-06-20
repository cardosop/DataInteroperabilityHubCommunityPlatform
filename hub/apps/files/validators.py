"""
File Validation Utilities

Validates file size, type, and other constraints.
"""

import logging
import os
import re
import unicodedata

from django.conf import settings
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 14.6  Magic-byte MIME validation
# ---------------------------------------------------------------------------

# Declared MIME type → detected MIME type pairs that are known-safe mismatches.
MIME_ALLOWED_MISMATCHES = {
    # text/csv files often detected as text/plain
    ("text/csv", "text/plain"): True,
    ("application/csv", "text/plain"): True,
    # JSON files sometimes detected as text/plain
    ("application/json", "text/plain"): True,
    # Parquet and some binary formats may be reported differently
    ("application/octet-stream", "application/x-par"): True,
}


def validate_file_magic(file_obj, declared_content_type: str, filename: str) -> None:
    """
    Validate a file's actual content against its declared MIME type using magic bytes.

    Reads the first 512 bytes of *file_obj* (then seeks back to 0) and uses
    ``python-magic`` (libmagic) to detect the real MIME type.  If the detected
    type disagrees with *declared_content_type* and the mismatch is not listed
    in :data:`MIME_ALLOWED_MISMATCHES`, a :class:`~django.core.exceptions.ValidationError`
    is raised.

    If ``python-magic`` / libmagic is not available the function logs a warning
    and returns without blocking the upload so that environments without the
    native library do not break.

    Args:
        file_obj: A file-like object that supports ``read()`` and ``seek()``.
        declared_content_type: The MIME type declared by the client (e.g. ``"text/plain"``).
        filename: Original filename (used for error messages only).

    Raises:
        ValidationError: When the detected MIME type is incompatible with the
            declared one and the mismatch is not allow-listed.
    """
    try:
        import magic  # python-magic
    except ImportError:
        logger.warning(
            "python-magic is not installed; skipping magic-byte MIME validation "
            "for file %r. Install python-magic>=0.4.27 and libmagic to enable.",
            filename,
        )
        return

    content = file_obj.read(512)
    file_obj.seek(0)

    try:
        detected_mime: str = magic.from_buffer(content, mime=True)
    except Exception as exc:  # pragma: no cover – libmagic runtime errors
        logger.warning(
            "python-magic failed to inspect file %r: %s; skipping magic-byte check.",
            filename,
            exc,
        )
        return

    # Exact match – all good.
    if detected_mime == declared_content_type:
        return

    # Allow-listed known-harmless mismatch.
    if MIME_ALLOWED_MISMATCHES.get((declared_content_type, detected_mime)):
        return

    raise ValidationError(
        f"File content type mismatch: declared {declared_content_type} but detected "
        f"{detected_mime}. Upload the correct file type."
    )


# ---------------------------------------------------------------------------
# 14.7  Path traversal prevention
# ---------------------------------------------------------------------------

# Characters and patterns that are dangerous in filenames.
_DANGEROUS_FILENAME_RE = re.compile(r'[<>:"|?*\x00-\x1f]|^\.|\.\.|\.$')


def validate_filename(name: str) -> str:
    """
    Sanitise and validate an uploaded filename.

    Steps performed:
    1. Strip directory components (handles both POSIX and Windows path separators).
    2. Reject names that contain dangerous characters or path-traversal sequences.
    3. Truncate to 255 UTF-8 bytes (the limit on most filesystems).

    Args:
        name: Raw filename submitted by the client.

    Returns:
        The sanitised filename (no path components, safely truncated).

    Raises:
        ValidationError: If the sanitised name is empty or contains dangerous
            patterns such as directory traversal, control characters, or
            reserved characters.
    """
    # Guard against None or non-string inputs before any string operations.
    if not name or not isinstance(name, str):
        raise ValidationError("Invalid filename: filename must be a non-empty string.")

    # Normalise to NFC (composed) form so that NFD-decomposed inputs
    # (e.g. 'café.csv') are stored as 'café.csv'. This ensures
    # locale-filename roundtripping produces consistent output and
    # downstream consumers don't encounter decomposed forms.
    name = unicodedata.normalize("NFC", name)

    # Normalise Windows-style separators before any checks.
    name = name.replace("\\", "/")

    # Reject any input that contains directory-traversal components BEFORE
    # stripping the path.  After basename('../../etc/passwd') you get 'passwd'
    # which looks innocent, but the original intent was traversal — reject it.
    if ".." in name.split("/"):
        raise ValidationError(
            f"Invalid filename: '{name}'. Filenames must not contain directory "
            "traversal, control characters, or reserved characters."
        )

    # Strip any remaining directory component (e.g. '/home/user/file.csv' → 'file.csv').
    name = os.path.basename(name)

    # Reject dangerous filenames (hidden files, reserved chars, control chars, etc.).
    if not name or _DANGEROUS_FILENAME_RE.search(name):
        raise ValidationError(
            f"Invalid filename: '{name}'. Filenames must not contain directory "
            "traversal, control characters, or reserved characters."
        )

    # Truncate to 255 UTF-8 bytes (decode with errors='ignore' in case the
    # truncation split a multi-byte character).
    name = name.encode("utf-8")[:255].decode("utf-8", errors="ignore")

    # Re-compose after byte truncation — truncating a multi-byte NFC
    # character (e.g. a 2-byte 'é') can split it, leaving a partial
    # character that decode(errors='ignore') drops.  A second NFC pass
    # repairs any remaining decomposed code points.
    name = unicodedata.normalize("NFC", name)

    if not name:
        raise ValidationError("Invalid filename: filename is empty after sanitisation.")

    return name


def validate_file_size(
    size: int, upload_method: str = "browser", tenant_id: str | None = None
) -> None:
    """
    Validate file size against limits (tenant config or platform defaults).

    Priority:
    1. Tenant-specific max_file_size_bytes from TenantConfig
    2. Platform default (10737418240 bytes = 10 GB)

    Also enforces method-specific limits (browser/SDK) which are typically lower
    than the tenant limit.

    Args:
        size: File size in bytes (0 is allowed for empty files)
        upload_method: "browser" or "sdk"
        tenant_id: Optional tenant UUID as string (for tenant-specific limits)

    Raises:
        ValidationError if file size exceeds limits
    """
    # Allow empty files (size=0)
    if size < 0:
        raise ValidationError("File size cannot be negative")

    # Get tenant-specific limit if tenant_id provided
    tenant_limit = None
    if tenant_id:
        try:
            from hub.apps.tenants.services import get_tenant_file_size_limit

            tenant_limit = get_tenant_file_size_limit(tenant_id)
        except Exception:
            # If tenant lookup fails, fall back to platform defaults
            pass

    # Determine effective limit (tenant limit or platform default)
    if tenant_limit:
        effective_limit = tenant_limit
        limit_source = "tenant configuration"
    else:
        effective_limit = settings.MAX_FILE_SIZE
        limit_source = "platform default"

    # Method-specific limits (browser/SDK) are typically lower than tenant limit
    if upload_method == "browser":
        method_limit = settings.MAX_BROWSER_UPLOAD_SIZE
        limit_name = "browser upload limit"
    elif upload_method == "sdk":
        method_limit = settings.MAX_SDK_UPLOAD_SIZE
        limit_name = "SDK upload limit"
    else:
        method_limit = effective_limit
        limit_name = f"file size limit ({limit_source})"

    # Use the more restrictive limit (method limit or tenant limit)
    max_size = min(method_limit, effective_limit)

    # Check tenant/platform limit (skip for empty files)
    if size > 0 and size > effective_limit:
        raise ValidationError(
            f"File size ({size} bytes) exceeds {limit_source} limit ({effective_limit} bytes)"
        )

    # Check method-specific limit (skip for empty files)
    if size > 0 and size > max_size:
        raise ValidationError(f"File size ({size} bytes) exceeds {limit_name} ({max_size} bytes)")


def validate_file_type(filename: str, content_type: str | None = None) -> None:
    """
    Validate file type against allowed types.

    Args:
        filename: Original filename
        content_type: MIME type (optional)

    Raises:
        ValidationError if file type is not allowed
    """
    # Extract extension from filename
    if "." not in filename:
        raise ValidationError("File must have an extension")

    extension = filename.rsplit(".", 1)[1].lower()
    allowed_types = [t.lower() for t in settings.ALLOWED_FILE_TYPES]

    if extension not in allowed_types:
        raise ValidationError(
            f"File type '{extension}' is not allowed. Allowed types: {', '.join(allowed_types)}"
        )

    # Optional: validate content_type matches extension
    if content_type:
        # Basic content type validation (can be expanded)
        content_type_map = {
            "csv": ["text/csv", "application/csv"],
            "json": ["application/json", "text/json"],
            "parquet": ["application/parquet", "application/x-parquet"],
            "txt": ["text/plain"],
            "xlsx": ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"],
            "xls": ["application/vnd.ms-excel"],
        }

        expected_types = content_type_map.get(extension, [])
        if expected_types and content_type not in expected_types:
            # Warning, not error - content_type can be unreliable
            pass


def get_chunk_size(file_size: int) -> int:
    """
    Calculate recommended chunk size for multipart upload.

    Args:
        file_size: Total file size in bytes

    Returns:
        Recommended chunk size in bytes (minimum 5MB, maximum 100MB)
    """
    # Use 5MB chunks for files < 100MB
    # Use 10MB chunks for files 100MB - 1GB
    # Use 50MB chunks for files 1GB - 5GB
    # Use 100MB chunks for files > 5GB

    if file_size < 100 * 1024 * 1024:  # < 100MB
        return 5 * 1024 * 1024  # 5MB
    elif file_size < 1024 * 1024 * 1024:  # < 1GB
        return 10 * 1024 * 1024  # 10MB
    elif file_size < 5 * 1024 * 1024 * 1024:  # < 5GB
        return 50 * 1024 * 1024  # 50MB
    else:
        return 100 * 1024 * 1024  # 100MB


def calculate_chunk_count(file_size: int, chunk_size: int | None = None) -> int:
    """
    Calculate number of chunks needed for file upload.

    Args:
        file_size: Total file size in bytes
        chunk_size: Chunk size in bytes (optional, will be calculated if not provided)

    Returns:
        Number of chunks needed
    """
    if chunk_size is None:
        chunk_size = get_chunk_size(file_size)

    return (file_size + chunk_size - 1) // chunk_size  # Ceiling division
