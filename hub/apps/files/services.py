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
from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.files.business_rules import FilesBusinessRules


class FileService(BaseService, FileEventPublisher):
    """
    Service for file operations.

    Provides business logic for retrieving and validating files.
    """
    service_name = "file_service"

    def __init__(self, tenant_id: Optional[str] = None, user_id: Optional[str] = None, request_id: Optional[str] = None):
        """Initialize FileService."""
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.request_id = request_id
        FileEventPublisher.__init__(self)

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

        # Publish file.downloaded event (file retrieval is treated as download).
        # Wrapped in transaction.atomic() to isolate potential DB errors from the
        # caller's transaction (prevents needs_rollback cascade).
        try:
            from django.db import transaction as _tx

            with _tx.atomic():
                download_duration_ms = int((time.time() - start_time) * 1000)
                self.publish_file_downloaded(
                    file_id=file_id,
                    download_duration_ms=download_duration_ms,
                    download_size=file_obj.size
                )
        except Exception as e:
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
                from django.db import transaction as _tx

                with _tx.atomic():
                    self.publish_file_updated(
                        file_id=str(file_id),
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
            # Plan limit enforcement (storage — delta is file size in bytes,
            # the limit check converts to GB internally).
            # Must be inside _create() so it runs within execute_with_transaction's
            # transaction.atomic() scope (select_for_update requires active transaction).
            from hub.apps.tenants.services import PlanLimitService
            plan_limit_service = PlanLimitService(tenant_id=tenant_id)
            plan_limit_service.check_limit(
                tenant_id=tenant_id,
                limit_key="max_storage_gb",
                delta=size,
            )

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
            # Publish events when completing upload (status -> ACTIVE).
            # IMPORTANT: wrapped in its own transaction.atomic() savepoint so that
            # if event publishing does a DB operation that fails (e.g. deduplication
            # store), the failure is contained in this savepoint.  Without this,
            # a caught DB error sets needs_rollback=True which cascades outward
            # via validate_no_broken_transaction(), corrupting the connection for
            # all subsequent queries in the same request cycle.
            if new_status == FileStatus.ACTIVE and content_sha256:
                try:
                    from django.db import transaction as _tx
                    from django.utils import timezone

                    with _tx.atomic():
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

            # Malware scan after any terminal upload-with-hash (ACTIVE or COMPLETED).
            scan_after_upload = bool(
                content_sha256
                and new_status in (FileStatus.ACTIVE, FileStatus.COMPLETED)
            )
            if scan_after_upload:
                from django.conf import settings as dj_settings
                from django.db import transaction as dj_transaction
                from django.utils import timezone as dj_timezone

                if not getattr(dj_settings, "CLAMAV_ENABLED", True):
                    file_obj.refresh_from_db()
                    file_obj.scan_status = FileScanStatus.SCAN_UNAVAILABLE
                    file_obj.scanned_at = dj_timezone.now()
                    file_obj.save(update_fields=["scan_status", "scanned_at", "updated_at"])
                    try:
                        from hub.apps.audit.utils import create_audit_event

                        create_audit_event(
                            resource_type="FILE",
                            action="FILE_MALWARE_SCAN_SKIPPED",
                            tenant=file_obj.tenant,
                            resource_id=str(file_obj.id),
                            result="WARNING",
                            details={"reason": "CLAMAV_DISABLED"},
                        )
                    except Exception as audit_exc:
                        import structlog

                        structlog.get_logger(__name__).warning(
                            "audit_file_malware_scan_skipped_failed",
                            file_id=str(file_obj.id),
                            error=str(audit_exc),
                        )
                else:
                    fid = str(file_obj.id)

                    def _enqueue_scan() -> None:
                        from hub.apps.files.tasks import enqueue_file_malware_scan

                        enqueue_file_malware_scan(fid)

                    dj_transaction.on_commit(_enqueue_scan)
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

