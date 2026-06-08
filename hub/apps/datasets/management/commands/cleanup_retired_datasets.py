"""
Phase 260.4.A.4 — hard-delete retired datasets past their retention window.

Designed to run on a Helm cron (default daily at 03:00 UTC). For each
``Dataset`` row with ``status = RETIRED`` AND
``retired_at < now - tenant.dataset_retain_after_retire_days``, delete
the row. Iterates per-tenant so every dataset is evaluated against
its OWNER tenant's retention policy (a tenant can shorten or lengthen
the window without code change).

Two safety nets:
    * ``--dry-run`` reports the eligible-row count without deleting.
    * The default-90-day retention window means a misconfigured cron
      cannot accidentally hard-delete a dataset that was retired today.
"""

from __future__ import annotations
from datetime import timedelta
from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone

from hub.apps.audit.event_types import DATASET_HARD_DELETED_AFTER_RETENTION
from hub.apps.audit.utils import create_audit_event
from hub.apps.datasets.models import Dataset
from hub.apps.tenants.models import Tenant


class Command(BaseCommand):
    help = (
        "Phase 260.4.A.4 — hard-delete RETIRED datasets older than "
        "their owner tenant's ``dataset_retain_after_retire_days`` "
        "window. Use ``--dry-run`` to preview eligible rows without "
        "deleting."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "List eligible rows + count without deleting. Useful "
                "before flipping the cron live for the first time."
            ),
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=10_000,
            help=(
                "Maximum rows to delete per run (defensive cap; "
                "default 10000 — the cleanup is per-tenant so a "
                "misconfigured huge tenant doesn't lock the table)."
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        dry_run: bool = bool(options.get("dry_run"))
        limit: int = int(options.get("limit") or 10_000)
        now = timezone.now()
        deleted_total = 0
        eligible_total = 0

        # Iterate per-tenant so every dataset is evaluated against
        # its OWNER tenant's retention window.
        tenants = Tenant.objects.all().only(
            "id", "dataset_retain_after_retire_days"
        )
        for tenant in tenants.iterator():
            window_days = int(tenant.dataset_retain_after_retire_days or 90)
            cutoff = now - timedelta(days=window_days)
            qs = Dataset.objects.filter(
                tenant_id=tenant.id,
                status="RETIRED",
                retired_at__lt=cutoff,
            ).order_by("retired_at")[:limit]

            count = qs.count()
            if count == 0:
                continue
            eligible_total += count

            if dry_run:
                self.stdout.write(
                    f"[dry-run] tenant={tenant.id} eligible={count} "
                    f"window_days={window_days}"
                )
                continue

            # Materialise the IDs first so the second-stage delete
            # doesn't trip on the slice + delete restriction in Django.
            ids = list(qs.values_list("id", flat=True))
            deleted_count, _ = Dataset.objects.filter(id__in=ids).delete()
            self.stdout.write(
                f"tenant={tenant.id} window_days={window_days} "
                f"deleted={deleted_count}"
            )
            deleted_total += deleted_count

            # Phase 260.4.A.R1 GAP-B fix: emit a per-tenant audit row
            # so 90-day-retention compliance regimes have a durable
            # trail of automated hard-deletions. One audit row per
            # tenant per run (NOT per deleted dataset) so a bulk
            # sweep doesn't flood the audit log; the row carries
            # ``deleted_count`` as the authoritative telemetry and
            # ``deleted_dataset_ids`` (truncated to first 100) for
            # forensic spot-checks.
            try:
                create_audit_event(
                    resource_type="DATASET",
                    action=DATASET_HARD_DELETED_AFTER_RETENTION,
                    actor_user=None,
                    tenant=tenant,
                    resource_id=None,
                    details={
                        "tenant_id": str(tenant.id),
                        "window_days": window_days,
                        "deleted_count": deleted_count,
                        "deleted_dataset_ids": [str(i) for i in ids[:100]],
                    },
                )
            except Exception as audit_err:
                # Audit emission must NOT block the cleanup — the
                # deletion is already durable on the row. Log so ops
                # has visibility but continue with the next tenant.
                self.stderr.write(
                    f"audit emit failed for tenant={tenant.id}: {audit_err}"
                )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY-RUN: {eligible_total} dataset row(s) would be hard-deleted."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Hard-deleted {deleted_total} retired dataset row(s) past retention."
                )
            )
