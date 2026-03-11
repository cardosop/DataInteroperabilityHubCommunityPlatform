"""
GDPR Services

Service layer for data portability and erasure operations.
"""

import io
import json
import zipfile
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import structlog
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from hub.apps.core.services.base import BaseService, NotFoundError, ValidationError
from hub.apps.files.storage import S3StorageClient
from hub.apps.gdpr.models import (
    DataExportJob,
    DataExportStatus,
    ErasureRequest,
    ErasureRequestStatus,
)

logger = structlog.get_logger(__name__)


class DataPortabilityService(BaseService):
    """
    Service for data portability (GDPR Article 20).

    Provides business logic for:
    - Creating data export jobs
    - Collecting user data
    - Building export archives
    - Generating download URLs
    """

    service_name = "data_portability_service"

    def __init__(self, tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        """
        Initialize DataPortabilityService.

        Args:
            tenant_id: Optional tenant ID
            user_id: Optional user ID
        """
        self.tenant_id = tenant_id
        self.user_id = user_id

    @transaction.atomic
    def create_export_job(self, user_id: str) -> DataExportJob:
        """
        Create a data export job for a user.

        Args:
            user_id: User ID requesting export

        Returns:
            Created DataExportJob instance
        """

        def _create():
            from hub.apps.users.models import User

            user = self.get_resource_or_raise(User, user_id)

            # Check for existing pending/processing job
            existing = DataExportJob.objects.filter(
                user=user, status__in=[DataExportStatus.PENDING, DataExportStatus.PROCESSING]
            ).first()

            if existing:
                raise ValidationError(
                    "Export job already in progress",
                    code="EXPORT_IN_PROGRESS",
                    details={"job_id": str(existing.id)},
                )

            # Create export job
            job = DataExportJob.objects.create(
                user=user, tenant=user.tenant, status=DataExportStatus.PENDING
            )

            # Process job asynchronously (in production, use Celery/django-rq)
            # For now, process synchronously
            try:
                self._process_export_job(job)
            except Exception as e:
                logger.error(
                    "data_export_job_failed",
                    job_id=str(job.id),
                    user_id=str(user_id),
                    error=str(e),
                    exc_info=True,
                    message=f"Failed to process export job: {e}",
                )
                job.status = DataExportStatus.FAILED
                job.error_message = str(e)
                job.save()

            return job

        return self.execute_with_metrics(
            operation="create_export_job", tenant_id=self.tenant_id, func=_create
        )

    def _process_export_job(self, job: DataExportJob):
        """
        Process export job: collect data, build archive, upload to storage.

        Args:
            job: DataExportJob instance
        """
        job.status = DataExportStatus.PROCESSING
        job.save()

        try:
            # Collect user data
            export_data = self._collect_user_data(job.user)

            # Build archive
            archive_bytes = self._build_archive(export_data, job.user)

            # Upload to storage
            storage_path = self._upload_archive(job, archive_bytes)

            # Generate signed download URL (24 hour expiry)
            download_url = self._generate_download_url(storage_path, expires_in=86400)

            job.status = DataExportStatus.COMPLETED
            job.storage_path = storage_path
            job.download_url = download_url
            job.download_url_expires_at = timezone.now() + timedelta(seconds=86400)
            job.completed_at = timezone.now()
            job.save()

            logger.info(
                "data_export_job_completed",
                job_id=str(job.id),
                user_id=str(job.user.id),
                storage_path=storage_path,
                message=f"Data export job {job.id} completed successfully",
            )

        except Exception as e:
            logger.error(
                "data_export_job_processing_failed",
                job_id=str(job.id),
                error=str(e),
                exc_info=True,
                message=f"Failed to process export job: {e}",
            )
            job.status = DataExportStatus.FAILED
            job.error_message = str(e)
            job.save()
            raise

    def _collect_user_data(self, user) -> Dict[str, Any]:
        """
        Collect all user data for export.

        Args:
            user: User instance

        Returns:
            Dictionary containing all user data
        """
        data = {
            "user_profile": {
                "id": str(user.id),
                "email": user.email,
                "display_name": user.display_name,
                "status": user.status,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "updated_at": user.updated_at.isoformat() if user.updated_at else None,
            },
            "audit_events": [],
            "assets": [],
            "datasets": [],
            "contracts": [],
        }

        # Collect audit events
        from hub.apps.audit.models import AuditEvent

        audit_events = AuditEvent.objects.filter(actor_user=user).order_by("-timestamp")[
            :1000
        ]  # Limit to recent 1000 events

        for event in audit_events:
            data["audit_events"].append(
                {
                    "id": str(event.id),
                    "resource_type": event.resource_type,
                    "action": event.action,
                    "resource_id": event.resource_id,
                    "details": event.details_json,
                    "created_at": event.timestamp.isoformat() if event.timestamp else None,
                }
            )

        # Collect assets (metadata only)
        from hub.apps.assets.models import Asset

        assets = Asset.objects.filter(tenant=user.tenant, created_by=user)

        for asset in assets:
            data["assets"].append(
                {
                    "id": str(asset.id),
                    "name": asset.name,
                    "description": asset.description,
                    "status": asset.status,
                    "created_at": asset.created_at.isoformat() if asset.created_at else None,
                }
            )

        # Collect datasets (metadata only)
        from hub.apps.datasets.models import Dataset

        datasets = Dataset.objects.filter(tenant=user.tenant, created_by=user)

        for dataset in datasets:
            # Dataset has no name/description/status; derive label from asset/file
            label = None
            if dataset.asset:
                label = dataset.asset.name
            elif dataset.file:
                label = dataset.file.name
            if not label:
                label = str(dataset.id)
            data["datasets"].append(
                {
                    "id": str(dataset.id),
                    "name": label,
                    "format": dataset.format,
                    "created_at": dataset.created_at.isoformat() if dataset.created_at else None,
                }
            )

        # Collect contracts (metadata only)
        from hub.apps.contracts.models import Contract

        contracts = Contract.objects.filter(tenant=user.tenant, created_by=user)

        for contract in contracts:
            # Contract has no name; derive label from asset or id
            label = contract.asset.name if contract.asset else f"Contract {contract.id}"
            data["contracts"].append(
                {
                    "id": str(contract.id),
                    "name": label,
                    "status": contract.status,
                    "created_at": contract.created_at.isoformat() if contract.created_at else None,
                }
            )

        return data

    def _build_archive(self, data: Dict[str, Any], user) -> bytes:
        """
        Build ZIP archive from user data.

        Args:
            data: User data dictionary
            user: User instance

        Returns:
            Archive bytes
        """
        archive_buffer = io.BytesIO()

        with zipfile.ZipFile(archive_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            # Add main data file (JSON)
            json_data = json.dumps(data, indent=2, default=str)
            zip_file.writestr("user_data.json", json_data)

            # Add README
            readme = f"""Data Export for {user.email}
Generated: {timezone.now().isoformat()}

This archive contains:
- user_data.json: Complete user profile and metadata
- README.txt: This file

Note: This export contains metadata only. Actual file contents are not included
for privacy and storage reasons. Contact support if you need file contents.
"""
            zip_file.writestr("README.txt", readme)

        archive_buffer.seek(0)
        return archive_buffer.read()

    def _upload_archive(self, job: DataExportJob, archive_bytes: bytes) -> str:
        """
        Upload archive to storage.

        Args:
            job: DataExportJob instance
            archive_bytes: Archive file bytes

        Returns:
            Storage path
        """
        storage_client = S3StorageClient()
        storage_client._ensure_bucket_exists()

        # Generate storage path
        storage_path = f"data-exports/{job.user.tenant.id}/{job.id}/export.zip"

        # Upload to storage
        import boto3
        from botocore.config import Config

        import os
        import sys

        _is_test = (
            "pytest" in sys.modules
            or "unittest" in sys.modules
            or os.getenv("PYTEST_CURRENT_TEST")
            or os.getenv("TESTING")
            or getattr(settings, "TESTING", False)
        )
        _connect_timeout = 10 if _is_test else 60
        _read_timeout = 30 if _is_test else 60
        s3_config = Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            retries={"max_attempts": 2 if _is_test else 3, "mode": "standard"},
            connect_timeout=_connect_timeout,
            read_timeout=_read_timeout,
        )

        s3_client = boto3.client(
            "s3",
            endpoint_url=storage_client.endpoint_url,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            use_ssl=storage_client.use_ssl,
            verify=getattr(settings, "AWS_S3_VERIFY", True),
            config=s3_config,
        )

        s3_client.put_object(
            Bucket=storage_client.bucket_name,
            Key=storage_path,
            Body=archive_bytes,
            ContentType="application/zip",
        )

        return storage_path

    def _generate_download_url(self, storage_path: str, expires_in: int = 86400) -> str:
        """
        Generate signed download URL.

        Args:
            storage_path: Storage path
            expires_in: URL expiry in seconds

        Returns:
            Signed download URL
        """
        storage_client = S3StorageClient()
        return storage_client.generate_presigned_download_url(
            key=storage_path, expires_in=expires_in
        )


class ErasureService(BaseService):
    """
    Service for data erasure (GDPR Article 17 - Right to be Forgotten).

    Provides business logic for:
    - Creating erasure requests
    - Executing erasure (anonymize/delete PII)
    - Handling retention exceptions
    """

    service_name = "erasure_service"

    def __init__(self, tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        """
        Initialize ErasureService.

        Args:
            tenant_id: Optional tenant ID
            user_id: Optional user ID (actor performing erasure)
        """
        self.tenant_id = tenant_id
        self.user_id = user_id

    @transaction.atomic
    def create_request(self, user_id: str) -> ErasureRequest:
        """
        Create an erasure request for a user.

        Args:
            user_id: User ID whose data is to be erased (target user).
                     When self.user_id is set and differs, the actor in audit
                     is self.user_id (e.g. platform admin); else the target user.

        Returns:
            Created ErasureRequest instance
        """

        def _create():
            from hub.apps.users.models import User

            user = self.get_resource_or_raise(User, user_id)

            # Check for existing pending/processing request
            existing = ErasureRequest.objects.filter(
                user=user,
                status__in=[ErasureRequestStatus.PENDING, ErasureRequestStatus.PROCESSING],
            ).first()

            if existing:
                raise ValidationError(
                    "Erasure request already in progress",
                    code="ERASURE_IN_PROGRESS",
                    details={"request_id": str(existing.id)},
                )

            # Create erasure request
            request = ErasureRequest.objects.create(
                user=user, tenant=user.tenant, status=ErasureRequestStatus.PENDING
            )

            # Actor: use self.user_id (platform admin) when provided; else target user (self-requested)
            # Lookup by id only (no tenant filter) so platform admins with tenant=None are found
            actor_user = user
            if self.user_id:
                actor_user_obj = User.objects.filter(id=self.user_id).first()
                if actor_user_obj:
                    actor_user = actor_user_obj

            # Build details: user_id, user_email; add initiated_by/source for platform-initiated
            details = {"user_id": str(user_id), "user_email": user.email}
            if str(actor_user.id) != str(user_id):
                details["initiated_by"] = str(actor_user.id)
                details["source"] = "platform_admin"

            # Log audit event
            from hub.apps.audit.utils import create_audit_event

            create_audit_event(
                resource_type="ERASURE_REQUEST",
                action="ERASURE_REQUESTED",
                tenant=user.tenant,
                actor_user=actor_user,
                resource_id=str(request.id),
                details=details,
            )

            return request

        return self.execute_with_metrics(
            operation="create_request", tenant_id=self.tenant_id, func=_create
        )

    def execute_erasure(self, request_id: str) -> ErasureRequest:
        """
        Execute erasure request: anonymize/delete PII.

        Args:
            request_id: ErasureRequest ID

        Returns:
            Updated ErasureRequest instance
        """

        def _execute():
            request = self.get_resource_or_raise(ErasureRequest, request_id)

            if request.status == ErasureRequestStatus.COMPLETED:
                return request

            request.status = ErasureRequestStatus.PROCESSING
            request.save()

            try:
                with transaction.atomic():
                    user = request.user
                    anonymized_fields = []
                    deleted_resources = []
                    retention_exceptions = []

                    # Anonymize user profile
                    original_email = user.email
                    user.email = f"deleted-{user.id}@deleted.local"
                    user.display_name = "Deleted User"
                    user.save()
                    anonymized_fields.append("email")
                    anonymized_fields.append("display_name")

                    # Revoke sessions: find sessions for this user by decoding session_data.
                    # Use iterator + limit to avoid O(n) over huge session tables (e.g. shared
                    # test DB).
                    from django.contrib.sessions.models import Session

                    MAX_SESSIONS_TO_CHECK = 10000
                    session_keys_to_delete = []
                    checked = 0
                    user_id_str = str(user.id)
                    qs = Session.objects.only("session_key", "session_data")
                    for s in qs.iterator(chunk_size=500):
                        if checked >= MAX_SESSIONS_TO_CHECK:
                            break
                        checked += 1
                        try:
                            if hasattr(s, "get_decoded"):
                                decoded = s.get_decoded()
                                if decoded.get("_auth_user_id") == user_id_str:
                                    session_keys_to_delete.append(s.session_key)
                        except Exception:
                            pass
                    if session_keys_to_delete:
                        Session.objects.filter(
                            session_key__in=session_keys_to_delete
                        ).delete()
                    deleted_resources.append("sessions")

                    # Revoke API keys
                    from hub.apps.baas.models import APIKey

                    APIKey.objects.filter(user=user, revoked_at__isnull=True).update(
                        revoked_at=timezone.now()
                    )
                    deleted_resources.append("api_keys")

                    # Anonymize audit events (per policy - some may be retained)
                    from hub.apps.audit.models import AuditEvent

                    # Keep audit events but anonymize PII in details_json (GDPR erasure).
                    # Use QuerySet.update to persist; AuditEvent.save() forbids updates.
                    audit_events = AuditEvent.objects.filter(actor_user=user)
                    for event in audit_events:
                        details = event.details_json
                        if details and isinstance(details, dict):
                            anonymized = dict(details)
                            if "actor_email" in anonymized:
                                anonymized["actor_email"] = "deleted@deleted.local"
                            if "user_email" in anonymized:
                                anonymized["user_email"] = "deleted@deleted.local"
                            if anonymized != details:
                                AuditEvent.objects.filter(pk=event.pk).update(
                                    details_json=anonymized
                                )

                    # Note: Some data may be retained for legal/compliance reasons
                    # This would be determined by retention policy
                    retention_exceptions.append("audit_events")  # Example

                    request.status = ErasureRequestStatus.COMPLETED
                    request.completed_at = timezone.now()
                    request.anonymized_fields = anonymized_fields
                    request.deleted_resources = deleted_resources
                    request.retention_exceptions = retention_exceptions
                    request.save()

                    # Log audit event
                    from hub.apps.audit.utils import create_audit_event

                    create_audit_event(
                        resource_type="ERASURE_REQUEST",
                        action="ERASURE_COMPLETED",
                        tenant=request.tenant,
                        actor_user=None,  # System action
                        resource_id=str(request.id),
                        details={
                            "user_id": str(user.id),
                            "original_email": original_email,
                            "anonymized_fields": anonymized_fields,
                            "deleted_resources": deleted_resources,
                            "retention_exceptions": retention_exceptions,
                        },
                    )

                    logger.info(
                        "erasure_request_completed",
                        request_id=str(request.id),
                        user_id=str(user.id),
                        message=f"Erasure request {request.id} completed successfully",
                    )

            except Exception as e:
                logger.error(
                    "erasure_request_execution_failed",
                    request_id=str(request.id),
                    error=str(e),
                    exc_info=True,
                    message=f"Failed to execute erasure request: {e}",
                )
                # Update FAILED outside the inner atomic so it persists (inner atomic
                # rolls back on exception; this save is in the outer transaction).
                request.status = ErasureRequestStatus.FAILED
                request.error_message = str(e)
                request.save()
                raise

            return request

        return self.execute_with_metrics(
            operation="execute_erasure", tenant_id=self.tenant_id, func=_execute
        )
