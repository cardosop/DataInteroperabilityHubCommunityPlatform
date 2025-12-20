"""
File Service

Business logic for file operations.
"""
from typing import Dict, Any, Optional
from django.db import transaction

from hub.apps.core.services.base import BaseService, ValidationError, NotFoundError
from hub.apps.files.models import File, FileStatus


class FileService(BaseService):
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

        return self.execute_with_metrics(
            operation="get_file",
            tenant_id=effective_tenant_id,
            func=lambda: self.get_resource_or_raise(
                File,
                file_id,
                tenant_id=effective_tenant_id
            )
        )

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

            if not file_obj.is_active():
                from hub.apps.core.exceptions import ServiceValidationError
                raise ServiceValidationError(
                    f"File is not active (status: {file_obj.status})",
                    details={"file_id": file_id, "status": file_obj.status}
                )

            return file_obj

        return self.execute_with_metrics(
            operation="validate_file_active",
            tenant_id=effective_tenant_id,
            func=_validate
        )

