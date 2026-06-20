"""
Phase 260.1.D — daily sweep: abort stale S3 multipart uploads; ``File.UPLOADING`` → ``DELETED``.

Scheduled via Kubernetes CronJob (``helm/templates/cronjob/cleanup-abandoned-multipart-uploads.yaml``).
OpenSpec text referenced “Celery beat”; this repo uses management commands + CronJobs
(same pattern as ``purge_deleted_files``).
"""

from __future__ import annotations

import sys

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

_CLEANUP_LOCK_KEY = "meshant:cleanup_abandoned_multipart_uploads:v1"


class Command(BaseCommand):
    help = (
        "Phase 260.1.D — list-and-abort stale multipart uploads in the files bucket; "
        "correlate File.UPLOADING rows; emit FILE_MULTIPART_ABANDONED."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Do not call S3 abort or update File rows; report counts only.",
        )
        parser.add_argument(
            "--min-age-hours",
            type=float,
            default=24.0,
            help=(
                "Cutoff = now minus this many hours; S3 Initiated and File.created_at use "
                "the same ``<= cutoff`` rule (default 24)."
            ),
        )
        parser.add_argument(
            "--tenant-id",
            type=str,
            default=None,
            help=(
                "Restrict which File.UPLOADING rows can be correlated and updated (DB-led pass). "
                "Stale multiparts listed in S3 are still aborted globally — this protects storage "
                "even when narrowing tenant work."
            ),
        )

    def handle(self, *args, **opts):
        dry_run = bool(opts.get("dry_run"))
        # ``opts.get("min_age_hours") or 24.0`` would mask a deliberate
        # ``min_age_hours=0`` (legitimate for ops + tests that want to
        # sweep everything regardless of age) because ``0`` is falsy
        # in Python. Discriminate ``None`` from ``0`` explicitly.
        raw_min_age = opts.get("min_age_hours")
        min_age_hours = float(24.0 if raw_min_age is None else raw_min_age)
        if min_age_hours < 0:
            raise CommandError("--min-age-hours must be non-negative")
        tenant_id_filter = opts.get("tenant_id")

        from hub.apps.api.middleware.idempotency_utils import get_redis_client
        from hub.apps.core.distributed_lock import (
            distributed_lock_acquire,
            distributed_lock_release,
        )
        from hub.apps.files.abandoned_multipart_cleanup import run_abandoned_multipart_sweep
        from hub.apps.files.storage import S3StorageClient

        try:
            redis_client = get_redis_client()
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"Redis unavailable: {exc}"))
            sys.exit(2)

        acquired, lock_token = distributed_lock_acquire(
            redis_client,
            _CLEANUP_LOCK_KEY,
            ttl_seconds=3600,
            wait_seconds=5,
            retry_interval_seconds=0.1,
        )
        if not acquired:
            self.stderr.write(
                self.style.ERROR(
                    "Another cleanup_abandoned_multipart_uploads instance holds the lock; exiting."
                )
            )
            sys.exit(1)

        try:
            storage = S3StorageClient()
            stats = run_abandoned_multipart_sweep(
                storage=storage,
                now=timezone.now(),
                min_age_hours=min_age_hours,
                tenant_id_filter=tenant_id_filter,
                dry_run=dry_run,
            )
        finally:
            distributed_lock_release(redis_client, _CLEANUP_LOCK_KEY, token=lock_token)

        self._print_summary(stats=stats, dry_run=dry_run)
        mode = "(dry-run) " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(f"cleanup_abandoned_multipart_uploads {mode}completed.")
        )

    def _print_summary(self, *, stats: dict, dry_run: bool) -> None:
        s = stats["s3"]
        d = stats["db"]
        self.stdout.write(
            f"S3-led pass: stale_multipart_seen={s['s3_stale_seen']} "
            f"multipart_aborts={'0' if dry_run else s['multipart_aborted']} "
            f"uploading_flipped_or_would={s['uploading_rows_flipped']}"
        )
        self.stdout.write(
            f"DB-led pass: stale_uploading_candidates={d['db_stale_candidates']} "
            f"multipart_aborts={'0' if dry_run else d['multipart_aborted']} "
            f"uploading_flipped_or_would={d['uploading_rows_flipped']}"
        )
