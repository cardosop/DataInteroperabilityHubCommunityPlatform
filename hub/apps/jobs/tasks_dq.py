"""
DQ Job Handlers

Handlers for Data Quality (DQ) job execution.

SAVING CHECKPOINT: This module contains DQ job handlers (< 700 lines per project rule).
"""

from .models import Job
from .tasks_base import JobExecutionError


def _execute_dq_run_job(job_obj: Job) -> dict:
    """
    Execute DQ_RUN job.

    Args:
        job_obj: Job instance

    Returns:
        Result dictionary with DQ run results

    Raises:
        ValueError: If dq_run_id is missing or DQ run not found
        ConnectionError: If DQ service is unavailable
        Exception: For other errors
    """
    # Get dq_run_id from job details or resource_id.
    # details_json is a JSONField that defaults to None — guard against
    # jobs created without populating it (e.g. test fixtures, fast-fail).
    dq_run_id = None
    if isinstance(job_obj.details_json, dict):
        dq_run_id = job_obj.details_json.get("dq_run_id")
    if not dq_run_id:  # None or empty string
        dq_run_id = job_obj.resource_id

    # Convert to string if it's a UUID object, handle None case
    if dq_run_id is not None:
        dq_run_id = str(dq_run_id)

    if not dq_run_id:
        raise ValueError("DQ run ID is required")

    # Check if DQ run exists before executing
    try:
        from hub.apps.dq.models import DQRun, DQRunStatus

        dq_run = DQRun.objects.get(id=dq_run_id)
    except DQRun.DoesNotExist:
        raise ValueError(f"DQ run {dq_run_id} not found")

    try:
        # Import here to avoid circular imports
        from hub.apps.dq.service_client import DQServiceClient
        from hub.apps.dq.views import execute_dq_run

        # Check if DQ service is available
        dq_client = DQServiceClient()
        is_healthy, _ = dq_client.health_check()
        if not is_healthy:
            raise ConnectionError("DQ service is unavailable")

        # Execute DQ run (this handles its own errors and updates DQRun status)
        execute_dq_run(str(dq_run_id))

        # Get updated DQ run (refresh from DB)
        dq_run.refresh_from_db()

        # Check if DQ run failed
        if dq_run.status == DQRunStatus.FAILED:
            error_msg = (
                dq_run.details_json.get("error", "DQ run failed")
                if dq_run.details_json
                else "DQ run failed"
            )
            raise JobExecutionError(f"DQ run failed: {error_msg}")

        return {
            "status": dq_run.status.lower(),
            "overall_status": dq_run.overall_status,
            "quality_score": dq_run.quality_score,
            "dq_run_id": str(dq_run.id),
            "engine": getattr(dq_run, "engine", None) or "",
        }

    except ConnectionError:
        raise  # Re-raise connection errors
    except ValueError:
        raise  # Re-raise validation errors
    except Exception as e:
        # Wrap other exceptions
        raise JobExecutionError(f"DQ run execution failed: {e!s}") from e
