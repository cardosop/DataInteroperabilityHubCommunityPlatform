"""
Job Utilities

Utilities for creating and managing jobs.
"""

import time
import uuid
from typing import Any

import structlog
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from django_rq import get_queue
from rest_framework.exceptions import ValidationError

from .models import Job, JobPriority, JobStatus, JobType

logger = structlog.get_logger(__name__)


# Default timeouts per job type (in seconds)
JOB_TIMEOUTS = {
    JobType.DQ_RUN: 1800,  # 30 minutes
    JobType.COMPLIANCE_RUN: 1800,  # 30 minutes
    JobType.CONTRACT_VALIDATION: 300,  # 5 minutes
    JobType.SEMANTIC_MAPPING: 60,  # 1 minute
    JobType.CONTRACT_MIGRATION: 600,  # 10 minutes
    JobType.SCHEDULED_INGESTION: 3600,  # 1 hour (file discovery, download, dataset creation can take time)
    JobType.RETENTION_POLICY_ENFORCEMENT: 3600,  # 1 hour
    JobType.SEARCH_INDEX_UPDATE: 300,  # 5 minutes
    JobType.ODPS_NORMALIZATION: 600,  # 10 minutes
    JobType.ODPS_REF_RESOLUTION: 600,  # 10 minutes
    JobType.ODPS_EXPORT: 300,  # 5 minutes
    JobType.ODPS_SEMANTIC_MAPPING: 600,  # 10 minutes
    JobType.ODPS_LINKING: 300,  # 5 minutes
    JobType.VIRTUAL_QUERY_EXECUTION: 3600,  # 1 hour (virtual queries can be long-running)
    JobType.MARKETPLACE_SYNC: 3600,  # 1 hour (sync operations can be long-running)
    JobType.ROPA_GENERATE: 1800,  # RoPA register export (may be large PDF/CSV)
    JobType.DPIA_REVIEW_DUE: 600,  # Periodic DPIA reopen sweep (multi-tenant)
    JobType.PROCESSOR_AGREEMENT_EXPIRY_CHECK: 600,  # Processor agreement 60/30/7-day sweep
    JobType.RETENTION_ENFORCEMENT_SWEEP: 3600,  # Retention tombstone/hard-delete multi-tenant sweep
}

# Maximum retry attempts per job type (from settings, fallback to defaults)
JOB_MAX_RETRIES = getattr(
    settings,
    "JOB_RETRY_MAX_ATTEMPTS",
    {
        JobType.DQ_RUN: 3,
        JobType.COMPLIANCE_RUN: 3,
        JobType.CONTRACT_VALIDATION: 2,
        JobType.SEMANTIC_MAPPING: 2,
        JobType.CONTRACT_MIGRATION: 1,
        JobType.SCHEDULED_INGESTION: 2,
        JobType.RETENTION_POLICY_ENFORCEMENT: 1,
        JobType.SEARCH_INDEX_UPDATE: 2,
        JobType.ODPS_NORMALIZATION: 2,
        JobType.ODPS_REF_RESOLUTION: 2,
        JobType.ODPS_EXPORT: 2,
        JobType.ODPS_SEMANTIC_MAPPING: 2,
        JobType.ODPS_LINKING: 2,
        JobType.VIRTUAL_QUERY_EXECUTION: 2,
        JobType.MARKETPLACE_SYNC: 2,
        JobType.DPIA_REVIEW_DUE: 1,
        JobType.PROCESSOR_AGREEMENT_EXPIRY_CHECK: 1,
        JobType.RETENTION_ENFORCEMENT_SWEEP: 1,
    },
)

# Base delay for exponential backoff (in seconds) - deprecated, use JOB_RETRY_INITIAL_DELAY per job type
JOB_RETRY_BASE_DELAY = 60  # Start with 1 minute delay (fallback)

# Worker concurrency limits (from settings)
WORKER_MAX_CONCURRENCY = settings.WORKER_MAX_CONCURRENCY
WORKER_MAX_CONCURRENCY_PER_TENANT = settings.WORKER_MAX_CONCURRENCY_PER_TENANT
WORKER_RESERVED_SLOTS = settings.WORKER_RESERVED_SLOTS
WORKER_SHARED_SLOTS = settings.WORKER_SHARED_SLOTS
WORKER_STARVATION_THRESHOLD_SECONDS = settings.WORKER_STARVATION_THRESHOLD_SECONDS


def get_job_timeout(job_type: str) -> int:
    """
    Get timeout for a job type.

    Args:
        job_type: Job type string

    Returns:
        Timeout in seconds
    """
    return JOB_TIMEOUTS.get(job_type, 600)  # Default 10 minutes


def _normalize_job_type_key(job_type) -> str:
    """Normalize job_type to string for dict lookups (handles TextChoices enum)."""
    if hasattr(job_type, "value"):
        return job_type.value
    return str(job_type)


def get_job_max_retries(job_type) -> int:
    """
    Get maximum retry attempts for a job type.

    Args:
        job_type: Job type (string or JobType enum)

    Returns:
        Maximum retry attempts
    """
    key = _normalize_job_type_key(job_type)
    return JOB_MAX_RETRIES.get(key, 2)


def get_job_retry_initial_delay(job_type) -> int:
    """
    Get initial retry delay for a job type.

    Args:
        job_type: Job type (string or JobType enum)

    Returns:
        Initial delay in seconds
    """
    key = _normalize_job_type_key(job_type)
    retry_initial_delay = getattr(settings, "JOB_RETRY_INITIAL_DELAY", {})
    return retry_initial_delay.get(key, JOB_RETRY_BASE_DELAY)


def get_job_retry_max_delay(job_type) -> int:
    """
    Get maximum retry delay cap for a job type.

    Args:
        job_type: Job type (string or JobType enum)

    Returns:
        Maximum delay in seconds
    """
    key = _normalize_job_type_key(job_type)
    retry_max_delay = getattr(settings, "JOB_RETRY_MAX_DELAY", {})
    return retry_max_delay.get(key, 3600)


def get_job_retry_backoff_factor(job_type) -> float:
    """
    Get exponential backoff factor for a job type.

    Args:
        job_type: Job type (string or JobType enum)

    Returns:
        Backoff factor (default: 2.0)
    """
    key = _normalize_job_type_key(job_type)
    retry_backoff_factor = getattr(settings, "JOB_RETRY_BACKOFF_FACTOR", {})
    return retry_backoff_factor.get(key, 2.0)


def is_transient_failure(exception: Exception) -> bool:
    """
    Check if an exception represents a transient failure that should be retried.

    Transient failures include:
    - ConnectionError: Service unavailable, network issues
    - TimeoutError: Request timeout, service slow to respond
    - Temporary service unavailability

    Non-transient failures (should not retry):
    - ValueError: Invalid input, validation errors
    - Resource not found errors

    Args:
        exception: Exception instance

    Returns:
        True if exception is transient and should be retried
    """
    if isinstance(exception, (ConnectionError, TimeoutError)):
        return True

    error_str = str(exception).lower()
    transient_keywords = [
        "timeout",
        "timed out",
        "connection",
        "unavailable",
        "network",
        "temporary",
        "retry",
        "service unavailable",
        "503",
        "502",
        "504",
    ]

    return any(keyword in error_str for keyword in transient_keywords)


def calculate_retry_delay(retry_count: int, job_type: str = None, base_delay: int = None) -> int:
    """
    Calculate retry delay using exponential backoff with configurable factors.

    Formula: initial_delay * (backoff_factor ^ retry_count), capped at max_delay
    - Retry 1: initial_delay * backoff_factor^0
    - Retry 2: initial_delay * backoff_factor^1
    - Retry 3: initial_delay * backoff_factor^2

    Args:
        retry_count: Current retry attempt (0-indexed)
        job_type: Job type string (optional, for job-specific configuration)
        base_delay: Base delay in seconds (optional, deprecated - use job_type instead)

    Returns:
        Delay in seconds (capped at max_delay for job type)
    """
    if job_type:
        initial_delay = get_job_retry_initial_delay(job_type)
        backoff_factor = get_job_retry_backoff_factor(job_type)
        max_delay = get_job_retry_max_delay(job_type)
    else:
        # Fallback to old behavior for backward compatibility
        initial_delay = base_delay if base_delay is not None else JOB_RETRY_BASE_DELAY
        backoff_factor = 2.0
        max_delay = 3600  # Default 1 hour

    delay = int(initial_delay * (backoff_factor**retry_count))
    return min(delay, max_delay)  # Cap at max_delay


def retry_job(job_obj: Job, job_type: str, exception: Exception) -> bool:
    """
    Retry a failed job if retries are remaining and error is transient.

    Args:
        job_obj: Job instance
        job_type: Job type string
        exception: Exception that caused the failure

    Returns:
        True if job was retried, False if no retries remaining or error is not transient
    """
    # Check if error is transient
    if not is_transient_failure(exception):
        return False

    # Get current retry count from details_json
    retry_count = job_obj.details_json.get("retry_count", 0)
    max_retries = get_job_max_retries(job_type)

    # Check if retries remaining
    if retry_count >= max_retries:
        logger.info(
            "job_retry_exhausted",
            job_id=str(job_obj.id),
            tenant_id=str(job_obj.tenant.id) if job_obj.tenant else None,
            job_type=job_type,
            retry_count=retry_count,
            max_retries=max_retries,
            message=f"Job {job_obj.id} exceeded max retries ({max_retries})",
        )
        return False

    # Increment retry count
    new_retry_count = retry_count + 1
    if job_obj.details_json is None:
        job_obj.details_json = {}
    job_obj.details_json["retry_count"] = new_retry_count
    job_obj.details_json["last_retry_error"] = str(exception)
    job_obj.details_json["last_retry_at"] = timezone.now().isoformat()

    # Calculate retry delay
    retry_delay = calculate_retry_delay(retry_count, job_type=job_type)

    # Track retry metrics
    try:
        from hub.apps.observability.otel_metrics import (
            job_retry_count,
            job_retry_delay_seconds,
        )

        queue_name = get_queue_for_job_type(job_type)
        job_retry_count.labels(job_type=job_type, queue_name=queue_name).observe(new_retry_count)
        job_retry_delay_seconds.labels(job_type=job_type).observe(retry_delay)
    except Exception:
        pass  # Metrics may not be available

    # Reset job status to PENDING for retry
    job_obj.status = JobStatus.PENDING
    job_obj.started_at = None  # Reset started_at for retry
    job_obj.completed_at = None  # Reset completed_at for retry
    job_obj.error_message = None  # Clear error message
    job_obj.save(
        update_fields=[
            "status",
            "started_at",
            "completed_at",
            "error_message",
            "details_json",
            "updated_at",
        ]
    )

    # Re-enqueue job with delay
    queue_name = get_queue_for_job_type(job_type)
    queue = get_queue(queue_name)

    # Use queue.enqueue_in to schedule job with delay
    # Import here to avoid circular imports
    from datetime import timedelta

    from .tasks import process_job

    queue.enqueue_in(
        timedelta(seconds=retry_delay),
        process_job,
        str(job_obj.id),
        job_type=job_type,
        timeout=get_job_timeout(job_type),
    )

    # Update tenant job counter: increment queued (job is back in queue)
    if job_obj.tenant:
        increment_tenant_job_counter(str(job_obj.tenant.id), "queued")

    logger.info(
        "job_retry_scheduled",
        job_id=str(job_obj.id),
        tenant_id=str(job_obj.tenant.id) if job_obj.tenant else None,
        job_type=job_type,
        retry_count=new_retry_count,
        max_retries=max_retries,
        retry_delay_seconds=retry_delay,
        error_type=type(exception).__name__,
        message=f"Job {job_obj.id} scheduled for retry {new_retry_count}/{max_retries} after {retry_delay}s",
    )

    return True


def check_tenant_job_limits(tenant_id: str) -> tuple[bool, str | None]:
    """
    Check if tenant has capacity for a new job (concurrency and queue depth).

    Checks:
    1. Running jobs < max_job_concurrency
    2. Queued jobs < max_queued_jobs

    Uses Redis counters for atomic operations.

    Args:
        tenant_id: Tenant UUID as string

    Returns:
        Tuple of (can_create_job: bool, error_message: Optional[str])
    """
    from hub.apps.tenants.services import get_tenant_job_limits

    try:
        limits = get_tenant_job_limits(tenant_id)
        max_concurrency = limits["max_job_concurrency"]
        max_queued = limits["max_queued_jobs"]

        # Get current counts from Redis (atomic operations)
        # Key format: job:tenant:{tenant_id}:running, job:tenant:{tenant_id}:queued
        running_key = f"job:tenant:{tenant_id}:running"
        queued_key = f"job:tenant:{tenant_id}:queued"

        # Get current counts (default to 0 if keys don't exist)
        running_count = cache.get(running_key, 0)
        queued_count = cache.get(queued_key, 0)

        # Check concurrency limit
        if running_count >= max_concurrency:
            return False, (
                f"Tenant has reached maximum concurrent job limit ({max_concurrency}). "
                f"Current running jobs: {running_count}. Please wait for jobs to complete."
            )

        # Check queue depth limit
        if queued_count >= max_queued:
            return False, (
                f"Tenant has reached maximum queued job limit ({max_queued}). "
                f"Current queued jobs: {queued_count}. Please wait for queue to process."
            )

        return True, None
    except Exception as e:
        logger.warning(
            "tenant_job_limit_check_failed",
            tenant_id=tenant_id,
            error=str(e),
            message="Failed to check tenant job limits, allowing job creation",
        )
        # On error, allow job creation (graceful degradation)
        return True, None


def get_tenant_job_counter(tenant_id: str, counter_type: str) -> int:
    """Get current value of tenant job counter."""
    key = f"job:tenant:{tenant_id}:{counter_type}"
    return cache.get(key, 0)


def increment_tenant_job_counter(tenant_id: str, counter_type: str = "queued") -> None:
    """
    Increment tenant job counter in Redis and update Prometheus metrics.

    Uses cache.add() (atomic SETNX) to initialise the key when absent, then
    cache.incr() for the actual increment.  The return value of incr() is
    reused directly for metrics, avoiding the extra cache.get() round-trip
    that the previous implementation required.

    Args:
        tenant_id: Tenant UUID as string
        counter_type: "running" or "queued"
    """
    key = f"job:tenant:{tenant_id}:{counter_type}"
    try:
        # Initialise key atomically if absent, then increment.
        # cache.add() maps to SETNX in Redis (no-op if key already exists).
        # cache.incr() returns the post-increment value, so no second GET needed.
        cache.add(key, 0, timeout=86400)
        new_count = cache.incr(key)
        # Refresh TTL so active counters never expire mid-day.
        # expire() is a django-redis extension not present on BaseCache.
        try:
            cache.expire(key, 86400)  # type: ignore[attr-defined]  # django-redis extension; LocMemCache fallback below
        except AttributeError:
            pass  # LocMemCache doesn't expose expire – safe to skip in tests

        # Update Prometheus metrics using the value already returned by incr()
        try:
            from hub.apps.observability.otel_metrics import tenant_queued_jobs, tenant_running_jobs

            if counter_type == "running":
                tenant_running_jobs.labels(tenant_id=tenant_id).set(new_count)
            elif counter_type == "queued":
                tenant_queued_jobs.labels(tenant_id=tenant_id).set(new_count)
        except Exception:
            pass  # Metrics may not be available
    except Exception as e:
        logger.warning(
            "tenant_job_counter_increment_failed",
            tenant_id=tenant_id,
            counter_type=counter_type,
            error=str(e),
            message="Failed to increment tenant job counter",
        )


def decrement_tenant_job_counter(tenant_id: str, counter_type: str = "running") -> None:
    """
    Decrement tenant job counter in Redis and update Prometheus metrics.

    The return value of decr() is reused directly for metrics, avoiding the
    extra cache.get() call that the previous implementation made.

    Args:
        tenant_id: Tenant UUID as string
        counter_type: "running" or "queued"
    """
    key = f"job:tenant:{tenant_id}:{counter_type}"
    try:
        current = cache.get(key, 0)
        new_count = cache.decr(key) if current > 0 else 0
        # Refresh TTL
        try:
            cache.expire(key, 86400)  # type: ignore[attr-defined]  # django-redis extension; LocMemCache fallback below
        except AttributeError:
            pass  # LocMemCache doesn't expose expire – safe to skip in tests

        # Update Prometheus metrics using the value already returned by decr()
        try:
            from hub.apps.observability.otel_metrics import tenant_queued_jobs, tenant_running_jobs

            if counter_type == "running":
                tenant_running_jobs.labels(tenant_id=tenant_id).set(new_count)
            elif counter_type == "queued":
                tenant_queued_jobs.labels(tenant_id=tenant_id).set(new_count)
        except Exception:
            pass  # Metrics may not be available
    except Exception as e:
        logger.warning(
            "tenant_job_counter_decrement_failed",
            tenant_id=tenant_id,
            counter_type=counter_type,
            error=str(e),
            message="Failed to decrement tenant job counter",
        )


def get_job_priority(job_type: str, priority: str | None = None) -> str:
    """
    Get priority for a job type.

    Priority assignment rules:
    1. If priority is explicitly provided, use it
    2. If job_type has a priority rule in JOB_PRIORITY_RULES, use it
    3. Otherwise, use JOB_PRIORITY_DEFAULT

    Args:
        job_type: Job type string
        priority: Explicit priority (optional)

    Returns:
        Priority string (HIGH, NORMAL, LOW)
    """
    if priority:
        return priority

    # Check priority rules
    priority_rule = settings.JOB_PRIORITY_RULES.get(job_type)
    if priority_rule:
        return priority_rule

    # Use default priority
    return settings.JOB_PRIORITY_DEFAULT


def get_queue_for_priority(priority: str) -> str:
    """
    Get queue name for a priority level.

    Priority to queue mapping:
    - HIGH -> job_critical
    - NORMAL -> job_default
    - LOW -> job_low

    Args:
        priority: Priority string (HIGH, NORMAL, LOW)

    Returns:
        Queue name
    """
    priority_to_queue = {
        JobPriority.HIGH: "job_critical",
        JobPriority.NORMAL: "job_default",
        JobPriority.LOW: "job_low",
    }
    return priority_to_queue.get(priority, "job_default")


def create_job(
    tenant=None,
    user=None,
    job_type: str = None,
    resource_type: str = None,
    resource_id: str = None,
    details_json: dict[str, Any] | None = None,
    timeout_seconds: int | None = None,
    queue_name: str = "default",
    priority: str | None = None,
    executed_by_prefect: bool = False,
    created_by=None,  # Alias for ``user`` — Phase 278 callers use this name.
) -> Job:
    """
    Create a job and optionally enqueue it for processing.

    When executed_by_prefect=True (e.g. Prefect flow creates the job for UI/audit),
    the job is created but NOT enqueued to RQ; RQ worker will no-op when it sees
    this job. details_json should include prefect_flow_run_id for UI linking.

    Checks tenant job limits (concurrency and queue depth) before creating job,
    unless executed_by_prefect=True (Prefect-executed jobs are not counted as queued).

    Args:
        tenant: Tenant instance (optional)
        user: User instance (optional, alias for created_by)
        created_by: User instance (optional, alias for user)
        job_type: Job type (from JobType enum)
        resource_type: Resource type (CONTRACT, DATASET, FILE, ASSET, etc.)
        resource_id: UUID of the resource
        details_json: Additional job details (optional; for Prefect include prefect_flow_run_id)
        timeout_seconds: Timeout in seconds (optional, defaults to job type default)
        queue_name: Queue name ('default', 'high', 'low') - deprecated, use priority instead
        priority: Job priority (HIGH, NORMAL, LOW) - if not provided, determined from job_type
        executed_by_prefect: If True, job is not enqueued; RQ worker will skip execution.

    Returns:
        Created Job instance

    Raises:
        ValidationError: If tenant job limits are exceeded (when not executed_by_prefect)
        ValueError: If job_type, resource_type, or resource_id is missing, or resource_id is not a valid UUID
    """
    # Validate required fields before touching DB
    if job_type is None:
        raise ValueError("job_type is required")
    if resource_type is None:
        raise ValueError("resource_type is required")
    if resource_id is None:
        raise ValueError("resource_id is required")
    # Alias: if caller passes ``created_by=``, resolve to ``user``.
    if user is None and created_by is not None:
        user = created_by
    try:
        uuid.UUID(str(resource_id))
    except (ValueError, TypeError):
        raise ValueError("resource_id must be a valid UUID") from None

    # Phase 3: SCHEDULED_INGESTION is never enqueued; only Prefect runs it.
    will_enqueue = not executed_by_prefect and job_type != JobType.SCHEDULED_INGESTION
    # Check tenant job limits if tenant is provided and job will be enqueued
    if tenant and will_enqueue:
        can_create, error_message = check_tenant_job_limits(str(tenant.id))
        if not can_create:
            raise ValidationError(error_message)

    # Get timeout for job type if not provided
    if timeout_seconds is None:
        timeout_seconds = get_job_timeout(job_type) if job_type else 600

    # Determine priority
    job_priority = get_job_priority(job_type, priority)

    # Merge executed_by_prefect into details when needed; preserve explicit None for details_json
    merged_details = {} if details_json is None else dict(details_json)
    if executed_by_prefect or job_type == JobType.SCHEDULED_INGESTION:
        merged_details["executed_by_prefect"] = True
    final_details = None if (details_json is None and not merged_details) else merged_details

    # Create job record
    job = Job.objects.create(
        tenant=tenant,
        type=job_type,
        status=JobStatus.PENDING,
        priority=job_priority,
        resource_type=resource_type,
        resource_id=resource_id,
        created_by=user,
        timeout_seconds=timeout_seconds,
        details_json=final_details,
    )

    if executed_by_prefect or job_type == JobType.SCHEDULED_INGESTION:
        # Do not enqueue; SCHEDULED_INGESTION is executed by Prefect only
        logger.info(
            "job_created_prefect_executed",
            job_id=str(job.id),
            tenant_id=str(tenant.id) if tenant else None,
            job_type=job_type,
            message="Job created for Prefect execution (not enqueued to RQ).",
        )
        return job

    # Increment queued counter before enqueuing
    if tenant:
        increment_tenant_job_counter(str(tenant.id), "queued")
        logger.info(
            "job_created",
            job_id=str(job.id),
            tenant_id=str(tenant.id),
            job_type=job_type,
            message=f"Job created and queued for tenant {tenant.id}",
        )

    # Track job enqueue timestamp for starvation prevention
    enqueue_timestamp = time.time()
    cache.set(
        f"job:enqueue_time:{job.id}",
        enqueue_timestamp,
        timeout=86400,  # 24 hours
    )

    # Determine queue name from priority if not explicitly provided
    if queue_name == "default":
        queue_name = get_queue_for_priority(job_priority)

    # Enqueue job for processing
    try:
        queue = get_queue(queue_name)
        from .tasks import process_job  # Import here to avoid circular imports

        _job_id = str(job.id)
        _job_type = job_type
        _timeout = timeout_seconds
        _queue = queue
        transaction.on_commit(
            lambda: _queue.enqueue(process_job, _job_id, job_type=_job_type, timeout=_timeout)
        )

        # Track priority metrics
        try:
            from hub.apps.observability.otel_metrics import job_queue_length_by_priority

            job_queue_length_by_priority.labels(
                priority=job_priority,
                job_type=job_type,
            ).inc()
        except Exception:
            pass  # Metrics may not be available
    except Exception as e:
        # The Job DB record exists in PENDING state but is NOT in the RQ queue.
        # The recover_stuck_jobs CronJob (Phase 25.8.2) runs every 15 minutes and
        # will detect this orphaned PENDING job, attempt to re-enqueue it, and mark
        # it FAILED with error_code=ORPHANED_PENDING if re-enqueue also fails.
        logger.error(
            "job_enqueue_failed",
            job_id=str(job.id),
            job_type=job_type,
            priority=job_priority,
            error=str(e),
            exc_info=True,
        )
        try:
            from hub.apps.observability.otel_metrics import job_enqueue_failed_total

            job_enqueue_failed_total.labels(job_type=job_type).inc()
        except Exception:
            pass

    return job


def get_queue_for_job_type(job_type: str) -> str:
    """
    Get RQ queue name for a job type.

    Queue / worker-pool mapping (Phase 16.4)
    ──────────────────────────────────────────────────────────────────────────
    job_critical  →  worker-heavy (WORKER_TYPE=heavy)
      DQ_RUN              — pandas DQ scan; up to 1800 s, high memory (DataFrames)
      COMPLIANCE_RUN      — policy evaluation across many rows; up to 1800 s

    job_default   →  worker-light (WORKER_TYPE=light)
      SCHEDULED_INGESTION — file discovery + dataset creation; up to 3600 s
                            (long but I/O-bound; does not need heavy-pod memory)
      RETENTION_POLICY_ENFORCEMENT — batch soft-deletes; up to 3600 s
      SEARCH_INDEX_UPDATE — Elasticsearch document push; < 300 s, I/O-bound
      ODPS_NORMALIZATION  — JSON→ODPS schema transform; up to 600 s
      ODPS_REF_RESOLUTION — resolve cross-dataset refs; up to 600 s
      ODPS_EXPORT         — zip + S3 upload; up to 300 s
      ODPS_SEMANTIC_MAPPING — LLM-assisted mapping; up to 600 s
      ODPS_LINKING        — link ODPS records; up to 300 s
      SEMANTIC_MAPPING    — ML-assisted column mapping; up to 60 s
      CONTRACT_MIGRATION  — schema migration across contract versions; up to 600 s
      VIRTUAL_QUERY_EXECUTION — data mesh query; up to 3600 s
      MARKETPLACE_SYNC    — external catalog sync; up to 3600 s

    job_low       →  worker-light (WORKER_TYPE=light)
      CONTRACT_VALIDATION — JSON schema validation; up to 300 s, CPU-light

    Rationale for the split:
      Heavy workers run one job at a time and have higher memory limits (2 GiB).
      Keeping DQ/compliance in job_critical prevents a wave of webhook deliveries
      from starving long-running DQ scans (and vice versa).  Light workers are
      scaled independently based on the job_default+job_low combined queue depth.
    ──────────────────────────────────────────────────────────────────────────

    Args:
        job_type: Job type string (from JobType enum or plain string)

    Returns:
        Queue name: "job_critical", "job_default", or "job_low"
    """
    # job_critical — heavy worker pool: long-running, memory-intensive jobs
    # (DQ scans load full DataFrames; compliance runs evaluate many-row policies)
    if job_type in [JobType.DQ_RUN, JobType.COMPLIANCE_RUN]:
        return "job_critical"

    # job_low — light worker pool: fast validation that must not block job_default
    if job_type in [JobType.CONTRACT_VALIDATION]:
        return "job_low"

    # job_default — light worker pool: I/O-bound operations (webhooks, cache
    # invalidation, search indexing, ODPS transforms, scheduled ingestion)
    return "job_default"


def get_job_enqueue_timestamp(job_id: str) -> float | None:
    """
    Get job enqueue timestamp from Redis.

    Args:
        job_id: Job UUID as string

    Returns:
        Enqueue timestamp (Unix timestamp) or None if not found
    """
    key = f"job:enqueue_time:{job_id}"
    return cache.get(key)


def get_job_wait_time(job_id: str) -> float | None:
    """
    Calculate job wait time in seconds.

    Args:
        job_id: Job UUID as string

    Returns:
        Wait time in seconds or None if timestamp not found
    """
    enqueue_timestamp = get_job_enqueue_timestamp(job_id)
    if enqueue_timestamp is None:
        return None
    return time.time() - enqueue_timestamp


def should_elevate_job(job_id: str, queue_name: str) -> bool:
    """
    Check if a job should be elevated due to starvation prevention.

    NORMAL priority jobs (job_default) are elevated to HIGH priority if they've been
    waiting longer than the starvation threshold.

    Args:
        job_id: Job UUID as string
        queue_name: Queue name ('job_critical', 'job_default', 'job_low')

    Returns:
        True if job should be elevated, False otherwise
    """
    # Only elevate NORMAL priority jobs (job_default)
    if queue_name != "job_default":
        return False

    wait_time = get_job_wait_time(job_id)
    if wait_time is None:
        return False

    return wait_time > WORKER_STARVATION_THRESHOLD_SECONDS


# ---------------------------------------------------------------------------
# Lua script: atomically increment a counter if it is below a limit.
#
# Returns the new counter value (>= 1) on success, or -1 if the limit has
# already been reached.  Running inside a single EVAL call gives us the
# read-modify-write atomicity that the previous get_or_set()+incr() pattern
# lacked (TOCTOU race under concurrent workers).
# ---------------------------------------------------------------------------
_LUA_TRY_ACQUIRE_SLOT = """
local current = tonumber(redis.call('GET', KEYS[1])) or 0
if current < tonumber(ARGV[1]) then
    local new_val = redis.call('INCR', KEYS[1])
    redis.call('EXPIRE', KEYS[1], 86400)
    return new_val
end
return -1
"""


def _try_acquire_slot(key: str, limit: int) -> bool:
    """
    Atomically check-and-increment a slot counter against *limit*.

    Uses a Lua script executed on the cache Redis instance so the check and
    the increment happen in a single round-trip with no race window.

    Falls back to an optimistic increment-then-rollback strategy when the
    cache backend does not support eval (e.g. LocMemCache in tests).  The
    fallback is not perfectly atomic but is correct under the low-concurrency
    conditions present in tests.

    Returns:
        True  – slot acquired (counter was below limit and was incremented)
        False – limit already reached (counter unchanged)
    """
    try:
        from hub.apps.core.redis_pools import get_redis_cache_client

        r = get_redis_cache_client()
        result = r.eval(_LUA_TRY_ACQUIRE_SLOT, 1, key, limit)
        return int(result) != -1
    except Exception:
        # Non-Redis backend or Redis unreachable: optimistic increment with rollback.
        cache.add(key, 0, timeout=86400)  # SETNX – initialise if absent
        new_count = cache.incr(key)
        if new_count > limit:
            cache.decr(key)
            return False
        return True


def try_acquire_reserved_slot() -> bool:
    """
    Atomically check and acquire a reserved slot for HIGH-priority jobs.

    Replaces the non-atomic can_use_reserved_slot() + increment_reserved_slots_usage()
    call pair that was vulnerable to a TOCTOU race under concurrent workers.

    Returns:
        True if a reserved slot was acquired, False if the limit is reached.
    """
    return _try_acquire_slot("worker:reserved_slots_usage", WORKER_RESERVED_SLOTS)


def try_acquire_shared_slot() -> bool:
    """
    Atomically check and acquire a shared slot (any priority).

    Replaces the non-atomic can_use_shared_slot() + increment_shared_slots_usage()
    call pair.

    Returns:
        True if a shared slot was acquired, False if the limit is reached.
    """
    return _try_acquire_slot("worker:shared_slots_usage", WORKER_SHARED_SLOTS)


def get_reserved_slots_usage() -> int:
    """
    Get current number of reserved slots in use.

    Reserved slots are for HIGH priority jobs only.

    Returns:
        Number of reserved slots currently in use
    """
    key = "worker:reserved_slots_usage"
    return cache.get(key, 0)


def increment_reserved_slots_usage() -> int:
    """
    Increment reserved slots usage counter.

    Returns:
        New reserved slots usage count
    """
    key = "worker:reserved_slots_usage"
    cache.get_or_set(key, 0, timeout=86400)
    new_count = cache.incr(key)
    # Set expiration if cache backend supports it (Redis does, LocMemCache doesn't)
    try:
        cache.expire(key, 86400)
    except AttributeError:
        # LocMemCache doesn't support expire, but that's fine for tests
        pass
    return new_count


def decrement_reserved_slots_usage() -> int:
    """
    Decrement reserved slots usage counter.

    Returns:
        New reserved slots usage count
    """
    key = "worker:reserved_slots_usage"
    current = cache.get(key, 0)
    if current > 0:
        new_count = cache.decr(key)
        return new_count
    return 0


def get_shared_slots_usage() -> int:
    """
    Get current number of shared slots in use.

    Shared slots can be used by any priority level.

    Returns:
        Number of shared slots currently in use
    """
    key = "worker:shared_slots_usage"
    return cache.get(key, 0)


def increment_shared_slots_usage() -> int:
    """
    Increment shared slots usage counter.

    Returns:
        New shared slots usage count
    """
    key = "worker:shared_slots_usage"
    cache.get_or_set(key, 0, timeout=86400)
    new_count = cache.incr(key)
    # Set expiration if cache backend supports it (Redis does, LocMemCache doesn't)
    try:
        cache.expire(key, 86400)
    except AttributeError:
        # LocMemCache doesn't support expire, but that's fine for tests
        pass
    return new_count


def decrement_shared_slots_usage() -> int:
    """
    Decrement shared slots usage counter.

    Returns:
        New shared slots usage count
    """
    key = "worker:shared_slots_usage"
    current = cache.get(key, 0)
    if current > 0:
        new_count = cache.decr(key)
        return new_count
    return 0


def can_use_reserved_slot() -> bool:
    """
    Check if a reserved slot is available for HIGH priority jobs.

    Returns:
        True if reserved slot is available, False otherwise
    """
    reserved_usage = get_reserved_slots_usage()
    return reserved_usage < WORKER_RESERVED_SLOTS


def can_use_shared_slot() -> bool:
    """
    Check if a shared slot is available for any priority job.

    Returns:
        True if shared slot is available, False otherwise
    """
    shared_usage = get_shared_slots_usage()
    return shared_usage < WORKER_SHARED_SLOTS


def can_process_job(queue_name: str, job_id: str | None = None) -> tuple[bool, str | None]:
    """
    Check if a job can be processed based on reserved slots and starvation prevention.

    Args:
        queue_name: Queue name ('job_critical', 'job_default', 'job_low')
        job_id: Optional job ID for starvation prevention check

    Returns:
        Tuple of (can_process: bool, reason: Optional[str])
    """
    # HIGH priority jobs (job_critical) can use reserved slots or shared slots
    if queue_name == "job_critical":
        if can_use_reserved_slot():
            return True, "reserved_slot"
        elif can_use_shared_slot():
            return True, "shared_slot"
        else:
            return False, "no_slots_available"

    # Check starvation prevention for NORMAL priority jobs
    if queue_name == "job_default" and job_id and should_elevate_job(job_id, queue_name):
        # Elevated job can use reserved slots or shared slots
        if can_use_reserved_slot():
            return True, "elevated_reserved_slot"
        elif can_use_shared_slot():
            return True, "elevated_shared_slot"
        else:
            return False, "no_slots_available"

    # NORMAL and LOW priority jobs can only use shared slots
    if queue_name in ["job_default", "job_low"]:
        if can_use_shared_slot():
            return True, "shared_slot"
        else:
            return False, "no_shared_slots_available"

    return False, "unknown_queue"
