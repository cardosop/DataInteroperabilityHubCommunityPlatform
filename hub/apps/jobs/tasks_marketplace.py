"""
Marketplace Job Handlers

Handlers for Marketplace sync job execution.

SAVING CHECKPOINT: This module contains Marketplace job handlers (< 700 lines per project rule).
"""

from .models import Job


def _execute_marketplace_sync_job(job_obj: Job) -> dict:
    """
    Execute MARKETPLACE_SYNC job.

    Processes a marketplace synchronization job by calling the execute_marketplace_sync task.

    Args:
        job_obj: Job instance

    Returns:
        Result dictionary with sync job execution results

    Raises:
        ValueError: If sync_job_id is missing or sync job not found
        ConnectionError: If connector cannot connect to marketplace
        Exception: For other errors
    """
    # Get sync_job_id from job details or resource_id
    sync_job_id = job_obj.details_json.get("sync_job_id")
    if not sync_job_id:
        sync_job_id = job_obj.resource_id

    # Convert to string if it's a UUID object
    if sync_job_id is not None:
        sync_job_id = str(sync_job_id)

    if not sync_job_id:
        raise ValueError("Sync job ID is required")

    # Get retry count from job details
    retry_count = job_obj.details_json.get("retry_count", 0) if job_obj.details_json else 0

    # Import here to avoid circular imports
    from hub.apps.integrations.tasks import execute_marketplace_sync

    # Execute the sync task
    # Note: execute_marketplace_sync is a django-rq job, but we can call it directly
    # from within another job handler. The @job decorator makes it callable as a function.
    result = execute_marketplace_sync(sync_job_id, retry_count=retry_count)

    # Ensure result is a dict
    if result is None:
        return {"status": "completed", "sync_job_id": sync_job_id}
    return result
