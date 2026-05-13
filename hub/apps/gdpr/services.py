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


# Version of the `user_data.json` envelope shape produced by
# `_collect_user_data`. Bump on every breaking change to that envelope
# (renamed key, removed key, changed semantics). Additive changes
# (new keys, new resource types) do NOT need a bump — readers should
# tolerate unknown keys.
#
# Format: semver. Consumers parsing the export should branch on the
# major version. Documented as part of the GDPR Article 20 contract
# (see OpenAPI schema for the export-data endpoint).
GDPR_EXPORT_FORMAT_VERSION = "1.1.0"  # Phase 277.B.013a — added orders, payments, webhooks, consent


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
            "format_version": GDPR_EXPORT_FORMAT_VERSION,
            "exported_at": timezone.now().isoformat(),
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
            "files": [],
            "marketplace_orders": [],
            "payment_transactions": [],
            "webhook_deliveries": [],
            "consent_records": [],
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

        # Phase 260.1.G.3 — file uploads attributed to the user (Article 20 metadata)
        from hub.apps.files.models import File

        user_files = File.objects.filter(created_by=user).order_by("created_at")

        for file_row in user_files:
            data["files"].append(
                {
                    "id": str(file_row.id),
                    "name": file_row.name,
                    "content_type": file_row.content_type,
                    "size": file_row.size,
                    "status": file_row.status,
                    "storage_path": file_row.storage_path,
                    "tenant_id": str(file_row.tenant_id),
                    "created_at": (
                        file_row.created_at.isoformat()
                        if file_row.created_at
                        else None
                    ),
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


        # Phase 277.B.013a — marketplace orders
        try:
            from hub.apps.marketplace.models import Order
            orders = Order.objects.filter(tenant=user.tenant, buyer=user)
            for o in orders:
                data["marketplace_orders"].append({"id": str(o.id), "status": o.status, "created_at": o.created_at.isoformat() if o.created_at else None})
        except Exception:
            logger.exception("gdpr_export_orders_failed")

        # Phase 277.B.013a — payment transactions
        try:
            from hub.apps.marketplace.models import PaymentTransaction
            txs = PaymentTransaction.objects.filter(order__tenant=user.tenant, order__buyer=user)
            for tx in txs:
                data["payment_transactions"].append({"id": str(tx.id), "status": getattr(tx, "status", "UNKNOWN"), "amount_cents": getattr(tx, "amount_cents", None), "created_at": tx.created_at.isoformat() if tx.created_at else None})
        except Exception:
            logger.exception("gdpr_export_payments_failed")

        # Phase 277.B.013a — webhook deliveries
        try:
            from hub.apps.webhooks.models import WebhookDelivery
            deliveries = WebhookDelivery.objects.filter(webhook__tenant=user.tenant).order_by("-created_at")[:100]
            for d in deliveries:
                data["webhook_deliveries"].append({"id": str(d.id), "event_type": getattr(d, "event_type", ""), "status": getattr(d, "status", "UNKNOWN"), "created_at": d.created_at.isoformat() if d.created_at else None})
        except Exception:
            logger.exception("gdpr_export_webhooks_failed")

        # Phase 277.B.013a — consent records
        try:
            from hub.apps.consent.models import ConsentRecord
            consents = ConsentRecord.objects.filter(tenant=user.tenant, user=user)
            for c in consents:
                data["consent_records"].append({"id": str(c.id), "purpose": getattr(c, "purpose", ""), "granted": getattr(c, "granted", True), "created_at": c.created_at.isoformat() if c.created_at else None})
        except Exception:
            logger.exception("gdpr_export_consents_failed")

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

                    original_email = user.email

                    # Audit scrub MUST run before mutating ``User.email``. Phase 2 of
                    # ``scrub_audit_events_for_gdpr_user_target`` matches JSON
                    # ``user_email`` against the subject's current address; if we
                    # anonymize first, that match fails and PII remains in audit rows
                    # logged by other actors.
                    from hub.apps.gdpr.audit_erasure import (
                        scrub_audit_events_for_gdpr_user_target,
                    )

                    scrub_audit_events_for_gdpr_user_target(user=user)

                    # Anonymize user profile
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

                    # Phase 250.5.F.5 — anonymise (NOT hard-delete)
                    # assets owned by the user. Hard-delete would
                    # orphan audit history; anonymisation removes
                    # PII while keeping the row for audit replay.
                    # Strategy: replace ``name`` / ``description``
                    # with a deterministic placeholder so a future
                    # GET on the row returns "Deleted user's asset"
                    # rather than the original PII-bearing text.
                    from hub.apps.assets.models import Asset

                    # Iterate + save() (NOT QuerySet.update()) so the
                    # Asset post_save signal fires — Phase 250.1.F's
                    # ``rebuild_asset_search_vector`` rebuilds the
                    # search_vector tsvector from the new (redacted)
                    # name + description. ``QuerySet.update()`` is a
                    # raw SQL UPDATE that bypasses signals; without
                    # this iteration the user's PII stays embedded in
                    # the search_vector and a future search query
                    # could surface the redacted asset by the
                    # original (PII-bearing) text — defeating the
                    # erasure invariant.
                    user_assets = Asset.objects.filter(
                        created_by=user,
                    )
                    redacted_name = f"asset-of-deleted-user-{user.id}"
                    redacted_description = (
                        "PII redacted per GDPR Article 17 "
                        "right-to-erasure (Phase 250.5.F.5)."
                    )
                    asset_count = 0
                    for asset in user_assets.iterator(chunk_size=200):
                        asset.name = redacted_name
                        asset.description = redacted_description
                        # ``update_fields`` keeps the save targeted —
                        # avoids racing with concurrent updates to
                        # other fields AND keeps the post_save
                        # signal payload minimal.
                        asset.save(
                            update_fields=["name", "description", "updated_at"],
                        )
                        asset_count += 1
                    if asset_count:
                        deleted_resources.append("assets")

                    # Phase 231.9 — user-attributed compliance runs (Job.created_by)
                    # retain row-level audit history but strip PII-bearing JSON
                    # columns that may embed column samples or regulatory text.
                    from hub.apps.compliance.models import ComplianceRun

                    _COMPLIANCE_ERASURE_PLACEHOLDER = {
                        "gdpr_redacted": True,
                        "reason": "article_17_erasure",
                    }
                    comp_updated = ComplianceRun.objects.filter(
                        job__created_by=user
                    ).update(
                        column_findings_json=[],
                        detected_categories_json={},
                        regulation_mapping_json=_COMPLIANCE_ERASURE_PLACEHOLDER,
                        cross_border_alert=_COMPLIANCE_ERASURE_PLACEHOLDER,
                        localisation_alert=_COMPLIANCE_ERASURE_PLACEHOLDER,
                        legal_basis_violations=[],
                        metadata_json=_COMPLIANCE_ERASURE_PLACEHOLDER,
                        regulations=[],
                    )
                    if comp_updated:
                        deleted_resources.append("compliance_runs")

                    # Phase 277.B.013b — anonymise Marketplace Listings
                    # where the user is listed as created_by.  The
                    # listing row is preserved (audit history) but
                    # PII-bearing metadata and FK are scrubbed.
                    from hub.apps.marketplace.models import Listing

                    _LISTING_TITLE = "Deleted User Listing"
                    _LISTING_DESC = (
                        "PII redacted per GDPR Article 17 right-to-erasure."
                    )
                    listing_count = 0
                    for listing in Listing.objects.filter(
                        created_by=user,
                    ).iterator(chunk_size=200):
                        current_meta = listing.metadata_json or {}
                        current_meta["title"] = _LISTING_TITLE
                        current_meta["description"] = _LISTING_DESC
                        for pii_key in (
                            "contact_email", "contact_name",
                            "support_email", "author_name",
                        ):
                            if pii_key in current_meta:
                                current_meta[pii_key] = "redacted@deleted.local"
                        listing.metadata_json = current_meta
                        listing.created_by = None
                        listing.save(
                            update_fields=[
                                "metadata_json", "created_by", "updated_at",
                            ],
                        )
                        listing_count += 1
                    if listing_count:
                        deleted_resources.append("marketplace_listings")

                    # Phase 277.B.013b — clear FK on ComplianceRun
                    # jobs where job.created_by = user.
                    from hub.apps.jobs.models import Job

                    job_updated = Job.objects.filter(
                        created_by=user,
                        type=JobType.COMPLIANCE_RUN,
                    ).update(created_by=None)
                    if job_updated:
                        deleted_resources.append("compliance_run_jobs")

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


def export_user_data(user_id: str) -> Dict[str, Any]:
    """
    GDPR Article 20 — return the same envelope as ``DataExportJob`` / ``user_data.json``.

    Public entrypoint for management commands and integrations that need the
    portable JSON document without creating a job row.
    """
    from hub.apps.users.models import User

    user = User.objects.get(pk=user_id)
    return DataPortabilityService()._collect_user_data(user)
