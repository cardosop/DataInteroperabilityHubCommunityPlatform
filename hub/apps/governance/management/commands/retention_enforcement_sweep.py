"""Phase 232.7 — CronJob-facing retention tombstone/hard-delete sweep (cross-tenant, flag gated)."""

from __future__ import annotations

import uuid

from django.core.management.base import BaseCommand
from django.utils import timezone

from hub.apps.governance.retention_auto_enforcer import run_retention_enforcement_sweep
from hub.apps.jobs.models import Job, JobPriority, JobStatus, JobType


class Command(BaseCommand):
    help = (
        "Run the Phase 232.7 retention auto-sweep across tenants flagged "
        "``compliance_retention_enforcer_enabled`` (tombstone + 90-day grace + hard delete)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview candidate policies without soft/hard deletes (audit footer still emits).",
        )
        parser.add_argument(
            "--skip-job-row",
            action="store_true",
            help="Do not persist a Job observability row (local smoke tests).",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        skip_job = options["skip_job_row"]

        resource_key = uuid.uuid4()
        job_row = None
        if not skip_job:
            job_row = Job.objects.create(
                tenant=None,
                type=JobType.RETENTION_ENFORCEMENT_SWEEP,
                status=JobStatus.RUNNING,
                priority=JobPriority.NORMAL,
                resource_type="SYSTEM",
                resource_id=resource_key,
                started_at=timezone.now(),
                details_json={"dry_run": dry_run},
            )

        try:
            counters = run_retention_enforcement_sweep(dry_run=dry_run)
            self.stdout.write(self.style.SUCCESS(f"Retention autosweep counters: {counters}"))
            if job_row:
                job_row.mark_completed(result_json=counters)
        except Exception as exc:
            if job_row:
                job_row.mark_failed(str(exc))
            raise
