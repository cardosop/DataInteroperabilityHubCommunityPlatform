"""
Phase 235.4.10 — every-5-minutes Impersonation expiration sweep.

Mirrors the Phase 235.3 ``tenant_hard_delete_sweep`` command shape:
creates a ``Job`` observability row, invokes the work function, then
marks the Job complete/failed.

Kubernetes wiring (every 5 minutes):

.. code-block:: yaml

    apiVersion: batch/v1
    kind: CronJob
    metadata:
      name: impersonation-expire
    spec:
      schedule: "*/5 * * * *"
      jobTemplate:
        spec:
          template:
            spec:
              containers:
              - name: api
                image: <hub-api-image>
                command: ["python", "hub/manage.py",
                          "expire_impersonation_sessions"]
              restartPolicy: OnFailure
"""
from __future__ import annotations
import uuid

from django.core.management.base import BaseCommand
from django.utils import timezone

from hub.apps.jobs.models import Job, JobPriority, JobStatus, JobType
from hub.apps.tenants.expire_impersonation_sweep import (
    run_expire_impersonation_sessions,
)


class Command(BaseCommand):
    help = (
        "Phase 235.4 — end ACTIVE ImpersonationSession rows whose "
        "expires_at has elapsed. Stamps ``end_reason='expired'`` and "
        "emits one IMPERSONATION_ENDED audit row per ended session."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-job-row",
            action="store_true",
            help="Do not persist a Job observability row (smoke tests).",
        )

    def handle(self, *args, **options):
        skip_job = bool(options.get("skip_job_row", False))

        resource_key = uuid.uuid4()
        job_row: Job | None = None
        if not skip_job:
            job_row = Job.objects.create(
                tenant=None,
                type=JobType.IMPERSONATION_EXPIRE_SWEEP,
                status=JobStatus.RUNNING,
                priority=JobPriority.NORMAL,
                resource_type="SYSTEM",
                resource_id=resource_key,
                started_at=timezone.now(),
                details_json={},
            )

        sweep_run_id = str(job_row.id) if job_row is not None else str(resource_key)

        try:
            summary = run_expire_impersonation_sessions(sweep_run_id=sweep_run_id)
            self.stdout.write(
                self.style.SUCCESS(f"Impersonation expire sweep: {summary}")
            )
            if job_row is not None:
                job_row.mark_completed(result_json={"summary": summary})
        except Exception as exc:
            if job_row is not None:
                job_row.mark_failed(str(exc))
            raise
