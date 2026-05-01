"""
Job Processing Tasks Base

Core job processing infrastructure: queue management, slot tracking, error handling.

SAVING CHECKPOINT: This module contains the core job processing infrastructure.
"""

import time
import traceback as tb_module
from datetime import timedelta

import structlog
from django.db import transaction
from django.utils import timezone
from django_rq import job

from hub.apps.audit.utils import create_audit_event

from .models import FailedJobDLQ, Job, JobPriority, JobStatus, JobType
from .utils import (
    WORKER_MAX_CONCURRENCY,
    WORKER_MAX_CONCURRENCY_PER_TENANT,
    WORKER_RESERVED_SLOTS,
    WORKER_SHARED_SLOTS,
    decrement_reserved_slots_usage,
    decrement_shared_slots_usage,
    decrement_tenant_job_counter,
    get_job_wait_time,
    get_queue_for_job_type,
    increment_shared_slots_usage,
    increment_tenant_job_counter,
    retry_job,
    should_elevate_job,
    try_acquire_reserved_slot,
    try_acquire_shared_slot,
)

logger = structlog.get_logger(__name__)


def _write_to_dlq(job_obj: Job, job_type: str, exception: Exception):
    """
    Write a failed job to the dead-letter queue (Phase 91.8).

    Called when a job reaches its final failure — either because max
    retries are exhausted or the error is non-transient.  Best-effort:
    failures are logged and never propagate.
    """
    try:
        FailedJobDLQ.objects.create(
            job_id=job_obj.id,
            queue=get_queue_for_job_type(job_type),
            func_name=f"hub.apps.jobs.tasks_base.process_job",
            args_json={
                "job_id": str(job_obj.id),
                "job_type": job_type,
            },
            error_message=str(exception),
            traceback=tb_module.format_exc(),
            tenant=job_obj.tenant,
        )
        logger.info(
            "job_written_to_dlq",
            job_id=str(job_obj.id),
            job_type=job_type,
            error_type=type(exception).__name__,
        )
    except Exception as dlq_err:
        logger.error(
            "dlq_write_failed",
            job_id=str(job_obj.id),
            error=str(dlq_err),
            exc_info=True,
        )


@job("default", timeout=600)
def process_job(job_id: str, job_type: str, timeout: int = 600):
    """
    Process a job.

    This is a placeholder that will be extended by specific job handlers.
    For MVP, this demonstrates the job processing pattern.

    Implements reserved slots and starvation prevention:
    - HIGH priority jobs (job_critical) can use reserved slots or shared slots
    - NORMAL priority jobs (job_default) can use shared slots, or reserved slots if elevated
    - LOW priority jobs (job_low) can only use shared slots
    - NORMAL priority jobs are elevated to HIGH if they've been waiting > threshold

    Args:
        job_id: UUID of the job
        job_type: Job type string
        timeout: Job timeout in seconds
    """
    # Determine queue name and check starvation prevention
    queue_name = get_queue_for_job_type(job_type)
    is_elevated = should_elevate_job(job_id, queue_name)
    wait_time = get_job_wait_time(job_id)

    # ── Step 1: Atomically claim the job (PENDING → RUNNING). ────────────────
    # A single UPDATE WHERE status='PENDING' is the definitive TOCTOU fix:
    # exactly one worker among N concurrent claimers gets claimed_count == 1.
    # select_for_update() is not needed here because a bare UPDATE with a
    # WHERE-clause is already atomic at the SQL level on any MVCC database.
    _now = timezone.now()
    with transaction.atomic():
        claimed_count = Job.objects.filter(
            id=job_id,
            status=JobStatus.PENDING,
        ).update(
            status=JobStatus.RUNNING,
            started_at=_now,
        )

    if claimed_count == 0:
        # Another worker already claimed the job, or it was cancelled/completed.
        try:
            _status = Job.objects.values_list("status", flat=True).get(id=job_id)
            if _status == JobStatus.CANCELLED:
                logger.info(
                    "job_cancelled_before_processing",
                    job_id=job_id,
                )
            else:
                logger.warning(
                    "job_already_claimed",
                    job_id=job_id,
                    current_status=_status,
                )
        except Job.DoesNotExist:
            logger.error("job_not_found", job_id=job_id)
        return

    # Slot type determined after claim; also captures tenant_id for
    # the finally block so we avoid a redundant DB query there.
    slot_type = None
    _tenant_id: str | None = None
    try:
        # ── Step 2: Load full job object with FK relations for audit events. ──
        job_obj = Job.objects.select_related("created_by", "tenant").get(
            id=job_id
        )
        # Capture tenant_id now so the finally block doesn't need to re-query.
        _tenant_id = str(job_obj.tenant.id) if job_obj.tenant else None

        # Determine slot type based on queue and elevation.
        # try_acquire_*_slot() performs the check-and-increment atomically via
        # a Lua script, eliminating the TOCTOU race of the old
        # can_use_*_slot() + increment_*_slots_usage() two-step pattern.
        if queue_name == "job_critical" or (
            queue_name == "job_default" and is_elevated
        ):
            # HIGH priority or elevated: reserved slot first, shared as fallback
            if try_acquire_reserved_slot():
                slot_type = "reserved"
            elif try_acquire_shared_slot():
                slot_type = "shared"
            else:
                # No slots – django-rq already pulled the job so we must run it
                logger.warning(
                    "job_no_slots_available",
                    job_id=job_id,
                    queue_name=queue_name,
                    is_elevated=is_elevated,
                    message="Job picked but no slots available",
                )
                slot_type = "shared"
                increment_shared_slots_usage()
        else:
            # NORMAL or LOW priority: shared slot only
            if try_acquire_shared_slot():
                slot_type = "shared"
            else:
                logger.warning(
                    "job_no_slots_available",
                    job_id=job_id,
                    queue_name=queue_name,
                    message="Job picked but no slots available",
                )
                slot_type = "shared"
                increment_shared_slots_usage()

        # Increment tenant job counter
        increment_tenant_job_counter(job_obj.tenant_id)

        # Execute job logic
        start_time = time.time()
        try:
            result = _execute_job_logic(job_obj, job_type)
            execution_time = time.time() - start_time

            # Mark job as completed
            job_obj.status = JobStatus.COMPLETED
            job_obj.completed_at = timezone.now()
            job_obj.result_json = result
            # Store execution time in details_json
            if job_obj.details_json is None:
                job_obj.details_json = {}
            job_obj.details_json["execution_time_seconds"] = execution_time
            job_obj.save(
                update_fields=[
                    "status",
                    "completed_at",
                    "result_json",
                    "details_json",
                ]
            )

            if job_type == JobType.CONTRACT_VALIDATION:
                from hub.apps.contracts.invalidation_cascade import (
                    persist_contract_validation_job_result,
                )

                persist_contract_validation_job_result(job_obj, result)

            # Log success
            logger.info(
                "job_completed",
                job_id=job_id,
                job_type=job_type,
                execution_time=execution_time,
                slot_type=slot_type,
                is_elevated=is_elevated,
            )

            # Create audit event
            create_audit_event(
                resource_type="JOB",
                action="JOB_COMPLETED",
                actor_user=job_obj.created_by,
                tenant=job_obj.tenant,
                resource_id=str(job_obj.id),
                details={
                    "job_type": job_type,
                    "execution_time": execution_time,
                    "result": result,
                },
            )

        except ValueError as e:
            # Validation error - mark as failed
            execution_time = time.time() - start_time
            job_obj.status = JobStatus.FAILED
            job_obj.completed_at = timezone.now()
            job_obj.error_message = str(e)
            job_obj.result_json = {"error": str(e), "error_code": "VALIDATION_ERROR"}
            # Store execution time in details_json
            if job_obj.details_json is None:
                job_obj.details_json = {}
            job_obj.details_json["execution_time_seconds"] = execution_time
            job_obj.save(
                update_fields=[
                    "status",
                    "completed_at",
                    "error_message",
                    "result_json",
                    "details_json",
                ]
            )

            logger.error(
                "job_failed_validation",
                job_id=job_id,
                job_type=job_type,
                error=str(e),
                execution_time=execution_time,
            )

            # Create audit event
            create_audit_event(
                resource_type="JOB",
                action="JOB_FAILED",
                actor_user=job_obj.created_by,
                tenant=job_obj.tenant,
                resource_id=str(job_obj.id),
                details={"job_type": job_type, "error": str(e), "error_type": "ValidationError"},
            )

            # Non-transient — write to DLQ immediately
            _write_to_dlq(job_obj, job_type, e)

        except TimeoutError as e:
            # Timeout error - mark as failed
            execution_time = time.time() - start_time
            job_obj.status = JobStatus.FAILED
            job_obj.completed_at = timezone.now()
            job_obj.error_message = f"Job timeout after {timeout} seconds"
            job_obj.result_json = {"error": job_obj.error_message, "error_code": "TIMEOUT"}
            # Store execution time in details_json
            if job_obj.details_json is None:
                job_obj.details_json = {}
            job_obj.details_json["execution_time_seconds"] = execution_time
            job_obj.save(
                update_fields=[
                    "status",
                    "completed_at",
                    "error_message",
                    "result_json",
                    "details_json",
                ]
            )

            logger.error(
                "job_failed_timeout",
                job_id=job_id,
                job_type=job_type,
                timeout=timeout,
                execution_time=execution_time,
            )

            # Create audit event
            create_audit_event(
                resource_type="JOB",
                action="JOB_FAILED",
                actor_user=job_obj.created_by,
                tenant=job_obj.tenant,
                resource_id=str(job_obj.id),
                details={
                    "job_type": job_type,
                    "error": "Timeout",
                    "timeout": timeout,
                    "error_type": "TimeoutError",
                },
            )

            # Non-transient — write to DLQ immediately
            _write_to_dlq(job_obj, job_type, e)

        except ConnectionError as e:
            # Connection error - mark as failed (service unavailable)
            execution_time = time.time() - start_time
            job_obj.status = JobStatus.FAILED
            job_obj.completed_at = timezone.now()
            job_obj.error_message = str(e)
            job_obj.result_json = {"error": str(e), "error_code": "SERVICE_UNAVAILABLE"}
            # Store execution time in details_json
            if job_obj.details_json is None:
                job_obj.details_json = {}
            job_obj.details_json["execution_time_seconds"] = execution_time
            job_obj.save(
                update_fields=[
                    "status",
                    "completed_at",
                    "error_message",
                    "result_json",
                    "details_json",
                ]
            )

            logger.error(
                "job_failed_connection",
                job_id=job_id,
                job_type=job_type,
                error=str(e),
                execution_time=execution_time,
            )

            # Try to retry job if appropriate (ConnectionError is transient)
            retried = False
            try:
                retried = retry_job(job_obj, job_type, e)
            except Exception as retry_error:
                logger.error(
                    "job_retry_failed",
                    job_id=job_id,
                    error=str(retry_error),
                    exc_info=True,
                )

            # If not retried (exhausted), write to DLQ
            if not retried:
                _write_to_dlq(job_obj, job_type, e)

            # Create audit event
            create_audit_event(
                resource_type="JOB",
                action="JOB_FAILED",
                actor_user=job_obj.created_by,
                tenant=job_obj.tenant,
                resource_id=str(job_obj.id),
                details={
                    "job_type": job_type,
                    "error": str(e),
                    "error_type": "ConnectionError",
                },
            )

        except Exception as e:
            # Other errors - mark as failed and potentially retry
            execution_time = time.time() - start_time
            job_obj.status = JobStatus.FAILED
            job_obj.completed_at = timezone.now()
            job_obj.error_message = str(e)
            job_obj.result_json = {"error": str(e), "error_code": "UNKNOWN_ERROR"}
            # Store execution time in details_json
            if job_obj.details_json is None:
                job_obj.details_json = {}
            job_obj.details_json["execution_time_seconds"] = execution_time
            job_obj.save(
                update_fields=[
                    "status",
                    "completed_at",
                    "error_message",
                    "result_json",
                    "details_json",
                ]
            )

            logger.error(
                "job_failed",
                job_id=job_id,
                job_type=job_type,
                error=str(e),
                execution_time=execution_time,
                exc_info=True,
            )

            # Try to retry job if appropriate
            retried = False
            try:
                retried = retry_job(job_obj, job_type, e)
            except Exception as retry_error:
                logger.error(
                    "job_retry_failed",
                    job_id=job_id,
                    error=str(retry_error),
                    exc_info=True,
                )

            # If not retried (exhausted), write to DLQ
            if not retried:
                _write_to_dlq(job_obj, job_type, e)

            # Create audit event
            create_audit_event(
                resource_type="JOB",
                action="JOB_FAILED",
                actor_user=job_obj.created_by,
                tenant=job_obj.tenant,
                resource_id=str(job_obj.id),
                details={
                    "job_type": job_type,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )

    except Job.DoesNotExist:
        logger.error("job_not_found", job_id=job_id, message=f"Job {job_id} not found")
    except Exception as e:
        logger.error(
            "job_processing_error",
            job_id=job_id,
            job_type=job_type,
            error=str(e),
            exc_info=True,
        )
    finally:
        # Decrement slot usage
        if slot_type == "reserved":
            decrement_reserved_slots_usage()
        elif slot_type == "shared":
            decrement_shared_slots_usage()

        # Decrement tenant job counter.
        # _tenant_id was captured right after the initial Job.objects.get()
        # call, so no second DB query is needed here.
        if _tenant_id:
            decrement_tenant_job_counter(_tenant_id)


def _execute_job_logic(job_obj: Job, job_type: str) -> dict:
    """
    Execute job logic based on job type.

    Delegates to specific job handlers in separate modules.

    Args:
        job_obj: Job instance
        job_type: Job type string

    Returns:
        Result dictionary with job execution results

    Raises:
        ValueError: For validation errors (missing parameters, invalid resource types)
        TimeoutError: For timeout errors
        ConnectionError: For service connection errors
        Exception: For other errors (will be caught and logged)
    """
    # Import job handlers dynamically to avoid circular imports
    if job_type == JobType.DQ_RUN:
        from .tasks_dq import _execute_dq_run_job

        return _execute_dq_run_job(job_obj)

    elif job_type == JobType.COMPLIANCE_RUN:
        from .tasks_compliance import _execute_compliance_run_job

        return _execute_compliance_run_job(job_obj)

    elif job_type == JobType.CONTRACT_VALIDATION:
        from .tasks_contract import _execute_contract_validation_job

        return _execute_contract_validation_job(job_obj)

    elif job_type == JobType.SEMANTIC_MAPPING:
        from .tasks_contract import _execute_semantic_mapping_job

        return _execute_semantic_mapping_job(job_obj)

    elif job_type == JobType.CONTRACT_MIGRATION:
        from .tasks_contract import _execute_contract_migration_job

        return _execute_contract_migration_job(job_obj)

    elif job_type == JobType.SCHEDULED_INGESTION:
        # Phase 3: SCHEDULED_INGESTION is executed only by Prefect. RQ handler no-ops
        # (job record may exist for UI/audit from Prefect flow; no legacy RQ execution).
        return {
            "executed_by_prefect": True,
            "message": "SCHEDULED_INGESTION executed by Prefect only; RQ worker no-op.",
            "prefect_flow_run_id": (job_obj.details_json or {}).get("prefect_flow_run_id"),
        }

    elif job_type == JobType.RETENTION_POLICY_ENFORCEMENT:
        from .tasks_governance import _execute_retention_policy_enforcement_job

        return _execute_retention_policy_enforcement_job(job_obj)

    elif job_type == JobType.SEARCH_INDEX_UPDATE:
        from .tasks_search import _execute_search_index_update_job

        return _execute_search_index_update_job(job_obj)

    elif job_type == JobType.ODPS_NORMALIZATION:
        from .tasks_odps import _execute_odps_normalization_job

        return _execute_odps_normalization_job(job_obj)

    elif job_type == JobType.ODPS_REF_RESOLUTION:
        from .tasks_odps import _execute_odps_ref_resolution_job

        return _execute_odps_ref_resolution_job(job_obj)

    elif job_type == JobType.ODPS_EXPORT:
        from .tasks_odps import _execute_odps_export_job

        return _execute_odps_export_job(job_obj)

    elif job_type == JobType.ODPS_SEMANTIC_MAPPING:
        from .tasks_odps import _execute_odps_semantic_mapping_job

        return _execute_odps_semantic_mapping_job(job_obj)

    elif job_type == JobType.ODPS_LINKING:
        from .tasks_odps import _execute_odps_linking_job

        return _execute_odps_linking_job(job_obj)

    elif job_type == JobType.VIRTUAL_QUERY_EXECUTION:
        from .tasks_virtualization import _execute_virtual_query_job

        return _execute_virtual_query_job(job_obj)

    elif job_type == JobType.MARKETPLACE_SYNC:
        from .tasks_marketplace import _execute_marketplace_sync_job

        return _execute_marketplace_sync_job(job_obj)

    elif job_type == JobType.SEMANTIC_SNAPSHOT:
        # Phase 230.4 (REQ-SEM-MEMENTO-001) — debounced snapshot job.
        from hub.apps.semantic.tasks import _execute_semantic_snapshot_job

        return _execute_semantic_snapshot_job(job_obj)

    else:
        raise ValueError(f"Unknown job type: {job_type}")


def check_job_timeouts():
    """
    Check for jobs that have exceeded their timeout and mark them as failed.

    Uses each job's timeout_seconds when set; otherwise defaults to 24 hours.
    This should be called periodically (e.g., via cron or scheduled task).
    """
    default_timeout_seconds = 86400  # 24 hours
    now = timezone.now()

    # select_related pre-fetches created_by and tenant so that the
    # create_audit_event() call inside the loop doesn't issue an extra
    # SELECT per job (N+1 elimination).
    running_jobs = (
        Job.objects.filter(status=JobStatus.RUNNING)
        .exclude(started_at__isnull=True)
        .select_related("created_by", "tenant")
    )

    for job_obj in running_jobs:
        timeout_seconds = job_obj.timeout_seconds if job_obj.timeout_seconds is not None else default_timeout_seconds
        threshold = now - timedelta(seconds=timeout_seconds)
        if job_obj.started_at >= threshold:
            continue

        job_obj.status = JobStatus.FAILED
        job_obj.completed_at = now
        error_msg = f"Job exceeded timeout ({timeout_seconds} seconds)"
        job_obj.error_message = error_msg
        job_obj.result_json = {"error": error_msg, "error_code": "TIMEOUT", "timeout": timeout_seconds}
        job_obj.save(update_fields=["status", "completed_at", "error_message", "result_json"])

        logger.warning(
            "job_timeout",
            job_id=str(job_obj.id),
            job_type=job_obj.type,
            started_at=job_obj.started_at.isoformat(),
            timeout_seconds=timeout_seconds,
        )

        # Create audit event
        create_audit_event(
            resource_type="JOB",
            action="JOB_TIMEOUT",
            actor_user=job_obj.created_by,
            tenant=job_obj.tenant,
            resource_id=str(job_obj.id),
            details={
                "job_type": job_obj.type,
                "started_at": job_obj.started_at.isoformat(),
                "timeout_seconds": timeout_seconds,
            },
        )
