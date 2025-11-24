"""
Job Utilities

Utilities for creating and managing jobs.
"""
from typing import Optional, Dict, Any
from django_rq import get_queue
from django.conf import settings
from .models import Job, JobType, JobStatus


# Default timeouts per job type (in seconds)
JOB_TIMEOUTS = {
    JobType.DQ_RUN: 1800,  # 30 minutes
    JobType.COMPLIANCE_RUN: 1800,  # 30 minutes
    JobType.CONTRACT_VALIDATION: 300,  # 5 minutes
    JobType.SEMANTIC_MAPPING: 60,  # 1 minute
    JobType.CONTRACT_MIGRATION: 600,  # 10 minutes
}

# Worker concurrency limits
WORKER_MAX_CONCURRENCY = getattr(settings, 'WORKER_MAX_CONCURRENCY', 4)
WORKER_MAX_CONCURRENCY_PER_TENANT = getattr(settings, 'WORKER_MAX_CONCURRENCY_PER_TENANT', 2)


def get_job_timeout(job_type: str) -> int:
    """
    Get timeout for a job type.
    
    Args:
        job_type: Job type string
    
    Returns:
        Timeout in seconds
    """
    return JOB_TIMEOUTS.get(job_type, 600)  # Default 10 minutes


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
    """
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
    
    # Enqueue job for processing
    queue = get_queue(queue_name)
    from .tasks import process_job  # Import here to avoid circular imports
    queue.enqueue(process_job, str(job.id), job_type=job_type, timeout=timeout_seconds)
    
    return job


def get_queue_for_job_type(job_type: str) -> str:
    """
    Determine which queue to use for a job type.
    
    Args:
        job_type: Job type string
    
    Returns:
        Queue name ('default', 'high', 'low')
    """
    # High priority queue for long-running jobs
    if job_type in [JobType.DQ_RUN, JobType.COMPLIANCE_RUN]:
        return 'high'
    
    # Low priority queue for quick jobs
    if job_type in [JobType.CONTRACT_VALIDATION]:
        return 'low'
    
    # Default queue for others
    return 'default'

