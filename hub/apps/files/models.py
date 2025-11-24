"""
File Storage Models

File model for managing uploaded files with S3-compatible storage.
"""
import uuid
import hashlib
from django.db import models
from django.conf import settings
from django.core.validators import FileExtensionValidator


class FileStatus(models.TextChoices):
    """File status enumeration"""
    PENDING = "PENDING", "Pending"
    UPLOADING = "UPLOADING", "Uploading"
    ACTIVE = "ACTIVE", "Active"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"
    DELETED = "DELETED", "Deleted"


class File(models.Model):
    """
    File model for managing uploaded files.
    
    Files are stored in S3-compatible storage (MinIO for dev, S3/GCS/Azure for prod).
    Content is hashed with SHA-256 for deduplication and integrity verification.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="files",
        help_text="Tenant this file belongs to"
    )
    name = models.CharField(
        max_length=255,
        help_text="Original filename"
    )
    content_type = models.CharField(
        max_length=100,
        help_text="MIME type (e.g., text/csv, application/json)"
    )
    size = models.BigIntegerField(
        help_text="File size in bytes"
    )
    content_sha256 = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        db_index=True,
        help_text="SHA-256 hash of file content (for deduplication and integrity)"
    )
    storage_path = models.CharField(
        max_length=500,
        help_text="Path in S3-compatible storage (bucket/key)"
    )
    status = models.CharField(
        max_length=20,
        choices=FileStatus.choices,
        default=FileStatus.PENDING,
        help_text="File status: PENDING, UPLOADING, ACTIVE, FAILED, DELETED"
    )
    metadata_json = models.JSONField(
        default=dict,
        help_text="Additional metadata (upload method, chunk info, etc.)"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="uploaded_files",
        null=True,
        blank=True,
        help_text="User who uploaded the file"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "files"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "created_at"]),
            models.Index(fields=["content_sha256"]),
            models.Index(fields=["status"]),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.size} bytes, {self.status})"
    
    @staticmethod
    def calculate_sha256(file_obj) -> str:
        """
        Calculate SHA-256 hash of file content.
        
        Args:
            file_obj: File-like object (open file, BytesIO, etc.)
        
        Returns:
            SHA-256 hash as hexadecimal string
        """
        sha256_hash = hashlib.sha256()
        # Reset file pointer to beginning
        file_obj.seek(0)
        # Read file in chunks to handle large files
        for chunk in iter(lambda: file_obj.read(4096), b""):
            sha256_hash.update(chunk)
        file_obj.seek(0)  # Reset again
        return sha256_hash.hexdigest()
    
    def is_active(self) -> bool:
        """Check if file is active"""
        return self.status == FileStatus.ACTIVE
    
    def is_uploading(self) -> bool:
        """Check if file is currently being uploaded"""
        return self.status == FileStatus.UPLOADING
    
    def can_download(self) -> bool:
        """Check if file can be downloaded"""
        return self.status == FileStatus.ACTIVE

