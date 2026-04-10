"""
Compliance async polling task (19.10.5).

Polls the compliance microservice for the result of an async scan job
and persists the result (or failure) onto the ComplianceRun record.
Re-enqueues itself until the remote job reaches a terminal state or the
30-minute absolute timeout is exceeded.
"""
import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)

# How long to wait between poll attempts
_POLL_RETRY_SECONDS = 10

# Statuses that indicate the run has already been resolved
_TERMINAL_STATUSES = frozenset(("SUCCEEDED", "FAILED"))


def poll_compliance_job(run_id) -> None:
    """
    RQ task: poll the compliance service for the result of an async job.

    Lifecycle:
      - Already terminal (SUCCEEDED/FAILED) → exit immediately
      - COMPLETED → call ComplianceService._persist_result
      - FAILED    → set ComplianceRun.status = FAILED
      - RUNNING / QUEUED (or unknown) → re-enqueue after
        _POLL_RETRY_SECONDS seconds
      - Elapsed > _MAX_POLL_MINUTES → mark FAILED (stuck-job guard)

    Args:
        run_id: ComplianceRun primary key (UUID)
    """
    from hub.apps.compliance.models import (
        ComplianceRun,
        ComplianceRunStatus,
    )
    from hub.apps.compliance.service_client import ComplianceServiceClient
    from hub.apps.compliance.services import ComplianceService

    # --- Load run with related objects to avoid N+1 in Model.clean() ----
    try:
        run = ComplianceRun.objects.select_related(
            "job", "asset", "dataset", "file"
        ).get(id=run_id)
    except ComplianceRun.DoesNotExist:
        logger.error(
            "poll_compliance_job: run not found",
            extra={"run_id": str(run_id)},
        )
        return

    # --- Guard: already in terminal state --------------------------------
    if run.status in _TERMINAL_STATUSES:
        logger.info(
            "poll_compliance_job: run already terminal, skipping",
            extra={"run_id": str(run_id), "status": run.status},
        )
        return

    # --- Extract job_id from metadata_json --------------------------------
    metadata = run.metadata_json or {}
    job_id = metadata.get("job_id")
    if not job_id:
        logger.error(
            "poll_compliance_job: no job_id in metadata_json",
            extra={"run_id": str(run_id)},
        )
        run.status = ComplianceRunStatus.FAILED
        run.save(update_fields=["status", "updated_at"])
        return

    # --- Polling deadline (Phase 69 — fail-closed on timeout) -------------
    from django.conf import settings as _s

    max_seconds = getattr(_s, "COMPLIANCE_POLL_MAX_SECONDS", 300)
    reference_time = run.started_at or run.created_at
    elapsed = (timezone.now() - reference_time).total_seconds()
    if elapsed > max_seconds:
        logger.warning(
            "poll_compliance_job: timeout exceeded, marking FAILED (fail-closed)",
            extra={
                "run_id": str(run_id),
                "elapsed_seconds": round(elapsed, 1),
                "max_seconds": max_seconds,
            },
        )
        run.status = ComplianceRunStatus.FAILED
        # Fail-closed: unknown risk, deny storage
        run.risk_level = "UNKNOWN"
        run.allowed_to_store = False
        run.completed_at = timezone.now()
        # Record error context in metadata (model has no error_message field)
        metadata = run.metadata_json or {}
        metadata["error_code"] = "POLL_TIMEOUT"
        metadata["error_message"] = f"Compliance service polling timed out after {int(elapsed)}s"
        run.metadata_json = metadata
        # Phase 78: Prometheus counter for poll timeouts
        try:
            from hub.apps.observability.otel_metrics import poll_timeout_total
            poll_timeout_total.labels(service="compliance").inc()
        except Exception:
            pass
        update_fields = [
            "status", "risk_level", "allowed_to_store",
            "completed_at", "metadata_json", "updated_at",
        ]
        run.save(update_fields=update_fields)
        return

    # --- Poll remote job --------------------------------------------------
    client = ComplianceServiceClient()
    try:
        result = client.get_scan_result(job_id)
    except Exception as exc:
        logger.warning(
            "poll_compliance_job: client error, will retry",
            extra={"run_id": str(run_id), "error": str(exc)},
        )
        _reenqueue(run_id)
        return

    remote_status = (result.get("status") or "").upper()

    if remote_status == "COMPLETED":
        # Unwrap nested result payload when the service wraps it
        result_payload = result.get("result", result)
        ComplianceService._persist_result(run, result_payload)
        logger.info(
            "poll_compliance_job: completed and persisted",
            extra={"run_id": str(run_id), "job_id": job_id},
        )

    elif remote_status == "FAILED":
        error_detail = (
            result.get("error")
            or result.get("detail")
            or "compliance microservice reported FAILED with no error/detail field"
        )
        logger.warning(
            "poll_compliance_job: remote job failed",
            extra={
                "run_id": str(run_id),
                "job_id": job_id,
                "error": error_detail,
            },
        )
        run.status = ComplianceRunStatus.FAILED
        # Phase 213.G.1 — persist error_detail so it is reachable to API
        # consumers (previously only logged, then thrown away).
        existing_mapping = dict(run.regulation_mapping_json or {})
        existing_mapping["error"] = error_detail
        existing_mapping["error_type"] = "REMOTE_FAILURE"
        run.regulation_mapping_json = existing_mapping
        run.save(
            update_fields=[
                "status",
                "regulation_mapping_json",
                "updated_at",
            ]
        )

    else:
        # RUNNING, QUEUED, or any unrecognised status → poll again
        logger.debug(
            "poll_compliance_job: still in progress, re-enqueuing",
            extra={
                "run_id": str(run_id),
                "remote_status": remote_status,
            },
        )
        _reenqueue(run_id)


def _reenqueue(run_id) -> None:
    """Re-enqueue poll_compliance_job with a fixed delay."""
    from django_rq import get_queue

    queue = get_queue("job_default")
    queue.enqueue_in(
        timedelta(seconds=_POLL_RETRY_SECONDS),
        poll_compliance_job,
        run_id,
    )
