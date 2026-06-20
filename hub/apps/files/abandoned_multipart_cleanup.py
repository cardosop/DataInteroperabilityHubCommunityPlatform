"""
Phase 260.1.D — correlate stale S3 multipart uploads with File rows stuck in UPLOADING.

Stale rule: same cutoff for S3 ``Initiated`` and DB ``created_at`` (**``lte`` parity**):
only timestamps **on or before** ``cutoff = now - min_age_hours`` are aborted / finalized.

Sweep order:
  1. ``list_multipart_uploads`` stale entries —
     abort multipart (unless ``dry_run``), correlate ``File.UPLOADING``.
  2. ``File.UPLOADING`` holding ``multipart_upload_id`` with ``created_at`` on or before
     ``cutoff`` —
     abort (idempotent unless ``dry_run``), flip row if still ``UPLOADING``.

DB mutations run inside ``tenant_context``.
"""

from __future__ import annotations

import logging
from datetime import UTC, timedelta

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


def cutoff_before_now(*, now, min_age_hours: float):
    """All comparisons use ``lte`` against this instant (parity S3 initiated vs DB created_at)."""
    return now - timedelta(hours=float(min_age_hours))


def _ensure_aware_for_compare(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return timezone.make_aware(dt, timezone=UTC)
    return dt


def resolve_uploading_file_for_multipart(
    *,
    storage_path: str,
    upload_id: str,
    tenant_id_filter: str | None,
):
    """Return the File row correlated with this multipart, if deterministically matchable."""
    from hub.apps.files.models import File, FileStatus

    qs = File.objects.filter(storage_path=storage_path, status=FileStatus.UPLOADING)
    if tenant_id_filter:
        qs = qs.filter(tenant_id=tenant_id_filter)

    narrowed = qs.filter(metadata_json__multipart_upload_id=upload_id).first()
    if narrowed:
        return narrowed

    first = qs.first()
    if first is None:
        return None
    if qs.exclude(pk=first.pk).exists():
        logger.warning(
            "multipart_abandon_ambiguous_file_rows storage_path=%s upload_prefix=%s count>1",
            storage_path,
            (upload_id or "")[:20],
        )
        return None
    return first


def finalize_uploading_after_multipart_abandon(
    *,
    file_row_id,
    tenant_id_str: str,
    storage_path: str,
    upload_id: str,
    abandon_source: str,
) -> bool:
    """``UPLOADING`` → ``DELETED`` + ``FILE_MULTIPART_ABANDONED``. True if DB row updated."""
    from hub.apps.audit import event_types as audit_event_types
    from hub.apps.audit.utils import create_audit_event
    from hub.apps.files.models import File, FileStatus
    from hub.apps.tenants.request_tenant import tenant_context

    ts = timezone.now()

    with tenant_context(tenant_id_str), transaction.atomic():
        n = File.objects.filter(pk=file_row_id, status=FileStatus.UPLOADING).update(
            status=FileStatus.DELETED.value,
            deleted_at=ts,
            updated_at=ts,
        )
        if n != 1:
            return False
        refreshed = File.objects.select_related("tenant").get(pk=file_row_id)
        tenant = refreshed.tenant
        create_audit_event(
            resource_type="FILE",
            action=audit_event_types.FILE_MULTIPART_ABANDONED,
            actor_user=None,
            tenant=tenant,
            resource_id=str(file_row_id),
            result="SUCCESS",
            details={
                "file_id": str(file_row_id),
                "tenant_id": tenant_id_str,
                "storage_path": storage_path,
                "upload_id": upload_id,
                "abandon_source": abandon_source,
                "reason": "stale_multipart_abandonment",
                "timestamp": ts.isoformat(),
            },
        )
    return True


def sweep_from_s3(
    *,
    storage,
    cutoff,
    tenant_id_filter: str | None,
    dry_run: bool,
) -> dict[str, int]:
    counts = {"s3_stale_seen": 0, "multipart_aborted": 0, "uploading_rows_flipped": 0}

    for rec in storage.iter_multipart_uploads():
        initiated = _ensure_aware_for_compare(rec["initiated"])
        if initiated is None:
            logger.warning(
                "multipart_abandon_missing_initiated upload_id=%s",
                (rec.get("upload_id") or "")[:20],
            )
            continue

        if initiated > cutoff:
            continue

        key = rec["key"]
        upload_id = rec["upload_id"]
        counts["s3_stale_seen"] += 1

        matched = resolve_uploading_file_for_multipart(
            storage_path=key,
            upload_id=upload_id,
            tenant_id_filter=tenant_id_filter,
        )

        if not dry_run:
            storage.abort_multipart_upload(key=key, upload_id=upload_id)
            counts["multipart_aborted"] += 1

        if matched is None:
            continue

        if dry_run:
            counts["uploading_rows_flipped"] += 1
            continue

        if finalize_uploading_after_multipart_abandon(
            file_row_id=matched.pk,
            tenant_id_str=str(matched.tenant_id),
            storage_path=matched.storage_path,
            upload_id=upload_id,
            abandon_source="s3_list_before_cutoff",
        ):
            counts["uploading_rows_flipped"] += 1

    return counts


def sweep_from_database(
    *,
    storage,
    cutoff,
    tenant_id_filter: str | None,
    dry_run: bool,
) -> dict[str, int]:
    from hub.apps.files.models import File, FileStatus

    counts = {"db_stale_candidates": 0, "multipart_aborted": 0, "uploading_rows_flipped": 0}

    qs = (
        File.objects.filter(
            status=FileStatus.UPLOADING,
            created_at__lte=cutoff,
        )
        .filter(metadata_json__has_key="multipart_upload_id")
        .select_related("tenant")
        .order_by("pk")
    )
    if tenant_id_filter:
        qs = qs.filter(tenant_id=tenant_id_filter)

    for row in qs.iterator(chunk_size=100):
        meta = row.metadata_json or {}
        upload_id = meta.get("multipart_upload_id")
        if not upload_id:
            continue

        counts["db_stale_candidates"] += 1

        key = row.storage_path
        uid_str = str(upload_id)

        if dry_run:
            counts["uploading_rows_flipped"] += 1
            continue

        storage.abort_multipart_upload(key=key, upload_id=uid_str)
        counts["multipart_aborted"] += 1

        if finalize_uploading_after_multipart_abandon(
            file_row_id=row.pk,
            tenant_id_str=str(row.tenant_id),
            storage_path=row.storage_path,
            upload_id=uid_str,
            abandon_source="db_orphan_scan_before_cutoff",
        ):
            counts["uploading_rows_flipped"] += 1

    return counts


def run_abandoned_multipart_sweep(
    *,
    storage,
    now,
    min_age_hours: float,
    tenant_id_filter: str | None,
    dry_run: bool,
) -> dict[str, dict[str, int]]:
    cutoff = cutoff_before_now(now=now, min_age_hours=min_age_hours)

    return {
        "s3": sweep_from_s3(
            storage=storage,
            cutoff=cutoff,
            tenant_id_filter=tenant_id_filter,
            dry_run=dry_run,
        ),
        "db": sweep_from_database(
            storage=storage,
            cutoff=cutoff,
            tenant_id_filter=tenant_id_filter,
            dry_run=dry_run,
        ),
    }
