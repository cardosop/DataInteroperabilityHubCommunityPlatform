"""
Django management command to recover stuck and orphaned jobs.

Phase 13.2 — Stuck RUNNING jobs:
  A "stuck" job is one whose worker process crashed or was killed after the
  PENDING→RUNNING atomic claim but before it could write a terminal status.
  This command marks them FAILED so downstream consumers are not misled.

Phase 25.8.1 — ScheduledIngestionRun sync:
  When a SCHEDULED_INGESTION Job is recovered, the corresponding
  ScheduledIngestionRun is also marked FAILED and the DLQ is synced.

Phase 25.8.2 — Orphaned PENDING jobs:
  Jobs stuck in PENDING beyond their timeout + 60 s grace period (and not
  executed by Prefect) are re-enqueued once.  If re-enqueue fails, they are
  marked FAILED with error_code ORPHANED_PENDING.

Designed to run every 15 minutes via a Kubernetes CronJob.
"""

import contextlib
from datetime import timedelta

import structlog
from django.core.management.base import BaseCommand
from django.utils import timezone

from hub.apps.audit.utils import create_audit_event
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.jobs.utils import get_job_timeout

logger = structlog.get_logger(__name__)

DEFAULT_THRESHOLD_MINUTES = 120  # 2 hours


class Command(BaseCommand):
    help = (
        "Recover RUNNING jobs whose worker died and PENDING jobs that were "
        "never picked up. Runs every 15 minutes via CronJob (13.2 / 25.8)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--threshold-minutes",
            type=int,
            default=DEFAULT_THRESHOLD_MINUTES,
            help=(
                "Jobs running longer than this many minutes without completing "
                f"are considered stuck (default: {DEFAULT_THRESHOLD_MINUTES})."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="List stuck/orphaned jobs without modifying them.",
        )

    def handle(self, *args, **options):
        threshold_minutes: int = options["threshold_minutes"]
        dry_run: bool = options["dry_run"]

        stuck = self._recover_stuck_running(threshold_minutes, dry_run)
        orphaned = self._recover_orphaned_pending(dry_run)
        prefect_orphans = self._recover_prefect_orphans(dry_run)

        if stuck == 0 and orphaned == 0 and prefect_orphans == 0:
            self.stdout.write(self.style.SUCCESS("No stuck jobs found"))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Recovered {stuck} stuck RUNNING + {orphaned} orphaned PENDING"
                    f" + {prefect_orphans} Prefect orphan(s)."
                )
            )

    # ------------------------------------------------------------------
    # Phase 13.2 — Stuck RUNNING jobs
    # ------------------------------------------------------------------
    def _recover_stuck_running(self, threshold_minutes: int, dry_run: bool) -> int:
        cutoff = timezone.now() - timedelta(minutes=threshold_minutes)

        stuck_jobs = (
            Job.objects.filter(
                status=JobStatus.RUNNING,
                started_at__lt=cutoff,
            )
            .select_related("created_by", "tenant")
            .order_by("started_at")
        )

        count = stuck_jobs.count()
        if count == 0:
            logger.info(
                "recover_stuck_jobs_none_found",
                threshold_minutes=threshold_minutes,
            )
            return 0

        self.stdout.write(f"Found {count} stuck RUNNING job(s) (> {threshold_minutes} min).")

        if dry_run:
            for job_obj in stuck_jobs:
                self.stdout.write(
                    f"  [DRY-RUN] {job_obj.id}  type={job_obj.type}"
                    f"  started={job_obj.started_at.isoformat()}"
                )
            return 0

        now = timezone.now()
        recovered = 0
        for job_obj in stuck_jobs:
            error_msg = (
                f"Job recovered by recover_stuck_jobs after "
                f"{threshold_minutes} minutes in RUNNING state "
                f"(worker likely crashed)."
            )
            job_obj.status = JobStatus.FAILED
            job_obj.completed_at = now
            job_obj.error_message = error_msg
            job_obj.result_json = {
                "error": error_msg,
                "error_code": "WORKER_DIED",
            }
            job_obj.save(
                update_fields=[
                    "status",
                    "completed_at",
                    "error_message",
                    "result_json",
                ]
            )

            logger.warning(
                "recover_stuck_job",
                job_id=str(job_obj.id),
                job_type=job_obj.type,
                started_at=job_obj.started_at.isoformat(),
                threshold_minutes=threshold_minutes,
            )

            # Phase 25.8.1 — Sync ScheduledIngestionRun + DLQ
            if job_obj.type == JobType.SCHEDULED_INGESTION:
                self._sync_ingestion_run(job_obj)

            try:
                create_audit_event(
                    resource_type="JOB",
                    action="JOB_RECOVERED",
                    actor_user=None,
                    tenant=job_obj.tenant,
                    resource_id=str(job_obj.id),
                    details={
                        "job_type": job_obj.type,
                        "started_at": job_obj.started_at.isoformat(),
                        "threshold_minutes": threshold_minutes,
                    },
                )
            except Exception as exc:
                logger.error(
                    "recover_stuck_job_audit_failed",
                    job_id=str(job_obj.id),
                    error=str(exc),
                )

            recovered += 1

        logger.info(
            "recover_stuck_jobs_complete",
            recovered=recovered,
            threshold_minutes=threshold_minutes,
        )
        return recovered

    # ------------------------------------------------------------------
    # Phase 25.8.1 — Sync ScheduledIngestionRun when Job recovered
    # ------------------------------------------------------------------
    @staticmethod
    def _sync_ingestion_run(job_obj: Job):
        """
        When a SCHEDULED_INGESTION Job is marked FAILED, find the
        corresponding ScheduledIngestionRun via Job.resource_id and
        mark it FAILED too.  Then sync the DLQ.
        """
        try:
            from hub.apps.scheduled_ingestion.models import (
                ScheduledIngestionRun,
                ScheduledIngestionRunStatus,
            )

            updated = ScheduledIngestionRun.objects.filter(
                scheduled_ingestion_id=job_obj.resource_id,
                status__in=[
                    ScheduledIngestionRunStatus.PENDING,
                    ScheduledIngestionRunStatus.RUNNING,
                ],
                job_id=job_obj.id,
            ).update(
                status=ScheduledIngestionRunStatus.FAILED,
                error_message="Worker process died (recovered by recover_stuck_jobs)",
            )

            if updated:
                logger.info(
                    "recover_stuck_ingestion_run_synced",
                    job_id=str(job_obj.id),
                    resource_id=str(job_obj.resource_id),
                    runs_updated=updated,
                )

            # Sync DLQ from ingestion state
            try:
                from hub.apps.scheduled_ingestion.dead_letter_queue import (
                    DeadLetterQueueManager,
                )

                DeadLetterQueueManager.sync_from_ingestion_state(str(job_obj.resource_id))
            except Exception as dlq_exc:
                logger.warning(
                    "recover_stuck_dlq_sync_failed",
                    job_id=str(job_obj.id),
                    error=str(dlq_exc),
                )

        except Exception as exc:
            logger.error(
                "recover_stuck_ingestion_run_sync_error",
                job_id=str(job_obj.id),
                error=str(exc),
                exc_info=True,
            )

    # ------------------------------------------------------------------
    # Phase 25.8.2 — Orphaned PENDING jobs
    # ------------------------------------------------------------------
    def _recover_orphaned_pending(self, dry_run: bool) -> int:
        """
        Find PENDING jobs whose creation time exceeds their job-type
        timeout + 60 s grace period and that are NOT executed by Prefect
        (Prefect-managed jobs have their own lifecycle).

        Attempt to re-enqueue each orphan once.  If that fails, mark FAILED.
        """
        now = timezone.now()
        grace_seconds = 60

        # Use the longest timeout as a coarse DB-level filter so we never
        # load thousands of recent PENDING jobs into memory.  The per-type
        # check below further narrows the set.
        max_timeout = max((get_job_timeout(jt) for jt in JobType), default=3600)
        coarse_cutoff = now - timedelta(seconds=max_timeout + grace_seconds)

        orphan_candidates = (
            Job.objects.filter(
                status=JobStatus.PENDING,
                created_at__lt=coarse_cutoff,
            )
            .exclude(details_json__executed_by_prefect=True)
            .select_related("tenant")
        )

        orphans = []
        for job_obj in orphan_candidates:
            timeout = get_job_timeout(job_obj.type)
            cutoff = now - timedelta(seconds=timeout + grace_seconds)
            if job_obj.created_at >= cutoff:
                continue  # Not old enough for *this* job type
            orphans.append(job_obj)

        if not orphans:
            return 0

        self.stdout.write(f"Found {len(orphans)} orphaned PENDING job(s).")

        if dry_run:
            for job_obj in orphans:
                self.stdout.write(
                    f"  [DRY-RUN] {job_obj.id}  type={job_obj.type}"
                    f"  created={job_obj.created_at.isoformat()}"
                )
            return 0

        recovered = 0
        for job_obj in orphans:
            # Attempt re-enqueue
            if self._try_reenqueue(job_obj):
                logger.info(
                    "recover_orphaned_pending_reenqueued",
                    job_id=str(job_obj.id),
                    job_type=job_obj.type,
                )
                recovered += 1
                continue

            # Re-enqueue failed — mark FAILED
            job_obj.status = JobStatus.FAILED
            job_obj.completed_at = now
            job_obj.error_message = (
                "Orphaned PENDING job: never picked up by worker "
                "(possible Redis enqueue failure). "
                "Recovered by recover_stuck_jobs."
            )
            job_obj.result_json = {
                "error": job_obj.error_message,
                "error_code": "ORPHANED_PENDING",
            }
            job_obj.save(
                update_fields=[
                    "status",
                    "completed_at",
                    "error_message",
                    "result_json",
                ]
            )

            # Phase 25.8.1 — Also sync ingestion run if applicable
            if job_obj.type == JobType.SCHEDULED_INGESTION:
                self._sync_ingestion_run(job_obj)

            logger.warning(
                "recover_orphaned_pending_failed",
                job_id=str(job_obj.id),
                job_type=job_obj.type,
                created_at=job_obj.created_at.isoformat(),
            )

            with contextlib.suppress(Exception):
                create_audit_event(
                    resource_type="JOB",
                    action="JOB_RECOVERED",
                    actor_user=None,
                    tenant=job_obj.tenant,
                    resource_id=str(job_obj.id),
                    details={
                        "job_type": job_obj.type,
                        "error_code": "ORPHANED_PENDING",
                        "created_at": job_obj.created_at.isoformat(),
                    },
                )

            recovered += 1

        logger.info(
            "recover_orphaned_pending_complete",
            recovered=recovered,
            total_orphans=len(orphans),
        )
        return recovered

    @staticmethod
    def _try_reenqueue(job_obj: Job) -> bool:
        """Attempt to re-enqueue a PENDING job. Returns True on success."""
        try:
            from django_rq import get_queue

            from hub.apps.jobs.tasks import process_job
            from hub.apps.jobs.utils import get_queue_for_job_type

            queue_name = get_queue_for_job_type(job_obj.type)
            queue = get_queue(queue_name)
            timeout = get_job_timeout(job_obj.type)
            queue.enqueue(
                process_job,
                str(job_obj.id),
                job_type=job_obj.type,
                timeout=timeout,
            )
            return True
        except Exception as exc:
            logger.warning(
                "recover_orphaned_reenqueue_failed",
                job_id=str(job_obj.id),
                error=str(exc),
            )
            return False

    # ------------------------------------------------------------------
    # Phase 73.1 — Prefect-executed orphan detection
    # ------------------------------------------------------------------
    def _recover_prefect_orphans(self, dry_run: bool) -> int:
        """
        Detect PENDING SCHEDULED_INGESTION jobs with executed_by_prefect=True
        that are older than 30 minutes — Prefect submission likely failed.

        Checks the Prefect integration service for a matching flow run.
        If no flow run exists, marks the job FAILED with PREFECT_SUBMISSION_ORPHAN.
        """
        import os

        import httpx

        cutoff = timezone.now() - timedelta(minutes=30)
        prefect_url = os.getenv("PREFECT_INTEGRATION_SERVICE_URL", "").rstrip("/")

        candidates = Job.objects.filter(
            status=JobStatus.PENDING,
            type="SCHEDULED_INGESTION",
            details_json__executed_by_prefect=True,
            created_at__lt=cutoff,
        )

        if not candidates.exists():
            return 0

        self.stdout.write(f"Found {candidates.count()} Prefect orphan candidate(s).")

        if dry_run:
            for job_obj in candidates:
                self.stdout.write(
                    f"  [DRY-RUN] Prefect orphan: {job_obj.id}"
                    f"  created={job_obj.created_at.isoformat()}"
                )
            return 0

        recovered = 0
        for job_obj in candidates:
            # Check if Prefect has a flow run for this job
            has_flow_run = False
            if prefect_url:
                try:
                    si_id = (job_obj.details_json or {}).get("scheduled_ingestion_id")
                    if si_id:
                        resp = httpx.get(
                            f"{prefect_url}/deployments/{si_id}/status",
                            timeout=5.0,
                        )
                        has_flow_run = resp.status_code == 200
                except Exception as exc:
                    logger.debug(
                        "prefect_orphan_check_error",
                        job_id=str(job_obj.id),
                        error=str(exc),
                    )

            if has_flow_run:
                logger.warning(
                    "prefect_orphan_has_flow_run",
                    job_id=str(job_obj.id),
                    message="Prefect flow run exists but job still PENDING — leaving for reconciliation",
                )
                continue

            # No flow run — mark as failed
            job_obj.status = JobStatus.FAILED
            job_obj.error_message = "Prefect flow was never submitted for this job"
            result = job_obj.result_json or {}
            result["error_code"] = "PREFECT_SUBMISSION_ORPHAN"
            job_obj.result_json = result
            job_obj.completed_at = timezone.now()
            job_obj.save(
                update_fields=[
                    "status",
                    "error_message",
                    "result_json",
                    "completed_at",
                    "updated_at",
                ]
            )

            logger.info(
                "prefect_orphan_marked_failed",
                job_id=str(job_obj.id),
                error_code="PREFECT_SUBMISSION_ORPHAN",
            )
            recovered += 1

        return recovered
