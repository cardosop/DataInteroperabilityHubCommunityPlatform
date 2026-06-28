"""
Test Factories for Files

Real factories (not mocks) for creating test data for File models.
"""

import hashlib
import uuid
from typing import Any

from django.contrib.auth import get_user_model

from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.tenants.models import Tenant

User = get_user_model()


class FileFactory:
    """Factory for creating File instances"""

    @staticmethod
    def create_file(
        tenant: Tenant,
        name: str | None = None,
        content_type: str | None = None,
        size: int | None = None,
        content_sha256: str | None = None,
        storage_path: str | None = None,
        status: FileStatus = FileStatus.ACTIVE,
        metadata_json: dict[str, Any] | None = None,
        created_by: User | None = None,
        **kwargs,
    ) -> File:
        """
        Create a File instance.

        Args:
            tenant: Tenant instance (required)
            name: Original filename (default: auto-generated)
            content_type: MIME type (default: text/csv)
            size: File size in bytes (default: 1024)
            content_sha256: SHA-256 hash (default: auto-generated)
            storage_path: Path in S3-compatible storage (default: auto-generated)
            status: File status (default: ACTIVE)
            metadata_json: Additional metadata
            created_by: User who uploaded the file
            **kwargs: Additional fields

        Returns:
            File instance
        """
        if name is None:
            name = f"test-file-{uuid.uuid4().hex[:8]}.csv"

        if content_type is None:
            content_type = "text/csv"

        if size is None:
            size = 1024

        if content_sha256 is None:
            # Generate a fake SHA-256 hash for testing
            fake_content = f"test-content-{uuid.uuid4().hex}"
            content_sha256 = hashlib.sha256(fake_content.encode()).hexdigest()

        if storage_path is None:
            storage_path = f"test/{tenant.slug}/{name}"

        if metadata_json is None:
            metadata_json = {"upload_method": "browser", "chunk_count": 1}

        scan_status = kwargs.pop("scan_status", None)
        if scan_status is None:
            if status == FileStatus.ACTIVE:
                scan_status = FileScanStatus.CLEAN
            else:
                scan_status = FileScanStatus.PENDING_SCAN

        return File.objects.create(
            tenant=tenant,
            name=name,
            content_type=content_type,
            size=size,
            content_sha256=content_sha256,
            storage_path=storage_path,
            status=status,
            scan_status=scan_status,
            metadata_json=metadata_json,
            created_by=created_by,
            **kwargs,
        )

    @staticmethod
    def create_file_with_all_statuses(tenant: Tenant, created_by: User | None = None) -> list[File]:
        """
        Create File instances with all possible statuses.

        Args:
            tenant: Tenant instance
            created_by: User who uploaded the files

        Returns:
            List of File instances
        """
        files = []
        for status in FileStatus:
            files.append(
                FileFactory.create_file(tenant=tenant, status=status, created_by=created_by)
            )
        return files

    @staticmethod
    def create_large_file(
        tenant: Tenant, size_mb: int = 100, created_by: User | None = None, **kwargs
    ) -> File:
        """
        Create a large file for testing.

        Args:
            tenant: Tenant instance
            size_mb: File size in megabytes (default: 100)
            created_by: User who uploaded the file
            **kwargs: Additional fields

        Returns:
            File instance
        """
        size_bytes = size_mb * 1024 * 1024
        return FileFactory.create_file(
            tenant=tenant,
            size=size_bytes,
            metadata_json={"upload_method": "multipart", "chunk_count": 10, "size_mb": size_mb},
            created_by=created_by,
            **kwargs,
        )
