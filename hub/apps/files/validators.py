"""
File Validation Utilities

Validates file size, type, and other constraints.
"""
from django.core.exceptions import ValidationError
from django.conf import settings
from typing import Optional


def validate_file_size(size: int, upload_method: str = "browser", tenant_id: Optional[str] = None) -> None:
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

