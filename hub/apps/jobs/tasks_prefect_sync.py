"""
Phase 25.6.2 — RQ task for syncing Prefect flow-run status.

Replaces the background-thread pattern that leaked ORM contexts, swallowed
exceptions, and bypassed request tracing.

Usage (from a view or signal):
    from hub.apps.jobs.tasks_prefect_sync import enqueue_prefect_status_sync

    transaction.on_commit(
        lambda: enqueue_prefect_status_sync(
            flow_run_id="...",
            resource_id="...",
            resource_type="scheduled_ingestion",  # or "scheduled_export"
        )
    )
"""

import os
from datetime import timedelta

import structlog
from django_rq import job

logger = structlog.get_logger(__name__)

# Retry config
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 10


@job("job_low", timeout=120)
def sync_prefect_flow_run_status(
    flow_run_id: str,
    resource_id: str,
    resource_type: str,
    attempt: int = 1,
):
    """
    Call the integration service ``POST /status/sync`` to reconcile
    the Prefect flow-run status with the Django run record.

    Retries up to ``MAX_RETRIES`` times on HTTP 5xx with a 10 s delay.
    After all retries exhausted, marks the run record as FAILED.

    Args:
        flow_run_id: Prefect flow-run UUID string.
        resource_id: Primary key of the ScheduledIngestionRun or
                     ScheduledExportRun record.
        resource_type: ``"scheduled_ingestion"`` or ``"scheduled_export"``.
        attempt: Current attempt number (1-based, used for retries).
    """
    import requests

    base_url = os.getenv("PREFECT_INTEGRATION_SERVICE_URL", "").rstrip("/")
    if not base_url:
        logger.debug(
            "prefect_status_sync_skipped",
            reason="PREFECT_INTEGRATION_SERVICE_URL not configured",
            flow_run_id=flow_run_id,
        )
        return

    url = f"{base_url}/status/sync"
    headers = {"X-Internal-Api-Key": os.getenv("INTERNAL_API_KEY", "")}
    payload = {"flow_run_id": flow_run_id}

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)

        if resp.ok:
            logger.info(
                "prefect_status_sync_ok",
                flow_run_id=flow_run_id,
                resource_type=resource_type,
                resource_id=resource_id,
            )
            return

        # Retryable server error — re-enqueue with delay instead of
        # sleeping in-process (which blocks the RQ worker thread).
        if resp.status_code >= 500 and attempt < MAX_RETRIES:
            logger.warning(
                "prefect_status_sync_retry",
                flow_run_id=flow_run_id,
                status_code=resp.status_code,
                attempt=attempt,
            )
            _schedule_retry(flow_run_id, resource_id, resource_type, attempt + 1)
            return

        # Non-retryable client error (4xx) or retries exhausted
        logger.warning(
            "prefect_status_sync_failed",
            flow_run_id=flow_run_id,
            status_code=resp.status_code,
            response_text=resp.text[:200],
            attempt=attempt,
        )
        _mark_run_failed(resource_id, resource_type, flow_run_id)

    except requests.ConnectionError:
        if attempt < MAX_RETRIES:
            logger.warning(
                "prefect_status_sync_connection_retry",
                flow_run_id=flow_run_id,
                attempt=attempt,
            )
            _schedule_retry(flow_run_id, resource_id, resource_type, attempt + 1)
            return
        logger.error(
            "prefect_status_sync_connection_exhausted",
            flow_run_id=flow_run_id,
            attempt=attempt,
        )
        _mark_run_failed(resource_id, resource_type, flow_run_id)

    except Exception as exc:
        logger.error(
            "prefect_status_sync_error",
            flow_run_id=flow_run_id,
            error=str(exc),
            exc_info=True,
        )
        _mark_run_failed(resource_id, resource_type, flow_run_id)


def _schedule_retry(
    flow_run_id: str,
    resource_id: str,
    resource_type: str,
    next_attempt: int,
):
    """Re-enqueue the sync task with a delay instead of sleeping in-process."""
    from django_rq import get_queue

    queue = get_queue("job_low")
    queue.enqueue_in(
        timedelta(seconds=RETRY_DELAY_SECONDS),
        sync_prefect_flow_run_status,
        flow_run_id=flow_run_id,
        resource_id=resource_id,
        resource_type=resource_type,
        attempt=next_attempt,
    )


def _mark_run_failed(resource_id: str, resource_type: str, flow_run_id: str):
    """Mark the corresponding run record as FAILED after retries exhausted."""
    try:
        if resource_type == "scheduled_ingestion":
            from hub.apps.scheduled_ingestion.models import (
                ScheduledIngestionRun,
                ScheduledIngestionRunStatus,
            )
            ScheduledIngestionRun.objects.filter(id=resource_id).update(
                status=ScheduledIngestionRunStatus.FAILED,
                error_message=f"Prefect status sync failed after {MAX_RETRIES} retries (flow_run_id={flow_run_id})",
            )
        elif resource_type == "scheduled_export":
            from hub.apps.scheduled_export.models import (
                ScheduledExportRun,
                ScheduledExportRunStatus,
            )
            ScheduledExportRun.objects.filter(id=resource_id).update(
                status=ScheduledExportRunStatus.FAILED,
            )
        logger.info(
            "prefect_status_sync_marked_failed",
            resource_id=resource_id,
            resource_type=resource_type,
            flow_run_id=flow_run_id,
        )
    except Exception as exc:
        logger.error(
            "prefect_status_sync_mark_failed_error",
            resource_id=resource_id,
            error=str(exc),
            exc_info=True,
        )


def enqueue_prefect_status_sync(
    flow_run_id: str,
    resource_id: str,
    resource_type: str,
):
    """
    Enqueue the status sync task on the ``job_low`` queue.

    Safe to call from within ``transaction.on_commit()`` — the task is
    only enqueued after the DB transaction commits, ensuring the run
    record exists when the worker picks up the task.
    """
    from django_rq import get_queue

    queue = get_queue("job_low")
    queue.enqueue(
        sync_prefect_flow_run_status,
        flow_run_id=flow_run_id,
        resource_id=resource_id,
        resource_type=resource_type,
        attempt=1,
    )
    logger.debug(
        "prefect_status_sync_enqueued",
        flow_run_id=flow_run_id,
        resource_id=resource_id,
        resource_type=resource_type,
        queue="job_low",
    )


# ---------------------------------------------------------------------------
# Phase 25.7.1 — Periodic reconciliation
# ---------------------------------------------------------------------------

STALE_RUN_THRESHOLD_MINUTES = 5


def reconcile_prefect_run_statuses():
    """
    Find all ScheduledIngestionRun and ScheduledExportRun records that are
    still RUNNING but haven't been updated in the last 5 minutes, and
    reconcile their status with Prefect via the integration service.

    Designed to be called from a Django management command that runs as a
    Kubernetes CronJob every 5 minutes.
    """
    import requests
    from django.utils import timezone as _tz

    base_url = os.getenv("PREFECT_INTEGRATION_SERVICE_URL", "").rstrip("/")
    if not base_url:
        logger.debug(
            "prefect_reconcile_skipped",
            reason="PREFECT_INTEGRATION_SERVICE_URL not configured",
        )
        return 0

    enabled = os.getenv("PREFECT_STATUS_RECONCILIATION_ENABLED", "true")
    if enabled.lower() not in ("true", "1", "yes"):
        logger.debug("prefect_reconcile_skipped", reason="feature disabled")
        return 0

    cutoff = _tz.now() - timedelta(minutes=STALE_RUN_THRESHOLD_MINUTES)
    reconciled = 0

    # --- Ingestion runs ---
    from hub.apps.scheduled_ingestion.models import (
        ScheduledIngestionRun,
        ScheduledIngestionRunStatus,
    )

    stale_ingestion_runs = ScheduledIngestionRun.objects.filter(
        status__in=[
            ScheduledIngestionRunStatus.PENDING,
            ScheduledIngestionRunStatus.RUNNING,
        ],
        updated_at__lt=cutoff,
        prefect_flow_run_id__isnull=False,
    ).exclude(prefect_flow_run_id="")

    for run in stale_ingestion_runs:
        terminal = _check_flow_run_status(
            base_url, run.prefect_flow_run_id, requests
        )
        if terminal:
            if terminal == "COMPLETED":
                run.status = ScheduledIngestionRunStatus.COMPLETED
            elif terminal == "FAILED":
                run.status = ScheduledIngestionRunStatus.FAILED
                run.error_message = (
                    "Reconciled by periodic check: Prefect reported "
                    f"terminal state for flow_run {run.prefect_flow_run_id}"
                )
            else:
                continue
            run.save(update_fields=["status", "error_message", "updated_at"])
            reconciled += 1
            logger.info(
                "prefect_reconcile_updated",
                resource_type="scheduled_ingestion",
                run_id=str(run.id),
                flow_run_id=run.prefect_flow_run_id,
                new_status=run.status,
            )

    # --- Export runs ---
    from hub.apps.scheduled_export.models import (
        ScheduledExportRun,
        ScheduledExportRunStatus,
    )

    stale_export_runs = ScheduledExportRun.objects.filter(
        status=ScheduledExportRunStatus.RUNNING,
        updated_at__lt=cutoff,
        prefect_flow_run_id__isnull=False,
    ).exclude(prefect_flow_run_id="")

    for run in stale_export_runs:
        new_status = _check_flow_run_status(
            base_url, run.prefect_flow_run_id, requests
        )
        if new_status:
            # Map to export status enum
            if new_status == "COMPLETED":
                run.status = ScheduledExportRunStatus.COMPLETED
            elif new_status == "FAILED":
                run.status = ScheduledExportRunStatus.FAILED
            else:
                continue
            run.save(update_fields=["status", "updated_at"])
            reconciled += 1
            logger.info(
                "prefect_reconcile_updated",
                resource_type="scheduled_export",
                run_id=str(run.id),
                flow_run_id=run.prefect_flow_run_id,
                new_status=run.status,
            )

    logger.info("prefect_reconcile_complete", reconciled=reconciled)
    return reconciled


def _check_flow_run_status(base_url: str, flow_run_id: str, requests_mod):
    """
    Ask the integration service for the current status of a Prefect flow run.

    Returns a terminal status string ("COMPLETED" or "FAILED") if the flow
    run is finished, or None if it's still running / unknown.
    """
    try:
        headers = {"X-Internal-Api-Key": os.getenv("INTERNAL_API_KEY", "")}
        resp = requests_mod.post(
            f"{base_url}/status/sync",
            json={"flow_run_id": flow_run_id},
            headers=headers,
            timeout=10,
        )
        if not resp.ok:
            return None
        data = resp.json()
        if not isinstance(data, dict):
            return None
        prefect_state = (data.get("state") or "").upper()
        if prefect_state in ("COMPLETED",):
            return "COMPLETED"
        if prefect_state in ("FAILED", "CRASHED", "CANCELLED", "CANCELLING"):
            return "FAILED"
        return None
    except Exception as exc:
        logger.debug(
            "prefect_reconcile_check_error",
            flow_run_id=flow_run_id,
            error=str(exc),
        )
        return None
