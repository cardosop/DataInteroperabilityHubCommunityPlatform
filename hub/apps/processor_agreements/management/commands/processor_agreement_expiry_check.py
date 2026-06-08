"""Periodic processor-agreement expiry sweep (Phase 232.6.7)."""

from __future__ import annotations
import uuid

from django.core.management.base import BaseCommand
from django.utils import timezone

from hub.apps.jobs.models import Job, JobPriority, JobStatus, JobType
from hub.apps.processor_agreements.expiry_scan import run_processor_agreement_expiry_scan


class Command(BaseCommand):
    help = (
        "Scan processor agreements for 60/30/7-day supervisory expiry reminders "
        "and expired status (Phase 232.6.7)."
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
                type=JobType.PROCESSOR_AGREEMENT_EXPIRY_CHECK,
                status=JobStatus.RUNNING,
                priority=JobPriority.NORMAL,
                resource_type="SYSTEM",
                resource_id=job_id,
                started_at=timezone.now(),
            )
        counters: dict[str, int] = {}
        try:
            counters = run_processor_agreement_expiry_scan()
            self.stdout.write(self.style.SUCCESS(f"Processor agreement expiry scan: {counters}"))
            if job_row:
                job_row.mark_completed(result_json={"counters": counters})
        except Exception as exc:
            if job_row:
                job_row.mark_failed(str(exc))
            raise
