"""
Phase 260.1.G.2 — Hard-delete every File row (and storage object) for a tenant.

Used for tenant-wide storage teardown / GDPR-related tenant offboarding file
phase. Does **not** run full audit-log scrub (that is user-scoped in
``delete_files_for_user``); only ``FILE_PURGED`` rows are emitted per file.

Distributed lock ``meshant:gdpr_delete_files_tenant:v1`` (Redis).
"""

from __future__ import annotations

import logging
import sys
import uuid

from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)

_LOCK_KEY = "meshant:gdpr_delete_files_tenant:v1"


class Command(BaseCommand):
    help = (
        "GDPR 260.1.G.2 — hard-purge all File rows + storage blobs for "
        "--tenant-id (no global audit scrub)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant-id",
            type=str,
            required=True,
            help="Tenant UUID.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Report file count only.",
        )

    def handle(self, *args, **opts):
        tid_raw = opts["tenant_id"]
        dry_run = bool(opts.get("dry_run"))

        try:
            tenant_pk = uuid.UUID(str(tid_raw))
        except ValueError as exc:
            raise CommandError(f"Invalid --tenant-id: {tid_raw}") from exc

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
            ttl_seconds=7200,
            wait_seconds=5,
            retry_interval_seconds=0.1,
        )
        if not acquired:
            self.stderr.write(
                self.style.ERROR(
                    "Another delete_files_for_tenant holds the lock; exiting.",
                ),
            )
            sys.exit(1)

        try:
            self._run(tenant_pk, dry_run=dry_run)
        finally:
            distributed_lock_release(
                redis_client,
                _LOCK_KEY,
                token=lock_token,
            )

    def _run(self, tenant_id: uuid.UUID, *, dry_run: bool) -> None:
        from hub.apps.files.gdpr_hard_delete import hard_purge_file_for_erasure
        from hub.apps.files.models import File
        from hub.apps.files.storage import S3StorageClient
        from hub.apps.tenants.models import Tenant

        if not Tenant.objects.filter(pk=tenant_id).exists():
            raise CommandError(f"Tenant not found: {tenant_id}")

        tid_str = str(tenant_id)
        files_qs = File.objects.filter(tenant_id=tenant_id).order_by("pk")
        n = files_qs.count()

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"dry-run: would hard-delete {n} file(s) for tenant {tenant_id}",
                ),
            )
            return

        file_ids = list(files_qs.values_list("pk", flat=True))

        storage = None
        try:
            storage = S3StorageClient()
        except Exception as exc:
            logger.warning("gdpr_delete_tenant_files_storage_failed error=%s", exc)

        purged = 0
        for fid in file_ids:
            file_obj = File.objects.get(pk=fid)
            hard_purge_file_for_erasure(
                file_obj=file_obj,
                tenant_id_str=tid_str,
                storage=storage,
                reason="GDPR_TENANT_FILE_SWEEP",
                subject_user_id=None,
            )
            purged += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"delete_files_for_tenant complete: purged {purged} file(s) for tenant {tenant_id}",
            ),
        )
