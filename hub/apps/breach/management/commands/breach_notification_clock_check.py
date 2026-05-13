"""Periodic breach statutory notification SLA scan (Kubernetes CronJob / ops)."""

from __future__ import annotations

import uuid

from django.core.management.base import BaseCommand
from django.utils import timezone

from hub.apps.breach.sla_metrics import emit_breach_sla_metrics
from hub.apps.breach.sla_scan import run_breach_notification_clock_scan
from hub.apps.jobs.models import Job, JobPriority, JobStatus, JobType


class Command(BaseCommand):
    help = (
        "Evaluate breach supervisory-notification deadlines — warn / alert / escalate (Phase 232.3.7)."
    )

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
                type=JobType.BREACH_NOTIFICATION_CLOCK_CHECK,
                status=JobStatus.RUNNING,
                priority=JobPriority.NORMAL,
                resource_type="SYSTEM",
                resource_id=job_id,
                started_at=timezone.now(),
            )
        # Phase 277.B.088 — emit SLA metrics before the scan so the gauge
        # reflects current state before any status updates are applied.
        sla_results = emit_breach_sla_metrics()
        counters = {}
        try:
            counters = run_breach_notification_clock_scan()
            self.stdout.write(self.style.SUCCESS(f"Breach SLA scan counters: {counters}"))
            if sla_results:
                oldest = sla_results[0]
                self.stdout.write(
                    f"  Breach SLA: {len(sla_results)} unresolved, "
                    f"oldest {oldest['hours']}h (id={oldest['breach_id']})"
                )
            if job_row:
                job_row.mark_completed(result_json={"counters": counters})
        except Exception as exc:
            if job_row:
                job_row.mark_failed(str(exc))
            raise
