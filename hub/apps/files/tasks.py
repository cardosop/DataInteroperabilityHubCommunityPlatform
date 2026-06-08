"""
RQ tasks for file malware scanning (Phase 203).

Queue: job_default — enqueued from FileService after upload completes (ACTIVE or COMPLETED + hash).
"""
from __future__ import annotations

import django_rq
import structlog
from django.conf import settings
from django.db import transaction
from django.utils import timezone

logger = structlog.get_logger(__name__)


def enqueue_file_malware_scan(file_id: str) -> None:
    """Enqueue ClamAV scan for file_id on job_default."""
    django_rq.get_queue("job_default").enqueue(
        scan_file_malware,
        file_id,
        job_timeout=int(getattr(settings, "CLAMAV_JOB_TIMEOUT_SECONDS", 300)),
    )


def scan_file_malware(file_id: str) -> None:
    """
    Download object from S3-compatible storage, scan with ClamAV, persist status.

    Idempotent: only processes rows still in PENDING_SCAN.
    """
    from hub.apps.audit.utils import create_audit_event
    from hub.apps.files.models import File, FileScanStatus
    from hub.apps.files.scanner import ClamAVScanner
    from hub.apps.files.storage import S3StorageClient

    if not getattr(settings, "CLAMAV_ENABLED", True):
        logger.info("clamav_scan_skipped_disabled", file_id=file_id)
        return

    with transaction.atomic():
        try:
            file_obj = File.objects.select_for_update().get(pk=file_id)
        except File.DoesNotExist:
            logger.warning("clamav_scan_file_missing", file_id=file_id)
            return

        if file_obj.scan_status != FileScanStatus.PENDING_SCAN:
            return

    try:
        storage = S3StorageClient()
        content = storage.get_file_content(file_obj.storage_path)
    except Exception as e:
        # StorageObjectNotFoundError is an expected condition — the S3 object
        # may not exist yet (async upload still in flight) or may have been
        # deleted by a lifecycle policy. The code handles it gracefully by
        # marking the file as SCAN_ERROR, so log at WARNING level.
        # All other storage errors (connection failures, auth errors, etc.)
        # are genuine infrastructure issues and remain at ERROR level.
        from hub.apps.files.storage import StorageObjectNotFoundError

        if isinstance(e, StorageObjectNotFoundError):
            logger.warning(
                "clamav_storage_object_missing",
                file_id=file_id,
                storage_path=file_obj.storage_path,
                error=str(e),
            )
        else:
            logger.error(
                "clamav_storage_read_failed",
                file_id=file_id,
                error=str(e),
                exc_info=True,
            )
        with transaction.atomic():
            try:
                file_obj = File.objects.select_for_update().get(pk=file_id)
            except File.DoesNotExist:
                return
            if file_obj.scan_status != FileScanStatus.PENDING_SCAN:
                return
            file_obj.scan_status = FileScanStatus.SCAN_ERROR
            file_obj.scanned_at = timezone.now()
            file_obj.save(update_fields=["scan_status", "scanned_at", "updated_at"])
        try:
            create_audit_event(
                resource_type="FILE",
                action="FILE_MALWARE_SCAN_STORAGE_ERROR",
                tenant=file_obj.tenant,
                resource_id=str(file_obj.id),
                result="WARNING",
                details={"error_type": type(e).__name__},
            )
        except Exception as audit_exc:
            logger.warning(
                "clamav_storage_audit_failed",
                file_id=file_id,
                error=str(audit_exc),
                exc_info=True,
            )
        return

    scanner = ClamAVScanner()
    outcome, threat_name = scanner.classify_bytes_with_detail(content)

    with transaction.atomic():
        try:
            file_obj = File.objects.select_for_update().get(pk=file_id)
        except File.DoesNotExist:
            return
        if file_obj.scan_status != FileScanStatus.PENDING_SCAN:
            return
        file_obj.scan_status = outcome
        file_obj.scanned_at = timezone.now()
        file_obj.save(update_fields=["scan_status", "scanned_at", "updated_at"])

    if outcome == FileScanStatus.SCAN_UNAVAILABLE:
        try:
            create_audit_event(
                resource_type="FILE",
                action="FILE_MALWARE_SCAN_UNAVAILABLE",
                tenant=file_obj.tenant,
                resource_id=str(file_obj.id),
                result="WARNING",
                details={
                    "reason": "clamav_unreachable_or_client_error",
                    "clamav_host": getattr(settings, "CLAMAV_HOST", ""),
                    "clamav_port": getattr(settings, "CLAMAV_PORT", ""),
                },
            )
        except Exception as e:
            logger.warning(
                "clamav_unavailable_audit_failed",
                file_id=file_id,
                error=str(e),
                exc_info=True,
            )
    elif outcome == FileScanStatus.INFECTED:
        try:
            create_audit_event(
                resource_type="FILE",
                action="FILE_MALWARE_DETECTED",
                tenant=file_obj.tenant,
                resource_id=str(file_obj.id),
                result="FAILURE",
                details={
                    "scan_status": outcome,
                    "threat_signature": threat_name or "unknown",
                },
            )
        except Exception as e:
            logger.warning(
                "clamav_infected_audit_failed",
                file_id=file_id,
                error=str(e),
                exc_info=True,
            )
