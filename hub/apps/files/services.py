"""
File Service

Business logic for file operations.
"""
from typing import Dict, Any, Optional
from django.db import transaction
import time

from hub.apps.core.services.base import BaseService, ValidationError, NotFoundError
from hub.apps.core.events.service_publishers import FileEventPublisher
from hub.apps.files.models import File, FileStatus


class FileService(BaseService, FileEventPublisher):
    """
    Service for file operations.

    Provides business logic for retrieving and validating files.
    """
    service_name = "file_service"

    def get_file(
        self,
        file_id: str,
        tenant_id: Optional[str] = None
    ) -> File:
        """
        Get file by ID.

        Args:
            file_id: File ID
            tenant_id: Tenant ID (uses service tenant_id if not provided)

        Returns:
            File instance

        Raises:
            NotFoundError: If file not found
        """
        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        start_time = time.time()
        file_obj = self.execute_with_metrics(
            operation="get_file",
            tenant_id=effective_tenant_id,
            func=lambda: self.get_resource_or_raise(
                File,
                file_id,
                tenant_id=effective_tenant_id
            )
        )

        # Publish file.downloaded event (file retrieval is treated as download)
        try:
            download_duration_ms = int((time.time() - start_time) * 1000)
            self.publish_file_downloaded(
                file_id=file_id,
                download_duration_ms=download_duration_ms,
                download_size=file_obj.size
            )
        except Exception as e:
            # Log but don't fail file retrieval if event publishing fails
            import structlog
            logger = structlog.get_logger(__name__)
            logger.warning(
                f"Failed to publish file.downloaded event for file {file_id}: {e}",
                extra={
                    "file_id": file_id,
                    "tenant_id": effective_tenant_id,
                    "error": str(e)
                },
                exc_info=True
            )

        return file_obj

    def validate_file_active(
        self,
        file_id: str,
        tenant_id: Optional[str] = None
    ) -> File:
        """
        Validate that file exists and is active.

        Args:
            file_id: File ID
            tenant_id: Tenant ID

        Returns:
            File instance

        Raises:
            NotFoundError: If file not found
            ValidationError: If file is not active
        """
        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        def _validate():
            file_obj = self.get_resource_or_raise(
                File,
                file_id,
                tenant_id=effective_tenant_id
            )

            previous_status = file_obj.status

            if not file_obj.is_active():
                from hub.apps.core.exceptions import ServiceValidationError
                raise ServiceValidationError(
                    f"File is not active (status: {file_obj.status})",
                    details={"file_id": file_id, "status": file_obj.status}
                )

            # Publish file.updated event if status changed (e.g., from PENDING to ACTIVE)
            # Note: This is a read operation, so status shouldn't change, but we track access
            # In practice, status changes happen during upload operations, not here
            # We'll publish an event for validation tracking purposes
            try:
                self.publish_file_updated(
                    file_id=file_id,
                    changes={
                        "validation": {
                            "old": None,
                            "new": "validated_active"
                        }
                    },
                    previous_status=previous_status,
                    new_status=file_obj.status
                )
            except Exception as e:
                # Log but don't fail validation if event publishing fails
                import structlog
                logger = structlog.get_logger(__name__)
                logger.warning(
                    f"Failed to publish file.updated event for file {file_id}: {e}",
                    extra={
                        "file_id": file_id,
                        "tenant_id": effective_tenant_id,
                        "error": str(e)
                    },
                    exc_info=True
                )

            return file_obj

        return self.execute_with_metrics(
            operation="validate_file_active",
            tenant_id=effective_tenant_id,
            func=_validate
        )

