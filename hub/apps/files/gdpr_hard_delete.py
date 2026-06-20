"""
Hard-delete File storage + DB row for GDPR / offboarding flows.

Mirrors ``purge_deleted_files`` destructive path: best-effort S3 removal,
``FILE_PURGED`` audit (with extra ``details``), then ORM ``delete()`` on the
File row — under ``tenant_context`` and ``transaction.atomic``.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


def hard_purge_file_for_erasure(
    *,
    file_obj: Any,
    tenant_id_str: str,
    storage: Any,
    reason: str,
    subject_user_id: str | None = None,
) -> None:
    """
    Delete blob + row; emit ``FILE_PURGED`` with ``reason`` in details.

    ``subject_user_id`` is stamped for traceability (GDPR user vs tenant sweep).
    """
    from hub.apps.audit import event_types as audit_event_types
    from hub.apps.audit.utils import create_audit_event
    from hub.apps.tenants.request_tenant import tenant_context

    tenant = file_obj.tenant
    pk = file_obj.pk
    name = file_obj.name
    sha = file_obj.content_sha256
    size = file_obj.size
    storage_path = file_obj.storage_path

    if storage is not None:
        try:
            storage.delete_file(storage_path)
        except Exception as exc:
            logger.warning(
                "gdpr_hard_purge_s3_delete_failed file_id=%s error=%s",
                pk,
                exc,
            )

    ts = timezone.now()

    def _emit_and_delete():
        details = {
            "file_id": str(pk),
            "name": name,
            "content_sha256": sha,
            "size": size,
            "tenant_id": tenant_id_str,
            "actor_user_id": None,
            "timestamp": ts.isoformat(),
            "reason": reason,
        }
        if subject_user_id:
            details["gdpr_subject_user_id"] = subject_user_id
        create_audit_event(
            resource_type="FILE",
            action=audit_event_types.FILE_PURGED,
            actor_user=None,
            tenant=tenant,
            resource_id=str(pk),
            result="SUCCESS",
            details=details,
        )
        # Phase 260.7.G.R1 GAP-A — emit ``file.purged`` event +
        # trigger webhook delivery alongside the audit so external
        # subscribers see GDPR-driven hard-deletes the SAME way they
        # see grace-period purges. Pre-R1 the ``purge_deleted_files``
        # cron path was wired (260.7.G.2) but THIS GDPR / offboarding
        # path was missed — symmetric-bug class (same shape as
        # 260.7.E.R1 GAP-A): one call site of FILE_PURGED audit got
        # the webhook, the other didn't. Fix routes both audit-
        # emitting hard-delete paths through the same publisher so
        # subscribers see ``file.purged`` regardless of WHICH purge
        # mechanism fired.
        #
        # Best-effort try/except so a publisher failure cannot
        # prevent the file_obj.delete() that follows — the audit is
        # the durable contract; the webhook is observability +
        # integration. Same defensive convention as the cron path.
        try:
            from hub.apps.files.services import FileService

            _file_service = FileService(tenant_id=tenant_id_str)
            _file_service.publish_file_purged(
                file_id=str(pk),
                name=name,
                size=size,
                content_sha256=sha,
                tenant_id=tenant_id_str,
            )
        except Exception as exc:
            logger.warning(
                "gdpr_hard_purge_event_emit_failed",
                extra={
                    "file_id": str(pk),
                    "tenant_id": tenant_id_str,
                    "reason": reason,
                    "error": str(exc),
                },
            )
        file_obj.delete()

    with tenant_context(tenant_id_str), transaction.atomic():
        _emit_and_delete()
