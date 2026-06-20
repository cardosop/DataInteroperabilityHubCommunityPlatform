"""
Phase 240.1.C.4 — DQ retention sweeper.

Two-phase purge with an audit trail:

1. **Soft-delete pass.** For each tenant, mark every ``DQRun`` whose
   ``created_at`` is older than the tenant's ``dq_run_retention_days``
   as ``is_deleted=True`` and stamp ``deleted_at``. Default manager
   semantics hide these rows from API queries immediately.

2. **Hard-delete pass.** Soft-deleted rows whose ``deleted_at`` is
   older than the fixed 30-day grace window (D240.7) are removed
   from the database AND their corresponding S3 payload prefix
   (``s3://<DQ_S3_BUCKET>/<DQ_S3_PREFIX>{run_id}/``) is wiped via
   ``S3StorageClient.delete_prefix``.

Each phase emits a ``DQ_RUN_PURGED`` audit row per batch with
``details_json={"phase": "soft_delete"|"hard_delete", "tenant_id":
..., "count": N, "dry_run": bool, "batch": K}`` so the auditor can
reconstruct the retention timeline without log scraping.

Safety nets
-----------
* ``--dry-run`` (default false in code) — report counts without
  mutating; combine with ``--batch-size`` to estimate runtime.
* ``DQ_PURGE_DRY_RUN=1`` env var (D240.16 first-7-days safety net)
  forces dry-run mode regardless of CLI flags. ``--no-dry-run``
  explicitly overrides.
* Batched processing — each pass walks rows in ``batch_size``
  chunks (default 500) so a single transaction never holds locks
  on the entire history.

Why a Django management command?
--------------------------------
Following the existing precedent in this repo (``recover-stuck-jobs``,
``backup-fuseki-tdb2``, ``mailhog-prune``, ``collect_dq_s3_metrics``,
``sample_dq_queue_depth``): scheduled work runs as Django
management commands invoked by Kubernetes CronJobs (no Celery beat,
no rq-scheduler dependency). The Helm CronJob for THIS command
lives at ``helm/templates/cronjob/purge-dq-runs.yaml``.
"""

from __future__ import annotations

import logging
import os
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


#: Fixed grace window between soft-delete and hard-delete (D240.7).
HARD_DELETE_GRACE_DAYS: int = 30

#: Default batch size — small enough that the per-batch transaction
#: doesn't hold locks for long; large enough to amortise the
#: ``UPDATE ... WHERE id IN (...)`` round-trips.
DEFAULT_BATCH_SIZE: int = 500


# ---------------------------------------------------------------------------
# Audit emission
# ---------------------------------------------------------------------------


def _emit_purged_audit(*, tenant, phase: str, count: int, dry_run: bool, batch: int) -> None:
    """Emit a ``DQ_RUN_PURGED`` audit row.

    Best-effort — wrapped in a try/except so an audit-backend hiccup
    doesn't crash the purge sweep (we'd rather lose one audit row
    than skip half a tenant's retention).
    """
    try:
        from hub.apps.audit.utils import create_audit_event

        create_audit_event(
            resource_type="DQ_RUN",
            action="DQ_RUN_PURGED",
            actor_user=None,
            tenant=tenant,
            resource_id=None,
            result="SUCCESS",
            details={
                "phase": phase,
                "tenant_id": str(tenant.id),
                "count": count,
                "dry_run": dry_run,
                "batch": batch,
            },
        )
    except Exception as exc:
        logger.warning(
            "purge_dq_runs_audit_emit_failed tenant_id=%s phase=%s error=%s",
            tenant.id,
            phase,
            exc,
        )


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------


class Command(BaseCommand):
    help = (
        "Phase 240.1.C — soft-delete DQRun rows past tenant retention; "
        "hard-delete soft-deleted rows past the 30-day grace window. "
        "Idempotent and batched."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Report counts without writing. Default false.",
        )
        parser.add_argument(
            "--no-dry-run",
            action="store_true",
            default=False,
            help=(
                "Explicitly disable dry-run, overriding the "
                "DQ_PURGE_DRY_RUN env-var safety net (D240.16)."
            ),
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=DEFAULT_BATCH_SIZE,
            help=f"Rows per batch (default {DEFAULT_BATCH_SIZE}).",
        )
        parser.add_argument(
            "--tenant-id",
            type=str,
            default=None,
            help="Limit to a single tenant (testing / one-off ops).",
        )

    def handle(self, *args, **opts):
        dry_run = bool(opts.get("dry_run"))
        no_dry_run = bool(opts.get("no_dry_run"))
        batch_size = int(opts.get("batch_size") or DEFAULT_BATCH_SIZE)
        tenant_id_filter = opts.get("tenant_id")

        # D240.16 safety net — if the env var is truthy AND the
        # operator did not explicitly pass --no-dry-run, force dry-
        # run regardless of the CLI flag.
        env_dry_run = os.environ.get("DQ_PURGE_DRY_RUN", "").lower() in (
            "1",
            "true",
            "yes",
        )
        if env_dry_run and not no_dry_run:
            dry_run = True
            self.stdout.write(
                self.style.WARNING(
                    "DQ_PURGE_DRY_RUN env-var set; forcing --dry-run "
                    "(pass --no-dry-run to override)."
                )
            )

        from hub.apps.tenants.models import Tenant

        tenants_qs = Tenant.objects.all()
        if tenant_id_filter:
            tenants_qs = tenants_qs.filter(pk=tenant_id_filter)

        soft_deleted_total = 0
        hard_deleted_total = 0

        for tenant in tenants_qs.iterator(chunk_size=50):
            soft_deleted_total += self._soft_delete_for_tenant(
                tenant=tenant,
                batch_size=batch_size,
                dry_run=dry_run,
            )
            hard_deleted_total += self._hard_delete_for_tenant(
                tenant=tenant,
                batch_size=batch_size,
                dry_run=dry_run,
            )

        action = "would soft-delete" if dry_run else "soft-deleted"
        action_h = "would hard-delete" if dry_run else "hard-deleted"
        self.stdout.write(
            self.style.SUCCESS(
                f"purge_dq_runs complete: {action} {soft_deleted_total} "
                f"runs; {action_h} {hard_deleted_total} runs."
            )
        )

    # ---- soft-delete pass ------------------------------------------------

    def _soft_delete_for_tenant(
        self,
        *,
        tenant,
        batch_size: int,
        dry_run: bool,
    ) -> int:
        from hub.apps.dq.models import DQRun

        retention_days = int(
            getattr(tenant, "dq_run_retention_days", 90) or 90,
        )
        cutoff = timezone.now() - timedelta(days=retention_days)
        candidates = DQRun.all_objects.filter(
            tenant=tenant,
            is_deleted=False,
            created_at__lt=cutoff,
        ).order_by("created_at")

        total = 0
        batch_no = 0
        while True:
            batch_ids: list[str] = list(candidates.values_list("id", flat=True)[:batch_size])
            if not batch_ids:
                break
            batch_no += 1
            if not dry_run:
                # Stamp deleted_at uniformly within the batch — easier
                # to reason about than per-row clock skew.
                DQRun.all_objects.filter(pk__in=batch_ids).update(
                    is_deleted=True,
                    deleted_at=timezone.now(),
                )
            count = len(batch_ids)
            total += count
            _emit_purged_audit(
                tenant=tenant,
                phase="soft_delete",
                count=count,
                dry_run=dry_run,
                batch=batch_no,
            )
            if dry_run:
                # In dry-run mode the candidates queryset doesn't
                # shrink; bail after one batch so we don't loop
                # forever counting the same rows.
                break
        return total

    # ---- hard-delete pass + S3 cleanup -----------------------------------

    def _hard_delete_for_tenant(
        self,
        *,
        tenant,
        batch_size: int,
        dry_run: bool,
    ) -> int:
        from hub.apps.dq.models import DQRun

        cutoff = timezone.now() - timedelta(days=HARD_DELETE_GRACE_DAYS)
        candidates = DQRun.all_objects.filter(
            tenant=tenant,
            is_deleted=True,
            deleted_at__lt=cutoff,
        ).order_by("deleted_at")

        total = 0
        batch_no = 0
        s3_client = self._maybe_get_s3_client()
        bucket, prefix = self._dq_s3_target()

        while True:
            batch_rows = list(candidates.values("id")[:batch_size])
            if not batch_rows:
                break
            batch_no += 1
            batch_ids = [row["id"] for row in batch_rows]

            if not dry_run:
                # 1. S3 cleanup BEFORE the DB delete so that on a
                #    crash mid-batch we re-process the same rows
                #    next sweep (the S3 prefix is already idempotent
                #    via delete_prefix returning 0 on empty).
                if s3_client and bucket:
                    for run_id in batch_ids:
                        run_prefix = f"{prefix}{run_id}"
                        try:
                            s3_client.delete_prefix(
                                run_prefix,
                                bucket=bucket,
                            )
                        except Exception as exc:
                            logger.warning(
                                "purge_dq_runs_s3_cleanup_failed tenant_id=%s run_id=%s error=%s",
                                tenant.id,
                                run_id,
                                exc,
                            )
                # 2. DB delete.
                DQRun.all_objects.filter(pk__in=batch_ids).delete()

            count = len(batch_ids)
            total += count
            _emit_purged_audit(
                tenant=tenant,
                phase="hard_delete",
                count=count,
                dry_run=dry_run,
                batch=batch_no,
            )
            if dry_run:
                break
        return total

    # ---- helpers ---------------------------------------------------------

    def _maybe_get_s3_client(self):
        """Build an S3 client, or return None if S3 isn't configured.

        Centralised so test environments without ``boto3`` /
        ``AWS_STORAGE_BUCKET_NAME`` skip the S3 step gracefully
        rather than crashing the entire purge.
        """
        try:
            from hub.apps.files.storage import S3StorageClient

            return S3StorageClient()
        except Exception as exc:
            logger.warning(
                "purge_dq_runs_s3_client_unavailable error=%s",
                exc,
            )
            return None

    def _dq_s3_target(self) -> tuple:
        bucket: str | None = getattr(
            settings,
            "DQ_S3_BUCKET",
            getattr(settings, "AWS_STORAGE_BUCKET_NAME", ""),
        )
        prefix: str = getattr(settings, "DQ_S3_PREFIX", "dq/") or "dq/"
        if not prefix.endswith("/"):
            prefix = prefix + "/"
        return bucket, prefix
