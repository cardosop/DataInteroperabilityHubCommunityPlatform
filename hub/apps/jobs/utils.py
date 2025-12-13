"""
Job Utilities

Utilities for creating and managing jobs.
"""
from typing import Optional, Dict, Any, Tuple
from django_rq import get_queue
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from .models import Job, JobType, JobStatus
import structlog
import time

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
}

# Maximum retry attempts per job type
JOB_MAX_RETRIES = {
    JobType.DQ_RUN: 3,  # DQ runs can retry up to 3 times
    JobType.COMPLIANCE_RUN: 3,  # Compliance runs can retry up to 3 times
    JobType.CONTRACT_VALIDATION: 2,  # Contract validation can retry up to 2 times
    JobType.SEMANTIC_MAPPING: 2,  # Semantic mapping can retry up to 2 times
    JobType.CONTRACT_MIGRATION: 1,  # Contract migration typically doesn't need retries
    JobType.SCHEDULED_INGESTION: 2,  # Scheduled ingestion can retry up to 2 times
    JobType.RETENTION_POLICY_ENFORCEMENT: 1,  # Retention policy enforcement typically doesn't need retries
    JobType.SEARCH_INDEX_UPDATE: 2,  # Search index update can retry up to 2 times
}

# Base delay for exponential backoff (in seconds)
JOB_RETRY_BASE_DELAY = 60  # Start with 1 minute delay

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


def get_job_max_retries(job_type: str) -> int:
    """
    Get maximum retry attempts for a job type.
    
    Args:
        job_type: Job type string
    
    Returns:
        Maximum retry attempts
    """
    return JOB_MAX_RETRIES.get(job_type, 2)  # Default 2 retries


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
        'timeout', 'timed out', 'connection', 'unavailable', 'network',
        'temporary', 'retry', 'service unavailable', '503', '502', '504'
    ]
    
    return any(keyword in error_str for keyword in transient_keywords)


def calculate_retry_delay(retry_count: int, base_delay: int = JOB_RETRY_BASE_DELAY) -> int:
    """
    Calculate retry delay using exponential backoff.
    
    Formula: base_delay * (2 ^ retry_count)
    - Retry 1: 60 seconds (1 minute)
    - Retry 2: 120 seconds (2 minutes)
    - Retry 3: 240 seconds (4 minutes)
    
    Args:
        retry_count: Current retry attempt (0-indexed)
        base_delay: Base delay in seconds (default: 60)
    
    Returns:
        Delay in seconds
    """
    return base_delay * (2 ** retry_count)


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
    retry_count = job_obj.details_json.get('retry_count', 0)
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
            message=f"Job {job_obj.id} exceeded max retries ({max_retries})"
        )
        return False
    
    # Increment retry count
    new_retry_count = retry_count + 1
    if job_obj.details_json is None:
        job_obj.details_json = {}
    job_obj.details_json['retry_count'] = new_retry_count
    job_obj.details_json['last_retry_error'] = str(exception)
    job_obj.details_json['last_retry_at'] = timezone.now().isoformat()
    
    # Calculate retry delay
    retry_delay = calculate_retry_delay(retry_count)
    
    # Reset job status to PENDING for retry
    job_obj.status = JobStatus.PENDING
    job_obj.started_at = None  # Reset started_at for retry
    job_obj.completed_at = None  # Reset completed_at for retry
    job_obj.error_message = None  # Clear error message
    job_obj.save(update_fields=['status', 'started_at', 'completed_at', 'error_message', 'details_json', 'updated_at'])
    
    # Re-enqueue job with delay
    queue_name = get_queue_for_job_type(job_type)
    queue = get_queue(queue_name)
    
    # Use django-rq's enqueue_in to schedule job with delay
    # Import here to avoid circular imports
    from django_rq import enqueue_in
    from .tasks import process_job
    enqueue_in(
        retry_delay,
        process_job,
        str(job_obj.id),
        job_type=job_type,
        timeout=get_job_timeout(job_type)
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
        message=f"Job {job_obj.id} scheduled for retry {new_retry_count}/{max_retries} after {retry_delay}s"
    )
    
    return True


def check_tenant_job_limits(tenant_id: str) -> Tuple[bool, Optional[str]]:
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
            message="Failed to check tenant job limits, allowing job creation"
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
    
    Args:
        tenant_id: Tenant UUID as string
        counter_type: "running" or "queued"
    """
    key = f"job:tenant:{tenant_id}:{counter_type}"
    try:
        # Use get_or_set to ensure key exists, then increment
        # This handles both Redis and LocMemCache backends
        current = cache.get_or_set(key, 0, timeout=86400)
        cache.incr(key)
        # Ensure expiration is set (24 hours) - refresh it after increment
        if hasattr(cache, 'expire'):
            cache.expire(key, 86400)
        
        # Update Prometheus metrics
        try:
            from hub.apps.observability.otel_metrics import tenant_running_jobs, tenant_queued_jobs
            new_count = cache.get(key, 0)
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
            message="Failed to increment tenant job counter"
        )


def decrement_tenant_job_counter(tenant_id: str, counter_type: str = "running") -> None:
    """
    Decrement tenant job counter in Redis and update Prometheus metrics.
    
    Args:
        tenant_id: Tenant UUID as string
        counter_type: "running" or "queued"
    """
    key = f"job:tenant:{tenant_id}:{counter_type}"
    try:
        current = cache.get(key, 0)
        if current > 0:
            cache.decr(key)
        # Ensure expiration is set (24 hours)
        if hasattr(cache, 'expire'):
            cache.expire(key, 86400)
        
        # Update Prometheus metrics
        try:
            from hub.apps.observability.otel_metrics import tenant_running_jobs, tenant_queued_jobs
            new_count = cache.get(key, 0)
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
            message="Failed to decrement tenant job counter"
        )


def create_job(
    tenant=None,
    user=None,
    job_type: str = None,
    resource_type: str = None,
    resource_id: str = None,
    details_json: Optional[Dict[str, Any]] = None,
    timeout_seconds: Optional[int] = None,
    queue_name: str = 'default'
) -> Job:
    """
    Create a job and enqueue it for processing.
    
    Checks tenant job limits (concurrency and queue depth) before creating job.
    Rejects job creation if limits are exceeded.
    
    Args:
        tenant: Tenant instance (optional)
        user: User instance (optional, alias for created_by)
        job_type: Job type (from JobType enum)
        resource_type: Resource type (CONTRACT, DATASET, FILE, ASSET, etc.)
        resource_id: UUID of the resource
        details_json: Additional job details (optional)
        timeout_seconds: Timeout in seconds (optional, defaults to job type default)
        queue_name: Queue name ('default', 'high', 'low')
    
    Returns:
        Created Job instance
    
    Raises:
        ValidationError: If tenant job limits are exceeded
    """
    # Check tenant job limits if tenant is provided
    if tenant:
        can_create, error_message = check_tenant_job_limits(str(tenant.id))
        if not can_create:
            raise ValidationError(error_message)
    
    # Get timeout for job type if not provided
    if timeout_seconds is None:
        timeout_seconds = get_job_timeout(job_type) if job_type else 600
    
    # Create job record
    job = Job.objects.create(
        tenant=tenant,
        type=job_type,
        status=JobStatus.PENDING,
        resource_type=resource_type,
        resource_id=resource_id,
        created_by=user,
        timeout_seconds=timeout_seconds,
        details_json=details_json or {}
    )
    
    # Increment queued counter before enqueuing
    if tenant:
        increment_tenant_job_counter(str(tenant.id), "queued")
        logger.info(
            "job_created",
            job_id=str(job.id),
            tenant_id=str(tenant.id),
            job_type=job_type,
            message=f"Job created and queued for tenant {tenant.id}"
        )
    
    # Track job enqueue timestamp for starvation prevention
    enqueue_timestamp = time.time()
    cache.set(
        f"job:enqueue_time:{job.id}",
        enqueue_timestamp,
        timeout=86400  # 24 hours
    )
    
    # Determine queue name from job type if not explicitly provided
    if queue_name == 'default' and job_type:
        queue_name = get_queue_for_job_type(job_type)
    
    # Enqueue job for processing
    try:
        queue = get_queue(queue_name)
        from .tasks import process_job  # Import here to avoid circular imports
        queue.enqueue(process_job, str(job.id), job_type=job_type, timeout=timeout_seconds)
    except Exception as e:
        # Handle Redis connection failures gracefully (e.g., in test environments)
        # Log warning but don't fail job creation - job remains in PENDING status
        # so it can be manually processed or retried when Redis becomes available
        logger.warning(
            "job_enqueue_failed",
            job_id=str(job.id),
            job_type=job_type,
            error=str(e),
            message="Failed to enqueue job (Redis may be unavailable). Job record created but not queued."
        )
        # Note: Job remains in PENDING status - can be manually processed or retried
    
    return job


def get_queue_for_job_type(job_type: str) -> str:
    """
    Get queue name for a job type.
    
    Queue mapping:
    - DQ_RUN, COMPLIANCE_RUN → job_critical (HIGH priority)
    - SEMANTIC_MAPPING, CONTRACT_MIGRATION → job_default (NORMAL priority)
    - CONTRACT_VALIDATION → job_low (LOW priority)
    - SCHEDULED_INGESTION → job_default (NORMAL priority, can be long-running)
    
    Args:
        job_type: Job type string
    
    Returns:
        Queue name
    """
    # HIGH priority queue (job_critical) for long-running critical jobs
    if job_type in [JobType.DQ_RUN, JobType.COMPLIANCE_RUN]:
        return 'job_critical'
    
    # LOW priority queue (job_low) for quick validation jobs
    if job_type in [JobType.CONTRACT_VALIDATION]:
        return 'job_low'
    
    # NORMAL priority queue (job_default) for standard jobs
    # Includes: SEMANTIC_MAPPING, CONTRACT_MIGRATION, SCHEDULED_INGESTION, RETENTION_POLICY_ENFORCEMENT, SEARCH_INDEX_UPDATE
    return 'job_default'


def get_job_enqueue_timestamp(job_id: str) -> Optional[float]:
    """
    Get job enqueue timestamp from Redis.
    
    Args:
        job_id: Job UUID as string
    
    Returns:
        Enqueue timestamp (Unix timestamp) or None if not found
    """
    key = f"job:enqueue_time:{job_id}"
    return cache.get(key)


def get_job_wait_time(job_id: str) -> Optional[float]:
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
    if queue_name != 'job_default':
        return False
    
    wait_time = get_job_wait_time(job_id)
    if wait_time is None:
        return False
    
    return wait_time > WORKER_STARVATION_THRESHOLD_SECONDS


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
    current = cache.get_or_set(key, 0, timeout=86400)
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
    current = cache.get_or_set(key, 0, timeout=86400)
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


def can_process_job(queue_name: str, job_id: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """
    Check if a job can be processed based on reserved slots and starvation prevention.
    
    Args:
        queue_name: Queue name ('job_critical', 'job_default', 'job_low')
        job_id: Optional job ID for starvation prevention check
    
    Returns:
        Tuple of (can_process: bool, reason: Optional[str])
    """
    # HIGH priority jobs (job_critical) can use reserved slots or shared slots
    if queue_name == 'job_critical':
        if can_use_reserved_slot():
            return True, "reserved_slot"
        elif can_use_shared_slot():
            return True, "shared_slot"
        else:
            return False, "no_slots_available"
    
    # Check starvation prevention for NORMAL priority jobs
    if queue_name == 'job_default' and job_id:
        if should_elevate_job(job_id, queue_name):
            # Elevated job can use reserved slots or shared slots
            if can_use_reserved_slot():
                return True, "elevated_reserved_slot"
            elif can_use_shared_slot():
                return True, "elevated_shared_slot"
            else:
                return False, "no_slots_available"
    
    # NORMAL and LOW priority jobs can only use shared slots
    if queue_name in ['job_default', 'job_low']:
        if can_use_shared_slot():
            return True, "shared_slot"
        else:
            return False, "no_shared_slots_available"
    
    return False, "unknown_queue"

