"""
Virtualization Job Handlers

Handlers for Virtual query execution job.

SAVING CHECKPOINT: This module contains Virtualization job handlers (< 700 lines per project rule).
"""

import structlog

from .models import Job

logger = structlog.get_logger(__name__)


def _execute_virtual_query_job(job_obj: Job) -> dict:
    """
    Execute virtual query execution job.

    Executes a virtual dataset query asynchronously.

    Args:
        job_obj: Job instance

    Returns:
        Result dictionary with execution results

    Raises:
        ValueError: For validation errors
        Exception: For execution errors
    """
    from hub.apps.virtualization.models import QueryExecution, QueryExecutionStatus
    from hub.apps.virtualization.services import VirtualizationService

    execution_id = job_obj.resource_id
    if not execution_id:
        raise ValueError("execution_id is required in resource_id")

    try:
        # Use select_for_update to prevent concurrent execution
        execution = QueryExecution.objects.select_for_update().get(id=execution_id)
    except QueryExecution.DoesNotExist:
        raise ValueError(f"QueryExecution {execution_id} not found")

    # Idempotency check: if execution is already in terminal state, return existing result
    if execution.is_completed():
        logger.warning(
            "virtual_query_execution_already_terminal",
            job_id=str(job_obj.id),
            execution_id=str(execution.id),
            status=execution.status,
            message=f"Execution {execution_id} is already in terminal state: {execution.status} (idempotency check)",
        )
        return {
            "execution_id": str(execution.id),
            "status": execution.status,
            "skipped": True,
            "reason": "Already in terminal state (idempotent retry)",
        }

    # Check if execution was cancelled
    if execution.status == QueryExecutionStatus.CANCELLED:
        logger.info(
            "virtual_query_execution_cancelled",
            job_id=str(job_obj.id),
            execution_id=str(execution.id),
            message=f"Execution {execution_id} was cancelled, skipping job execution",
        )
        return {
            "execution_id": str(execution.id),
            "status": execution.status,
            "skipped": True,
            "reason": "Execution was cancelled",
        }

    # Mark execution as started
    execution.mark_started()
    execution.add_log_entry("INFO", f"Job {job_obj.id} started processing")

    try:
        # Get execution details from job
        details = job_obj.details_json or {}
        str(execution.virtual_dataset_id)
        timeout_seconds = details.get("timeout_seconds", 3600)

        # Initialize service
        service = VirtualizationService(
            tenant_id=str(execution.virtual_dataset.tenant_id),
            user_id=str(job_obj.created_by.id) if job_obj.created_by else None,
        )

        # Execute query synchronously (job worker handles async execution)
        execution.add_log_entry("INFO", "Executing virtual dataset query")

        # Execute the query using the sync method (job worker provides async execution)
        execution = service._execute_query_sync(
            execution, execution.virtual_dataset, execution.parameters or {}, timeout_seconds
        )

        execution.add_log_entry("INFO", "Query execution completed successfully")

        # Sync execution status from job to ensure consistency
        execution.sync_status_from_job()

        return {
            "execution_id": str(execution.id),
            "status": execution.status,
            "row_count": execution.get_metric("rows_processed", 0),
            "duration_ms": execution.get_metric("duration_ms", 0),
        }

    except Exception as e:
        error_msg = str(e)
        execution.mark_failed(error_message=error_msg)

        # Sync execution status from job to ensure consistency
        execution.sync_status_from_job()

        logger.error(
            "virtual_query_execution_error",
            job_id=str(job_obj.id),
            execution_id=str(execution.id),
            error=error_msg,
            exc_info=True,
            message=f"Error during virtual query execution: {error_msg}",
        )
        raise Exception(f"Virtual query execution error: {error_msg}") from e
