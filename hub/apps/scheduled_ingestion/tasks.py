"""
Phase 6.2 dlt dispatch spine — async execution task (b7 #18 fix).

The trigger view for dlt-flagged tenants used to execute the FULL dlt
pipeline synchronously inside the HTTP request
(``IngestionService.execute_ingestion_run`` in the view). A pipeline
that takes longer than the client's response budget (or stalls on a
destination connect/retry loop) left the trigger hanging indefinitely —
the E2E's 90s ``waitForResponse`` exhausted its 3 attempts and burned
the whole 300s test budget on an API request that never answered.

The trigger contract is now: create the PENDING run, enqueue THIS task
on commit, return ``run_id`` immediately. The worker executes the
pipeline and finalizes the run with the same terminal-state contract as
the old synchronous path (COMPLETED when nothing failed, FAILED
otherwise, plus the worker_run_lifecycle completion side effects).
"""

from __future__ import annotations

import structlog
from django_rq import job

logger = structlog.get_logger(__name__)


@job("default", timeout="1h")
def execute_scheduled_ingestion_run(run_id: str, tenant_id: str) -> None:
    """Execute the dlt pipeline for a PENDING run and finalize it.

    Mirrors ``IngestionService.execute_ingestion_run``'s terminal-state
    contract. Fail-soft on the pipeline exception: the run is marked
    FAILED with the error message rather than re-raising into the RQ
    retry machinery (the run row is the durable outcome).

    ``tenant_id`` is passed at enqueue time (not derived from the run)
    because the run row itself is tenant-RLS-scoped — the worker cannot
    read it before entering ``tenant_context``.
    """

    def _execute() -> None:
        from django.utils import timezone

        from hub.apps.scheduled_ingestion.models import (
            ScheduledIngestionRun,
            ScheduledIngestionRunStatus,
        )
        from hub.apps.scheduled_ingestion.worker_run_lifecycle import (
            apply_run_completion_side_effects,
        )

        run = ScheduledIngestionRun.objects.get(id=run_id)

        # W3.1 (R2-P1) — the worker lifecycle is explicit and guarded:
        # a run already cancelled when the task picks it up is skipped
        # outright, and PENDING→RUNNING happens BEFORE the entrypoint
        # executes.
        if run.status == ScheduledIngestionRunStatus.CANCELLED:
            logger.info("dlt_ingestion_run_cancelled_skipped", run_id=run_id)
            return
        if run.status == ScheduledIngestionRunStatus.PENDING:
            run.status = ScheduledIngestionRunStatus.RUNNING
            # W3.5 (R2-P4) — the worker claims the run with a heartbeat
            # (the liveness lease): the stuck-run detector only recovers
            # runs whose lease expired.
            run.heartbeat_at = timezone.now()
            run.save(update_fields=["status", "heartbeat_at", "updated_at"])

        try:
            from hub.data_movement.ingestion_execution import execute_dlt_ingestion

            result = execute_dlt_ingestion(str(run.scheduled_ingestion_id))
        except Exception as e:
            logger.error(
                "dlt_ingestion_run_failed",
                run_id=run_id,
                error=str(e),
                exc_info=True,
            )
            result = {"error_message": str(e), "files_failed": 1}

        # W3.1 (R2-P1) — the worker honors CANCELLED: a run cancelled
        # while the pipeline ran keeps its terminal state; the dlt
        # outcome is recorded without overwriting it.
        run.refresh_from_db()
        if run.status == ScheduledIngestionRunStatus.CANCELLED:
            run.result_json = {**(run.result_json or {}), "dlt_outcome": result}
            run.save(update_fields=["result_json", "updated_at"])
            logger.info("dlt_ingestion_run_cancelled_outcome_recorded", run_id=run_id)
            return

        failed = bool(result.get("files_failed")) or bool(result.get("error_message"))
        new_status = (
            ScheduledIngestionRunStatus.FAILED if failed else ScheduledIngestionRunStatus.COMPLETED
        )
        run.status = new_status
        run.files_found = result.get("files_found") or 0
        run.files_processed = result.get("files_processed") or 0
        run.files_failed = result.get("files_failed") or 0
        # The outcome carries datasets_created (one per ingested file) —
        # the run row must record it too, or the UI/API reports 0 while
        # the pipeline really ingested files (JOURNEY-INGESTION-001
        # real-work assertion, 2026-10-03).
        run.datasets_created = result.get("datasets_created") or 0
        # The classified failure must land on the run row's canonical
        # error_message, not only inside result_json.dlt_outcome:
        # worker_run_lifecycle.apply_run_completion_side_effects reads
        # run.error_message to propagate the reason to the parent
        # ScheduledIngestion (falling back to a generic "Run failed"),
        # and the dashboard/DLQ surfaces only the canonical field
        # (2026-10-03: a fail-closed trigger left error_message null
        # while the classified refusal sat in result_json).
        run.error_message = result.get("error_message")
        run.completed_at = timezone.now()
        run.result_json = {**(run.result_json or {}), "dlt_outcome": result}
        run.save(
            update_fields=[
                "status",
                "files_found",
                "files_processed",
                "files_failed",
                "datasets_created",
                "error_message",
                "completed_at",
                "result_json",
                "updated_at",
            ]
        )

        try:
            apply_run_completion_side_effects(run, new_status)
        except Exception as e:
            logger.error(
                "dlt_ingestion_side_effects_failed",
                run_id=run_id,
                error=str(e),
                exc_info=True,
            )

    # Tenant Isolation contract: worker code touching tenant-scoped
    # models MUST run inside tenant_context (RLS resolves via
    # current_setting('app.current_tenant_id')).
    from hub.apps.tenants.request_tenant import tenant_context

    with tenant_context(tenant_id):
        _execute()
