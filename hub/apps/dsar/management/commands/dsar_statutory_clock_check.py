"""Daily statutory-clock scanner for DSAR pipeline (Kubernetes CronJob / RQ feeder)."""

from __future__ import annotations

import uuid

from django.core.management.base import BaseCommand
from django.utils import timezone

from hub.apps.dsar.sla_scan import run_dsar_statutory_clock_scan
from hub.apps.jobs.models import Job, JobPriority, JobStatus, JobType


class Command(BaseCommand):
    help = "Evaluate DSAR statutory deadlines — warn / alert / escalate (Phase 232.2.5)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-job-row",
            action="store_true",
            help="Do not persist a Job row (useful for local smoke tests)",
        )

    def handle(self, *args, **options):
        skip_job = options["skip_job_row"]
        job_id = uuid.uuid4()
        job_row = None
        if not skip_job:
            job_row = Job.objects.create(
                tenant=None,
                type=JobType.DSAR_STATUTORY_CLOCK_CHECK,
                status=JobStatus.RUNNING,
                priority=JobPriority.NORMAL,
                resource_type="SYSTEM",
                resource_id=job_id,
                started_at=timezone.now(),
            )
        counters = {}
        try:
            counters = run_dsar_statutory_clock_scan()
            self.stdout.write(self.style.SUCCESS(f"DSAR SLA scan counters: {counters}"))
            if job_row:
                job_row.mark_completed(result_json={"counters": counters})
        except Exception as exc:
            if job_row:
                job_row.mark_failed(str(exc))
            raise
