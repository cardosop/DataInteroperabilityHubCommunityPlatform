"""
File Service

Business logic for file operations.
"""
import uuid
import time
from typing import Dict, Any, Optional

from django.db import transaction

from hub.apps.core.services.base import BaseService, ValidationError, NotFoundError
from hub.apps.core.events.service_publishers import FileEventPublisher
from hub.apps.files.models import File, FileStatus
from hub.apps.files.business_rules import FilesBusinessRules


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
                raise ValidationError(
                    f"File is not active (status: {file_obj.status})",
                    code="VALIDATION_ERROR",
                    details={"file_id": file_id, "status": file_obj.status},
                )

            # Publish file.updated event if status changed (e.g., from PENDING to ACTIVE)
            # Note: This is a read operation, so status shouldn't change, but we track access
            # In practice, status changes happen during upload operations, not here
            # We'll publish an event for validation tracking purposes
            try:
                self.publish_file_updated(
                    file_id=str(file_id),  # Ensure file_id is a string (not UUID)
                    changes={
                        "validation": {
                            "old": None,
                            "new": "validated_active"
                        }
                    },
                    previous_status=previous_status.value if hasattr(previous_status, 'value') else str(previous_status),
                    new_status=file_obj.status.value if hasattr(file_obj.status, 'value') else str(file_obj.status)
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

    def create_file(
        self,
        tenant_id: str,
        user_id: Optional[str],
        name: str,
        content_type: str,
        size: int,
        upload_method: str = "browser",
        created_by_id: Optional[str] = None,
    ) -> File:
        """
        Create a file record (init upload). Runs FilesBusinessRules.validate_file_for_create
        before creating; on invalid, raises ValidationError with code BUSINESS_RULES_VALIDATION.

        Returns:
            Created File instance (status=PENDING).
        """
        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import User

        tenant = self.get_resource_or_raise(Tenant, tenant_id)
        user = None
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                pass

        rules = FilesBusinessRules(tenant_id=tenant_id, user_id=user_id)
        result = rules.validate_file_for_create(
            tenant=tenant,
            name=name,
            size=size,
            content_type=content_type,
            upload_method=upload_method,
            user=user,
        )
        if not result.is_valid:
            raise ValidationError(
                "; ".join(result.errors),
                code="BUSINESS_RULES_VALIDATION",
                details=result.details,
            )

        file_id = uuid.uuid4()
        storage_path = f"{tenant_id}/{file_id}/{name}"
        metadata_json = {
            "upload_method": upload_method,
            "chunk_size": None,
            "chunk_count": None,
            "multipart_upload_id": None,
        }

        def _create():
            file_obj = File.objects.create(
                id=file_id,
                tenant_id=tenant_id,
                name=name,
                content_type=content_type,
                size=size,
                storage_path=storage_path,
                status=FileStatus.PENDING,
                created_by_id=created_by_id or user_id,
                metadata_json=metadata_json,
            )
            try:
                self.publish_file_created(
                    file_id=str(file_obj.id),
                    name=file_obj.name,
                    content_type=file_obj.content_type,
                    size=file_obj.size,
                    status=file_obj.status,
                    content_sha256=file_obj.content_sha256,
                )
            except Exception as e:
                import structlog
                log = structlog.get_logger(__name__)
                log.warning("Failed to publish file.created", file_id=str(file_obj.id), error=str(e))
            return file_obj

        return self.execute_with_transaction(
            operation="create_file",
            tenant_id=tenant_id,
            func=_create,
        )

    def update_file(
        self,
        file_id: str,
        tenant_id: str,
        user_id: Optional[str],
        content_sha256: Optional[str] = None,
        new_status: Optional[str] = None,
    ) -> File:
        """
        Update file (e.g. complete upload). Runs FilesBusinessRules.validate_file_for_update
        before updating; on invalid, raises ValidationError with code BUSINESS_RULES_VALIDATION.

        Returns:
            Updated File instance.
        """
        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import User

        file_obj = self.get_resource_or_raise(File, file_id, tenant_id=tenant_id)
        tenant = self.get_resource_or_raise(Tenant, tenant_id)
        user = None
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                pass

        rules = FilesBusinessRules(tenant_id=tenant_id, user_id=user_id)
        result = rules.validate_file_for_update(
            file=file_obj,
            tenant=tenant,
            user=user,
            new_status=new_status,
        )
        if not result.is_valid:
            raise ValidationError(
                "; ".join(result.errors),
                code="BUSINESS_RULES_VALIDATION",
                details=result.details,
            )

        def _update():
            file_obj.refresh_from_db()
            previous_status = file_obj.status
            updates = {}
            if content_sha256 is not None:
                file_obj.content_sha256 = content_sha256
                updates["content_sha256"] = content_sha256
            if new_status is not None:
                file_obj.status = new_status
                updates["status"] = new_status
            if updates:
                file_obj.save(update_fields=list(updates.keys()) + ["updated_at"])
            # Publish events when completing upload (status -> ACTIVE)
            if new_status == FileStatus.ACTIVE and content_sha256:
                try:
                    from django.utils import timezone
                    upload_start = file_obj.created_at.timestamp() if file_obj.created_at else None
                    upload_duration_ms = int((timezone.now().timestamp() - upload_start) * 1000) if upload_start else None
                    self.publish_file_uploaded(
                        file_id=str(file_obj.id),
                        file_size=file_obj.size,
                        content_type=file_obj.content_type,
                        upload_duration_ms=upload_duration_ms,
                        content_sha256=file_obj.content_sha256,
                    )
                    self.publish_file_updated(
                        file_id=str(file_obj.id),
                        changes={
                            "status": {"old": previous_status, "new": FileStatus.ACTIVE},
                            "content_sha256": {"old": None, "new": content_sha256},
                        },
                        previous_status=previous_status.value if hasattr(previous_status, "value") else str(previous_status),
                        new_status=FileStatus.ACTIVE.value if hasattr(FileStatus.ACTIVE, "value") else str(FileStatus.ACTIVE),
                    )
                except Exception as e:
                    import structlog
                    log = structlog.get_logger(__name__)
                    log.warning("Failed to publish file.uploaded/updated", file_id=str(file_obj.id), error=str(e))
            return file_obj

        return self.execute_with_transaction(
            operation="update_file",
            tenant_id=tenant_id,
            func=_update,
        )

    def delete_file(
        self,
        file_id: str,
        tenant_id: str,
        user_id: Optional[str],
    ) -> None:
        """
        Soft-delete file and remove from storage. Runs FilesBusinessRules.validate_file_for_destroy
        before deleting; on invalid, raises ValidationError with code BUSINESS_RULES_VALIDATION.
        """
        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import User
        from hub.apps.files.storage import S3StorageClient

        file_obj = self.get_resource_or_raise(File, file_id, tenant_id=tenant_id)
        tenant = self.get_resource_or_raise(Tenant, tenant_id)
        user = None
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                pass

        rules = FilesBusinessRules(tenant_id=tenant_id, user_id=user_id)
        result = rules.validate_file_for_destroy(
            file=file_obj,
            tenant=tenant,
            user=user,
        )
        if not result.is_valid:
            raise ValidationError(
                "; ".join(result.errors),
                code="BUSINESS_RULES_VALIDATION",
                details=result.details,
            )

        def _delete():
            file_obj.refresh_from_db()
            try:
                storage_client = S3StorageClient()
                storage_client.delete_file(file_obj.storage_path)
            except Exception:
                pass
            file_obj.status = FileStatus.DELETED
            file_obj.save(update_fields=["status", "updated_at"])
            try:
                self.publish_file_deleted(
                    file_id=str(file_obj.id),
                    reason="User requested deletion",
                )
            except Exception as e:
                import structlog
                log = structlog.get_logger(__name__)
                log.warning("Failed to publish file.deleted", file_id=str(file_obj.id), error=str(e))

        self.execute_with_transaction(
            operation="delete_file",
            tenant_id=tenant_id,
            func=_delete,
        )

