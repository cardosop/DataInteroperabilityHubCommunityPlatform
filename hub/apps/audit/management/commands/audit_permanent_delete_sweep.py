"""
Phase 234.4 — daily Audit permanent-delete sweep (CronJob-facing entry point).

Mirrors the Phase 232.7 ``retention_enforcement_sweep`` command shape:
creates a ``Job`` observability row, invokes the work function, then
marks the Job complete/failed.

Kubernetes wiring (daily, off-peak):

.. code-block:: yaml

    apiVersion: batch/v1
    kind: CronJob
    metadata:
      name: audit-permanent-delete-daily
    spec:
      schedule: "30 3 * * *"  # 03:30 UTC daily
      jobTemplate:
        spec:
          template:
            spec:
              containers:
              - name: audit
                image: <hub-api-image>
                command: ["python", "hub/manage.py",
                          "audit_permanent_delete_sweep"]
              restartPolicy: OnFailure

Options
=======

* ``--dry-run`` — preview deletions without persisting them (the
  meta-audit row is still written with ``dry_run=true``).
* ``--age-days N`` — grace threshold; default 90.
* ``--tenant-id <uuid>`` — restrict to one tenant; ``__platform__`` for
  the no-tenant chain. Omit to sweep every tenant.
* ``--skip-job-row`` — do not persist a ``Job`` observability row
  (local smoke tests).
"""
from __future__ import annotations
import uuid

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from hub.apps.audit.retention_purge import (
    DEFAULT_AGE_THRESHOLD_DAYS,
    run_audit_permanent_delete_sweep,
)
from hub.apps.jobs.models import Job, JobPriority, JobStatus, JobType


class Command(BaseCommand):
    help = (
        "Phase 234.4 — hard-delete archived AuditEvent rows past the "
        "configured grace window. Idempotent; emits one "
        "AUDIT_RETENTION_PURGED meta-audit per tenant per run."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview deletions without persisting them.",
        )
        parser.add_argument(
            "--age-days",
            type=int,
            default=DEFAULT_AGE_THRESHOLD_DAYS,
            help=(
                f"Grace window (days since archived_at). Default: "
                f"{DEFAULT_AGE_THRESHOLD_DAYS}."
            ),
        )
        parser.add_argument(
            "--tenant-id",
            type=str,
            default=None,
            help=(
                "Restrict to one tenant. Pass a UUID, or '__platform__' "
                "/ empty string for the platform chain. Omit to sweep "
                "every tenant."
            ),
        )
        parser.add_argument(
            "--skip-job-row",
            action="store_true",
            help="Do not persist a Job observability row (smoke tests).",
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run", False))
        age_days = int(options.get("age_days", DEFAULT_AGE_THRESHOLD_DAYS))
        tenant_arg = options.get("tenant_id")
        skip_job = bool(options.get("skip_job_row", False))

        if age_days < 1:
            raise CommandError("--age-days must be >= 1")

        resource_key = uuid.uuid4()
        job_row: Job | None = None
        if not skip_job:
            job_row = Job.objects.create(
                tenant=None,
                type=JobType.AUDIT_PERMANENT_DELETE_SWEEP,
                status=JobStatus.RUNNING,
                priority=JobPriority.NORMAL,
                resource_type="SYSTEM",
                resource_id=resource_key,
                started_at=timezone.now(),
                details_json={
                    "dry_run": dry_run,
                    "age_threshold_days": age_days,
                    "tenant_id": tenant_arg,
                },
            )

        try:
            summary = run_audit_permanent_delete_sweep(
                dry_run=dry_run,
                tenant_id=tenant_arg,
                age_threshold_days=age_days,
            )
            self.stdout.write(
                self.style.SUCCESS(f"Audit permanent-delete sweep: {summary}")
            )
            if job_row is not None:
                job_row.mark_completed(result_json={"summary": summary})
        except Exception as exc:
            if job_row is not None:
                job_row.mark_failed(str(exc))
            raise
