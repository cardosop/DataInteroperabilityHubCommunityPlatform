"""
285.10.3.5.1 — Stuck Run Detector for DQ and Compliance runs.

Finds DQRun / ComplianceRun instances stuck in RUNNING (and ComplianceRun
QUEUED) for >2x their configured timeout, marks them FAILED with
``error_code: STUCK_RUN_DETECTED``, transitions the associated Job,
writes to the DLQ, emits audit events, and publishes Prometheus metrics.

Designed to run periodically via Kubernetes CronJob (every 15 minutes).
"""

from datetime import timedelta

import structlog
from django.core.management.base import BaseCommand
from django.db import transaction as db_transaction
from django.utils import timezone

from hub.apps.audit.utils import create_audit_event
from hub.apps.jobs.models import FailedJobDLQ, JobStatus
from hub.apps.jobs.utils import JOB_TIMEOUTS, get_queue_for_job_type
from hub.apps.tenants.models import Tenant
from hub.apps.tenants.request_tenant import tenant_context

logger = structlog.get_logger(__name__)

# 285.10.3.5.1 — constants
ERROR_CODE_STUCK_RUN_DETECTED = "STUCK_RUN_DETECTED"
STUCK_ACTION_LABEL = "STUCK_RUN_DETECTED"

# Default query timeout for warehouse-native runs (seconds).
DEFAULT_WAREHOUSE_QUERY_TIMEOUT = 300

# Fallback timeout when no job timeout or warehouse config is available.
DEFAULT_FALLBACK_TIMEOUT = 1800

# Cap on error_message stored on failed runs (chars).
MAX_ERROR_MESSAGE_LENGTH = 2000


class Command(BaseCommand):
    help = (
        "285.10.3.5.1 — Detect DQ/Compliance runs stuck in RUNNING "
        "for >2x their timeout, mark them FAILED."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="List stuck runs without modifying them.",
        )
        parser.add_argument(
            "--tenant-id",
            default=None,
            help="Restrict execution to a single tenant UUID.",
        )
        parser.add_argument(
            "--threshold-multiplier",
            type=float,
            default=2.0,
            help="Multiplier applied to the per-run timeout (default: 2.0 for 2x timeout).",
        )
        parser.add_argument(
            "--direction",
            choices=["dq", "compliance", "both"],
            default="both",
            help="Which run types to check (default: both).",
        )
        parser.add_argument(
            "--stale-queued-minutes",
            type=int,
            default=60,
            help="ComplianceRuns stuck in QUEUED longer than this are detected (default: 60 min).",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        target_tenant_id = options.get("tenant_id")
        multiplier: float = options["threshold_multiplier"]
        direction: str = options["direction"]
        stale_queued_minutes: int = options["stale_queued_minutes"]

        if target_tenant_id:
            tenant_ids = [str(target_tenant_id)]
        else:
            tenant_ids = [
                str(tid) for tid in Tenant.objects.order_by("id").values_list("id", flat=True)
            ]

        total_dq = 0
        total_compliance = 0
        total_queued = 0

        for tenant_id in tenant_ids:
            with tenant_context(tenant_id):
                if direction in ("dq", "both"):
                    total_dq += self._detect_stuck_dq_runs(
                        tenant_id,
                        multiplier,
                        dry_run,
                    )
                if direction in ("compliance", "both"):
                    total_compliance += self._detect_stuck_compliance_runs(
                        tenant_id,
                        multiplier,
                        dry_run,
                    )
                    total_queued += self._detect_stale_queued_compliance_runs(
                        tenant_id,
                        stale_queued_minutes,
                        dry_run,
                    )

        # Emit aggregate metrics after all tenants processed.
        self._emit_metrics(total_dq, total_compliance, total_queued)

        total_all = total_dq + total_compliance + total_queued
        if total_all == 0:
            self.stdout.write(self.style.SUCCESS("No stuck DQ/Compliance runs found"))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Recovered {total_dq} stuck DQ run(s) + "
                    f"{total_compliance} stuck Compliance run(s) + "
                    f"{total_queued} stale QUEUED Compliance run(s)."
                )
            )

    # ── DQ Runs ─────────────────────────────────────────────────────────

    def _detect_stuck_dq_runs(self, tenant_id: str, multiplier: float, dry_run: bool) -> int:
        from hub.apps.dq.models import DQRun, DQRunStatus

        now = timezone.now()
        stuck: list[DQRun] = []

        # We load all RUNNING DQ runs for this tenant and compute the
        # per-run threshold in Python because the threshold is derived
        # from a JSON field (warehouse_config).
        runs = DQRun.objects.filter(
            tenant_id=tenant_id,
            status=DQRunStatus.RUNNING,
            started_at__isnull=False,
        ).select_related("job", "job__tenant")

        for run in runs:
            timeout = self._get_run_timeout(run)
            threshold = now - timedelta(seconds=int(timeout * multiplier))
            if run.started_at < threshold:
                stuck.append(run)

        if not stuck:
            return 0

        self.stdout.write(
            f"[DQ] Found {len(stuck)} stuck RUNNING DQ run(s) "
            f"(tenant={tenant_id}, multiplier={multiplier})."
        )

        if dry_run:
            for run in stuck:
                timeout = self._get_run_timeout(run)
                self.stdout.write(
                    f"  [DRY-RUN] {run.id}  profile={run.profile_key}"
                    f"  started={run.started_at.isoformat()}"
                    f"  timeout={timeout}s"
                )
            return 0

        recovered = 0
        for run in stuck:
            try:
                self._fail_stuck_dq_run(run, now)
                recovered += 1
            except Exception as exc:
                logger.error(
                    "stuck_dq_run_recovery_failed",
                    dq_run_id=str(run.id),
                    error=str(exc),
                    exc_info=True,
                )

        logger.info(
            "stuck_dq_runs_recovered",
            recovered=recovered,
            tenant_id=tenant_id,
        )
        return recovered

    def _fail_stuck_dq_run(self, run, now):
        from hub.apps.dq.models import DQRunStatus

        timeout = self._get_run_timeout(run)
        stuck_duration = int((now - run.started_at).total_seconds())
        error_msg = (
            f"DQ run stuck in RUNNING for {stuck_duration}s "
            f"(timeout={timeout}s, >2x threshold). "
            f"Recovered by detect_stuck_dq_compliance_runs."
        )

        with db_transaction.atomic():
            run.status = DQRunStatus.FAILED
            run.completed_at = now

            # Persist error info in details_json (error_code/error_message
            # fields were removed in migration 0105).
            details = run.details_json or {}
            details["stuck_detected_at"] = now.isoformat()
            details["stuck_duration_seconds"] = stuck_duration
            details["timeout_seconds"] = timeout
            details["error_code"] = ERROR_CODE_STUCK_RUN_DETECTED
            details["error_message"] = error_msg[:MAX_ERROR_MESSAGE_LENGTH]
            run.details_json = details

            run.save(
                update_fields=[
                    "status",
                    "completed_at",
                    "details_json",
                    "updated_at",
                ]
            )

            # Also fail the associated Job if still RUNNING.
            job = run.job
            if job and job.status == JobStatus.RUNNING:
                job.status = JobStatus.FAILED
                job.completed_at = now
                job.error_message = error_msg[:2000]
                job.result_json = {
                    "error": error_msg[:2000],
                    "error_code": ERROR_CODE_STUCK_RUN_DETECTED,
                    "stuck_duration_seconds": stuck_duration,
                }
                job.save(
                    update_fields=[
                        "status",
                        "completed_at",
                        "error_message",
                        "result_json",
                        "updated_at",
                    ]
                )

                # Write to DLQ.
                try:
                    FailedJobDLQ.objects.create(
                        job_id=job.id,
                        queue=get_queue_for_job_type(job.type),
                        func_name="hub.apps.jobs.tasks_base.process_job",
                        args_json={
                            "job_id": str(job.id),
                            "job_type": job.type,
                        },
                        error_message=error_msg[:2000],
                        tenant=job.tenant,
                    )
                except Exception as dlq_err:
                    logger.error(
                        "stuck_dq_dlq_write_failed",
                        job_id=str(job.id),
                        error=str(dlq_err),
                    )

        logger.warning(
            "stuck_dq_run_detected",
            dq_run_id=str(run.id),
            profile=run.profile_key,
            started_at=run.started_at.isoformat(),
            stuck_duration=stuck_duration,
            timeout=timeout,
        )

        # Audit event (outside atomic block — audit DB outage must not
        # roll back the status transition).
        try:
            create_audit_event(
                resource_type="DQ_RUN",
                action="DQ_RUN_STUCK_DETECTED",
                actor_user=None,
                tenant=run.tenant,
                resource_id=str(run.id),
                details={
                    "error_code": ERROR_CODE_STUCK_RUN_DETECTED,
                    "started_at": run.started_at.isoformat(),
                    "stuck_duration_seconds": stuck_duration,
                    "timeout_seconds": timeout,
                },
            )
        except Exception as exc:
            logger.error(
                "stuck_dq_run_audit_failed",
                dq_run_id=str(run.id),
                error=str(exc),
            )

    # ── Compliance Runs ──────────────────────────────────────────────────

    def _detect_stuck_compliance_runs(
        self, tenant_id: str, multiplier: float, dry_run: bool
    ) -> int:
        from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus

        now = timezone.now()
        stuck: list[ComplianceRun] = []

        runs = ComplianceRun.objects.filter(
            tenant_id=tenant_id,
            status=ComplianceRunStatus.RUNNING,
            started_at__isnull=False,
        ).select_related("job", "job__tenant")

        for run in runs:
            timeout = self._get_run_timeout(run)
            threshold = now - timedelta(seconds=int(timeout * multiplier))
            if run.started_at < threshold:
                stuck.append(run)

        if not stuck:
            return 0

        self.stdout.write(
            f"[Compliance] Found {len(stuck)} stuck RUNNING Compliance run(s) "
            f"(tenant={tenant_id}, multiplier={multiplier})."
        )

        if dry_run:
            for run in stuck:
                timeout = self._get_run_timeout(run)
                self.stdout.write(
                    f"  [DRY-RUN] {run.id}"
                    f"  started={run.started_at.isoformat()}"
                    f"  timeout={timeout}s"
                )
            return 0

        recovered = 0
        for run in stuck:
            try:
                self._fail_stuck_compliance_run(run, now)
                recovered += 1
            except Exception as exc:
                logger.error(
                    "stuck_compliance_run_recovery_failed",
                    run_id=str(run.id),
                    error=str(exc),
                    exc_info=True,
                )

        logger.info(
            "stuck_compliance_runs_recovered",
            recovered=recovered,
            tenant_id=tenant_id,
        )
        return recovered

    def _fail_stuck_compliance_run(self, run, now):
        from hub.apps.compliance.models import ComplianceRunStatus

        timeout = self._get_run_timeout(run)
        stuck_duration = int((now - run.started_at).total_seconds())
        error_msg = (
            f"Compliance run stuck in RUNNING for {stuck_duration}s "
            f"(timeout={timeout}s, >2x threshold). "
            f"Recovered by detect_stuck_dq_compliance_runs."
        )

        with db_transaction.atomic():
            run.status = ComplianceRunStatus.FAILED
            run.completed_at = now

            metadata = run.metadata_json or {}
            metadata["stuck_detected_at"] = now.isoformat()
            metadata["stuck_duration_seconds"] = stuck_duration
            metadata["timeout_seconds"] = timeout
            metadata["error_code"] = ERROR_CODE_STUCK_RUN_DETECTED
            metadata["error_message"] = error_msg[:MAX_ERROR_MESSAGE_LENGTH]
            run.metadata_json = metadata

            run.save(
                update_fields=[
                    "status",
                    "completed_at",
                    "metadata_json",
                    "updated_at",
                ]
            )

            job = run.job
            if job and job.status == JobStatus.RUNNING:
                job.status = JobStatus.FAILED
                job.completed_at = now
                job.error_message = error_msg[:2000]
                job.result_json = {
                    "error": error_msg[:2000],
                    "error_code": ERROR_CODE_STUCK_RUN_DETECTED,
                    "stuck_duration_seconds": stuck_duration,
                }
                job.save(
                    update_fields=[
                        "status",
                        "completed_at",
                        "error_message",
                        "result_json",
                        "updated_at",
                    ]
                )

                try:
                    FailedJobDLQ.objects.create(
                        job_id=job.id,
                        queue=get_queue_for_job_type(job.type),
                        func_name="hub.apps.jobs.tasks_base.process_job",
                        args_json={
                            "job_id": str(job.id),
                            "job_type": job.type,
                        },
                        error_message=error_msg[:2000],
                        tenant=job.tenant,
                    )
                except Exception as dlq_err:
                    logger.error(
                        "stuck_compliance_dlq_write_failed",
                        job_id=str(job.id),
                        error=str(dlq_err),
                    )

        logger.warning(
            "stuck_compliance_run_detected",
            run_id=str(run.id),
            started_at=run.started_at.isoformat(),
            stuck_duration=stuck_duration,
            timeout=timeout,
        )

        try:
            create_audit_event(
                resource_type="COMPLIANCE_RUN",
                action="COMPLIANCE_RUN_STUCK_DETECTED",
                actor_user=None,
                tenant=run.tenant,
                resource_id=str(run.id),
                details={
                    "error_code": ERROR_CODE_STUCK_RUN_DETECTED,
                    "started_at": run.started_at.isoformat(),
                    "stuck_duration_seconds": stuck_duration,
                    "timeout_seconds": timeout,
                },
            )
        except Exception as exc:
            logger.error(
                "stuck_compliance_run_audit_failed",
                run_id=str(run.id),
                error=str(exc),
            )

    # ── Stale QUEUED Compliance Runs ────────────────────────────────────
    #
    # ComplianceRun has a QUEUED status (async job accepted by compliance
    # service).  If a run stays QUEUED and never transitions to RUNNING
    # (compliance-service crash, queue loss, etc.), the stuck-run detector
    # picks it up on the next cycle.

    def _detect_stale_queued_compliance_runs(
        self,
        tenant_id: str,
        stale_minutes: int,
        dry_run: bool,
    ) -> int:
        from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus

        now = timezone.now()
        cutoff = now - timedelta(minutes=stale_minutes)

        runs = ComplianceRun.objects.filter(
            tenant_id=tenant_id,
            status=ComplianceRunStatus.QUEUED,
            created_at__lt=cutoff,
        ).select_related("job", "job__tenant")

        count = runs.count()
        if count == 0:
            return 0

        self.stdout.write(
            f"[Compliance-QUEUED] Found {count} stale QUEUED Compliance run(s) "
            f"(tenant={tenant_id}, >{stale_minutes} min)."
        )

        if dry_run:
            for run in runs:
                self.stdout.write(
                    f"  [DRY-RUN] QUEUED {run.id}  created={run.created_at.isoformat()}"
                )
            return 0

        recovered = 0
        for run in runs:
            try:
                self._fail_stale_queued_compliance_run(run, now, stale_minutes)
                recovered += 1
            except Exception as exc:
                logger.error(
                    "stale_queued_compliance_run_recovery_failed",
                    run_id=str(run.id),
                    error=str(exc),
                    exc_info=True,
                )

        logger.info(
            "stale_queued_compliance_runs_recovered",
            recovered=recovered,
            tenant_id=tenant_id,
        )
        return recovered

    def _fail_stale_queued_compliance_run(self, run, now, stale_minutes):
        from hub.apps.compliance.models import ComplianceRunStatus

        stuck_duration_seconds = int((now - run.created_at).total_seconds())
        error_msg = (
            f"Compliance run stuck in QUEUED for {stuck_duration_seconds}s "
            f"(>{stale_minutes} min threshold). "
            f"Recovered by detect_stuck_dq_compliance_runs."
        )[:MAX_ERROR_MESSAGE_LENGTH]

        with db_transaction.atomic():
            run.status = ComplianceRunStatus.FAILED
            run.completed_at = now

            metadata = run.metadata_json or {}
            metadata["stuck_detected_at"] = now.isoformat()
            metadata["stuck_duration_seconds"] = stuck_duration_seconds
            metadata["stale_queued_minutes"] = stale_minutes
            metadata["error_code"] = ERROR_CODE_STUCK_RUN_DETECTED
            metadata["error_message"] = error_msg
            run.metadata_json = metadata

            run.save(
                update_fields=[
                    "status",
                    "completed_at",
                    "metadata_json",
                    "updated_at",
                ]
            )

            job = run.job
            if job and job.status == JobStatus.RUNNING:
                job.status = JobStatus.FAILED
                job.completed_at = now
                job.error_message = error_msg[:2000]
                job.result_json = {
                    "error": error_msg[:2000],
                    "error_code": ERROR_CODE_STUCK_RUN_DETECTED,
                    "stuck_duration_seconds": stuck_duration_seconds,
                    "stale_queued_minutes": stale_minutes,
                }
                job.save(
                    update_fields=[
                        "status",
                        "completed_at",
                        "error_message",
                        "result_json",
                        "updated_at",
                    ]
                )

                try:
                    FailedJobDLQ.objects.create(
                        job_id=job.id,
                        queue=get_queue_for_job_type(job.type),
                        func_name="hub.apps.jobs.tasks_base.process_job",
                        args_json={
                            "job_id": str(job.id),
                            "job_type": job.type,
                        },
                        error_message=error_msg[:2000],
                        tenant=job.tenant,
                    )
                except Exception as dlq_err:
                    logger.error(
                        "stale_queued_dlq_write_failed",
                        job_id=str(job.id),
                        error=str(dlq_err),
                    )

        logger.warning(
            "stale_queued_compliance_run_detected",
            run_id=str(run.id),
            created_at=run.created_at.isoformat(),
            stuck_duration=stuck_duration_seconds,
            stale_minutes=stale_minutes,
        )

        try:
            create_audit_event(
                resource_type="COMPLIANCE_RUN",
                action="COMPLIANCE_RUN_STUCK_DETECTED",
                actor_user=None,
                tenant=run.tenant,
                resource_id=str(run.id),
                details={
                    "error_code": ERROR_CODE_STUCK_RUN_DETECTED,
                    "sub_type": "STALE_QUEUED",
                    "created_at": run.created_at.isoformat(),
                    "stuck_duration_seconds": stuck_duration_seconds,
                    "stale_queued_minutes": stale_minutes,
                },
            )
        except Exception as exc:
            logger.error(
                "stale_queued_audit_failed",
                run_id=str(run.id),
                error=str(exc),
            )

    # ── Metrics ─────────────────────────────────────────────────────────

    @staticmethod
    def _emit_metrics(total_dq: int, total_compliance: int, total_queued: int) -> None:
        total = total_dq + total_compliance + total_queued
        if total == 0:
            return
        try:
            from hub.apps.observability.otel_metrics import (
                stuck_runs_detected_total,
            )

            if total_dq:
                stuck_runs_detected_total.labels(
                    run_type="dq",
                    error_code=ERROR_CODE_STUCK_RUN_DETECTED,
                ).inc(total_dq)
            if total_compliance:
                stuck_runs_detected_total.labels(
                    run_type="compliance",
                    error_code=ERROR_CODE_STUCK_RUN_DETECTED,
                ).inc(total_compliance)
            if total_queued:
                stuck_runs_detected_total.labels(
                    run_type="compliance_queued",
                    error_code=ERROR_CODE_STUCK_RUN_DETECTED,
                ).inc(total_queued)
        except Exception:
            pass  # Metrics may not be available

    # ── Timeout helpers ─────────────────────────────────────────────────

    @staticmethod
    def _get_run_timeout(run) -> int:
        """Determine the timeout (in seconds) for a DQRun or ComplianceRun.

        Priority:
        1. ``warehouse_config.query_timeout_seconds`` (warehouse-native runs)
        2. Associated ``Job.timeout_seconds``
        3. ``JOB_TIMEOUTS`` default for the job type
        4. ``DEFAULT_FALLBACK_TIMEOUT`` (1800 s)
        """
        # Warehouse config on the run itself.
        wh_config = getattr(run, "warehouse_config", None) or {}
        if isinstance(wh_config, dict):
            wh_timeout = wh_config.get("query_timeout_seconds")
            if wh_timeout is not None:
                return int(wh_timeout)

        # Associated Job-level timeout.
        job = getattr(run, "job", None)
        if job is not None and getattr(job, "timeout_seconds", None) is not None:
            return int(job.timeout_seconds)

        # Job-type default from JOB_TIMEOUTS.
        if job is not None:
            jt = getattr(job, "type", None)
            if jt and jt in JOB_TIMEOUTS:
                return JOB_TIMEOUTS[jt]

        return DEFAULT_FALLBACK_TIMEOUT
