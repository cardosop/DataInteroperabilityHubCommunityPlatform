"""
Phase 260.1.A.1 — hard-delete files past per-tenant soft-delete grace.

User/API delete sets ``File.status=DELETING`` and ``deleted_at``; this sweep
removes the object from S3-compatible storage and deletes the DB row.

Safety
------
* ``--dry-run`` — log counts without mutating storage or DB.
* ``FILE_PURGE_DRY_RUN_REQUIRED=true`` (D260.10) forces dry-run unless
  ``--no-dry-run`` is passed (mirrors ``DQ_PURGE_DRY_RUN``).
* Redis SET NX + tokenised release (``hub.apps.core.distributed_lock``) on
  ``meshant:purge_deleted_files:v1`` — only one worker runs a destructive pass
  cluster-wide; compare-and-del Lua prevents accidental release of another
  holder’s lock after TTL races.
* Batched 500 rows by default to cap transaction / lock duration.

Scheduled via Kubernetes CronJob (``helm/templates/cronjob/purge-deleted-files.yaml``)
at 03:00 UTC — repo standard replaces Celery beat for periodic Django work.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE: int = 500
_PURGE_LOCK_KEY = "meshant:purge_deleted_files:v1"


def _env_forces_dry_run() -> bool:
    v = os.environ.get("FILE_PURGE_DRY_RUN_REQUIRED", "").strip().lower()
    return v in ("1", "true", "yes", "on")


class Command(BaseCommand):
    help = (
        "Phase 260.1.A — purge File rows in DELETING/DELETED past "
        "tenant.file_soft_delete_grace_days; delete S3 objects; emit FILE_PURGED audits."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Report work without deleting storage or DB rows.",
        )
        parser.add_argument(
            "--no-dry-run",
            action="store_true",
            default=False,
            help="Override FILE_PURGE_DRY_RUN_REQUIRED and allow destructive run.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=DEFAULT_BATCH_SIZE,
            help=f"Maximum files per tenant per invocation chunk (default {DEFAULT_BATCH_SIZE}).",
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
        tenant_id_filter = opts.get("tenant_id")

        if _env_forces_dry_run() and not no_dry_run:
            dry_run = True
            self.stdout.write(
                self.style.WARNING(
                    "FILE_PURGE_DRY_RUN_REQUIRED is set; forcing --dry-run "
                    "(pass --no-dry-run to override)."
                )
            )

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
            _PURGE_LOCK_KEY,
            ttl_seconds=3600,
            wait_seconds=5,
            retry_interval_seconds=0.1,
        )
        if not acquired:
            self.stderr.write(
                self.style.ERROR(
                    "Another purge_deleted_files instance holds the distributed lock; exiting."
                )
            )
            sys.exit(1)

        purged = 0
        try:
            purged = self._run_purge(
                dry_run=dry_run,
                batch_size=batch_size,
                tenant_id_filter=tenant_id_filter,
            )
        finally:
            distributed_lock_release(
                redis_client,
                _PURGE_LOCK_KEY,
                token=lock_token,
            )

        action = "would purge" if dry_run else "purged"
        self.stdout.write(
            self.style.SUCCESS(f"purge_deleted_files complete: {action} {purged} file(s).")
        )

    def _run_purge(
        self,
        *,
        dry_run: bool,
        batch_size: int,
        tenant_id_filter: str | None,
    ) -> int:
        from hub.apps.files.file_retention import file_is_purge_eligible
        from hub.apps.files.models import File, FileStatus
        from hub.apps.files.storage import S3StorageClient
        from hub.apps.tenants.models import Tenant
        from hub.apps.tenants.request_tenant import tenant_context

        tenants = Tenant.objects.all().order_by("pk")
        if tenant_id_filter:
            tenants = tenants.filter(pk=tenant_id_filter)

        total = 0
        now = timezone.now()
        storage = None
        if not dry_run:
            storage = S3StorageClient()

        for tenant in tenants.iterator(chunk_size=20):
            with tenant_context(str(tenant.id)):
                grace = int(getattr(tenant, "file_soft_delete_grace_days", 30) or 30)
                cutoff = now - timedelta(days=grace)

                # Cursor-paginate by primary key. The hard-delete path
                # consumes the row (so a fresh ``pk > cursor`` query
                # would naturally advance), but the dry-run path only
                # COUNTS — without an explicit cursor the same batch
                # would be fetched forever and the command would never
                # terminate. Track the last-seen pk and bound every
                # batch to ``pk__gt=cursor`` so both paths advance
                # deterministically.
                cursor: object = None
                while True:
                    qs = File.objects.filter(
                        tenant=tenant,
                        status__in=(FileStatus.DELETING, FileStatus.DELETED),
                        deleted_at__isnull=False,
                        deleted_at__lte=cutoff,
                    )
                    if cursor is not None:
                        qs = qs.filter(pk__gt=cursor)
                    batch: list[File] = list(qs.order_by("pk")[:batch_size])
                    if not batch:
                        break

                    for file_obj in batch:
                        if not file_is_purge_eligible(
                            status=file_obj.status,
                            deleted_at=file_obj.deleted_at,
                            grace_days=grace,
                            now=now,
                        ):
                            continue

                        if dry_run:
                            total += 1
                            continue

                        self._hard_delete_one_file(
                            file_obj=file_obj,
                            storage=storage,
                            tenant=tenant,
                        )
                        total += 1

                    cursor = batch[-1].pk
                    # If the batch was smaller than the page size the
                    # next query would return empty — short-circuit
                    # rather than running an empty-result query.
                    if len(batch) < batch_size:
                        break

        return total

    def _hard_delete_one_file(self, *, file_obj, storage, tenant) -> None:
        from hub.apps.audit import event_types as audit_event_types
        from hub.apps.audit.utils import create_audit_event
        from hub.apps.tenants.request_tenant import tenant_context

        pk = file_obj.pk
        name = file_obj.name
        sha = file_obj.content_sha256
        size = file_obj.size
        storage_path = file_obj.storage_path
        tenant_id_str = str(tenant.id)

        if storage is None:
            raise RuntimeError("purge_deleted_files: storage client required for hard delete")

        try:
            storage.delete_file(storage_path)
        except Exception as exc:
            logger.warning(
                "purge_deleted_files_s3_delete_failed file_id=%s error=%s",
                pk,
                exc,
            )

        ts = timezone.now()

        def _emit_audit_and_delete():
            create_audit_event(
                resource_type="FILE",
                action=audit_event_types.FILE_PURGED,
                actor_user=None,
                tenant=tenant,
                resource_id=str(pk),
                result="SUCCESS",
                details={
                    "file_id": str(pk),
                    "name": name,
                    "content_sha256": sha,
                    "size": size,
                    "tenant_id": tenant_id_str,
                    "actor_user_id": None,
                    "timestamp": ts.isoformat(),
                    "dry_run": False,
                },
            )
            # Phase 260.7.G — emit ``file.purged`` event + trigger
            # webhook delivery alongside the audit so external
            # subscribers (registered via POST /api/v1/webhooks/ with
            # ``event_types=["file.purged"]``) can run cleanup that
            # wasn't safe during the grace window.
            #
            # Best-effort: publish_file_purged catches its own failures
            # (event-bus publish AND webhook trigger are both wrapped),
            # but we also wrap the call site so a constructor failure
            # cannot prevent the file.delete() that follows. Audit row
            # is the durable contract; the webhook is observability +
            # integration on top.
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
                    "purge_deleted_files_event_emit_failed",
                    extra={
                        "file_id": str(pk),
                        "tenant_id": tenant_id_str,
                        "error": str(exc),
                    },
                )
            file_obj.delete()

        with tenant_context(tenant_id_str), transaction.atomic():
            _emit_audit_and_delete()
