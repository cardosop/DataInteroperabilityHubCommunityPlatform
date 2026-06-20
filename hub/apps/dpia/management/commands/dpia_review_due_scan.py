"""Periodic DPIA review sweep — approved assessments past ``next_review_due_at`` (CronJob / ops)."""

from __future__ import annotations

import uuid

from django.core.management.base import BaseCommand
from django.utils import timezone

from hub.apps.dpia.services.review_due import run_dpia_review_due_scan
from hub.apps.jobs.models import Job, JobPriority, JobStatus, JobType


class Command(BaseCommand):
    help = "Re-open APPROVED DPIAs whose periodic review deadline has passed (Phase 232.5.5)."

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
                type=JobType.DPIA_REVIEW_DUE,
                status=JobStatus.RUNNING,
                priority=JobPriority.NORMAL,
                resource_type="SYSTEM",
                resource_id=job_id,
                started_at=timezone.now(),
            )
        counters = {}
        try:
            counters = run_dpia_review_due_scan()
            self.stdout.write(self.style.SUCCESS(f"DPIA review-due scan counters: {counters}"))
            if job_row:
                job_row.mark_completed(result_json={"counters": counters})
        except Exception as exc:
            if job_row:
                job_row.mark_failed(str(exc))
            raise
