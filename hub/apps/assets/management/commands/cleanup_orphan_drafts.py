"""
Phase 250.1.E.1 — orphan-DRAFT cleanup sweep.

Hard-deletes ``Asset`` rows that are stuck in ``DRAFT`` status past the
configured age threshold (default 30 days). These are the long-tail of
pre-Phase-250.1.A workflow runs that never progressed past ``DRAFT``,
plus any future runs that abort between ``asset_create`` and
``activate`` without compensation deletion.

Behaviour
---------

* Iterates tenants (or one tenant via ``--tenant-id``).
* For each tenant, walks ``Asset.objects.filter(status=DRAFT,
  created_at < now - age_threshold)`` in ``--batch-size`` chunks
  (default 500).
* Per batch: hard-deletes the rows AND emits one
  ``ASSET_ORPHAN_DRAFT_PURGED`` audit row with diagnostic
  ``details_json``.
* Default ``--dry-run=False``; the env-var ``ASSET_ORPHAN_CLEANUP_DRY_RUN=true``
  forces dry-run regardless of CLI flag (D240.16 7-day post-deploy
  safety net). Pass ``--no-dry-run`` to override the env var.

Why a Django management command?
--------------------------------
Following the existing precedent in this repo (``purge_dq_runs``,
``recover-stuck-jobs``, ``backup-fuseki-tdb2``, ``mailhog-prune``,
``collect_dq_s3_metrics``, ``sample_dq_queue_depth``): scheduled work
runs as Django management commands invoked by Kubernetes CronJobs (no
Celery beat, no rq-scheduler dependency). The Helm CronJob for THIS
command lives at ``helm/templates/cronjob/cleanup-orphan-drafts.yaml``.

Idempotency
-----------
A re-invocation on the same DB state produces the same DB state. In
non-dry-run mode the second sweep finds zero orphans (the first
deleted them). In dry-run mode each invocation accumulates one audit
row per batch — intentional, so audit replay can reconstruct the
observation timeline.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import timedelta
from typing import List, Optional

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone


logger = logging.getLogger(__name__)


#: Default batch size — small enough that the per-batch transaction
#: doesn't hold locks for long; large enough to amortise the
#: ``DELETE ... WHERE id IN (...)`` round-trips. Mirrors purge_dq_runs.
DEFAULT_BATCH_SIZE: int = 500

#: Default orphan age threshold per docs/runbooks/orphan-draft-cleanup.md.
DEFAULT_AGE_THRESHOLD_DAYS: int = 30

#: Cap on the number of asset_ids carried in audit details_json for
#: SRE triage. The full batch may be N rows; we sample the first
#: 10 to keep audit row size bounded while still giving operators
#: a starting point for spot-checks.
_AUDIT_ASSET_ID_SAMPLE_SIZE: int = 10


# ---------------------------------------------------------------------------
# Audit emission
# ---------------------------------------------------------------------------


def _emit_purged_audit(
    *,
    tenant,
    count: int,
    dry_run: bool,
    batch: int,
    age_threshold_days: int,
    asset_ids: list[str],
    correlation_id: str,
) -> None:
    """Emit one ``ASSET_ORPHAN_DRAFT_PURGED`` audit row per batch.

    ``correlation_id`` is the per-sweep UUID stamped on every batch
    row from a single cron invocation — SRE filters on it to see
    "what happened in last night's 04:00 sweep" without joining on
    timestamp windows.

    Best-effort — wrapped in try/except so an audit-backend hiccup
    doesn't crash the sweep (we'd rather lose one audit row than
    skip a batch's deletion).
    """
    try:
        from hub.apps.audit import event_types as audit_event_types
        from hub.apps.audit.utils import create_audit_event

        create_audit_event(
            resource_type=audit_event_types.ASSET_RESOURCE_TYPE,
            action=audit_event_types.ASSET_ORPHAN_DRAFT_PURGED,
            actor_user=None,
            tenant=tenant,
            resource_id=None,
            result="SUCCESS",
            details={
                "tenant_id": str(tenant.id),
                "count": count,
                "dry_run": dry_run,
                "batch": batch,
                "age_threshold_days": age_threshold_days,
                "asset_ids": asset_ids[:_AUDIT_ASSET_ID_SAMPLE_SIZE],
                "correlation_id": correlation_id,
            },
        )
    except Exception as exc:  # noqa: BLE001 — boundary
        logger.warning(
            "cleanup_orphan_drafts_audit_emit_failed tenant_id=%s "
            "batch=%s error=%s",
            tenant.id, batch, exc,
        )


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------


class Command(BaseCommand):
    help = (
        "Phase 250.1.E.1 — hard-delete orphan DRAFT assets older than "
        "--age-threshold-days (default 30). Idempotent + batched. "
        "Default dry-run when ASSET_ORPHAN_CLEANUP_DRY_RUN=true."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Report counts without deleting. Default false.",
        )
        parser.add_argument(
            "--no-dry-run",
            action="store_true",
            default=False,
            help=(
                "Explicitly disable dry-run, overriding the "
                "ASSET_ORPHAN_CLEANUP_DRY_RUN env-var safety net."
            ),
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=DEFAULT_BATCH_SIZE,
            help=f"Rows per batch (default {DEFAULT_BATCH_SIZE}).",
        )
        parser.add_argument(
            "--age-threshold-days",
            type=int,
            default=DEFAULT_AGE_THRESHOLD_DAYS,
            help=(
                f"Minimum age in days for a DRAFT to be considered "
                f"orphan (default {DEFAULT_AGE_THRESHOLD_DAYS})."
            ),
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
        age_threshold_days = int(
            opts.get("age_threshold_days") or DEFAULT_AGE_THRESHOLD_DAYS
        )
        tenant_id_filter = opts.get("tenant_id")

        # 7-day safety net per D240.16 / D250.12 — env var forces
        # dry-run unless --no-dry-run was explicitly set.
        env_dry_run = os.environ.get(
            "ASSET_ORPHAN_CLEANUP_DRY_RUN", ""
        ).lower() in ("1", "true", "yes")
        if env_dry_run and not no_dry_run:
            dry_run = True
            self.stdout.write(self.style.WARNING(
                "ASSET_ORPHAN_CLEANUP_DRY_RUN env-var set; forcing "
                "--dry-run (pass --no-dry-run to override)."
            ))

        from hub.apps.assets.models import Asset, AssetStatus
        from hub.apps.tenants.models import Tenant

        tenants_qs = Tenant.objects.all()
        if tenant_id_filter:
            tenants_qs = tenants_qs.filter(pk=tenant_id_filter)

        # One UUID per cron-run stamped on every batch's audit row
        # so SRE can answer "show me what last night's 04:00 sweep
        # touched" with a single filter on details_json.correlation_id.
        correlation_id = str(uuid.uuid4())

        # Surface the running config in stdout up front so the
        # K8s CronJob log scraper can grep for parameters per run.
        self.stdout.write(
            f"cleanup_orphan_drafts starting: "
            f"batch_size={batch_size} "
            f"age_threshold_days={age_threshold_days} "
            f"dry_run={dry_run} "
            f"tenant_id_filter={tenant_id_filter} "
            f"correlation_id={correlation_id}"
        )

        deleted_total = 0
        for tenant in tenants_qs.iterator(chunk_size=50):
            deleted_total += self._sweep_tenant(
                tenant=tenant,
                batch_size=batch_size,
                age_threshold_days=age_threshold_days,
                dry_run=dry_run,
                correlation_id=correlation_id,
            )

        action_word = "would delete" if dry_run else "deleted"
        self.stdout.write(self.style.SUCCESS(
            f"cleanup_orphan_drafts complete: {action_word} "
            f"{deleted_total} orphan DRAFT assets across "
            f"{tenants_qs.count()} tenant(s)."
        ))

    # ------------------------------------------------------------------
    # Per-tenant sweep
    # ------------------------------------------------------------------

    def _sweep_tenant(
        self,
        *,
        tenant,
        batch_size: int,
        age_threshold_days: int,
        dry_run: bool,
        correlation_id: str,
    ) -> int:
        """Walk + delete orphans for one tenant; return total processed.

        Each batch runs in its own transaction so the lock window stays
        short. In dry-run mode we run exactly one batch's worth of
        candidates so the loop doesn't spin (the candidates queryset
        doesn't shrink without DELETE).
        """
        from hub.apps.assets.models import Asset, AssetStatus

        cutoff = timezone.now() - timedelta(days=age_threshold_days)
        candidates = Asset.objects.filter(
            tenant=tenant,
            status=AssetStatus.DRAFT,
            created_at__lt=cutoff,
        ).order_by("created_at")

        total = 0
        batch_no = 0
        while True:
            batch_ids: List[str] = list(
                candidates.values_list("id", flat=True)[:batch_size]
            )
            if not batch_ids:
                break

            batch_no += 1
            count = len(batch_ids)
            asset_id_strs = [str(i) for i in batch_ids]

            if not dry_run:
                # Hard-delete in a per-batch transaction. Each row's
                # post_delete signal still fires (search-index
                # cleanup, etc. — the cascading work is the model's
                # responsibility, not ours).
                with transaction.atomic():
                    Asset.objects.filter(pk__in=batch_ids).delete()

            _emit_purged_audit(
                tenant=tenant,
                count=count,
                dry_run=dry_run,
                batch=batch_no,
                age_threshold_days=age_threshold_days,
                asset_ids=asset_id_strs,
                correlation_id=correlation_id,
            )

            total += count

            if dry_run:
                # In dry-run mode the candidates queryset doesn't
                # shrink (we didn't DELETE); bail after one batch
                # so we don't loop forever counting the same rows.
                # The audit row already reports `count` for the SRE.
                break

        return total
