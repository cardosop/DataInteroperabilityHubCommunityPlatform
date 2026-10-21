"""
File Storage Models

File model for managing uploaded files with S3-compatible storage.
"""

import hashlib
import uuid

from django.conf import settings
from django.db import models


class FileStatus(models.TextChoices):
    """File status enumeration.

    Phase 260.6.A: ``COMPLETED`` retired — rows with the legacy
    ``COMPLETED`` status were rewritten to ``ACTIVE`` by migration
    ``0009_drop_completed_file_status``, and a DB CHECK constraint
    (``file_status_no_completed``) forbids new writes.
    """

    PENDING = "PENDING", "Pending"
    UPLOADING = "UPLOADING", "Uploading"
    ACTIVE = "ACTIVE", "Active"
    FAILED = "FAILED", "Failed"
    DELETED = "DELETED", "Deleted"
    DELETING = "DELETING", "Deleting"


class FileScanStatus(models.TextChoices):
    """Malware scan state (separate from upload lifecycle FileStatus)."""

    PENDING_SCAN = "PENDING_SCAN", "Pending scan"
    CLEAN = "CLEAN", "Clean"
    INFECTED = "INFECTED", "Infected"
    SCAN_UNAVAILABLE = "SCAN_UNAVAILABLE", "Scan unavailable"
    SCAN_ERROR = "SCAN_ERROR", "Scan error"

    @staticmethod
    def _default_scan_status() -> str:
        """Default ``File.scan_status`` for new rows (migration 0016).

        Returns ``PENDING_SCAN`` — a freshly-created file awaits its
        ClamAV scan. Defined as a callable (rather than a literal) so the
        ``0016_alter_file_scan_status_default`` migration and the model
        field deconstruct to one shared source of truth.
        """
        return FileScanStatus.PENDING_SCAN


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
        help_text="Tenant this file belongs to",
    )
    name = models.CharField(max_length=255, help_text="Original filename")
    content_type = models.CharField(
        max_length=100, help_text="MIME type (e.g., text/csv, application/json)"
    )
    size = models.BigIntegerField(help_text="File size in bytes")
    content_sha256 = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        db_index=True,
        help_text="SHA-256 hash of file content (for deduplication and integrity)",
    )
    storage_path = models.CharField(
        max_length=500, help_text="Path in S3-compatible storage (bucket/key)"
    )
    status = models.CharField(
        max_length=20,
        choices=FileStatus.choices,
        default=FileStatus.PENDING,
        help_text="File status: PENDING, UPLOADING, ACTIVE, FAILED, DELETED",
    )
    scan_status = models.CharField(
        max_length=32,
        choices=FileScanStatus.choices,
        default=FileScanStatus._default_scan_status,
        db_index=True,
        help_text="Malware scan status (ClamAV); independent of upload status",
    )
    scanned_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the last malware scan finished (any outcome)",
    )
    metadata_json = models.JSONField(
        default=dict, help_text="Additional metadata (upload method, chunk info, etc.)"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="uploaded_files",
        null=True,
        blank=True,
        help_text="User who uploaded the file",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, help_text="Soft-delete timestamp")

    class Meta:
        db_table = "files"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "scan_status"]),
            models.Index(fields=["tenant", "created_at"]),
            models.Index(fields=["content_sha256"]),
            models.Index(fields=["status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name"],
                condition=models.Q(status="ACTIVE"),
                name="unique_active_filename_per_tenant",
            ),
        ]

    def save(self, *args, **kwargs):
        """Validate metadata_json size before persisting.

        Raises:
            ServiceValidationError: When metadata_json exceeds the storage cap
                (code=FILE_METADATA_TOO_LARGE, http_status=400).
        """
        from .metadata_validators import validate_metadata_json_size

        validate_metadata_json_size(self.metadata_json)
        super().save(*args, **kwargs)

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
        """Check if file is in a terminal usable state."""
        return self.status in (FileStatus.ACTIVE,)

    def is_uploading(self) -> bool:
        """Check if file is currently being uploaded"""
        return self.status == FileStatus.UPLOADING

    def can_download(self) -> bool:
        """Check if file can be downloaded (lifecycle + malware scan)."""
        if self.status != FileStatus.ACTIVE:
            return False
        return self.scan_status not in (
            FileScanStatus.PENDING_SCAN,
            FileScanStatus.INFECTED,
        )
