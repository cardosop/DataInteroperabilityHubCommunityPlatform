"""
Phase 235.3 — daily Tenant hard-delete sweep (CronJob-facing entry point).

Mirrors the Phase 234.4 ``audit_permanent_delete_sweep`` command shape:
creates a ``Job`` observability row, invokes the work function, then
marks the Job complete/failed.

Kubernetes wiring (daily, off-peak):

.. code-block:: yaml

    apiVersion: batch/v1
    kind: CronJob
    metadata:
      name: tenant-hard-delete-daily
    spec:
      schedule: "30 4 * * *"  # 04:30 UTC daily
      jobTemplate:
        spec:
          template:
            spec:
              containers:
              - name: api
                image: <hub-api-image>
                command: ["python", "hub/manage.py",
                          "tenant_hard_delete_sweep"]
              restartPolicy: OnFailure

Options
=======

* ``--dry-run`` — preview deletions without persisting them.
* ``--skip-job-row`` — do not persist a ``Job`` observability row
  (local smoke tests).
"""

from __future__ import annotations

import uuid

from django.core.management.base import CommandError
from django.utils import timezone

from hub.apps.audit.command_audit import AuditedCommand
from hub.apps.jobs.models import Job, JobPriority, JobStatus, JobType
from hub.apps.tenants.tenant_hard_delete_sweep import run_tenant_hard_delete_sweep


class Command(AuditedCommand):
    help = (
        "Phase 235.3 — hard-delete Tenants past the 90-day grace window "
        "opened by the PLATFORM_ADMIN soft-delete endpoint. Re-checks "
        "legal_hold + DSAR-restriction at sweep time; emits one "
        "TENANT_HARD_DELETED audit row per tenant before the cascade."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview deletions without persisting them.",
        )
        parser.add_argument(
            "--skip-job-row",
            action="store_true",
            help="Do not persist a Job observability row (smoke tests).",
        )
        # P3-1 — the drill contract (pinned by the tenant-data-export
        # suite): the 90-day grace is bypassable ONLY for NAMED tenants
        # in a drill, and ONLY with the explicit --drill-skip-grace
        # flag. The legal-hold + DSAR re-checks stay enforced in every
        # mode.
        parser.add_argument(
            "--tenant-slug",
            dest="tenant_slug",
            action="append",
            default=None,
            help="Restrict the sweep to the named tenant slug(s) — drill mode.",
        )
        parser.add_argument(
            "--drill-skip-grace",
            dest="drill_skip_grace",
            action="store_true",
            help="Bypass the 90-day grace window (drill mode) — legal "
            "hold + DSAR re-checks remain enforced.",
        )

    def handle(self, *_args, **options):
        dry_run = bool(options.get("dry_run", False))
        skip_job = bool(options.get("skip_job_row", False))
        tenant_slug = options.get("tenant_slug") or None
        drill_skip_grace = bool(options.get("drill_skip_grace", False))
        if tenant_slug and not drill_skip_grace:
            raise CommandError(
                "--tenant-slug (drill mode) requires the explicit "
                "--drill-skip-grace flag — the grace bypass must be "
                "named, never incidental."
            )

        resource_key = uuid.uuid4()
        job_row: Job | None = None
        if not skip_job:
            job_row = Job.objects.create(
                tenant=None,
                type=JobType.TENANT_HARD_DELETE_SWEEP,
                status=JobStatus.RUNNING,
                priority=JobPriority.NORMAL,
                resource_type="SYSTEM",
                resource_id=resource_key,
                started_at=timezone.now(),
                details_json={"dry_run": dry_run},
            )

        sweep_run_id = str(job_row.id) if job_row is not None else str(resource_key)

        try:
            summary = run_tenant_hard_delete_sweep(
                dry_run=dry_run,
                sweep_run_id=sweep_run_id,
                tenant_slug=tenant_slug,
                drill_skip_grace=drill_skip_grace,
            )
            self.stdout.write(self.style.SUCCESS(f"Tenant hard-delete sweep: {summary}"))
            if job_row is not None:
                job_row.mark_completed(result_json={"summary": summary})
        except Exception as exc:
            if job_row is not None:
                job_row.mark_failed(str(exc))
            raise
