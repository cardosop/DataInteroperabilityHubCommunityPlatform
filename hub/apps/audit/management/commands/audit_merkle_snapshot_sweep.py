"""
Phase 234.1.5 — hourly Merkle-snapshot sweep across all tenants + platform chain.

CronJob-facing entry point. Mirrors
``hub/apps/governance/management/commands/retention_enforcement_sweep.py``:
creates a ``Job`` observability row, invokes the snapshot pipeline, then
marks the Job complete/failed.

Kubernetes wiring (per Phase 234.1.5 — "runs hourly per tenant"):

.. code-block:: yaml

    apiVersion: batch/v1
    kind: CronJob
    metadata:
      name: audit-merkle-snapshot-hourly
    spec:
      schedule: "0 * * * *"  # top of every hour
      jobTemplate:
        spec:
          template:
            spec:
              containers:
              - name: audit
                image: <hub-api-image>
                command: ["python", "hub/manage.py",
                          "audit_merkle_snapshot_sweep"]
              restartPolicy: OnFailure

Options
=======

* ``--window-hours N`` — width of each tenant's snapshot window (default 1).
* ``--skip-job-row`` — skip the observability ``Job`` row (local smoke tests).
* ``--tenant-id <uuid>`` — restrict to a single tenant (debug / re-snap). Pass
  ``__platform__`` for the no-tenant chain. Omit to fan out across all tenants.
"""
from __future__ import annotations
import uuid

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from hub.apps.jobs.models import Job, JobPriority, JobStatus, JobType


class Command(BaseCommand):
    help = (
        "Phase 234.1.5 — produce hourly Merkle snapshots for the per-tenant "
        "audit hash chain (and the platform-level chain). Run via the "
        "audit-merkle-snapshot-hourly CronJob."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--window-hours",
            type=int,
            default=1,
            help="Width of each tenant's snapshot window in hours (default: 1).",
        )
        parser.add_argument(
            "--skip-job-row",
            action="store_true",
            help="Do not persist a Job observability row (local smoke tests).",
        )
        parser.add_argument(
            "--tenant-id",
            type=str,
            default=None,
            help=(
                "Restrict to a single tenant UUID, or '__platform__' for the "
                "no-tenant chain. Omit to sweep every tenant + the platform "
                "chain (the canonical hourly path)."
            ),
        )

    def handle(self, *args, **options):
        window_hours = int(options.get("window_hours", 1))
        skip_job = bool(options.get("skip_job_row", False))
        tenant_arg = options.get("tenant_id")

        if window_hours < 1:
            raise CommandError("--window-hours must be >= 1")

        # Local import keeps the command thin and lets the audit app
        # finish AppConfig.ready() before we touch the snapshot pipeline.
        from hub.apps.audit.merkle import (
            snapshot_all_tenants_now,
            snapshot_tenant_window,
        )

        resource_key = uuid.uuid4()
        job_row: Job | None = None
        if not skip_job:
            job_row = Job.objects.create(
                tenant=None,
                type=JobType.AUDIT_MERKLE_SNAPSHOT,
                status=JobStatus.RUNNING,
                priority=JobPriority.NORMAL,
                resource_type="SYSTEM",
                resource_id=resource_key,
                started_at=timezone.now(),
                details_json={"window_hours": window_hours, "tenant_id": tenant_arg},
            )

        try:
            if tenant_arg:
                # Single-tenant path. Resolve the Tenant row (or None for
                # the platform chain) and compute the bucketed window
                # explicitly so the result matches what the all-tenants
                # path would produce for the same wall-clock minute.
                from datetime import timedelta

                from hub.apps.tenants.models import Tenant

                normalized = tenant_arg.strip()
                if normalized in ("", "__platform__"):
                    target = None
                else:
                    try:
                        target = Tenant.objects.get(id=normalized)
                    except (Tenant.DoesNotExist, ValueError) as exc:
                        raise CommandError(
                            f"--tenant-id={tenant_arg!r}: tenant not found"
                        ) from exc

                now = timezone.now()
                period_end = now.replace(minute=0, second=0, microsecond=0)
                period_start = period_end - timedelta(hours=window_hours)
                row = snapshot_tenant_window(
                    tenant=target,
                    period_start=period_start,
                    period_end=period_end,
                )
                rows = [row]
            else:
                rows = snapshot_all_tenants_now(window_hours=window_hours)

            summary = {
                "snapshots_produced": len(rows),
                "window_hours": window_hours,
            }
            self.stdout.write(self.style.SUCCESS(
                f"Audit Merkle sweep: {summary}"
            ))
            if job_row is not None:
                job_row.mark_completed(result_json={"summary": summary})
        except Exception as exc:
            if job_row is not None:
                job_row.mark_failed(str(exc))
            raise
