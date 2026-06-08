"""
Phase 260.1.E — one-time / scheduled cleanup of pre-Phase-260 orphan File rows.

Files with no in-tenant Dataset, ComplianceRun, DQRun, RetentionPolicy, or
AccessRequest reference, older than ``--min-age-days`` (default 30), are
soft-deleted via :class:`hub.apps.files.services.FileService` (DELETING +
storage lifecycle tag), matching API delete semantics.

Safety
------
* ``--dry-run`` — audit each batch without mutating files.
* ``FILE_ORPHAN_CLEANUP_DRY_RUN=true`` forces dry-run for the first 7 days
  post-deploy unless ``--no-dry-run`` is passed (mirrors ``ASSET_ORPHAN_CLEANUP_DRY_RUN``).
* Redis distributed lock ``meshant:cleanup_orphan_files:v1`` — one cluster-wide
  sweep at a time (avoids duplicate soft-deletes / audit noise).
* Non-dry-run batches re-query the **first** ``batch_size`` orphans each
  iteration so DELETING rows disappear; avoids skipping lower-pk rows if a
  mid-batch delete fails (cursor ``pk__gt`` would advance past them).
"""
from __future__ import annotations
import logging
import os
import sys
import uuid
from datetime import datetime, timedelta
from typing import Any, List

from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE: int = 500
DEFAULT_MIN_AGE_DAYS: int = 30
_FILE_ID_AUDIT_SAMPLE: int = 10
_LOCK_KEY = "meshant:cleanup_orphan_files:v1"


def _env_forces_dry_run() -> bool:
    v = os.environ.get("FILE_ORPHAN_CLEANUP_DRY_RUN", "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _emit_batch_audit(
    *,
    tenant: Any,
    count: int,
    dry_run: bool,
    batch: int,
    min_age_days: int,
    file_ids: List[str],
    correlation_id: str,
    soft_deleted: int | None = None,
    failure_sample: list[dict[str, str]] | None = None,
) -> None:
    try:
        from hub.apps.audit import event_types as audit_event_types
        from hub.apps.audit.utils import create_audit_event

        details: dict[str, Any] = {
            "tenant_id": str(tenant.id),
            "count": count,
            "dry_run": dry_run,
            "batch": batch,
            "min_age_days": min_age_days,
            "file_ids": file_ids[:_FILE_ID_AUDIT_SAMPLE],
            "correlation_id": correlation_id,
        }
        if soft_deleted is not None:
            details["soft_deleted"] = soft_deleted
        if failure_sample:
            details["failure_sample"] = failure_sample[:5]

        create_audit_event(
            resource_type="FILE",
            action=audit_event_types.FILE_ORPHAN_CLEANUP_COMPLETED,
            actor_user=None,
            tenant=tenant,
            resource_id=None,
            result="SUCCESS",
            details=details,
        )
    except Exception as exc:  # noqa: BLE001 — boundary
        logger.warning(
            "cleanup_orphan_files_audit_failed tenant_id=%s batch=%s error=%s",
            tenant.id,
            batch,
            exc,
        )


class Command(BaseCommand):
    help = (
        "Phase 260.1.E — soft-delete orphan File rows (no Dataset/DQ/Compliance/"
        "Governance ref) older than --min-age-days; emit FILE_ORPHAN_CLEANUP_COMPLETED "
        "per batch."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Report batches via audit without soft-deleting files.",
        )
        parser.add_argument(
            "--no-dry-run",
            action="store_true",
            default=False,
            help="Override FILE_ORPHAN_CLEANUP_DRY_RUN and allow FileService.delete_file.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=DEFAULT_BATCH_SIZE,
            help=f"Maximum files per tenant per batch (default {DEFAULT_BATCH_SIZE}).",
        )
        parser.add_argument(
            "--min-age-days",
            type=int,
            default=DEFAULT_MIN_AGE_DAYS,
            help=(
                "Only files with created_at at least this many days ago "
                f"(default {DEFAULT_MIN_AGE_DAYS})."
            ),
        )
        parser.add_argument(
            "--tenant-id",
            type=str,
            default=None,
            help="Limit to a single tenant UUID.",
        )

    def handle(self, *args, **opts):
        dry_run = bool(opts.get("dry_run"))
        no_dry_run = bool(opts.get("no_dry_run"))
        batch_size = int(opts.get("batch_size") or DEFAULT_BATCH_SIZE)
        min_age_days = int(opts.get("min_age_days") or DEFAULT_MIN_AGE_DAYS)
        tenant_id_filter = opts.get("tenant_id")

        if _env_forces_dry_run() and not no_dry_run:
            dry_run = True
            self.stdout.write(
                self.style.WARNING(
                    "FILE_ORPHAN_CLEANUP_DRY_RUN is set; forcing dry-run "
                    "(pass --no-dry-run to override)."
                ),
            )

        # Explicit destructive flag wins over --dry-run (and any env default).
        if no_dry_run:
            dry_run = False

        from hub.apps.api.middleware.idempotency_utils import get_redis_client
        from hub.apps.core.distributed_lock import (
            distributed_lock_acquire,
            distributed_lock_release,
        )

        try:
            redis_client = get_redis_client()
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"Redis unavailable: {exc}"))
            sys.exit(2)

        acquired, lock_token = distributed_lock_acquire(
            redis_client,
            _LOCK_KEY,
            ttl_seconds=3600,
            wait_seconds=5,
            retry_interval_seconds=0.1,
        )
        if not acquired:
            self.stderr.write(
                self.style.ERROR(
                    "Another cleanup_orphan_files instance holds the "
                    "distributed lock; exiting.",
                ),
            )
            sys.exit(1)

        correlation_id = str(uuid.uuid4())
        cutoff = timezone.now() - timedelta(days=min_age_days)

        try:
            processed = self._run_sweep(
                dry_run=dry_run,
                batch_size=batch_size,
                min_age_days=min_age_days,
                cutoff=cutoff,
                tenant_id_filter=tenant_id_filter,
                correlation_id=correlation_id,
            )
        finally:
            distributed_lock_release(
                redis_client,
                _LOCK_KEY,
                token=lock_token,
            )

        action = "would process" if dry_run else "processed"
        self.stdout.write(
            self.style.SUCCESS(
                f"cleanup_orphan_files complete: {action} {processed} file(s) "
                f"(correlation_id={correlation_id}).",
            ),
        )

    def _run_sweep(
        self,
        *,
        dry_run: bool,
        batch_size: int,
        min_age_days: int,
        cutoff: datetime,
        tenant_id_filter: str | None,
        correlation_id: str,
    ) -> int:
        from hub.apps.files.orphan_file_cleanup import orphan_cleanup_candidate_qs
        from hub.apps.files.services import FileService
        from hub.apps.tenants.models import Tenant
        from hub.apps.tenants.request_tenant import tenant_context

        tenants = Tenant.objects.all().order_by("pk")
        if tenant_id_filter:
            tenants = tenants.filter(pk=tenant_id_filter)

        self.stdout.write(
            f"cleanup_orphan_files starting: batch_size={batch_size} "
            f"min_age_days={min_age_days} dry_run={dry_run} "
            f"tenant_id_filter={tenant_id_filter} "
            f"correlation_id={correlation_id}",
        )

        total_processed = 0
        for tenant in tenants.iterator(chunk_size=20):
            tid = str(tenant.id)
            total_processed += self._sweep_tenant(
                tenant=tenant,
                tenant_id_str=tid,
                batch_size=batch_size,
                min_age_days=min_age_days,
                cutoff=cutoff,
                dry_run=dry_run,
                correlation_id=correlation_id,
                orphan_cleanup_candidate_qs=orphan_cleanup_candidate_qs,
                file_service_factory=lambda: FileService(
                    tenant_id=tid,
                    user_id=None,
                ),
                tenant_context=tenant_context,
            )
        return total_processed

    def _sweep_tenant(
        self,
        *,
        tenant: Any,
        tenant_id_str: str,
        batch_size: int,
        min_age_days: int,
        cutoff: datetime,
        dry_run: bool,
        correlation_id: str,
        orphan_cleanup_candidate_qs: Any,
        file_service_factory: Any,
        tenant_context: Any,
    ) -> int:
        last_pk = None
        batch_no = 0
        tenant_total = 0

        if dry_run:
            # Cursor pagination: candidates do not leave the queryset.
            while True:
                qs = orphan_cleanup_candidate_qs(
                    tenant_id=tenant.pk,
                    min_age_cutoff=cutoff,
                )
                if last_pk is not None:
                    qs = qs.filter(pk__gt=last_pk)
                batch: List[Any] = list(qs[:batch_size])
                if not batch:
                    break

                batch_no += 1
                last_pk = batch[-1].pk
                id_strs = [str(o.pk) for o in batch]

                _emit_batch_audit(
                    tenant=tenant,
                    count=len(batch),
                    dry_run=True,
                    batch=batch_no,
                    min_age_days=min_age_days,
                    file_ids=id_strs,
                    correlation_id=correlation_id,
                )
                tenant_total += len(batch)
            return tenant_total

        # Non-dry-run: always slice the head of the orphan queryset so rows
        # that transition to DELETING fall out. (pk__gt cursor would skip
        # any row that failed mid-batch and still has pk < last_pk.)
        while True:
            qs = orphan_cleanup_candidate_qs(
                tenant_id=tenant.pk,
                min_age_cutoff=cutoff,
            )
            batch = list(qs[:batch_size])
            if not batch:
                break

            batch_no += 1
            id_strs = [str(o.pk) for o in batch]
            successes = 0
            failures: list[dict[str, str]] = []
            svc = file_service_factory()
            with tenant_context(tenant_id_str):
                for obj in batch:
                    try:
                        svc.delete_file(
                            str(obj.pk),
                            tenant_id_str,
                            None,
                        )
                        successes += 1
                    except Exception as exc:  # noqa: BLE001 — batch boundary
                        logger.warning(
                            "cleanup_orphan_files_delete_failed tenant=%s file=%s error=%s",
                            tenant_id_str,
                            obj.pk,
                            exc,
                        )
                        failures.append(
                            {"file_id": str(obj.pk), "error": str(exc)},
                        )

            _emit_batch_audit(
                tenant=tenant,
                count=len(batch),
                dry_run=False,
                batch=batch_no,
                min_age_days=min_age_days,
                file_ids=id_strs,
                correlation_id=correlation_id,
                soft_deleted=successes,
                failure_sample=failures,
            )
            tenant_total += len(batch)

        return tenant_total
