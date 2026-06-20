"""
Scheduled Ingestion Job Execution

Handles execution of SCHEDULED_INGESTION job type.
"""

import contextlib
from datetime import datetime
from typing import Any

import structlog
from django.utils import timezone

from hub.apps.jobs.models import Job
from hub.apps.scheduled_ingestion.cost_tracking import CostTrackingManager
from hub.apps.scheduled_ingestion.dead_letter_queue import DeadLetterQueueManager
from hub.apps.scheduled_ingestion.ingestion import ScheduledIngestionProcessor
from hub.apps.scheduled_ingestion.models import (
    ScheduledIngestion,
    ScheduledIngestionRun,
    ScheduledIngestionRunStatus,
    ScheduledIngestionStatus,
)

logger = structlog.get_logger(__name__)


def _execute_scheduled_ingestion_job(job_obj: Job) -> dict[str, Any]:
    """
    Execute SCHEDULED_INGESTION job.

    Args:
        job_obj: Job instance

    Returns:
        Result dictionary with ingestion results

    Raises:
        ValueError: If scheduled_ingestion_id is missing or ingestion not found
        Exception: For other errors
    """
    # Get scheduled_ingestion_id from resource_id or details_json
    scheduled_ingestion_id = job_obj.resource_id
    if not scheduled_ingestion_id:
        scheduled_ingestion_id = job_obj.details_json.get("scheduled_ingestion_id")

    # Convert to string if it's a UUID object
    if scheduled_ingestion_id:
        scheduled_ingestion_id = str(scheduled_ingestion_id)

    if not scheduled_ingestion_id:
        raise ValueError("Scheduled ingestion ID is required")

    # Get scheduled ingestion
    try:
        scheduled_ingestion = ScheduledIngestion.objects.get(id=scheduled_ingestion_id)
    except ScheduledIngestion.DoesNotExist:
        raise ValueError(f"Scheduled ingestion {scheduled_ingestion_id} not found")

    # Get or create run record
    run = None
    if job_obj.details_json and job_obj.details_json.get("scheduled_ingestion_run_id"):
        with contextlib.suppress(ScheduledIngestionRun.DoesNotExist):
            run = ScheduledIngestionRun.objects.get(
                id=job_obj.details_json["scheduled_ingestion_run_id"]
            )

    if not run:
        # Create new run record
        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=scheduled_ingestion,
            job_id=job_obj.id,
            status=ScheduledIngestionRunStatus.RUNNING,
            started_at=timezone.now(),
            prefect_flow_run_id=(
                job_obj.details_json.get("prefect_flow_run_id") if job_obj.details_json else None
            ),
        )
    else:
        # Update existing run
        run.status = ScheduledIngestionRunStatus.RUNNING
        run.started_at = timezone.now()
        run.job_id = job_obj.id
        run.save(update_fields=["status", "started_at", "job_id", "updated_at"])

    try:
        # Initialize processor
        processor = ScheduledIngestionProcessor(scheduled_ingestion)

        # Process ingestion
        result = processor.process()

        # Treat run as failed when processor returns errors or file failures
        has_errors = bool(result.get("errors")) or (result.get("files_failed", 0) or 0) > 0
        if has_errors:
            run.status = ScheduledIngestionRunStatus.FAILED
            run.completed_at = timezone.now()
            run.files_found = result.get("files_found", 0)
            run.files_processed = result.get("files_processed", 0)
            run.files_failed = result.get("files_failed", 0)
            run.datasets_created = result.get("datasets_created", 0)
            run.result_json = result
            errors_list = result.get("errors") or []
            run.error_message = (
                "; ".join(str(e) for e in errors_list)
                if errors_list
                else f"Files failed: {result.get('files_failed', 0)}"
            )
            run.save(
                update_fields=[
                    "status",
                    "completed_at",
                    "files_found",
                    "files_processed",
                    "files_failed",
                    "datasets_created",
                    "result_json",
                    "error_message",
                    "updated_at",
                ]
            )
            scheduled_ingestion.status = ScheduledIngestionStatus.ERROR
            scheduled_ingestion.error_message = run.error_message
            scheduled_ingestion.save(update_fields=["status", "error_message", "updated_at"])
        else:
            # Update run with results
            run.status = ScheduledIngestionRunStatus.COMPLETED
            run.completed_at = timezone.now()
            run.files_found = result.get("files_found", 0)
            run.files_processed = result.get("files_processed", 0)
            run.files_failed = result.get("files_failed", 0)
            run.datasets_created = result.get("datasets_created", 0)
            run.result_json = result
            run.save(
                update_fields=[
                    "status",
                    "completed_at",
                    "files_found",
                    "files_processed",
                    "files_failed",
                    "datasets_created",
                    "result_json",
                    "updated_at",
                ]
            )

        # Persist last_incremental_value from processor as last_processed_timestamp
        last_inc = result.get("last_incremental_value")
        if last_inc is not None:
            try:
                if isinstance(last_inc, str):
                    if last_inc.endswith("Z"):
                        last_inc = last_inc.replace("Z", "+00:00")
                    scheduled_ingestion.last_processed_timestamp = datetime.fromisoformat(last_inc)
                else:
                    scheduled_ingestion.last_processed_timestamp = last_inc
                scheduled_ingestion.save(update_fields=["last_processed_timestamp", "updated_at"])
            except (ValueError, TypeError):
                pass

        # Calculate and store costs
        try:
            CostTrackingManager.calculate_run_costs(str(run.id))
        except Exception as e:
            logger.warning("Failed to calculate ingestion costs", run_id=str(run.id), error=str(e))

        # Sync DLQ items from ingestion state
        try:
            DeadLetterQueueManager.sync_from_ingestion_state(str(scheduled_ingestion.id))
        except Exception as e:
            logger.warning(
                "Failed to sync DLQ items",
                scheduled_ingestion_id=str(scheduled_ingestion.id),
                error=str(e),
            )

        # Update scheduled ingestion status (only if we didn't set ERROR above)
        if not has_errors and scheduled_ingestion.status == ScheduledIngestionStatus.ERROR:
            scheduled_ingestion.status = ScheduledIngestionStatus.ACTIVE
            scheduled_ingestion.error_message = None
            scheduled_ingestion.save(update_fields=["status", "error_message", "updated_at"])

        logger.info(
            "Scheduled ingestion job completed",
            job_id=str(job_obj.id),
            scheduled_ingestion_id=scheduled_ingestion_id,
            run_id=str(run.id),
            files_processed=result.get("files_processed", 0),
            datasets_created=result.get("datasets_created", 0),
        )

        return {
            "status": "completed" if not has_errors else "failed",
            "run_id": str(run.id),
            "files_found": result.get("files_found", 0),
            "files_processed": result.get("files_processed", 0),
            "files_failed": result.get("files_failed", 0),
            "datasets_created": result.get("datasets_created", 0),
            "errors": result.get("errors", []),
        }

    except Exception as e:
        # Update run with failure
        run.status = ScheduledIngestionRunStatus.FAILED
        run.completed_at = timezone.now()
        run.error_message = str(e)
        run.result_json = {"error": str(e), "error_type": type(e).__name__}
        run.save(
            update_fields=["status", "completed_at", "error_message", "result_json", "updated_at"]
        )

        # Update scheduled ingestion status
        scheduled_ingestion.status = ScheduledIngestionStatus.ERROR
        scheduled_ingestion.error_message = str(e)
        scheduled_ingestion.save(update_fields=["status", "error_message", "updated_at"])

        logger.error(
            "Scheduled ingestion job failed",
            job_id=str(job_obj.id),
            scheduled_ingestion_id=scheduled_ingestion_id,
            run_id=str(run.id),
            error=str(e),
            exc_info=True,
        )

        raise
