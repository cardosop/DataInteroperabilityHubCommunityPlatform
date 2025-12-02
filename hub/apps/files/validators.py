"""
File Validation Utilities

Validates file size, type, and other constraints.
"""
from django.core.exceptions import ValidationError
from django.conf import settings
from typing import Optional


def validate_file_size(size: int, upload_method: str = "browser") -> None:
    """
    Validate file size against limits.
    
    Args:
        size: File size in bytes (0 is allowed for empty files)
        upload_method: "browser" or "sdk"
    
    Raises:
        ValidationError if file size exceeds limits
    """
    # Allow empty files (size=0)
    if size < 0:
        raise ValidationError("File size cannot be negative")
    
    if upload_method == "browser":
        max_size = settings.MAX_BROWSER_UPLOAD_SIZE
        limit_name = "browser upload limit"
    elif upload_method == "sdk":
        max_size = settings.MAX_SDK_UPLOAD_SIZE
        limit_name = "SDK upload limit"
    else:
        max_size = settings.MAX_FILE_SIZE
        limit_name = "global file size limit"
    
    # Also check global max (skip for empty files)
    if size > 0 and size > settings.MAX_FILE_SIZE:
        raise ValidationError(
            f"File size ({size} bytes) exceeds global maximum ({settings.MAX_FILE_SIZE} bytes)"
        )
    
    if size > 0 and size > max_size:
        raise ValidationError(
            f"File size ({size} bytes) exceeds {limit_name} ({max_size} bytes)"
        )


def validate_file_type(filename: str, content_type: Optional[str] = None) -> None:
    """
    Validate file type against allowed types.
    
    Args:
        filename: Original filename
        content_type: MIME type (optional)
    
    Raises:
        ValidationError if file type is not allowed
    """
    # Extract extension from filename
    if '.' not in filename:
        raise ValidationError("File must have an extension")
    
    extension = filename.rsplit('.', 1)[1].lower()
    allowed_types = [t.lower() for t in settings.ALLOWED_FILE_TYPES]
    
    if extension not in allowed_types:
        raise ValidationError(
            f"File type '{extension}' is not allowed. Allowed types: {', '.join(allowed_types)}"
        )
    
    # Optional: validate content_type matches extension
    if content_type:
        # Basic content type validation (can be expanded)
        content_type_map = {
            'csv': ['text/csv', 'application/csv'],
            'json': ['application/json', 'text/json'],
            'parquet': ['application/parquet', 'application/x-parquet'],
            'txt': ['text/plain'],
            'xlsx': ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'],
            'xls': ['application/vnd.ms-excel'],
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


def calculate_chunk_count(file_size: int, chunk_size: Optional[int] = None) -> int:
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

